"""TRUST-9 design-partner beta gating + telemetry tests."""

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

from app.account_models import User, Workspace  # noqa: E402
from app.account_service import signup_user  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import HealthCheckRun, OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.production_readiness import confirm_least_privilege, run_snapshot_drill, verify_backup_artifact  # noqa: E402
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _complete_readiness(db, conn: OdooConnection) -> None:
    run_snapshot_drill(db, conn)
    confirm_least_privilege(db, conn, acknowledge_admin=True)
    verify_backup_artifact(db, conn.id)
    db.add(
        HealthCheckRun(
            connection_id=conn.id,
            status="complete",
            ok_count=1,
            broken_count=0,
            report_json="[]",
            message="ok",
        )
    )
    db.commit()


def _conn_with_workspace(*, beta: bool = False) -> tuple[OdooConnection, str]:
    db = SessionLocal()
    try:
        _user, ws, _ = signup_user(
            db,
            email=f"beta-{uuid.uuid4().hex[:8]}@example.com",
            password="beta-pass-99-long",
        )
        ws.beta_partner = beta
        db.add(ws)
        conn = OdooConnection(
            name="beta-conn",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="custom",
            secret_encrypted=encrypt_secret("secret"),
            write_mode="standard",
            server_version="19.0",
            workspace_id=ws.id,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        return conn, ws.id
    finally:
        db.close()


def test_production_blocked_without_beta_partner(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "beta_production_gating_enabled", True)
    monkeypatch.setattr(settings, "production_write_mode_ga_unlocked", False)
    conn, _ws_id = _conn_with_workspace(beta=False)
    db = SessionLocal()
    try:
        _complete_readiness(db, conn)
    finally:
        db.close()

    resp = client.patch(
        f"/api/connections/{conn.id}/write-mode",
        json={"write_mode": "production"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "beta_partner_required"


def test_production_allowed_for_beta_partner(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "beta_production_gating_enabled", True)
    monkeypatch.setattr(settings, "production_write_mode_ga_unlocked", False)
    conn, _ws_id = _conn_with_workspace(beta=True)
    db = SessionLocal()
    try:
        _complete_readiness(db, conn)
    finally:
        db.close()

    resp = client.patch(
        f"/api/connections/{conn.id}/write-mode",
        json={"write_mode": "production"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["write_mode"] == "production"


def test_ga_unlock_bypasses_beta_gate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "production_write_mode_ga_unlocked", True)
    conn, _ws_id = _conn_with_workspace(beta=False)
    db = SessionLocal()
    try:
        _complete_readiness(db, conn)
    finally:
        db.close()

    resp = client.patch(
        f"/api/connections/{conn.id}/write-mode",
        json={"write_mode": "production"},
    )
    assert resp.status_code == 200


def test_admin_trust_telemetry_and_ga_criteria(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "app_admin_email", f"sa-{uuid.uuid4().hex[:6]}@test.local")
    monkeypatch.setattr(settings, "app_admin_password", "superadmin-pass-99")
    init_db()
    db = SessionLocal()
    try:
        for u in db.query(User).filter(User.is_superadmin.is_(True)).all():
            db.delete(u)
        db.commit()
        from app.admin_bootstrap import bootstrap_superadmin_from_env

        assert bootstrap_superadmin_from_env(db) is True
    finally:
        db.close()

    with TestClient(app) as admin_client:
        login = admin_client.post(
            "/api/accounts/login",
            json={"email": settings.app_admin_email, "password": settings.app_admin_password},
        )
        assert login.status_code == 200, login.text

        criteria = admin_client.get("/api/admin/ga-criteria")
        assert criteria.status_code == 200
        assert criteria.json()["min_beta_partner_workspaces"] == settings.beta_ga_min_workspaces

        telemetry = admin_client.get("/api/admin/trust-telemetry")
        assert telemetry.status_code == 200
        body = telemetry.json()
        assert "workspaces" in body
        assert "totals" in body


def test_admin_set_beta_partner_flag(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "app_admin_email", f"sa2-{uuid.uuid4().hex[:6]}@test.local")
    monkeypatch.setattr(settings, "app_admin_password", "superadmin-pass-99")
    init_db()
    db = SessionLocal()
    try:
        for u in db.query(User).filter(User.is_superadmin.is_(True)).all():
            db.delete(u)
        db.commit()
        from app.admin_bootstrap import bootstrap_superadmin_from_env

        assert bootstrap_superadmin_from_env(db) is True
        _user, ws, _ = signup_user(
            db,
            email=f"ws-{uuid.uuid4().hex[:8]}@example.com",
            password="ws-pass-99-long",
        )
        ws_id = ws.id
    finally:
        db.close()

    with TestClient(app) as admin_client:
        login = admin_client.post(
            "/api/accounts/login",
            json={"email": settings.app_admin_email, "password": settings.app_admin_password},
        )
        assert login.status_code == 200

        patch = admin_client.patch(
            f"/api/admin/workspaces/{ws_id}/beta-partner",
            json={"enabled": True, "reason": "design partner onboarding"},
        )
        assert patch.status_code == 200
        assert patch.json()["beta_partner"] is True

        db = SessionLocal()
        try:
            ws = db.get(Workspace, ws_id)
            assert ws is not None
            assert ws.beta_partner is True
        finally:
            db.close()
