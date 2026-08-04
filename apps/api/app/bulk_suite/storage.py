"""Persist BulkRunResult rows for BLK suite operations."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.bulk_suite.transitions import BulkRunResult
from app.db_models import BulkRun


def save_bulk_run(
    db: Session,
    *,
    connection_id: str,
    result: BulkRunResult,
) -> BulkRun:
    row = BulkRun(
        id=result.run_id,
        connection_id=connection_id,
        operation=result.operation,
        model=result.model,
        dry_run="yes" if result.dry_run else "no",
        total=result.total,
        succeeded=result.succeeded,
        failed=result.failed,
        result_json=json.dumps(result.to_dict()),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_bulk_run(db: Session, *, run_id: str, result: BulkRunResult) -> BulkRun:
    row = db.get(BulkRun, run_id)
    if row is None:
        raise LookupError(f"Bulk run {run_id} not found")
    row.operation = result.operation
    row.model = result.model
    row.dry_run = "yes" if result.dry_run else "no"
    row.total = result.total
    row.succeeded = result.succeeded
    row.failed = result.failed
    row.result_json = json.dumps(result.to_dict())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def load_bulk_run(db: Session, run_id: str) -> dict[str, Any] | None:
    row = db.get(BulkRun, run_id)
    if row is None:
        return None
    payload = json.loads(row.result_json)
    payload["connection_id"] = row.connection_id
    payload["created_at"] = row.created_at.isoformat() if row.created_at else None
    payload["can_continue"] = bool(
        payload.get("pending_ids") and payload.get("status") == "sample_paused"
    )
    return payload


def mark_bulk_run_abort_requested(db: Session, run_id: str) -> dict[str, Any]:
    payload = load_bulk_run(db, run_id)
    if payload is None:
        raise LookupError(f"Bulk run {run_id} not found")
    payload["abort_requested"] = True
    row = db.get(BulkRun, run_id)
    assert row is not None
    row.result_json = json.dumps(payload)
    db.add(row)
    db.commit()
    return payload


def bulk_run_abort_checker(db: Session, run_id: str):
    """Return a callable that reads abort_requested from persisted run state."""

    def _check() -> bool:
        payload = load_bulk_run(db, run_id)
        return bool(payload and payload.get("abort_requested"))

    return _check
