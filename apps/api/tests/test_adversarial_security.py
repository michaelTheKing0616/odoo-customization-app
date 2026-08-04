"""Adversarial / security regression tests (no live Odoo required)."""

from __future__ import annotations

import base64
import io
import json
import os
import zipfile

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.client_ip import client_ip  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import MetadataSnapshot, OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import settings  # noqa: E402
from app.snapshots import CONFIRM_PHRASE  # noqa: E402
from app.zip_safety import MAX_ZIP_BYTES  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _mk_connection(name: str = "adv") -> OdooConnection:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name=name,
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def _slip_zip_b64() -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.txt", "nope")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _oversized_b64() -> str:
    # Not a valid zip — size guard runs before ZipFile parse.
    raw = b"PK" + b"x" * (MAX_ZIP_BYTES + 1)
    return base64.b64encode(raw).decode("ascii")


def test_health_reports_database_ok(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["database_ok"] is True
    assert body["status"] == "ok"


def test_rollback_wrong_connection_http_404(client: TestClient) -> None:
    a = _mk_connection("snap-owner")
    b = _mk_connection("snap-other")
    db = SessionLocal()
    try:
        snap = MetadataSnapshot(
            connection_id=a.id,
            resource_type="view",
            resource_key="view:1",
            label="test",
            payload_json=json.dumps({"view": {"id": 1, "arch": "<form/>"}}),
            reversible="yes",
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        snap_id = snap.id
    finally:
        db.close()

    # Must 404 without contacting Odoo (ownership checked first).
    res = client.post(f"/api/connections/{b.id}/snapshots/{snap_id}/rollback")
    assert res.status_code == 404
    assert "connection" in res.json()["detail"].lower() or "not found" in res.json()["detail"].lower()


def test_zip_slip_and_oversized_via_sandbox_endpoint(client: TestClient) -> None:
    conn = _mk_connection("zip-adv")
    slip = client.post(
        f"/api/connections/{conn.id}/sandbox/run",
        json={"zip_base64": _slip_zip_b64(), "keep_alive": False},
    )
    assert slip.status_code == 400, slip.text
    assert "slip" in slip.json()["detail"].lower() or "traversal" in slip.json()["detail"].lower()

    huge = client.post(
        f"/api/connections/{conn.id}/sandbox/run",
        json={"zip_base64": _oversized_b64(), "keep_alive": False},
    )
    assert huge.status_code == 413, huge.text
    assert "too large" in huge.json()["detail"].lower()

    missing = client.post(
        "/api/connections/00000000-0000-0000-0000-000000000000/sandbox/run",
        json={"zip_base64": _slip_zip_b64()},
    )
    assert missing.status_code == 404


def test_confirm_gates_without_phrase_unit(client: TestClient) -> None:
    """Confirm runs before Odoo — 403 even when connection exists."""
    conn = _mk_connection("confirm-adv")
    cid = conn.id

    for path in (
        f"/api/connections/{cid}/fields/1",
        f"/api/connections/{cid}/models/x_thing",
        f"/api/connections/{cid}/automations/1",
        f"/api/connections/{cid}/access/rights/1",
        f"/api/connections/{cid}/access/rules/1",
    ):
        denied = client.request("DELETE", path, json={})
        assert denied.status_code == 403, f"{path} → {denied.status_code} {denied.text}"
        detail = denied.json()["detail"]
        assert detail["requires_confirmation"] is True
        assert detail["confirm_phrase"] == CONFIRM_PHRASE

    promote = client.post(
        f"/api/connections/{cid}/modules/promote",
        json={"technical_name": "x", "display_name": "X", "validation_id": "nope"},
    )
    assert promote.status_code == 403
    assert promote.json()["detail"]["requires_confirmation"] is True

    uninstall = client.post(
        f"/api/connections/{cid}/modules/uninstall",
        json={"module_name": "x_mod"},
    )
    assert uninstall.status_code == 403


def test_create_record_requires_target_model(client: TestClient) -> None:
    conn = _mk_connection("create-rec")
    res = client.post(
        f"/api/connections/{conn.id}/automations",
        json={
            "name": "Spawn",
            "model": "res.partner",
            "trigger": "on_create",
            "action_kind": "create_record",
            # missing target_model
        },
    )
    assert res.status_code == 422
    assert "target_model" in res.json()["detail"]


def test_code_live_without_confirm_403(client: TestClient) -> None:
    conn = _mk_connection("code-live")
    res = client.post(
        f"/api/connections/{conn.id}/automations",
        json={
            "name": "Live",
            "model": "res.partner",
            "trigger": "on_create",
            "action_kind": "code_live",
            "python_code": "record.write({})",
            "confirm_advanced": False,
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"]["requires_confirmation"] is True


@pytest.mark.parametrize(
    "action_kind,extra",
    [
        ("webhook", {"webhook_url": "https://example.com/hook"}),
        ("sms", {"sms_body": "Hello"}),
        ("followers", {"partner_ids": [1]}),
        ("remove_followers", {"partner_ids": [1]}),
    ],
)
def test_advanced_automation_actions_require_confirm(
    client: TestClient, action_kind: str, extra: dict
) -> None:
    conn = _mk_connection(f"adv-{action_kind}")
    denied = client.post(
        f"/api/connections/{conn.id}/automations",
        json={
            "name": f"Adv {action_kind}",
            "model": "res.partner",
            "trigger": "on_create",
            "action_kind": action_kind,
            **extra,
        },
    )
    assert denied.status_code == 403, denied.text
    detail = denied.json()["detail"]
    assert detail["requires_confirmation"] is True
    assert detail["confirm_phrase"] == CONFIRM_PHRASE

    wrong_phrase = client.post(
        f"/api/connections/{conn.id}/automations",
        json={
            "name": f"Adv {action_kind}",
            "model": "res.partner",
            "trigger": "on_create",
            "action_kind": action_kind,
            "confirm_advanced": True,
            "confirm_phrase": "wrong",
            **extra,
        },
    )
    assert wrong_phrase.status_code == 403


def test_auth_mode_api_key_blocks_connections(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "api_key")
    monkeypatch.setattr(settings, "app_api_key", "oc_adversarial_secret_key")
    denied = client.get("/api/connections")
    assert denied.status_code == 401


def test_xff_ignored_when_trusted_proxy_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy", False)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"203.0.113.9")],
        "client": ("10.0.0.5", 12345),
        "server": ("127.0.0.1", 80),
    }
    req = Request(scope)
    assert client_ip(req) == "10.0.0.5"

    monkeypatch.setattr(settings, "trusted_proxy", True)
    assert client_ip(req) == "203.0.113.9"


def test_create_field_body_related_currency_schema() -> None:
    from app.schemas import CreateFieldBody

    related = CreateFieldBody(
        model="x_thing",
        name="x_partner_name",
        field_description="Partner",
        ttype="char",
        related="partner_id.name",
    )
    assert related.related == "partner_id.name"
    assert related.inject_strategy == "inherit"

    monetary = CreateFieldBody(
        model="x_thing",
        name="x_amount",
        field_description="Amount",
        ttype="monetary",
        currency_field="currency_id",
    )
    assert monetary.currency_field == "currency_id"

    mutate = CreateFieldBody(
        model="x_thing",
        name="x_note",
        field_description="Note",
        ttype="char",
        inject_strategy="mutate",
        confirm_advanced=True,
        confirm_phrase="I understand the risks",
    )
    assert mutate.inject_strategy == "mutate"
