"""Fake-RPC tests for Enterprise drivers (TIER-5)."""

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
from app.ee_drivers import (  # noqa: E402
    APPROVAL_RULE_MODEL,
    create_approval_rule,
    list_approval_rules,
    probe_all_drivers,
    probe_approval_rules_driver,
)
from app.main import app  # noqa: E402


class _FakeApprovalClient:
    def __init__(self) -> None:
        self._rules: dict[int, dict[str, Any]] = {1: {"id": 1, "name": "Pay bill", "active": True}}
        self._next = 2
        self.models = {
            APPROVAL_RULE_MODEL,
            "ir.module.module",
            "sign.request",
            "sign.template",
            "documents.document",
            "spreadsheet.dashboard",
        }
        self.installed = {"web_studio", "sign", "documents", "spreadsheet_dashboard"}

    def model_exists(self, name: str) -> bool:
        return name in self.models

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        kwargs = kwargs or {}
        if model == "ir.module.module" and method == "search_read":
            domain = args[0] if args else []
            mod = None
            for clause in domain:
                if isinstance(clause, (list, tuple)) and clause[0] == "name":
                    mod = clause[2]
            if mod in self.installed:
                return [{"state": "installed"}]
            return [{"state": "uninstalled"}]
        if model == APPROVAL_RULE_MODEL and method == "fields_get":
            return {
                "name": {"type": "char"},
                "model_id": {"type": "many2one"},
                "method": {"type": "char"},
                "user_ids": {"type": "many2many"},
                "domain": {"type": "char"},
                "active": {"type": "boolean"},
            }
        if model == APPROVAL_RULE_MODEL and method == "search_read":
            return list(self._rules.values())
        if model == APPROVAL_RULE_MODEL and method == "create":
            vals = args[0]
            rid = self._next
            self._next += 1
            row = {"id": rid, **vals}
            self._rules[rid] = row
            return rid
        if model == APPROVAL_RULE_MODEL and method == "read":
            ids = args[0]
            return [self._rules[i] for i in ids if i in self._rules]
        if method == "fields_get":
            return {"id": {"type": "integer"}, "name": {"type": "char"}}
        if method == "search_read":
            return [{"id": 1, "name": "Row"}]
        raise AssertionError(f"unexpected {model}.{method}")


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _conn_id() -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="ee-drivers",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0+e",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def test_probe_approval_driver_live_fields_subset() -> None:
    fake = _FakeApprovalClient()
    status = probe_approval_rules_driver(fake)
    assert status.available is True
    assert "name" in status.verified_fields
    assert status.verify_state in {"live", "pending-live"}


def test_create_approval_rule_uses_probed_fields() -> None:
    fake = _FakeApprovalClient()
    rule_id, status = create_approval_rule(fake, {"name": "Approve PO", "active": True})
    assert rule_id == 2
    rows, _ = list_approval_rules(fake)
    assert any(r["name"] == "Approve PO" for r in rows)
    assert status.verify_state in {"live", "pending-live"}


def test_driver_status_http(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeApprovalClient()
    with patch("app.routers.ee_drivers.client_from_connection", return_value=fake):
        res = client.get(f"/api/connections/{cid}/ee-drivers/status")
    assert res.status_code == 200
    body = res.json()
    by_id = {r["driver_id"]: r for r in body}
    assert by_id["studio_approval_rules"]["available"] is True
    assert by_id["ee_playbook_sign"]["available"] is True
    assert by_id["ee_playbook_documents"]["available"] is True


def test_approval_rules_crud_http(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeApprovalClient()
    with patch("app.routers.ee_drivers.client_from_connection", return_value=fake):
        listed = client.get(f"/api/connections/{cid}/ee-drivers/approval-rules")
        created = client.post(
            f"/api/connections/{cid}/ee-drivers/approval-rules",
            json={"name": "New rule", "active": True},
        )
    assert listed.status_code == 200
    assert created.status_code == 201
    assert created.json()["data"]["name"] == "New rule"
    if created.json().get("verify_state") == "pending-live":
        assert "[SKIPPED-LIVE-VERIFY]" in (created.json().get("note") or "")


def test_probe_all_drivers_counts() -> None:
    fake = _FakeApprovalClient()
    rows = probe_all_drivers(fake)
    assert len(rows) == 4
