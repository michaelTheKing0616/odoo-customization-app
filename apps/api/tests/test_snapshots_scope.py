"""Unit tests for snapshot connection scoping and cascade delete helpers."""

from __future__ import annotations

import json
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
from app.db_models import MetadataSnapshot, OdooConnection  # noqa: E402
from app.main import app  # noqa: E402
from app.snapshots import rollback_snapshot  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _mk_connection(name: str = "c1") -> OdooConnection:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name=name,
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def test_rollback_rejects_wrong_connection() -> None:
    init_db()
    a = _mk_connection("snap-a")
    b = _mk_connection("snap-b")
    db = SessionLocal()
    try:
        snap = MetadataSnapshot(
            connection_id=a.id,
            resource_type="view",
            resource_key="view:1",
            label="test",
            payload_json=json.dumps({"view": {"id": 1, "arch": "<form/>"}}),
            reversible="yes",
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        snap_id = snap.id
    finally:
        db.close()

    class DummyClient:
        pass

    db = SessionLocal()
    try:
        with pytest.raises(LookupError, match="this connection"):
            rollback_snapshot(db, DummyClient(), snap_id, connection_id=b.id)  # type: ignore[arg-type]
    finally:
        db.close()


def test_health_reports_database(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert "database_ok" in body
    assert body["odoo_target_version"] == "19"


def test_delete_connection_cascades_snapshots(client: TestClient) -> None:
    conn = _mk_connection("cascade")
    db = SessionLocal()
    try:
        db.add(
            MetadataSnapshot(
                connection_id=conn.id,
                resource_type="view",
                resource_key="view:9",
                label="x",
                payload_json="{}",
                reversible="yes",
            )
        )
        db.commit()
    finally:
        db.close()

    res = client.delete(f"/api/connections/{conn.id}")
    assert res.status_code == 204

    db = SessionLocal()
    try:
        left = (
            db.query(MetadataSnapshot)
            .filter(MetadataSnapshot.connection_id == conn.id)
            .count()
        )
        assert left == 0
        assert db.get(OdooConnection, conn.id) is None
    finally:
        db.close()
