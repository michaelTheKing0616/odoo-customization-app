"""Unit tests for Phase P2: relational_pair schema + draft projects."""

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

from app.main import app  # noqa: E402
from app.schemas import RelationalPairBody  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_relational_pair_schema() -> None:
    body = RelationalPairBody(
        parent_model="x_lib_book",
        child_model="x_lib_loan",
        parent_o2m_name="x_loan_ids",
        child_m2o_name="x_book_id",
        parent_o2m_string="Loans",
        child_m2o_string="Book",
        inject_into_views=True,
    )
    assert body.parent_o2m_name == "x_loan_ids"
    assert body.inject_into_views is True


def test_project_create_from_library_template(client: TestClient) -> None:
    """Creates a draft with library ModuleSpec models without needing Odoo."""
    # Need a connection row — create without verify if DB available
    create = client.post(
        "/api/connections",
        json={
            "name": "P2 Projects Unit",
            "url": "http://127.0.0.1:8069",
            "db_name": "odoo_dev",
            "username": "admin",
            "password": "admin",
            "verify": False,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"app-db not ready: {create.text}")
    cid = create.json()["id"]
    try:
        proj = client.post(
            f"/api/connections/{cid}/projects",
            json={"name": "Lib draft", "template_id": "library", "spec_json": {}},
        )
        assert proj.status_code == 201, proj.text
        body = proj.json()
        assert body["status"] == "draft"
        assert body["template_id"] == "library"
        models = body["spec_json"].get("models") or []
        assert len(models) >= 3
        names = {m["model"] for m in models}
        assert "x_lib_book" in names
        assert "x_lib_loan" in names
        book = next(m for m in models if m["model"] == "x_lib_book")
        assert "mail.thread" in (book.get("mixins") or [])

        listed = client.get(f"/api/connections/{cid}/projects")
        assert listed.status_code == 200
        assert any(p["id"] == body["id"] for p in listed.json())
    finally:
        client.delete(f"/api/connections/{cid}")
