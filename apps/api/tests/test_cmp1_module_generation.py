"""CMP-1 API tests: xpath preview + module generation contracts."""

from __future__ import annotations

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
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_xpath_preview_move_and_wrap(client: TestClient) -> None:
    conn = client.post(
        "/api/connections",
        json={
            "name": f"xpath {uuid.uuid4().hex[:6]}",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo_dev",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    assert conn.status_code == 201, conn.text
    cid = conn.json()["id"]

    move = client.post(
        f"/api/connections/{cid}/views/xpath/preview",
        json={"expr": "//field[@name='x_status']", "position": "move"},
    )
    assert move.status_code == 200, move.text
    assert 'position="move"' in move.json()["arch"]
    assert move.json()["issues"] == []

    wrap = client.post(
        f"/api/connections/{cid}/views/xpath/preview",
        json={
            "expr": "//field[@name='x_name']",
            "wrapper_xml": '<div class="wrap">$0</div>',
        },
    )
    assert wrap.status_code == 200, wrap.text
    assert "$0" in wrap.json()["arch"]
