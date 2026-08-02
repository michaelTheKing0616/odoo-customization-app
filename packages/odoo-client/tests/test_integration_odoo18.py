"""Live RPC smoke against optional Docker Odoo 18 (GA alongside 19).

Requires:
  docker compose -p odoo18 -f docker/docker-compose.odoo18.yml up -d
  ./docker/init-db-18.sh

Env defaults: ODOO18_URL=http://127.0.0.1:8070 ODOO18_DB=odoo18_dev
"""

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
from odoo_client.automation import (
    AutomationTrigger,
    CreateAutomationRequest,
    RelatedWriteAction,
    UpdateFieldAction,
)
from odoo_client.client import OdooClientError
from odoo_client.compat import CapabilityId
from odoo_client.security import CreateAccessRightRequest
from odoo_client.view_arch import ButtonNode


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@pytest.fixture(scope="module")
def client18() -> OdooClient:
    config = ConnectionConfig(
        url=_env("ODOO18_URL", "http://127.0.0.1:8070"),
        db=_env("ODOO18_DB", "odoo18_dev"),
        username=_env("ODOO18_USER", "admin"),
        password=_env("ODOO18_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 18 not reachable for M2 smoke: {exc}")
    if c.capabilities.major != 18:
        pytest.skip(f"Expected major 18, got {c.capabilities.major}")
    return c


@pytest.mark.integration
def test_server_is_odoo_18(client18: OdooClient) -> None:
    version = client18.server_version()
    assert str(version.get("server_version", "")).startswith("18")
    assert client18.capabilities.supports(CapabilityId.RELATED_WRITE_DOTTED_PATH)
    assert client18.capabilities.ga is True


@pytest.mark.integration
def test_create_model_field_and_update_automation(client18: OdooClient) -> None:
    """Safe subset: custom model + field + object_write automation."""
    suffix = uuid.uuid4().hex[:6]
    model = f"x_m2_smoke_{suffix}"
    client18.create_model(CreateModelRequest(model=model, name=f"M2 Smoke {suffix}"))
    client18.create_field(
        CreateFieldRequest(
            model=model,
            name="x_note",
            ttype=FieldType.CHAR,
            field_description="Note",
        )
    )
    auto = client18.create_automation(
        CreateAutomationRequest(
            name=f"M2 set note {suffix}",
            model=model,
            trigger=AutomationTrigger.ON_CREATE,
            action=UpdateFieldAction(field_name="x_note", value="ok18"),
        )
    )
    assert auto.id > 0
    assert client18.capabilities.supports(CapabilityId.OBJECT_WRITE_UPDATE_PATH)


@pytest.mark.integration
def test_related_write_dotted_object_write_18(client18: OdooClient) -> None:
    """M2: dotted update_path related_write works on Community 18."""
    client18.ensure_module_installed("base_automation")
    client18.capabilities.require(CapabilityId.RELATED_WRITE_DOTTED_PATH)

    suffix = uuid.uuid4().hex[:6]
    vehicle_model = f"x_rw18_veh_{suffix}"
    contract_model = f"x_rw18_ctr_{suffix}"

    client18.create_model(
        CreateModelRequest(name=f"RW18 Vehicle {suffix}", model=vehicle_model),
        with_defaults=True,
    )
    time.sleep(0.3)
    if not client18.field_exists(vehicle_model, "x_status"):
        client18.create_field(
            CreateFieldRequest(
                model=vehicle_model,
                name="x_status",
                field_description="Status",
                ttype=FieldType.CHAR,
            )
        )
    client18.create_model(
        CreateModelRequest(name=f"RW18 Contract {suffix}", model=contract_model),
        with_defaults=True,
    )
    time.sleep(0.3)
    client18.create_field(
        CreateFieldRequest(
            model=contract_model,
            name="x_vehicle_id",
            field_description="Vehicle",
            ttype=FieldType.MANY2ONE,
            relation=vehicle_model,
        )
    )
    if not client18.field_exists(contract_model, "x_status"):
        client18.create_field(
            CreateFieldRequest(
                model=contract_model,
                name="x_status",
                field_description="Status",
                ttype=FieldType.CHAR,
            )
        )

    created = client18.create_automation(
        CreateAutomationRequest(
            name=f"RW18 vehicle rented {suffix}",
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
    sa_id = int(created.action_server_ids[0])
    sa = client18.execute_kw(
        "ir.actions.server",
        "read",
        [[sa_id]],
        {"fields": ["state", "update_path", "value"]},
    )[0]
    assert sa["state"] == "object_write"
    assert sa["update_path"] == "x_vehicle_id.x_status"

    veh_id = int(
        client18.execute_kw(
            vehicle_model, "create", [{"x_name": "Car A", "x_status": "available"}]
        )
    )
    ctr_id = int(
        client18.execute_kw(
            contract_model,
            "create",
            [{"x_name": "CNT", "x_vehicle_id": veh_id, "x_status": "draft"}],
        )
    )
    client18.execute_kw(contract_model, "write", [[ctr_id], {"x_status": "confirmed"}])
    time.sleep(0.5)
    status = client18.execute_kw(vehicle_model, "read", [[veh_id], ["x_status"]])[0][
        "x_status"
    ]
    assert status == "rented", f"expected rented after related_write, got {status!r}"


@pytest.mark.integration
def test_smart_buttons_inherit_keeps_primary_arch_18(client18: OdooClient) -> None:
    """M2: smart button inject uses inherit; does not mutate primary form arch."""
    client18.capabilities.require(CapabilityId.SMART_BUTTON_INHERIT_BOX)

    primary = client18.find_view(
        "res.partner", "form", primary_only=True
    ) or client18.find_view("res.partner", "form")
    assert primary is not None
    arch_before = primary.arch or ""
    assert arch_before

    suffix = uuid.uuid4().hex[:6]
    view_name = f"res.partner.studio.smart_buttons.m2_{suffix}"
    created = client18.inject_smart_buttons_into_form(
        "res.partner",
        [
            ButtonNode(
                string=f"M2 Smoke {suffix}",
                name="1",
                type="action",
                class_name="oe_stat_button",
                icon="fa-list",
            )
        ],
        view_name=view_name,
    )
    try:
        after = client18.get_view(primary.id)
        assert (after.arch or "") == arch_before
        assert created.name == view_name
        assert "xpath" in (created.arch or "")
    finally:
        client18.execute_kw("ir.ui.view", "unlink", [[created.id]])


@pytest.mark.integration
def test_field_inject_inherit_on_partner_18(client18: OdooClient) -> None:
    """M2: inherit field inject on stock model leaves primary arch intact."""
    client18.capabilities.require(CapabilityId.VIEW_INJECT_INHERIT)
    suffix = uuid.uuid4().hex[:6]
    field_name = f"x_m2_lbl_{suffix}"
    client18.create_field(
        CreateFieldRequest(
            model="res.partner",
            name=field_name,
            field_description=f"M2 Label {suffix}",
            ttype=FieldType.CHAR,
        )
    )
    primary = client18.find_view(
        "res.partner", "form", primary_only=True
    ) or client18.find_view("res.partner", "form")
    assert primary is not None
    arch_before = primary.arch or ""
    updated = client18.inject_field_into_views(
        "res.partner", field_name, view_types=["form"], strategy="inherit"
    )
    assert updated
    after = client18.get_view(primary.id)
    assert (after.arch or "") == arch_before
    child = updated[0]
    assert field_name in (child.arch or "")
    assert child.name == f"res.partner.custom.{field_name}.form"


@pytest.mark.integration
def test_menu_create_and_report_qweb_18(client18: OdooClient) -> None:
    """M2 broader UAT: menus + QWeb PDF report create/read/cleanup on 18."""
    suffix = uuid.uuid4().hex[:6]
    root_name = f"M2 App {suffix}"
    child_name = f"Partners {suffix}"
    report_key = f"custom.m2_report_{suffix}"

    root_id = client18.create_menu(
        name=root_name,
        sequence=90,
        web_icon="base,static/description/icon.png",
    )
    assert root_id > 0
    action_id = client18.create_window_action(
        name=f"M2 partners {suffix}",
        model="res.partner",
        view_mode="list,form",
    )
    child_id = client18.create_menu(
        name=child_name,
        parent_id=root_id,
        action_id=action_id,
        sequence=10,
    )
    view_id: int | None = None
    report_id: int | None = None
    try:
        rows = client18.execute_kw(
            "ir.ui.menu",
            "read",
            [[root_id, child_id]],
            {"fields": ["name", "parent_id", "action", "web_icon"]},
        )
        by_id = {int(r["id"]): r for r in rows}
        assert by_id[root_id]["web_icon"]
        assert by_id[child_id]["parent_id"][0] == root_id
        assert f"ir.actions.act_window,{action_id}" in str(
            by_id[child_id].get("action") or ""
        )

        arch = (
            f'<t t-name="{report_key}">'
            '<t t-call="web.html_container">'
            '<t t-foreach="docs" t-as="doc">'
            '<div class="page"><h2 t-field="doc.display_name"/></div>'
            "</t></t></t>"
        )
        view_id = int(
            client18.execute_kw(
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
            client18.execute_kw(
                "ir.actions.report",
                "create",
                [
                    {
                        "name": f"M2 Report {suffix}",
                        "model": "res.partner",
                        "report_type": "qweb-pdf",
                        "report_name": report_key,
                    }
                ],
            )
        )
        report = client18.execute_kw(
            "ir.actions.report",
            "read",
            [[report_id]],
            {"fields": ["name", "model", "report_name", "report_type"]},
        )[0]
        assert report["report_name"] == report_key
        assert report["model"] == "res.partner"
        views = client18.execute_kw(
            "ir.ui.view",
            "search_read",
            [[("key", "=", report_key), ("type", "=", "qweb")]],
            {"fields": ["arch"], "limit": 1},
        )
        assert views and report_key in (views[0].get("arch") or "")
    finally:
        if report_id:
            client18.execute_kw("ir.actions.report", "unlink", [[report_id]])
        if view_id:
            client18.execute_kw("ir.ui.view", "unlink", [[view_id]])
        client18.execute_kw("ir.ui.menu", "unlink", [[child_id, root_id]])
        client18.execute_kw("ir.actions.act_window", "unlink", [[action_id]])


@pytest.mark.integration
def test_list_models_and_update_view_arch_18(client18: OdooClient) -> None:
    """Deepen 18 live suite toward 19 coverage (list models + view arch write)."""
    models = client18.list_models(limit=500)
    assert len(models) >= 1
    assert any(m.model == "res.partner" for m in models)

    suffix = uuid.uuid4().hex[:6]
    model = f"x_v18_{suffix}"
    client18.create_model(
        CreateModelRequest(model=model, name=f"V18 {suffix}"),
        with_defaults=True,
    )
    views = client18.list_views(model)
    form = next((v for v in views if v.type == "form"), None)
    assert form is not None and form.arch
    arch_before = form.arch
    # Inherit-style soft touch: re-write same arch must succeed
    client18.update_view_arch(form.id, arch_before)
    after = client18.get_view(form.id)
    assert (after.arch or "") == arch_before


@pytest.mark.integration
def test_access_right_create_18(client18: OdooClient) -> None:
    """ACL create on custom model (parity with deeper 19/16 suites)."""
    suffix = uuid.uuid4().hex[:6]
    model = f"x_acl18_{suffix}"
    client18.create_model(CreateModelRequest(model=model, name=f"ACL18 {suffix}"))
    access = client18.create_access_right(
        CreateAccessRightRequest(
            model=model,
            name=f"access_{model}_user",
            perm_read=True,
            perm_write=True,
            perm_create=True,
            perm_unlink=False,
        )
    )
    assert access.id > 0
    assert access.perm_read is True
    assert access.perm_unlink is False
