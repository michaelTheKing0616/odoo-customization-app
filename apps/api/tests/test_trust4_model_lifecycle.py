"""TRUST-4 model delete pre-export + artifact.json tests."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.model_lifecycle import ModelLifecycleError, export_model_records_json  # noqa: E402
from odoo_client.client import OdooClientError  # noqa: E402


def test_export_model_records_json_batches() -> None:
    client = MagicMock()
    client.model_exists.return_value = True
    client.execute_kw.side_effect = [
        [{"name": "x_name", "ttype": "char"}],
        [{"id": 1, "x_name": "a"}, {"id": 2, "x_name": "b"}],
    ]
    export = export_model_records_json(client, model="x_test")
    assert export.record_count == 2
    payload = json.loads(export.json_text)
    assert payload["model"] == "x_test"
    assert len(payload["records"]) == 2


def test_export_model_refused_on_rpc_error() -> None:
    client = MagicMock()
    client.model_exists.return_value = True
    client.execute_kw.side_effect = OdooClientError("boom")
    with pytest.raises(ModelLifecycleError, match="Field introspection failed"):
        export_model_records_json(client, model="x_test")


def test_delete_model_refused_when_export_fails() -> None:
    from fastapi.testclient import TestClient

    from app.db import init_db
    from app.main import app

    init_db()
    with TestClient(app) as http:
        create = http.post(
            "/api/connections",
            json={
                "name": "TRUST4M",
                "url": "http://127.0.0.1:8069",
                "db_name": "odoo",
                "username": "admin",
                "password": "admin",
                "verify": False,
            },
        )
        conn_id = create.json()["id"]
        http.patch(
            f"/api/connections/{conn_id}/write-mode",
            json={"write_mode": "standard", "confirm_advanced": True, "confirm_phrase": "I understand the risks"},
        )
        with pytest.MonkeyPatch.context() as mp:
            from app import routers

            mock_client = MagicMock()
            mock_client.model_exists.return_value = False
            mp.setattr(routers.builder, "_client", lambda *_a, **_k: mock_client)
            res = http.request(
                "DELETE",
                f"/api/connections/{conn_id}/models/x_missing",
                json={"confirm_advanced": True, "confirm_phrase": "I understand the risks"},
            )
        assert res.status_code == 422
        assert res.json()["detail"]["error"] == "model_export_failed"
