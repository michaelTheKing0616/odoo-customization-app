"""Odoo 19 automation / object_write encoding (extracted from OdooClient).

Pure vals builders — RPC validation (M2O checks, field ids) stays on the client.
"""

from __future__ import annotations

import pprint
from typing import Any

from odoo_client.automation import (
    ADVANCED_SERVER_STATES,
    BLOCKED_SERVER_STATES,
    CreateActivityAction,
    CreateRecordAction,
    FollowersAction,
    MailPostAction,
    RelatedWriteAction,
    RemoveFollowersAction,
    SmsAction,
    UpdateFieldAction,
    WebhookAction,
)


def related_write_update_path(relation_field: str, field_name: str) -> str:
    """Odoo 19 dotted ``update_path`` for related object_write."""
    return f"{relation_field}.{field_name}"


def encode_update_field_server_vals(
    *,
    name: str,
    model_id: int,
    action: UpdateFieldAction,
) -> dict[str, Any]:
    return {
        "name": f"{name} / update {action.field_name}",
        "model_id": model_id,
        "state": "object_write",
        "update_path": action.field_name,
        "evaluation_type": "value",
        "value": action.value,
    }


def encode_related_write_server_vals(
    *,
    name: str,
    model_id: int,
    action: RelatedWriteAction,
) -> dict[str, Any]:
    path = related_write_update_path(action.relation_field, action.field_name)
    return {
        "name": f"{name} / related {path}",
        "model_id": model_id,
        "state": "object_write",
        "update_path": path,
        "evaluation_type": "value",
        "value": action.value,
    }


def encode_create_activity_server_vals(
    *,
    name: str,
    model_id: int,
    action: CreateActivityAction,
    activity_user_field_name: str | None = None,
) -> dict[str, Any]:
    server_vals: dict[str, Any] = {
        "name": f"{name} / activity",
        "model_id": model_id,
        "state": "next_activity",
        "activity_type_id": action.activity_type_id,
        "activity_summary": action.summary,
        "activity_user_type": action.user_type,
    }
    if action.note:
        server_vals["activity_note"] = action.note
    if action.user_type == "specific":
        if not action.user_id:
            raise ValueError(
                "create_activity with user_type=specific requires user_id"
            )
        server_vals["activity_user_id"] = action.user_id
    else:
        if not activity_user_field_name:
            raise ValueError(
                "create_activity with user_type=generic requires activity_user_field_name"
            )
        server_vals["activity_user_field_name"] = activity_user_field_name
    return server_vals


def encode_create_record_server_vals(
    *,
    name: str,
    model_id: int,
    target_model: str,
    target_model_id: int,
    field_values: dict[str, str],
) -> dict[str, Any]:
    value_literal = pprint.pformat(dict(field_values), width=120)
    return {
        "name": f"{name} / create {target_model}",
        "model_id": model_id,
        "state": "object_create",
        "crud_model_id": target_model_id,
        "value": value_literal,
    }


def encode_mail_post_server_vals(
    *,
    name: str,
    model_id: int,
    template_id: int,
    mail_post_method: str,
) -> dict[str, Any]:
    return {
        "name": f"{name} / mail_post",
        "model_id": model_id,
        "state": "mail_post",
        "template_id": template_id,
        "mail_post_method": mail_post_method,
    }


def encode_webhook_server_vals(
    *,
    name: str,
    model_id: int,
    action: WebhookAction,
    webhook_field_ids: list[int] | None = None,
) -> dict[str, Any]:
    vals: dict[str, Any] = {
        "name": f"{name} / webhook",
        "model_id": model_id,
        "state": "webhook",
        "webhook_url": action.webhook_url.strip(),
    }
    if webhook_field_ids:
        vals["webhook_field_ids"] = [(6, 0, list(webhook_field_ids))]
    return vals


def encode_sms_server_vals(
    *,
    name: str,
    model_id: int,
    action: SmsAction,
    sms_template_id: int,
) -> dict[str, Any]:
    return {
        "name": f"{name} / sms",
        "model_id": model_id,
        "state": "sms",
        "sms_template_id": sms_template_id,
        "sms_method": action.sms_method,
    }


def encode_followers_server_vals(
    *,
    name: str,
    model_id: int,
    action: FollowersAction,
) -> dict[str, Any]:
    vals: dict[str, Any] = {
        "name": f"{name} / followers",
        "model_id": model_id,
        "state": "followers",
        "followers_type": action.followers_type,
    }
    if action.partner_ids:
        vals["partner_ids"] = [(6, 0, list(action.partner_ids))]
    if action.followers_type == "generic" and action.followers_partner_field_name:
        vals["followers_partner_field_name"] = action.followers_partner_field_name
    return vals


def encode_remove_followers_server_vals(
    *,
    name: str,
    model_id: int,
    action: RemoveFollowersAction,
) -> dict[str, Any]:
    vals: dict[str, Any] = {
        "name": f"{name} / remove_followers",
        "model_id": model_id,
        "state": "remove_followers",
    }
    if action.partner_ids:
        vals["partner_ids"] = [(6, 0, list(action.partner_ids))]
    return vals


def encode_object_write_button_vals(
    *,
    name: str,
    model_id: int,
    field_name: str,
    value: str,
    bind_to_model: bool,
) -> dict[str, Any]:
    """Form-bound object_write (header/action button), Odoo 19 update_path shape."""
    vals: dict[str, Any] = {
        "name": name,
        "model_id": model_id,
        "state": "object_write",
        "update_path": field_name,
        "evaluation_type": "value",
        "value": value,
        "usage": "ir_actions_server",
    }
    if bind_to_model:
        vals["binding_model_id"] = model_id
        vals["binding_type"] = "action"
        vals["binding_view_types"] = "form,list"
    return vals


def assert_server_state_allowed(state: str, *, allow_advanced: bool = False) -> None:
    """Refuse blocked states; allow ADVANCED_SERVER_STATES only when requested."""
    if state in ADVANCED_SERVER_STATES:
        if allow_advanced:
            return
        raise ValueError(
            f"Server action state {state!r} requires advanced confirmation "
            "(pass allow_advanced=True)"
        )
    if state in BLOCKED_SERVER_STATES:
        raise ValueError(f"Server action state {state!r} is blocked")


def build_automation_record_vals(
    *,
    name: str,
    model_id: int,
    trigger: str,
    active: bool,
    server_vals: dict[str, Any],
    filter_domain: str | None = None,
    filter_pre_domain: str | None = None,
    trigger_field_ids: list[int] | None = None,
    trg_date_id: int | None = None,
    trg_date_range: int | None = None,
    trg_date_range_type: str | None = None,
    trg_date_range_mode: str | None = None,
    allow_advanced: bool = False,
) -> dict[str, Any]:
    assert_server_state_allowed(
        str(server_vals.get("state") or ""), allow_advanced=allow_advanced
    )
    auto_vals: dict[str, Any] = {
        "name": name,
        "model_id": model_id,
        "trigger": trigger,
        "active": active,
        "action_server_ids": [(0, 0, server_vals)],
    }
    if filter_domain:
        auto_vals["filter_domain"] = filter_domain
    if filter_pre_domain:
        auto_vals["filter_pre_domain"] = filter_pre_domain
    if trigger_field_ids:
        auto_vals["trigger_field_ids"] = [(6, 0, trigger_field_ids)]
    if trigger == "on_time" and trg_date_id is not None:
        auto_vals["trg_date_id"] = trg_date_id
        if trg_date_range is not None:
            auto_vals["trg_date_range"] = trg_date_range
        if trg_date_range_type:
            auto_vals["trg_date_range_type"] = trg_date_range_type
        if trg_date_range_mode:
            auto_vals["trg_date_range_mode"] = trg_date_range_mode
    return auto_vals


# Re-export action types for adapter consumers
__all__ = [
    "CreateActivityAction",
    "CreateRecordAction",
    "FollowersAction",
    "MailPostAction",
    "RelatedWriteAction",
    "RemoveFollowersAction",
    "SmsAction",
    "UpdateFieldAction",
    "WebhookAction",
    "assert_server_state_allowed",
    "build_automation_record_vals",
    "encode_create_activity_server_vals",
    "encode_create_record_server_vals",
    "encode_followers_server_vals",
    "encode_mail_post_server_vals",
    "encode_object_write_button_vals",
    "encode_related_write_server_vals",
    "encode_remove_followers_server_vals",
    "encode_sms_server_vals",
    "encode_update_field_server_vals",
    "encode_webhook_server_vals",
    "related_write_update_path",
]
