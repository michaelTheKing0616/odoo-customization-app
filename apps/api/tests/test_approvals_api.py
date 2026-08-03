"""HTTP tests for approvals API (CMP-5)."""

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


class _FakeApprovalClient:
    def __init__(self, *, studio: bool = False) -> None:
        self.studio = studio
        self.models = {
            "ir.module.module",
            "res.users",
            "ir.config_parameter",
            "mail.activity.type",
            "mail.activity",
            "res.partner",
        }
        if studio:
            self.models.add("studio.approval.rule")
        self.installed = {"base", "mail"}

    def model_exists(self, name: str) -> bool:
        return name in self.models

    def execute_kw(
        self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> Any:
        kwargs = kwargs or {}
        if model == "ir.module.module" and method == "search_read":
            return [{"state": "installed"}]
        if model == "studio.approval.rule" and method == "fields_get":
            return {"name": {"type": "char"}, "user_ids": {"type": "many2many"}}
        if model == "res.users" and method == "read":
            return [{"groups_id": []}]
        if model == "ir.config_parameter" and method == "set_param":
            return True
        if model == "mail.activity.type" and method == "search_read":
            return [{"id": 1}]
        if model == "mail.activity" and method == "create":
            return 99
        if model == "res.partner" and method == "search_count":
            return 1
        if method == "message_post":
            return True
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
            name="cmp5",
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


def test_approvals_gate_community_engine(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeApprovalClient()
    with patch("app.routers.approvals.client_from_connection", return_value=fake):
        res = client.get(f"/api/connections/{cid}/approvals/gate")
    assert res.status_code == 200
    body = res.json()
    assert body["engine"] == "community"
    assert body["community_available"] is True


def test_create_and_check_community_rule(client: TestClient) -> None:
    cid = _conn_id()
    fake = _FakeApprovalClient()
    with patch("app.routers.approvals.client_from_connection", return_value=fake):
        created = client.post(
            f"/api/connections/{cid}/approvals/rules",
            json={
                "name": "Approve partner archive",
                "target_model": "res.partner",
                "button_method": "action_archive",
                "steps": [{"order": 1, "approver_user_ids": [2]}],
                "engine": "community",
            },
        )
        assert created.status_code == 201
        rule_id = created.json()["id"]
        check = client.post(
            f"/api/connections/{cid}/approvals/rules/{rule_id}/check",
            json={"record_id": 7, "actor_user_id": 2},
        )
    assert check.status_code == 200
    body = check.json()
    assert body["allowed"] is False
    assert body["pending_step"] == 1
