"""T8-CLARIFY rules on the scripted adapter.

EV-AMB-01 through EV-AMB-08 are assigned ids. Their YAML scenario bodies
are still missing. These tests do not invent those stories and do not
claim those ids passed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.agent_runtime.clarify import (
    ASSIGNED_EVAL_IDS,
    YAML_BODIES_MISSING,
    ClarifyCase,
    decide,
    score_scripted_turn,
)
from app.llm_gateway.scripted import ScriptedAdapter
from app.llm_gateway.types import LLMResponse

pytestmark = pytest.mark.no_app_db

_ASSUMPTION = "Use the stated form placement."
_TARGET_Q = "Which target should this change use?"
_DEFAULT_Q = "Which option should be used? There is no safe default."
_SPEC_Q = "This request is R3 or higher and underspecified. What exactly should change?"
_SOURCE_Q = "The sources disagree. Which source should be followed?"
_FINANCIAL_Q = "This topic is financial. What should be confirmed before planning?"
_HR_Q = "This topic is HR. What should be confirmed before planning?"
_LEGAL_Q = "This topic is legal. What should be confirmed before planning?"
_RISK_Q = "The risk class is not R0, R1, R2, R3, or R4. What is the request?"


@dataclass(frozen=True, slots=True)
class _Script:
    name: str
    case: ClarifyCase
    step: dict[str, Any]
    passed: bool
    action: str
    reasons: tuple[str, ...]
    failure: str | None = None


def _ask(question: str) -> dict[str, Any]:
    return {"tool_calls": [{"name": "ask_user", "args": {"questions": [question]}}]}


def _proceed(text: str = "") -> dict[str, Any]:
    return {"stop_reason": "end", "text": text}


def _one(model: str = "sale.order") -> tuple[str, ...]:
    return (model,)


_SCRIPTS = (
    _Script(
        "two_targets_ask",
        ClarifyCase(
            risk="R1",
            matching_targets=("sale.order", "purchase.order"),
            safe_default="sale.order",
            assumptions=(_ASSUMPTION,),
        ),
        _ask(_TARGET_Q),
        True,
        "ask",
        ("multiple_targets",),
    ),
    _Script(
        "two_targets_ignored_fails",
        ClarifyCase(
            risk="R0",
            matching_targets=("sale.order", "purchase.order"),
            safe_default="sale.order",
            assumptions=(_ASSUMPTION,),
        ),
        _proceed(_ASSUMPTION),
        False,
        "ask",
        ("multiple_targets",),
        "questions_mismatch",
    ),
    _Script(
        "no_safe_default_r2_asks",
        ClarifyCase(risk="R2", matching_targets=_one(), safe_default=None),
        _ask(_DEFAULT_Q),
        True,
        "ask",
        ("no_safe_default",),
    ),
    _Script(
        "r0_missing_default_proceeds_with_assumption",
        ClarifyCase(
            risk="R0",
            matching_targets=_one(),
            safe_default=None,
            assumptions=(_ASSUMPTION,),
        ),
        _proceed(_ASSUMPTION),
        True,
        "proceed",
        ("stated_assumptions",),
    ),
    _Script(
        "r1_missing_default_proceeds_with_assumption",
        ClarifyCase(
            risk="r1",
            matching_targets=_one(),
            safe_default="  ",
            assumptions=(_ASSUMPTION,),
        ),
        _proceed(_ASSUMPTION),
        True,
        "proceed",
        ("stated_assumptions",),
    ),
    _Script(
        "r0_missing_default_without_assumption_asks",
        ClarifyCase(risk="R0", matching_targets=_one(), safe_default=None),
        _ask(_DEFAULT_Q),
        True,
        "ask",
        ("no_safe_default",),
    ),
    _Script(
        "r2_assumptions_do_not_waive_missing_default",
        ClarifyCase(
            risk="R2",
            matching_targets=_one(),
            safe_default=None,
            assumptions=(_ASSUMPTION,),
        ),
        _proceed(_ASSUMPTION),
        False,
        "ask",
        ("no_safe_default",),
        "questions_mismatch",
    ),
    _Script(
        "r3_underspecified_asks",
        ClarifyCase(
            risk="R3",
            matching_targets=_one("account.move"),
            safe_default="draft",
            underspecified=True,
        ),
        _ask(_SPEC_Q),
        True,
        "ask",
        ("underspecified_r3",),
    ),
    _Script(
        "r4_underspecified_asks",
        ClarifyCase(
            risk="R4",
            matching_targets=_one("account.move"),
            safe_default="draft",
            underspecified=True,
        ),
        _ask(_SPEC_Q),
        True,
        "ask",
        ("underspecified_r3",),
    ),
    _Script(
        "r3_specified_proceeds",
        ClarifyCase(
            risk="R3",
            matching_targets=_one("account.move"),
            safe_default="draft",
            underspecified=False,
        ),
        _proceed(),
        True,
        "proceed",
        ("clear",),
    ),
    _Script(
        "r2_underspecified_with_default_proceeds",
        ClarifyCase(
            risk="R2",
            matching_targets=_one(),
            safe_default="draft",
            underspecified=True,
        ),
        _proceed(),
        True,
        "proceed",
        ("clear",),
    ),
    _Script(
        "sources_conflict_asks",
        ClarifyCase(
            risk="R0",
            matching_targets=_one(),
            safe_default="draft",
            sources_conflict=True,
            assumptions=(_ASSUMPTION,),
        ),
        _ask(_SOURCE_Q),
        True,
        "ask",
        ("sources_conflict",),
    ),
    _Script(
        "financial_asks",
        ClarifyCase(
            risk="R0",
            matching_targets=_one("account.move"),
            safe_default="draft",
            topic="Financial",
            assumptions=(_ASSUMPTION,),
        ),
        _ask(_FINANCIAL_Q),
        True,
        "ask",
        ("sensitive_topic",),
    ),
    _Script(
        "hr_asks",
        ClarifyCase(
            risk="R1",
            matching_targets=_one("hr.employee"),
            safe_default="draft",
            topic="HR",
            assumptions=(_ASSUMPTION,),
        ),
        _ask(_HR_Q),
        True,
        "ask",
        ("sensitive_topic",),
    ),
    _Script(
        "legal_asks",
        ClarifyCase(
            risk="R1",
            matching_targets=_one("account.move"),
            safe_default="draft",
            topic="legal",
        ),
        _ask(_LEGAL_Q),
        True,
        "ask",
        ("sensitive_topic",),
    ),
    _Script(
        "inventory_topic_proceeds",
        ClarifyCase(
            risk="R1",
            matching_targets=_one(),
            safe_default="draft",
            topic="inventory",
        ),
        _proceed(),
        True,
        "proceed",
        ("clear",),
    ),
    _Script(
        "duplicate_targets_do_not_ask",
        ClarifyCase(
            risk="R1",
            matching_targets=("sale.order", "Sale.Order", "  "),
            safe_default="draft",
        ),
        _proceed(),
        True,
        "proceed",
        ("clear",),
    ),
    _Script(
        "unknown_risk_asks",
        ClarifyCase(risk="R9", matching_targets=_one(), safe_default="draft"),
        _ask(_RISK_Q),
        True,
        "ask",
        ("unknown_risk",),
    ),
    _Script(
        "known_target_is_not_asked",
        ClarifyCase(
            risk="R1",
            matching_targets=("sale.order", "purchase.order"),
            safe_default="sale.order",
            known_facts=frozenset({"target"}),
        ),
        _proceed(),
        True,
        "proceed",
        ("introspection_answered",),
    ),
    _Script(
        "asking_known_target_fails",
        ClarifyCase(
            risk="R1",
            matching_targets=("sale.order", "purchase.order"),
            safe_default="sale.order",
            known_facts=frozenset({"target"}),
        ),
        _ask(_TARGET_Q),
        False,
        "proceed",
        ("introspection_answered",),
        "asked_known_fact",
    ),
    _Script(
        "known_default_is_not_asked",
        ClarifyCase(
            risk="R2",
            matching_targets=_one(),
            safe_default=None,
            known_facts=frozenset({"default"}),
        ),
        _proceed(),
        True,
        "proceed",
        ("introspection_answered",),
    ),
    _Script(
        "known_specification_is_not_asked",
        ClarifyCase(
            risk="R3",
            matching_targets=_one("account.move"),
            safe_default="draft",
            underspecified=True,
            known_facts=frozenset({"specification"}),
        ),
        _proceed(),
        True,
        "proceed",
        ("introspection_answered",),
    ),
    _Script(
        "known_source_is_not_asked",
        ClarifyCase(
            risk="R2",
            matching_targets=_one(),
            safe_default="draft",
            sources_conflict=True,
            known_facts=frozenset({"source"}),
        ),
        _proceed(),
        True,
        "proceed",
        ("introspection_answered",),
    ),
    _Script(
        "known_financial_confirmation_is_not_asked",
        ClarifyCase(
            risk="R0",
            matching_targets=_one("account.move"),
            safe_default="draft",
            topic="financial",
            known_facts=frozenset({"sensitive_confirmation"}),
        ),
        _proceed(),
        True,
        "proceed",
        ("introspection_answered",),
    ),
    _Script(
        "asking_known_financial_confirmation_fails",
        ClarifyCase(
            risk="R0",
            matching_targets=_one("account.move"),
            safe_default="draft",
            topic="financial",
            known_facts=frozenset({"sensitive_confirmation"}),
        ),
        _ask(_FINANCIAL_Q),
        False,
        "proceed",
        ("introspection_answered",),
        "asked_known_fact",
    ),
)


def _calls(response: LLMResponse) -> tuple[dict[str, Any], ...]:
    return tuple({"name": call.name, "args": dict(call.args or {})} for call in response.tool_calls)


@pytest.mark.parametrize("script", _SCRIPTS, ids=[script.name for script in _SCRIPTS])
def test_clarification_rules_on_the_scripted_adapter(script: _Script) -> None:
    """Each rule is a structured case. The model turn is scripted."""
    decision = decide(script.case)
    assert decision.action == script.action
    assert decision.reasons == script.reasons
    adapter = ScriptedAdapter([script.step])
    response = adapter.complete({"messages": []})
    assert adapter.calls == 1
    assert type(adapter).__module__ == "app.llm_gateway.scripted"
    score = score_scripted_turn(script.case, tool_calls=_calls(response), text=response.text)
    assert score.passed is script.passed
    assert score.action == script.action
    assert score.reasons == script.reasons
    if script.failure is None:
        assert score.failures == ()
    else:
        assert script.failure in score.failures


def test_five_triggers_keep_every_reason_and_cap_the_scripted_question() -> None:
    """ask_user accepts three questions. The other triggers stay on the decision."""
    case = ClarifyCase(
        risk="R3",
        matching_targets=("sale.order", "purchase.order"),
        safe_default=None,
        underspecified=True,
        sources_conflict=True,
        topic="legal",
    )
    decision = decide(case)
    assert [question.fact for question in decision.questions] == [
        "sensitive_confirmation",
        "source",
        "target",
        "specification",
        "default",
    ]
    assert [question.text for question in decision.tool_questions] == [
        _LEGAL_Q,
        _SOURCE_Q,
        _TARGET_Q,
    ]
    assert decision.reasons == (
        "sensitive_topic",
        "sources_conflict",
        "multiple_targets",
        "underspecified_r3",
        "no_safe_default",
        "ask_user_cap",
    )
    adapter = ScriptedAdapter(
        [
            {
                "tool_calls": [
                    {
                        "name": "ask_user",
                        "args": {"questions": [question.text for question in decision.tool_questions]},
                    }
                ]
            }
        ]
    )
    response = adapter.complete({})
    score = score_scripted_turn(case, tool_calls=_calls(response), text=response.text)
    assert score.passed is True
    assert len(decision.questions) == 5
    assert len(decision.tool_questions) == 3


def test_r0_proceed_fails_when_the_scripted_text_omits_the_assumption() -> None:
    case = ClarifyCase(
        risk="R0",
        matching_targets=_one(),
        safe_default=None,
        assumptions=(_ASSUMPTION,),
    )
    adapter = ScriptedAdapter([_proceed("Proceeding without the assumption.")])
    response = adapter.complete({})
    score = score_scripted_turn(case, tool_calls=_calls(response), text=response.text)
    assert score.passed is False
    assert score.failures == ("assumption_missing",)
    assert score.action == "proceed"


def test_assigned_ev_amb_yaml_bodies_are_still_missing() -> None:
    """The eight assigned ids have no scenario bodies. They are not scored."""
    repo = Path(__file__).resolve().parents[3]
    found: list[str] = []
    for root in (repo / "apps" / "api", repo / "docs"):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if "EV-AMB" in path.name and path.suffix in {".yaml", ".yml"}:
                found.append(path.relative_to(repo).as_posix())
    assert found == []
    assert ASSIGNED_EVAL_IDS == tuple(f"EV-AMB-{index:02d}" for index in range(1, 9))
    assert "still missing" in YAML_BODIES_MISSING
    for eval_id in ASSIGNED_EVAL_IDS:
        assert eval_id in YAML_BODIES_MISSING
    assert "does not score those ids" in YAML_BODIES_MISSING
