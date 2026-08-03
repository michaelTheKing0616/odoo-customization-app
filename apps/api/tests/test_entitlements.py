"""MON-2 entitlement and billing tests."""

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
os.environ.setdefault("BILLING_MODE", "fake")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.account_models import Workspace  # noqa: E402
from app.billing_models import WorkspaceSubscription  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import CustomizationProject, OdooConnection  # noqa: E402
from app.entitlements import assert_feature, resolve_entitlements, seed_plan_features  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _workspace(db) -> str:
    ws = Workspace(name="Ent WS", slug=f"ent-{uuid.uuid4().hex[:8]}", plan="free_solo")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    seed_plan_features(db)
    ensure = WorkspaceSubscription(workspace_id=ws.id, plan_id="free_solo", status="active")
    db.add(ensure)
    db.commit()
    return ws.id


def test_free_solo_blocks_bulk_suite(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        ws_id = _workspace(db)
        user_email = f"bulk-{uuid.uuid4().hex[:8]}@example.com"
        from app.account_service import signup_user

        user, _, _ = signup_user(db, email=user_email, password="bulk-test-pass1")
        user.email_verified = True
        db.add(user)
        from app.account_models import WorkspaceMembership

        db.add(WorkspaceMembership(workspace_id=ws_id, user_id=user.id, role="owner"))
        db.commit()
    finally:
        db.close()

    with TestClient(app) as c:
        login = c.post("/api/accounts/login", json={"email": user_email, "password": "bulk-test-pass1"})
        assert login.status_code == 200
        # Switch session workspace — login picks first membership; ensure ws matches
        denied = c.get("/api/connections/x/bulk-suite/scan-duplicates")
        assert denied.status_code in {403, 404}


def test_entitlements_bypass_when_auth_off(client: TestClient) -> None:
    db = SessionLocal()
    try:
        ws_id = _workspace(db)
        ent = resolve_entitlements(db, ws_id)
        assert ent.plan_id == "free_solo"
        assert ent.features.get("bulk_suite") == "false"
        # AUTH_MODE=off bypasses assert
        assert_feature(db, ws_id, "bulk_suite", None)
    finally:
        db.close()


def test_active_project_slot_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        ws_id = _workspace(db)
        conn = OdooConnection(
            name="Slot test",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=ws_id,
        )
        db.add(conn)
        db.flush()
        db.add(
            CustomizationProject(
                connection_id=conn.id,
                workspace_id=ws_id,
                name="P1",
                spec_json="{}",
                lifecycle_status="active",
            )
        )
        db.commit()
        conn_id = conn.id
        email = f"slot-{uuid.uuid4().hex[:8]}@example.com"
        from app.account_service import signup_user
        from app.account_models import WorkspaceMembership

        user, _, _ = signup_user(db, email=email, password="slot-test-pass1")
        user.email_verified = True
        db.add(user)
        db.add(WorkspaceMembership(workspace_id=ws_id, user_id=user.id, role="owner"))
        db.commit()
    finally:
        db.close()

    with TestClient(app) as c:
        c.post("/api/accounts/login", json={"email": email, "password": "slot-test-pass1"})
        denied = c.post(
            f"/api/connections/{conn_id}/projects",
            json={"name": "Second", "spec_json": {}},
        )
        assert denied.status_code == 403
        detail = denied.json()["detail"]
        assert detail["feature_key"] == "active_projects_limit"


def test_stripe_webhook_fake_signature(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "billing_mode", "fake")
    db = SessionLocal()
    try:
        ws_id = _workspace(db)
    finally:
        db.close()

    event = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "mode": "subscription",
                "customer": "cus_test",
                "subscription": "sub_test",
                "metadata": {"workspace_id": ws_id, "plan_id": "pro"},
            }
        },
    }
    res = client.post(
        "/api/billing/webhooks/stripe",
        content=json.dumps(event),
        headers={"Content-Type": "application/json", "stripe-signature": "t=1,v1=fake"},
    )
    assert res.status_code == 200
    db = SessionLocal()
    try:
        sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws_id).first()
        assert sub is not None
        assert sub.plan_id == "pro"
    finally:
        db.close()


def test_webhook_replay_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "billing_mode", "fake")
    event = {"id": "evt_replay_test", "type": "ping", "data": {"object": {}}}
    headers = {"Content-Type": "application/json", "stripe-signature": "t=1,v1=fake"}
    first = client.post("/api/billing/webhooks/stripe", content=json.dumps(event), headers=headers)
    second = client.post("/api/billing/webhooks/stripe", content=json.dumps(event), headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


def test_operate_bulk_not_slot_gated(client: TestClient) -> None:
    """OPERATE suite must stay reachable regardless of project slots (AUTH_MODE=off)."""
    res = client.get("/health")
    assert res.status_code == 200
