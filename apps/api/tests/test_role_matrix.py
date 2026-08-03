"""Role matrix tests — viewer/builder/admin/owner × router families (REM-10)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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

from app.account_models import User, WorkspaceMembership  # noqa: E402
from app.account_service import hash_password, signup_user  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.entitlements import ensure_workspace_subscription, seed_plan_features  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:8]}@example.com"


def _workspace_with_roles(db) -> tuple[str, str, dict[str, tuple[str, str]]]:
    """Returns workspace_id, connection_id, role -> (email, password)."""
    seed_plan_features(db)
    owner, ws, _ = signup_user(db, email=_email("owner"), password="owner-pass-99")
    owner.email_verified = True
    db.add(owner)
    roles: dict[str, tuple[str, str]] = {"owner": (owner.email, "owner-pass-99")}

    for role in ("admin", "builder", "viewer"):
        email = _email(role)
        password = f"{role}-pass-99"
        user = User(email=email, password_hash=hash_password(password), email_verified=True)
        db.add(user)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=role))
        roles[role] = (email, password)

    conn = OdooConnection(
        name="Matrix conn",
        url="http://127.0.0.1:8069",
        db_name="odoo_dev",
        username="admin",
        secret_encrypted=encrypt_secret("admin"),
        workspace_id=ws.id,
    )
    db.add(conn)
    sub = ensure_workspace_subscription(db, ws.id)
    sub.plan_id = "internal"
    sub.status = "active"
    db.add(sub)
    db.commit()
    return ws.id, conn.id, roles


def _login(client: TestClient, email: str, password: str) -> None:
    res = client.post("/api/accounts/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text


@pytest.mark.parametrize(
    "role,expect_create",
    [
        ("viewer", 403),
        ("builder", 201),
        ("admin", 201),
        ("owner", 201),
    ],
)
def test_connections_create_role_matrix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, role: str, expect_create: int
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "business_trial_enabled", False)
    init_db()
    db = SessionLocal()
    try:
        _ws_id, _conn_id, roles = _workspace_with_roles(db)
        email, password = roles[role]
    finally:
        db.close()

    with TestClient(app) as c:
        _login(c, email, password)
        res = c.post(
            "/api/connections",
            json={
                "name": f"New {role}",
                "url": "http://127.0.0.1:8069",
                "db_name": "odoo_dev",
                "username": "admin",
                "password": "admin",
                "verify": False,
            },
        )
        assert res.status_code == expect_create


@pytest.mark.parametrize(
    "role,expect_delete",
    [
        ("viewer", 403),
        ("builder", 403),
        ("admin", 204),
        ("owner", 204),
    ],
)
def test_connections_delete_role_matrix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, role: str, expect_delete: int
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        _ws_id, conn_id, roles = _workspace_with_roles(db)
        email, password = roles[role]
    finally:
        db.close()

    with TestClient(app) as c:
        _login(c, email, password)
        res = c.delete(f"/api/connections/{conn_id}")
        assert res.status_code == expect_delete


@pytest.mark.parametrize(
    "role,expect_checkout",
    [
        ("viewer", 403),
        ("builder", 403),
        ("admin", 200),
        ("owner", 200),
    ],
)
def test_billing_checkout_role_matrix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, role: str, expect_checkout: int
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "billing_mode", "fake")
    monkeypatch.setattr(settings, "business_trial_enabled", False)
    init_db()
    db = SessionLocal()
    try:
        _ws_id, _conn_id, roles = _workspace_with_roles(db)
        email, password = roles[role]
    finally:
        db.close()

    with TestClient(app) as c:
        _login(c, email, password)
        res = c.post(
            "/api/billing/checkout/stripe",
            json={
                "plan_id": "pro",
                "seat_quantity": 1,
                "success_url": "http://localhost/success",
                "cancel_url": "http://localhost/cancel",
            },
        )
        assert res.status_code == expect_checkout


def test_all_roles_read_connections(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        _ws_id, _conn_id, roles = _workspace_with_roles(db)
    finally:
        db.close()

    with TestClient(app) as c:
        for role, (email, password) in roles.items():
            _login(c, email, password)
            listed = c.get("/api/connections")
            assert listed.status_code == 200, role
            names = {row["name"] for row in listed.json()}
            assert "Matrix conn" in names, role


def test_viewer_cannot_invite(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        _ws_id, _conn_id, roles = _workspace_with_roles(db)
        email, password = roles["viewer"]
    finally:
        db.close()

    with TestClient(app) as c:
        _login(c, email, password)
        denied = c.post(
            "/api/accounts/invitations",
            json={"email": _email("invitee"), "role": "viewer"},
        )
        assert denied.status_code == 403


@pytest.mark.parametrize(
    "role,expect_denied",
    [
        ("viewer", 403),
        ("builder", 403),
        ("admin", 403),
        ("owner", 403),
    ],
)
def test_projects_slot_limit_role_matrix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, role: str, expect_denied: int
) -> None:
    """At active-project slot limit, every role is blocked equally (slot gate, not role gate)."""
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "business_trial_enabled", False)
    init_db()
    db = SessionLocal()
    try:
        ws_id, conn_id, roles = _workspace_with_roles(db)
        from app.billing_models import EntitlementOverride
        from app.db_models import CustomizationProject

        sub = ensure_workspace_subscription(db, ws_id)
        sub.plan_id = "pro"
        sub.status = "active"
        db.add(sub)
        db.add(
            EntitlementOverride(
                workspace_id=ws_id,
                feature_key="active_projects_limit",
                value="1",
                reason="role-matrix slot test",
            )
        )
        db.add(
            CustomizationProject(
                connection_id=conn_id,
                workspace_id=ws_id,
                name="Existing",
                spec_json="{}",
                lifecycle_status="active",
            )
        )
        db.commit()
        email, password = roles[role]
    finally:
        db.close()

    with TestClient(app) as c:
        _login(c, email, password)
        res = c.post(
            f"/api/connections/{conn_id}/projects",
            json={"name": f"Second {role}", "spec_json": {}},
        )
        assert res.status_code == expect_denied
        assert res.json()["detail"]["feature_key"] == "active_projects_limit"


@pytest.mark.parametrize(
    "role,expect_read",
    [
        ("viewer", 200),
        ("builder", 200),
        ("admin", 200),
        ("owner", 200),
    ],
)
def test_bulk_read_role_matrix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, role: str, expect_read: int
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        _ws_id, conn_id, roles = _workspace_with_roles(db)
        email, password = roles[role]
    finally:
        db.close()

    mock_client = MagicMock()
    with patch("app.routers.bulk_suite.client_from_connection", return_value=mock_client), patch(
        "app.routers.bulk_suite.list_crons_enriched",
        return_value=([], {"supported": True}),
    ):
        with TestClient(app) as c:
            _login(c, email, password)
            res = c.get(f"/api/connections/{conn_id}/bulk/crons")
            assert res.status_code == expect_read


@pytest.mark.parametrize(
    "role,expect_status",
    [
        ("viewer", 422),
        ("builder", 422),
        ("admin", 422),
        ("owner", 422),
    ],
)
def test_automations_pcm_role_matrix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, role: str, expect_status: int
) -> None:
    """PCM refusal is role-agnostic — tier-1 write blocked for every role."""
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        _ws_id, conn_id, roles = _workspace_with_roles(db)
        email, password = roles[role]
    finally:
        db.close()

    with TestClient(app) as c:
        _login(c, email, password)
        res = c.post(
            f"/api/connections/{conn_id}/automations",
            json={
                "name": "Evil",
                "model": "account.move",
                "trigger": "on_create",
                "action_kind": "update_field",
                "field_name": "state",
                "value": "posted",
            },
        )
        assert res.status_code == expect_status


@pytest.mark.parametrize(
    "role,expect_ask",
    [
        ("viewer", 200),
        ("builder", 200),
        ("admin", 200),
        ("owner", 200),
    ],
)
def test_expert_ask_role_matrix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, role: str, expect_ask: int
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        _ws_id, _conn_id, roles = _workspace_with_roles(db)
        email, password = roles[role]
    finally:
        db.close()

    with TestClient(app) as c:
        _login(c, email, password)
        res = c.post("/api/expert/ask", json={"question": "What is ir.ui.view?", "conversation": []})
        assert res.status_code in {expect_ask, 503}


@pytest.mark.parametrize(
    "role,expect_admin",
    [
        ("viewer", 403),
        ("builder", 403),
        ("admin", 403),
        ("owner", 403),
    ],
)
def test_superadmin_console_role_matrix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, role: str, expect_admin: int
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        _ws_id, _conn_id, roles = _workspace_with_roles(db)
        email, password = roles[role]
    finally:
        db.close()

    with TestClient(app) as c:
        _login(c, email, password)
        res = c.get("/api/admin/workspaces")
        assert res.status_code == expect_admin


@pytest.mark.parametrize(
    "role,expect_invite",
    [
        ("viewer", 403),
        ("builder", 403),
        ("admin", 201),
        ("owner", 201),
    ],
)
def test_invitations_create_role_matrix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, role: str, expect_invite: int
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        _ws_id, _conn_id, roles = _workspace_with_roles(db)
        email, password = roles[role]
    finally:
        db.close()

    with TestClient(app) as c:
        _login(c, email, password)
        res = c.post(
            "/api/accounts/invitations",
            json={"email": _email("matrix-invitee"), "role": "viewer"},
        )
        assert res.status_code == expect_invite
