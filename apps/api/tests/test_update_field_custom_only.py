"""PATCH /fields/{id} refuses stock (non-custom) fields."""

from __future__ import annotations

import os
import uuid
from types import SimpleNamespace
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


def _conn() -> OdooConnection:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name=f"field-guard-{uuid.uuid4().hex[:8]}",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
            write_mode="standard",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def test_patch_field_refuses_stock_non_custom(client: TestClient) -> None:
    row = _conn()
    fake = MagicMock()
    fake.get_field.return_value = SimpleNamespace(
        id=42, name="name", state="base", field_description="Name", ttype="char"
    )

    with patch("app.routers.builder.client_from_connection", return_value=fake):
        res = client.patch(
            f"/api/connections/{row.id}/fields/42",
            json={"help": "should not apply"},
        )
    assert res.status_code == 403, res.text
    detail = res.json()["detail"]
    assert "Only custom fields can be edited" in detail
    assert "built-in" in detail
    fake.update_field.assert_not_called()


def test_patch_field_allows_manual_custom(client: TestClient) -> None:
    row = _conn()
    fake = MagicMock()
    fake.get_field.return_value = SimpleNamespace(
        id=7, name="x_note", state="manual", field_description="Note", ttype="char"
    )
    updated = SimpleNamespace(
        id=7,
        name="x_note",
        field_description="Note",
        ttype="char",
        required=False,
        readonly=False,
        relation=None,
        state="manual",
        help="ok",
        selection=None,
        related=None,
        currency_field=None,
        relation_field=None,
        tracking=False,
    )
    updated.model_dump = lambda: {
        "id": 7,
        "name": "x_note",
        "field_description": "Note",
        "ttype": "char",
        "required": False,
        "readonly": False,
        "relation": None,
        "state": "manual",
        "help": "ok",
        "selection": None,
        "related": None,
        "currency_field": None,
        "relation_field": None,
        "tracking": False,
    }
    fake.update_field.return_value = updated

    with patch("app.routers.builder.client_from_connection", return_value=fake):
        res = client.patch(
            f"/api/connections/{row.id}/fields/7",
            json={"help": "ok"},
        )
    assert res.status_code == 200, res.text
    fake.update_field.assert_called_once()
