"""Inbox rules: hash binding, self-approval, and connection scope."""

from __future__ import annotations

import pytest

from app.changeset.inbox import Inbox, InboxError


def _field() -> dict:
    return {"type": "field.create", "params": {"model": "x_m", "name": "x_note"}}


def test_submit_renders_a_card_and_hides_other_connections() -> None:
    inbox = Inbox()
    result = inbox.submit(
        [_field()],
        goal="Add a note",
        assumptions=["the field is empty"],
        environment="staging",
        requester_id="u1",
        known_models={"x_m"},
        connection_id="c1",
    )
    assert result["ok"] is True
    assert inbox.visible("c2") == []
    assert len(inbox.visible("c1")) == 1


def test_r4_is_not_queued() -> None:
    inbox = Inbox()
    result = inbox.submit(
        [{"type": "module.uninstall", "params": {"model": "sale"}}],
        goal="remove",
        assumptions=[],
        environment="production",
        requester_id="u1",
        known_models={"sale"},
        connection_id="c1",
    )
    assert result["ok"] is False


def test_requester_cannot_approve_r3() -> None:
    inbox = Inbox()
    result = inbox.submit(
        [{"type": "access.create", "params": {"model": "res.partner", "name": "x_acl"}}],
        goal="grant",
        assumptions=[],
        environment="production",
        requester_id="u1",
        known_models={"res.partner"},
        connection_id="c1",
    )
    assert result["ok"] is True
    with pytest.raises(InboxError, match="requester"):
        inbox.decide(
            result["card"]["plan_hash"],
            approver_id="u1",
            decision="approve",
            connection_id="c1",
        )


def test_other_connection_is_not_found() -> None:
    inbox = Inbox()
    result = inbox.submit(
        [_field()],
        goal="Add a note",
        assumptions=[],
        environment="staging",
        requester_id="u1",
        known_models={"x_m"},
        connection_id="c1",
    )
    with pytest.raises(InboxError, match="not found"):
        inbox.decide(
            result["card"]["plan_hash"],
            approver_id="u2",
            decision="approve",
            connection_id="c2",
        )
