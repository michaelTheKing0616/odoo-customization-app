"""TIER-2 API endpoint smoke tests."""

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


def test_automations_gate_endpoint_onprem(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="tier2-gate",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
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

    res = client.get(f"/api/connections/{cid}/automations/gate")
    assert res.status_code == 200
    body = res.json()
    assert "automations" in body
    assert body["automations"]["capability_key"] == "base_automation"


def test_validate_live_endpoint(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="tier2-validate",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
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

    spec = {
        "models": [{"model": "x_tier2_test", "fields": [{"name": "x_name", "ttype": "char"}]}],
        "views": [],
    }
    res = client.post(
        f"/api/connections/{cid}/module-spec/validate-live",
        json={"spec": spec},
    )
    assert res.status_code in (200, 502)
