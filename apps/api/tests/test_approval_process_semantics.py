"""Unit tests for CMP-10 approval process chain semantics."""

from __future__ import annotations

import json

from app.approval_process_semantics import (
    LevelApproval,
    all_levels_satisfied,
    can_approve_at_level,
    dump_level_approvals,
    is_refused,
    parse_chain,
    parse_level_approvals,
    pending_level,
)


def test_two_level_chain_min_approvals_two_at_level_one() -> None:
    chain = parse_chain(
        [
            {"level": 1, "min_approvals": 2, "approver_user_ids": [2, 3, 4]},
            {"level": 2, "min_approvals": 1, "approver_user_ids": [5]},
        ]
    )
    levels: dict[int, list[LevelApproval]] = {}
    assert pending_level(chain, levels) == 1
    levels[1] = [LevelApproval(user_id=2, status="approved")]
    assert pending_level(chain, levels) == 1
    levels[1].append(LevelApproval(user_id=3, status="approved"))
    assert pending_level(chain, levels) == 2
    levels[2] = [LevelApproval(user_id=5, status="approved")]
    assert pending_level(chain, levels) is None
    assert all_levels_satisfied(chain, levels)


def test_refusal_short_circuits() -> None:
    chain = parse_chain([{"level": 1, "min_approvals": 1, "approver_user_ids": [2]}])
    levels = {1: [LevelApproval(user_id=2, status="refused")]}
    assert is_refused(levels)
    assert pending_level(chain, levels) is None


def test_can_approve_requires_pending_level() -> None:
    chain = parse_chain(
        [
            {"level": 1, "min_approvals": 1, "approver_user_ids": [2]},
            {"level": 2, "min_approvals": 1, "approver_user_ids": [3]},
        ]
    )
    lv2 = chain[1]
    ok, msg = can_approve_at_level(
        level=lv2,
        pending=1,
        user_id=3,
        user_group_ids=set(),
        existing=[],
    )
    assert ok is False
    assert "Level 1" in msg


def test_dump_and_parse_roundtrip() -> None:
    raw = dump_level_approvals({1: [LevelApproval(user_id=2, status="approved")]})
    parsed = parse_level_approvals(raw)
    assert parsed[1][0].user_id == 2
    assert json.loads(raw)["levels"]["1"][0]["status"] == "approved"
