"""POST /module-spec/import-json — paste ModuleSpec JSON."""

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


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_import_json_runs_live_prep(client: TestClient) -> None:
    body = {
        "spec": {
            "technical_name": "paste_demo",
            "models": [
                {
                    "model": "x_branch",
                    "mode": "new",
                    "fields": [
                        {"name": "x_name", "ttype": "char"},
                        {"name": "company_id", "ttype": "many2one", "relation": "res.company"},
                    ],
                }
            ],
        },
        "prepare": True,
    }
    res = client.post("/api/module-spec/import-json", json=body)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    assert data["source"] == "json_paste"
    names = {f["name"] for f in data["spec"]["models"][0]["fields"]}
    assert "x_company_id" in names
    assert any("x_company_id" in n for n in data["warnings"])


def test_import_json_rejects_empty_models(client: TestClient) -> None:
    res = client.post("/api/module-spec/import-json", json={"spec": {"models": []}})
    assert res.status_code == 422
