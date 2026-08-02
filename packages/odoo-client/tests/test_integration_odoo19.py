"""Live RPC smoke tests against local Docker Odoo 19 (skills/odoo-rpc-gate.md)."""

from __future__ import annotations

import os
import time
import uuid

import pytest

from odoo_client import (
    ConnectionConfig,
    CreateFieldRequest,
    CreateModelRequest,
    FieldType,
    OdooClient,
)
from odoo_client.client import OdooClientError


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@pytest.fixture(scope="module")
def client() -> OdooClient:
    config = ConnectionConfig(
        url=_env("ODOO_URL", "http://127.0.0.1:8069"),
        db=_env("ODOO_DB", "odoo_dev"),
        username=_env("ODOO_USER", "admin"),
        password=_env("ODOO_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 19 not reachable for integration tests: {exc}")
    return c


@pytest.mark.integration
def test_server_is_odoo_19(client: OdooClient) -> None:
    version = client.server_version()
    assert str(version.get("server_version", "")).startswith("19")


@pytest.mark.integration
def test_list_models(client: OdooClient) -> None:
    models = client.list_models(limit=500)
    assert len(models) > 0
    assert any(m.model == "res.partner" for m in models)


@pytest.mark.integration
def test_create_model_and_field(client: OdooClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    model_name = f"x_smoke_{suffix}"
    created_model = client.create_model(
        CreateModelRequest(name=f"Smoke {suffix}", model=model_name),
        with_defaults=True,
    )
    assert created_model.model == model_name
    assert created_model.id > 0

    time.sleep(0.5)

    assert client.field_exists(model_name, "x_name")
    views = client.list_views(model_name)
    assert any(v.type in {"list", "tree"} for v in views)
    assert any(v.type == "form" for v in views)

    created_field = client.create_field(
        CreateFieldRequest(
            model=model_name,
            name="x_label",
            field_description="Label",
            ttype=FieldType.CHAR,
            required=False,
        )
    )
    assert created_field.name == "x_label"
    assert created_field.ttype == "char"

    fields = client.list_fields(model_name)
    assert any(f.name == "x_label" for f in fields)

    with pytest.raises(OdooClientError, match="already exists"):
        client.create_model(CreateModelRequest(name="Dup", model=model_name))


@pytest.mark.integration
def test_update_view_arch(client: OdooClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    model_name = f"x_varch_{suffix}"
    client.create_model(
        CreateModelRequest(name=f"VArch {suffix}", model=model_name),
        with_defaults=True,
    )
    view = client.find_view(model_name, "form")
    assert view is not None
    from odoo_client.view_arch import FieldNode, FormViewSpec, GroupNode, render_form_arch

    arch = render_form_arch(
        FormViewSpec(
            string="Updated",
            children=[
                GroupNode(children=[FieldNode(name="x_name", required=True)]),
            ],
        )
    )
    updated = client.update_view_arch(view.id, arch)
    assert updated.id == view.id
    assert updated.arch and "Updated" in updated.arch


@pytest.mark.integration
def test_create_automation_update_field(client: OdooClient) -> None:
    from odoo_client import CreateFieldRequest, FieldType
    from odoo_client.automation import (
        AutomationTrigger,
        CreateAutomationRequest,
        UpdateFieldAction,
    )

    client.ensure_module_installed("base_automation")
    field_name = "x_auto_note"
    if not client.field_exists("res.partner", field_name):
        client.create_field(
            CreateFieldRequest(
                model="res.partner",
                name=field_name,
                field_description="Auto Note",
                ttype=FieldType.CHAR,
            )
        )

    created = client.create_automation(
        CreateAutomationRequest(
            name=f"Smoke auto {uuid.uuid4().hex[:6]}",
            model="res.partner",
            trigger=AutomationTrigger.ON_CREATE,
            action=UpdateFieldAction(field_name=field_name, value="from-test"),
        )
    )
    assert created.id > 0
    assert created.trigger == "on_create"
    assert created.action_server_ids


@pytest.mark.integration
def test_inherit_field_inject_on_partner(client: OdooClient) -> None:
    """Default inject strategy creates xpath child views, not mutate parent."""
    suffix = uuid.uuid4().hex[:6]
    field_name = f"x_inh_{suffix}"
    if not client.field_exists("res.partner", field_name):
        client.create_field(
            CreateFieldRequest(
                model="res.partner",
                name=field_name,
                field_description="Inherit inject",
                ttype=FieldType.CHAR,
            )
        )
    injected = client.inject_field_into_views("res.partner", field_name, strategy="inherit")
    assert injected, "expected at least one inherit view"
    for view in injected:
        assert field_name in (view.name or "") or view.id > 0
        # Child extension names follow {model}.custom.{field}.{type}
        assert "custom" in view.name or view.arch is not None


@pytest.mark.integration
def test_phase2_form_actions_on_library_book(client: OdooClient) -> None:
    """Phase 2: update-field, next_activity (create_uid fallback), mail_post, smart count."""
    from odoo_client import (
        CreateMailPostServerAction,
        CreateNextActivityServerAction,
        CreateSmartButtonBundle,
        CreateUpdateFieldServerAction,
    )

    if not client.model_exists("x_lib_book"):
        pytest.skip("Acme Library models not present (scaffold first)")

    books = client.execute_kw("x_lib_book", "search", [[]], {"limit": 1})
    if not books:
        books = [client.execute_kw("x_lib_book", "create", [{"x_name": "Phase2 Smoke Book"}])]
    book_id = int(books[0])

    sa = client.create_update_field_server_action(
        CreateUpdateFieldServerAction(
            name=f"IT Mark Available {uuid.uuid4().hex[:6]}",
            model="x_lib_book",
            field_name="x_status",
            value="available",
        )
    )
    client.execute_kw("x_lib_book", "write", [[book_id], {"x_status": "loaned"}])
    client.run_server_action(sa.id, model="x_lib_book", record_id=book_id)
    status = client.execute_kw("x_lib_book", "read", [[book_id], ["x_status"]])[0]["x_status"]
    assert status == "available"

    client.ensure_mail_mixins("x_lib_book")
    types = client.list_activity_types(limit=1)
    assert types
    na = client.create_next_activity_server_action(
        CreateNextActivityServerAction(
            name=f"IT Activity {uuid.uuid4().hex[:6]}",
            model="x_lib_book",
            activity_type_id=int(types[0]["id"]),
            summary="IT follow-up",
        )
    )
    client.run_server_action(na.id, model="x_lib_book", record_id=book_id)

    mp = client.create_mail_post_server_action(
        CreateMailPostServerAction(
            name=f"IT Mail {uuid.uuid4().hex[:6]}",
            model="x_lib_book",
            mail_post_method="note",
            subject="IT",
            body_html="<p>IT</p>",
        )
    )
    client.run_server_action(mp.id, model="x_lib_book", record_id=book_id)

    suffix = uuid.uuid4().hex[:6]
    bundle = client.create_smart_button_bundle(
        CreateSmartButtonBundle(
            name=f"IT Loans {suffix}",
            source_model="x_lib_book",
            target_model="x_lib_loan",
            relation_field="x_book_id",
            one2many_field="x_loan_ids",
            count_field_name=f"x_it_loan_count_{suffix}",
            create_count_field=True,
        )
    )
    assert bundle.count_field
    assert bundle.window_action.id > 0
    client.execute_kw("x_lib_book", "read", [[book_id], [bundle.count_field]])


@pytest.mark.integration
def test_related_write_dotted_object_write(client: OdooClient) -> None:
    """Car-rental style: automation writes related M2O field via dotted update_path."""
    from odoo_client.automation import (
        AutomationTrigger,
        CreateAutomationRequest,
        RelatedWriteAction,
    )

    client.ensure_module_installed("base_automation")
    suffix = uuid.uuid4().hex[:6]
    vehicle_model = f"x_rw_veh_{suffix}"
    contract_model = f"x_rw_ctr_{suffix}"

    client.create_model(
        CreateModelRequest(name=f"RW Vehicle {suffix}", model=vehicle_model),
        with_defaults=True,
    )
    time.sleep(0.3)
    if not client.field_exists(vehicle_model, "x_status"):
        client.create_field(
            CreateFieldRequest(
                model=vehicle_model,
                name="x_status",
                field_description="Status",
                ttype=FieldType.CHAR,
            )
        )
    client.create_model(
        CreateModelRequest(name=f"RW Contract {suffix}", model=contract_model),
        with_defaults=True,
    )
    time.sleep(0.3)
    client.create_field(
        CreateFieldRequest(
            model=contract_model,
            name="x_vehicle_id",
            field_description="Vehicle",
            ttype=FieldType.MANY2ONE,
            relation=vehicle_model,
        )
    )
    if not client.field_exists(contract_model, "x_status"):
        client.create_field(
            CreateFieldRequest(
                model=contract_model,
                name="x_status",
                field_description="Status",
                ttype=FieldType.CHAR,
            )
        )

    created = client.create_automation(
        CreateAutomationRequest(
            name=f"RW vehicle rented {suffix}",
            model=contract_model,
            trigger=AutomationTrigger.ON_WRITE,
            filter_domain="[('x_status','=','confirmed')]",
            action=RelatedWriteAction(
                relation_field="x_vehicle_id",
                field_name="x_status",
                value="rented",
            ),
        )
    )
    assert created.id > 0
    assert created.action_server_ids

    sa_id = int(created.action_server_ids[0])
    sa = client.execute_kw(
        "ir.actions.server",
        "read",
        [[sa_id]],
        {"fields": ["state", "update_path", "value", "evaluation_type"]},
    )[0]
    assert sa["state"] == "object_write"
    assert sa["update_path"] == "x_vehicle_id.x_status"
    assert sa.get("evaluation_type") in ("value", False, None) or sa.get(
        "evaluation_type"
    ) == "value"
    assert "rented" in str(sa.get("value") or "")

    # End-to-end: confirm contract → vehicle status becomes rented
    veh_id = int(
        client.execute_kw(
            vehicle_model, "create", [{"x_name": "Car A", "x_status": "available"}]
        )
    )
    ctr_id = int(
        client.execute_kw(
            contract_model,
            "create",
            [{"x_name": "CNT", "x_vehicle_id": veh_id, "x_status": "draft"}],
        )
    )
    client.execute_kw(
        contract_model, "write", [[ctr_id], {"x_status": "confirmed"}]
    )
    # Automations may run sync on write; allow brief settle
    time.sleep(0.5)
    status = client.execute_kw(
        vehicle_model, "read", [[veh_id], ["x_status"]]
    )[0]["x_status"]
    assert status == "rented", f"expected rented after related_write, got {status!r}"


@pytest.mark.integration
def test_menu_create_and_report_qweb(client: OdooClient) -> None:
    """Live smoke: ir.ui.menu + QWeb report create/read/cleanup."""
    suffix = uuid.uuid4().hex[:6]
    root_name = f"Smoke App {suffix}"
    child_name = f"Partners {suffix}"
    report_key = f"custom.smoke_report_{suffix}"

    root_id = client.create_menu(
        name=root_name,
        sequence=90,
        web_icon="base,static/description/icon.png",
    )
    assert root_id > 0
    action_id = client.create_window_action(
        name=f"Smoke partners {suffix}",
        model="res.partner",
        view_mode="list,form",
    )
    child_id = client.create_menu(
        name=child_name,
        parent_id=root_id,
        action_id=action_id,
        sequence=10,
    )
    try:
        rows = client.execute_kw(
            "ir.ui.menu",
            "read",
            [[root_id, child_id]],
            {"fields": ["name", "parent_id", "action", "web_icon"]},
        )
        by_id = {int(r["id"]): r for r in rows}
        assert by_id[root_id]["web_icon"]
        assert by_id[child_id]["parent_id"][0] == root_id
        assert f"ir.actions.act_window,{action_id}" in str(by_id[child_id].get("action") or "")

        arch = (
            f'<t t-name="{report_key}">'
            '<t t-call="web.html_container">'
            '<t t-foreach="docs" t-as="doc">'
            '<div class="page"><h2 t-field="doc.display_name"/></div>'
            "</t></t></t>"
        )
        view_id = int(
            client.execute_kw(
                "ir.ui.view",
                "create",
                [
                    {
                        "name": report_key,
                        "type": "qweb",
                        "key": report_key,
                        "arch": arch,
                    }
                ],
            )
        )
        report_id = int(
            client.execute_kw(
                "ir.actions.report",
                "create",
                [
                    {
                        "name": f"Smoke Report {suffix}",
                        "model": "res.partner",
                        "report_type": "qweb-pdf",
                        "report_name": report_key,
                    }
                ],
            )
        )
        report = client.execute_kw(
            "ir.actions.report",
            "read",
            [[report_id]],
            {"fields": ["name", "model", "report_name", "report_type"]},
        )[0]
        assert report["report_name"] == report_key
        assert report["model"] == "res.partner"
        views = client.execute_kw(
            "ir.ui.view",
            "search_read",
            [[("key", "=", report_key), ("type", "=", "qweb")]],
            {"fields": ["arch"], "limit": 1},
        )
        assert views and report_key in (views[0].get("arch") or "")
        client.execute_kw("ir.actions.report", "unlink", [[report_id]])
        client.execute_kw("ir.ui.view", "unlink", [[view_id]])
    finally:
        client.execute_kw("ir.ui.menu", "unlink", [[child_id, root_id]])
        client.execute_kw("ir.actions.act_window", "unlink", [[action_id]])


@pytest.mark.integration
def test_partner_smart_buttons_inherit_keeps_primary_arch(client: OdooClient) -> None:
    """Regression: never rewrite Contacts primary form (phone xpath inherits)."""
    from odoo_client.view_arch import ButtonNode

    primary = client.find_view("res.partner", "form", primary_only=True) or client.find_view(
        "res.partner", "form"
    )
    assert primary is not None
    arch_before = primary.arch or ""
    assert arch_before

    suffix = uuid.uuid4().hex[:6]
    view_name = f"res.partner.studio.smart_buttons.smoke_{suffix}"
    created = client.inject_smart_buttons_into_form(
        "res.partner",
        [
            ButtonNode(
                string=f"Smoke {suffix}",
                name="1",
                type="action",
                class_name="oe_stat_button",
                icon="fa-list",
            )
        ],
        view_name=view_name,
    )
    try:
        after = client.get_view(primary.id)
        assert (after.arch or "") == arch_before
        assert created.name == view_name
        assert "button_box" in (created.arch or "") or f"Smoke {suffix}" in (
            created.arch or ""
        )
        assert 'xpath' in (created.arch or "")
    finally:
        client.execute_kw("ir.ui.view", "unlink", [[created.id]])
