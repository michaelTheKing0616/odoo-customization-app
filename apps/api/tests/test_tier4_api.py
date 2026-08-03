"""TIER-4 API endpoint tests."""

from __future__ import annotations

import os
from unittest.mock import patch

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


def test_health_check_run_queues_job(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="tier4-hc",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
            last_seen_version="18.0",
            upgrade_detected=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    with patch("app.health_check.enqueue") as mock_enqueue:
        mock_enqueue.side_effect = lambda job_id, fn: None
        res = client.post(f"/api/connections/{cid}/health-check/run?async_job=true")
    assert res.status_code == 200
    body = res.json()
    assert body["async_job"] is True
    assert body["job_id"]
    assert body["run_id"]


def test_latest_health_check_empty(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="tier4-empty",
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

    res = client.get(f"/api/connections/{cid}/health-check/latest")
    assert res.status_code == 200
    assert res.json() is None


def test_connection_includes_upgrade_fields(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="tier4-conn",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
            last_seen_version="18.0",
            upgrade_detected=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    res = client.get(f"/api/connections/{cid}")
    assert res.status_code == 200
    body = res.json()
    assert body["upgrade_detected"] is True
    assert body["last_seen_version"] == "18.0"
