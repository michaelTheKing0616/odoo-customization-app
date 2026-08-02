"""Live API smoke: config / menus-builder / reports against Odoo 19."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.main import app  # noqa: E402

CONFIRM = {"confirm_advanced": True, "confirm_phrase": "I understand the risks"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _connection_id(client: TestClient) -> str:
    create = client.post(
        "/api/connections",
        json={
            "name": f"Ops smoke {uuid.uuid4().hex[:6]}",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    return create.json()["id"]


@pytest.mark.integration
def test_config_company_sequences_mail_activity(client: TestClient) -> None:
    cid = _connection_id(client)
    try:
        companies = client.get(f"/api/connections/{cid}/config/companies")
        assert companies.status_code == 200
        rows = companies.json()
        assert rows
        company_id = rows[0]["id"]
        patched = client.patch(
            f"/api/connections/{cid}/config/companies/{company_id}",
            json={"website": rows[0].get("website") or "https://smoke.example"},
        )
        assert patched.status_code == 200

        seq = client.post(
            f"/api/connections/{cid}/config/sequences",
            json={
                "name": f"Smoke Seq {uuid.uuid4().hex[:6]}",
                "code": f"smoke.seq.{uuid.uuid4().hex[:6]}",
                "prefix": "SMK/",
                "padding": 4,
            },
        )
        assert seq.status_code == 201, seq.text
        seq_id = seq.json()["id"]

        langs = client.get(f"/api/connections/{cid}/config/languages")
        assert langs.status_code == 200
        assert any(l["code"] for l in langs.json())

        csv = client.get(
            f"/api/connections/{cid}/config/translations.csv",
            params={"model": "res.partner", "lang": "en_US"},
        )
        assert csv.status_code == 200
        assert "field" in csv.text or "model" in csv.text

        mail = client.post(
            f"/api/connections/{cid}/config/mail-templates",
            json={
                "name": f"Smoke Mail {uuid.uuid4().hex[:6]}",
                "model": "res.partner",
                "subject": "Smoke",
                "body_html": "<p>Hi</p>",
                "email_to": "${object.email}",
            },
        )
        assert mail.status_code == 201, mail.text

        acts = client.get(f"/api/connections/{cid}/config/activity-types")
        assert acts.status_code == 200
        assert isinstance(acts.json(), list)

        # cleanup sequence
        from odoo_client import ConnectionConfig, OdooClient

        oc = OdooClient(
            ConnectionConfig(
                url=os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
                db=os.environ.get("ODOO_DB", "odoo_dev"),
                username=os.environ.get("ODOO_USER", "admin"),
                password=os.environ.get("ODOO_PASSWORD", "admin"),
            )
        )
        oc.connect()
        oc.execute_kw("ir.sequence", "unlink", [[seq_id]])
        oc.execute_kw("mail.template", "unlink", [[mail.json()["id"]]])
    finally:
        client.delete(f"/api/connections/{cid}")


@pytest.mark.integration
def test_menus_builder_and_reports_live(client: TestClient) -> None:
    cid = _connection_id(client)
    suffix = uuid.uuid4().hex[:6]
    menu_id = None
    action_id = None
    report_id = None
    try:
        tree = client.get(f"/api/connections/{cid}/menus-builder/tree", params={"roots_only": True})
        assert tree.status_code == 200

        action = client.post(
            f"/api/connections/{cid}/menus-builder/actions",
            json={
                "name": f"Smoke Act {suffix}",
                "model": "res.partner",
                "view_mode": "list,form",
            },
        )
        assert action.status_code == 201, action.text
        action_id = action.json()["id"]

        menu = client.post(
            f"/api/connections/{cid}/menus-builder/menus",
            json={
                "name": f"Smoke Root {suffix}",
                "sequence": 95,
                "web_icon": "base,static/description/icon.png",
                "action_id": action_id,
            },
        )
        assert menu.status_code == 201, menu.text
        menu_id = menu.json()["id"]

        patched = client.patch(
            f"/api/connections/{cid}/menus-builder/menus/{menu_id}",
            json={"sequence": 96},
        )
        assert patched.status_code == 200

        papers = client.get(f"/api/connections/{cid}/reports/paperformats")
        assert papers.status_code == 200

        report = client.post(
            f"/api/connections/{cid}/reports",
            json={
                "name": f"Smoke PDF {suffix}",
                "model": "res.partner",
                "report_key": f"custom.api_smoke_{suffix}",
            },
        )
        assert report.status_code == 201, report.text
        report_id = report.json()["id"]
        listed = client.get(f"/api/connections/{cid}/reports", params={"model": "res.partner"})
        assert listed.status_code == 200
        assert any(r["id"] == report_id for r in listed.json())

        deleted = client.request(
            "DELETE",
            f"/api/connections/{cid}/reports/{report_id}",
            json=CONFIRM,
        )
        assert deleted.status_code == 200
        report_id = None

        deleted_menu = client.request(
            "DELETE",
            f"/api/connections/{cid}/menus-builder/menus/{menu_id}",
            json=CONFIRM,
        )
        assert deleted_menu.status_code == 200
        menu_id = None
    finally:
        from odoo_client import ConnectionConfig, OdooClient

        oc = OdooClient(
            ConnectionConfig(
                url=os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
                db=os.environ.get("ODOO_DB", "odoo_dev"),
                username=os.environ.get("ODOO_USER", "admin"),
                password=os.environ.get("ODOO_PASSWORD", "admin"),
            )
        )
        try:
            oc.connect()
            if report_id:
                oc.execute_kw("ir.actions.report", "unlink", [[report_id]])
            if menu_id:
                oc.execute_kw("ir.ui.menu", "unlink", [[menu_id]])
            if action_id:
                oc.execute_kw("ir.actions.act_window", "unlink", [[action_id]])
        except Exception:  # noqa: BLE001
            pass
        client.delete(f"/api/connections/{cid}")
