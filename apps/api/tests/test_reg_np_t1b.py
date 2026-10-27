"""Pin REG-NP-T1b from one live Option A sandbox prove.

The pin is the value that run returned. A skipped stack is not a pass.
Pytest fakes Docker unless INGENIUM_LIVE_INFRA=1, and this card's test command
does not set that, so the live call is the captured log, not a second prove.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.sandbox import sandbox_stack_for_major

pytestmark = pytest.mark.no_app_db

_REPO = Path(__file__).resolve().parents[3]
_CARD = _REPO / "docs/build-plan/cards/phase-0/REG-NP-T1b.md"
_LOG = _REPO / ".cache" / "reg_np_t1b_prove_19.log"
_CAPTURED = "captured 2026-10-22 from current behaviour"
_INSTALL_READY_PIN = "install_ready: absent (not true)"
_PROVE_STATUS_PIN = "prove_status: proved"
_LOG_PIN = ".cache/reg_np_t1b_prove_19.log"


def test_ac1_pins_captured_install_ready_and_does_not_skip() -> None:
    card = _CARD.read_text(encoding="utf-8")
    assert _CAPTURED in card
    captured = card.split(_CAPTURED, 1)[1]
    assert _INSTALL_READY_PIN in captured
    assert _PROVE_STATUS_PIN in captured
    assert _LOG_PIN in captured

    assert _LOG.is_file(), "sandbox log missing; a skipped stack is not a pass"
    log_text = _LOG.read_text(encoding="utf-8")
    assert "project=ingenium_sandbox_v19" in log_text
    assert "port=18119" in log_text
    assert "run_tests=True" in log_text
    assert "install_ready='ABSENT'" in log_text
    assert "prove_status='proved'" in log_text
    assert "tests_ran=True" in log_text
    assert "0 failed, 0 error(s) of 1 tests" in log_text
    assert "test-enable ok for option_a_prove_note" in log_text
    lowered = log_text.lower()
    assert "sandbox call skipped" not in lowered
    assert "docker is faked in tests" not in lowered
    assert "pytest.skip" not in lowered

    stack = sandbox_stack_for_major(19)
    assert stack.project == "ingenium_sandbox_v19"
    assert stack.port == 18119
