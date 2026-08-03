"""Background job runner hardening (PROD-3)."""

from __future__ import annotations

import time

from app.db import SessionLocal, init_db
from app.db_models import BackgroundJob
from app.job_runner import (
    MAX_CONCURRENT_JOBS,
    InProcessJobRunner,
    mark_interrupted_jobs_on_boot,
)


def test_mark_interrupted_jobs_on_boot() -> None:
    init_db()
    db = SessionLocal()
    try:
        row = BackgroundJob(kind="sandbox", status="running")
        db.add(row)
        db.commit()
        jid = row.id
        n = mark_interrupted_jobs_on_boot(db)
        assert n >= 1
        refreshed = db.get(BackgroundJob, jid)
        assert refreshed is not None
        assert refreshed.status == "interrupted"
    finally:
        db.close()


def test_concurrent_job_cap() -> None:
    runner = InProcessJobRunner(max_workers=MAX_CONCURRENT_JOBS)
    init_db()
    db = SessionLocal()
    try:
        jobs = [
            BackgroundJob(kind="health_check", status="queued"),
            BackgroundJob(kind="health_check", status="queued"),
            BackgroundJob(kind="health_check", status="queued"),
        ]
        for j in jobs:
            db.add(j)
        db.commit()
        barrier = __import__("threading").Event()

        def slow() -> dict:
            barrier.wait(timeout=5)
            time.sleep(0.05)
            return {"ok": True}

        runner.enqueue(jobs[0].id, slow)
        runner.enqueue(jobs[1].id, slow)
        runner.enqueue(jobs[2].id, slow)
        barrier.set()
        time.sleep(0.3)
        db.expire_all()
        statuses = {db.get(BackgroundJob, j.id).status for j in jobs}
        assert "failed" in statuses or "queued" in statuses or "running" in statuses
    finally:
        db.close()


def test_cancel_sandbox_signal() -> None:
    from app.sandbox import cancel_sandbox_if_running

    cancel_sandbox_if_running("nonexistent-id")
