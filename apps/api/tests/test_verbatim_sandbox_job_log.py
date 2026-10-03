"""T1-D3 — verbatim Odoo sandbox fault on BackgroundJob.error (redacted secrets)."""

from __future__ import annotations

import time

from app.db import SessionLocal, init_db
from app.db_models import BackgroundJob
from app.job_runner import InProcessJobRunner
from app.sandbox import (
    SANDBOX_PASSWORD,
    sandbox_job_error_from_result,
    verbatim_sandbox_error_text,
)

_KNOWN_TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "addons/ext_markup_test/models/sale_order.py", line 42, in write\n'
    '    raise ValidationError("bad field x_markup")\n'
    "ValidationError: bad field x_markup"
)

_TRACE_HEAD = "Traceback (most recent call last):"
_TRACE_TAIL = "ValidationError: bad field x_markup ENDMARKER"


def _long_traceback(*, pad_len: int = 5000) -> str:
    """Odoo-scale fault text (>4000 chars) with distinct head and tail."""
    return (
        f"{_TRACE_HEAD}\n"
        f'  File "addons/ext_markup_test/models/sale_order.py", line 42, in write\n'
        f"{'X' * pad_len}\n"
        f"{_TRACE_TAIL}"
    )


def test_verbatim_sandbox_error_text_keeps_traceback_redacts_secrets() -> None:
    secret_line = f"connect password={SANDBOX_PASSWORD} api_key=sk-testkey1234567890"
    raw = f"{_KNOWN_TRACEBACK}\n{secret_line}"
    stored = verbatim_sandbox_error_text(message="Module install failed", log_tail=raw)
    assert _KNOWN_TRACEBACK in stored
    assert SANDBOX_PASSWORD not in stored
    assert "sk-testkey1234567890" not in stored
    assert "[redacted]" in stored


def test_sandbox_job_error_from_result_nested_payload() -> None:
    payload = {
        "ok": False,
        "sandbox": {
            "ok": False,
            "message": "RPC fault",
            "log_tail": _KNOWN_TRACEBACK,
        },
    }
    text = sandbox_job_error_from_result(payload)
    assert text is not None
    assert _KNOWN_TRACEBACK in text


def test_sandbox_background_job_stores_verbatim_error() -> None:
    runner = InProcessJobRunner(max_workers=1)
    init_db()
    db = SessionLocal()
    try:
        row = BackgroundJob(kind="sandbox", status="queued")
        db.add(row)
        db.commit()
        jid = row.id

        def work() -> dict:
            return {
                "ok": False,
                "message": "Sandbox install failed",
                "log_tail": _KNOWN_TRACEBACK,
            }

        runner.enqueue(jid, work)
        deadline = time.time() + 3.0
        status = "queued"
        while time.time() < deadline and status in {"queued", "running"}:
            time.sleep(0.05)
            db.expire_all()
            refreshed = db.get(BackgroundJob, jid)
            assert refreshed is not None
            status = refreshed.status
        assert status == "succeeded"
        assert refreshed.error is not None
        assert _KNOWN_TRACEBACK in refreshed.error
        assert "ValidationError: bad field x_markup" in refreshed.error
    finally:
        db.close()


def test_sandbox_background_job_keeps_long_traceback_redacts_secrets() -> None:
    runner = InProcessJobRunner(max_workers=1)
    init_db()
    db = SessionLocal()
    try:
        row = BackgroundJob(kind="sandbox", status="queued")
        db.add(row)
        db.commit()
        jid = row.id
        long_tb = _long_traceback()
        assert len(long_tb) > 4000
        secret_line = f"connect password={SANDBOX_PASSWORD} api_key=sk-longtrace-secret99"
        log_tail = f"{long_tb}\n{secret_line}"

        def work() -> dict:
            return {
                "ok": False,
                "message": "Sandbox install failed",
                "log_tail": log_tail,
            }

        runner.enqueue(jid, work)
        deadline = time.time() + 3.0
        status = "queued"
        refreshed = None
        while time.time() < deadline and status in {"queued", "running"}:
            time.sleep(0.05)
            db.expire_all()
            refreshed = db.get(BackgroundJob, jid)
            assert refreshed is not None
            status = refreshed.status
        assert status == "succeeded"
        assert refreshed is not None and refreshed.error is not None
        assert len(refreshed.error) > 4000
        assert _TRACE_HEAD in refreshed.error
        assert _TRACE_TAIL in refreshed.error
        assert SANDBOX_PASSWORD not in refreshed.error
        assert "sk-longtrace-secret99" not in refreshed.error
        assert "[redacted]" in refreshed.error
    finally:
        db.close()


def test_job_runner_failed_job_keeps_long_traceback_redacted() -> None:
    runner = InProcessJobRunner(max_workers=1)
    init_db()
    db = SessionLocal()
    try:
        row = BackgroundJob(kind="health_check", status="queued")
        db.add(row)
        db.commit()
        jid = row.id
        pad = "Y" * 5000

        def work() -> dict:
            raise RuntimeError(f"{_TRACE_HEAD}\n{pad}\n{_TRACE_TAIL} password={SANDBOX_PASSWORD}")

        runner.enqueue(jid, work)
        deadline = time.time() + 3.0
        status = "queued"
        refreshed = None
        while time.time() < deadline and status in {"queued", "running"}:
            time.sleep(0.05)
            db.expire_all()
            refreshed = db.get(BackgroundJob, jid)
            assert refreshed is not None
            status = refreshed.status
        assert status == "failed"
        assert refreshed is not None and refreshed.error is not None
        assert len(refreshed.error) > 4000
        assert _TRACE_HEAD in refreshed.error
        assert _TRACE_TAIL in refreshed.error
        assert SANDBOX_PASSWORD not in refreshed.error
    finally:
        db.close()
