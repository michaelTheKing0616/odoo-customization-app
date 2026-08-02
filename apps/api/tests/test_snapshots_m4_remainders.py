"""Snapshot helpers + rollback honesty (mastery M4 remainders)."""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import MetadataSnapshot, OdooConnection  # noqa: E402
from app.snapshots import (  # noqa: E402
    rollback_snapshot,
    save_snapshot,
    snapshot_action,
)


def _mk_connection(name: str = "snap-m4") -> OdooConnection:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name=name,
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def test_snapshot_action_created_rollback_unlinks() -> None:
    init_db()
    conn = _mk_connection("action-create")
    db = SessionLocal()
    try:
        client = MagicMock()
        client.execute_kw.side_effect = [
            {"name": {}, "state": {}},  # fields_get
            [{"id": 42, "name": "Test SA", "state": "object_write"}],  # read
            True,  # unlink
        ]
        snap = snapshot_action(
            db,
            conn.id,
            client,
            model="ir.actions.server",
            action_id=42,
            created=True,
        )
        assert snap.resource_type == "action"
        payload = json.loads(snap.payload_json)
        assert payload["created"] is True
        assert payload["model"] == "ir.actions.server"

        result = rollback_snapshot(db, client, snap.id, connection_id=conn.id)
        assert result["action"] == "unlinked"
        assert result["id"] == 42
        client.execute_kw.assert_any_call("ir.actions.server", "unlink", [[42]])
    finally:
        db.close()


def test_snapshot_menu_created_rollback_unlinks() -> None:
    init_db()
    conn = _mk_connection("menu-create")
    db = SessionLocal()
    try:
        snap = save_snapshot(
            db,
            connection_id=conn.id,
            resource_type="menu",
            resource_key="menu:9",
            label="Menu X",
            payload={"menu": {"id": 9, "name": "X"}, "created": True},
            reversible="yes",
        )
        client = MagicMock()
        client.execute_kw.return_value = True
        result = rollback_snapshot(db, client, snap.id, connection_id=conn.id)
        assert result["action"] == "unlinked"
        client.execute_kw.assert_called_with("ir.ui.menu", "unlink", [[9]])
    finally:
        db.close()


def test_field_post_create_partial_rollback() -> None:
    init_db()
    conn = _mk_connection("field-partial")
    db = SessionLocal()
    try:
        snap = save_snapshot(
            db,
            connection_id=conn.id,
            resource_type="field",
            resource_key="field:7",
            label="Field x_test",
            payload={"field": {"id": 7, "name": "x_test"}, "created": True},
            reversible="partial",
        )
        client = MagicMock()
        client.execute_kw.return_value = True
        result = rollback_snapshot(db, client, snap.id, connection_id=conn.id)
        assert result.get("partial") is True
        assert result["action"] == "unlinked"
    finally:
        db.close()


def test_config_parameter_rollback_restores_value() -> None:
    init_db()
    conn = _mk_connection("cfg-param")
    db = SessionLocal()
    try:
        snap = save_snapshot(
            db,
            connection_id=conn.id,
            resource_type="config_parameter",
            resource_key="config_parameter:3",
            label="Config web.base.url",
            payload={"config_parameter": {"id": 3, "key": "web.base.url", "value": "http://old"}},
            reversible="yes",
        )
        client = MagicMock()
        client.execute_kw.return_value = True
        result = rollback_snapshot(db, client, snap.id, connection_id=conn.id)
        assert result["restored"] == "config_parameter"
        client.execute_kw.assert_called_with(
            "ir.config_parameter", "write", [[3], {"value": "http://old"}]
        )
    finally:
        db.close()
