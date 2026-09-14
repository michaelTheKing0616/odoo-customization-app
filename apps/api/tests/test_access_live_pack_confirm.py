"""Access live pack must not create a global ir.rule without the confirm phrase."""

from __future__ import annotations

import os
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

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.snapshots import CONFIRM_PHRASE  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _connection_id() -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="access-live-pack",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def test_apply_live_pack_requires_confirm_phrase(client: TestClient) -> None:
    cid = _connection_id()
    fake = MagicMock()
    with (
        patch("app.routers.access.client_from_connection", return_value=fake),
        patch("app.multi_company_pack.apply_multi_company_live") as apply_live,
    ):
        res = client.post(
            f"/api/connections/{cid}/access/multi-company/apply-live",
            json={"models": ["x_visitor_log"]},
        )
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["requires_confirmation"] is True
    assert detail["confirm_phrase"] == CONFIRM_PHRASE
    assert "ir.rule" in detail["warning"]
    apply_live.assert_not_called()
    fake.create_record_rule.assert_not_called()


def test_apply_live_pack_with_confirm_phrase_writes(client: TestClient) -> None:
    cid = _connection_id()
    fake = MagicMock()
    with (
        patch("app.routers.access.client_from_connection", return_value=fake),
        patch(
            "app.multi_company_pack.apply_multi_company_live",
            return_value={
                "ok": True,
                "models": ["x_visitor_log"],
                "fields_created": 1,
                "rules_created": 1,
                "warnings": [],
            },
        ) as apply_live,
    ):
        res = client.post(
            f"/api/connections/{cid}/access/multi-company/apply-live",
            json={
                "models": ["x_visitor_log"],
                "confirm_advanced": True,
                "confirm_phrase": CONFIRM_PHRASE,
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["rules_created"] == 1
    apply_live.assert_called_once()
    assert apply_live.call_args.args[1] == ["x_visitor_log"]
