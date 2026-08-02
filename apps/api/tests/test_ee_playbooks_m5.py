"""EE playbooks — catalog + HTTP grey-out when modules absent (mastery M5)."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

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
from app.routers.ee_playbooks import PLAYBOOKS  # noqa: E402


def test_playbooks_catalog_has_sign_documents_studio() -> None:
    ids = {p["id"] for p in PLAYBOOKS}
    assert "sign_templates" in ids
    assert "documents_folders" in ids
    assert "studio_presence" in ids
    assert "spreadsheet_dashboard" in ids
    assert "voip" in ids
    assert "iot" in ids
    assert "account_accountant" in ids
    assert "hr_payroll" in ids
    studio = next(p for p in PLAYBOOKS if p["id"] == "studio_presence")
    assert studio.get("warn_only") is True
    payroll = next(p for p in PLAYBOOKS if p["id"] == "hr_payroll")
    assert payroll.get("warn_only") is True


def test_playbooks_never_reference_studio_source_paths() -> None:
    blob = str(PLAYBOOKS).lower()
    assert "web_studio/static" not in blob
    assert "enterprise/addons/web_studio" not in blob


class _FakeEeClient:
    def __init__(self, installed: set[str] | None = None, models: set[str] | None = None) -> None:
        self.installed = installed or {"base", "web", "mail"}
        self.models = models or set()

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        kwargs = kwargs or {}
        if model == "ir.module.module" and method == "search_read":
            domain = args[0] if args else []
            name = None
            for clause in domain:
                if isinstance(clause, (list, tuple)) and len(clause) >= 3 and clause[0] == "name":
                    name = clause[2]
            if name in self.installed:
                return [{"name": name, "state": "installed"}]
            if name:
                return [{"name": name, "state": "uninstalled"}]
            return []
        if method == "search_read":
            return [{"id": 1, "name": "Row"}]
        raise AssertionError(f"unexpected {model}.{method}")

    def model_exists(self, name: str) -> bool:
        return name in self.models


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _conn_id() -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="ee-pb",
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


def test_list_playbooks_http_unavailable_without_ee_modules(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeEeClient(installed={"base", "web", "mail"})

    def _client_from_connection(_row):
        return fake

    with patch("app.routers.ee_playbooks.client_from_connection", _client_from_connection):
        res = client.get(f"/api/connections/{cid}/ee-playbooks")
    assert res.status_code == 200
    body = res.json()
    by_id = {r["id"]: r for r in body}
    assert by_id["sign_templates"]["available"] is False
    assert "not installed" in by_id["sign_templates"]["reason"].lower() or "Modules" in by_id[
        "sign_templates"
    ]["reason"]
    assert by_id["documents_folders"]["available"] is False
    assert by_id["studio_presence"]["available"] is False
    assert by_id["spreadsheet_dashboard"]["available"] is False
    assert by_id["voip"]["available"] is False
    assert by_id["iot"]["available"] is False
    assert by_id["account_accountant"]["available"] is False
    assert by_id["hr_payroll"]["available"] is False


def test_list_playbooks_http_available_when_sign_installed(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeEeClient(installed={"base", "web", "sign", "documents", "web_studio"})

    with patch("app.routers.ee_playbooks.client_from_connection", return_value=fake):
        res = client.get(f"/api/connections/{cid}/ee-playbooks")
    assert res.status_code == 200
    by_id = {r["id"]: r for r in res.json()}
    assert by_id["sign_templates"]["available"] is True
    assert by_id["documents_folders"]["available"] is True
    assert by_id["studio_presence"]["available"] is True
    assert by_id["studio_presence"]["warn_only"] is True
    assert "Studio" in by_id["studio_presence"]["reason"]


def test_spreadsheet_available_via_alternate_module(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeEeClient(installed={"spreadsheet"}, models={"spreadsheet.dashboard"})
    with patch("app.routers.ee_playbooks.client_from_connection", return_value=fake):
        res = client.get(f"/api/connections/{cid}/ee-playbooks")
        dash = client.get(f"/api/connections/{cid}/ee-playbooks/spreadsheet/dashboards")
    by_id = {r["id"]: r for r in res.json()}
    assert by_id["spreadsheet_dashboard"]["available"] is True
    assert dash.status_code == 200
    assert len(dash.json()) == 1


def test_voip_404_when_module_absent(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeEeClient(installed={"base"})
    with patch("app.routers.ee_playbooks.client_from_connection", return_value=fake):
        res = client.get(f"/api/connections/{cid}/ee-playbooks/voip/phonecalls")
    assert res.status_code == 404


def test_sign_templates_404_when_module_absent(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeEeClient(installed={"base"})
    with patch("app.routers.ee_playbooks.client_from_connection", return_value=fake):
        res = client.get(f"/api/connections/{cid}/ee-playbooks/sign/templates")
    assert res.status_code == 404
    assert "not installed" in res.json()["detail"].lower()
