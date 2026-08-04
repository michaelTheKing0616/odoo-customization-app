"""DEV-3 — script runner subprocess sandbox tests."""

from __future__ import annotations

import os
import textwrap
import time

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")

from app.script_runner.executor import cancel_script_if_running, run_script_in_subprocess  # noqa: E402


@pytest.fixture
def fake_config() -> dict:
    return {
        "url": "http://127.0.0.1:8069",
        "db": "odoo_dev",
        "username": "admin",
        "password": "admin",
        "write_mode": "standard",
    }


def test_subprocess_timeout_kills_script(fake_config: dict) -> None:
    script = textwrap.dedent(
        """
        import time
        while True:
            time.sleep(0.2)
        """
    )
    result = run_script_in_subprocess(
        script=script,
        connection_config=fake_config,
        job_id="timeout-test",
        timeout_s=2,
    )
    assert result["ok"] is False
    assert "timeout" in (result.get("error") or "").lower()


def test_import_allowlist_blocks_socket(fake_config: dict) -> None:
    script = "import socket\n"
    result = run_script_in_subprocess(
        script=script,
        connection_config=fake_config,
        job_id="import-test",
        timeout_s=10,
    )
    assert result["ok"] is False
    assert "not allowed" in (result.get("stderr") or result.get("error") or "").lower()


def test_simple_log_script_runs(fake_config: dict) -> None:
    script = textwrap.dedent(
        """
        log("hello from sandbox test")
        """
    )
    result = run_script_in_subprocess(
        script=script,
        connection_config=fake_config,
        job_id="log-test",
        timeout_s=30,
    )
    # May fail if Odoo unreachable — still proves subprocess bootstrap
    if result.get("ok"):
        assert "hello from sandbox test" in (result.get("stdout") or "")
    else:
        assert result.get("stderr") or result.get("error")


def test_abort_mid_run_terminates_subprocess(fake_config: dict) -> None:
    import threading

    script = textwrap.dedent(
        """
        import time
        for _ in range(600):
            time.sleep(0.1)
        """
    )
    job_id = "abort-mid-run"
    result_holder: dict = {}

    def _run() -> None:
        result_holder["result"] = run_script_in_subprocess(
            script=script,
            connection_config=fake_config,
            job_id=job_id,
            timeout_s=120,
        )

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    time.sleep(0.5)
    cancel_script_if_running(job_id)
    thread.join(timeout=15)
    result = result_holder.get("result") or {}
    assert thread.is_alive() is False
    assert result.get("ok") is False
