"""EE view save gating + grid arch (TIER-5)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

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
from odoo_client.view_arch import GridViewSpec, parse_grid_arch, render_grid_arch  # noqa: E402


def test_grid_arch_round_trip() -> None:
    spec = GridViewSpec(
        string="Planning",
        row_field="user_id",
        col_field="project_id",
        measure="planned_hours",
        date_start="date_start",
        date_stop="date_stop",
    )
    arch = render_grid_arch(spec)
    assert 'row_field="user_id"' in arch
    parsed = parse_grid_arch(arch)
    assert parsed.row_field == "user_id"
    assert parsed.measure == "planned_hours"


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def test_community_blocks_gantt_save(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="comm-views",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    fake = MagicMock()
    with patch("app.routers.views.client_from_connection", return_value=fake):
        res = client.post(
            f"/api/connections/{cid}/views/save",
            json={
                "model": "project.task",
                "view_type": "gantt",
                "spec": {"string": "Tasks", "date_start": "date_start"},
                "create_if_missing": True,
            },
        )
    assert res.status_code == 409
    assert res.json()["detail"]["capability"] == "views_enterprise_types"


def test_save_view_auto_creates_missing_custom_model(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="designer-autocreate",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    fake = MagicMock()
    fake.model_exists.return_value = False
    fake.find_view.return_value = None
    fake.create_view.return_value = MagicMock(
        id=99,
        model_dump=lambda: {
            "id": 99,
            "name": "x_ticket.form",
            "model": "x_ticket",
            "type": "form",
            "arch": "<form/>",
        },
    )
    fake.create_model.return_value = MagicMock(model="x_ticket", id=7)

    with patch("app.routers.views.client_from_connection", return_value=fake):
        res = client.post(
            f"/api/connections/{cid}/views/save",
            json={
                "model": "x_ticket",
                "view_type": "form",
                "spec": {"string": "Ticket", "fields": []},
                "create_if_missing": True,
                "strategy": "inherit",
            },
        )

    assert res.status_code == 200, res.text
    fake.create_model.assert_called_once()
    assert fake.create_model.call_args.kwargs.get("with_defaults") is True


def test_repair_designer_inherit_rewrites_full_replace(client: TestClient) -> None:
    from odoo_client.view_arch import (
        ButtonNode,
        FieldNode,
        FormViewSpec,
        GroupNode,
        NotebookNode,
        PageNode,
        render_form_arch,
        render_inherit_replace_arch,
    )

    db = SessionLocal()
    try:
        row = OdooConnection(
            name="designer-repair",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    dumped = FormViewSpec(
        string="Bills",
        header_buttons=[
            ButtonNode(string="Send", name="action_invoice_sent", type="object"),
        ],
        children=[
            GroupNode(string="Main", children=[FieldNode(name="partner_id")]),
            GroupNode(
                string="TEST GROUP",
                children=[FieldNode(name="x_demo_note"), FieldNode(name="x_test_field")],
            ),
            NotebookNode(
                pages=[PageNode(string="Other Info", children=[FieldNode(name="narration")])]
            ),
        ],
    )
    bad_arch = render_inherit_replace_arch("form", render_form_arch(dumped))

    fake = MagicMock()
    fake.find_designer_inherit_rows.return_value = [
        {
            "id": 55,
            "name": "account.move.designer.form",
            "model": "account.move",
            "type": "form",
            "arch": bad_arch,
            "inherit_id": [10, "account.view_move_form"],
            "mode": "extension",
            "priority": 99,
        }
    ]
    fake.list_custom_field_inject_names.return_value = []
    fake.find_view.return_value = MagicMock(arch="<form><field name='partner_id'/></form>")
    fake.update_view_arch.return_value = MagicMock(
        id=55,
        model_dump=lambda: {
            "id": 55,
            "name": "account.move.designer.form",
            "model": "account.move",
            "type": "form",
            "arch": "<data/>",
        },
    )

    snap = MagicMock(id="snap-repair-1")
    with (
        patch("app.routers.views.client_from_connection", return_value=fake),
        patch("app.snapshots.snapshot_view", return_value=snap),
    ):
        res = client.post(
            f"/api/connections/{cid}/views/designer-inherit/repair",
            json={"model": "account.move", "view_type": "form"},
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["action"] == "repaired"
    assert "x_demo_note" in body["kept_custom_fields"]
    written = fake.update_view_arch.call_args.args[1]
    assert "//sheet" in written
    assert "TEST GROUP" in written
    assert "<header" not in written
    assert "<notebook" not in written


def test_save_additive_rewrites_x_even_when_combined_has_them(
    client: TestClient,
) -> None:
    """Create-field inject puts x_* on combined; Save must still write designer.form."""
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="designer-additive-x",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    primary = MagicMock(
        id=10,
        name="account.view_move_form",
        arch="<form><sheet><field name='partner_id'/></sheet></form>",
    )
    fake = MagicMock()
    fake.model_exists.return_value = True
    fake.find_view.return_value = primary
    fake.execute_kw.side_effect = lambda *a, **k: (
        []  # no existing designer child search; then inject search
        if a[1] == "search"
        else None
    )
    fake.get_combined_view_arch.return_value = (
        "<form><sheet>"
        "<field name='partner_id'/>"
        "<field name='x_demo_note'/>"
        "</sheet></form>"
    )
    fake.create_inherit_view.return_value = MagicMock(
        id=88,
        model_dump=lambda: {
            "id": 88,
            "name": "account.move.designer.form",
            "model": "account.move",
            "type": "form",
            "arch": "<data/>",
        },
    )
    fake.unlink_view = MagicMock()

    snap = MagicMock(id="snap-add-1")
    with (
        patch("app.routers.views.client_from_connection", return_value=fake),
        patch("app.snapshots.snapshot_view", return_value=snap),
    ):
        res = client.post(
            f"/api/connections/{cid}/views/save",
            json={
                "model": "account.move",
                "view_type": "form",
                "strategy": "inherit",
                "create_if_missing": True,
                "spec": {
                    "string": "Bills",
                    "children": [
                        {
                            "kind": "group",
                            "string": "Main",
                            "children": [{"kind": "field", "name": "partner_id"}],
                        },
                        {
                            "kind": "group",
                            "string": "My Group",
                            "children": [
                                {"kind": "field", "name": "x_demo_note"},
                            ],
                        },
                    ],
                },
            },
        )
    assert res.status_code == 200, res.text
    assert fake.create_inherit_view.called
    written = fake.create_inherit_view.call_args.kwargs["arch"]
    assert "My Group" in written
    assert 'name="x_demo_note"' in written
    assert "<header" not in written


def test_unlink_designer_inherit_requires_confirm(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="designer-unlink",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    fake = MagicMock()
    with patch("app.routers.views.client_from_connection", return_value=fake):
        res = client.post(
            f"/api/connections/{cid}/views/designer-inherit/unlink",
            json={"model": "account.move", "view_type": "form"},
        )
    assert res.status_code == 403
    assert res.json()["detail"]["requires_confirmation"] is True
    fake.unlink_view.assert_not_called()


def test_unlink_designer_inherit_with_confirm(client: TestClient) -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="designer-unlink-ok",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="19.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        cid = row.id
    finally:
        db.close()

    fake = MagicMock()
    fake.find_designer_inherit_rows.return_value = [
        {
            "id": 77,
            "name": "account.move.designer.form",
            "model": "account.move",
            "type": "form",
            "arch": "<data/>",
            "inherit_id": [10, "parent"],
            "mode": "extension",
        }
    ]
    fake.list_custom_field_inject_names.return_value = ["account.move.custom.x_demo_note.form"]
    snap = MagicMock(id="snap-unlink-1")
    with (
        patch("app.routers.views.client_from_connection", return_value=fake),
        patch("app.snapshots.snapshot_view", return_value=snap),
        patch("app.snapshots.save_snapshot", return_value=snap),
    ):
        res = client.post(
            f"/api/connections/{cid}/views/designer-inherit/unlink",
            json={
                "model": "account.move",
                "view_type": "form",
                "confirm_advanced": True,
                "confirm_phrase": "I understand the risks",
            },
        )
    assert res.status_code == 200, res.text
    assert res.json()["action"] == "unlinked"
    fake.unlink_view.assert_called_once_with(77)
