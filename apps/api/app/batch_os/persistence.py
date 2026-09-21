"""Persist Batch OS jobs on the existing BulkRun table (no second stack)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.batch_os.types import (
    BatchJobState,
    BatchPhase,
    MappedLine,
    MovePreview,
    RiskTier,
    RowError,
)
from app.db_models import BulkRun

OPERATION_PREFIX = "batch_os:"


def operation_for(recipe_id: str) -> str:
    return f"{OPERATION_PREFIX}{recipe_id}"[:40]


def save_job(db: Session, state: BatchJobState) -> BulkRun:
    payload = state.to_dict()
    # Keep raw rows for resume (not in public to_dict sample-only form).
    payload["raw_rows"] = list(state.raw_rows)
    row = db.get(BulkRun, state.job_id)
    if row is None:
        row = BulkRun(
            id=state.job_id,
            connection_id=state.connection_id,
            operation=operation_for(state.recipe_id),
            model=state.extras.get("model") or "account.move",
            dry_run="yes" if state.dry_run else "no",
            total=len(state.moves) or len(state.raw_rows),
            succeeded=len(state.created_move_ids),
            failed=sum(1 for e in state.errors if e.code == "blocking"),
            result_json=json.dumps(payload),
        )
        db.add(row)
    else:
        row.operation = operation_for(state.recipe_id)
        row.model = state.extras.get("model") or row.model
        row.dry_run = "yes" if state.dry_run else "no"
        row.total = len(state.moves) or len(state.raw_rows)
        row.succeeded = len(state.created_move_ids)
        row.failed = sum(1 for e in state.errors if e.code == "blocking")
        row.result_json = json.dumps(payload)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def load_job(db: Session, job_id: str) -> BatchJobState | None:
    row = db.get(BulkRun, job_id)
    if row is None:
        return None
    try:
        payload = json.loads(row.result_json)
    except json.JSONDecodeError:
        return None
    if not str(row.operation or "").startswith(OPERATION_PREFIX):
        # Allow resume only for Batch OS operations.
        if not payload.get("recipe_id"):
            return None
    return state_from_payload(payload, connection_id=row.connection_id, job_id=row.id)


def state_from_payload(
    payload: dict[str, Any],
    *,
    connection_id: str,
    job_id: str,
) -> BatchJobState:
    mapped = [
        MappedLine(**{k: v for k, v in m.items() if k in MappedLine.__dataclass_fields__})
        for m in (payload.get("mapped_lines") or [])
        if isinstance(m, dict)
    ]
    moves = [
        MovePreview(**{k: v for k, v in m.items() if k in MovePreview.__dataclass_fields__})
        for m in (payload.get("moves") or [])
        if isinstance(m, dict)
    ]
    errors = [
        RowError(**{k: v for k, v in e.items() if k in RowError.__dataclass_fields__})
        for e in (payload.get("errors") or [])
        if isinstance(e, dict)
    ]
    risk: RiskTier = payload.get("risk") if payload.get("risk") in {"L0", "L1", "L2", "L3"} else "L1"
    phase: BatchPhase = payload.get("phase") or "intake"  # type: ignore[assignment]
    if phase not in {
        "intake",
        "mapped",
        "validated",
        "dry_run",
        "applied",
        "failed",
    }:
        phase = "intake"
    return BatchJobState(
        job_id=job_id,
        connection_id=connection_id,
        recipe_id=str(payload.get("recipe_id") or "accounting.journal_batch"),
        risk=risk,
        phase=phase,
        filename=str(payload.get("filename") or ""),
        headers=list(payload.get("headers") or []),
        raw_rows=list(payload.get("raw_rows") or []),
        column_map=dict(payload.get("column_map") or {}),
        mapped_lines=mapped,
        moves=moves,
        errors=errors,
        warnings=list(payload.get("warnings") or []),
        message=str(payload.get("message") or ""),
        honesty=str(payload.get("honesty") or ""),
        dry_run=bool(payload.get("dry_run", True)),
        post_after_create=bool(payload.get("post_after_create", False)),
        extras=dict(payload.get("extras") or {}),
        created_move_ids=[int(x) for x in (payload.get("created_move_ids") or [])],
        posted_move_ids=[int(x) for x in (payload.get("posted_move_ids") or [])],
    )


def public_job_dict(state: BatchJobState) -> dict[str, Any]:
    """API-facing payload without full raw_rows dump."""
    return state.to_dict()
