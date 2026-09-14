"""Overlay apply endpoint tests (REM-6)."""

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


@pytest.fixture
def connection_id() -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="overlay-test",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def test_overlay_preview_hide(client: TestClient, connection_id: str) -> None:
    res = client.post(
        f"/api/connections/{connection_id}/views/overlay/preview",
        json={
            "model": "res.partner",
            "view_type": "form",
            "operation": "hide",
            "expr": "//field[@name='email']",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "invisible" in body["xpath_arch"]
    assert body["issues"] == []


def test_overlay_apply_creates_inherit(client: TestClient, connection_id: str) -> None:
    fake_primary = MagicMock(id=10, arch='<form><field name="email"/></form>', type="form")
    fake_view = MagicMock(id=99, arch="<data/>", type="form")

    fake_client = MagicMock()
    fake_client.find_view.return_value = fake_primary
    fake_client._find_view_by_exact_name.return_value = None
    fake_client.create_inherit_view.return_value = fake_view

    with patch("app.routers.views.client_from_connection", return_value=fake_client):
        with patch("app.snapshots.snapshot_view", return_value=MagicMock(id="snap-1")):
            res = client.post(
                f"/api/connections/{connection_id}/views/overlay/apply",
                json={
                    "model": "res.partner",
                    "view_type": "form",
                    "operation": "hide",
                    "expr": "//field[@name='email']",
                    "field_name": "email",
                },
            )
    assert res.status_code == 200
    body = res.json()
    assert body["view_id"] == 99
    assert body["snapshot_id"] == "snap-1"
    assert "res.partner.overlay.form" in (body["inherit_name"] or "")
    fake_client.create_inherit_view.assert_called_once()


def test_overlay_apply_blocks_missing_locator(client: TestClient, connection_id: str) -> None:
    fake_primary = MagicMock(id=10, arch='<form><field name="email"/></form>', type="form")
    fake_client = MagicMock()
    fake_client.find_view.return_value = fake_primary
    fake_client._find_view_by_exact_name.return_value = None

    with patch("app.routers.views.client_from_connection", return_value=fake_client):
        with patch("app.snapshots.snapshot_view", return_value=MagicMock(id="snap-1")):
            res = client.post(
                f"/api/connections/{connection_id}/views/overlay/apply",
                json={
                    "model": "res.partner",
                    "view_type": "form",
                    "operation": "hide",
                    "expr": "//field[@name='missing']",
                    "field_name": "missing",
                },
            )
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert detail["code"] == "missing_node"
    assert detail["expr"] == "//field[@name='missing']"
    fake_client.create_inherit_view.assert_not_called()


def test_save_xpath_inherit_blocks_missing_locator(client: TestClient, connection_id: str) -> None:
    fake_primary = MagicMock(
        id=10,
        arch='<form><sheet><field name="email"/></sheet></form>',
        type="form",
        name="res.partner.form",
    )
    fake_client = MagicMock()
    fake_client.model_exists.return_value = True
    fake_client.find_view.return_value = fake_primary
    fake_client.execute_kw.return_value = []

    arch = (
        "<data>"
        "<xpath expr=\"//field[@name='missing']\" position=\"inside\">"
        "<field name=\"x_extra\"/>"
        "</xpath>"
        "</data>"
    )
    with patch("app.routers.views.client_from_connection", return_value=fake_client):
        with patch("app.snapshots.snapshot_view", return_value=MagicMock(id="snap-1")):
            res = client.post(
                f"/api/connections/{connection_id}/views/save",
                json={
                    "model": "res.partner",
                    "view_type": "form",
                    "strategy": "inherit",
                    "create_if_missing": True,
                    "arch": arch,
                },
            )
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert detail["code"] == "missing_node"
    assert "missing" in (detail.get("expr") or "")
    fake_client.create_inherit_view.assert_not_called()


FORM_WITH_NOTEBOOK = (
    '<form><sheet><group id="g"><field name="email"/></group>'
    '<notebook><page string="Main"><field name="name"/></page></notebook>'
    "</sheet></form>"
)


def test_overlay_preview_add_page(client: TestClient, connection_id: str) -> None:
    res = client.post(
        f"/api/connections/{connection_id}/views/overlay/preview",
        json={
            "model": "res.partner",
            "view_type": "form",
            "operation": "add_page",
            "string": "Notes",
            "parent_arch": FORM_WITH_NOTEBOOK,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "x_page_notes" in body["xpath_arch"]
    assert "//notebook" in body["xpath_arch"]
    assert not any(i["severity"] == "error" for i in body["locator_issues"])


def test_overlay_apply_add_page_creates_inherit(
    client: TestClient, connection_id: str
) -> None:
    fake_primary = MagicMock(id=10, arch=FORM_WITH_NOTEBOOK, type="form")
    fake_view = MagicMock(id=77, arch="<data/>", type="form")
    fake_client = MagicMock()
    fake_client.find_view.return_value = fake_primary
    fake_client._find_view_by_exact_name.return_value = None
    fake_client.create_inherit_view.return_value = fake_view

    with patch("app.routers.views.client_from_connection", return_value=fake_client):
        with patch("app.snapshots.snapshot_view", return_value=MagicMock(id="snap-page")):
            res = client.post(
                f"/api/connections/{connection_id}/views/overlay/apply",
                json={
                    "model": "res.partner",
                    "view_type": "form",
                    "operation": "add_page",
                    "string": "Notes",
                    "parent_arch": FORM_WITH_NOTEBOOK,
                },
            )
    assert res.status_code == 200, res.text
    kwargs = fake_client.create_inherit_view.call_args.kwargs
    assert "x_page_notes" in kwargs["arch"]


def test_overlay_apply_move_inside_blocks_missing_group(
    client: TestClient, connection_id: str
) -> None:
    fake_primary = MagicMock(id=10, arch=FORM_WITH_NOTEBOOK, type="form")
    fake_client = MagicMock()
    fake_client.find_view.return_value = fake_primary
    fake_client._find_view_by_exact_name.return_value = None

    with patch("app.routers.views.client_from_connection", return_value=fake_client):
        with patch("app.snapshots.snapshot_view", return_value=MagicMock(id="snap-1")):
            res = client.post(
                f"/api/connections/{connection_id}/views/overlay/apply",
                json={
                    "model": "res.partner",
                    "view_type": "form",
                    "operation": "move",
                    "expr": "//field[@name='email']",
                    "anchor_expr": "//group[@id='missing']",
                    "move_position": "inside",
                    "parent_arch": FORM_WITH_NOTEBOOK,
                },
            )
    assert res.status_code == 422, res.text
    assert res.json()["detail"]["code"] == "missing_node"
    fake_client.create_inherit_view.assert_not_called()


def test_resolve_structure_ranks_named_group(client: TestClient, connection_id: str) -> None:
    res = client.post(
        f"/api/connections/{connection_id}/views/resolve-structure",
        json={"arch": FORM_WITH_NOTEBOOK},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    xpaths = [c["xpath"] for c in body["candidates"]]
    assert "//group[@id='g']" in xpaths
    assert any(c["tag"] == "notebook" for c in body["candidates"])
