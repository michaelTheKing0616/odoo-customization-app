"""Client Approver sees one client's approvals and cannot reach another client."""

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

from app.account_service import grant_connection_access, hash_password, signup_user  # noqa: E402
from app.client_access import client_request_decision  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.account_models import User  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


def _email(local: str) -> str:
    return f"{local}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.no_app_db
def test_client_path_policy_hides_other_connections() -> None:
    scope = frozenset({"conn-a"})
    assert client_request_decision("GET", "/api/connections", "client_approver", scope) == "allow"
    assert (
        client_request_decision("GET", "/api/connections/conn-b", "client_approver", scope) == "hide"
    )
    assert (
        client_request_decision("GET", "/api/connections/conn-b/studio", "client_approver", scope)
        == "hide"
    )
    assert (
        client_request_decision("GET", "/api/connections/conn-a", "client_approver", scope) == "deny"
    )
    assert (
        client_request_decision("POST", "/api/connections", "client_approver", scope) == "deny"
    )
    assert (
        client_request_decision(
            "POST",
            "/api/connections/conn-a/approvals/entries/e1/approve",
            "client_approver",
            scope,
        )
        == "allow"
    )
    assert (
        client_request_decision(
            "POST",
            "/api/connections/conn-a/approvals/entries/e1/approve",
            "client_viewer",
            scope,
        )
        == "deny"
    )
    assert (
        client_request_decision(
            "POST",
            "/api/connections/conn-a/approvals/rules",
            "client_approver",
            scope,
        )
        == "deny"
    )
    assert client_request_decision("GET", "/api/inbox/plans", "client_approver", scope) == "allow"
    assert client_request_decision("GET", "/api/inbox/plans", "client_viewer", scope) == "allow"
    assert client_request_decision("POST", "/api/inbox/plans", "client_approver", scope) == "deny"
    assert client_request_decision("POST", "/api/inbox/plans", "client_viewer", scope) == "deny"
    assert (
        client_request_decision(
            "POST",
            "/api/inbox/plans/plan-hash-abc/decide",
            "client_approver",
            scope,
        )
        == "allow"
    )
    assert (
        client_request_decision(
            "POST",
            "/api/inbox/plans/plan-hash-abc/decide",
            "client_viewer",
            scope,
        )
        == "deny"
    )


def test_client_approver_cannot_reach_a_second_client(monkeypatch: pytest.MonkeyPatch) -> None:
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
        db.add(approver)
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
        approver_email = approver.email
        granted_id = granted.id
        other_id = other.id
    finally:
        db.close()

    with TestClient(app) as client:
        login = client.post(
            "/api/accounts/login",
            json={"email": approver_email, "password": "approver-pass-99"},
        )
        assert login.status_code == 200, login.text
        assert login.json()["workspace"]["role"] == "client_approver"

        listed = client.get("/api/connections")
        assert listed.status_code == 200, listed.text
        ids = {row["id"] for row in listed.json()}
        assert ids == {granted_id}

        hidden = client.get(f"/api/connections/{other_id}")
        assert hidden.status_code == 404

        own_detail = client.get(f"/api/connections/{granted_id}")
        assert own_detail.status_code == 403

        studio = client.post("/api/ai/sessions", json={"connection_id": other_id, "brief": "x"})
        assert studio.status_code == 403

        create = client.post(
            "/api/connections",
            json={
                "name": "Nope",
                "url": "http://127.0.0.1:8069",
                "db_name": "odoo_dev",
                "username": "admin",
                "password": "admin",
                "verify": False,
            },
        )
        assert create.status_code == 403


def test_signup_user_with_a_grant_logs_into_the_client_not_the_empty_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        owner, agency, _ = signup_user(
            db, email=_email("agency"), password="agency-pass-99", workspace_name="Agency"
        )
        owner.email_verified = True
        db.add(owner)
        approver, _personal, _ = signup_user(
            db, email=_email("finance"), password="finance-pass-99", workspace_name="Finance"
        )
        approver.email_verified = True
        db.add(approver)
        granted = OdooConnection(
            name="Client books",
            url="http://127.0.0.1:8069",
            db_name="books",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=agency.id,
        )
        db.add(granted)
        db.flush()
        grant_connection_access(
            db,
            workspace_id=agency.id,
            connection_id=granted.id,
            user_id=approver.id,
            role="client_approver",
        )
        email = approver.email
        granted_id = granted.id
    finally:
        db.close()

    with TestClient(app) as client:
        login = client.post(
            "/api/accounts/login",
            json={"email": email, "password": "finance-pass-99"},
        )
        assert login.status_code == 200, login.text
        assert login.json()["workspace"]["role"] == "client_approver"
        listed = client.get("/api/connections")
        assert {row["id"] for row in listed.json()} == {granted_id}
