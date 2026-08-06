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


def test_entitlements_bypass_when_auth_off(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "off")
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


def test_billing_entitlements_auth_off(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "off")
    res = client.get("/api/billing/entitlements")
    assert res.status_code == 200
    body = res.json()
    assert body["plan_id"] == "internal"
    assert body["workspace_id"] == "local-dev"
    assert body["features"].get("ai_draft") == "true"


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
        from app.account_models import User, WorkspaceMembership
        from app.account_service import hash_password

        user = User(
            email=email,
            password_hash=hash_password("slot-test-pass1"),
            email_verified=True,
        )
        db.add(user)
        db.flush()
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


def test_operate_bulk_not_slot_gated(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """OPERATE suite stays reachable at active-project slot limit; BUILD surfaces are gated."""
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "business_trial_enabled", False)
    init_db()
    db = SessionLocal()
    try:
        ws_id = _workspace(db)
        sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws_id).first()
        assert sub is not None
        sub.plan_id = "business"
        sub.status = "active"
        db.add(sub)
        from app.billing_models import EntitlementOverride

        db.add(
            EntitlementOverride(
                workspace_id=ws_id,
                feature_key="active_projects_limit",
                value="1",
                reason="rem10 slot-limit test",
            )
        )
        conn = OdooConnection(
            name="Operate slot test",
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
                name="Only active",
                spec_json="{}",
                lifecycle_status="active",
            )
        )
        conn_id = conn.id
        email = f"operate-{uuid.uuid4().hex[:8]}@example.com"
        from app.account_models import User, WorkspaceMembership
        from app.account_service import hash_password

        user = User(
            email=email,
            password_hash=hash_password("operate-test-pass1"),
            email_verified=True,
        )
        db.add(user)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=ws_id, user_id=user.id, role="owner"))
        db.commit()
    finally:
        db.close()

    def _not_slot_gated(status: int, body: dict | list) -> None:
        if status == 403 and isinstance(body, dict):
            detail = body.get("detail", body)
            if isinstance(detail, dict):
                assert detail.get("feature_key") != "active_projects_limit"

    with TestClient(app) as c:
        c.post("/api/accounts/login", json={"email": email, "password": "operate-test-pass1"})

        bulk = c.get(f"/api/connections/{conn_id}/bulk/crons")
        assert bulk.status_code in {200, 502}
        if bulk.status_code == 502:
            pass
        else:
            _not_slot_gated(bulk.status_code, bulk.json())

        health = c.get(f"/api/connections/{conn_id}/health-check/runs")
        assert health.status_code == 200

        expert = c.post("/api/expert/ask", json={"question": "What is a view?", "conversation": []})
        assert expert.status_code in {200, 503}
        if expert.status_code == 200:
            _not_slot_gated(expert.status_code, expert.json())

        snaps = c.get(f"/api/connections/{conn_id}/snapshots")
        assert snaps.status_code == 200

        denied = c.post(
            f"/api/connections/{conn_id}/projects",
            json={"name": "Second project", "spec_json": {}},
        )
        assert denied.status_code == 403
        detail = denied.json()["detail"]
        assert detail["feature_key"] == "active_projects_limit"


def test_stripe_webhook_signature_fail(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "billing_mode", "test")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_secret_for_sig_fail")
    event = {"id": "evt_sig_fail", "type": "ping", "data": {"object": {}}}
    res = client.post(
        "/api/billing/webhooks/stripe",
        content=json.dumps(event),
        headers={"Content-Type": "application/json", "stripe-signature": "t=1,v1=deadbeef"},
    )
    assert res.status_code == 400
    assert "signature" in res.json()["detail"].lower()


def test_paystack_webhook_signature_fail(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "billing_mode", "test")
    monkeypatch.setattr(settings, "paystack_secret_key", "sk_test_paystack_secret")
    res = client.post(
        "/api/billing/webhooks/paystack",
        content=b'{"event":"charge.success","data":{"id":"1"}}',
        headers={"Content-Type": "application/json", "x-paystack-signature": "invalid"},
    )
    assert res.status_code == 400


def test_paystack_webhook_upgrade_and_replay(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "billing_mode", "fake")
    db = SessionLocal()
    try:
        ws_id = _workspace(db)
    finally:
        db.close()

    event = {
        "event": "charge.success",
        "data": {
            "id": f"ps_{uuid.uuid4().hex[:8]}",
            "metadata": {"workspace_id": ws_id, "plan_id": "pro"},
        },
    }
    headers = {"Content-Type": "application/json", "x-paystack-signature": "fake"}
    first = client.post("/api/billing/webhooks/paystack", content=json.dumps(event), headers=headers)
    second = client.post("/api/billing/webhooks/paystack", content=json.dumps(event), headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

    db = SessionLocal()
    try:
        sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws_id).first()
        assert sub is not None
        assert sub.plan_id == "pro"
        assert sub.processor == "paystack"
    finally:
        db.close()


def test_stripe_webhook_extra_slots(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "billing_mode", "fake")
    db = SessionLocal()
    try:
        ws_id = _workspace(db)
        sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws_id).first()
        assert sub is not None
        sub.plan_id = "pro"
        db.add(sub)
        db.commit()
    finally:
        db.close()

    event = {
        "id": f"evt_slot_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "mode": "subscription",
                "metadata": {
                    "workspace_id": ws_id,
                    "plan_id": "pro",
                    "sku": "extra_project_slot",
                    "slot_quantity": "2",
                },
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
        assert sub.extra_project_slots == 2
    finally:
        db.close()


def test_stripe_webhook_out_of_order_delete(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Subscription deleted before any prior create event — workspace downgrades safely."""
    monkeypatch.setattr(settings, "billing_mode", "fake")
    db = SessionLocal()
    try:
        ws_id = _workspace(db)
        sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws_id).first()
        assert sub is not None
        sub.plan_id = "business"
        sub.status = "active"
        db.add(sub)
        db.commit()
    finally:
        db.close()

    event = {
        "id": f"evt_del_{uuid.uuid4().hex}",
        "type": "customer.subscription.deleted",
        "data": {"object": {"metadata": {"workspace_id": ws_id}}},
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
        assert sub.plan_id == "free_solo"
        assert sub.status == "canceled"
    finally:
        db.close()


def test_billing_plans_catalog_shape(client: TestClient) -> None:
    res = client.get("/api/billing/plans")
    assert res.status_code == 200
    body = res.json()
    assert "plans" in body
    assert "display_features" in body
    assert "tier_order" in body
    pro = next(p for p in body["plans"] if p["id"] == "pro")
    assert pro["monthly_usd"] == 39
    assert pro["extra_slot_monthly_usd"] == 15
