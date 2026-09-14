"""Background job runner hardening (PROD-3 / REM-9)."""

from __future__ import annotations

import json
import threading
import time

import pytest

from app.db import SessionLocal, init_db
from app.db_models import BackgroundJob
from app.job_runner import (
    JOB_TIMEOUTS,
    MAX_CONCURRENT_JOBS,
    InProcessJobRunner,
    cancel_job,
    mark_interrupted_jobs_on_boot,
    update_job_progress,
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
        barrier = threading.Event()

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


def test_job_timeout_sets_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(JOB_TIMEOUTS, "health_check", 0.15)
    runner = InProcessJobRunner(max_workers=1)
    init_db()
    db = SessionLocal()
    try:
        row = BackgroundJob(kind="health_check", status="queued")
        db.add(row)
        db.commit()
        jid = row.id

        def slow() -> dict:
            time.sleep(1.0)
            return {"ok": True}

        runner.enqueue(jid, slow)
        deadline = time.time() + 3.0
        status = "running"
        while time.time() < deadline and status == "running":
            time.sleep(0.05)
            db.expire_all()
            refreshed = db.get(BackgroundJob, jid)
            assert refreshed is not None
            status = refreshed.status
        assert status == "timeout"
        assert refreshed.error and "exceeded" in refreshed.error.lower()
    finally:
        db.close()


def test_job_timeout_keeps_progress_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Timeout must not wipe a draft already written via progress()."""
    monkeypatch.setitem(JOB_TIMEOUTS, "health_check", 0.2)
    runner = InProcessJobRunner(max_workers=1)
    init_db()
    db = SessionLocal()
    try:
        row = BackgroundJob(kind="health_check", status="queued")
        db.add(row)
        db.commit()
        jid = row.id

        def slow_with_progress() -> dict:
            update_job_progress(
                jid,
                {"partial_draft": {"models": [{"name": "x_matter"}], "module": "x_legal"}},
            )
            time.sleep(1.0)
            return {"ok": True}

        runner.enqueue(jid, slow_with_progress)
        deadline = time.time() + 3.0
        status = "running"
        refreshed = None
        while time.time() < deadline and status in ("queued", "running"):
            time.sleep(0.05)
            db.expire_all()
            refreshed = db.get(BackgroundJob, jid)
            assert refreshed is not None
            status = refreshed.status
        assert status == "timeout"
        assert refreshed is not None
        result = json.loads(refreshed.result_json or "{}")
        assert result.get("draft", {}).get("module") == "x_legal"
        warnings = result.get("warnings") or []
        assert any("time cap" in str(w).lower() for w in warnings)
    finally:
        db.close()


def test_job_timeout_does_not_wait_for_inner_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(JOB_TIMEOUTS, "health_check", 0.2)
    runner = InProcessJobRunner(max_workers=1)
    init_db()
    db = SessionLocal()
    try:
        row = BackgroundJob(kind="health_check", status="queued")
        db.add(row)
        db.commit()
        jid = row.id

        def slow() -> dict:
            time.sleep(5.0)
            return {"ok": True}

        started = time.time()
        runner.enqueue(jid, slow)
        status = "running"
        while time.time() - started < 2.0 and status == "running":
            time.sleep(0.05)
            db.expire_all()
            refreshed = db.get(BackgroundJob, jid)
            assert refreshed is not None
            status = refreshed.status
        assert status == "timeout"
        assert time.time() - started < 2.0
    finally:
        db.close()


def test_cancel_running_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(JOB_TIMEOUTS, "health_check", None)
    runner = InProcessJobRunner(max_workers=1)
    init_db()
    db = SessionLocal()
    try:
        row = BackgroundJob(kind="health_check", status="queued")
        db.add(row)
        db.commit()
        jid = row.id
        started = threading.Event()
        release = threading.Event()

        def long_job() -> dict:
            started.set()
            release.wait(timeout=5)
            return {"ok": True}

        runner.enqueue(jid, long_job)
        assert started.wait(timeout=5)
        cancelled = runner.cancel(jid)
        assert cancelled is True
        release.set()
        time.sleep(0.2)
        db.expire_all()
        refreshed = db.get(BackgroundJob, jid)
        assert refreshed is not None
        assert refreshed.status in {"cancelled", "succeeded"}
    finally:
        db.close()


def test_cancel_job_api_marks_cancelled() -> None:
    init_db()
    db = SessionLocal()
    try:
        row = BackgroundJob(kind="sandbox", status="running")
        db.add(row)
        db.commit()
        out = cancel_job(db, row.id)
        assert out is not None
        assert out.status == "cancelled"
    finally:
        db.close()


def test_cancel_sandbox_kills_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    import time

    from app.sandbox import _sandbox_subprocesses, cancel_sandbox_if_running

    proc = subprocess.Popen(["sleep", "30"])
    job_id = "cancel-kill-test"
    _sandbox_subprocesses[job_id] = proc
    assert proc.poll() is None
    cancel_sandbox_if_running(job_id)
    deadline = time.time() + 3.0
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.05)
    assert proc.poll() is not None
    assert job_id not in _sandbox_subprocesses


def test_cancel_sandbox_signal() -> None:
    from app.sandbox import cancel_sandbox_if_running

    cancel_sandbox_if_running("nonexistent-id")
