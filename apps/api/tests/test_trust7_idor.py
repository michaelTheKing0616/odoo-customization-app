"""TRUST-7 — cross-workspace IDOR sweep + route-enumeration guard."""

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
os.environ.setdefault("BILLING_MODE", "fake")

from app.account_models import User, WorkspaceMembership  # noqa: E402
from app.account_service import hash_password, signup_user  # noqa: E402
from app.bulk_suite.storage import save_bulk_run  # noqa: E402
from app.bulk_suite.transitions import BulkRunResult  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import CustomizationProject, MetadataSnapshot, OdooConnection  # noqa: E402
from app.entitlements import ensure_workspace_subscription, seed_plan_features  # noqa: E402
from app.main import app  # noqa: E402
from app.security.idor_registry import (  # noqa: E402
    IDOR_GET_PROBES,
    connection_scoped_paths,
    idor_probe_paths,
)
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:8]}@example.com"


def _login(client: TestClient, email: str, password: str) -> None:
    res = client.post("/api/accounts/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text


class CrossWorkspaceFixture:
    """Alice workspace owns victim resources; Bob tries to read them."""

    def __init__(self) -> None:
        self.alice_email = _email("alice")
        self.bob_email = _email("bob")
        self.alice_password = "alice-pass-99"
        self.bob_password = "bob-pass-99"
        self.victim_connection_id = ""
        self.victim_project_id = ""
        self.victim_snapshot_id = ""
        self.victim_run_id = ""


def _seed_cross_workspace() -> CrossWorkspaceFixture:
    fx = CrossWorkspaceFixture()
    db = SessionLocal()
    try:
        seed_plan_features(db)
        _alice, ws_a, _ = signup_user(
            db,
            email=fx.alice_email,
            password=fx.alice_password,
            workspace_name="Alice WS",
        )
        _bob, ws_b, _ = signup_user(
            db,
            email=fx.bob_email,
            password=fx.bob_password,
            workspace_name="Bob WS",
        )
        for email in (fx.alice_email, fx.bob_email):
            user = db.query(User).filter(User.email == email).one()
            user.email_verified = True
            db.add(user)

        conn = OdooConnection(
            name="Alice victim conn",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("super-secret-password"),
            workspace_id=ws_a.id,
        )
        db.add(conn)
        db.flush()
        fx.victim_connection_id = conn.id

        project = CustomizationProject(
            connection_id=conn.id,
            workspace_id=ws_a.id,
            name="Alice project",
            spec_json="{}",
            lifecycle_status="active",
        )
        db.add(project)
        db.flush()
        fx.victim_project_id = project.id

        snap = MetadataSnapshot(
            connection_id=conn.id,
            resource_type="field",
            resource_key="field:x_test",
            label="csv export",
            payload_json=json.dumps(
                {
                    "format": "csv",
                    "model": "res.partner",
                    "field_name": "email",
                    "csv": "email\na@example.com\n",
                }
            ),
            reversible="partial",
        )
        db.add(snap)
        db.flush()
        fx.victim_snapshot_id = snap.id

        for ws_id in (ws_a.id, ws_b.id):
            sub = ensure_workspace_subscription(db, ws_id)
            sub.plan_id = "internal"
            sub.status = "active"
            db.add(sub)

        db.commit()

        run = BulkRunResult(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            operation="transitions",
            model="res.partner",
            dry_run=True,
            total=1,
            succeeded=1,
            failed=0,
        )
        save_bulk_run(db, connection_id=conn.id, result=run)
        fx.victim_run_id = run.run_id
    finally:
        db.close()
    return fx


def test_connection_scoped_route_inventory_not_empty() -> None:
    paths = connection_scoped_paths(app.openapi()["paths"])
    assert len(paths) >= 20
    assert "/api/connections/{connection_id}" in paths


def test_idor_get_probes_still_in_openapi() -> None:
    missing = idor_probe_paths(app.openapi()["paths"])
    assert not missing, "Stale IDOR probes — update IDOR_GET_PROBES:\n" + "\n".join(
        f"{m} {p}" for m, p in missing
    )


@pytest.mark.parametrize("method,path_template", IDOR_GET_PROBES)
def test_cross_workspace_get_returns_404(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path_template: str,
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    fx = _seed_cross_workspace()

    path = path_template.format(
        connection_id=fx.victim_connection_id,
        project_id=fx.victim_project_id,
        snapshot_id=fx.victim_snapshot_id,
        run_id=fx.victim_run_id,
    )

    with TestClient(app) as bob_client:
        _login(bob_client, fx.bob_email, fx.bob_password)
        res = bob_client.request(method, path)
        assert res.status_code == 404, f"{method} {path} leaked: {res.status_code} {res.text[:200]}"


def test_admin_routes_require_superadmin(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        owner, ws, _ = signup_user(db, email=_email("owner"), password="owner-pass-99")
        owner.email_verified = True
        admin_email = _email("admin-user")
        admin_user = User(
            email=admin_email,
            password_hash=hash_password("admin-pass-99"),
            email_verified=True,
        )
        db.add(admin_user)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=admin_user.id, role="admin"))
        db.commit()
    finally:
        db.close()

    with TestClient(app) as c:
        _login(c, admin_email, "admin-pass-99")
        denied = c.get("/api/admin/users")
        assert denied.status_code == 403


def test_role_matrix_suite_present() -> None:
    """REM-10 role matrix absorbed — guard against accidental deletion."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).with_name("test_role_matrix.py")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "@pytest.mark.parametrize" in text
    assert "viewer" in text and "builder" in text


def test_webhook_hardening_regression() -> None:
    """Cross-check REM-10 webhook tests still present (no duplication)."""
    from pathlib import Path

    text = Path(__file__).with_name("test_entitlements.py").read_text(encoding="utf-8")
    assert "test_webhook_replay_rejected" in text
    assert "test_stripe_webhook_fake_signature" in text
