"""TRUST-2 dry-run receipts on bulk execute endpoints (beyond transitions/run)."""

from __future__ import annotations

import os
import uuid
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

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.bulk_suite.mass_edit import MassEditResult  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def test_mass_edit_requires_dry_run_receipt(client: TestClient) -> None:
    create = client.post(
        "/api/connections",
        json={
            "name": "Receipt bulk",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    assert create.status_code == 201, create.text
    conn_id = create.json()["id"]
    client.patch(
        f"/api/connections/{conn_id}/write-mode",
        json={"write_mode": "standard"},
    )

    from app.db import SessionLocal
    from app.db_models import OdooConnection

    db = SessionLocal()
    try:
        row = db.get(OdooConnection, conn_id)
        assert row is not None
    finally:
        db.close()

    odoo = MagicMock()
    odoo.execute_kw.return_value = [{"id": 1, "display_name": "A"}]

    with patch("app.routers.bulk_suite._client", return_value=(row, odoo)):
        with patch("app.routers.bulk_suite.manifest_for_connection", return_value={"models": {}}):
            with patch(
                "app.routers.bulk_suite.resolve_and_cap",
                return_value=[1],
            ):
                execute = client.post(
                    f"/api/connections/{conn_id}/bulk/mass-edit",
                    json={
                        "model": "res.partner",
                        "values": {"comment": "x"},
                        "ids": [1],
                        "dry_run": False,
                        "confirm_advanced": True,
                        "confirm_phrase": "I understand the risks",
                    },
                )
    assert execute.status_code == 403
    assert execute.json()["detail"]["error"] == "dry_run_receipt_required"

    with patch("app.routers.bulk_suite._client", return_value=(row, odoo)):
        with patch("app.routers.bulk_suite.manifest_for_connection", return_value={"models": {}}):
            with patch("app.routers.bulk_suite.resolve_and_cap", return_value=[1]):
                with patch(
                    "app.routers.bulk_suite.run_mass_edit",
                    return_value=MassEditResult(
                        run_id=f"dry-{uuid.uuid4().hex[:8]}",
                        operation="mass_edit",
                        model="res.partner",
                        total=1,
                        succeeded=1,
                        failed=0,
                        per_record=[],
                        dry_run=True,
                        message="ok",
                    ),
                ):
                    dry = client.post(
                        f"/api/connections/{conn_id}/bulk/mass-edit",
                        json={
                            "model": "res.partner",
                            "values": {"comment": "x"},
                            "ids": [1],
                            "dry_run": True,
                        },
                    )
    assert dry.status_code == 200, dry.text
    token = dry.json()["receipt_token"]
    assert token

    with patch("app.routers.bulk_suite._client", return_value=(row, odoo)):
        with patch("app.routers.bulk_suite.manifest_for_connection", return_value={"models": {}}):
            with patch("app.routers.bulk_suite.resolve_and_cap", return_value=[1]):
                with patch(
                    "app.routers.bulk_suite.run_mass_edit",
                    return_value=MassEditResult(
                        run_id=f"exec-{uuid.uuid4().hex[:8]}",
                        operation="mass_edit",
                        model="res.partner",
                        total=1,
                        succeeded=1,
                        failed=0,
                        per_record=[],
                        dry_run=False,
                        message="ok",
                    ),
                ):
                    ok = client.post(
                        f"/api/connections/{conn_id}/bulk/mass-edit",
                        json={
                            "model": "res.partner",
                            "values": {"comment": "x"},
                            "ids": [1],
                            "dry_run": False,
                            "receipt_token": token,
                            "confirm_advanced": True,
                            "confirm_phrase": "I understand the risks",
                        },
                    )
    assert ok.status_code == 200, ok.text
