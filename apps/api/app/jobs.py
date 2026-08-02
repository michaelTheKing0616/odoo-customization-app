"""Lightweight background jobs for long sandbox/promote runs (thread pool, no Redis)."""

from __future__ import annotations

import json
import logging
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.db_models import BackgroundJob

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="odoo-job")
_lock = threading.Lock()


@dataclass
class JobHandle:
    id: str
    status: str


def create_job(db: Session, *, kind: str, connection_id: str | None = None) -> BackgroundJob:
    row = BackgroundJob(
        id=str(uuid.uuid4()),
        kind=kind,
        connection_id=connection_id,
        status="queued",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_job(db: Session, job_id: str) -> BackgroundJob | None:
    return db.get(BackgroundJob, job_id)


def cancel_job(db: Session, job_id: str) -> BackgroundJob | None:
    """Mark queued/running job cancelled. Running work may still finish but result is discarded."""
    row = db.get(BackgroundJob, job_id)
    if row is None:
        return None
    if row.status in {"succeeded", "failed", "cancelled"}:
        return row
    row.status = "cancelled"
    row.finished_at = datetime.now(timezone.utc)
    row.error = (row.error or "") + "\nCancelled by user"
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _set_status(
    job_id: str,
    status: str,
    *,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        row = db.get(BackgroundJob, job_id)
        if row is None:
            return
        # Do not overwrite a user cancel
        if row.status == "cancelled" and status in {"running", "succeeded", "failed"}:
            return
        row.status = status
        if result is not None:
            row.result_json = json.dumps(result)
        if error is not None:
            row.error = error[:4000]
        if status in {"succeeded", "failed", "cancelled"}:
            row.finished_at = datetime.now(timezone.utc)
        db.add(row)
        db.commit()
    finally:
        db.close()


def enqueue(job_id: str, fn: Callable[[], dict[str, Any]]) -> None:
    """Run fn in a worker thread; persist result/error on the job row."""

    def _run() -> None:
        db = SessionLocal()
        try:
            row = db.get(BackgroundJob, job_id)
            if row is not None and row.status == "cancelled":
                return
        finally:
            db.close()
        _set_status(job_id, "running")
        try:
            result = fn()
            _set_status(job_id, "succeeded", result=result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("background job %s failed", job_id)
            _set_status(
                job_id,
                "failed",
                error=f"{exc}\n{traceback.format_exc()[-1500:]}",
            )

    with _lock:
        _executor.submit(_run)
