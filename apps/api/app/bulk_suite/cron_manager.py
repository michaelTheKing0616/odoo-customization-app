"""Cron manager — plain-language descriptions + run-now (BLK-4)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.transitions import BulkRunResult, BulkSuiteError, PerRecordResult

RunVia = Literal["method_direct_trigger", "model_method", "dry_run"]
_KNOWN_CRON_HINTS: dict[str, str] = {
    "mail: email queue manager": "process outgoing mail queue",
    "notification": "send pending notifications",
    "payment": "process payment transactions",
    "autovacuum": "clean up old database records",
    "session": "garbage-collect expired web sessions",
    "publisher": "publish module updates metadata",
    "digest": "send periodic digest emails",
    "sms": "dispatch queued SMS messages",
}

_INTERVAL_LABELS = {
    "minutes": "minute",
    "hours": "hour",
    "days": "day",
    "weeks": "week",
    "months": "month",
}

_PROBE_CACHE: dict[int, dict[str, Any]] = {}


class CronManagerError(BulkSuiteError):
    pass


@dataclass
class CronRowEnriched:
    id: int
    name: str
    model_name: str | None
    interval_number: int | None
    interval_type: str | None
    active: bool
    nextcall: str | None
    lastcall: str | None
    description: str
    state: str | None = None
    code_preview: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "model_name": self.model_name,
            "interval_number": self.interval_number,
            "interval_type": self.interval_type,
            "active": self.active,
            "nextcall": self.nextcall,
            "lastcall": self.lastcall,
            "description": self.description,
            "state": self.state,
            "code_preview": self.code_preview,
        }


@dataclass
class CronRunResult(BulkRunResult):
    cron_ids: list[int] = field(default_factory=list)
    run_via: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["cron_ids"] = list(self.cron_ids)
        data["run_via"] = self.run_via
        return data


def _m2o_name(value: Any) -> str | None:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[1])
    return None


def _interval_phrase(number: int | None, itype: str | None) -> str:
    n = int(number or 1)
    unit = _INTERVAL_LABELS.get(str(itype or "days"), str(itype or "day"))
    if n == 1:
        return f"Every {unit}"
    return f"Every {n} {unit}s"


def _known_hint(name: str) -> str | None:
    lower = name.lower()
    for key, hint in _KNOWN_CRON_HINTS.items():
        if key in lower:
            return hint
    return None


def _parse_model_method(code: str) -> str | None:
    text = (code or "").strip()
    m = re.match(r"^model\.([a-zA-Z_]\w*)\(\s*\)\s*$", text)
    if m:
        return m.group(1)
    m = re.search(r"\.([a-zA-Z_]\w*)\(\s*\)\s*$", text)
    if m:
        return m.group(1)
    return None


def render_cron_description(row: dict[str, Any]) -> str:
    name = str(row.get("name") or row.get("cron_name") or "Scheduled action")
    model = row.get("model_name") or _m2o_name(row.get("model_id")) or "unknown model"
    every = _interval_phrase(
        int(row["interval_number"]) if row.get("interval_number") not in (None, False) else None,
        row.get("interval_type"),
    )
    hint = _known_hint(name)
    if not hint:
        code = str(row.get("code") or "").strip()
        method = _parse_model_method(code)
        if method:
            hint = f"runs {model}.{method}()"
        elif code:
            hint = "runs server action code"
        else:
            hint = f"runs on {model}"
    active = "active" if row.get("active", True) else "inactive"
    return f"{every}: {hint} ({name}; {active})"


def probe_run_method(client: OdooClient) -> dict[str, Any]:
    major = getattr(getattr(client, "capabilities", None), "major", None)
    key = int(major) if major is not None else 0
    if key in _PROBE_CACHE:
        return dict(_PROBE_CACHE[key])

    probe: dict[str, Any] = {
        "major": major,
        "primary": "method_direct_trigger",
        "primary_available": True,
        "fallback": "model_method",
        "note": "Assumed available on GA majors until first failure",
    }
    try:
        fg = client.execute_kw("ir.cron", "fields_get", [], {"attributes": []})
        probe["primary_available"] = "method_direct_trigger" in fg or True
    except OdooClientError as exc:
        probe["primary_available"] = False
        probe["error"] = str(exc)
    _PROBE_CACHE[key] = probe
    return dict(probe)


def list_crons_enriched(
    client: OdooClient,
    *,
    q: str | None = None,
    active: bool | None = None,
    limit: int = 300,
) -> tuple[list[CronRowEnriched], dict[str, Any]]:
    domain: list[Any] = []
    if q:
        domain.append(("name", "ilike", q))
    if active is not None:
        domain.append(("active", "=", active))
    fields = [
        "name",
        "cron_name",
        "model_id",
        "model_name",
        "interval_number",
        "interval_type",
        "active",
        "nextcall",
        "lastcall",
        "state",
        "code",
    ]
    available = set(client.execute_kw("ir.cron", "fields_get", [], {"attributes": []}).keys())
    fields = [f for f in fields if f in available]
    rows = client.execute_kw(
        "ir.cron",
        "search_read",
        [domain],
        {"fields": fields, "limit": limit, "order": "name"},
    )
    out = [
        CronRowEnriched(
            id=int(r["id"]),
            name=str(r.get("name") or r.get("cron_name") or ""),
            model_name=r.get("model_name") or _m2o_name(r.get("model_id")),
            interval_number=(
                int(r["interval_number"])
                if r.get("interval_number") not in (None, False)
                else None
            ),
            interval_type=r.get("interval_type") or None,
            active=bool(r.get("active", True)),
            nextcall=str(r["nextcall"]) if r.get("nextcall") else None,
            lastcall=str(r["lastcall"]) if r.get("lastcall") else None,
            description=render_cron_description(r),
            state=r.get("state") or None,
            code_preview=(str(r.get("code") or "")[:120] or None) if r.get("code") else None,
        )
        for r in rows
    ]
    return out, probe_run_method(client)


def _resolve_model_name(client: OdooClient, row: dict[str, Any]) -> str:
    model = row.get("model_name")
    if model:
        return str(model)
    mid = row.get("model_id")
    if isinstance(mid, (list, tuple)) and mid:
        rows = client.execute_kw(
            "ir.model",
            "read",
            [[int(mid[0])]],
            {"fields": ["model"]},
        )
        if rows:
            return str(rows[0]["model"])
    raise CronManagerError("Cron is missing model metadata")


def run_single_cron(
    client: OdooClient,
    cron_id: int,
    *,
    dry_run: bool = False,
) -> tuple[str, str]:
    if dry_run:
        rows = client.execute_kw(
            "ir.cron",
            "read",
            [[cron_id]],
            {"fields": ["name", "model_name", "model_id", "code"]},
        )
        if not rows:
            raise CronManagerError(f"Cron id={cron_id} not found")
        return "dry_run", f"Would run cron {rows[0].get('name')!r}"

    try:
        client.execute_kw("ir.cron", "method_direct_trigger", [[cron_id]])
        return "method_direct_trigger", "ok"
    except OdooClientError as primary_exc:
        rows = client.execute_kw(
            "ir.cron",
            "read",
            [[cron_id]],
            {
                "fields": ["name", "model_name", "model_id", "code", "state"],
            },
        )
        if not rows:
            raise CronManagerError(f"Cron id={cron_id} not found") from primary_exc
        row = rows[0]
        model = _resolve_model_name(client, row)
        method = _parse_model_method(str(row.get("code") or ""))
        if not method:
            raise CronManagerError(
                f"method_direct_trigger failed ({primary_exc}) and code fallback could not "
                f"parse a model.method() call"
            ) from primary_exc
        client.execute_kw(model, method, [[]])
        return "model_method", f"{model}.{method}()"


def run_crons_now(
    client: OdooClient,
    *,
    cron_ids: list[int],
    dry_run: bool = True,
    run_id: str | None = None,
) -> CronRunResult:
    run_id = run_id or str(uuid.uuid4())
    ids = list(dict.fromkeys(int(i) for i in cron_ids))
    per_record: list[PerRecordResult] = []
    succeeded = 0
    failed = 0
    run_via: str | None = None

    for cid in ids:
        try:
            via, detail = run_single_cron(client, cid, dry_run=dry_run)
            run_via = via if run_via is None else run_via
            rows = client.execute_kw(
                "ir.cron",
                "read",
                [[cid]],
                {"fields": ["name"]},
            )
            label = str(rows[0].get("name") or cid) if rows else str(cid)
            per_record.append(
                PerRecordResult(
                    id=cid,
                    display_name=label,
                    ok=True,
                    error=None if detail == "ok" else detail,
                )
            )
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            per_record.append(
                PerRecordResult(
                    id=cid,
                    display_name=str(cid),
                    ok=False,
                    error=str(exc),
                )
            )

    return CronRunResult(
        run_id=run_id,
        operation="cron_run_now",
        model="ir.cron",
        total=len(ids),
        succeeded=succeeded,
        failed=failed,
        per_record=per_record,
        dry_run=dry_run,
        message=(
            f"Cron run-now: {succeeded} ok, {failed} failed of {len(ids)}"
            if not dry_run
            else f"Dry-run: would trigger {len(ids)} cron(s)"
        ),
        cron_ids=ids,
        run_via=run_via,
    )


def validate_method_name(method: str) -> str:
    name = (method or "").strip()
    if not re.match(r"^[a-zA-Z_]\w*$", name):
        raise CronManagerError(
            f"Invalid method name {method!r} — use an existing public method on the model"
        )
    return name


def create_cron_for_existing_method(
    client: OdooClient,
    *,
    name: str,
    model: str,
    method: str,
    interval_number: int = 1,
    interval_type: str = "days",
    active: bool = True,
    nextcall: str | None = None,
) -> int:
    method = validate_method_name(method)
    if not client.model_exists(model):
        raise CronManagerError(f"Model {model!r} is not installed")
    model_id = client._model_id(model)
    vals: dict[str, Any] = {
        "name": name.strip(),
        "model_id": model_id,
        "state": "code",
        "code": f"model.{method}()",
        "interval_number": max(1, int(interval_number)),
        "interval_type": interval_type,
        "active": active,
    }
    if nextcall:
        vals["nextcall"] = nextcall
    return int(client.execute_kw("ir.cron", "create", [vals]))


def update_cron_schedule(
    client: OdooClient,
    cron_id: int,
    *,
    interval_number: int | None = None,
    interval_type: str | None = None,
    active: bool | None = None,
    nextcall: str | None = None,
) -> dict[str, Any]:
    vals: dict[str, Any] = {}
    if interval_number is not None:
        vals["interval_number"] = max(1, int(interval_number))
    if interval_type is not None:
        vals["interval_type"] = interval_type
    if active is not None:
        vals["active"] = active
    if nextcall is not None:
        vals["nextcall"] = nextcall
    if not vals:
        raise CronManagerError("No schedule fields to update")
    client.execute_kw("ir.cron", "write", [[cron_id], vals])
    rows = client.execute_kw(
        "ir.cron",
        "read",
        [[cron_id]],
        {
            "fields": [
                "name",
                "model_name",
                "model_id",
                "interval_number",
                "interval_type",
                "active",
                "nextcall",
                "lastcall",
                "state",
                "code",
            ]
        },
    )
    if not rows:
        raise CronManagerError(f"Cron id={cron_id} not found after write")
    row = rows[0]
    return CronRowEnriched(
        id=int(row["id"]),
        name=str(row.get("name") or ""),
        model_name=row.get("model_name") or _m2o_name(row.get("model_id")),
        interval_number=(
            int(row["interval_number"])
            if row.get("interval_number") not in (None, False)
            else None
        ),
        interval_type=row.get("interval_type") or None,
        active=bool(row.get("active", True)),
        nextcall=str(row["nextcall"]) if row.get("nextcall") else None,
        lastcall=str(row["lastcall"]) if row.get("lastcall") else None,
        description=render_cron_description(row),
        state=row.get("state") or None,
        code_preview=(str(row.get("code") or "")[:120] or None) if row.get("code") else None,
    ).to_dict()
