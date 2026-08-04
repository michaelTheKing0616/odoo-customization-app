"""DEV-3 — script runner gating and journal tests."""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import patch

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
from app.account_service import hash_password, signup_user  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import AuditLog, OdooConnection  # noqa: E402
from app.entitlements import ensure_workspace_subscription, seed_plan_features  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _conn() -> OdooConnection:
    db = SessionLocal()
    try:
        _user, ws, _ = signup_user(
            db,
            email=f"sr-{uuid.uuid4().hex[:8]}@example.com",
            password="sr-pass-99-long",
        )
        conn = OdooConnection(
            name="script-runner",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
            workspace_id=ws.id,
        )
        db.add(conn)
        sub = ensure_workspace_subscription(db, ws.id)
        sub.plan_id = "internal"
        db.commit()
        db.refresh(conn)
        return conn
    finally:
        db.close()


def test_templates_endpoint(client: TestClient) -> None:
    conn = _conn()
    res = client.get(f"/api/connections/{conn.id}/script-runner/templates")
    assert res.status_code == 200
    assert len(res.json()["templates"]) >= 5


@patch("app.routers.script_runner.run_script_sync")
def test_run_journals_full_script(mock_run, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    conn = _conn()
    from app.db_models import ScriptRun
    from datetime import datetime, timezone

    mock_run.return_value = ScriptRun(
        id="run-1",
        connection_id=conn.id,
        script_content="log('x')",
        script_hash="abc",
        status="succeeded",
        finished_at=datetime.now(timezone.utc),
    )
    before = SessionLocal().query(AuditLog).count()
    res = client.post(
        f"/api/connections/{conn.id}/script-runner/run",
        json={
            "script": "log('x')",
            "async_job": False,
            "confirm_advanced": True,
            "confirm_phrase": "I understand the risks",
        },
    )
    assert res.status_code == 200, res.text
    after = SessionLocal().query(AuditLog).count()
    assert after > before
    row = SessionLocal().query(AuditLog).order_by(AuditLog.created_at.desc()).first()
    detail = json.loads(row.detail_json or "{}")
    assert detail.get("code") == "log('x')"


def test_observer_mode_refuses_script_run(client: TestClient) -> None:
    conn = _conn()
    db = SessionLocal()
    try:
        row = db.get(OdooConnection, conn.id)
        row.write_mode = "observer"
        db.commit()
    finally:
        db.close()
    res = client.post(
        f"/api/connections/{conn.id}/script-runner/run",
        json={
            "script": "log(1)",
            "confirm_advanced": True,
            "confirm_phrase": "I understand the risks",
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "observer_mode"


def test_builder_cannot_run_scripts(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        seed_plan_features(db)
        _owner, ws, _ = signup_user(
            db,
            email=f"o-{uuid.uuid4().hex[:6]}@example.com",
            password="owner-pass-99-long",
        )
        email = f"b-{uuid.uuid4().hex[:6]}@example.com"
        user = User(email=email, password_hash=hash_password("builder-pass-99"), email_verified=True)
        db.add(user)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role="builder"))
        conn = OdooConnection(
            name="sr-role",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
            workspace_id=ws.id,
        )
        db.add(conn)
        sub = ensure_workspace_subscription(db, ws.id)
        sub.plan_id = "internal"
        db.commit()
        conn_id = conn.id
    finally:
        db.close()
    client.post("/api/accounts/login", json={"email": email, "password": "builder-pass-99"})
    res = client.post(
        f"/api/connections/{conn_id}/script-runner/run",
        json={"script": "log(1)"},
    )
    assert res.status_code == 403
