"""Stage 5/6 — dry-run and commit via data_import (ING-7/ING-8)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from odoo_client import OdooClient

from app.data_import import dry_run_or_commit

INGEST_BULK_CONTEXT = {
    "tracking_disable": True,
    "mail_create_nosubscribe": True,
    "mail_notrack": True,
}
from app.ingest.schema import IngestBatch, IngestCommitLog, IngestTable


def _rows_for_table(table: IngestTable) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in table.rows:
        merged = dict(row.raw)
        merged.update({k: str(v) for k, v in row.values.items() if v is not None})
        out.append(merged)
    return out


def _commit_table(
    client: OdooClient,
    table: IngestTable,
    *,
    dry_run: bool,
    batch_size: int,
) -> dict[str, Any]:
    result = dry_run_or_commit(
        client,
        model=table.model,
        rows=_rows_for_table(table),
        mapping=table.mapping,
        mode=table.mode,
        match_fields=table.natural_key_fields,
        dry_run=dry_run,
        batch_size=batch_size,
        rpc_context=None if dry_run else INGEST_BULK_CONTEXT,
    )
    return {
        "table_id": table.id,
        "model": table.model,
        "created": result.created,
        "updated": result.updated,
        "failed": result.failed,
        "skipped": result.skipped,
        "message": result.message,
        "ok": result.ok,
    }


def run_commit_plan(
    client: OdooClient,
    batch: IngestBatch,
    *,
    dry_run: bool = True,
    batch_size: int = 50,
    parallel_cap: int = 2,
) -> IngestCommitLog:
    if not batch.plan or not batch.plan.steps:
        return IngestCommitLog(
            dry_run=dry_run,
            messages=["No ingest plan — run map/plan stages first"],
        )

    table_by_id = {t.id: t for t in batch.tables}
    log = IngestCommitLog(dry_run=dry_run)
    for step in sorted(batch.plan.steps, key=lambda s: s.step_index):
        step_tables = [table_by_id[tid] for tid in step.table_ids if tid in table_by_id]
        if not step_tables:
            continue
        if step.parallel_ok and len(step_tables) > 1 and not dry_run:
            with ThreadPoolExecutor(max_workers=min(parallel_cap, len(step_tables))) as pool:
                futures = {
                    pool.submit(
                        _commit_table,
                        client,
                        tbl,
                        dry_run=dry_run,
                        batch_size=batch_size,
                    ): tbl
                    for tbl in step_tables
                }
                for fut in as_completed(futures):
                    res = fut.result()
                    log.step_results.append(res)
                    log.created += int(res.get("created") or 0)
                    log.updated += int(res.get("updated") or 0)
                    log.failed += int(res.get("failed") or 0)
                    log.skipped += int(res.get("skipped") or 0)
                    if res.get("message"):
                        log.messages.append(str(res["message"]))
        else:
            for tbl in step_tables:
                res = _commit_table(
                    client,
                    tbl,
                    dry_run=dry_run,
                    batch_size=batch_size,
                )
                log.step_results.append(res)
                log.created += int(res.get("created") or 0)
                log.updated += int(res.get("updated") or 0)
                log.failed += int(res.get("failed") or 0)
                log.skipped += int(res.get("skipped") or 0)
                if res.get("message"):
                    log.messages.append(str(res["message"]))
    return log
