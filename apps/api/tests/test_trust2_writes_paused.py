"""TRUST-2 writes_paused kill switch API tests."""

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

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.account_models import Workspace  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    from app.account_service import ensure_default_workspace_for_legacy_rows
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        ensure_default_workspace_for_legacy_rows(db)
        ws = db.query(Workspace).first()
        if ws is not None and ws.writes_paused:
            ws.writes_paused = False
            db.add(ws)
            db.commit()
    finally:
        db.close()
    with TestClient(app) as c:
        yield c


def test_connection_writes_paused_blocks_mutating_route(client: TestClient) -> None:
    init_db()
    create = client.post(
        "/api/connections",
        json={
            "name": "Paused conn",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    assert create.status_code == 201, create.text
    conn_id = create.json()["id"]
    unlock = client.patch(
        f"/api/connections/{conn_id}/write-mode",
        json={"write_mode": "standard"},
    )
    assert unlock.status_code == 200
    pause = client.patch(
        f"/api/connections/{conn_id}/writes-paused",
        json={"writes_paused": True},
    )
    assert pause.status_code == 200, pause.text
    assert pause.json()["writes_paused"] is True

    resp = client.patch(
        f"/api/connections/{conn_id}",
        json={"name": "Renamed"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "writes_paused"


def test_workspace_writes_paused_blocks_connection_create(client: TestClient) -> None:
    init_db()
    from app.account_service import ensure_default_workspace_for_legacy_rows
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        ensure_default_workspace_for_legacy_rows(db)
    finally:
        db.close()

    pause = client.patch(
        "/api/workspaces/writes-paused",
        json={"writes_paused": True},
    )
    assert pause.status_code == 200, pause.text

    resp = client.post(
        "/api/connections",
        json={
            "name": "Blocked",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "writes_paused"

    client.patch("/api/workspaces/writes-paused", json={"writes_paused": False})
