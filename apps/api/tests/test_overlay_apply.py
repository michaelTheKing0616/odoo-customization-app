"""Overlay apply endpoint tests (REM-6)."""

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


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def connection_id() -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="overlay-test",
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


def test_overlay_preview_hide(client: TestClient, connection_id: str) -> None:
    res = client.post(
        f"/api/connections/{connection_id}/views/overlay/preview",
        json={
            "model": "res.partner",
            "view_type": "form",
            "operation": "hide",
            "expr": "//field[@name='email']",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "invisible" in body["xpath_arch"]
    assert body["issues"] == []


def test_overlay_apply_creates_inherit(client: TestClient, connection_id: str) -> None:
    fake_primary = MagicMock(id=10, arch='<form><field name="email"/></form>', type="form")
    fake_view = MagicMock(id=99, arch="<data/>", type="form")

    fake_client = MagicMock()
    fake_client.find_view.return_value = fake_primary
    fake_client._find_view_by_exact_name.return_value = None
    fake_client.create_inherit_view.return_value = fake_view

    with patch("app.routers.views.client_from_connection", return_value=fake_client):
        with patch("app.snapshots.snapshot_view", return_value=MagicMock(id="snap-1")):
            res = client.post(
                f"/api/connections/{connection_id}/views/overlay/apply",
                json={
                    "model": "res.partner",
                    "view_type": "form",
                    "operation": "hide",
                    "expr": "//field[@name='email']",
                    "field_name": "email",
                },
            )
    assert res.status_code == 200
    body = res.json()
    assert body["view_id"] == 99
    assert body["snapshot_id"] == "snap-1"
    assert "res.partner.overlay.form" in (body["inherit_name"] or "")
    fake_client.create_inherit_view.assert_called_once()
