"""GET /api/accounts/connection-grants — admin-only list scoped to one connection."""

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

from app.account_models import User, WorkspaceMembership  # noqa: E402
from app.account_service import (  # noqa: E402
    grant_connection_access,
    hash_password,
    signup_user,
)
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


def _email(local: str) -> str:
    return f"{local}-{uuid.uuid4().hex[:8]}@example.com"


def _signup_verified(email: str, password: str, workspace_name: str) -> tuple[str, str]:
    db = SessionLocal()
    try:
        user, workspace, _ = signup_user(
            db, email=email, password=password, workspace_name=workspace_name
        )
        user.email_verified = True
        db.add(user)
        db.commit()
        return user.id, workspace.id
    finally:
        db.close()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    with TestClient(app) as c:
        yield c


def test_list_connection_grants_refuses_non_admin(client: TestClient) -> None:
    owner_email = _email("list-owner")
    owner_password = "owner-pass-99"
    viewer_email = _email("list-viewer")
    viewer_password = "viewer-pass-99"
    _owner_id, workspace_id = _signup_verified(owner_email, owner_password, "List grants WS")
    db = SessionLocal()
    try:
        viewer = User(
            email=viewer_email,
            password_hash=hash_password(viewer_password),
            email_verified=True,
        )
        db.add(viewer)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=workspace_id, user_id=viewer.id, role="viewer"))
        conn = OdooConnection(
            name="List conn",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace_id,
        )
        db.add(conn)
        db.commit()
        connection_id = conn.id
    finally:
        db.close()

    login = client.post(
        "/api/accounts/login",
        json={"email": viewer_email, "password": viewer_password},
    )
    assert login.status_code == 200, login.text

    res = client.get("/api/accounts/connection-grants", params={"connection_id": connection_id})
    assert res.status_code == 403, res.text


def test_list_connection_grants_other_workspace_connection_not_found(client: TestClient) -> None:
    owner_a_email = _email("ws-a-owner")
    owner_a_password = "owner-a-pass-99"
    owner_b_email = _email("ws-b-owner")
    owner_b_password = "owner-b-pass-99"
    _signup_verified(owner_a_email, owner_a_password, "Workspace A")
    _owner_b_id, workspace_b_id = _signup_verified(owner_b_email, owner_b_password, "Workspace B")
    db = SessionLocal()
    try:
        foreign = OdooConnection(
            name="Foreign conn",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace_b_id,
        )
        db.add(foreign)
        db.commit()
        foreign_connection_id = foreign.id
    finally:
        db.close()

    login = client.post(
        "/api/accounts/login",
        json={"email": owner_a_email, "password": owner_a_password},
    )
    assert login.status_code == 200, login.text

    res = client.get(
        "/api/accounts/connection-grants",
        params={"connection_id": foreign_connection_id},
    )
    assert res.status_code == 404, res.text
    assert res.json()["detail"] == "Connection not found"


def test_list_connection_grants_only_includes_requested_connection(client: TestClient) -> None:
    owner_email = _email("iso-owner")
    owner_password = "owner-pass-99"
    grantee_email = _email("iso-grantee")
    owner_id, workspace_id = _signup_verified(owner_email, owner_password, "Isolation WS")
    db = SessionLocal()
    try:
        grantee = User(
            email=grantee_email,
            password_hash=hash_password("grantee-pass-99"),
            email_verified=True,
        )
        db.add(grantee)
        conn_a = OdooConnection(
            name="Conn A",
            url="http://127.0.0.1:8069",
            db_name="odoo_a",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace_id,
        )
        conn_b = OdooConnection(
            name="Conn B",
            url="http://127.0.0.1:8069",
            db_name="odoo_b",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace_id,
        )
        db.add(conn_a)
        db.add(conn_b)
        db.flush()
        grant_a = grant_connection_access(
            db,
            workspace_id=workspace_id,
            connection_id=conn_a.id,
            user_id=grantee.id,
            role="client_approver",
            actor_user_id=owner_id,
        )
        grant_b = grant_connection_access(
            db,
            workspace_id=workspace_id,
            connection_id=conn_b.id,
            user_id=grantee.id,
            role="client_viewer",
            actor_user_id=owner_id,
        )
        db.commit()
        connection_a_id = conn_a.id
        grant_a_id = grant_a.id
        grant_b_id = grant_b.id
    finally:
        db.close()

    login = client.post(
        "/api/accounts/login",
        json={"email": owner_email, "password": owner_password},
    )
    assert login.status_code == 200, login.text

    res = client.get(
        "/api/accounts/connection-grants",
        params={"connection_id": connection_a_id},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    ids = {row["id"] for row in body}
    assert grant_a_id in ids
    assert grant_b_id not in ids
    assert all(row["connection_id"] == connection_a_id for row in body)
