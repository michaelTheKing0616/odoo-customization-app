"""5A-12 production budgets: caps as tests, owned items as pointers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent_runtime.runtime import (
    MAX_STEPS,
    MAX_TOOL_CALLS,
    AgentRuntime,
    BudgetExceeded,
)
from app.blast_radius import (
    PRODUCTION_APPLY_RECORD_CAP,
    BlastRadiusExceeded,
    assert_production_apply_records,
)
from app.changeset.executor import apply, reset_journal
from app.changeset.policy import policy_decision, self_approval_allowed
from app.worker_bot import WorkerBot
from app.worker_bot.l4_policy import L4_MAX_BLAST
from tests import test_bridge_protocol, test_executor_bridge

pytestmark = pytest.mark.no_app_db

_REPO = Path(__file__).resolve().parents[3]
_T6_CARD = _REPO / "docs/plans/next-phase/cards/T6_AUTH_INBOX.md"


def _reach_plan(runtime: AgentRuntime):
    state = runtime.start()
    runtime.complete_phase(state, "DISCOVER")
    runtime.complete_phase(state, "PLAN")
    return state


def test_max_steps_is_forty_and_the_41st_step_raises_budget_exceeded() -> None:
    assert MAX_STEPS == 40
    runtime = AgentRuntime()
    state = _reach_plan(runtime)
    nxt = "VALIDATE"
    while state.step < MAX_STEPS:
        runtime.complete_phase(state, nxt)
        nxt = "PLAN" if nxt == "VALIDATE" else "VALIDATE"
    assert state.step == 40
    with pytest.raises(BudgetExceeded, match="max steps"):
        runtime.complete_phase(state, nxt)
    assert state.status == "aborted_budget"


def test_max_tool_calls_is_120_and_the_121st_call_tool_raises_budget_exceeded() -> None:
    assert MAX_TOOL_CALLS == 120
    runtime = AgentRuntime()
    state = runtime.start()
    runtime.complete_phase(state, "DISCOVER")
    for i in range(MAX_TOOL_CALLS):
        runtime.call_tool(state, "schema_search", {"query": f"q{i}"})
    assert state.tool_calls == 120
    assert state.step == 1
    with pytest.raises(BudgetExceeded, match="max tool calls"):
        runtime.call_tool(state, "schema_search", {"query": "q120"})
    assert state.status == "aborted_budget"


def test_production_apply_refuses_201_records_and_l4_cap_stays_50_inactive() -> None:
    assert PRODUCTION_APPLY_RECORD_CAP == 200
    assert L4_MAX_BLAST == 50
    with pytest.raises(ValueError, match="invalid autonomy level"):
        WorkerBot("L4")
    assert_production_apply_records(201, environment="development")
    assert_production_apply_records(201, environment="")
    assert_production_apply_records(200, environment="production")
    with pytest.raises(BlastRadiusExceeded, match="201"):
        assert_production_apply_records(201, environment="production")
    reset_journal()
    op = {
        "type": "field.create",
        "params": {"model": "sale.order", "name": "x_po", "ids": list(range(201))},
    }
    with pytest.raises(BlastRadiusExceeded):
        apply([op], mode="T", environment="production")
    assert apply([op], mode="T", environment="development")["status"] in {"APPLIED", "VERIFIED"}


def test_change_windows_owned_by_t6_04_and_t6_06() -> None:
    """Pointer only. T6-04 owns freeze-on-approve; T6-06 owns the R3 allowed window."""
    text = _T6_CARD.read_text(encoding="utf-8")
    assert "### T6-04" in text
    assert "a freeze window blocks approve" in text
    assert "### T6-06" in text
    assert "an allowed window" in text


def test_r3_is_one_approval_and_l4_does_not_apply_it() -> None:
    """R3 is one approval. The requester may approve. L4 does not drop that approval."""
    text = _T6_CARD.read_text(encoding="utf-8")
    assert "### T6-06" in text
    assert self_approval_allowed("R3") is True
    assert self_approval_allowed("R4") is False
    assert self_approval_allowed("R2") is True
    decision = policy_decision("R3", "production", autonomy="L4")
    assert decision["approvers"] == 1
    assert decision["deny"] is False


def test_kill_switch_owned_by_existing_bridge_tests() -> None:
    """Pointer: do not build a second kill switch."""
    assert hasattr(test_bridge_protocol, "test_kill_switch_protocol_and_escalation_refuse_before_work")
    assert hasattr(test_executor_bridge, "test_reader_and_kill_switch_do_not_touch_the_port_or_journal")
