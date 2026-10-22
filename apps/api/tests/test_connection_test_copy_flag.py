"""Saved 'This is a test copy' flag: set on create, editable, None for old rows."""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom")
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402


def _body(**kw):
    return {"name": "Flag conn", "url": "http://127.0.0.1:8069", "db_name": "ingenium_flag", "username": "admin", "password": "x", "verify": False, **kw}


def test_flag_round_trip():
    init_db()
    with TestClient(app) as c:
        old = c.post("/api/connections", json=_body()).json()
        assert old["is_test_copy"] is None
        new = c.post("/api/connections", json=_body(is_test_copy=True)).json()
        assert new["is_test_copy"] is True
        upd = c.patch(f"/api/connections/{new['id']}", json={"is_test_copy": False, "verify": False})
        assert upd.status_code == 200, upd.text
        assert upd.json()["is_test_copy"] is False
        for cid in (old["id"], new["id"]):
            c.delete(f"/api/connections/{cid}")
