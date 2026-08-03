"""EE view save gating + grid arch (TIER-5)."""

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
from odoo_client.view_arch import parse_grid_arch, render_grid_arch, GridViewSpec  # noqa: E402


def test_grid_arch_round_trip() -> None:
    spec = GridViewSpec(
        string="Planning",
        row_field="user_id",
        col_field="project_id",
        measure="planned_hours",
        date_start="date_start",
        date_stop="date_stop",
    )
    arch = render_grid_arch(spec)
    assert 'row_field="user_id"' in arch
    parsed = parse_grid_arch(arch)
    assert parsed.row_field == "user_id"
    assert parsed.measure == "planned_hours"


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def test_community_blocks_gantt_save(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="comm-views",
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

    fake = MagicMock()
    with patch("app.routers.views.client_from_connection", return_value=fake):
        res = client.post(
            f"/api/connections/{cid}/views/save",
            json={
                "model": "project.task",
                "view_type": "gantt",
                "spec": {"string": "Tasks", "date_start": "date_start"},
                "create_if_missing": True,
            },
        )
    assert res.status_code == 409
    assert res.json()["detail"]["capability"] == "views_enterprise_types"
