"""Stored computed-field recompute via dependency touch + probe honesty (BLK-7)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field as dc_field
from typing import Any

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.transitions import BulkRunResult, BulkSuiteError, PerRecordResult, _load_display_names
from app.hosting import hosting_hint_from_url

_TRACK_CTX = {
    "tracking_disable": True,
    "mail_create_nosubscribe": True,
    "mail_notrack": True,
}


class RecomputeValidationError(BulkSuiteError):
    pass


@dataclass
class RecomputeProbeResult:
    ok: bool
    field: str
    model: str
    dependencies: list[str]
    probe_ids: list[int]
    message: str
    honesty_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "field": self.field,
            "model": self.model,
            "dependencies": list(self.dependencies),
            "probe_ids": list(self.probe_ids),
            "message": self.message,
            "honesty_message": self.honesty_message,
        }


@dataclass
class RecomputeRunResult(BulkRunResult):
    field: str = ""
    dependencies: list[str] = dc_field(default_factory=list)
    probe: RecomputeProbeResult | None = dc_field(default=None)

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["field"] = self.field
        data["dependencies"] = list(self.dependencies)
        data["probe"] = self.probe.to_dict() if self.probe else None
        return data


def honesty_message(hosting_hint: str) -> str:
    label = {
        "online": "Odoo Online",
        "odoo_sh": "Odoo.sh",
        "self_hosted": "this hosting",
        "unknown": "this hosting",
    }.get(hosting_hint, "this hosting")
    return (
        f"This fix needs server shell access, which {label} doesn't "
        "provide. No changes were made. If you have an Odoo.sh or self-hosted copy, run it there."
    )


def _field_meta(client: OdooClient, model: str, field_name: str) -> dict[str, Any]:
    fg = client.execute_kw(model, "fields_get", [[field_name]], {"attributes": ["type", "compute", "depends", "store", "readonly"]})
    if field_name not in fg:
        raise RecomputeValidationError(f"Field {field_name!r} not found on {model!r}")
    return fg[field_name]


def _parse_depends(meta: dict[str, Any]) -> list[str]:
    raw = meta.get("depends")
    if isinstance(raw, str) and raw.strip():
        return [p.strip() for p in raw.split(",") if p.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw if str(x).strip()]
    return []


def probe_recompute(
    client: OdooClient,
    *,
    model: str,
    field_name: str,
    record_ids: list[int],
    hosting_hint: str | None = None,
) -> RecomputeProbeResult:
    field_name = field_name.strip()
    meta = _field_meta(client, model, field_name)
    deps = _parse_depends(meta)
    is_stored_compute = bool(meta.get("store")) and (
        bool(meta.get("compute")) or bool(deps)
    )
    if not is_stored_compute:
        msg = honesty_message(hosting_hint or "unknown")
        reason = (
            f"Field {field_name!r} is not a stored computed field."
            if not meta.get("store")
            else f"Field {field_name!r} is not a computed field."
        )
        return RecomputeProbeResult(
            ok=False,
            field=field_name,
            model=model,
            dependencies=[],
            probe_ids=[],
            message=reason,
            honesty_message=msg,
        )
    if not deps:
        msg = honesty_message(hosting_hint or "unknown")
        return RecomputeProbeResult(
            ok=False,
            field=field_name,
            model=model,
            dependencies=[],
            probe_ids=[],
            message=f"Could not introspect compute dependencies for {field_name!r}.",
            honesty_message=msg,
        )

    probe_ids = list(dict.fromkeys(int(i) for i in record_ids))[:3]
    if not probe_ids:
        raise RecomputeValidationError("No records available for recompute probe")

    read_fields = list(dict.fromkeys([field_name, *deps]))
    try:
        before_rows = client.execute_kw(model, "read", [probe_ids], {"fields": read_fields})
    except OdooClientError as exc:
        msg = honesty_message(hosting_hint or "unknown")
        return RecomputeProbeResult(
            ok=False,
            field=field_name,
            model=model,
            dependencies=deps,
            probe_ids=probe_ids,
            message=f"Probe read failed: {exc}",
            honesty_message=msg,
        )

    for row in before_rows:
        rid = int(row["id"])
        touch_vals = {dep: row.get(dep) for dep in deps if dep in row}
        if not touch_vals:
            msg = honesty_message(hosting_hint or "unknown")
            return RecomputeProbeResult(
                ok=False,
                field=field_name,
                model=model,
                dependencies=deps,
                probe_ids=probe_ids,
                message=f"Probe could not read dependency values on record {rid}.",
                honesty_message=msg,
            )
        try:
            client.execute_kw(
                model,
                "write",
                [[rid], touch_vals],
                {"context": _TRACK_CTX},
            )
        except OdooClientError as exc:
            msg = honesty_message(hosting_hint or "unknown")
            return RecomputeProbeResult(
                ok=False,
                field=field_name,
                model=model,
                dependencies=deps,
                probe_ids=probe_ids,
                message=f"Probe touch write failed on record {rid}: {exc}",
                honesty_message=msg,
            )

    try:
        after_rows = client.execute_kw(model, "read", [probe_ids], {"fields": [field_name]})
    except OdooClientError as exc:
        msg = honesty_message(hosting_hint or "unknown")
        return RecomputeProbeResult(
            ok=False,
            field=field_name,
            model=model,
            dependencies=deps,
            probe_ids=probe_ids,
            message=f"Probe re-read failed: {exc}",
            honesty_message=msg,
        )

    before_map = {int(r["id"]): r.get(field_name) for r in before_rows}
    after_map = {int(r["id"]): r.get(field_name) for r in after_rows}
    if len(after_map) != len(before_map):
        msg = honesty_message(hosting_hint or "unknown")
        return RecomputeProbeResult(
            ok=False,
            field=field_name,
            model=model,
            dependencies=deps,
            probe_ids=probe_ids,
            message="Probe could not confirm recompute on all sample records.",
            honesty_message=msg,
        )

    return RecomputeProbeResult(
        ok=True,
        field=field_name,
        model=model,
        dependencies=deps,
        probe_ids=probe_ids,
        message=(
            f"Probe ok on {len(probe_ids)} record(s): touch write on {deps} "
            f"for stored compute field {field_name!r}."
        ),
    )


def run_recompute(
    client: OdooClient,
    *,
    model: str,
    field_name: str,
    record_ids: list[int],
    dry_run: bool = True,
    run_id: str | None = None,
    hosting_hint: str | None = None,
) -> RecomputeRunResult:
    run_id = run_id or str(uuid.uuid4())
    hint = hosting_hint or hosting_hint_from_url(getattr(getattr(client, "config", None), "url", None))
    probe = probe_recompute(
        client,
        model=model,
        field_name=field_name,
        record_ids=record_ids,
        hosting_hint=hint,
    )
    if not probe.ok:
        msg = probe.honesty_message or probe.message
        return RecomputeRunResult(
            run_id=run_id,
            operation="bulk_recompute",
            model=model,
            total=len(record_ids),
            succeeded=0,
            failed=len(record_ids),
            per_record=[
                PerRecordResult(id=rid, display_name=str(rid), ok=False, error=msg)
                for rid in record_ids
            ],
            dry_run=dry_run,
            message=msg,
            field=field_name,
            dependencies=probe.dependencies,
            probe=probe,
        )

    names = _load_display_names(client, model, record_ids)
    per_record: list[PerRecordResult] = []
    succeeded = 0
    failed = 0

    read_fields = list(dict.fromkeys([field_name, *probe.dependencies]))
    rows = client.execute_kw(model, "read", [record_ids], {"fields": read_fields})
    row_map = {int(r["id"]): r for r in rows}

    for rid in record_ids:
        label = names.get(rid, str(rid))
        row = row_map.get(rid)
        if not row:
            failed += 1
            per_record.append(PerRecordResult(id=rid, display_name=label, ok=False, error="not found"))
            continue
        touch_vals = {dep: row.get(dep) for dep in probe.dependencies if dep in row}
        if dry_run:
            succeeded += 1
            per_record.append(PerRecordResult(id=rid, display_name=label, ok=True, error="dry-run"))
            continue
        try:
            client.execute_kw(
                model,
                "write",
                [[rid], touch_vals],
                {"context": _TRACK_CTX},
            )
            succeeded += 1
            per_record.append(PerRecordResult(id=rid, display_name=label, ok=True))
        except Exception as exc:  # noqa: BLE001
            failed += 1
            per_record.append(PerRecordResult(id=rid, display_name=label, ok=False, error=str(exc)))

    return RecomputeRunResult(
        run_id=run_id,
        operation="bulk_recompute",
        model=model,
        total=len(record_ids),
        succeeded=succeeded,
        failed=failed,
        per_record=per_record,
        dry_run=dry_run,
        message=(
            f"Recompute touch on {field_name!r}: {succeeded} ok, {failed} failed of {len(record_ids)}"
            if not dry_run
            else f"Dry-run: would touch dependencies {probe.dependencies} on {len(record_ids)} record(s)"
        ),
        field=field_name,
        dependencies=probe.dependencies,
        probe=probe,
    )
