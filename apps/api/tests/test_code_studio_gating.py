"""DEV-1 — Code Studio gating, validate, bind, and adversarial role tests."""

from __future__ import annotations

import base64
import io
import json
import os
import uuid
import zipfile
from unittest.mock import MagicMock, patch

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
from app.code_studio_service import (  # noqa: E402
    CodeStudioRuleError,
    bind_code_action,
    export_option_a_zip,
    test_run_code as run_code_action,
    validate_code,
)
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import AuditLog, OdooConnection  # noqa: E402
from app.entitlements import ensure_workspace_subscription, seed_plan_features  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _conn(*, probe: dict | None = None) -> OdooConnection:
    db = SessionLocal()
    try:
        _user, ws, _ = signup_user(
            db,
            email=f"dev1-{uuid.uuid4().hex[:8]}@example.com",
            password="dev1-pass-99-long",
        )
        conn = OdooConnection(
            name="code-studio",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
            write_mode="standard",
            workspace_id=ws.id,
            code_studio_probe_json=json.dumps(probe) if probe else None,
        )
        db.add(conn)
        sub = ensure_workspace_subscription(db, ws.id)
        sub.plan_id = "internal"
        sub.status = "active"
        db.commit()
        db.refresh(conn)
        return conn
    finally:
        db.close()


def test_validate_code_syntax_and_warnings() -> None:
    ok = validate_code("for rec in records:\n    rec.write({'x': 1})")
    assert ok["ok"] is True
    bad = validate_code("for rec in records\n    pass")
    assert bad["ok"] is False
    warn = validate_code("import os\nfor rec in records:\n    rec.unlink()")
    assert warn["ok"] is True
    codes = {w["code"] for w in warn["warnings"]}
    assert "imports_forbidden" in codes
    assert "unlink_pattern" in codes


@patch("app.routers.code_studio.client_from_connection")
@patch("app.code_studio_gating.client_from_connection")
def test_gate_uses_cached_probe(
    mock_gate_client,
    mock_router_client,
    client: TestClient,
) -> None:
    probe = {"supported": True, "key": "code_server_actions"}
    conn = _conn(probe=probe)
    res = client.get(f"/api/connections/{conn.id}/code-studio/gate")
    assert res.status_code == 200
    body = res.json()
    assert body["probe"]["supported"] is True
    assert body["gating"]["available"] is True
    mock_gate_client.assert_not_called()


@patch("app.code_studio_gating.probe_code_server_actions")
@patch("app.code_studio_gating.client_from_connection")
def test_failed_probe_returns_module_path_options(
    mock_client_from,
    mock_probe,
    client: TestClient,
) -> None:
    conn = _conn()
    mock_client_from.return_value = MagicMock()
    mock_probe.return_value = {
        "supported": False,
        "error": "state missing",
        "key": "code_server_actions",
    }
    res = client.get(f"/api/connections/{conn.id}/code-studio/gate")
    assert res.status_code == 200
    opts = res.json()["gating"]["options"]
    assert any("Option A" in o for o in opts)


@pytest.mark.parametrize(
    "role,expect",
    [
        ("viewer", 403),
        ("builder", 403),
        ("developer", 200),
        ("admin", 200),
    ],
)
def test_validate_requires_developer_role(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    expect: int,
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        seed_plan_features(db)
        _owner, ws, _ = signup_user(
            db,
            email=f"owner-{uuid.uuid4().hex[:6]}@example.com",
            password="owner-pass-99-long",
        )
        email = f"{role}-{uuid.uuid4().hex[:6]}@example.com"
        user = User(email=email, password_hash=hash_password("role-pass-99-long"), email_verified=True)
        db.add(user)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=role))
        conn = OdooConnection(
            name="role-matrix",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=ws.id,
            write_mode="standard",
            code_studio_probe_json=json.dumps({"supported": True}),
        )
        db.add(conn)
        sub = ensure_workspace_subscription(db, ws.id)
        sub.plan_id = "internal"
        db.commit()
        conn_id = conn.id
    finally:
        db.close()

    login = client.post("/api/accounts/login", json={"email": email, "password": "role-pass-99-long"})
    assert login.status_code == 200
    res = client.post(
        f"/api/connections/{conn_id}/code-studio/validate",
        json={"code": "x = 1"},
    )
    assert res.status_code == expect


@patch("app.routers.code_studio.bind_code_action")
@patch("app.routers.code_studio.client_from_connection")
def test_bind_sets_audit_detail_with_full_code(
    mock_client_from,
    mock_bind,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    conn = _conn(probe={"supported": True})
    mock_client_from.return_value = MagicMock()
    mock_bind.return_value = {
        "bind_kind": "standalone",
        "code": "for rec in records: pass",
        "snapshot_id": "snap-1",
        "server_action_id": 5,
    }
    before = SessionLocal().query(AuditLog).count()
    res = client.post(
        f"/api/connections/{conn.id}/code-studio/bind",
        json={
            "name": "Test",
            "model": "res.partner",
            "code": "for rec in records: pass",
            "bind_kind": "standalone",
            "confirm_advanced": True,
            "confirm_phrase": "I understand the risks",
        },
    )
    assert res.status_code == 200, res.text
    after = SessionLocal().query(AuditLog).count()
    assert after > before
    row = SessionLocal().query(AuditLog).order_by(AuditLog.created_at.desc()).first()
    assert row and row.detail_json
    detail = json.loads(row.detail_json)
    assert detail["code"] == "for rec in records: pass"
    assert detail["operation"] == "code_studio_bind"


def test_observer_mode_refuses_bind(client: TestClient) -> None:
    conn = _conn(probe={"supported": True})
    db = SessionLocal()
    try:
        row = db.get(OdooConnection, conn.id)
        row.write_mode = "observer"
        db.commit()
    finally:
        db.close()
    res = client.post(
        f"/api/connections/{conn.id}/code-studio/bind",
        json={
            "name": "Test",
            "model": "res.partner",
            "code": "x=1",
            "bind_kind": "standalone",
            "confirm_advanced": True,
            "confirm_phrase": "I understand the risks",
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "observer_mode"


def _bind_body(**overrides):
    body = {
        "name": "Test",
        "model": "res.partner",
        "code": "x = 1",
        "bind_kind": "standalone",
        "bind_to_model": False,
        "confirm_advanced": True,
        "confirm_phrase": CONFIRM_PHRASE,
    }
    body.update(overrides)
    return body


@patch("app.routers.code_studio.client_from_connection")
def test_import_refuses_bind_and_writes_no_state_code(
    mock_client_from,
    client: TestClient,
) -> None:
    conn = _conn(probe={"supported": True})
    odoo = MagicMock()
    mock_client_from.return_value = odoo
    res = client.post(
        f"/api/connections/{conn.id}/code-studio/bind",
        json=_bind_body(code="import os\nx = 1"),
    )
    assert res.status_code == 400, res.text
    detail = res.json()["detail"]
    assert detail["error"] == "imports_forbidden"
    assert "imports_forbidden" in detail["message"]
    odoo.execute_kw.assert_not_called()


@pytest.mark.parametrize(
    "code,rule",
    [
        ("for rec in records:\n    rec.sudo()", "sudo_pattern"),
        ("for rec in records:\n    rec.unlink()", "unlink_pattern"),
    ],
)
@patch("app.routers.code_studio.client_from_connection")
def test_sudo_and_unlink_refuse_bind(
    mock_client_from,
    client: TestClient,
    code: str,
    rule: str,
) -> None:
    conn = _conn(probe={"supported": True})
    odoo = MagicMock()
    mock_client_from.return_value = odoo
    res = client.post(
        f"/api/connections/{conn.id}/code-studio/bind",
        json=_bind_body(code=code),
    )
    assert res.status_code == 400, res.text
    assert res.json()["detail"]["error"] == rule
    odoo.execute_kw.assert_not_called()


@patch("app.routers.code_studio.client_from_connection")
def test_missing_confirm_phrase_refuses_bind(
    mock_client_from,
    client: TestClient,
) -> None:
    conn = _conn(probe={"supported": True})
    odoo = MagicMock()
    mock_client_from.return_value = odoo
    res = client.post(
        f"/api/connections/{conn.id}/code-studio/bind",
        json=_bind_body(confirm_advanced=False, confirm_phrase=None),
    )
    assert res.status_code == 403, res.text
    assert res.json()["detail"]["requires_confirmation"] is True
    odoo.execute_kw.assert_not_called()


@patch("app.routers.code_studio.client_from_connection")
def test_failed_probe_refuses_bind(
    mock_client_from,
    client: TestClient,
) -> None:
    conn = _conn(probe={"supported": False, "error": "probe failed"})
    res = client.post(
        f"/api/connections/{conn.id}/code-studio/bind",
        json=_bind_body(),
    )
    assert res.status_code == 409, res.text
    mock_client_from.assert_not_called()


def test_bind_saves_snapshot_before_state_code_create() -> None:
    conn = _conn(probe={"supported": True})
    odoo = MagicMock()
    created_after_snapshot = {"ok": False}

    def execute_kw(model, method, args, kwargs=None):
        if method == "search":
            return [3]
        if method == "create":
            db = SessionLocal()
            try:
                from app.db_models import MetadataSnapshot

                rows = (
                    db.query(MetadataSnapshot)
                    .filter(MetadataSnapshot.connection_id == conn.id)
                    .all()
                )
                pending = [
                    row
                    for row in rows
                    if json.loads(row.payload_json).get("pending") is True
                ]
                created_after_snapshot["ok"] = bool(pending)
            finally:
                db.close()
            assert args[0]["state"] == "code"
            return 44
        if method == "read":
            return [
                {
                    "id": 44,
                    "name": "N",
                    "state": "code",
                    "code": "x = 1",
                    "model_id": [3, "res.partner"],
                    "binding_model_id": False,
                    "binding_type": False,
                }
            ]
        return None

    odoo.execute_kw.side_effect = execute_kw
    db = SessionLocal()
    try:
        result = bind_code_action(
            db,
            odoo,
            connection_id=conn.id,
            name="N",
            model="res.partner",
            code="x = 1",
            bind_kind="standalone",
            confirm_advanced=True,
            confirm_phrase=CONFIRM_PHRASE,
            bind_to_model=False,
        )
    finally:
        db.close()
    assert created_after_snapshot["ok"] is True
    assert result["snapshot_id"]
    assert result["server_action_id"] == 44


def test_failed_test_run_refuses_bind_and_names_snapshot() -> None:
    conn = _conn(probe={"supported": True})
    odoo = MagicMock()

    def execute_kw(model, method, args, kwargs=None):
        if method == "search":
            return [1]
        if method == "create":
            return 9
        if method == "run":
            raise RuntimeError("boom")
        if method == "unlink":
            return True
        return None

    odoo.execute_kw.side_effect = execute_kw
    db = SessionLocal()
    try:
        ran = run_code_action(
            odoo,
            db=db,
            connection_id=conn.id,
            model="res.partner",
            record_id=None,
            code="x = 1",
        )
        assert ran["ok"] is False
        assert ran["snapshot_id"]
        odoo.execute_kw.reset_mock()
        with pytest.raises(CodeStudioRuleError) as caught:
            bind_code_action(
                db,
                odoo,
                connection_id=conn.id,
                name="N",
                model="res.partner",
                code="x = 1",
                bind_kind="standalone",
                confirm_advanced=True,
                confirm_phrase=CONFIRM_PHRASE,
                bind_to_model=False,
            )
    finally:
        db.close()
    assert caught.value.rule == "test_run_failed"
    assert caught.value.snapshot_id == ran["snapshot_id"]
    odoo.execute_kw.assert_not_called()


def test_missing_confirm_raises_before_odoo() -> None:
    conn = _conn(probe={"supported": True})
    odoo = MagicMock()
    db = SessionLocal()
    try:
        with pytest.raises(ConfirmationRequired):
            bind_code_action(
                db,
                odoo,
                connection_id=conn.id,
                name="N",
                model="res.partner",
                code="x = 1",
                bind_kind="standalone",
                confirm_advanced=False,
                confirm_phrase="",
                bind_to_model=False,
            )
    finally:
        db.close()
    odoo.execute_kw.assert_not_called()


@patch("app.routers.code_studio.client_from_connection")
def test_option_a_zip_is_not_installed(mock_client_from, client: TestClient) -> None:
    conn = _conn(probe={"supported": False, "error": "probe failed"})
    res = client.post(
        f"/api/connections/{conn.id}/code-studio/option-a",
        json={
            "name": "Custom action",
            "model": "res.partner",
            "code": "for rec in records:\n    pass\n",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["installed"] is False
    assert body["promoted"] is False
    assert "not installed" in body["note"]
    raw = base64.b64decode(body["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
        assert not any(name.endswith("ir.model.access.csv") for name in names)
        snippet = next(name for name in names if name.endswith("code_studio_snippet.py"))
        text = zf.read(snippet).decode()
        assert "for rec in records:" in text
        assert 'state">code' not in text
    mock_client_from.assert_not_called()
    from app.db_models import AuditChainEntry

    db = SessionLocal()
    try:
        kinds = {
            row.kind
            for row in db.query(AuditChainEntry)
            .filter(AuditChainEntry.kind == "module")
            .order_by(AuditChainEntry.ts.desc())
            .limit(5)
        }
    finally:
        db.close()
    assert "module" in kinds


def test_export_option_a_zip_has_no_install_side_effect() -> None:
    exported = export_option_a_zip(
        name="Shelf count",
        model="stock.quant",
        code="log('ready')\n",
    )
    assert exported["installed"] is False
    assert exported["promoted"] is False
    raw = base64.b64decode(exported["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        blob = "\n".join(zf.read(name).decode(errors="replace") for name in zf.namelist())
    assert "button_immediate_install" not in blob
    assert "log('ready')" in blob
