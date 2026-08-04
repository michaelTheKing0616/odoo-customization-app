"""DEV-1 — Code Studio gating, validate, bind, and adversarial role tests."""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import MagicMock, patch

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
from app.code_studio_service import validate_code  # noqa: E402
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


def _conn(*, probe: dict | None = None) -> OdooConnection:
    db = SessionLocal()
    try:
        _user, ws, _ = signup_user(
            db,
            email=f"dev1-{uuid.uuid4().hex[:8]}@example.com",
            password="dev1-pass-99-long",
        )
        conn = OdooConnection(
            name="code-studio",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
            write_mode="standard",
            workspace_id=ws.id,
            code_studio_probe_json=json.dumps(probe) if probe else None,
        )
        db.add(conn)
        sub = ensure_workspace_subscription(db, ws.id)
        sub.plan_id = "internal"
        sub.status = "active"
        db.commit()
        db.refresh(conn)
        return conn
    finally:
        db.close()


def test_validate_code_syntax_and_warnings() -> None:
    ok = validate_code("for rec in records:\n    rec.write({'x': 1})")
    assert ok["ok"] is True
    bad = validate_code("for rec in records\n    pass")
    assert bad["ok"] is False
    warn = validate_code("import os\nfor rec in records:\n    rec.unlink()")
    assert warn["ok"] is True
    codes = {w["code"] for w in warn["warnings"]}
    assert "imports_forbidden" in codes
    assert "unlink_pattern" in codes


@patch("app.routers.code_studio.client_from_connection")
@patch("app.code_studio_gating.client_from_connection")
def test_gate_uses_cached_probe(
    mock_gate_client,
    mock_router_client,
    client: TestClient,
) -> None:
    probe = {"supported": True, "key": "code_server_actions"}
    conn = _conn(probe=probe)
    res = client.get(f"/api/connections/{conn.id}/code-studio/gate")
    assert res.status_code == 200
    body = res.json()
    assert body["probe"]["supported"] is True
    assert body["gating"]["available"] is True
    mock_gate_client.assert_not_called()


@patch("app.code_studio_gating.probe_code_server_actions")
@patch("app.code_studio_gating.client_from_connection")
def test_failed_probe_returns_module_path_options(
    mock_client_from,
    mock_probe,
    client: TestClient,
) -> None:
    conn = _conn()
    mock_client_from.return_value = MagicMock()
    mock_probe.return_value = {
        "supported": False,
        "error": "state missing",
        "key": "code_server_actions",
    }
    res = client.get(f"/api/connections/{conn.id}/code-studio/gate")
    assert res.status_code == 200
    opts = res.json()["gating"]["options"]
    assert any("Option A" in o for o in opts)


@pytest.mark.parametrize(
    "role,expect",
    [
        ("viewer", 403),
        ("builder", 403),
        ("developer", 200),
        ("admin", 200),
    ],
)
def test_validate_requires_developer_role(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    expect: int,
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        seed_plan_features(db)
        _owner, ws, _ = signup_user(
            db,
            email=f"owner-{uuid.uuid4().hex[:6]}@example.com",
            password="owner-pass-99-long",
        )
        email = f"{role}-{uuid.uuid4().hex[:6]}@example.com"
        user = User(email=email, password_hash=hash_password("role-pass-99-long"), email_verified=True)
        db.add(user)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=role))
        conn = OdooConnection(
            name="role-matrix",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=ws.id,
            write_mode="standard",
            code_studio_probe_json=json.dumps({"supported": True}),
        )
        db.add(conn)
        sub = ensure_workspace_subscription(db, ws.id)
        sub.plan_id = "internal"
        db.commit()
        conn_id = conn.id
    finally:
        db.close()

    login = client.post("/api/accounts/login", json={"email": email, "password": "role-pass-99-long"})
    assert login.status_code == 200
    res = client.post(
        f"/api/connections/{conn_id}/code-studio/validate",
        json={"code": "x = 1"},
    )
    assert res.status_code == expect


@patch("app.routers.code_studio.bind_code_action")
@patch("app.routers.code_studio.client_from_connection")
def test_bind_sets_audit_detail_with_full_code(
    mock_client_from,
    mock_bind,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    conn = _conn(probe={"supported": True})
    mock_client_from.return_value = MagicMock()
    mock_bind.return_value = {
        "bind_kind": "standalone",
        "code": "for rec in records: pass",
        "snapshot_id": "snap-1",
        "server_action_id": 5,
    }
    before = SessionLocal().query(AuditLog).count()
    res = client.post(
        f"/api/connections/{conn.id}/code-studio/bind",
        json={
            "name": "Test",
            "model": "res.partner",
            "code": "for rec in records: pass",
            "bind_kind": "standalone",
            "confirm_advanced": True,
            "confirm_phrase": "I understand the risks",
        },
    )
    assert res.status_code == 200, res.text
    after = SessionLocal().query(AuditLog).count()
    assert after > before
    row = SessionLocal().query(AuditLog).order_by(AuditLog.created_at.desc()).first()
    assert row and row.detail_json
    detail = json.loads(row.detail_json)
    assert detail["code"] == "for rec in records: pass"
    assert detail["operation"] == "code_studio_bind"


def test_observer_mode_refuses_bind(client: TestClient) -> None:
    conn = _conn(probe={"supported": True})
    db = SessionLocal()
    try:
        row = db.get(OdooConnection, conn.id)
        row.write_mode = "observer"
        db.commit()
    finally:
        db.close()
    res = client.post(
        f"/api/connections/{conn.id}/code-studio/bind",
        json={
            "name": "Test",
            "model": "res.partner",
            "code": "x=1",
            "bind_kind": "standalone",
            "confirm_advanced": True,
            "confirm_phrase": "I understand the risks",
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "observer_mode"
