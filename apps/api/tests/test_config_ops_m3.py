"""Mastery M3 config surfaces — paperformat, defaults, property, cron, website."""

from __future__ import annotations

import json
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
from app.snapshots import CONFIRM_PHRASE  # noqa: E402

CONFIRM = {"confirm_advanced": True, "confirm_phrase": CONFIRM_PHRASE}


class FakeM3Odoo:
    """In-memory stand-in covering M3 config RPC surfaces."""

    def __init__(self, *, website_installed: bool = False, property_exists: bool = True) -> None:
        self._seq = 200
        self.website_installed = website_installed
        self.property_exists = property_exists
        self.paperformats: dict[int, dict[str, Any]] = {
            1: {
                "id": 1,
                "name": "A4",
                "format": "A4",
                "orientation": "Portrait",
                "margin_top": 40.0,
                "margin_bottom": 20.0,
                "margin_left": 7.0,
                "margin_right": 7.0,
                "header_line": True,
                "header_spacing": 35.0,
                "dpi": 90,
            }
        }
        self.fields_meta = {
            "report.paperformat": {
                "name": {},
                "format": {},
                "orientation": {},
                "margin_top": {},
                "margin_bottom": {},
                "margin_left": {},
                "margin_right": {},
                "header_line": {},
                "header_spacing": {},
                "dpi": {},
            },
            "ir.default": {
                "field_id": {},
                "json_value": {},
                "user_id": {},
                "company_id": {},
                "condition": {},
            },
            "ir.property": {
                "name": {},
                "fields_id": {},
                "res_id": {},
                "company_id": {},
                "type": {},
                "value_text": {},
                "value_integer": {},
                "value_float": {},
                "value_reference": {},
            },
            "ir.cron": {
                "name": {},
                "model_id": {},
                "model_name": {},
                "interval_number": {},
                "interval_type": {},
                "active": {},
                "nextcall": {},
                "lastcall": {},
                "priority": {},
            },
            "website.page": {
                "name": {},
                "url": {},
                "website_id": {},
                "is_published": {},
                "view_id": {},
            },
            "website.menu": {
                "name": {},
                "url": {},
                "website_id": {},
                "parent_id": {},
                "sequence": {},
                "is_visible": {},
                "page_id": {},
            },
        }
        self.model_fields = [
            {
                "id": 10,
                "name": "name",
                "model": "res.partner",
                "model_id": [1, "Contact"],
            },
            {
                "id": 11,
                "name": "email",
                "model": "res.partner",
                "model_id": [1, "Contact"],
            },
        ]
        self.defaults: dict[int, dict[str, Any]] = {}
        self.properties: dict[int, dict[str, Any]] = {
            1: {
                "id": 1,
                "name": "property_account_payable_id",
                "fields_id": [11, "email"],
                "res_id": False,
                "company_id": [1, "My Company"],
                "type": "char",
                "value_text": "x",
                "value_integer": False,
                "value_float": False,
                "value_reference": False,
            }
        }
        self.crons: dict[int, dict[str, Any]] = {
            5: {
                "id": 5,
                "name": "Mail: Email Queue Manager",
                "model_id": [3, "mail.mail"],
                "model_name": "mail.mail",
                "interval_number": 1,
                "interval_type": "hours",
                "active": True,
                "nextcall": "2026-07-28 12:00:00",
                "lastcall": False,
                "priority": 5,
            }
        }
        self.website_pages = [
            {
                "id": 1,
                "name": "Home",
                "url": "/",
                "website_id": [1, "My Website"],
                "is_published": True,
                "view_id": [9, "Home"],
            }
        ]
        self.website_menus = [
            {
                "id": 1,
                "name": "Home",
                "url": "/",
                "website_id": [1, "My Website"],
                "parent_id": False,
                "sequence": 10,
                "is_visible": True,
                "page_id": [1, "Home"],
            }
        ]
        self.calls: list[tuple] = []

    def _next(self) -> int:
        self._seq += 1
        return self._seq

    def model_exists(self, model: str) -> bool:
        if model == "ir.property":
            return self.property_exists
        if model in ("website.page", "website.menu"):
            return self.website_installed
        if model == "uom.uom":
            return False
        if model == "account.fiscal.position":
            return False
        if model == "res.currency.rate":
            return True
        return True

    def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
        kwargs = kwargs or {}
        self.calls.append((model, method, args, kwargs))

        if method == "fields_get":
            return dict(self.fields_meta.get(model, {"name": {}}))

        if model == "ir.module.module" and method == "search_read":
            domain = args[0] if args else []
            name = None
            for clause in domain:
                if isinstance(clause, (list, tuple)) and clause[0] == "name":
                    name = clause[2]
            if name == "website":
                if self.website_installed:
                    return [{"id": 99, "state": "installed"}]
                return [{"id": 99, "state": "uninstalled"}]
            if name in ("uom", "account"):
                return [{"id": 98, "state": "uninstalled"}]
            return []

        if model == "res.currency" and method == "search_read":
            return [
                {"id": 1, "name": "USD", "symbol": "$", "active": True, "rate": 1.0},
            ]

        if model == "res.currency.rate" and method == "search_read":
            return [
                {
                    "id": 1,
                    "name": "2026-01-01",
                    "rate": 1.0,
                    "currency_id": [1, "USD"],
                }
            ]

        if model == "ir.model" and method == "search":
            domain = args[0] if args else []
            for clause in domain:
                if isinstance(clause, (list, tuple)) and clause[0] == "model":
                    if clause[2] == "ir.property":
                        return [1] if self.property_exists else []
                    return [1]
            return [1]

        if model == "ir.model" and method == "read":
            return [{"id": args[0][0], "model": "res.partner"}]

        if model == "report.paperformat" and method == "search_read":
            return list(self.paperformats.values())
        if model == "report.paperformat" and method == "create":
            pid = self._next()
            row = {"id": pid, **args[0]}
            row.setdefault("orientation", "Portrait")
            row.setdefault("header_line", False)
            self.paperformats[pid] = row
            return pid
        if model == "report.paperformat" and method == "write":
            for i in args[0]:
                self.paperformats[i].update(args[1])
            return True
        if model == "report.paperformat" and method == "read":
            return [self.paperformats[i] for i in args[0] if i in self.paperformats]

        if model == "ir.model.fields" and method == "search":
            domain = args[0] if args else []
            model_name = None
            field_name = None
            for clause in domain:
                if not isinstance(clause, (list, tuple)):
                    continue
                if clause[0] == "model":
                    model_name = clause[2]
                if clause[0] == "name":
                    field_name = clause[2]
            out = []
            for f in self.model_fields:
                if model_name and f["model"] != model_name:
                    continue
                if field_name and f["name"] != field_name:
                    continue
                out.append(f["id"])
            return out
        if model == "ir.model.fields" and method == "read":
            return [dict(f) for f in self.model_fields if f["id"] in args[0]]

        if model == "ir.default" and method == "search_read":
            domain = args[0] if args else []
            rows = list(self.defaults.values())
            for clause in domain:
                if isinstance(clause, (list, tuple)) and clause[0] == "field_id.model":
                    field_ids = {f["id"] for f in self.model_fields if f["model"] == clause[2]}
                    rows = [r for r in rows if _m2o(r.get("field_id")) in field_ids]
                if isinstance(clause, (list, tuple)) and clause[0] == "field_id" and clause[1] == "in":
                    allowed = set(clause[2])
                    rows = [r for r in rows if _m2o(r.get("field_id")) in allowed]
            return rows
        if model == "ir.default" and method == "search":
            domain = args[0] if args else []
            rows = list(self.defaults.values())
            for clause in domain:
                if not isinstance(clause, (list, tuple)):
                    continue
                key, op, val = clause[0], clause[1], clause[2]
                if key == "field_id" and op == "=":
                    rows = [r for r in rows if _m2o(r.get("field_id")) == val]
                if key == "user_id" and op == "=":
                    if val is False:
                        rows = [
                            r
                            for r in rows
                            if r.get("user_id") in (False, None) or _m2o(r.get("user_id")) is None
                        ]
                    else:
                        rows = [r for r in rows if _m2o(r.get("user_id")) == val]
            return [r["id"] for r in rows]
        if model == "ir.default" and method == "create":
            did = self._next()
            vals = dict(args[0])
            fid = vals.get("field_id")
            fname = next((f["name"] for f in self.model_fields if f["id"] == fid), str(fid))
            vals["id"] = did
            vals["field_id"] = [fid, fname]
            vals.setdefault("user_id", False)
            vals.setdefault("company_id", False)
            vals.setdefault("condition", False)
            self.defaults[did] = vals
            return did
        if model == "ir.default" and method == "write":
            for i in args[0]:
                self.defaults[i].update(args[1])
            return True
        if model == "ir.default" and method == "read":
            return [self.defaults[i] for i in args[0] if i in self.defaults]

        if model == "ir.property" and method == "search_read":
            if not self.property_exists:
                raise AssertionError("ir.property should not be queried when missing")
            return list(self.properties.values())

        if model == "ir.cron" and method == "search_read":
            rows = list(self.crons.values())
            domain = args[0] if args else []
            for clause in domain:
                if isinstance(clause, (list, tuple)) and clause[0] == "active":
                    rows = [r for r in rows if bool(r.get("active")) == clause[2]]
                if isinstance(clause, (list, tuple)) and clause[0] == "name":
                    rows = [r for r in rows if clause[2].lower() in str(r.get("name", "")).lower()]
            return rows
        if model == "ir.cron" and method == "write":
            for i in args[0]:
                self.crons[i].update(args[1])
            return True
        if model == "ir.cron" and method == "read":
            return [self.crons[i] for i in args[0] if i in self.crons]

        if model == "website.page" and method == "search_read":
            if not self.website_installed:
                raise RuntimeError("website.page missing")
            return list(self.website_pages)
        if model == "website.menu" and method == "search_read":
            if not self.website_installed:
                raise RuntimeError("website.menu missing")
            return list(self.website_menus)

        raise AssertionError(f"unexpected {model}.{method} {args}")


def _m2o(val: Any) -> int | None:
    if isinstance(val, (list, tuple)) and val:
        return int(val[0])
    if isinstance(val, int):
        return val
    return None


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _mk_connection() -> OdooConnection:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="fake-m3",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


@pytest.fixture
def fake_m3(client: TestClient):
    conn = _mk_connection()
    fake = FakeM3Odoo(website_installed=False, property_exists=True)

    def _client_from_connection(_row):
        return fake

    with patch("app.routers.config_ops.client_from_connection", _client_from_connection):
        yield conn.id, fake


def test_paperformat_list_and_upsert(client: TestClient, fake_m3) -> None:
    cid, fake = fake_m3
    listed = client.get(f"/api/connections/{cid}/config/paperformats")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "A4"
    assert listed.json()[0]["header_line"] is True

    created = client.post(
        f"/api/connections/{cid}/config/paperformats",
        json={
            "name": "Letter",
            "format": "Letter",
            "margin_top": 30,
            "header_line": False,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["name"] == "Letter"
    assert body["format"] == "Letter"
    pid = body["id"]

    updated = client.post(
        f"/api/connections/{cid}/config/paperformats",
        json={"id": pid, "margin_left": 12},
    )
    assert updated.status_code == 200
    assert updated.json()["margin_left"] == 12.0
    assert fake.paperformats[pid]["margin_left"] == 12


def test_ir_default_list_and_upsert(client: TestClient, fake_m3) -> None:
    cid, _fake = fake_m3
    empty = client.get(
        f"/api/connections/{cid}/config/defaults",
        params={"model": "res.partner"},
    )
    assert empty.status_code == 200
    assert empty.json() == []

    created = client.post(
        f"/api/connections/{cid}/config/defaults",
        json={"model": "res.partner", "field_name": "email", "value": "default@example.com"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["field_id"] == 11
    assert json.loads(created.json()["json_value"]) == "default@example.com"

    again = client.post(
        f"/api/connections/{cid}/config/defaults",
        json={
            "field_id": 11,
            "json_value": json.dumps("other@example.com"),
        },
    )
    assert again.status_code == 200
    assert again.json()["id"] == created.json()["id"]
    assert json.loads(again.json()["json_value"]) == "other@example.com"

    listed = client.get(
        f"/api/connections/{cid}/config/defaults",
        params={"model": "res.partner"},
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_ir_property_ok_and_missing(client: TestClient, fake_m3) -> None:
    cid, fake = fake_m3
    ok = client.get(f"/api/connections/{cid}/config/properties")
    assert ok.status_code == 200
    assert ok.json()[0]["name"] == "property_account_payable_id"

    fake.property_exists = False
    missing = client.get(f"/api/connections/{cid}/config/properties")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "ir.property not available on this database"


def test_ir_cron_list_and_deactivate_confirm(client: TestClient, fake_m3) -> None:
    cid, fake = fake_m3
    listed = client.get(f"/api/connections/{cid}/config/crons")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == 5
    assert listed.json()[0]["interval_type"] == "hours"
    assert listed.json()[0]["active"] is True

    denied = client.patch(
        f"/api/connections/{cid}/config/crons/5",
        json={"active": False},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["confirm_phrase"] == "I understand the risks"
    assert fake.crons[5]["active"] is True

    wrong = client.patch(
        f"/api/connections/{cid}/config/crons/5",
        json={"active": False, "confirm_advanced": True, "confirm_phrase": "wrong"},
    )
    assert wrong.status_code == 403

    deactivated = client.patch(
        f"/api/connections/{cid}/config/crons/5",
        json={"active": False, **CONFIRM},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False
    assert fake.crons[5]["active"] is False

    # Re-activate does not require confirm phrase.
    activated = client.patch(
        f"/api/connections/{cid}/config/crons/5",
        json={"active": True},
    )
    assert activated.status_code == 200
    assert activated.json()["active"] is True


def test_website_unavailable_without_module(client: TestClient, fake_m3) -> None:
    cid, fake = fake_m3
    assert fake.website_installed is False

    pages = client.get(f"/api/connections/{cid}/config/website/pages")
    assert pages.status_code == 200
    assert pages.json() == {
        "available": False,
        "reason": "website module not installed",
        "pages": None,
        "menus": None,
    }

    menus = client.get(f"/api/connections/{cid}/config/website/menus")
    assert menus.status_code == 200
    assert menus.json()["available"] is False
    assert menus.json()["reason"] == "website module not installed"


def test_website_available_when_installed(client: TestClient, fake_m3) -> None:
    cid, fake = fake_m3
    fake.website_installed = True

    pages = client.get(f"/api/connections/{cid}/config/website/pages")
    assert pages.status_code == 200
    body = pages.json()
    assert body["available"] is True
    assert body["pages"][0]["url"] == "/"

    menus = client.get(f"/api/connections/{cid}/config/website/menus")
    assert menus.status_code == 200
    assert menus.json()["available"] is True
    assert menus.json()["menus"][0]["name"] == "Home"


def test_currencies_available(client: TestClient, fake_m3) -> None:
    cid, _fake = fake_m3
    res = client.get(f"/api/connections/{cid}/config/currencies")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    assert body["rows"][0]["name"] == "USD"


def test_uom_and_fiscal_unavailable_without_modules(client: TestClient, fake_m3) -> None:
    cid, _fake = fake_m3
    uom = client.get(f"/api/connections/{cid}/config/uom")
    assert uom.status_code == 200
    assert uom.json()["available"] is False
    assert "uom" in (uom.json()["reason"] or "").lower()

    fiscal = client.get(f"/api/connections/{cid}/config/fiscal-positions")
    assert fiscal.status_code == 200
    assert fiscal.json()["available"] is False
    assert "account" in (fiscal.json()["reason"] or "").lower()


def test_currency_rates_available(client: TestClient, fake_m3) -> None:
    cid, _fake = fake_m3
    res = client.get(f"/api/connections/{cid}/config/currency-rates")
    assert res.status_code == 200
    assert res.json()["available"] is True
    assert res.json()["rows"][0]["rate"] == 1.0
