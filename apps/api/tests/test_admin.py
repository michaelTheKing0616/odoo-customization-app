"""MON-3 admin bootstrap and access tests."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom")
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.account_models import User  # noqa: E402
from app.account_service import hash_password, signup_user  # noqa: E402
from app.admin_bootstrap import bootstrap_superadmin_from_env  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


def test_bootstrap_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "app_admin_email", f"admin-{uuid.uuid4().hex[:6]}@test.local")
    monkeypatch.setattr(settings, "app_admin_password", "bootstrap-test-pass-99")
    init_db()
    db = SessionLocal()
    try:
        for u in db.query(User).filter(User.is_superadmin.is_(True)).all():
            db.delete(u)
        db.commit()
        assert bootstrap_superadmin_from_env(db) is True
        assert bootstrap_superadmin_from_env(db) is False
        assert db.query(User).filter(User.is_superadmin.is_(True)).count() == 1
    finally:
        db.close()


def test_admin_forbidden_for_non_superadmin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    db = SessionLocal()
    try:
        user, _, _ = signup_user(db, email=email, password="user-pass-99")
        user.email_verified = True
        db.add(user)
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        client.post("/api/accounts/login", json={"email": email, "password": "user-pass-99"})
        res = client.get("/api/admin/users")
        assert res.status_code == 403
