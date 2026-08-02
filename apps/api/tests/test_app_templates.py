"""Unit + integration tests for app wizard templates (Phase P1)."""

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

from app.app_templates import list_templates  # noqa: E402
from app.main import app  # noqa: E402
from app.snapshots import CONFIRM_PHRASE  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_list_templates_includes_library() -> None:
    templates = list_templates()
    ids = {t["id"] for t in templates}
    assert "library" in ids
    assert "crm_lite" in ids
    assert "inventory_lite" in ids
    lib = next(t for t in templates if t["id"] == "library")
    assert lib["name"] == "Library"
    assert "description" in lib


def test_get_apps_templates_api(client: TestClient) -> None:
    res = client.get("/api/apps/templates")
    assert res.status_code == 200, res.text
    body = res.json()
    assert isinstance(body, list)
    assert any(t["id"] == "library" for t in body)


def test_scaffold_requires_confirm(client: TestClient) -> None:
    # Connection may or may not exist — confirm gate runs after 404 check.
    # Use a fake UUID; expect 404 before confirm when connection missing.
    res = client.post(
        "/api/connections/00000000-0000-0000-0000-000000000000/apps/scaffold",
        json={"template_id": "library"},
    )
    assert res.status_code == 404


@pytest.mark.integration
def test_scaffold_library_on_live_odoo(client: TestClient) -> None:
    create = client.post(
        "/api/connections",
        json={
            "name": "Library Scaffold Gate",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]

    denied = client.post(
        f"/api/connections/{cid}/apps/scaffold",
        json={"template_id": "library", "display_name": "Library Gate"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["confirm_phrase"] == CONFIRM_PHRASE

    scaffold = client.post(
        f"/api/connections/{cid}/apps/scaffold",
        json={
            "template_id": "library",
            "display_name": "Library Gate",
            "confirm_advanced": True,
            "confirm_phrase": CONFIRM_PHRASE,
        },
    )
    assert scaffold.status_code == 200, scaffold.text
    body = scaffold.json()
    assert body["ok"] is True
    assert body["template_id"] == "library"
    assert "x_lib_category" in body["models"]
    assert "x_lib_book" in body["models"]
    assert "x_lib_loan" in body["models"]
    assert body["fields_created"] >= 0

    # Idempotent re-run: models skipped, no crash
    again = client.post(
        f"/api/connections/{cid}/apps/scaffold",
        json={
            "template_id": "library",
            "confirm_advanced": True,
            "confirm_phrase": CONFIRM_PHRASE,
        },
    )
    assert again.status_code == 200, again.text
    again_body = again.json()
    assert "x_lib_book" in again_body["models_skipped"] or again_body["ok"]

    models = client.get(f"/api/connections/{cid}/models")
    assert models.status_code == 200
    model_names = {m["model"] for m in models.json()}
    assert "x_lib_book" in model_names
    assert "x_lib_loan" in model_names

    fields = client.get(f"/api/connections/{cid}/models/x_lib_book/fields")
    assert fields.status_code == 200
    field_names = {f["name"] for f in fields.json()}
    assert "x_isbn" in field_names
    assert "x_status" in field_names
    assert "x_category_id" in field_names
