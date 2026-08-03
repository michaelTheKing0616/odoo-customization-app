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


def load_bulk_run(db: Session, run_id: str) -> dict[str, Any] | None:
    row = db.get(BulkRun, run_id)
    if row is None:
        return None
    payload = json.loads(row.result_json)
    payload["connection_id"] = row.connection_id
    payload["created_at"] = row.created_at.isoformat() if row.created_at else None
    return payload
