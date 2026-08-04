"""DEV-2 — module-spec lint/export-sandbox role and entitlement gating."""

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

from app.account_models import User, WorkspaceMembership  # noqa: E402
from app.account_service import hash_password, signup_user  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.entitlements import ensure_workspace_subscription, seed_plan_features  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402

SPEC = {
    "technical_name": "x_dev_gate",
    "custom_code_blocks": [
        {"source_file": "models/x.py", "kind": "python", "content": "x = 1\n"},
    ],
}


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _conn_with_role(role: str, *, plan: str = "internal") -> tuple[str, str]:
    """Return (connection_id, user_email) for a workspace member with given role."""
    db = SessionLocal()
    try:
        seed_plan_features(db)
        owner_email = f"o-{uuid.uuid4().hex[:6]}@example.com"
        _owner, ws, _ = signup_user(
            db,
            email=owner_email,
            password="owner-pass-99-long",
        )
        member_email = f"m-{uuid.uuid4().hex[:6]}@example.com"
        user = User(
            email=member_email,
            password_hash=hash_password("member-pass-99-long"),
            email_verified=True,
        )
        db.add(user)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=role))
        conn = OdooConnection(
            name="dev2-gate",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
            workspace_id=ws.id,
        )
        db.add(conn)
        sub = ensure_workspace_subscription(db, ws.id)
        sub.plan_id = plan
        sub.status = "active"
        db.commit()
        return conn.id, member_email
    finally:
        db.close()


@pytest.mark.parametrize(
    "route",
    [
        "/module-spec/lint-blocks",
        "/module-spec/export-sandbox",
    ],
)
def test_builder_cannot_lint_or_export_sandbox(
    client: TestClient,
    route: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    conn_id, email = _conn_with_role("builder")
    client.post("/api/accounts/login", json={"email": email, "password": "member-pass-99-long"})
    res = client.post(
        f"/api/connections/{conn_id}{route}",
        json={"spec": SPEC, "async_job": False},
    )
    assert res.status_code == 403


def test_developer_can_lint_blocks(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    conn_id, email = _conn_with_role("developer")
    client.post("/api/accounts/login", json={"email": email, "password": "member-pass-99-long"})
    res = client.post(
        f"/api/connections/{conn_id}/module-spec/lint-blocks",
        json={"spec": SPEC},
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True


def test_remote_python_promote_refusal_named_test_exists() -> None:
    """DEV-2 card: remote no-filesystem promote refusal — covered by existing contract tests."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    hosting = (repo / "tests" / "test_hosting_m1.py").read_text(encoding="utf-8")
    mastery = (repo / "tests" / "test_mastery_regression_battery.py").read_text(encoding="utf-8")
    assert "test_promote_python_zip_online_error_contract" in hosting
    assert "test_promote_online_python_error_substring_and_guidance" in mastery
