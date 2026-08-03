"""Bulk state transition run engine + discovery cache."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.discovery import (
    TransitionButton,
    _model_has_state_field,
    _primary_form_arch,
    discover_buttons_from_arch,
)
from app.bulk_suite.domain_util import parse_domain

DEFAULT_RECORD_CAP = 1000

# Cache per (connection_id, model, odoo_version) — invalidate when version changes.
_DISCOVERY_CACHE: dict[tuple[str, str, str], list[TransitionButton]] = {}


class BulkSuiteError(Exception):
    pass


@dataclass
class PerRecordResult:
    id: int
    display_name: str
    ok: bool
    error: str | None = None


@dataclass
class BulkRunResult:
    run_id: str
    operation: str
    model: str
    total: int
    succeeded: int
    failed: int
    per_record: list[PerRecordResult] = field(default_factory=list)
    dry_run: bool = True
    method: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


def cache_key(connection_id: str, model: str, odoo_version: str | None) -> tuple[str, str, str]:
    return (connection_id, model, (odoo_version or "").strip() or "unknown")


def invalidate_discovery_cache(
    *,
    connection_id: str | None = None,
    model: str | None = None,
) -> None:
    """Drop cached discovery rows (TIER-4 hook: call on connection version change)."""
    global _DISCOVERY_CACHE
    if connection_id is None and model is None:
        _DISCOVERY_CACHE.clear()
        return
    drop = [
        key
        for key in _DISCOVERY_CACHE
        if (connection_id is None or key[0] == connection_id)
        and (model is None or key[1] == model)
    ]
    for key in drop:
        _DISCOVERY_CACHE.pop(key, None)


def discover_transitions(
    client: OdooClient,
    *,
    connection_id: str,
    model: str,
    odoo_version: str | None = None,
    use_cache: bool = True,
) -> list[TransitionButton]:
    if not client.model_exists(model):
        raise BulkSuiteError(f"Model {model!r} is not installed on this database")
    key = cache_key(connection_id, model, odoo_version)
    if use_cache and key in _DISCOVERY_CACHE:
        return list(_DISCOVERY_CACHE[key])

    arch = _primary_form_arch(client, model)
    if not arch:
        raise BulkSuiteError(f"No form view arch found for model {model!r}")
    has_state = _model_has_state_field(client, model)
    buttons = discover_buttons_from_arch(arch, has_state_field=has_state)
    _DISCOVERY_CACHE[key] = list(buttons)
    return buttons


def resolve_record_ids(
    client: OdooClient,
    *,
    model: str,
    ids: list[int] | None,
    domain: list[Any] | str | None,
    cap: int = DEFAULT_RECORD_CAP,
) -> list[int]:
    cap = max(1, min(int(cap or DEFAULT_RECORD_CAP), 5000))
    if ids:
        unique = list(dict.fromkeys(int(i) for i in ids))
        if len(unique) > cap:
            raise BulkSuiteError(
                f"Explicit id list has {len(unique)} records; cap is {cap}. "
                "Split the run or raise the cap."
            )
        return unique
    dom = parse_domain(domain)
    found = client.execute_kw(model, "search", [dom], {"limit": cap + 1})
    if len(found) > cap:
        raise BulkSuiteError(
            f"Domain matches at least {len(found)} records; cap is {cap}. "
            "Narrow the domain or pass explicit ids."
        )
    return [int(i) for i in found]


def _load_display_names(
    client: OdooClient, model: str, record_ids: list[int]
) -> dict[int, str]:
    if not record_ids:
        return {}
    names: dict[int, str] = {rid: str(rid) for rid in record_ids}
    try:
        rows = client.execute_kw(
            model,
            "read",
            [record_ids],
            {"fields": ["display_name"]},
        )
    except OdooClientError:
        try:
            rows = client.execute_kw(model, "read", [record_ids], {"fields": ["name"]})
        except OdooClientError:
            return names
    for row in rows:
        rid = int(row["id"])
        label = row.get("display_name") or row.get("name") or str(rid)
        names[rid] = str(label)
    return names


def run_bulk_transition(
    client: OdooClient,
    *,
    model: str,
    method: str,
    record_ids: list[int],
    dry_run: bool = True,
    run_id: str | None = None,
) -> BulkRunResult:
    run_id = run_id or str(uuid.uuid4())
    names = _load_display_names(client, model, record_ids)
    total = len(record_ids)

    if total == 0:
        return BulkRunResult(
            run_id=run_id,
            operation="bulk_transition",
            model=model,
            method=method,
            total=0,
            succeeded=0,
            failed=0,
            per_record=[],
            dry_run=dry_run,
            message="No records matched the selection.",
        )

    if dry_run:
        per = [
            PerRecordResult(id=rid, display_name=names.get(rid, str(rid)), ok=True)
            for rid in record_ids
        ]
        return BulkRunResult(
            run_id=run_id,
            operation="bulk_transition",
            model=model,
            method=method,
            total=total,
            succeeded=total,
            failed=0,
            per_record=per,
            dry_run=True,
            message=f"Dry-run: would call {method} on {total} record(s).",
        )

    per_record: list[PerRecordResult] = []
    succeeded = 0
    failed = 0

    try:
        client.execute_kw(model, method, [record_ids])
        for rid in record_ids:
            per_record.append(
                PerRecordResult(
                    id=rid,
                    display_name=names.get(rid, str(rid)),
                    ok=True,
                )
            )
        succeeded = total
    except Exception as batch_exc:  # noqa: BLE001
        batch_msg = str(batch_exc)
        for rid in record_ids:
            try:
                client.execute_kw(model, method, [[rid]])
                per_record.append(
                    PerRecordResult(
                        id=rid,
                        display_name=names.get(rid, str(rid)),
                        ok=True,
                    )
                )
                succeeded += 1
            except Exception as row_exc:  # noqa: BLE001
                per_record.append(
                    PerRecordResult(
                        id=rid,
                        display_name=names.get(rid, str(rid)),
                        ok=False,
                        error=str(row_exc) or batch_msg,
                    )
                )
                failed += 1

    return BulkRunResult(
        run_id=run_id,
        operation="bulk_transition",
        model=model,
        method=method,
        total=total,
        succeeded=succeeded,
        failed=failed,
        per_record=per_record,
        dry_run=False,
        message=(
            f"{method}: {succeeded} ok, {failed} failed of {total} record(s)"
            if failed
            else f"{method}: {succeeded} record(s) updated."
        ),
    )
