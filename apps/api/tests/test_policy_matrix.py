"""Policy matrix: ten risk × environment cells, plus freeze and expiry."""

from __future__ import annotations

import pytest

from app.changeset.policy import (
    apply_blocked,
    approval_count_met,
    approval_expiry_hours,
    policy_decision,
    self_approval_allowed,
)

pytestmark = pytest.mark.no_app_db

_WEEK_HOURS = 7 * 24
_DAY_HOURS = 24
_RISKS = ("R0", "R1", "R2", "R3", "R4")
_ENVIRONMENTS = ("staging", "production")

# Default autonomy is L2. Elevated is false. Staging R1 at L3+ is asserted in the test.
_MATRIX = (
    {
        "risk": "R0",
        "environment": "staging",
        "allow": True,
        "approvers": 0,
        "needs_simulation": False,
        "deny": False,
        "needs_backup": False,
        "needs_window": False,
        "expiry_hours": _WEEK_HOURS,
        "self_approval": True,
    },
    {
        "risk": "R1",
        "environment": "staging",
        "allow": True,
        "approvers": 1,
        "needs_simulation": False,
        "deny": False,
        "needs_backup": False,
        "needs_window": False,
        "expiry_hours": _WEEK_HOURS,
        "self_approval": True,
    },
    {
        "risk": "R2",
        "environment": "staging",
        "allow": True,
        "approvers": 1,
        "needs_simulation": False,
        "deny": False,
        "needs_backup": False,
        "needs_window": False,
        "expiry_hours": _WEEK_HOURS,
        "self_approval": True,
    },
    {
        "risk": "R3",
        "environment": "staging",
        "allow": True,
        "approvers": 1,
        "needs_simulation": False,
        "deny": False,
        "needs_backup": False,
        "needs_window": False,
        "expiry_hours": _WEEK_HOURS,
        "self_approval": True,
    },
    {
        "risk": "R4",
        "environment": "staging",
        "allow": False,
        "approvers": 0,
        "needs_simulation": False,
        "deny": True,
        "needs_backup": False,
        "needs_window": False,
        "expiry_hours": _WEEK_HOURS,
        "self_approval": False,
    },
    {
        "risk": "R0",
        "environment": "production",
        "allow": True,
        "approvers": 0,
        "needs_simulation": False,
        "deny": False,
        "needs_backup": False,
        "needs_window": False,
        "expiry_hours": _WEEK_HOURS,
        "self_approval": True,
    },
    {
        "risk": "R1",
        "environment": "production",
        "allow": True,
        "approvers": 1,
        "needs_simulation": True,
        "deny": False,
        "needs_backup": False,
        "needs_window": False,
        "expiry_hours": _WEEK_HOURS,
        "self_approval": True,
    },
    {
        "risk": "R2",
        "environment": "production",
        "allow": True,
        "approvers": 1,
        "needs_simulation": True,
        "deny": False,
        "needs_backup": False,
        "needs_window": False,
        "expiry_hours": _DAY_HOURS,
        "self_approval": True,
    },
    {
        "risk": "R3",
        "environment": "production",
        "allow": True,
        "approvers": 1,
        "needs_simulation": False,
        "deny": False,
        "needs_backup": False,
        "needs_window": False,
        "expiry_hours": _DAY_HOURS,
        "self_approval": True,
    },
    {
        "risk": "R4",
        "environment": "production",
        "allow": False,
        "approvers": 0,
        "needs_simulation": False,
        "deny": True,
        "needs_backup": False,
        "needs_window": False,
        "expiry_hours": _DAY_HOURS,
        "self_approval": False,
    },
)


def _cell_id(cell: dict[str, object]) -> str:
    return f"{cell['environment']}-{cell['risk']}"


def test_matrix_covers_every_risk_and_environment() -> None:
    covered = {(row["risk"], row["environment"]) for row in _MATRIX}
    expected = {(risk, env) for risk in _RISKS for env in _ENVIRONMENTS}
    assert covered == expected
    assert len(_MATRIX) == 10


@pytest.mark.parametrize("cell", _MATRIX, ids=_cell_id)
def test_policy_matrix_cell(cell: dict[str, object]) -> None:
    risk = str(cell["risk"])
    environment = str(cell["environment"])
    decision = policy_decision(risk, environment)
    assert decision["allow"] is cell["allow"]
    assert decision["approvers"] == cell["approvers"]
    assert decision["needs_simulation"] is cell["needs_simulation"]
    assert decision["deny"] is cell["deny"]
    assert decision["needs_backup"] is cell["needs_backup"]
    assert decision["needs_window"] is cell["needs_window"]
    assert decision["domain_owner"] is False
    assert decision["expiry_hours"] == cell["expiry_hours"]
    assert approval_expiry_hours(risk, environment) == cell["expiry_hours"]
    assert self_approval_allowed(risk) is cell["self_approval"]
    assert apply_blocked(decision, frozen=True) is True
    assert apply_blocked(decision, frozen=False) is (cell["deny"] or not cell["allow"])

    # L4 does not open production, or any cell other than staging R1.
    if not (risk == "R1" and environment == "staging"):
        at_l4 = policy_decision(risk, environment, autonomy="L4")
        assert at_l4["approvers"] == cell["approvers"]
        assert at_l4["allow"] is cell["allow"]
        assert at_l4["needs_simulation"] is cell["needs_simulation"]
        assert at_l4["deny"] is cell["deny"]

    if risk == "R1" and environment == "staging":
        assert policy_decision(risk, environment, autonomy="L2")["approvers"] == 1
        assert policy_decision(risk, environment, autonomy="L1")["approvers"] == 1
        for level in ("L3", "L4"):
            opened = policy_decision(risk, environment, autonomy=level)
            assert opened["approvers"] == 0
            assert opened["allow"] is True
            assert opened["deny"] is False
            assert opened["needs_simulation"] is False
            assert apply_blocked(opened, frozen=True) is True

    elevated = policy_decision(risk, environment, elevated=True)
    if cell["deny"]:
        assert elevated["domain_owner"] is False
        assert elevated["allow"] is False
        assert elevated["deny"] is True
    else:
        assert elevated["domain_owner"] is True
        assert elevated["approvers"] == cell["approvers"]
        assert elevated["needs_backup"] is cell["needs_backup"]
        assert elevated["needs_window"] is cell["needs_window"]
        assert elevated["needs_simulation"] is cell["needs_simulation"]
        assert apply_blocked(elevated, frozen=True) is True

    if risk == "R3":
        assert self_approval_allowed(risk) is True
        assert decision["approvers"] == 1
        assert decision["needs_simulation"] is False
        assert decision["needs_backup"] is False
        assert decision["needs_window"] is False
        required = int(decision["approvers"])
        assert approval_count_met(required, required) is True
        assert approval_count_met(required - 1, required) is False


def test_heavy_r4_keeps_two_people_and_l4_cannot_skip_it() -> None:
    """Heavy production R4 stays a two-person gate. L4 cannot apply R3 or R4."""
    staging = policy_decision("R4", "staging", heavy=True, autonomy="L4")
    assert staging["allow"] is True
    assert staging["deny"] is False
    assert staging["approvers"] == 1
    assert staging["needs_simulation"] is False
    production = policy_decision("R4", "production", heavy=True, autonomy="L4", elevated=True)
    assert production["allow"] is True
    assert production["deny"] is False
    assert production["approvers"] == 2
    assert production["needs_simulation"] is True
    assert production["needs_backup"] is True
    assert production["needs_window"] is True
    assert production["domain_owner"] is True
    hard = policy_decision("R4", "production", autonomy="L4")
    assert hard["deny"] is True
    assert hard["allow"] is False
    r3 = policy_decision("R3", "production", autonomy="L4")
    assert r3["approvers"] == 1
    assert r3["needs_simulation"] is False


def test_equal_approver_count_meets_the_requirement() -> None:
    """A mutant that flips >= to > fails the equal-count cases."""
    for required in (0, 1, 2):
        assert approval_count_met(required, required) is True
        assert approval_count_met(required - 1, required) is False
    assert approval_count_met(2, 1) is True
