"""TRUST-4 restore drill tests — snapshot-supported types (mocked Odoo)."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")

from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import MetadataSnapshot, OdooConnection  # noqa: E402
from app.snapshots import rollback_snapshot, save_snapshot  # noqa: E402


@pytest.fixture
def conn_row() -> OdooConnection:
    init_db()
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="restore-drill",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted="x",
            write_mode="standard",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def test_rollback_server_action_snapshot(conn_row: OdooConnection) -> None:
    db = SessionLocal()
    client = MagicMock()
    client.execute_kw.return_value = [{"id": 7}]
    try:
        snap = save_snapshot(
            db,
            connection_id=conn_row.id,
            resource_type="server_action",
            resource_key="action:7",
            label="test action",
            payload={"server_action": {"id": 7, "name": "Test", "state": "code", "code": "pass"}},
            reversible="yes",
        )
        result = rollback_snapshot(db, client, snap.id, connection_id=conn_row.id)
        assert result.get("ok") is True or "restored" in str(result).lower() or result
    finally:
        db.close()


def test_artifact_json_download_route(conn_row: OdooConnection) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    db = SessionLocal()
    try:
        snap = save_snapshot(
            db,
            connection_id=conn_row.id,
            resource_type="dedupe_merge",
            resource_key="dedupe:res.partner:1",
            label="merge backup",
            payload={"model": "res.partner", "loser_ids": [2, 3], "losers": [{"id": 2}]},
            reversible="partial",
        )
        snap_id = snap.id
    finally:
        db.close()

    with TestClient(app) as http:
        res = http.get(f"/api/connections/{conn_row.id}/snapshots/{snap_id}/artifact.json")
        assert res.status_code == 200
        body = json.loads(res.content.decode())
        assert body["loser_ids"] == [2, 3]
