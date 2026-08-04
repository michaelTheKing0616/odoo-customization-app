"""TRUST-4 power-ops destructive pre-export tests."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

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


def test_destructive_power_ops_creates_pre_export_artifact(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="power-ops-export",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
        )
        db.add(row)
        db.commit()
        conn_id = row.id
    finally:
        db.close()

    mock_client = MagicMock()
    mock_client.model_exists.return_value = True
    mock_client.execute_kw.side_effect = [
        [{"name": "name", "ttype": "char"}],  # fields_get for export
        [{"id": 1, "name": "Row"}],  # read for export
        [1],  # search for recipe ids
        True,  # run step
    ]

    with patch("app.routers.power_ops.client_from_connection", return_value=mock_client), patch(
        "app.routers.power_ops.run_recipe",
        return_value=MagicMock(
            ok=True,
            dry_run=False,
            processed=1,
            succeeded=1,
            failed=0,
            message="ok",
            available=True,
            unavailable_reason=None,
            logs=[],
        ),
    ):
        res = client.post(
            f"/api/connections/{conn_id}/power-ops/run",
            json={
                "recipe_id": "mass_unlink",
                "model": "x_test",
                "ids": [1],
                "dry_run": False,
                "confirm_advanced": True,
                "confirm_phrase": "I understand the risks",
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("snapshot_id")
    assert body.get("artifact_url", "").endswith("/artifact.json")
