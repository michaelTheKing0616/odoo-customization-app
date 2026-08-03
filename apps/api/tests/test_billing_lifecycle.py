"""Billing lifecycle, jobs, and plan diff tests (Wave 9 finish)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom")
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.account_models import Workspace  # noqa: E402
from app.billing_jobs import expire_project_passes, run_billing_jobs_on_boot  # noqa: E402
from app.billing_models import EntitlementOverride, ProjectPass, WorkspaceSubscription  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.entitlements import ensure_workspace_subscription, plan_feature_diff, resolve_entitlements, seed_plan_features  # noqa: E402
from app.settings import settings  # noqa: E402


@pytest.fixture
def db():
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_business_trial_on_new_workspace(db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "business_trial_enabled", True)
    seed_plan_features(db)
    ws = Workspace(name="Trial WS", slug=f"trial-{uuid.uuid4().hex[:8]}", plan="free_solo")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    sub = ensure_workspace_subscription(db, ws.id)
    assert sub.status == "trialing"
    assert sub.plan_id == "business"
    assert sub.trial_ends_at is not None


def test_plan_feature_diff_pro_to_free(db) -> None:
    seed_plan_features(db)
    lost = plan_feature_diff(db, "pro", "free_solo")
    keys = {x["feature_key"] for x in lost}
    assert "designer" in keys
    assert "bulk_suite" in keys or "automations" in keys


def test_override_expiry_ignored(db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "business_trial_enabled", False)
    seed_plan_features(db)
    ws = Workspace(name="Ov", slug=f"ov-{uuid.uuid4().hex[:8]}", plan="free_solo")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    ensure_workspace_subscription(db, ws.id)
    db.add(
        EntitlementOverride(
            workspace_id=ws.id,
            feature_key="designer",
            value="true",
            reason="expired",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
    )
    db.add(
        EntitlementOverride(
            workspace_id=ws.id,
            feature_key="import",
            value="true",
            reason="test active",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    db.commit()
    ent = resolve_entitlements(db, ws.id)
    assert ent.features.get("designer") != "true"
    assert ent.features.get("import") == "true"


def test_project_pass_expiry_job(db) -> None:
    ws = Workspace(name="Pass", slug=f"pass-{uuid.uuid4().hex[:8]}", plan="free_solo")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    db.add(
        ProjectPass(
            workspace_id=ws.id,
            status="active",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    db.commit()
    n = expire_project_passes(db)
    assert n == 1
    row = db.query(ProjectPass).filter(ProjectPass.workspace_id == ws.id).first()
    assert row is not None
    assert row.status == "expired"


def test_bootstrap_admin_no_password_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    from app.admin_bootstrap import bootstrap_superadmin_from_env

    caplog.set_level(logging.INFO)
    db = SessionLocal()
    try:
        bootstrap_superadmin_from_env(db)
    finally:
        db.close()
    for record in caplog.records:
        assert "bootstrap-test" not in record.getMessage().lower()
        assert "password" not in record.getMessage().lower() or "env" in record.getMessage().lower()
