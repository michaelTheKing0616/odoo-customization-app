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
from app.rpc_resilience import execute_mutation_with_verify

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
    status: str = "completed"
    pending_ids: list[int] = field(default_factory=list)
    processed_count: int = 0
    aborted: bool = False
    abort_requested: bool = False

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


def _execute_transition_chunk(
    client: OdooClient,
    *,
    model: str,
    method: str,
    record_ids: list[int],
    names: dict[int, str],
) -> list[PerRecordResult]:
    if not record_ids:
        return []
    per_record: list[PerRecordResult] = []
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
        return per_record
    except Exception as batch_exc:  # noqa: BLE001
        batch_msg = str(batch_exc)
        for rid in record_ids:
            ok, err = execute_mutation_with_verify(
                client,
                model=model,
                method=method,
                record_id=rid,
            )
            if ok:
                per_record.append(
                    PerRecordResult(
                        id=rid,
                        display_name=names.get(rid, str(rid)),
                        ok=True,
                    )
                )
            else:
                per_record.append(
                    PerRecordResult(
                        id=rid,
                        display_name=names.get(rid, str(rid)),
                        ok=False,
                        error=err or batch_msg,
                    )
                )
        return per_record


def run_bulk_transition(
    client: OdooClient,
    *,
    model: str,
    method: str,
    record_ids: list[int],
    dry_run: bool = True,
    run_id: str | None = None,
    batch_size: int | None = None,
    sleep_ms: int | None = None,
    should_abort=None,
    on_mutations=None,
    pending_ids: list[int] | None = None,
    status: str = "completed",
) -> BulkRunResult:
    run_id = run_id or str(uuid.uuid4())
    all_ids = list(dict.fromkeys(list(record_ids) + list(pending_ids or [])))
    names = _load_display_names(client, model, all_ids)
    total = len(all_ids)

    if len(record_ids) == 0 and not pending_ids:
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
            status="completed",
        )

    if dry_run:
        preview_ids = record_ids if record_ids else (pending_ids or [])
        per = [
            PerRecordResult(id=rid, display_name=names.get(rid, str(rid)), ok=True)
            for rid in preview_ids
        ]
        return BulkRunResult(
            run_id=run_id,
            operation="bulk_transition",
            model=model,
            method=method,
            total=total,
            succeeded=len(per),
            failed=0,
            per_record=per,
            dry_run=True,
            message=f"Dry-run: would call {method} on {total} record(s).",
            status="completed",
            pending_ids=list(pending_ids or []),
        )

    from app.bulk_suite.executor import execute_in_batches
    from app.settings import settings

    per_record, aborted, unprocessed = execute_in_batches(
        record_ids,
        lambda chunk: _execute_transition_chunk(
            client, model=model, method=method, record_ids=chunk, names=names
        ),
        batch_size=batch_size or settings.bulk_batch_size,
        sleep_ms=sleep_ms if sleep_ms is not None else settings.bulk_batch_sleep_ms,
        should_abort=should_abort,
        on_mutations=on_mutations,
    )
    succeeded = sum(1 for r in per_record if r.ok)
    failed = sum(1 for r in per_record if not r.ok)
    processed_count = len(per_record)
    all_pending = list(unprocessed) + list(pending_ids or [])

    if aborted:
        final_status = "aborted"
        msg = (
            f"Aborted after {processed_count} record(s): {succeeded} ok, {failed} failed. "
            f"{len(all_pending)} record(s) not processed."
        )
    elif status == "sample_paused" and all_pending:
        final_status = "sample_paused"
        msg = (
            f"Sample phase: {method} on {processed_count} record(s) — "
            f"{succeeded} ok, {failed} failed. Review results, then continue for "
            f"{len(all_pending)} remaining record(s)."
        )
    else:
        final_status = "completed" if not all_pending else status
        msg = (
            f"{method}: {succeeded} ok, {failed} failed of {processed_count} record(s)"
            if failed
            else f"{method}: {succeeded} record(s) updated."
        )
        if all_pending and final_status != "completed":
            msg += f" {len(all_pending)} record(s) pending."

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
        message=msg,
        status=final_status,
        pending_ids=all_pending,
        processed_count=processed_count,
        aborted=aborted,
    )
