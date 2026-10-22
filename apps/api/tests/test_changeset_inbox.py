"""Inbox rules: hash binding, self-approval, and connection scope."""

from __future__ import annotations

from datetime import datetime, timezone

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


def test_hard_stop_r4_is_not_queued() -> None:
    inbox = Inbox()
    result = inbox.submit(
        [{"type": "access.create", "params": {"model": "res.partner", "name": "x_acl"}}],
        goal="open access",
        assumptions=[],
        environment="production",
        requester_id="u1",
        known_models={"res.partner"},
        connection_id="c1",
    )
    assert result["ok"] is False


def test_requester_can_approve_production_r3() -> None:
    inbox = Inbox()
    result = inbox.submit(
        [{"type": "access.create", "params": {"model": "res.partner", "name": "x_acl", "group": "sales.group_sale_user"}}],
        goal="grant",
        assumptions=[],
        environment="production",
        requester_id="u1",
        known_models={"res.partner"},
        connection_id="c1",
    )
    assert result["ok"] is True
    card = inbox.decide(
        result["card"]["plan_hash"],
        approver_id="u1",
        decision="approve",
        connection_id="c1",
        user_id="u1",
    )
    assert card["status"] == "approved"


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


_R3_NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
_R3_WINDOW = {
    "start": "2026-10-04T14:00:00+00:00",
    "end": "2026-10-04T16:00:00+00:00",
}
_ACCESS = {
    "type": "access.create",
    "params": {"model": "res.partner", "name": "x_acl", "group": "sales.group_sale_user"},
}
_HEAVY = {"type": "module.uninstall", "params": {"module": "sale"}}
_PROTECTED = {"type": "data.delete", "params": {"model": "product.category"}}


def _submit_production(op: dict, models: set[str], requester_id: str = "u1") -> tuple[Inbox, dict]:
    inbox = Inbox()
    result = inbox.submit(
        [op],
        goal="change",
        assumptions=[],
        environment="production",
        requester_id=requester_id,
        known_models=models,
        connection_id="c1",
    )
    assert result["ok"] is True
    card = result["card"]
    assert card["max_risk"] == "R4"
    assert card["risk"]["policy"]["approvers"] == 2
    assert card["risk"]["policy"]["needs_simulation"] is True
    assert card["risk"]["policy"]["needs_backup"] is True
    assert card["risk"]["policy"]["needs_window"] is True
    return inbox, card


def _approve(inbox: Inbox, plan_hash: str, approver_id: str, **extra: object) -> dict:
    payload: dict = {
        "approver_id": approver_id,
        "decision": "approve",
        "connection_id": "c1",
        "simulation_passed": True,
        "backup_id": "backup-1",
        "allowed_window": _R3_WINDOW,
        "now": _R3_NOW,
    }
    payload.update(extra)
    return inbox.decide(plan_hash, **payload)


def test_production_r3_approves_with_one_call_from_the_requester() -> None:
    inbox = Inbox()
    result = inbox.submit(
        [_ACCESS],
        goal="grant",
        assumptions=[],
        environment="production",
        requester_id="u1",
        known_models={"res.partner"},
        connection_id="c1",
    )
    assert result["ok"] is True
    card = result["card"]
    assert card["max_risk"] == "R3"
    assert card["risk"]["policy"]["approvers"] == 1
    assert card["risk"]["policy"]["needs_simulation"] is False
    approved = inbox.decide(
        card["plan_hash"],
        approver_id="u1",
        decision="approve",
        connection_id="c1",
        user_id="u1",
    )
    assert approved["status"] == "approved"


def test_rt18_requester_second_identity_is_refused() -> None:
    """The requester's two identities cannot be both heavy-R4 approvers."""
    inbox, card = _submit_production(_HEAVY, {"sale"})
    first = _approve(
        inbox,
        card["plan_hash"],
        "google-subject",
        user_id="u1",
        provider="google",
        session_id="sess-google",
    )
    second = _approve(
        inbox,
        card["plan_hash"],
        "microsoft-subject",
        user_id="u1",
        provider="microsoft",
        session_id="sess-microsoft",
    )
    assert first["status"] == "pending"
    assert second["status"] == "pending"
    assert "distinct_approvers" in second["r3_blockers"]


def test_google_and_microsoft_identities_count_as_one_approver() -> None:
    inbox, card = _submit_production(_HEAVY, {"sale"})
    plan_hash = card["plan_hash"]
    first = _approve(
        inbox,
        plan_hash,
        "google-ada",
        user_id="ada",
        provider="google",
        session_id="sess-google",
    )
    second = _approve(
        inbox,
        plan_hash,
        "microsoft-ada",
        user_id="ada",
        provider="microsoft",
        session_id="sess-microsoft",
    )
    assert first["status"] == "pending"
    assert second["status"] == "pending"
    assert len(second["approvals"]) == 2
    assert "distinct_approvers" in second["r3_blockers"]
    done = _approve(inbox, plan_hash, "microsoft-mina", user_id="mina", provider="microsoft")
    assert done["status"] == "approved"
    assert done["r3_blockers"] == []


def test_two_sessions_of_one_user_count_as_one_approver() -> None:
    inbox, card = _submit_production(_HEAVY, {"sale"})
    plan_hash = card["plan_hash"]
    _approve(inbox, plan_hash, "session-1", user_id="ada", session_id="session-1")
    second = _approve(inbox, plan_hash, "session-2", user_id="ada", session_id="session-2")
    assert second["status"] == "pending"
    assert "distinct_approvers" in second["r3_blockers"]
    done = _approve(inbox, plan_hash, "session-3", user_id="mina", session_id="session-3")
    assert done["status"] == "approved"


def test_heavy_r4_stays_pending_without_simulation_backup_or_window() -> None:
    inbox, card = _submit_production(_HEAVY, {"sale"})
    plan_hash = card["plan_hash"]
    no_simulation = _approve(inbox, plan_hash, "ada", user_id="ada", simulation_passed=False)
    assert no_simulation["status"] == "pending"
    assert "simulation" in no_simulation["r3_blockers"]

    inbox, card = _submit_production(_HEAVY, {"sale"})
    plan_hash = card["plan_hash"]
    _approve(inbox, plan_hash, "ada", user_id="ada", backup_id="")
    missing_backup = _approve(inbox, plan_hash, "mina", user_id="mina", backup_id="")
    assert missing_backup["status"] == "pending"
    assert "backup" in missing_backup["r3_blockers"]

    inbox, card = _submit_production(_HEAVY, {"sale"})
    plan_hash = card["plan_hash"]
    closed = {
        "start": "2026-10-04T10:00:00+00:00",
        "end": "2026-10-04T11:00:00+00:00",
    }
    _approve(inbox, plan_hash, "ada", user_id="ada", allowed_window=closed)
    outside = _approve(inbox, plan_hash, "mina", user_id="mina", allowed_window=closed)
    assert outside["status"] == "pending"
    assert "window" in outside["r3_blockers"]


def test_protected_heavy_r4_needs_a_domain_owner() -> None:
    inbox, card = _submit_production(_PROTECTED, {"product.category"})
    plan_hash = card["plan_hash"]
    _approve(inbox, plan_hash, "ada", user_id="ada")
    waiting = _approve(inbox, plan_hash, "mina", user_id="mina")
    assert waiting["status"] == "pending"
    assert waiting["r3_blockers"] == ["domain_owner"]
    owned = _approve(inbox, plan_hash, "mina", user_id="mina", domain_owner=True)
    assert owned["status"] == "approved"
    assert owned["r3_blockers"] == []


def test_two_approver_ids_without_user_id_leave_heavy_r4_pending() -> None:
    """Two decide calls with different approver ids and no user id stay pending."""
    inbox, card = _submit_production(_HEAVY, {"sale"})
    plan_hash = card["plan_hash"]
    first = _approve(inbox, plan_hash, "approver-a")
    second = _approve(inbox, plan_hash, "approver-b")
    assert first["status"] == "pending"
    assert second["status"] == "pending"
    assert "distinct_approvers" in second["r3_blockers"]


def test_heavy_r4_approves_with_two_distinct_people_and_gates() -> None:
    inbox, card = _submit_production(_HEAVY, {"sale"})
    plan_hash = card["plan_hash"]
    _approve(inbox, plan_hash, "ada", user_id="ada")
    done = _approve(inbox, plan_hash, "mina", user_id="mina")
    assert done["status"] == "approved"
    assert done["r3_blockers"] == []


def test_http_decide_approves_production_r3_and_carries_heavy_r4(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/inbox/plans/{hash}/decide approves production R3 in one call.

    The same route carries a heavy-R4 approval. Two identities of one person
    count once. A missing simulation, backup, or window leaves the card pending.
    """
    import os
    import uuid
    from datetime import datetime, timedelta, timezone

    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
    )
    os.environ.setdefault("FERNET_KEY", "dev-only-test")
    os.environ.setdefault("AUTH_MODE", "off")
    os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

    from fastapi.testclient import TestClient

    from app.crypto import encrypt_secret
    from app.db import SessionLocal, init_db
    from app.db_models import OdooConnection
    from app.main import app
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", "off")
    init_db()
    session = SessionLocal()
    try:
        row = OdooConnection(
            name="R3-HTTP",
            url="http://127.0.0.1:8069",
            db_name=f"r3http-{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
        )
        session.add(row)
        session.commit()
        connection_id = row.id
    finally:
        session.close()

    now = datetime.now(timezone.utc)
    window = {
        "start": (now - timedelta(hours=1)).isoformat(),
        "end": (now + timedelta(hours=1)).isoformat(),
    }

    def submit(changeset: list[dict], models: list[str]) -> dict:
        response = client.post(
            "/api/inbox/plans",
            json={
                "connection_id": connection_id,
                "requester_id": "u1",
                "goal": "Change",
                "assumptions": ["empty"],
                "environment": "production",
                "known_models": models,
                "changeset": changeset,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()["card"]

    def decide(card: dict, approver_id: str, **extra: object) -> object:
        body = {
            "connection_id": connection_id,
            "approver_id": approver_id,
            "decision": "approve",
            "plan_hash": card["plan_hash"],
            "schema_fp": card["schema_fp"],
        }
        body.update(extra)
        return client.post(f"/api/inbox/plans/{card['plan_hash']}/decide", json=body)

    with TestClient(app) as client:
        r3 = submit([_ACCESS], ["res.partner"])
        assert r3["max_risk"] == "R3"
        approved = decide(r3, "u1", user_id="u1")
        assert approved.status_code == 200, approved.text
        assert approved.json()["card"]["status"] == "approved"

        facts = {
            "simulation_passed": True,
            "backup_id": "backup-1",
            "allowed_window": window,
        }
        heavy = submit([_HEAVY], ["sale"])
        assert heavy["max_risk"] == "R4"
        same = decide(heavy, "google-ada", user_id="ada", **facts)
        assert same.status_code == 200, same.text
        again = decide(heavy, "microsoft-ada", user_id="ada", **facts)
        assert again.status_code == 200, again.text
        assert again.json()["card"]["status"] == "pending"
        assert "distinct_approvers" in again.json()["card"]["r3_blockers"]
        done = decide(heavy, "mina", user_id="mina", **facts)
        assert done.status_code == 200, done.text
        assert done.json()["card"]["status"] == "approved"

        no_sim = {"simulation_passed": False, "backup_id": "backup-1", "allowed_window": window}
        missing_simulation = submit([_HEAVY], ["sale"])
        decide(missing_simulation, "ada", user_id="ada", **no_sim)
        waiting_sim = decide(missing_simulation, "mina", user_id="mina", **no_sim)
        assert waiting_sim.json()["card"]["status"] == "pending"
        assert "simulation" in waiting_sim.json()["card"]["r3_blockers"]

        no_backup = {"simulation_passed": True, "backup_id": "", "allowed_window": window}
        missing_backup = submit([_HEAVY], ["sale"])
        decide(missing_backup, "ada", user_id="ada", **no_backup)
        waiting_backup = decide(missing_backup, "mina", user_id="mina", **no_backup)
        assert waiting_backup.json()["card"]["status"] == "pending"
        assert "backup" in waiting_backup.json()["card"]["r3_blockers"]

        no_window = {"simulation_passed": True, "backup_id": "backup-1"}
        missing_window = submit([_HEAVY], ["sale"])
        decide(missing_window, "ada", user_id="ada", **no_window)
        waiting_window = decide(missing_window, "mina", user_id="mina", **no_window)
        assert waiting_window.json()["card"]["status"] == "pending"
        assert "window" in waiting_window.json()["card"]["r3_blockers"]

        protected = submit([_PROTECTED], ["product.category"])
        decide(protected, "ada", user_id="ada", **facts)
        waiting_owner = decide(protected, "mina", user_id="mina", **facts)
        assert waiting_owner.json()["card"]["status"] == "pending"
        assert "domain_owner" in waiting_owner.json()["card"]["r3_blockers"]
        owned = decide(protected, "mina", user_id="mina", domain_owner=True, **facts)
        assert owned.status_code == 200, owned.text
        assert owned.json()["card"]["status"] == "approved"
