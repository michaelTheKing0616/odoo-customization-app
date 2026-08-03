"""Unit tests for health sweep logic (TIER-4)."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

import pytest
from odoo_client.client import OdooClientError

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import MetadataSnapshot, OdooConnection  # noqa: E402
from app.health_check import _check_view, deep_link_for, run_health_sweep  # noqa: E402


@pytest.fixture(autouse=True)
def _db_ready() -> None:
    init_db()


def test_deep_link_for_view_includes_model() -> None:
    link = deep_link_for(
        "conn-1",
        "view",
        "view:42",
        payload={"view": {"model": "res.partner"}},
    )
    assert link == "/connections/conn-1/designer?model=res.partner"


def test_broken_view_detected() -> None:
    client = MagicMock()
    client.execute_kw.side_effect = OdooClientError("View not found")

    row = MetadataSnapshot(
        connection_id="c1",
        resource_type="view",
        resource_key="view:999",
        label="Broken view",
        payload_json=json.dumps({"view": {"model": "res.partner", "type": "form"}}),
        reversible="yes",
    )

    item = _check_view(client, "conn-abc", row, json.loads(row.payload_json))
    assert item.status == "broken"
    assert "999" in item.reason
    assert item.deep_link == "/connections/conn-abc/designer?model=res.partner"


def test_health_sweep_counts_ok_and_broken() -> None:
    db = SessionLocal()
    try:
        conn = OdooConnection(
            name="hc-sweep",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
            last_seen_version="19.0",
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)

        good = MetadataSnapshot(
            connection_id=conn.id,
            resource_type="model",
            resource_key="model:res.partner",
            label="Partner model",
            payload_json="{}",
            reversible="yes",
        )
        bad = MetadataSnapshot(
            connection_id=conn.id,
            resource_type="view",
            resource_key="view:404",
            label="Missing view",
            payload_json=json.dumps({"view": {"model": "res.partner", "type": "form"}}),
            reversible="yes",
        )
        db.add_all([good, bad])
        db.commit()

        client = MagicMock()

        def _execute_kw(model: str, method: str, args, kwargs=None):
            kwargs = kwargs or {}
            if model == "ir.ui.view" and method == "read":
                raise OdooClientError("missing")
            if model == "res.partner" and method == "model_exists":
                return True
            raise OdooClientError(f"unexpected {model}.{method}")

        client.execute_kw.side_effect = _execute_kw
        client.model_exists.return_value = True

        report = run_health_sweep(
            db,
            connection_id=conn.id,
            client=client,
            trigger="manual",
            current_version="19.0",
        )

        assert report.broken_count >= 1
        assert report.ok_count >= 1
        broken = [i for i in report.items if i.status == "broken"]
        assert any(i.resource_key == "view:404" for i in broken)
    finally:
        db.close()
