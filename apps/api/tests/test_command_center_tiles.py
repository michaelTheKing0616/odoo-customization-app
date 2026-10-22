"""T6-08 — read-only command center tile counts."""

from __future__ import annotations

import json
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
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import BackgroundJob, OdooConnection, PlanCardRecord  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


def _email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_command_tiles_return_scoped_counts(client: TestClient) -> None:
    init_db()
    db = SessionLocal()
    try:
        _owner, workspace, _ = signup_user(
            db,
            email=_email("owner"),
            password="owner-pass-99",
            workspace_name="Fleet",
        )
        conn = OdooConnection(
            name="Alpha",
            url="http://127.0.0.1:8069",
            db_name="alpha",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
            upgrade_detected=True,
        )
        db.add(conn)
        db.flush()
        db.add(
            PlanCardRecord(
                connection_id=conn.id,
                requester_id="req-1",
                plan_hash="abc123def4567890",
                status="pending",
                card_json=json.dumps({"plan_hash": "abc123def4567890", "connection_id": conn.id}),
            )
        )
        db.add(
            BackgroundJob(
                kind="sandbox",
                connection_id=conn.id,
                status="failed",
                error="boom",
            )
        )
        db.commit()
        conn_id = conn.id
    finally:
        db.close()

    clients = client.get("/api/command/tiles/clients")
    assert clients.status_code == 200
    assert clients.json()["count"] >= 1

    pending = client.get("/api/command/tiles/pending-approvals")
    assert pending.status_code == 200
    assert pending.json()["count"] >= 1

    failed = client.get("/api/command/tiles/failed-jobs")
    assert failed.status_code == 200
    assert failed.json()["count"] >= 1

    drift = client.get("/api/command/tiles/drift")
    assert drift.status_code == 200
    assert drift.json()["count"] >= 1

    assert conn_id


def test_client_grant_cannot_read_command_tiles(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        owner, workspace, _ = signup_user(
            db,
            email=_email("owner2"),
            password="owner-pass-99",
            workspace_name="Agency",
        )
        owner.email_verified = True
        db.add(owner)
        conn = OdooConnection(
            name="Granted",
            url="http://127.0.0.1:8069",
            db_name="granted",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        db.add(conn)
        db.flush()
        from app.account_models import User

        approver = User(
            email=_email("approver"),
            password_hash=hash_password("approver-pass-99"),
            email_verified=True,
        )
        db.add(approver)
        db.flush()
        grant_connection_access(
            db,
            workspace_id=workspace.id,
            connection_id=conn.id,
            user_id=approver.id,
            role="client_approver",
            actor_user_id=owner.id,
        )
        db.commit()
        approver_email = approver.email
    finally:
        db.close()

    login = client.post(
        "/api/accounts/login",
        json={"email": approver_email, "password": "approver-pass-99"},
    )
    assert login.status_code == 200

    denied = client.get("/api/command/tiles/clients")
    assert denied.status_code == 403
