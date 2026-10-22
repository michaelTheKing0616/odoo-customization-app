"""REG-NP-DEV oracle. Locked: the Worker does not edit this file.

AC1: a customer can bind a server action only after the instance probe, the
developer role, dev_tools, the confirm phrase, and a snapshot. Imports, sudo,
unlink, a missing phrase, an observer connection, a failed probe, and a
missing dev_tools entitlement refuse the bind. Option A produces a zip and
does not install it.
"""

from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import uuid
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from starlette.requests import Request

_DB_PATH = Path(tempfile.gettempdir()) / f"ingenium_reg_np_dev_{os.getpid()}.sqlite"
if _DB_PATH.exists():
    _DB_PATH.unlink()

# Disposable ingenium sqlite. Set before app import so the engine never opens
# the app Postgres (ports 5433 and 5436 are forbidden for this card).
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["FERNET_KEY"] = "dev-only-test"
os.environ["AUTH_MODE"] = "accounts"
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"
os.environ["DB_MIGRATIONS"] = "off"
os.environ["AI_ASSIST"] = "off"
os.environ["EMAIL_TRANSPORT"] = "console"
os.environ["TEST_DEFAULT_WRITE_MODE"] = "standard"
os.environ["INGENIUM_AI_CACHE_PATH"] = str(
    Path(tempfile.gettempdir()) / f"ingenium_reg_np_dev_cache_{os.getpid()}.sqlite"
)

import app.db as dbmod  # noqa: E402

_engine = create_engine(
    os.environ["DATABASE_URL"],
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)
dbmod.engine = _engine
dbmod.SessionLocal.configure(bind=_engine)

import app.safety_dependency as safety_dependency  # noqa: E402
from app.account_models import WorkspaceMembership  # noqa: E402
from app.account_service import signup_user  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.entitlements import ensure_workspace_subscription, seed_plan_features  # noqa: E402
from app.routers.code_studio import (  # noqa: E402
    BindCodeBody,
    code_studio_bind,
    code_studio_option_a,
)
from app.safety_registry import ROUTE_OVERRIDES  # noqa: E402
from app.snapshots import CONFIRM_PHRASE, save_snapshot  # noqa: E402
from app.workspace_auth import WorkspaceAuth, bind_workspace_auth  # noqa: E402

# The bind route's SafetySpec, without building the whole OpenAPI app.
_BIND_PATH = "/api/connections/{connection_id}/code-studio/bind"
_BIND_KEY = f"POST:{_BIND_PATH}"
safety_dependency._REGISTRY = {_BIND_KEY: ROUTE_OVERRIDES[_BIND_KEY]}

pytestmark = pytest.mark.no_app_db

_PASSWORD = "role-pass-99-long"
_SAFE_CODE = "x = 1"
_READ_ROW = {
    "id": 44,
    "name": "Test",
    "state": "code",
    "code": _SAFE_CODE,
    "model_id": [3, "res.partner"],
    "binding_model_id": False,
    "binding_type": False,
}


class _Route:
    def __init__(self, path: str) -> None:
        self.path = path


def _assert_disposable_db() -> None:
    url = str(dbmod.engine.url)
    assert dbmod.engine.dialect.name == "sqlite", url
    assert _DB_PATH.name.startswith("ingenium_"), _DB_PATH.name
    for port in ("5433", "5436", "8069", "8070", "8071", "8072", "8073", "8001", "11434"):
        assert port not in url, url


@pytest.fixture(scope="module", autouse=True)
def _schema():
    _assert_disposable_db()
    init_db()
    yield
    dbmod.engine.dispose()
    _DB_PATH.unlink(missing_ok=True)
    Path(os.environ["INGENIUM_AI_CACHE_PATH"]).unlink(missing_ok=True)


def _bind_fields(**overrides: object) -> dict:
    body = {
        "name": "Test",
        "model": "res.partner",
        "code": _SAFE_CODE,
        "bind_kind": "standalone",
        "bind_to_model": False,
        "confirm_advanced": True,
        "confirm_phrase": CONFIRM_PHRASE,
    }
    body.update(overrides)
    return body


def _request(connection_id: str) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": f"/api/connections/{connection_id}/code-studio/bind",
        "raw_path": b"",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 9),
        "server": ("test", 80),
        "root_path": "",
        "path_params": {"connection_id": connection_id},
        "route": _Route(_BIND_PATH),
    }
    return Request(scope)


def _auth(workspace_id: str, *, role: str, email: str) -> WorkspaceAuth:
    return WorkspaceAuth(
        mode="accounts",
        user_id=str(uuid.uuid4()),
        email=email,
        workspace_id=workspace_id,
        role=role,
    )


def _customer(db, *, plan_id: str, role: str) -> tuple[str, str, WorkspaceAuth]:
    email = f"reg-np-dev-{uuid.uuid4().hex[:8]}@example.com"
    user, workspace, _token = signup_user(db, email=email, password=_PASSWORD)
    user.email_verified = True
    membership = (
        db.query(WorkspaceMembership).filter(WorkspaceMembership.user_id == user.id).one()
    )
    membership.role = role
    seed_plan_features(db)
    subscription = ensure_workspace_subscription(db, workspace.id)
    subscription.plan_id = plan_id
    subscription.status = "active"
    db.add(user)
    db.add(membership)
    db.add(subscription)
    db.commit()
    return workspace.id, email, _auth(workspace.id, role=role, email=email)


def _connection(
    db,
    workspace_id: str,
    *,
    probe: dict | None,
    write_mode: str = "standard",
) -> str:
    row = OdooConnection(
        name="code-studio",
        url="http://127.0.0.1:9",
        db_name="ingenium_reg_np_dev",
        username="admin",
        secret_encrypted=encrypt_secret("admin"),
        server_version="19.0",
        write_mode=write_mode,
        workspace_id=workspace_id,
        code_studio_probe_json=json.dumps(probe) if probe is not None else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id


def _call_bind(db, auth: WorkspaceAuth, connection_id: str, **overrides: object):
    bind_workspace_auth(auth)
    body = BindCodeBody(**_bind_fields(**overrides))
    return code_studio_bind(connection_id, body, _request(connection_id), db, auth)


def _refuse_bind(db, auth: WorkspaceAuth, connection_id: str, **overrides: object) -> HTTPException:
    with pytest.raises(HTTPException) as caught:
        _call_bind(db, auth, connection_id, **overrides)
    return caught.value


@patch("app.routers.code_studio.client_from_connection")
def test_ac1_negative_refuses_bind_without_state_code_or_execute_kw(mock_client_from) -> None:
    """Blocked code, a missing phrase, observer mode, a failed probe, and no dev_tools."""
    assert CONFIRM_PHRASE == "I understand the risks"
    odoo = MagicMock()
    mock_client_from.return_value = odoo
    db = SessionLocal()
    try:
        workspace_id, email, auth = _customer(db, plan_id="internal", role="developer")
        connection_id = _connection(
            db,
            workspace_id,
            probe={"supported": True, "key": "code_server_actions"},
        )
        blocked = (
            ("import os\nx = 1", "imports_forbidden"),
            ("for rec in records:\n    rec.sudo()", "sudo_pattern"),
            ("for rec in records:\n    rec.unlink()", "unlink_pattern"),
        )
        for code, rule in blocked:
            odoo.execute_kw.reset_mock()
            refused = _refuse_bind(db, auth, connection_id, code=code)
            assert refused.status_code == 400
            assert refused.detail["error"] == rule
            odoo.execute_kw.assert_not_called()

        odoo.execute_kw.reset_mock()
        missing = _refuse_bind(
            db,
            auth,
            connection_id,
            confirm_advanced=True,
            confirm_phrase="not the phrase",
        )
        assert missing.status_code == 403
        assert missing.detail["requires_confirmation"] is True
        odoo.execute_kw.assert_not_called()

        failed_id = _connection(
            db,
            workspace_id,
            probe={"supported": False, "error": "probe failed"},
        )
        mock_client_from.reset_mock()
        failed = _refuse_bind(db, auth, failed_id)
        assert failed.status_code == 409
        mock_client_from.assert_not_called()
        odoo.execute_kw.assert_not_called()

        observer_id = _connection(
            db,
            workspace_id,
            probe={"supported": True, "key": "code_server_actions"},
            write_mode="observer",
        )
        with pytest.raises(HTTPException) as observer_caught:
            safety_dependency.enforce_safety_gate(_request(observer_id), db, auth)
        assert observer_caught.value.status_code == 403
        assert observer_caught.value.detail["error"] == "observer_mode"
        odoo.execute_kw.assert_not_called()

        _viewer_ws, _viewer_email, viewer = _customer(db, plan_id="internal", role="viewer")
        viewer_conn = _connection(
            db,
            _viewer_ws,
            probe={"supported": True, "key": "code_server_actions"},
        )
        viewer_refusal = _refuse_bind(db, viewer, viewer_conn)
        assert viewer_refusal.status_code == 403
        assert viewer_refusal.detail["error"] == "developer_role_required"
        odoo.execute_kw.assert_not_called()

        gated_ws, gated_email, gated = _customer(db, plan_id="free_solo", role="developer")
        gated_conn = _connection(
            db,
            gated_ws,
            probe={"supported": True, "key": "code_server_actions"},
        )
        gated_refusal = _refuse_bind(db, gated, gated_conn)
        assert gated_refusal.status_code == 403
        assert gated_refusal.detail["error"] == "feature_gated"
        assert gated_refusal.detail["feature_key"] == "dev_tools"
        odoo.execute_kw.assert_not_called()
        assert email and gated_email
    finally:
        db.close()


@patch("app.routers.code_studio.client_from_connection")
def test_ac1_positive_bind_allowed_after_gates_and_option_a_zip_not_installed(
    mock_client_from,
) -> None:
    """Probe, developer role, dev_tools, confirm phrase, and a snapshot allow bind."""
    events: list[str] = []
    odoo = MagicMock()

    def execute_kw(model, method, args, kwargs=None):
        if method == "search":
            return [3]
        if method == "create":
            events.append(f"create:{args[0].get('state')}")
            return 44
        if method == "read":
            return [_READ_ROW]
        return None

    odoo.execute_kw.side_effect = execute_kw
    mock_client_from.return_value = odoo
    db = SessionLocal()
    try:
        workspace_id, _email, auth = _customer(db, plan_id="internal", role="developer")
        connection_id = _connection(
            db,
            workspace_id,
            probe={"supported": True, "key": "code_server_actions"},
        )
        safety_dependency.enforce_safety_gate(_request(connection_id), db, auth)

        def _save(*args, **kwargs):
            pending = (kwargs.get("payload") or {}).get("pending")
            events.append("snapshot" if pending is True else "snapshot-other")
            return save_snapshot(*args, **kwargs)

        with patch("app.code_studio_service.save_snapshot", side_effect=_save):
            bound = _call_bind(db, auth, connection_id)

        assert bound.server_action_id == 44
        assert bound.snapshot_id
        assert events.index("snapshot") < events.index("create:code")

        mock_client_from.reset_mock()
        odoo.execute_kw.reset_mock()
        from app.routers.code_studio import OptionABody

        exported = code_studio_option_a(
            connection_id,
            OptionABody(
                name="Custom action",
                model="res.partner",
                code="for rec in records:\n    pass\n",
            ),
            _request(connection_id),
            db,
            auth,
        )
        assert exported.installed is False
        assert exported.promoted is False
        assert "not installed" in exported.note
        raw = base64.b64decode(exported.content_base64)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            snippet = next(
                name for name in archive.namelist() if name.endswith("code_studio_snippet.py")
            )
            text = archive.read(snippet).decode()
        assert "for rec in records:" in text
        mock_client_from.assert_not_called()
        odoo.execute_kw.assert_not_called()
        _screen_states_both_limits()
    finally:
        db.close()


def _screen_states_both_limits() -> None:
    """The Code Studio screen states the live-bind limit and the Option A limit."""
    root = Path(__file__).resolve().parents[3]
    screen = (root / "apps/web/src/components/code-studio/CodeStudioScreen.tsx").read_text(
        encoding="utf-8"
    )
    honesty = (root / "apps/web/src/components/code-studio/CodeStudioHonesty.tsx").read_text(
        encoding="utf-8"
    )
    assert "<CodeStudioHonesty />" in screen
    assert 'data-testid="code-studio-limit-live"' in honesty
    assert "Import" in honesty and "sudo" in honesty and "unlink are refused" in honesty
    assert 'data-testid="code-studio-limit-option-a"' in honesty
    assert "does not install" in honesty
