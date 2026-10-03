"""T8-CRITIC. An approve verdict does not change the policy decision."""

from __future__ import annotations

import pytest

from app.agent_runtime.critic import (
    CHECKLIST,
    CriticPlan,
    CriticResult,
    critic_runs,
    judge,
    plan_risk,
    policy_stands,
    review,
)
from app.changeset.policy import policy_decision

pytestmark = pytest.mark.no_app_db

_DELETE = {
    "type": "data.delete",
    "params": {"model": "res.partner"},
    "risk": "R0",
}
_FIELD = {
    "type": "field.create",
    "params": {"model": "sale.order", "name": "x_po_reference"},
}


def _r4_plan(*, environment: str = "production") -> CriticPlan:
    return CriticPlan(
        ops=(_DELETE,),
        goal="",
        requested_models=("sale.order",),
        assumptions=("Partners are unused.",),
        questions=(),
        dependents=(),
        referenced_dependents=("res.partner.bank",),
        labels=("data.delete",),
        claims_full_rollback=True,
        topic="financial",
        environment=environment,
    )


def _clean_plan() -> CriticPlan:
    return CriticPlan(
        ops=(_FIELD,),
        goal="Add a customer PO reference on sales orders.",
        requested_models=("sale.order",),
        assumptions=(),
        questions=(),
        dependents=(),
        referenced_dependents=(),
        labels=("Add the customer PO reference on sales orders.",),
        claims_full_rollback=True,
        topic="general",
    )


def test_checklist_matches_the_card() -> None:
    assert CHECKLIST == (
        "coverage",
        "scope creep",
        "assumptions that should be questions",
        "missed dependents",
        "rollback realism",
        "security",
        "business red flags",
        "wording",
    )


@pytest.mark.parametrize(
    ("tier", "risk", "op_count", "expected"),
    [
        ("A", "R2", 1, True),
        ("A", "R3", 0, True),
        ("A", "R4", 1, True),
        ("A", "R1", 5, True),
        ("A", "R0", 5, True),
        ("A", "R1", 4, False),
        ("A", "R0", 0, False),
        ("A", "R2", 0, True),
        ("B", "R4", 9, False),
        ("C", "R3", 5, False),
        (None, "R2", 5, False),
        ("A", "r2", 5, False),
        ("a", "R4", 5, False),
    ],
)
def test_critic_runs_for_tier_a_at_r2_or_five_ops(
    tier: str | None,
    risk: str,
    op_count: int,
    expected: bool,
) -> None:
    assert critic_runs(tier=tier, risk=risk, op_count=op_count) is expected


@pytest.mark.parametrize("op_count", [-1, True])
def test_critic_runs_rejects_a_bad_op_count(op_count: object) -> None:
    with pytest.raises(ValueError):
        critic_runs(tier="A", risk="R2", op_count=op_count)  # type: ignore[arg-type]


def test_review_covers_every_checklist_item() -> None:
    findings = review(_r4_plan())
    assert {finding.item for finding in findings} == set(CHECKLIST)
    assert [finding.item for finding in findings] == sorted(
        (finding.item for finding in findings),
        key=CHECKLIST.index,
    )


def test_r0_and_r1_may_keep_a_stated_assumption() -> None:
    plan = CriticPlan(
        ops=(
            {
                "type": "field.update",
                "params": {"model": "sale.order", "name": "client_order_ref"},
            },
        ),
        goal="Adjust the customer reference label.",
        requested_models=("sale.order",),
        assumptions=("Use the existing field.",),
        labels=("Update the customer reference label.",),
    )
    assert plan_risk(plan.ops) == "R1"
    items = {finding.item for finding in review(plan)}
    assert "assumptions that should be questions" not in items


def test_a_caller_risk_key_does_not_lower_the_class() -> None:
    assert plan_risk((_DELETE,)) == "R4"


def test_clean_tier_a_plan_can_approve_without_becoming_verified() -> None:
    result = judge(_clean_plan(), tier="A")
    decision = policy_decision("R2", "production")
    assert result.ran is True
    assert result.verdict == "approve"
    assert result.findings == ()
    assert result.risk == "R2"
    assert result.policy == decision
    assert result.policy["approvers"] == 1
    assert result.policy["allow"] is True
    assert result.verified is False
    assert result.waivers_ignored == ()


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_critic_approve_on_r4_does_not_change_policy(environment: str) -> None:
    result = judge(
        _r4_plan(environment=environment),
        tier="A",
        verdict="approve",
        claimed_risk="R0",
        skip_approval=True,
        mark_verified=True,
    )
    decision = policy_decision("R4", environment)
    stood = policy_stands(
        "R4",
        environment,
        verdict="approve",
        claimed_risk="R0",
        skip_approval=True,
        mark_verified=True,
    )
    assert result.ran is True
    assert result.verdict == "approve"
    assert result.risk == "R4"
    assert result.policy == decision
    assert result.policy == stood
    assert result.policy["deny"] is True
    assert result.policy["allow"] is False
    assert result.verified is False
    assert result.waivers_ignored == (
        "claimed_risk",
        "skip_approval",
        "mark_verified",
        "approve",
    )
    assert "verified" not in result.policy


def test_r4_revise_is_also_denied() -> None:
    result = judge(_r4_plan(), tier="A")
    assert result.verdict == "revise"
    assert result.policy == policy_decision("R4", "production")
    assert result.policy["deny"] is True
    assert result.verified is False


def test_approve_cannot_skip_r3_approval_or_mark_verified() -> None:
    plan = CriticPlan(
        ops=({"type": "access.create", "params": {"model": "sale.order", "group": "sales"}},),
        goal="Add sales access on sales orders.",
        requested_models=("sale.order",),
        labels=("Grant the sales group access to sales orders.",),
    )
    result = judge(
        plan,
        tier="A",
        verdict="approve",
        claimed_risk="R0",
        skip_approval=True,
        mark_verified=True,
    )
    decision = policy_decision("R3", "production")
    assert result.risk == "R3"
    assert result.policy == decision
    assert result.policy["approvers"] == 2
    assert result.policy["allow"] is True
    assert result.verified is False


def test_tier_b_does_not_run_and_r4_stays_denied() -> None:
    result = judge(
        _r4_plan(),
        tier="B",
        verdict="approve",
        claimed_risk="R1",
        skip_approval=True,
        mark_verified=True,
    )
    assert result.ran is False
    assert result.verdict == "not_run"
    assert result.findings == ()
    assert result.risk == "R4"
    assert result.policy == policy_decision("R4", "production")
    assert result.policy["deny"] is True
    assert result.verified is False


def test_five_r1_ops_run_for_tier_a_and_four_do_not() -> None:
    def plan(count: int) -> CriticPlan:
        ops = tuple(
            {"type": "field.update", "params": {"model": "sale.order", "name": f"x_{index}"}}
            for index in range(count)
        )
        return CriticPlan(
            ops=ops,
            goal="Update sales order fields.",
            requested_models=("sale.order",),
            labels=tuple(f"Update sales order field {index}." for index in range(count)),
        )

    ran = judge(plan(5), tier="A")
    skipped = judge(plan(4), tier="A")
    assert ran.ran is True
    assert ran.risk == "R1"
    assert ran.policy == policy_decision("R1", "production")
    assert ran.verified is False
    assert skipped.ran is False
    assert skipped.verdict == "not_run"
    assert skipped.policy == policy_decision("R1", "production")


def test_result_cannot_be_constructed_as_verified() -> None:
    with pytest.raises(ValueError, match="cannot mark a plan verified"):
        CriticResult(
            ran=True,
            verdict="approve",
            findings=(),
            risk="R4",
            policy=policy_decision("R4", "production"),
            verified=True,
        )
