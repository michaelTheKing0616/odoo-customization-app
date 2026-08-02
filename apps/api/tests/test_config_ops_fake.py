"""FakeClient unit tests for config / menus-builder / reports routers."""

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


class FakeOdoo:
    """In-memory Odoo stand-in for new ops routers."""

    def __init__(self) -> None:
        self._seq = 100
        self.companies = [
            {
                "id": 1,
                "name": "My Company",
                "email": "a@b.c",
                "phone": None,
                "website": None,
                "street": None,
                "street2": None,
                "city": None,
                "zip": None,
                "vat": None,
                "company_registry": None,
                "currency_id": [1, "USD"],
            }
        ]
        self.sequences: dict[int, dict[str, Any]] = {}
        self.menus: dict[int, dict[str, Any]] = {}
        self.actions: dict[int, dict[str, Any]] = {}
        self.reports: dict[int, dict[str, Any]] = {}
        self.views: dict[int, dict[str, Any]] = {}
        self.mail_templates: dict[int, dict[str, Any]] = {}
        self.activity_types = [
            {"id": 1, "name": "To-Do", "summary": None, "icon": "fa-check", "category": None, "active": True}
        ]
        self.langs = [{"id": 1, "code": "en_US", "name": "English", "active": True}]
        self.fields = [
            {
                "id": 10,
                "name": "name",
                "ttype": "char",
                "field_description": "Name",
                "state": "base",
                "model": "res.partner",
            }
        ]
        self.paperformats = [
            {
                "id": 1,
                "name": "A4",
                "format": "A4",
                "orientation": "Portrait",
                "margin_top": 40,
                "margin_bottom": 20,
                "margin_left": 7,
                "margin_right": 7,
            }
        ]
        self.calls: list[tuple] = []

    def model_exists(self, model: str) -> bool:
        return True

    def _next(self) -> int:
        self._seq += 1
        return self._seq

    def list_mail_templates(self, *, model: str | None = None, limit: int = 200):
        rows = list(self.mail_templates.values())
        if model:
            rows = [r for r in rows if r.get("model") == model]
        return rows[:limit]

    def create_mail_template(self, **kwargs):
        tid = self._next()
        row = {"id": tid, "model": kwargs.get("model"), **kwargs}
        self.mail_templates[tid] = row
        return tid

    def create_menu(self, *, name, parent_id=None, action_id=None, sequence=10, web_icon=None):
        mid = self._next()
        action = f"ir.actions.act_window,{action_id}" if action_id else False
        self.menus[mid] = {
            "id": mid,
            "name": name,
            "parent_id": [parent_id, "Parent"] if parent_id else False,
            "action": action,
            "sequence": sequence,
            "web_icon": web_icon,
            "child_id": [],
        }
        if parent_id and parent_id in self.menus:
            self.menus[parent_id]["child_id"].append(mid)
        return mid

    def create_window_action(self, *, name, model, view_mode="list,form", domain=None, context=None):
        aid = self._next()
        self.actions[aid] = {
            "id": aid,
            "name": name,
            "res_model": model,
            "view_mode": view_mode,
            "domain": domain or False,
            "context": context or "{}",
            "target": "current",
        }
        return aid

    def ensure_app_menus(self, *, root_name, model_entries, web_icon="base,static/description/icon.png"):
        root = self.create_menu(name=root_name, web_icon=web_icon)
        ids = [root]
        for model, label in model_entries:
            aid = self.create_window_action(name=label, model=model)
            ids.append(self.create_menu(name=label, parent_id=root, action_id=aid))
        return ids

    def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
        kwargs = kwargs or {}
        self.calls.append((model, method, args, kwargs))
        if model == "res.company" and method == "search":
            return [c["id"] for c in self.companies]
        if model == "res.company" and method == "read":
            ids = args[0]
            return [dict(c) for c in self.companies if c["id"] in ids]
        if model == "res.company" and method == "write":
            ids, vals = args[0], args[1]
            for c in self.companies:
                if c["id"] in ids:
                    c.update(vals)
            return True
        if model == "ir.sequence" and method == "search":
            return list(self.sequences.keys())
        if model == "ir.sequence" and method == "read":
            return [self.sequences[i] for i in args[0] if i in self.sequences]
        if model == "ir.sequence" and method == "create":
            sid = self._next()
            vals = dict(args[0])
            vals["id"] = sid
            vals.setdefault("number_next_actual", vals.get("number_next", 1))
            vals.setdefault("active", True)
            vals.setdefault("code", False)
            vals.setdefault("prefix", False)
            vals.setdefault("suffix", False)
            self.sequences[sid] = vals
            return sid
        if model == "ir.sequence" and method == "write":
            for i in args[0]:
                self.sequences[i].update(args[1])
            return True
        if model == "ir.ui.menu" and method == "search_read":
            return list(self.menus.values())[: kwargs.get("limit", 500)]
        if model == "ir.ui.menu" and method == "read":
            return [self.menus[i] for i in args[0] if i in self.menus]
        if model == "ir.ui.menu" and method == "write":
            for i in args[0]:
                vals = dict(args[1])
                if "parent_id" in vals and vals["parent_id"] is False:
                    vals["parent_id"] = False
                elif "parent_id" in vals and isinstance(vals["parent_id"], int):
                    vals["parent_id"] = [vals["parent_id"], "P"]
                if "action" in vals and vals["action"] is False:
                    vals["action"] = False
                self.menus[i].update(vals)
            return True
        if model == "ir.ui.menu" and method == "unlink":
            for i in args[0]:
                self.menus.pop(i, None)
            return True
        if model == "ir.actions.act_window" and method == "search_read":
            return list(self.actions.values())[: kwargs.get("limit", 200)]
        if model == "ir.actions.act_window" and method == "read":
            return [self.actions[i] for i in args[0] if i in self.actions]
        if model == "ir.actions.act_window" and method == "write":
            for i in args[0]:
                self.actions[i].update(args[1])
            return True
        if model == "ir.actions.act_window" and method == "create":
            return self.create_window_action(
                name=args[0]["name"],
                model=args[0]["res_model"],
                view_mode=args[0].get("view_mode", "list,form"),
            )
        if model == "report.paperformat" and method == "search_read":
            return list(self.paperformats)
        if model == "ir.actions.report" and method == "search_read":
            return list(self.reports.values())
        if model == "ir.actions.report" and method == "read":
            return [self.reports[i] for i in args[0] if i in self.reports]
        if model == "ir.actions.report" and method == "create":
            rid = self._next()
            vals = dict(args[0])
            vals["id"] = rid
            vals.setdefault("paperformat_id", False)
            self.reports[rid] = vals
            return rid
        if model == "ir.actions.report" and method == "write":
            for i in args[0]:
                self.reports[i].update(args[1])
            return True
        if model == "ir.actions.report" and method == "unlink":
            for i in args[0]:
                self.reports.pop(i, None)
            return True
        if model == "ir.ui.view" and method == "search_read":
            domain = args[0] if args else []
            key = None
            for clause in domain:
                if isinstance(clause, (list, tuple)) and clause[0] == "key":
                    key = clause[2]
            out = [v for v in self.views.values() if key is None or v.get("key") == key]
            return out[:1]
        if model == "ir.ui.view" and method == "create":
            vid = self._next()
            vals = dict(args[0])
            vals["id"] = vid
            self.views[vid] = vals
            return vid
        if model == "ir.ui.view" and method == "write":
            for i in args[0]:
                self.views[i].update(args[1])
            return True
        if model == "mail.template" and method == "read":
            return [self.mail_templates[i] for i in args[0] if i in self.mail_templates]
        if model == "mail.template" and method == "write":
            for i in args[0]:
                self.mail_templates[i].update(args[1])
            return True
        if model == "mail.activity.type" and method == "search_read":
            return list(self.activity_types)
        if model == "mail.activity.type" and method == "create":
            tid = self._next()
            vals = dict(args[0])
            vals.update({"id": tid, "active": True, "summary": vals.get("summary"), "icon": vals.get("icon"), "category": None})
            self.activity_types.append(vals)
            return tid
        if model == "mail.activity.type" and method == "read":
            return [a for a in self.activity_types if a["id"] in args[0]]
        if model == "res.lang" and method == "search_read":
            return list(self.langs)
        if model == "ir.model.fields" and method == "search_read":
            return [
                {**f, "id": f["id"]}
                for f in self.fields
            ]
        if model == "ir.model.fields" and method == "search":
            return [f["id"] for f in self.fields]
        if model == "ir.model.fields" and method == "write":
            return True
        raise AssertionError(f"unexpected {model}.{method} {args}")


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _mk_connection() -> OdooConnection:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="fake-ops",
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
def fake_odoo(client: TestClient):
    conn = _mk_connection()
    fake = FakeOdoo()

    def _client_from_connection(_row):
        return fake

    with patch("app.routers.config_ops.client_from_connection", _client_from_connection), patch(
        "app.routers.menus_builder.client_from_connection", _client_from_connection
    ), patch("app.routers.reports.client_from_connection", _client_from_connection):
        yield conn.id, fake


def test_fake_config_company_and_sequence(client: TestClient, fake_odoo) -> None:
    cid, fake = fake_odoo
    res = client.get(f"/api/connections/{cid}/config/companies")
    assert res.status_code == 200
    assert res.json()[0]["name"] == "My Company"

    patched = client.patch(
        f"/api/connections/{cid}/config/companies/1",
        json={"city": "Lagos"},
    )
    assert patched.status_code == 200
    assert patched.json()["city"] == "Lagos"

    created = client.post(
        f"/api/connections/{cid}/config/sequences",
        json={"name": "Test", "code": "test.code", "prefix": "T/", "padding": 3},
    )
    assert created.status_code == 201
    assert created.json()["prefix"] == "T/" or created.json()["name"] == "Test"


def test_fake_mail_activity_translations(client: TestClient, fake_odoo) -> None:
    cid, fake = fake_odoo
    mail = client.post(
        f"/api/connections/{cid}/config/mail-templates",
        json={
            "name": "Hello",
            "model": "res.partner",
            "subject": "Hi",
            "body_html": "<p>x</p>",
            "email_to": "${object.email}",
        },
    )
    assert mail.status_code == 201

    acts = client.get(f"/api/connections/{cid}/config/activity-types")
    assert acts.status_code == 200
    assert acts.json()[0]["name"] == "To-Do"

    created_act = client.post(
        f"/api/connections/{cid}/config/activity-types",
        json={"name": "Call back"},
    )
    assert created_act.status_code == 201

    csv = client.get(
        f"/api/connections/{cid}/config/translations.csv",
        params={"model": "res.partner", "lang": "en_US", "include_menus": False},
    )
    assert csv.status_code == 200
    assert "name" in csv.text


def test_fake_menus_builder_crud(client: TestClient, fake_odoo) -> None:
    cid, fake = fake_odoo
    action = client.post(
        f"/api/connections/{cid}/menus-builder/actions",
        json={"name": "Partners", "model": "res.partner"},
    )
    assert action.status_code == 201
    aid = action.json()["id"]

    menu = client.post(
        f"/api/connections/{cid}/menus-builder/menus",
        json={
            "name": "App",
            "web_icon": "base,static/description/icon.png",
            "action_id": aid,
        },
    )
    assert menu.status_code == 201
    mid = menu.json()["id"]

    tree = client.get(f"/api/connections/{cid}/menus-builder/tree")
    assert tree.status_code == 200
    assert any(m["id"] == mid for m in tree.json())

    patched = client.patch(
        f"/api/connections/{cid}/menus-builder/menus/{mid}",
        json={"sequence": 20},
    )
    assert patched.status_code == 200

    deleted = client.request(
        "DELETE",
        f"/api/connections/{cid}/menus-builder/menus/{mid}",
        json={"confirm_advanced": True, "confirm_phrase": "I understand the risks"},
    )
    assert deleted.status_code == 200


def test_fake_reports_crud(client: TestClient, fake_odoo) -> None:
    cid, fake = fake_odoo
    papers = client.get(f"/api/connections/{cid}/reports/paperformats")
    assert papers.status_code == 200
    assert papers.json()[0]["name"] == "A4"

    created = client.post(
        f"/api/connections/{cid}/reports",
        json={
            "name": "Partner PDF",
            "model": "res.partner",
            "report_key": "custom.partner_pdf",
        },
    )
    assert created.status_code == 201, created.text
    rid = created.json()["id"]
    assert created.json()["report_name"] == "custom.partner_pdf"

    listed = client.get(f"/api/connections/{cid}/reports")
    assert any(r["id"] == rid for r in listed.json())

    updated = client.patch(
        f"/api/connections/{cid}/reports/{rid}",
        json={"name": "Partner PDF v2"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Partner PDF v2"

    deleted = client.request(
        "DELETE",
        f"/api/connections/{cid}/reports/{rid}",
        json={"confirm_advanced": True, "confirm_phrase": "I understand the risks"},
    )
    assert deleted.status_code == 200


def test_menus_delete_requires_confirm(client: TestClient, fake_odoo) -> None:
    cid, _fake = fake_odoo
    menu = client.post(
        f"/api/connections/{cid}/menus-builder/menus",
        json={"name": "Temp"},
    )
    mid = menu.json()["id"]
    denied = client.request(
        "DELETE",
        f"/api/connections/{cid}/menus-builder/menus/{mid}",
        json={},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["requires_confirmation"] is True
