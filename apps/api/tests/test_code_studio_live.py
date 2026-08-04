"""DEV-1 live integration smoke (optional — requires docker Odoo 19)."""

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

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.odoo_service import client_from_connection  # noqa: E402
from odoo_client.client import OdooClientError  # noqa: E402


def _live_client():
    from odoo_client import ConnectionConfig, OdooClient

    config = ConnectionConfig(
        url=os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
        db=os.environ.get("ODOO_DB", "odoo_dev"),
        username=os.environ.get("ODOO_USER", "admin"),
        password=os.environ.get("ODOO_PASSWORD", "admin"),
    )
    client = OdooClient(config)
    try:
        client.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 19 not reachable: {exc}")
    return client


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.mark.integration
def test_live_probe_supports_code_actions() -> None:
    from app.code_studio_probe import probe_code_server_actions

    oc = _live_client()
    result = probe_code_server_actions(oc)
    assert "supported" in result


@pytest.mark.integration
def test_live_test_run_partner_comment(client: TestClient) -> None:
    oc = _live_client()
    db = SessionLocal()
    try:
        conn = OdooConnection(
            name=f"live-cs-{uuid.uuid4().hex[:6]}",
            url=os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            db_name=os.environ.get("ODOO_DB", "odoo_dev"),
            username=os.environ.get("ODOO_USER", "admin"),
            secret_encrypted=encrypt_secret(os.environ.get("ODOO_PASSWORD", "admin")),
            server_version=str(oc.server_version().get("server_version", "19.0")),
            write_mode="standard",
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        conn_id = conn.id
    finally:
        db.close()

    partner_ids = oc.execute_kw("res.partner", "search", [[("active", "=", True)]], {"limit": 1})
    if not partner_ids:
        pytest.skip("No partner for test run")
    pid = partner_ids[0]
    code = "for rec in records:\n    rec.write({'comment': 'code-studio-live-test'})"
    res = client.post(
        f"/api/connections/{conn_id}/code-studio/test-run",
        json={"model": "res.partner", "record_id": pid, "code": code},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("ran_for_real") is True
