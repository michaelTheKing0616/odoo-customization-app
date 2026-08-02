"""Live RPC smoke against optional Docker Odoo 17 (GA alongside 18/19).

  docker compose -p odoo17 -f docker/docker-compose.odoo17.yml up -d
  ./docker/init-db-17.sh
  ODOO17_URL=http://127.0.0.1:8071
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


@pytest.fixture(scope="module")
def client17() -> OdooClient:
    config = ConnectionConfig(
        url=os.environ.get("ODOO17_URL", "http://127.0.0.1:8071"),
        db=os.environ.get("ODOO17_DB", "odoo17_dev"),
        username=os.environ.get("ODOO17_USER", "admin"),
        password=os.environ.get("ODOO17_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 17 not reachable for M3 smoke: {exc}")
    if c.capabilities.major != 17:
        pytest.skip(f"Expected major 17, got {c.capabilities.major}")
    return c


@pytest.mark.integration
def test_server_is_odoo_17(client17: OdooClient) -> None:
    assert str(client17.server_version().get("server_version", "")).startswith("17")
    assert client17.capabilities.ga is True
    assert client17.capabilities.supports(CapabilityId.RELATED_WRITE_DOTTED_PATH)


@pytest.mark.integration
def test_model_field_update_automation_17(client17: OdooClient) -> None:
    suffix = uuid.uuid4().hex[:6]
    model = f"x_m3_17_{suffix}"
    client17.create_model(CreateModelRequest(model=model, name=f"M3 17 {suffix}"))
    client17.create_field(
        CreateFieldRequest(
            model=model,
            name="x_note",
            ttype=FieldType.CHAR,
            field_description="Note",
        )
    )
    auto = client17.create_automation(
        CreateAutomationRequest(
            name=f"M3 17 note {suffix}",
            model=model,
            trigger=AutomationTrigger.ON_CREATE,
            action=UpdateFieldAction(field_name="x_note", value="ok17"),
        )
    )
    assert auto.id > 0


@pytest.mark.integration
def test_related_write_dotted_object_write_17(client17: OdooClient) -> None:
    """M3: dotted update_path related_write works on Community 17."""
    client17.ensure_module_installed("base_automation")
    client17.capabilities.require(CapabilityId.RELATED_WRITE_DOTTED_PATH)

    suffix = uuid.uuid4().hex[:6]
    vehicle_model = f"x_rw17_veh_{suffix}"
    contract_model = f"x_rw17_ctr_{suffix}"

    client17.create_model(
        CreateModelRequest(name=f"RW17 Vehicle {suffix}", model=vehicle_model),
        with_defaults=True,
    )
    time.sleep(0.3)
    if not client17.field_exists(vehicle_model, "x_status"):
        client17.create_field(
            CreateFieldRequest(
                model=vehicle_model,
                name="x_status",
                field_description="Status",
                ttype=FieldType.CHAR,
            )
        )
    client17.create_model(
        CreateModelRequest(name=f"RW17 Contract {suffix}", model=contract_model),
        with_defaults=True,
    )
    time.sleep(0.3)
    client17.create_field(
        CreateFieldRequest(
            model=contract_model,
            name="x_vehicle_id",
            field_description="Vehicle",
            ttype=FieldType.MANY2ONE,
            relation=vehicle_model,
        )
    )
    if not client17.field_exists(contract_model, "x_status"):
        client17.create_field(
            CreateFieldRequest(
                model=contract_model,
                name="x_status",
                field_description="Status",
                ttype=FieldType.CHAR,
            )
        )

    created = client17.create_automation(
        CreateAutomationRequest(
            name=f"RW17 vehicle rented {suffix}",
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
    sa = client17.execute_kw(
        "ir.actions.server",
        "read",
        [[sa_id]],
        {"fields": ["state", "update_path", "value"]},
    )[0]
    assert sa["state"] == "object_write"
    assert sa["update_path"] == "x_vehicle_id.x_status"

    veh_id = int(
        client17.execute_kw(
            vehicle_model, "create", [{"x_name": "Car A", "x_status": "available"}]
        )
    )
    ctr_id = int(
        client17.execute_kw(
            contract_model,
            "create",
            [{"x_name": "CNT", "x_vehicle_id": veh_id, "x_status": "draft"}],
        )
    )
    client17.execute_kw(contract_model, "write", [[ctr_id], {"x_status": "confirmed"}])
    time.sleep(0.5)
    status = client17.execute_kw(vehicle_model, "read", [[veh_id], ["x_status"]])[0][
        "x_status"
    ]
    assert status == "rented", f"expected rented after related_write, got {status!r}"


@pytest.mark.integration
def test_window_action_menu_view_mode_tree_17(client17: OdooClient) -> None:
    """create_window_action normalizes list→tree; menu create binds action."""
    suffix = uuid.uuid4().hex[:6]
    root_name = f"M3 17 App {suffix}"
    child_name = f"Partners {suffix}"

    root_id = client17.create_menu(
        name=root_name,
        sequence=90,
        web_icon="base,static/description/icon.png",
    )
    assert root_id > 0
    action_id = client17.create_window_action(
        name=f"M3 17 partners {suffix}",
        model="res.partner",
        view_mode="list,form",
    )
    child_id = client17.create_menu(
        name=child_name,
        parent_id=root_id,
        action_id=action_id,
        sequence=10,
    )
    try:
        action = client17.execute_kw(
            "ir.actions.act_window",
            "read",
            [[action_id]],
            {"fields": ["name", "res_model", "view_mode"]},
        )[0]
        assert action["res_model"] == "res.partner"
        assert action["view_mode"] == "tree,form", (
            f"expected tree,form on ≤17, got {action['view_mode']!r}"
        )

        rows = client17.execute_kw(
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
    finally:
        client17.execute_kw("ir.ui.menu", "unlink", [[child_id, root_id]])
        client17.execute_kw("ir.actions.act_window", "unlink", [[action_id]])


@pytest.mark.integration
def test_qweb_report_create_17(client17: OdooClient) -> None:
    """Minimal QWeb PDF report via public ORM (no dedicated client helper)."""
    # Client has create_menu / create_window_action but no create_report helper —
    # prove ir.ui.view (qweb) + ir.actions.report create/read/cleanup like 18/19.
    suffix = uuid.uuid4().hex[:6]
    report_key = f"custom.m3_17_report_{suffix}"
    view_id: int | None = None
    report_id: int | None = None
    try:
        arch = (
            f'<t t-name="{report_key}">'
            '<t t-call="web.html_container">'
            '<t t-foreach="docs" t-as="doc">'
            '<div class="page"><h2 t-field="doc.display_name"/></div>'
            "</t></t></t>"
        )
        view_id = int(
            client17.execute_kw(
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
            client17.execute_kw(
                "ir.actions.report",
                "create",
                [
                    {
                        "name": f"M3 17 Report {suffix}",
                        "model": "res.partner",
                        "report_type": "qweb-pdf",
                        "report_name": report_key,
                    }
                ],
            )
        )
        report = client17.execute_kw(
            "ir.actions.report",
            "read",
            [[report_id]],
            {"fields": ["name", "model", "report_name", "report_type"]},
        )[0]
        assert report["report_name"] == report_key
        assert report["model"] == "res.partner"
        views = client17.execute_kw(
            "ir.ui.view",
            "search_read",
            [[("key", "=", report_key), ("type", "=", "qweb")]],
            {"fields": ["arch"], "limit": 1},
        )
        assert views and report_key in (views[0].get("arch") or "")
    except OdooClientError as exc:
        pytest.skip(f"QWeb report create not available on this Odoo 17: {exc}")
    finally:
        if report_id:
            try:
                client17.execute_kw("ir.actions.report", "unlink", [[report_id]])
            except OdooClientError:
                pass
        if view_id:
            try:
                client17.execute_kw("ir.ui.view", "unlink", [[view_id]])
            except OdooClientError:
                pass


@pytest.mark.integration
def test_adversarial_list_as_list_type_refused_on_17(client17: OdooClient) -> None:
    """Odoo 17 is GA but still omits list_as_list_type — tree-primary views."""
    assert client17.capabilities.ga is True
    assert client17.capabilities.supports(CapabilityId.RELATED_WRITE_DOTTED_PATH)
    assert not client17.capabilities.supports(CapabilityId.LIST_AS_LIST_TYPE)
    with pytest.raises(Exception) as exc:
        client17.capabilities.require(CapabilityId.LIST_AS_LIST_TYPE)
    from odoo_client.compat import UnsupportedCapabilityError

    assert isinstance(exc.value, UnsupportedCapabilityError)
    assert "list_as_list_type" in str(exc.value)
    assert "Odoo 17" in str(exc.value)


@pytest.mark.integration
def test_adversarial_empty_domain_search_17(client17: OdooClient) -> None:
    ids = client17.execute_kw(
        "res.partner",
        "search",
        [[("id", "=", -1)]],
        {"limit": 10000},
    )
    assert ids == []
