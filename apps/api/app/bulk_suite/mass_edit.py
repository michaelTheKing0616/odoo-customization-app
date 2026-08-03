"""Universal mass field edit (BLK-2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.transitions import (
    DEFAULT_RECORD_CAP,
    BulkRunResult,
    BulkSuiteError,
    PerRecordResult,
    _load_display_names,
    resolve_record_ids,
)
from app.protected_enforcement import (
    is_custom_field,
    is_custom_model,
    manifest_for_connection,
    protected_models_for,
)

_CHATTER_MASS_EDIT_FIELDS = frozenset({"activity_ids"})


@dataclass
class MassEditPreviewRow:
    id: int
    display_name: str
    before: dict[str, Any]
    after: dict[str, Any]


@dataclass
class MassEditResult(BulkRunResult):
    values: dict[str, Any] = field(default_factory=dict)
    preview: list[MassEditPreviewRow] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["values"] = dict(self.values)
        data["preview"] = [
            {
                "id": row.id,
                "display_name": row.display_name,
                "before": row.before,
                "after": row.after,
            }
            for row in self.preview
        ]
        return data


class MassEditValidationError(BulkSuiteError):
    pass


def _fields_get(client: OdooClient, model: str) -> dict[str, dict[str, Any]]:
    return client.execute_kw(model, "fields_get", [], {"attributes": ["type", "readonly", "required", "selection", "relation"]})


def check_mass_edit_policy(
    manifest: dict[str, Any],
    *,
    model: str,
    field_names: list[str],
) -> None:
    tier = protected_models_for(manifest, model)
    if tier == "tier_1" and not is_custom_model(model):
        if field_names and all(name in _CHATTER_MASS_EDIT_FIELDS for name in field_names):
            return
        raise MassEditValidationError(
            f"Mass edit on tier-1 model {model!r} is blocked — "
            "only whitelisted chatter fields are allowed."
        )
    if tier == "tier_2" and not is_custom_model(model):
        for name in field_names:
            if not is_custom_field(name):
                raise MassEditValidationError(
                    f"Mass edit on tier-2 model {model!r} may only touch x_* custom fields; "
                    f"got {name!r}."
                )


def _coerce_value(
    client: OdooClient,
    model: str,
    field_name: str,
    meta: dict[str, Any],
    raw: Any,
) -> Any:
    ftype = str(meta.get("type") or "")
    if meta.get("readonly"):
        raise MassEditValidationError(f"Field {field_name!r} is readonly")
    if ftype in {"one2many", "many2many"}:
        raise MassEditValidationError(
            f"Field {field_name!r} ({ftype}) is not supported for mass edit — use Odoo UI or server actions."
        )
    if ftype == "selection":
        selection = meta.get("selection") or []
        keys = {str(k) for k, _label in selection}
        val = str(raw)
        if val not in keys:
            raise MassEditValidationError(
                f"Invalid selection key {val!r} for {field_name!r}; allowed: {sorted(keys)}"
            )
        return val
    if ftype == "many2one":
        rid = int(raw)
        rel = str(meta.get("relation") or "")
        if not rel:
            raise MassEditValidationError(f"Field {field_name!r} missing relation metadata")
        exists = client.execute_kw(rel, "search", [[("id", "=", rid)]], {"limit": 1})
        if not exists:
            raise MassEditValidationError(f"Related record id={rid} not found for {field_name!r}")
        return rid
    if ftype == "boolean":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if ftype in {"integer", "float", "monetary"}:
        return int(raw) if ftype == "integer" else float(raw)
    return raw


def validate_mass_edit_values(
    client: OdooClient,
    *,
    model: str,
    values: dict[str, Any],
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not values:
        raise MassEditValidationError("values must include at least one field")
    names = list(values.keys())
    if manifest is not None:
        check_mass_edit_policy(manifest, model=model, field_names=names)
    fg = _fields_get(client, model)
    coerced: dict[str, Any] = {}
    for name, raw in values.items():
        if name not in fg:
            raise MassEditValidationError(f"Unknown field {name!r} on {model!r}")
        meta = fg[name]
        if str(meta.get("type") or "") == "binary":
            raise MassEditValidationError(f"Field {field_name!r} type binary is not mass-editable here")
        coerced[name] = _coerce_value(client, model, name, meta, raw)
    return coerced


def _preview_rows(
    client: OdooClient,
    model: str,
    record_ids: list[int],
    values: dict[str, Any],
    *,
    limit: int = 20,
) -> list[MassEditPreviewRow]:
    sample = record_ids[:limit]
    names = _load_display_names(client, model, sample)
    fields = list(values.keys())
    rows = client.execute_kw(model, "read", [sample], {"fields": fields})
    out: list[MassEditPreviewRow] = []
    for row in rows:
        rid = int(row["id"])
        before = {f: row.get(f) for f in fields}
        after = {**before, **values}
        out.append(
            MassEditPreviewRow(
                id=rid,
                display_name=names.get(rid, str(rid)),
                before=before,
                after=after,
            )
        )
    return out


def run_mass_edit(
    client: OdooClient,
    *,
    model: str,
    record_ids: list[int],
    values: dict[str, Any],
    dry_run: bool = True,
    run_id: str | None = None,
    manifest: dict[str, Any] | None = None,
) -> MassEditResult:
    run_id = run_id or str(uuid.uuid4())
    coerced = validate_mass_edit_values(client, model=model, values=values, manifest=manifest)
    total = len(record_ids)
    names = _load_display_names(client, model, record_ids)

    if total == 0:
        return MassEditResult(
            run_id=run_id,
            operation="mass_edit",
            model=model,
            total=0,
            succeeded=0,
            failed=0,
            per_record=[],
            dry_run=dry_run,
            values=coerced,
            message="No records matched the selection.",
        )

    preview = _preview_rows(client, model, record_ids, coerced) if dry_run else []

    if dry_run:
        per = [
            PerRecordResult(id=rid, display_name=names.get(rid, str(rid)), ok=True)
            for rid in record_ids
        ]
        return MassEditResult(
            run_id=run_id,
            operation="mass_edit",
            model=model,
            total=total,
            succeeded=total,
            failed=0,
            per_record=per,
            dry_run=True,
            values=coerced,
            preview=preview,
            message=f"Dry-run: would write {coerced} on {total} record(s).",
        )

    per_record: list[PerRecordResult] = []
    succeeded = 0
    failed = 0
    try:
        client.execute_kw(model, "write", [record_ids, coerced])
        for rid in record_ids:
            per_record.append(
                PerRecordResult(id=rid, display_name=names.get(rid, str(rid)), ok=True)
            )
        succeeded = total
    except Exception:  # noqa: BLE001
        for rid in record_ids:
            try:
                client.execute_kw(model, "write", [[rid], coerced])
                per_record.append(
                    PerRecordResult(id=rid, display_name=names.get(rid, str(rid)), ok=True)
                )
                succeeded += 1
            except Exception as row_exc:  # noqa: BLE001
                per_record.append(
                    PerRecordResult(
                        id=rid,
                        display_name=names.get(rid, str(rid)),
                        ok=False,
                        error=str(row_exc),
                    )
                )
                failed += 1

    return MassEditResult(
        run_id=run_id,
        operation="mass_edit",
        model=model,
        total=total,
        succeeded=succeeded,
        failed=failed,
        per_record=per_record,
        dry_run=False,
        values=coerced,
        preview=[],
        message=(
            f"mass_edit: {succeeded} ok, {failed} failed of {total} record(s)"
            if failed
            else f"mass_edit: updated {succeeded} record(s)."
        ),
    )


def resolve_and_cap(
    client: OdooClient,
    *,
    model: str,
    ids: list[int] | None,
    domain: list[Any] | str | None,
    cap: int = DEFAULT_RECORD_CAP,
) -> list[int]:
    return resolve_record_ids(client, model=model, ids=ids, domain=domain, cap=cap)
