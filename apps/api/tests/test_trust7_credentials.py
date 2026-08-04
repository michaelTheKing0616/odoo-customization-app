"""TRUST-7 — credential handling, session cookies, log/response secret hygiene."""

from __future__ import annotations

import json
import logging
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

from app.account_service import SESSION_COOKIE, signup_user  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import AuditLog, OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import ConnectionOut  # noqa: E402
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:8]}@example.com"


SECRET_FIELD_NAMES = frozenset(
    {
        "password",
        "secret",
        "secret_encrypted",
        "api_key",
        "token",
        "fernet_key",
    }
)


def test_connection_out_schema_never_exposes_secrets() -> None:
    fields = set(ConnectionOut.model_fields.keys())
    leaked = fields & SECRET_FIELD_NAMES
    assert not leaked, f"ConnectionOut must not expose: {leaked}"


def test_connection_api_response_never_echoes_password(client: TestClient) -> None:
    odoo_password = "never-echo-this-password-99"
    res = client.post(
        "/api/connections",
        json={
            "name": "Secret hygiene",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo_dev",
            "username": "admin",
            "password": odoo_password,
            "verify": False,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    dumped = json.dumps(body).lower()
    assert odoo_password not in dumped
    for key in SECRET_FIELD_NAMES:
        assert key not in body


def test_audit_log_does_not_store_request_bodies(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    odoo_password = "audit-body-must-not-appear-88"
    with caplog.at_level(logging.INFO):
        res = client.post(
            "/api/connections",
            json={
                "name": "Audit scrub",
                "url": "http://127.0.0.1:8069",
                "db_name": "odoo_dev",
                "username": "admin",
                "password": odoo_password,
                "verify": False,
            },
        )
    assert res.status_code == 201, res.text

    db = SessionLocal()
    try:
        row = db.query(AuditLog).order_by(AuditLog.created_at.desc()).first()
        assert row is not None
        assert row.path == "/api/connections"
        assert odoo_password not in (row.path or "")
        assert odoo_password not in (row.api_key_prefix or "")
    finally:
        db.close()

    for record in caplog.records:
        msg = record.getMessage()
        assert odoo_password not in msg


def test_session_cookie_flags_on_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "session_cookie_secure", True)
    init_db()
    email = _email("cookie-user")
    password = "cookie-pass-99-long"
    db = SessionLocal()
    try:
        user, _ws, _ = signup_user(db, email=email, password=password)
        user.email_verified = True
        db.add(user)
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        res = client.post("/api/accounts/login", json={"email": email, "password": password})
        assert res.status_code == 200, res.text
        raw = res.headers.get("set-cookie", "")
        assert SESSION_COOKIE in raw.lower()
        assert "httponly" in raw.lower()
        assert "samesite=lax" in raw.lower().replace(" ", "")
        assert "secure" in raw.lower()


def test_stored_connection_secret_is_encrypted_not_plaintext() -> None:
    init_db()
    db = SessionLocal()
    try:
        plain = "stored-plain-must-not-match"
        row = OdooConnection(
            name="crypto-at-rest",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret(plain),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        assert row.secret_encrypted != plain
        assert plain not in row.secret_encrypted
    finally:
        db.close()
