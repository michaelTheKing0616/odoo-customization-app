"""T6-01 — ROLE_CAPABILITIES enforced: roles × route groups (one probe per group)."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

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
from app.account_service import grant_connection_access, hash_password, signup_user  # noqa: E402
from app.client_access import (  # noqa: E402
    ROUTE_GROUPS,
    T6_MATRIX_ROLES,
    role_allows_route_group,
)
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402

_FIELD_OP = [{"type": "field.create", "params": {"model": "x_m", "name": "x_note"}}]


def _email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:8]}@example.com"


@dataclass
class T6Fixtures:
    granted_id: str
    other_id: str
    plan_hash: str
    schema_fp: str
    logins: dict[str, tuple[str, str]]


@pytest.fixture
def t6_ctx(monkeypatch: pytest.MonkeyPatch) -> T6Fixtures:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        owner, workspace, _ = signup_user(
            db, email=_email("owner"), password="owner-pass-99", workspace_name="Agency"
        )
        owner.email_verified = True
        db.add(owner)
        logins: dict[str, tuple[str, str]] = {"owner": (owner.email, "owner-pass-99")}

        for role in ("admin", "builder"):
            email = _email(role)
            password = f"{role}-pass-99"
            user = User(email=email, password_hash=hash_password(password), email_verified=True)
            db.add(user)
            db.flush()
            db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role=role))
            logins[role] = (email, password)

        granted = OdooConnection(
            name="Granted client",
            url="http://127.0.0.1:8069",
            db_name="granted",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        other = OdooConnection(
            name="Other client",
            url="http://127.0.0.1:8070",
            db_name="other",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        db.add(granted)
        db.add(other)
        db.flush()

        for grant_role in ("client_approver", "client_viewer"):
            email = _email(grant_role)
            password = f"{grant_role}-pass-99"
            user = User(email=email, password_hash=hash_password(password), email_verified=True)
            db.add(user)
            db.flush()
            grant_connection_access(
                db,
                workspace_id=workspace.id,
                connection_id=granted.id,
                user_id=user.id,
                role=grant_role,
            )
            logins[grant_role] = (email, password)

        granted_id = granted.id
        other_id = other.id
    finally:
        db.close()

    with TestClient(app) as client:
        email, password = logins["owner"]
        login = client.post("/api/accounts/login", json={"email": email, "password": password})
        assert login.status_code == 200, login.text
        submitted = client.post(
            "/api/inbox/plans",
            json={
                "connection_id": granted_id,
                "requester_id": "owner",
                "goal": "Add a note",
                "assumptions": [],
                "environment": "staging",
                "known_models": ["x_m"],
                "changeset": _FIELD_OP,
            },
        )
        assert submitted.status_code == 200, submitted.text
        card = submitted.json()["card"]
        plan_hash = card["plan_hash"]
        schema_fp = card["schema_fp"]

    return T6Fixtures(
        granted_id=granted_id,
        other_id=other_id,
        plan_hash=plan_hash,
        schema_fp=schema_fp,
        logins=logins,
    )


def _login(client: TestClient, email: str, password: str) -> None:
    res = client.post("/api/accounts/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text


def _probe(client: TestClient, group: str, ctx: T6Fixtures) -> int:
    if group == "account_self":
        return client.get("/api/accounts/me").status_code
    if group == "connections_list":
        return client.get("/api/connections").status_code
    if group == "connections_mutate":
        return client.post(
            "/api/connections",
            json={
                "name": "Nope",
                "url": "http://127.0.0.1:8069",
                "db_name": "odoo_dev",
                "username": "admin",
                "password": "admin",
                "verify": False,
            },
        ).status_code
    if group == "approvals_read":
        return client.get(f"/api/connections/{ctx.granted_id}/approvals/gate").status_code
    if group == "approvals_decide":
        return client.post(
            f"/api/connections/{ctx.granted_id}/approvals/entries/probe-entry/approve",
            json={},
        ).status_code
    if group == "inbox_read":
        return client.get("/api/inbox/plans", params={"connection_id": ctx.granted_id}).status_code
    if group == "inbox_submit":
        return client.post(
            "/api/inbox/plans",
            json={
                "connection_id": ctx.granted_id,
                "requester_id": "probe",
                "goal": "Probe",
                "assumptions": [],
                "environment": "staging",
                "known_models": ["x_m"],
                "changeset": _FIELD_OP,
            },
        ).status_code
    if group == "inbox_decide":
        return client.post(
            f"/api/inbox/plans/{ctx.plan_hash}/decide",
            json={
                "connection_id": ctx.granted_id,
                "approver_id": "probe-approver",
                "decision": "approve",
                "plan_hash": ctx.plan_hash,
                "schema_fp": ctx.schema_fp,
            },
        ).status_code
    raise AssertionError(f"unknown route group {group!r}")


_MATRIX_GROUPS = tuple(g for g in ROUTE_GROUPS if g != "other_client_connection")


@pytest.mark.parametrize("role", T6_MATRIX_ROLES)
@pytest.mark.parametrize("group", _MATRIX_GROUPS)
def test_role_route_group_matrix(
    t6_ctx: T6Fixtures,
    role: str,
    group: str,
) -> None:
    allowed = role_allows_route_group(role, group)
    email, password = t6_ctx.logins[role]
    with TestClient(app) as client:
        _login(client, email, password)
        status = _probe(client, group, t6_ctx)
    if allowed:
        assert status != 403, f"{role} should pass {group}, got {status}"
    else:
        assert status == 403, f"{role} should be refused on {group}, got {status}"


@pytest.mark.parametrize("role", ("client_approver", "client_viewer"))
def test_client_grant_hides_other_connection(t6_ctx: T6Fixtures, role: str) -> None:
    email, password = t6_ctx.logins[role]
    with TestClient(app) as client:
        _login(client, email, password)
        hidden = client.get(f"/api/connections/{t6_ctx.other_id}")
        assert hidden.status_code == 404


def test_client_viewer_inbox_decide_refused(t6_ctx: T6Fixtures) -> None:
    email, password = t6_ctx.logins["client_viewer"]
    with TestClient(app) as client:
        _login(client, email, password)
        denied = client.post(
            f"/api/inbox/plans/{t6_ctx.plan_hash}/decide",
            json={
                "connection_id": t6_ctx.granted_id,
                "approver_id": "viewer",
                "decision": "approve",
                "plan_hash": t6_ctx.plan_hash,
                "schema_fp": t6_ctx.schema_fp,
            },
        )
        assert denied.status_code == 403
