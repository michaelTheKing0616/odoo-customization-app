"""A4: one History merges snapshots and real (non-test) bulk runs, filters by page/record type."""

from __future__ import annotations

import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom")
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import BulkRun, MetadataSnapshot, OdooConnection  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def setup():
    init_db()
    db = SessionLocal()
    conn = OdooConnection(name="hist", url="http://127.0.0.1:8069", db_name="odoo_dev", username="admin",
                          secret_encrypted=encrypt_secret("admin"))
    db.add(conn)
    db.commit()
    cid = conn.id
    db.add_all([
        MetadataSnapshot(connection_id=cid, resource_type="access", resource_key="access:1", label="Sales can read invoices",
                         payload_json=json.dumps({"model": "account.move"}), reversible="yes"),
        MetadataSnapshot(connection_id=cid, resource_type="menu", resource_key="menu:2", label="Renamed Sales menu",
                         payload_json="{}", reversible="no"),
        BulkRun(id=str(uuid.uuid4()), connection_id=cid, operation="update_field", model="res.partner", dry_run="no",
                total=50, succeeded=48, failed=2, result_json="{}"),
        BulkRun(id=str(uuid.uuid4()), connection_id=cid, operation="update_field", model="res.partner", dry_run="yes",
                total=50, succeeded=50, failed=0, result_json="{}"),
    ])
    db.commit()
    db.close()
    with TestClient(app) as c:
        yield c, cid
    db = SessionLocal()
    db.query(MetadataSnapshot).filter_by(connection_id=cid).delete()
    db.query(BulkRun).filter_by(connection_id=cid).delete()
    db.query(OdooConnection).filter_by(id=cid).delete()
    db.commit()
    db.close()


def test_history_merges_and_filters(setup):
    c, cid = setup
    body = c.get(f"/api/connections/{cid}/history").json()
    kinds = sorted(e["kind"] for e in body["entries"])
    assert kinds == ["bulk_run", "snapshot", "snapshot"]  # test runs never appear
    bulk = next(e for e in body["entries"] if e["kind"] == "bulk_run")
    assert bulk["label"].endswith("48 of 50 updated, 2 need you")
    access = c.get(f"/api/connections/{cid}/history", params={"page": "Access"}).json()["entries"]
    assert [e["label"] for e in access] == ["Sales can read invoices"]
    assert access[0]["undo"]["snapshot_id"] and access[0]["record_type"] == "account.move"
    menu = c.get(f"/api/connections/{cid}/history", params={"resource_type": "menu"}).json()["entries"]
    assert menu[0]["undo"] is None
    assert set(body["pages"]) >= {"Access", "Menus", "Run & look after"}


def test_history_unknown_connection_404(setup):
    c, _ = setup
    assert c.get(f"/api/connections/{uuid.uuid4()}/history").status_code == 404
