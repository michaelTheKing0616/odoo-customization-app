"""Domain playbooks — CRM / Project / Sale module-gated honesty (M3-P2)."""

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
from app.routers.domain_playbooks import PLAYBOOKS  # noqa: E402


def test_domain_playbooks_catalog() -> None:
    ids = {p["id"] for p in PLAYBOOKS}
    assert ids == {"crm_stages", "project_stages", "sale_pricelists"}


class _FakeDomainClient:
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
            return [{"id": 1, "name": "Demo", "sequence": 1}]
        if method == "fields_get":
            return {"name": {"type": "char"}, "sequence": {"type": "integer"}}
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
            name="domain-pb",
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


def test_list_domain_playbooks_unavailable_without_modules(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeDomainClient()
    with patch("app.routers.domain_playbooks.client_from_connection", return_value=fake):
        res = client.get(f"/api/connections/{cid}/domain-playbooks")
    assert res.status_code == 200
    by_id = {r["id"]: r for r in res.json()}
    assert by_id["crm_stages"]["available"] is False
    assert by_id["project_stages"]["available"] is False
    assert by_id["sale_pricelists"]["available"] is False


def test_crm_stages_available_when_crm_installed(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeDomainClient(installed={"crm"}, models={"crm.stage"})
    with patch("app.routers.domain_playbooks.client_from_connection", return_value=fake):
        catalog = client.get(f"/api/connections/{cid}/domain-playbooks")
        stages = client.get(f"/api/connections/{cid}/domain-playbooks/crm/stages")
    assert catalog.json()[0]["available"] is True or any(
        r["id"] == "crm_stages" and r["available"] for r in catalog.json()
    )
    assert stages.status_code == 200
    body = stages.json()
    assert body["available"] is True
    assert body["model"] == "crm.stage"
    assert len(body["rows"]) == 1


def test_crm_stages_honesty_when_absent(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeDomainClient()
    with patch("app.routers.domain_playbooks.client_from_connection", return_value=fake):
        res = client.get(f"/api/connections/{cid}/domain-playbooks/crm/stages")
    assert res.status_code == 200
    assert res.json()["available"] is False
    assert "not installed" in (res.json()["reason"] or "").lower()
