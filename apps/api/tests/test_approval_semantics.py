"""Unit tests for approval step semantics (CMP-5)."""

from __future__ import annotations

from app.approval_semantics import (
    ApprovalEntryState,
    ApprovalStep,
    all_steps_approved,
    can_approve_step,
    exclusive_violation,
    parse_steps,
    pending_step_order,
)


def test_parse_steps_sorted() -> None:
    steps = parse_steps(
        [
            {"order": 2, "approver_user_ids": [3]},
            {"order": 1, "approver_user_ids": [2], "exclusive": True},
        ]
    )
    assert [s.order for s in steps] == [1, 2]
    assert steps[0].exclusive is True


def test_ordered_steps_require_sequence() -> None:
    steps = [
        ApprovalStep(order=1, approver_user_ids=(2,)),
        ApprovalStep(order=2, approver_user_ids=(3,)),
    ]
    entries = [ApprovalEntryState(step_order=1, status="approved", approver_user_id=2)]
    assert pending_step_order(steps, entries) == 2
    ok, reason = can_approve_step(
        step=steps[1],
        user_id=3,
        user_group_ids=set(),
        entries=entries,
        all_steps=steps,
    )
    assert ok is True
    ok2, _ = can_approve_step(
        step=steps[1],
        user_id=3,
        user_group_ids=set(),
        entries=[],
        all_steps=steps,
    )
    assert ok2 is False


def test_exclusive_blocks_second_step() -> None:
    steps = [
        ApprovalStep(order=1, approver_user_ids=(2,), exclusive=True),
        ApprovalStep(order=2, approver_user_ids=(2,)),
    ]
    entries = [ApprovalEntryState(step_order=1, status="approved", approver_user_id=2)]
    assert exclusive_violation(step=steps[1], user_id=2, entries=entries, all_steps=steps) is True


def test_all_steps_approved() -> None:
    steps = [ApprovalStep(order=1, approver_user_ids=(2,))]
    entries = [ApprovalEntryState(step_order=1, status="approved", approver_user_id=2)]
    assert all_steps_approved(steps, entries) is True
