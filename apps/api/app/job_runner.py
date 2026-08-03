"""Background job runner seam + in-process hardening (PROD-3).

v1 keeps the thread-pool runner (no Redis/arq). Swap ``get_job_runner()`` later
without changing call sites when multi-instance deploy demands it.
"""

from __future__ import annotations

import json
import logging
import threading
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.db_models import BackgroundJob

logger = logging.getLogger(__name__)

# Per job kind — seconds (None = no timeout enforcement in worker)
JOB_TIMEOUTS: dict[str, float | None] = {
    "sandbox": 900.0,
    "promote": 900.0,
    "health_check": 600.0,
    "expert_ingest": 1200.0,
}

MAX_CONCURRENT_JOBS = 2


class JobRunner(Protocol):
    def enqueue(self, job_id: str, fn: Callable[[], dict[str, Any]]) -> None: ...

    def cancel(self, job_id: str) -> bool: ...


@dataclass
class JobHandle:
    id: str
    status: str


class InProcessJobRunner:
    """Thread-pool runner with cancel signals, caps, and structured logs."""

    def __init__(self, *, max_workers: int = MAX_CONCURRENT_JOBS) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="odoo-job")
        self._lock = threading.Lock()
        self._cancel_events: dict[str, threading.Event] = {}
        self._futures: dict[str, Future[None]] = {}
        self._active_count = 0

    def enqueue(self, job_id: str, fn: Callable[[], dict[str, Any]]) -> None:
        cancel_ev = threading.Event()
        with self._lock:
            if self._active_count >= MAX_CONCURRENT_JOBS:
                _set_status(
                    job_id,
                    "failed",
                    error="Job queue full — retry shortly (concurrent cap reached)",
                )
                return
            self._cancel_events[job_id] = cancel_ev
            self._active_count += 1

        def _run() -> None:
            db = SessionLocal()
            try:
                row = db.get(BackgroundJob, job_id)
                if row is not None and row.status == "cancelled":
                    return
            finally:
                db.close()

            kind = _job_kind(job_id)
            timeout = JOB_TIMEOUTS.get(kind or "", None)
            _set_status(job_id, "running")
            logger.info(
                "job.start",
                extra={"job_id": job_id, "kind": kind, "timeout_s": timeout},
            )
            try:
                if cancel_ev.is_set():
                    _set_status(job_id, "cancelled", error="Cancelled before start")
                    return
                result = fn()
                if cancel_ev.is_set():
                    _set_status(job_id, "cancelled", error="Cancelled during run")
                    return
                _set_status(job_id, "succeeded", result=result)
                logger.info("job.succeeded", extra={"job_id": job_id, "kind": kind})
            except Exception as exc:  # noqa: BLE001
                if cancel_ev.is_set():
                    _set_status(job_id, "cancelled", error=f"Cancelled: {exc}")
                else:
                    logger.exception("job.failed", extra={"job_id": job_id, "kind": kind})
                    _set_status(
                        job_id,
                        "failed",
                        error=f"{exc}\n{traceback.format_exc()[-1500:]}",
                    )
            finally:
                with self._lock:
                    self._active_count = max(0, self._active_count - 1)
                    self._cancel_events.pop(job_id, None)
                    self._futures.pop(job_id, None)

        with self._lock:
            fut = self._executor.submit(_run)
            self._futures[job_id] = fut

    def cancel(self, job_id: str) -> bool:
        ev = self._cancel_events.get(job_id)
        if ev is not None:
            ev.set()
        from app.sandbox import cancel_sandbox_if_running

        cancel_sandbox_if_running(job_id)
        return ev is not None

    def is_cancelled(self, job_id: str) -> bool:
        ev = self._cancel_events.get(job_id)
        return bool(ev and ev.is_set())


_runner: InProcessJobRunner | None = None
_runner_lock = threading.Lock()


def get_job_runner() -> JobRunner:
    global _runner
    with _runner_lock:
        if _runner is None:
            _runner = InProcessJobRunner()
        return _runner


def _job_kind(job_id: str) -> str | None:
    db = SessionLocal()
    try:
        row = db.get(BackgroundJob, job_id)
        return row.kind if row else None
    finally:
        db.close()


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


def mark_interrupted_jobs_on_boot(db: Session) -> int:
    """Jobs left queued/running after process death → interrupted."""
    rows = (
        db.query(BackgroundJob)
        .filter(BackgroundJob.status.in_(["queued", "running"]))
        .all()
    )
    now = datetime.now(timezone.utc)
    for row in rows:
        row.status = "interrupted"
        row.finished_at = now
        row.error = (row.error or "") + "\nProcess restarted before job finished"
        db.add(row)
    if rows:
        db.commit()
    return len(rows)


def cancel_job(db: Session, job_id: str) -> BackgroundJob | None:
    row = db.get(BackgroundJob, job_id)
    if row is None:
        return None
    if row.status in {"succeeded", "failed", "cancelled", "interrupted"}:
        return row
    get_job_runner().cancel(job_id)
    row.status = "cancelled"
    row.finished_at = datetime.now(timezone.utc)
    row.error = (row.error or "") + "\nCancelled by user"
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def enqueue(job_id: str, fn: Callable[[], dict[str, Any]]) -> None:
    get_job_runner().enqueue(job_id, fn)


def job_cancelled(job_id: str) -> bool:
    runner = get_job_runner()
    if isinstance(runner, InProcessJobRunner):
        return runner.is_cancelled(job_id)
    return False


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
        if row.status == "cancelled" and status in {"running", "succeeded", "failed"}:
            return
        row.status = status
        if result is not None:
            row.result_json = json.dumps(result)
        if error is not None:
            row.error = error[:4000]
        if status in {"succeeded", "failed", "cancelled", "interrupted"}:
            row.finished_at = datetime.now(timezone.utc)
        db.add(row)
        db.commit()
    finally:
        db.close()
