"""CMP-2 preview arch emits major-aware field modifiers."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _conn_id(server_version: str) -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name=f"cmp2-{server_version}",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version=server_version,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _preview(client: TestClient, cid: str) -> str:
    res = client.post(
        f"/api/connections/{cid}/views/preview",
        json={
            "view_type": "form",
            "spec": {
                "string": "T",
                "children": [
                    {
                        "kind": "group",
                        "children": [
                            {
                                "kind": "field",
                                "name": "x_status",
                                "invisible": "[('active', '=', False)]",
                            }
                        ],
                    }
                ],
            },
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["arch"]


def test_preview_attrs_modern_on_odoo19(client: TestClient) -> None:
    arch = _preview(client, _conn_id("19.0"))
    assert "invisible=" in arch
    assert "attrs=" not in arch


def test_preview_attrs_legacy_on_odoo16(client: TestClient) -> None:
    arch = _preview(client, _conn_id("16.0"))
    assert "attrs=" in arch
