"""GATE-L4-04: a standing rule activates only after two distinct admins, one the owner.

L4 stays off. This file does not enable a runtime level.
"""

from __future__ import annotations

import pytest

from app.worker_bot.l4_policy import HUMAN_ADMIN_ROLES
from app.worker_bot.runtime import WorkerBot
from app.worker_bot.standing_rule import (
    GATE_L4_04,
    STANDING_RULE_ROLES,
    StandingRuleBook,
    standing_rule_is_active,
)

pytestmark = pytest.mark.no_app_db

_OWNER = "user-owner"
_ADMIN = "user-admin"
_OTHER = "user-other"


def test_gate_id_is_gate_l4_04() -> None:
    assert GATE_L4_04 == "GATE-L4-04"
    assert STANDING_RULE_ROLES == HUMAN_ADMIN_ROLES


def test_rule_is_inactive_until_owner_and_a_second_admin_approve() -> None:
    book = StandingRuleBook()
    opened = book.open("rule-1")
    assert opened.active is False
    assert opened.admin_user_ids == frozenset()

    owner_only = book.approve("rule-1", {"user_id": _OWNER, "role": "owner", "label": "Ada"})
    assert owner_only.active is False
    assert owner_only.admin_user_ids == frozenset({_OWNER})
    assert owner_only.owner_user_ids == frozenset({_OWNER})

    active = book.approve(
        "rule-1",
        {"user_id": _ADMIN, "role": "admin", "label": "Grace", "approver_id": "client-label"},
    )
    assert active.active is True
    assert active.admin_user_ids == frozenset({_OWNER, _ADMIN})
    assert active.owner_user_ids == frozenset({_OWNER})


def test_admin_then_owner_activates() -> None:
    book = StandingRuleBook()
    assert book.approve("rule-1", {"user_id": _ADMIN, "role": "Admin"}).active is False
    view = book.approve("rule-1", {"user_id": _OWNER, "role": "Owner"})
    assert view.active is True
    assert view.owner_user_ids == frozenset({_OWNER})


def test_two_owners_activate() -> None:
    approvals = (
        {"user_id": _OWNER, "role": "owner"},
        {"user_id": _OTHER, "role": "owner"},
    )
    assert standing_rule_is_active(approvals) is True


def test_same_admin_twice_does_not_activate() -> None:
    approvals = (
        {"user_id": _ADMIN, "role": "admin", "label": "Ada", "approver_id": "ada"},
        {
            "user_id": _ADMIN,
            "role": "admin",
            "label": "Grace",
            "approver_id": "grace",
            "display_name": "Someone else",
        },
    )
    assert standing_rule_is_active(approvals) is False
    book = StandingRuleBook()
    book.approve("rule-1", approvals[0])
    view = book.approve("rule-1", approvals[1])
    assert view.active is False
    assert view.admin_user_ids == frozenset({_ADMIN})
    assert view.owner_user_ids == frozenset()


def test_same_user_id_with_owner_role_is_still_one_person() -> None:
    approvals = (
        {"user_id": _OWNER, "role": "admin", "label": "Ada"},
        {"user_id": _OWNER, "role": "owner", "label": "Ada Owner", "approver_id": "second-seat"},
    )
    assert standing_rule_is_active(approvals) is False
    book = StandingRuleBook()
    book.approve("rule-1", approvals[0])
    view = book.approve("rule-1", approvals[1])
    assert view.active is False
    assert view.admin_user_ids == frozenset({_OWNER})
    assert view.owner_user_ids == frozenset({_OWNER})


def test_two_admins_who_are_not_the_owner_do_not_activate() -> None:
    approvals = (
        {"user_id": _ADMIN, "role": "admin", "label": "owner"},
        {"user_id": _OTHER, "role": "admin", "approver_id": "workspace-owner"},
    )
    assert standing_rule_is_active(approvals) is False
    book = StandingRuleBook()
    book.approve("rule-1", approvals[0])
    view = book.approve("rule-1", approvals[1])
    assert view.active is False
    assert view.owner_user_ids == frozenset()
    assert view.admin_user_ids == frozenset({_ADMIN, _OTHER})


def test_omitted_user_id_is_not_a_second_person() -> None:
    book = StandingRuleBook()
    book.approve("rule-1", {"user_id": _OWNER, "role": "owner"})
    missing = book.approve(
        "rule-1",
        {"role": "admin", "label": "Grace", "approver_id": _ADMIN, "display_name": "Grace"},
    )
    assert missing.active is False
    assert missing.admin_user_ids == frozenset({_OWNER})

    blank = book.approve("rule-1", {"user_id": "  ", "role": "admin", "label": _OTHER})
    assert blank.active is False
    assert blank.admin_user_ids == frozenset({_OWNER})

    not_a_string = book.approve("rule-1", {"user_id": 2, "role": "admin"})
    assert not_a_string.active is False
    assert standing_rule_is_active(
        (
            {"role": "owner", "approver_id": _OWNER, "label": "Ada"},
            {"role": "admin", "approver_id": _ADMIN, "label": "Grace"},
        )
    ) is False


def test_non_admin_plus_owner_does_not_activate() -> None:
    book = StandingRuleBook()
    book.approve("rule-1", {"user_id": _OWNER, "role": "owner"})
    view = book.approve("rule-1", {"user_id": _OTHER, "role": "viewer", "label": "admin"})
    assert view.active is False
    assert view.admin_user_ids == frozenset({_OWNER})


def test_books_do_not_share_approvals() -> None:
    left = StandingRuleBook()
    right = StandingRuleBook()
    left.approve("rule-1", {"user_id": _OWNER, "role": "owner"})
    left.approve("rule-1", {"user_id": _ADMIN, "role": "admin"})
    assert left.get("rule-1").active is True
    assert right.get("rule-1").active is False
    assert right.open("rule-1").active is False


def test_second_open_does_not_clear_approvals() -> None:
    book = StandingRuleBook()
    book.approve("rule-1", {"user_id": _OWNER, "role": "owner"})
    book.approve("rule-1", {"user_id": _ADMIN, "role": "admin"})
    assert book.open("rule-1").active is True


def test_blank_rule_id_is_refused() -> None:
    book = StandingRuleBook()
    with pytest.raises(ValueError, match="invalid standing rule id"):
        book.open("  ")


def test_active_standing_rule_does_not_enable_l4() -> None:
    book = StandingRuleBook()
    book.approve("rule-1", {"user_id": _OWNER, "role": "owner"})
    view = book.approve("rule-1", {"user_id": _ADMIN, "role": "admin"})
    assert view.active is True
    with pytest.raises(ValueError, match="invalid autonomy level"):
        WorkerBot("L4")
