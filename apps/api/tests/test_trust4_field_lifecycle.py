"""TRUST-4 field lifecycle tests."""

from __future__ import annotations

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

from app.field_lifecycle import FieldLifecycleError, export_field_column_csv  # noqa: E402
from odoo_client.client import OdooClientError  # noqa: E402


def test_export_field_column_csv_builds_id_value_rows() -> None:
    client = MagicMock()
    client.field_exists.return_value = True
    client.execute_kw.return_value = [
        {"id": 1, "x_note": "alpha"},
        {"id": 2, "x_note": None},
    ]

    export = export_field_column_csv(client, model="x.test", field_name="x_note")
    assert export.row_count == 2
    assert "1,alpha" in export.csv_text
    assert "2," in export.csv_text
    assert export.truncated is False


def test_export_field_column_csv_refuses_on_rpc_error() -> None:
    client = MagicMock()
    client.field_exists.return_value = True
    client.execute_kw.side_effect = OdooClientError("boom")
    with pytest.raises(FieldLifecycleError, match="Column export failed"):
        export_field_column_csv(client, model="x.test", field_name="x_note")


def test_deprecate_field_renames() -> None:
    from app.field_lifecycle import deprecate_field as deprecate_field_fn

    client = MagicMock()
    updated = MagicMock()
    updated.model_dump.return_value = {"id": 99, "name": "x_deprecated_note", "readonly": True}
    client.deprecate_field.return_value = updated

    result = deprecate_field_fn(client, 99)
    client.deprecate_field.assert_called_once_with(99)
    assert result["name"] == "x_deprecated_note"


def test_hard_delete_refused_when_export_fails() -> None:
    from fastapi.testclient import TestClient

    from app.db import init_db  # noqa: E402
    from app.main import app  # noqa: E402

    init_db()
    with TestClient(app) as http:
        create = http.post(
            "/api/connections",
            json={
                "name": "TRUST4",
                "url": "http://127.0.0.1:8069",
                "db_name": "odoo",
                "username": "admin",
                "password": "admin",
                "verify": False,
            },
        )
        assert create.status_code == 201
        conn_id = create.json()["id"]
        unlock = http.patch(
            f"/api/connections/{conn_id}/write-mode",
            json={"write_mode": "standard"},
        )
        assert unlock.status_code == 200

        import app.routers.builder as builder_router

        odoo = MagicMock()
        odoo.read_field_raw.return_value = {
            "id": 5,
            "name": "x_note",
            "model": "x_trust4_custom",
        }
        odoo.field_exists.return_value = True
        odoo.execute_kw.side_effect = OdooClientError("export failed")

        original = builder_router._client
        original_manifest = builder_router.manifest_for_connection

        builder_router.manifest_for_connection = lambda _row: {"models": {}}

        def fake_client(_cid, _db):
            return odoo

        builder_router._client = fake_client
        try:
            resp = http.request(
                "DELETE",
                f"/api/connections/{conn_id}/fields/5",
                json={
                    "mode": "hard_delete",
                    "confirm_advanced": True,
                    "confirm_phrase": "I understand the risks",
                },
            )
        finally:
            builder_router._client = original
            builder_router.manifest_for_connection = original_manifest

    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "field_export_failed"
