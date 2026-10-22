"""T6-03 — typed auth events on the one hash chain."""

from __future__ import annotations

import json
import os
import uuid

import pyotp
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
from app.account_service import (  # noqa: E402
    AccountError,
    change_membership_role,
    disable_totp,
    enroll_totp,
    grant_connection_access,
    hash_password,
    revoke_connection_access,
    signup_user,
)
from app.audit_chain import verify_db  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import Base, SessionLocal, init_db  # noqa: E402
from app.db_models import AuditChainEntry, OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


def _email(local: str) -> str:
    return f"{local}-{uuid.uuid4().hex[:8]}@example.com"


def _ids(kind: str) -> set[str]:
    db = SessionLocal()
    try:
        return {
            row.id
            for row in db.query(AuditChainEntry).filter(AuditChainEntry.kind == kind).all()
        }
    finally:
        db.close()


def _new_rows(kind: str, before: set[str]) -> list[AuditChainEntry]:
    db = SessionLocal()
    try:
        return (
            db.query(AuditChainEntry)
            .filter(AuditChainEntry.kind == kind, AuditChainEntry.id.notin_(before or {"_"}))
            .order_by(AuditChainEntry.ts.asc(), AuditChainEntry.id.asc())
            .all()
        )
    finally:
        db.close()


def _payload(row: AuditChainEntry) -> dict:
    return json.loads(row.payload_json)


def _signup_verified(email: str, password: str, workspace_name: str = "Audit WS"):
    db = SessionLocal()
    try:
        user, workspace, _ = signup_user(db, email=email, password=password, workspace_name=workspace_name)
        user.email_verified = True
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id, workspace.id
    finally:
        db.close()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    with TestClient(app) as c:
        yield c


def test_login_success_writes_one_typed_row(client: TestClient) -> None:
    email = _email("login-ok")
    password = "secure-pass-99"
    user_id, _ = _signup_verified(email, password)
    before = _ids("login")
    res = client.post("/api/accounts/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    rows = _new_rows("login", before)
    assert len(rows) == 1
    payload = _payload(rows[0])
    assert payload["actor"] == user_id
    assert payload["target_user"] == user_id
    assert payload["provider"] == "password"
    assert payload["result"] == "success"
    assert password not in rows[0].payload_json


def test_failed_login_writes_row_without_password(client: TestClient) -> None:
    email = _email("login-fail")
    password = "secure-pass-99"
    attempted = "wrong-password-should-never-be-logged"
    user_id, _ = _signup_verified(email, password)
    before = _ids("login")
    res = client.post("/api/accounts/login", json={"email": email, "password": attempted})
    assert res.status_code == 401
    rows = _new_rows("login", before)
    assert len(rows) == 1
    payload = _payload(rows[0])
    assert payload["actor"] == user_id
    assert payload["target_user"] == user_id
    assert payload["provider"] == "password"
    assert payload["result"] == "failure"
    assert "password" not in payload
    assert attempted not in rows[0].payload_json
    assert attempted not in json.dumps(payload)


def test_logout_success_and_failure_each_one_row(client: TestClient) -> None:
    email = _email("logout")
    password = "secure-pass-99"
    user_id, _ = _signup_verified(email, password)
    login = client.post("/api/accounts/login", json={"email": email, "password": password})
    assert login.status_code == 200
    before = _ids("logout")
    ok = client.post("/api/accounts/logout")
    assert ok.status_code == 204
    success_rows = _new_rows("logout", before)
    assert len(success_rows) == 1
    payload = _payload(success_rows[0])
    assert payload["actor"] == user_id
    assert payload["target_user"] == user_id
    assert payload["result"] == "success"
    after_success = _ids("logout")
    missing = client.post("/api/accounts/logout")
    assert missing.status_code == 204
    fail_rows = _new_rows("logout", after_success)
    assert len(fail_rows) == 1
    assert _payload(fail_rows[0])["result"] == "failure"


def test_grant_create_and_revoke_each_one_typed_row(client: TestClient) -> None:
    owner_email = _email("grant-owner")
    owner_password = "owner-pass-99"
    owner_id, workspace_id = _signup_verified(owner_email, owner_password, "Grant WS")
    grantee_email = _email("grantee")
    db = SessionLocal()
    try:
        grantee = User(
            email=grantee_email,
            password_hash=hash_password("grantee-pass-99"),
            email_verified=True,
        )
        db.add(grantee)
        conn = OdooConnection(
            name="Grant conn",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace_id,
        )
        db.add(conn)
        db.commit()
        grantee_id = grantee.id
        connection_id = conn.id
    finally:
        db.close()

    login = client.post("/api/accounts/login", json={"email": owner_email, "password": owner_password})
    assert login.status_code == 200

    before_grant = _ids("grant")
    created = client.post(
        "/api/accounts/connection-grants",
        json={"connection_id": connection_id, "email": grantee_email, "role": "client_approver"},
    )
    assert created.status_code == 201, created.text
    grant_id = created.json()["id"]
    grant_rows = _new_rows("grant", before_grant)
    assert len(grant_rows) == 1
    grant_payload = _payload(grant_rows[0])
    assert grant_payload["actor"] == owner_id
    assert grant_payload["target_user"] == grantee_id
    assert grant_payload["result"] == "success"

    before_fail = _ids("grant")
    missing = client.post(
        "/api/accounts/connection-grants",
        json={"connection_id": connection_id, "email": _email("nobody"), "role": "client_approver"},
    )
    assert missing.status_code == 404
    fail_rows = _new_rows("grant", before_fail)
    assert len(fail_rows) == 1
    assert _payload(fail_rows[0])["result"] == "failure"

    before_revoke = _ids("revoke")
    revoked = client.delete(f"/api/accounts/connection-grants/{grant_id}")
    assert revoked.status_code == 204
    revoke_rows = _new_rows("revoke", before_revoke)
    assert len(revoke_rows) == 1
    revoke_payload = _payload(revoke_rows[0])
    assert revoke_payload["actor"] == owner_id
    assert revoke_payload["target_user"] == grantee_id
    assert revoke_payload["result"] == "success"

    before_revoke_fail = _ids("revoke")
    again = client.delete(f"/api/accounts/connection-grants/{grant_id}")
    assert again.status_code == 404
    revoke_fail = _new_rows("revoke", before_revoke_fail)
    assert len(revoke_fail) == 1
    assert _payload(revoke_fail[0])["result"] == "failure"


def test_totp_enroll_and_disable_each_one_row(client: TestClient) -> None:
    email = _email("totp-audit")
    password = "secure-pass-99"
    user_id, _ = _signup_verified(email, password)
    login = client.post("/api/accounts/login", json={"email": email, "password": password})
    assert login.status_code == 200

    before_enroll = _ids("totp")
    enroll = client.post("/api/accounts/totp/enroll")
    assert enroll.status_code == 200, enroll.text
    secret = enroll.json()["secret"]
    assert secret
    enroll_rows = _new_rows("totp", before_enroll)
    assert len(enroll_rows) == 1
    enroll_payload = _payload(enroll_rows[0])
    assert enroll_payload["actor"] == user_id
    assert enroll_payload["target_user"] == user_id
    assert enroll_payload["provider"] == "totp"
    assert enroll_payload["result"] == "success"
    assert enroll_payload["action"] == "enroll"
    assert secret not in enroll_rows[0].payload_json
    assert "secret" not in enroll_payload

    verify = client.post("/api/accounts/totp/verify", json={"code": pyotp.TOTP(secret).now()})
    assert verify.status_code == 200, verify.text
    recovery_codes = verify.json()["recovery_codes"]
    assert len(_new_rows("totp", before_enroll)) == 1

    before_disable = _ids("totp")
    disabled = client.post("/api/accounts/totp/disable")
    assert disabled.status_code == 204
    disable_rows = _new_rows("totp", before_disable)
    assert len(disable_rows) == 1
    disable_payload = _payload(disable_rows[0])
    assert disable_payload["result"] == "success"
    assert disable_payload["action"] == "disable"
    assert secret not in disable_rows[0].payload_json
    for code in recovery_codes:
        assert code not in disable_rows[0].payload_json

    before_disable_fail = _ids("totp")
    again = client.post("/api/accounts/totp/disable")
    assert again.status_code == 400
    fail_rows = _new_rows("totp", before_disable_fail)
    assert len(fail_rows) == 1
    assert _payload(fail_rows[0])["result"] == "failure"


def test_role_change_success_and_failure_each_one_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    owner_email = _email("role-owner")
    db = SessionLocal()
    try:
        owner, workspace, _ = signup_user(db, email=owner_email, password="owner-pass-99")
        owner.email_verified = True
        member = User(
            email=_email("role-member"),
            password_hash=hash_password("member-pass-99"),
            email_verified=True,
        )
        db.add(owner)
        db.add(member)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=member.id, role="viewer"))
        db.commit()
        member_id = member.id
        workspace_id = workspace.id
        owner_id = owner.id
    finally:
        db.close()

    before = _ids("grant")
    db = SessionLocal()
    try:
        change_membership_role(
            db,
            workspace_id=workspace_id,
            target_user_id=member_id,
            role="builder",
            actor_user_id=owner_id,
        )
    finally:
        db.close()
    rows = _new_rows("grant", before)
    assert len(rows) == 1
    payload = _payload(rows[0])
    assert payload["actor"] == owner_id
    assert payload["target_user"] == member_id
    assert payload["result"] == "success"
    assert payload["action"] == "role_change"

    before_fail = _ids("grant")
    db = SessionLocal()
    try:
        with pytest.raises(AccountError):
            change_membership_role(
                db,
                workspace_id=workspace_id,
                target_user_id=member_id,
                role="not-a-role",
                actor_user_id=owner_id,
            )
    finally:
        db.close()
    fail_rows = _new_rows("grant", before_fail)
    assert len(fail_rows) == 1
    assert _payload(fail_rows[0])["result"] == "failure"
    assert _payload(fail_rows[0])["action"] == "role_change"


def test_verify_db_stays_green_after_auth_events(client: TestClient) -> None:
    email = _email("verify-chain")
    password = "secure-pass-99"
    _signup_verified(email, password)
    client.post("/api/accounts/login", json={"email": email, "password": password})
    client.post("/api/accounts/logout")
    client.post("/api/accounts/login", json={"email": email, "password": "wrong-pass-99"})
    db = SessionLocal()
    try:
        ok, bad = verify_db(db)
        assert ok is True
        assert bad is None
    finally:
        db.close()


def test_no_second_auth_audit_table() -> None:
    names = set(Base.metadata.tables)
    assert "audit_chain_entries" in names
    chain_tables = sorted(name for name in names if "audit_chain" in name)
    assert chain_tables == ["audit_chain_entries"]
    assert "auth_events" not in names
    assert "auth_audit" not in names
    assert "auth_log" not in names


def test_oauth_link_failure_writes_one_login_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    from app.oauth_service import OAuthProfile, resolve_oauth_login

    email = _email("oauth-fail")
    db = SessionLocal()
    try:
        user, _, _ = signup_user(db, email=email, password="secure-pass-99")
        user.email_verified = True
        db.add(user)
        db.commit()
    finally:
        db.close()
    before = _ids("login")
    db = SessionLocal()
    try:
        with pytest.raises(AccountError):
            resolve_oauth_login(
                db,
                OAuthProfile(
                    provider="google",
                    subject=f"google-sub-{uuid.uuid4().hex[:8]}",
                    email=email,
                    email_verified=False,
                ),
            )
    finally:
        db.close()
    rows = _new_rows("login", before)
    assert len(rows) == 1
    payload = _payload(rows[0])
    assert payload["provider"] == "google"
    assert payload["result"] == "failure"


def test_service_enroll_failure_writes_one_totp_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    before = _ids("totp")
    db = SessionLocal()
    try:
        with pytest.raises(AccountError):
            enroll_totp(db, None, actor_user_id="anonymous")
    finally:
        db.close()
    rows = _new_rows("totp", before)
    assert len(rows) == 1
    assert _payload(rows[0])["result"] == "failure"
    assert _payload(rows[0])["action"] == "enroll"


def test_service_revoke_and_grant_helpers_write_one_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        owner, workspace, _ = signup_user(db, email=_email("svc-owner"), password="owner-pass-99")
        grantee = User(
            email=_email("svc-grantee"),
            password_hash=hash_password("grantee-pass-99"),
            email_verified=True,
        )
        db.add(grantee)
        conn = OdooConnection(
            name="Svc conn",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        db.add(conn)
        db.commit()
        before_grant = _ids("grant")
        grant = grant_connection_access(
            db,
            workspace_id=workspace.id,
            connection_id=conn.id,
            user_id=grantee.id,
            role="client_viewer",
            actor_user_id=owner.id,
        )
        grant_rows = _new_rows("grant", before_grant)
        assert len(grant_rows) == 1
        before_revoke = _ids("revoke")
        revoke_connection_access(
            db,
            workspace_id=workspace.id,
            grant_id=grant.id,
            actor_user_id=owner.id,
        )
        revoke_rows = _new_rows("revoke", before_revoke)
        assert len(revoke_rows) == 1
        with pytest.raises(AccountError):
            disable_totp(db, owner, actor_user_id=owner.id)
    finally:
        db.close()
