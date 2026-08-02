"""Live RPC smoke against optional Docker Odoo 16 (M3 experimental).

  docker compose -p odoo16 -f docker/docker-compose.odoo16.yml up -d
  ./docker/init-db-16.sh
  ODOO16_URL=http://127.0.0.1:8072

Note: related_write / object_write update_path are NOT in ODOO_16_CAPABILITIES.
"""

from __future__ import annotations

import os
import uuid

import pytest

from odoo_client import (
    ConnectionConfig,
    CreateAccessRightRequest,
    CreateFieldRequest,
    CreateMailPostServerAction,
    CreateModelRequest,
    CreateNextActivityServerAction,
    CreateRecordRuleRequest,
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
from odoo_client.compat import CapabilityId, UnsupportedCapabilityError
from odoo_client.compat.adapters import automation_v16
from odoo_client.view_arch import ButtonNode


@pytest.fixture(scope="module")
def client16() -> OdooClient:
    config = ConnectionConfig(
        url=os.environ.get("ODOO16_URL", "http://127.0.0.1:8072"),
        db=os.environ.get("ODOO16_DB", "odoo16_dev"),
        username=os.environ.get("ODOO16_USER", "admin"),
        password=os.environ.get("ODOO16_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 16 not reachable for M3 smoke: {exc}")
    if c.capabilities.major != 16:
        pytest.skip(f"Expected major 16, got {c.capabilities.major}")
    return c


@pytest.mark.integration
def test_server_is_odoo_16(client16: OdooClient) -> None:
    assert str(client16.server_version().get("server_version", "")).startswith("16")
    assert client16.capabilities.ga is False
    assert not client16.capabilities.supports(CapabilityId.RELATED_WRITE_DOTTED_PATH)
    assert not client16.capabilities.supports(CapabilityId.OBJECT_WRITE_UPDATE_PATH)
    assert client16.capabilities.supports(CapabilityId.VIEW_INJECT_INHERIT)


@pytest.mark.integration
def test_related_write_refused_on_16(client16: OdooClient) -> None:
    with pytest.raises(UnsupportedCapabilityError):
        client16.capabilities.require(CapabilityId.RELATED_WRITE_DOTTED_PATH)


@pytest.mark.integration
def test_encode_and_update_path_still_refused_16(client16: OdooClient) -> None:
    """Live + adapter: update_path / related_write encoders stay hard-refused on 16."""
    with pytest.raises(UnsupportedCapabilityError):
        client16.capabilities.require(CapabilityId.OBJECT_WRITE_UPDATE_PATH)

    with pytest.raises(automation_v16.UnsupportedOnOdoo16Error):
        automation_v16.related_write_update_path("x_vehicle_id", "x_status")
    with pytest.raises(automation_v16.UnsupportedOnOdoo16Error):
        automation_v16.encode_update_field_server_vals(
            name="n",
            model_id=1,
            action=UpdateFieldAction(field_name="x_note", value="x"),
        )
    with pytest.raises(automation_v16.UnsupportedOnOdoo16Error):
        automation_v16.encode_related_write_server_vals(
            name="n",
            model_id=1,
            action=RelatedWriteAction(
                relation_field="x_vehicle_id",
                field_name="x_status",
                value="rented",
            ),
        )

    # Client path must refuse before any RPC mutation.
    with pytest.raises(UnsupportedCapabilityError):
        client16.create_automation(
            CreateAutomationRequest(
                name="must-refuse-related",
                model="res.partner",
                trigger=AutomationTrigger.ON_CREATE,
                action=RelatedWriteAction(
                    relation_field="parent_id",
                    field_name="name",
                    value="x",
                ),
            )
        )
    with pytest.raises(UnsupportedCapabilityError):
        client16.create_automation(
            CreateAutomationRequest(
                name="must-refuse-update",
                model="res.partner",
                trigger=AutomationTrigger.ON_CREATE,
                action=UpdateFieldAction(field_name="name", value="x"),
            )
        )


@pytest.mark.integration
def test_model_field_and_smart_buttons_16(client16: OdooClient) -> None:
    suffix = uuid.uuid4().hex[:6]
    model = f"x_m3_16_{suffix}"
    client16.create_model(CreateModelRequest(model=model, name=f"M3 16 {suffix}"))
    client16.create_field(
        CreateFieldRequest(
            model=model,
            name="x_note",
            ttype=FieldType.CHAR,
            field_description="Note",
        )
    )
    # Stock partner smart buttons inherit
    primary = client16.find_view(
        "res.partner", "form", primary_only=True
    ) or client16.find_view("res.partner", "form")
    assert primary is not None
    arch_before = primary.arch or ""
    view_name = f"res.partner.studio.smart_buttons.m3_16_{suffix}"
    created = client16.inject_smart_buttons_into_form(
        "res.partner",
        [
            ButtonNode(
                string=f"M316 {suffix}",
                name="1",
                type="action",
                class_name="oe_stat_button",
                icon="fa-list",
            )
        ],
        view_name=view_name,
    )
    try:
        after = client16.get_view(primary.id)
        assert (after.arch or "") == arch_before
    finally:
        client16.execute_kw("ir.ui.view", "unlink", [[created.id]])


@pytest.mark.integration
def test_window_action_uses_tree_view_mode_16(client16: OdooClient) -> None:
    """create_window_action normalizes list→tree on Odoo 16."""
    suffix = uuid.uuid4().hex[:6]
    action_id = client16.create_window_action(
        name=f"M3 16 partners {suffix}",
        model="res.partner",
        view_mode="list,form",
    )
    try:
        action = client16.execute_kw(
            "ir.actions.act_window",
            "read",
            [[action_id]],
            {"fields": ["name", "res_model", "view_mode"]},
        )[0]
        assert action["res_model"] == "res.partner"
        assert action["view_mode"] == "tree,form", (
            f"expected tree,form on ≤17, got {action['view_mode']!r}"
        )
        assert "list" not in action["view_mode"].split(",")
    finally:
        client16.execute_kw("ir.actions.act_window", "unlink", [[action_id]])


@pytest.mark.integration
def test_menu_create_16(client16: OdooClient) -> None:
    """Root + child menu with window action binding."""
    suffix = uuid.uuid4().hex[:6]
    root_name = f"M3 16 App {suffix}"
    child_name = f"Partners {suffix}"

    root_id = client16.create_menu(
        name=root_name,
        sequence=90,
        web_icon="base,static/description/icon.png",
    )
    assert root_id > 0
    action_id = client16.create_window_action(
        name=f"M3 16 menu partners {suffix}",
        model="res.partner",
        view_mode="list,form",
    )
    child_id = client16.create_menu(
        name=child_name,
        parent_id=root_id,
        action_id=action_id,
        sequence=10,
    )
    try:
        rows = client16.execute_kw(
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
        action = client16.execute_kw(
            "ir.actions.act_window",
            "read",
            [[action_id]],
            {"fields": ["view_mode"]},
        )[0]
        assert action["view_mode"] == "tree,form"
    finally:
        client16.execute_kw("ir.ui.menu", "unlink", [[child_id, root_id]])
        client16.execute_kw("ir.actions.act_window", "unlink", [[action_id]])


@pytest.mark.integration
def test_qweb_report_create_16(client16: OdooClient) -> None:
    """Optional: QWeb PDF report via public ORM if available on 16."""
    suffix = uuid.uuid4().hex[:6]
    report_key = f"custom.m3_16_report_{suffix}"
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
            client16.execute_kw(
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
            client16.execute_kw(
                "ir.actions.report",
                "create",
                [
                    {
                        "name": f"M3 16 Report {suffix}",
                        "model": "res.partner",
                        "report_type": "qweb-pdf",
                        "report_name": report_key,
                    }
                ],
            )
        )
        report = client16.execute_kw(
            "ir.actions.report",
            "read",
            [[report_id]],
            {"fields": ["name", "model", "report_name", "report_type"]},
        )[0]
        assert report["report_name"] == report_key
        assert report["model"] == "res.partner"
    except OdooClientError as exc:
        pytest.skip(f"QWeb report create not available on this Odoo 16: {exc}")
    finally:
        if report_id:
            try:
                client16.execute_kw("ir.actions.report", "unlink", [[report_id]])
            except OdooClientError:
                pass
        if view_id:
            try:
                client16.execute_kw("ir.ui.view", "unlink", [[view_id]])
            except OdooClientError:
                pass


@pytest.mark.integration
def test_access_rule_create_16(client16: OdooClient) -> None:
    """ir.model.access and/or ir.rule create via public ORM (experimental 16)."""
    suffix = uuid.uuid4().hex[:6]
    model = f"x_m3_16_acl_{suffix}"
    access_id: int | None = None
    rule_id: int | None = None
    try:
        client16.create_model(CreateModelRequest(model=model, name=f"M3 16 ACL {suffix}"))
        created = client16.create_access_right(
            CreateAccessRightRequest(
                model=model,
                name=f"access_{model}_user",
                perm_read=True,
                perm_write=True,
                perm_create=True,
                perm_unlink=False,
            )
        )
        access_id = int(created.id)
        assert access_id > 0
        row = client16.get_access_right(access_id)
        assert row.model == model
        assert row.perm_read is True
        assert row.perm_unlink is False

        rule = client16.create_record_rule(
            CreateRecordRuleRequest(
                model=model,
                name=f"rule_{model}_{suffix}",
                domain_force="[('id','!=',False)]",
                perm_read=True,
                perm_write=True,
                perm_create=True,
                perm_unlink=False,
            )
        )
        rule_id = int(rule.id)
        assert rule_id > 0
        fetched = client16.get_record_rule(rule_id)
        assert fetched.model == model
        assert "[('id','!=',False)]" in (fetched.domain_force or "").replace(" ", "")
    except OdooClientError as exc:
        pytest.skip(f"Access rule create not available on this Odoo 16: {exc}")
    finally:
        if rule_id:
            try:
                client16.delete_rule(rule_id)
            except OdooClientError:
                pass
        if access_id:
            try:
                client16.delete_access(access_id)
            except OdooClientError:
                pass


@pytest.mark.integration
def test_mail_post_and_next_activity_16(client16: OdooClient) -> None:
    """Honesty: mail_post / next_activity create on 16, or skip-with-reason."""
    # Selection gate — if states missing, skip honestly (do not claim support).
    try:
        fields_get = client16.execute_kw(
            "ir.actions.server",
            "fields_get",
            [["state"]],
            {"attributes": ["selection"]},
        )
    except OdooClientError as exc:
        pytest.skip(f"Cannot read ir.actions.server.state on Odoo 16: {exc}")

    selection = {
        str(key)
        for key, _label in (fields_get.get("state") or {}).get("selection") or []
    }
    if "mail_post" not in selection and "next_activity" not in selection:
        pytest.skip(
            "Odoo 16 ir.actions.server has neither mail_post nor next_activity "
            f"in state selection ({sorted(selection)!r}) — unsupported on this build"
        )

    # res.partner is mail-threaded on stock Community; prefer it over custom models.
    partner_ids = client16.execute_kw("res.partner", "search", [[]], {"limit": 1})
    if not partner_ids:
        pytest.skip("No res.partner row for mail_post/next_activity smoke on Odoo 16")
    partner_id = int(partner_ids[0])
    created_ids: list[int] = []

    try:
        if "next_activity" in selection:
            types = client16.list_activity_types(limit=1)
            if not types:
                pytest.skip(
                    "next_activity in selection but no mail.activity.type on this Odoo 16"
                )
            na = client16.create_next_activity_server_action(
                CreateNextActivityServerAction(
                    name=f"M3 16 activity {uuid.uuid4().hex[:6]}",
                    model="res.partner",
                    activity_type_id=int(types[0]["id"]),
                    summary="M3 16 follow-up",
                    bind_to_model=False,
                )
            )
            assert na.id > 0
            assert na.state == "next_activity"
            created_ids.append(int(na.id))
            client16.run_server_action(na.id, model="res.partner", record_id=partner_id)

        if "mail_post" in selection:
            mp = client16.create_mail_post_server_action(
                CreateMailPostServerAction(
                    name=f"M3 16 mail {uuid.uuid4().hex[:6]}",
                    model="res.partner",
                    mail_post_method="note",
                    subject="M3 16",
                    body_html="<p>M3 16 note</p>",
                    bind_to_model=False,
                )
            )
            assert mp.id > 0
            assert mp.state == "mail_post"
            created_ids.append(int(mp.id))
            client16.run_server_action(mp.id, model="res.partner", record_id=partner_id)
    except (OdooClientError, UnsupportedCapabilityError) as exc:
        pytest.skip(f"mail_post/next_activity not usable on this Odoo 16: {exc}")
    finally:
        for action_id in created_ids:
            try:
                client16.execute_kw("ir.actions.server", "unlink", [[action_id]])
            except OdooClientError:
                pass


@pytest.mark.integration
def test_field_inject_inherit_on_partner_16(client16: OdooClient) -> None:
    """Inherit field inject on stock model leaves primary arch intact (experimental 16)."""
    client16.capabilities.require(CapabilityId.VIEW_INJECT_INHERIT)
    suffix = uuid.uuid4().hex[:6]
    field_name = f"x_m3_16_lbl_{suffix}"
    client16.create_field(
        CreateFieldRequest(
            model="res.partner",
            name=field_name,
            field_description=f"M3 16 Label {suffix}",
            ttype=FieldType.CHAR,
        )
    )
    primary = client16.find_view(
        "res.partner", "form", primary_only=True
    ) or client16.find_view("res.partner", "form")
    assert primary is not None
    arch_before = primary.arch or ""
    updated = client16.inject_field_into_views(
        "res.partner", field_name, view_types=["form"], strategy="inherit"
    )
    assert updated
    try:
        after = client16.get_view(primary.id)
        assert (after.arch or "") == arch_before
        child = updated[0]
        assert field_name in (child.arch or "")
        assert child.name == f"res.partner.custom.{field_name}.form"
        assert "xpath" in (child.arch or "")
    finally:
        for view in updated:
            try:
                client16.execute_kw("ir.ui.view", "unlink", [[view.id]])
            except OdooClientError:
                pass


@pytest.mark.integration
def test_adversarial_capability_refuse_exact_messages_16(client16: OdooClient) -> None:
    """Capability.require + encoder hard-fail messages stay precise on live 16."""
    with pytest.raises(UnsupportedCapabilityError) as cap_exc:
        client16.capabilities.require(CapabilityId.OBJECT_WRITE_UPDATE_PATH)
    assert "object_write_update_path" in str(cap_exc.value)
    assert "Odoo 16" in str(cap_exc.value)

    with pytest.raises(UnsupportedCapabilityError) as rel_exc:
        client16.capabilities.require(CapabilityId.RELATED_WRITE_DOTTED_PATH)
    assert "related_write_dotted_path" in str(rel_exc.value)

    with pytest.raises(automation_v16.UnsupportedOnOdoo16Error) as enc:
        automation_v16.encode_update_field_server_vals(
            name="adversarial",
            model_id=1,
            action=UpdateFieldAction(field_name="x_note", value="nope"),
        )
    assert "object_write update_path" in str(enc.value)
    assert "not supported on Odoo 16" in str(enc.value)
    assert "'x_note'" in str(enc.value)
    assert "adversarial" in str(enc.value)


@pytest.mark.integration
def test_adversarial_empty_partner_domain_search_16(client16: OdooClient) -> None:
    """Empty-match domain returns [] — no accidental full-table hit for Power Ops style search."""
    ids = client16.execute_kw(
        "res.partner",
        "search",
        [[("id", "=", -1)]],
        {"limit": 10000},
    )
    assert ids == []
