"""T6-04 — decide binds to the plan hash and schema fingerprint.

Expiry follows the approval flow: 24 hours on production for R2 and above,
and 7 days on staging. Apply rechecks that instant. No live LLM and no Odoo.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.changeset.store import (  # noqa: E402
    ApprovalExpired,
    FreezeWindow,
    PlanStale,
    apply_approved_plan,
    clear_freeze_window,
    decide_plan,
    set_freeze_window,
    submit_plan,
)
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402

_STAGING_EXPIRY_HOURS = 7 * 24
_PRODUCTION_R2_EXPIRY_HOURS = 24


def _field(name: str) -> list[dict]:
    return [{"type": "field.create", "params": {"model": "x_m", "name": name}}]


def _hours_until(expires_at: str, now: datetime) -> float:
    return (datetime.fromisoformat(expires_at) - now).total_seconds() / 3600


@pytest.fixture
def db():
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_mode", "off")
    init_db()
    with TestClient(app) as test_client:
        yield test_client


def _connection() -> str:
    session = SessionLocal()
    try:
        row = OdooConnection(
            name="T6-04",
            url="http://127.0.0.1:8069",
            db_name=f"t604-{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
        )
        session.add(row)
        session.commit()
        return row.id
    finally:
        session.close()


def _submit(client: TestClient, connection_id: str, *, name: str, schema_slice: dict | None = None) -> dict:
    response = client.post(
        "/api/inbox/plans",
        json={
            "connection_id": connection_id,
            "requester_id": "requester",
            "goal": "Add a note",
            "assumptions": ["empty"],
            "environment": "staging",
            "known_models": ["x_m"],
            "changeset": _field(name),
            "schema_slice": schema_slice,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["card"]


def _decide(
    client: TestClient,
    connection_id: str,
    *,
    path_hash: str,
    plan_hash: str,
    schema_fp: str,
    decision: str = "approve",
) -> object:
    return client.post(
        f"/api/inbox/plans/{path_hash}/decide",
        json={
            "connection_id": connection_id,
            "approver_id": "approver",
            "decision": decision,
            "plan_hash": plan_hash,
            "schema_fp": schema_fp,
        },
    )


def test_decide_fingerprint_mismatch_returns_409_plan_stale(client: TestClient) -> None:
    """A decide body whose hash or schema fingerprint differs is 409 plan_stale."""
    connection_id = _connection()
    card = _submit(client, connection_id, name="x_note", schema_slice={"models": ["x_m"], "revision": 1})
    wrong_schema = _decide(
        client,
        connection_id,
        path_hash=card["plan_hash"],
        plan_hash=card["plan_hash"],
        schema_fp="f" * 64,
    )
    assert wrong_schema.status_code == 409
    assert wrong_schema.json()["detail"]["error"] == "plan_stale"

    wrong_hash = _decide(
        client,
        connection_id,
        path_hash=card["plan_hash"],
        plan_hash="a" * 16,
        schema_fp=card["schema_fp"],
    )
    assert wrong_hash.status_code == 409
    assert wrong_hash.json()["detail"]["error"] == "plan_stale"

    listed = client.get("/api/inbox/plans", params={"connection_id": connection_id})
    assert listed.status_code == 200
    assert listed.json()["plans"][0]["status"] == "pending"

    matched = _decide(
        client,
        connection_id,
        path_hash=card["plan_hash"],
        plan_hash=card["plan_hash"],
        schema_fp=card["schema_fp"],
    )
    assert matched.status_code == 200, matched.text
    assert matched.json()["card"]["status"] == "approved"


def test_rt17_replay_on_modified_plan_is_refused(client: TestClient, db) -> None:
    """An approval for one fingerprint is refused on a modified plan."""
    connection_id = _connection()
    original = _submit(
        client, connection_id, name="x_original", schema_slice={"models": ["x_m"], "revision": 1}
    )
    modified = _submit(
        client, connection_id, name="x_modified", schema_slice={"models": ["x_m"], "revision": 2}
    )
    assert original["plan_hash"] != modified["plan_hash"]

    replay = _decide(
        client,
        connection_id,
        path_hash=modified["plan_hash"],
        plan_hash=original["plan_hash"],
        schema_fp=original["schema_fp"],
    )
    assert replay.status_code == 409
    assert replay.json()["detail"]["error"] == "plan_stale"

    approved = _decide(
        client,
        connection_id,
        path_hash=original["plan_hash"],
        plan_hash=original["plan_hash"],
        schema_fp=original["schema_fp"],
    )
    assert approved.status_code == 200, approved.text

    drifted = _submit(
        client, connection_id, name="x_original", schema_slice={"models": ["x_m"], "revision": 3}
    )
    assert drifted["plan_hash"] == original["plan_hash"]
    assert drifted["schema_fp"] != original["schema_fp"]
    stale_decide = _decide(
        client,
        connection_id,
        path_hash=original["plan_hash"],
        plan_hash=original["plan_hash"],
        schema_fp=original["schema_fp"],
    )
    assert stale_decide.status_code == 409
    assert stale_decide.json()["detail"]["error"] == "plan_stale"

    with pytest.raises(PlanStale):
        apply_approved_plan(
            db,
            original["plan_hash"],
            connection_id=connection_id,
            body_plan_hash=original["plan_hash"],
            schema_fp=original["schema_fp"],
        )


def test_rt19_expired_approval_is_refused_at_apply(db) -> None:
    """Apply refuses an approval at or after expires_at. The window is unchanged."""
    cases = (
        ("staging", "x_stage_note", _STAGING_EXPIRY_HOURS),
        ("production", "x_prod_note", _PRODUCTION_R2_EXPIRY_HOURS),
    )
    for environment, field_name, expected_hours in cases:
        now = datetime.now(timezone.utc)
        connection_id = str(uuid.uuid4())
        result = submit_plan(
            db,
            changeset=_field(field_name),
            goal="Add a note",
            assumptions=["empty"],
            environment=environment,
            requester_id="requester",
            known_models={"x_m"},
            connection_id=connection_id,
        )
        assert result["ok"] is True
        card = result["card"]
        assert card["risk"]["max"] == "R2"
        assert card["risk"]["policy"]["expiry_hours"] == expected_hours
        assert _hours_until(card["expires_at"], now) == pytest.approx(expected_hours, abs=0.05)
        expires = datetime.fromisoformat(card["expires_at"])
        approved = decide_plan(
            db,
            card["plan_hash"],
            approver_id="approver",
            decision="approve",
            connection_id=connection_id,
            body_plan_hash=card["plan_hash"],
            schema_fp=card["schema_fp"],
            now=now,
        )
        assert approved["status"] == "approved"
        with pytest.raises(ApprovalExpired):
            apply_approved_plan(
                db,
                card["plan_hash"],
                connection_id=connection_id,
                body_plan_hash=card["plan_hash"],
                schema_fp=card["schema_fp"],
                now=expires + timedelta(seconds=1),
            )
        still_valid = apply_approved_plan(
            db,
            card["plan_hash"],
            connection_id=connection_id,
            body_plan_hash=card["plan_hash"],
            schema_fp=card["schema_fp"],
            now=expires - timedelta(seconds=1),
        )
        assert still_valid["ok"] is True
        assert still_valid["status"] == "approval_valid"


def test_rt20_freeze_window_blocks_approve(client: TestClient, db) -> None:
    """A freeze window blocks approve and a later apply. Deny still records."""
    connection_id = _connection()
    card = _submit(client, connection_id, name="x_frozen")
    start = datetime.now(timezone.utc) - timedelta(minutes=1)
    end = datetime.now(timezone.utc) + timedelta(hours=1)
    set_freeze_window(connection_id, start=start, end=end)
    try:
        blocked = _decide(
            client,
            connection_id,
            path_hash=card["plan_hash"],
            plan_hash=card["plan_hash"],
            schema_fp=card["schema_fp"],
            decision="approve",
        )
        assert blocked.status_code == 409
        assert blocked.json()["detail"]["error"] == "frozen"
        listed = client.get("/api/inbox/plans", params={"connection_id": connection_id})
        assert listed.json()["plans"][0]["status"] == "pending"

        denied = _decide(
            client,
            connection_id,
            path_hash=card["plan_hash"],
            plan_hash=card["plan_hash"],
            schema_fp=card["schema_fp"],
            decision="deny",
        )
        assert denied.status_code == 200, denied.text
        assert denied.json()["card"]["status"] == "denied"
    finally:
        clear_freeze_window(connection_id)

    fresh_id = _connection()
    fresh = _submit(client, fresh_id, name="x_later_freeze")
    approved = _decide(
        client,
        fresh_id,
        path_hash=fresh["plan_hash"],
        plan_hash=fresh["plan_hash"],
        schema_fp=fresh["schema_fp"],
    )
    assert approved.status_code == 200, approved.text
    set_freeze_window(fresh_id, start=start, end=end)
    try:
        with pytest.raises(FreezeWindow):
            apply_approved_plan(
                db,
                fresh["plan_hash"],
                connection_id=fresh_id,
                body_plan_hash=fresh["plan_hash"],
                schema_fp=fresh["schema_fp"],
            )
    finally:
        clear_freeze_window(fresh_id)


def test_deny_and_stop_is_a_decide_choice(client: TestClient) -> None:
    """The third choice is deny-and-stop, and it stops the card."""
    connection_id = _connection()
    card = _submit(client, connection_id, name="x_stop")
    stopped = _decide(
        client,
        connection_id,
        path_hash=card["plan_hash"],
        plan_hash=card["plan_hash"],
        schema_fp=card["schema_fp"],
        decision="deny-and-stop",
    )
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["card"]["status"] == "stopped"
    assert stopped.json()["card"]["approvals"][0]["decision"] == "deny_and_stop"

    other = _submit(client, connection_id, name="x_stop_code")
    coded = _decide(
        client,
        connection_id,
        path_hash=other["plan_hash"],
        plan_hash=other["plan_hash"],
        schema_fp=other["schema_fp"],
        decision="deny_and_stop",
    )
    assert coded.status_code == 200, coded.text
    assert coded.json()["card"]["status"] == "stopped"
