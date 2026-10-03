"""PR-D: sandbox --test-enable argv + parseable failures (no Docker required)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.sandbox import (
    SandboxResult,
    build_test_enable_argv,
    parse_odoo_test_output,
    _run_module_tests,
)


def test_build_test_enable_argv_contains_flags() -> None:
    argv = build_test_enable_argv("x_demo_app", odoo_major=19)
    assert "--test-enable" in argv
    assert "--stop-after-init" in argv
    assert "--http-port" in argv
    assert argv[argv.index("--http-port") + 1] == "8070"
    assert "-u" in argv
    assert argv[argv.index("-u") + 1] == "x_demo_app"
    assert "-d" in argv
    assert argv[argv.index("-d") + 1] == "sandbox_test"


def test_parse_odoo_test_output_fail_and_error_lines() -> None:
    blob = """
Running tests...
FAIL: TestFoo.test_bar
AssertionError: expected True
ERROR: TestFoo.test_baz
Traceback (most recent call last):
1 failed, 1 error(s) of 3 tests
"""
    rows = parse_odoo_test_output(blob)
    assert any(r.startswith("FAIL: TestFoo.test_bar") for r in rows)
    assert any(r.startswith("ERROR: TestFoo.test_baz") for r in rows)
    assert any("SUMMARY:" in r and "1 failed" in r for r in rows)


def test_parse_odoo_test_output_clean_log_empty() -> None:
    assert parse_odoo_test_output("0 failed, 0 error(s) of 12 tests\nAll good") == []


def test_run_module_tests_passes_test_enable_via_compose_exec() -> None:
    captured: list[tuple] = []

    def fake_compose(*args, check=True, odoo_major=19, job_id=None):  # noqa: ANN001
        captured.append(args)
        return MagicMock(returncode=0, stdout="0 failed, 0 error(s)\n", stderr="")

    with patch("app.sandbox._compose", side_effect=fake_compose):
        ok, _log, failures = _run_module_tests("x_demo_app", odoo_major=19)

    assert ok is True
    assert failures == []
    assert captured, "compose exec should be invoked"
    args = captured[0]
    assert args[:3] == ("exec", "-T", "odoo")
    assert "--test-enable" in args
    assert "--stop-after-init" in args
    assert "x_demo_app" in args


def test_run_module_tests_failing_module_is_parseable() -> None:
    """Sandbox mark: failing test → ok=False with FAIL line in failures."""

    def fake_compose(*args, check=True, odoo_major=19, job_id=None):  # noqa: ANN001
        return MagicMock(
            returncode=1,
            stdout="",
            stderr="FAIL: test_ingenium_smoke.test_always_false\n1 failed, 0 error(s)\n",
        )

    with patch("app.sandbox._compose", side_effect=fake_compose):
        ok, log, failures = _run_module_tests("x_failing_mod", odoo_major=19)

    assert ok is False
    assert any("FAIL: test_ingenium_smoke.test_always_false" in f for f in failures)
    assert "FAIL:" in log


def test_sandbox_result_defaults_tests_off() -> None:
    result = SandboxResult(ok=True, module="x_a", message="ok")
    assert result.tests_ran is False
    assert result.test_failures == []
