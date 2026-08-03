"""TIER-3 API endpoint tests."""

from __future__ import annotations

import base64
import os
import zipfile
from io import BytesIO

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


def test_library_export_store_ready(client: TestClient) -> None:
    res = client.post(
        "/api/apps/templates/library/export?store_ready=true",
        json={"technical_name": "library_mgmt", "display_name": "Library Management"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["store_readiness"] is not None
    assert body["store_readiness"]["fail_count"] == 0
    raw = base64.b64decode(body["content_base64"])
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        assert "library_mgmt/STORE_READINESS.json" in zf.namelist()


def test_migration_assist_online_connection(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="tier3-online",
            url="https://tenant.odoo.com",
            db_name="tenant",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    res = client.get(f"/api/connections/{cid}/migration-assist")
    assert res.status_code == 200
    body = res.json()
    assert body["eligible"] is True
    assert len(body["unlocks"]) >= 1
