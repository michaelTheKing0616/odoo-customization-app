"""Unit tests for compat capability matrix + adapters (no live Odoo)."""

from __future__ import annotations

import pytest

from odoo_client.automation import (
    CreateActivityAction,
    CreateRecordAction,
    RelatedWriteAction,
    UpdateFieldAction,
)
from odoo_client.compat import (
    CapabilityId,
    UnsupportedOdooMajorError,
    for_major,
    ga_majors,
    parse_major,
    supported_majors,
)
from odoo_client.compat.adapters import automation_v16, automation_v19, views_v16, views_v19


def test_supported_majors_16_to_19() -> None:
    assert supported_majors() == frozenset({16, 17, 18, 19})
    assert ga_majors() == frozenset({17, 18, 19})


def test_for_major_19_18_17_are_ga() -> None:
    assert for_major(19).ga is True
    assert for_major(18).ga is True
    assert for_major(17).ga is True
    assert for_major(19).supports(CapabilityId.RELATED_WRITE_DOTTED_PATH)


def test_for_major_17_full_safe() -> None:
    caps = for_major(17)
    assert caps.ga is True
    assert caps.supports(CapabilityId.RELATED_WRITE_DOTTED_PATH)


def test_for_major_16_thinner_set() -> None:
    caps = for_major(16)
    assert caps.ga is False
    assert not caps.supports(CapabilityId.RELATED_WRITE_DOTTED_PATH)
    assert not caps.supports(CapabilityId.OBJECT_WRITE_UPDATE_PATH)
    assert caps.supports(CapabilityId.VIEW_INJECT_INHERIT)


def test_for_major_15_fails_closed() -> None:
    with pytest.raises(UnsupportedOdooMajorError):
        for_major(15)


def test_parse_major() -> None:
    assert parse_major("19.0") == 19
    assert parse_major("19.0+e") == 19
    assert parse_major("18.4") == 18
    assert parse_major("16.0") == 16


def test_related_write_update_path() -> None:
    assert (
        automation_v19.related_write_update_path("x_vehicle_id", "x_status")
        == "x_vehicle_id.x_status"
    )


def test_encode_update_and_related_write() -> None:
    upd = automation_v19.encode_update_field_server_vals(
        name="Rule",
        model_id=7,
        action=UpdateFieldAction(field_name="x_note", value="hi"),
    )
    assert upd["state"] == "object_write"
    assert upd["update_path"] == "x_note"

    rel = automation_v19.encode_related_write_server_vals(
        name="Rule",
        model_id=7,
        action=RelatedWriteAction(
            relation_field="x_vehicle_id",
            field_name="x_status",
            value="rented",
        ),
    )
    assert rel["update_path"] == "x_vehicle_id.x_status"


def test_encode_create_record_and_activity() -> None:
    rec = automation_v19.encode_create_record_server_vals(
        name="Spawn",
        model_id=1,
        target_model="res.partner",
        target_model_id=2,
        field_values={"name": "X"},
    )
    assert rec["state"] == "object_create"

    act = automation_v19.encode_create_activity_server_vals(
        name="Follow",
        model_id=1,
        action=CreateActivityAction(activity_type_id=3, summary="Ping"),
        activity_user_field_name="create_uid",
    )
    assert act["state"] == "next_activity"


def test_build_automation_blocks_code_state() -> None:
    with pytest.raises(ValueError, match="blocked"):
        automation_v19.build_automation_record_vals(
            name="Bad",
            model_id=1,
            trigger="on_create",
            active=True,
            server_vals={"state": "code", "code": "print(1)"},
        )


def test_build_automation_advanced_states_need_allow_flag() -> None:
    from odoo_client.automation import (
        FollowersAction,
        RemoveFollowersAction,
        SmsAction,
        WebhookAction,
    )

    webhook_vals = automation_v19.encode_webhook_server_vals(
        name="Hook",
        model_id=1,
        action=WebhookAction(webhook_url="https://example.com/h"),
    )
    assert webhook_vals["state"] == "webhook"
    with pytest.raises(ValueError, match="advanced"):
        automation_v19.build_automation_record_vals(
            name="Hook",
            model_id=1,
            trigger="on_create",
            active=True,
            server_vals=webhook_vals,
        )
    ok = automation_v19.build_automation_record_vals(
        name="Hook",
        model_id=1,
        trigger="on_webhook",
        active=True,
        server_vals=webhook_vals,
        filter_pre_domain="[('active','=',True)]",
        allow_advanced=True,
    )
    assert ok["trigger"] == "on_webhook"
    assert ok["filter_pre_domain"] == "[('active','=',True)]"

    sms_vals = automation_v19.encode_sms_server_vals(
        name="SMS",
        model_id=1,
        action=SmsAction(body="hi"),
        sms_template_id=9,
    )
    assert sms_vals["state"] == "sms"
    assert sms_vals["sms_template_id"] == 9

    fol = automation_v19.encode_followers_server_vals(
        name="Fol",
        model_id=1,
        action=FollowersAction(partner_ids=[3], followers_type="specific"),
    )
    assert fol["state"] == "followers"
    rem = automation_v19.encode_remove_followers_server_vals(
        name="Rem",
        model_id=1,
        action=RemoveFollowersAction(partner_ids=[3]),
    )
    assert rem["state"] == "remove_followers"
    with pytest.raises(ValueError, match="advanced"):
        automation_v19.build_automation_record_vals(
            name="Rem",
            model_id=1,
            trigger="on_create",
            active=True,
            server_vals=rem,
        )


def test_views_v19_and_v16_fallbacks() -> None:
    assert views_v19.list_type_fallbacks("list") == ["list", "tree"]
    assert views_v16.list_type_fallbacks("list") == ["tree", "list"]
    assert views_v19.list_arch_root() == "list"
    assert views_v16.list_arch_root() == "tree"
    assert views_v19.normalize_view_mode("list,form") == "list,form"
    assert views_v16.normalize_view_mode("list,form") == "tree,form"
    assert views_v19.default_window_view_mode() == "list,form"
    assert views_v16.default_window_view_mode() == "tree,form"


def test_v16_encoders_hard_refuse_update_path() -> None:
    with pytest.raises(automation_v16.UnsupportedOnOdoo16Error):
        automation_v16.related_write_update_path("a", "b")
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
                relation_field="x_partner_id",
                field_name="name",
                value="x",
            ),
        )
