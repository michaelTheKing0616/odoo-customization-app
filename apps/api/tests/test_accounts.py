"""MON-1 account, session, workspace isolation tests."""

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
from app.account_service import SESSION_COOKIE, hash_password, signup_user, verify_email  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _email(local: str) -> str:
    return f"{local}-{uuid.uuid4().hex[:8]}@example.com"


def test_signup_verify_login_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    email = _email("mon1-user")
    with TestClient(app) as client:
        signup = client.post(
            "/api/accounts/signup",
            json={
                "email": email,
                "password": "secure-pass-99",
                "workspace_name": "Team Alpha",
            },
        )
        assert signup.status_code == 201, signup.text

        login_before = client.post(
            "/api/accounts/login",
            json={"email": email, "password": "secure-pass-99"},
        )
        assert login_before.status_code == 403

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            user.email_verified = True
            db.add(user)
            db.commit()
        finally:
            db.close()

        login = client.post(
            "/api/accounts/login",
            json={"email": email, "password": "secure-pass-99"},
        )
        assert login.status_code == 200, login.text
        assert SESSION_COOKIE in login.cookies

        me = client.get("/api/accounts/me")
        assert me.status_code == 200
        body = me.json()
        assert body["user"]["email"] == email
        assert body["workspace"]["name"] == "Team Alpha"

        logout = client.post("/api/accounts/logout")
        assert logout.status_code == 204
        me_after = client.get("/api/accounts/me")
        assert me_after.status_code == 401


def test_verify_email_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        user, _ws, raw = signup_user(db, email=_email("verify-me"), password="verify-pass-99")
        assert user.email_verified is False
        verify_email(db, raw)
        db.refresh(user)
        assert user.email_verified is True
    finally:
        db.close()


def test_workspace_isolation_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()

    db = SessionLocal()
    try:
        email_a = _email("alice")
        email_b = _email("bob")
        _user_a, ws_a, _ = signup_user(db, email=email_a, password="alice-pass-99")
        _user_b, ws_b, _ = signup_user(db, email=email_b, password="bob-pass-99")
        for u in db.query(User).filter(User.email.in_([email_a, email_b])).all():
            u.email_verified = True
            db.add(u)
        db.commit()

        conn_a = OdooConnection(
            name="Alice conn",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=ws_a.id,
        )
        conn_b = OdooConnection(
            name="Bob conn",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=ws_b.id,
        )
        db.add(conn_a)
        db.add(conn_b)
        db.commit()
        conn_b_id = conn_b.id
    finally:
        db.close()

    with TestClient(app) as client:
        login_a = client.post(
            "/api/accounts/login",
            json={"email": email_a, "password": "alice-pass-99"},
        )
        assert login_a.status_code == 200

        listed = client.get("/api/connections")
        assert listed.status_code == 200
        names = {c["name"] for c in listed.json()}
        assert "Alice conn" in names
        assert "Bob conn" not in names

        denied = client.get(f"/api/connections/{conn_b_id}")
        assert denied.status_code == 404


def test_viewer_cannot_create_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()

    db = SessionLocal()
    try:
        owner, ws, _ = signup_user(db, email=_email("owner"), password="owner-pass-99")
        owner.email_verified = True
        viewer_email = _email("viewer")
        viewer = User(email=viewer_email, password_hash=hash_password("viewer-pass-99"), email_verified=True)
        db.add(viewer)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=viewer.id, role="viewer"))
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        login = client.post(
            "/api/accounts/login",
            json={"email": viewer_email, "password": "viewer-pass-99"},
        )
        assert login.status_code == 200

        denied = client.post(
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
        assert denied.status_code == 403


def test_auth_mode_off_unchanged(client: TestClient) -> None:
    res = client.get("/api/connections")
    assert res.status_code == 200


def test_api_key_mode_unchanged(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "api_key")
    monkeypatch.setattr(settings, "app_api_key", "oc_test_mon1_key")

    denied = client.get("/api/connections")
    assert denied.status_code == 401

    ok = client.get(
        "/api/connections",
        headers={"Authorization": "Bearer oc_test_mon1_key"},
    )
    assert ok.status_code == 200


def test_weak_password_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    with TestClient(app) as client:
        res = client.post(
            "/api/accounts/signup",
            json={"email": _email("weak"), "password": "password123"},
        )
        assert res.status_code == 400


def test_accounts_mode_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    with TestClient(app) as client:
        denied = client.get("/api/connections")
        assert denied.status_code == 401
