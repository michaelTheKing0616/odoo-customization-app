"""T6-07 — Client Approver inbox scope over HTTP (gate 6-2 on inbox)."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.account_models import User  # noqa: E402
from app.account_service import grant_connection_access, hash_password, signup_user  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402

def _field_op(field_name: str) -> list[dict]:
    return [{"type": "field.create", "params": {"model": "x_m", "name": field_name}}]


def _email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:8]}@example.com"


def _submit_plan(client: TestClient, connection_id: str, *, field_name: str) -> dict:
    res = client.post(
        "/api/inbox/plans",
        json={
            "connection_id": connection_id,
            "requester_id": "owner",
            "goal": "Add a note",
            "assumptions": [],
            "environment": "staging",
            "known_models": ["x_m"],
            "changeset": _field_op(field_name),
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["card"]


def test_client_approver_inbox_lists_only_granted_connection_and_hides_other_plans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Client Approver HTTP inbox: scoped list, 404 on other client, viewer cannot decide."""
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        owner, workspace, _ = signup_user(
            db, email=_email("owner"), password="owner-pass-99", workspace_name="Agency"
        )
        owner.email_verified = True
        db.add(owner)

        approver = User(
            email=_email("approver"),
            password_hash=hash_password("approver-pass-99"),
            email_verified=True,
        )
        viewer = User(
            email=_email("viewer"),
            password_hash=hash_password("viewer-pass-99"),
            email_verified=True,
        )
        db.add(approver)
        db.add(viewer)
        db.flush()

        granted = OdooConnection(
            name="Granted client",
            url="http://127.0.0.1:8069",
            db_name="granted",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        other = OdooConnection(
            name="Other client",
            url="http://127.0.0.1:8070",
            db_name="other",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        db.add(granted)
        db.add(other)
        db.flush()

        grant_connection_access(
            db,
            workspace_id=workspace.id,
            connection_id=granted.id,
            user_id=approver.id,
            role="client_approver",
        )
        grant_connection_access(
            db,
            workspace_id=workspace.id,
            connection_id=granted.id,
            user_id=viewer.id,
            role="client_viewer",
        )

        owner_email = owner.email
        approver_email = approver.email
        viewer_email = viewer.email
        granted_id = granted.id
        other_id = other.id
    finally:
        db.close()

    with TestClient(app) as client:
        login_owner = client.post(
            "/api/accounts/login",
            json={"email": owner_email, "password": "owner-pass-99"},
        )
        assert login_owner.status_code == 200, login_owner.text
        granted_card = _submit_plan(client, granted_id, field_name="x_note_granted")
        other_card = _submit_plan(client, other_id, field_name="x_note_other")
        assert granted_card["plan_hash"] != other_card["plan_hash"]
        client.post("/api/accounts/logout")

        login_approver = client.post(
            "/api/accounts/login",
            json={"email": approver_email, "password": "approver-pass-99"},
        )
        assert login_approver.status_code == 200, login_approver.text
        assert login_approver.json()["workspace"]["role"] == "client_approver"

        listed = client.get("/api/inbox/plans", params={"connection_id": granted_id})
        assert listed.status_code == 200, listed.text
        plans = listed.json()["plans"]
        assert len(plans) == 1
        assert plans[0]["plan_hash"] == granted_card["plan_hash"]
        assert plans[0]["connection_id"] == granted_id
        assert other_card["plan_hash"] not in {row["plan_hash"] for row in plans}

        hidden_list = client.get("/api/inbox/plans", params={"connection_id": other_id})
        assert hidden_list.status_code == 404
        assert "not found" in hidden_list.text.lower()

        cross_body = {
            "connection_id": granted_id,
            "approver_id": "approver",
            "decision": "approve",
            "plan_hash": other_card["plan_hash"],
            "schema_fp": other_card["schema_fp"],
        }
        cross_decide = client.post(
            f"/api/inbox/plans/{other_card['plan_hash']}/decide",
            json=cross_body,
        )
        assert cross_decide.status_code == 404
        assert cross_decide.status_code != 403
        assert "not found" in cross_decide.text.lower()

        wrong_conn_body = {
            **cross_body,
            "connection_id": other_id,
            "plan_hash": other_card["plan_hash"],
            "schema_fp": other_card["schema_fp"],
        }
        wrong_conn = client.post(
            f"/api/inbox/plans/{other_card['plan_hash']}/decide",
            json=wrong_conn_body,
        )
        assert wrong_conn.status_code == 404
        assert wrong_conn.status_code != 403

        approve = client.post(
            f"/api/inbox/plans/{granted_card['plan_hash']}/decide",
            json={
                "connection_id": granted_id,
                "approver_id": "approver",
                "decision": "approve",
                "plan_hash": granted_card["plan_hash"],
                "schema_fp": granted_card["schema_fp"],
                "user_id": "approver-user",
            },
        )
        assert approve.status_code == 200, approve.text
        assert approve.json()["card"]["status"] == "approved"

        submit_denied = client.post(
            "/api/inbox/plans",
            json={
                "connection_id": granted_id,
                "requester_id": "approver",
                "goal": "Nope",
                "assumptions": [],
                "environment": "staging",
                "known_models": ["x_m"],
                "changeset": _field_op("x_note_denied"),
            },
        )
        assert submit_denied.status_code == 403

        client.post("/api/accounts/logout")

        login_viewer = client.post(
            "/api/accounts/login",
            json={"email": viewer_email, "password": "viewer-pass-99"},
        )
        assert login_viewer.status_code == 200, login_viewer.text

        viewer_decide = client.post(
            f"/api/inbox/plans/{granted_card['plan_hash']}/decide",
            json={
                "connection_id": granted_id,
                "approver_id": "viewer",
                "decision": "approve",
                "plan_hash": granted_card["plan_hash"],
                "schema_fp": granted_card["schema_fp"],
            },
        )
        assert viewer_decide.status_code == 403
