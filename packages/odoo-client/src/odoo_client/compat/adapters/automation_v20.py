"""Odoo 20 automation encoding.

V11: automations stay a separate ``ir.actions.server`` (nested ``action_server_ids``).
V12: cron ``numbercall`` is removed on 18+ and must not be sent on 20.

Majors 16–19 keep their own adapter modules; do not import this file from them.
"""

from __future__ import annotations

from typing import Any

from odoo_client.compat.adapters.automation_v19 import (  # noqa: F401
    CreateActivityAction,
    CreateRecordAction,
    FollowersAction,
    MailPostAction,
    RelatedWriteAction,
    RemoveFollowersAction,
    SmsAction,
    UpdateFieldAction,
    WebhookAction,
    assert_server_state_allowed,
    build_automation_record_vals,
    encode_create_activity_server_vals,
    encode_create_record_server_vals,
    encode_followers_server_vals,
    encode_mail_post_server_vals,
    encode_object_write_button_vals,
    encode_related_write_server_vals,
    encode_remove_followers_server_vals,
    encode_sms_server_vals,
    encode_update_field_server_vals,
    encode_webhook_server_vals,
    related_write_update_path,
)


def encode_cron_vals(
    *,
    name: str,
    model_id: int,
    code: str,
    interval_number: int = 1,
    interval_type: str = "days",
    active: bool = True,
) -> dict[str, Any]:
    """``ir.cron`` vals for Odoo 20. Never emit ``numbercall`` (V12)."""
    vals: dict[str, Any] = {
        "name": name,
        "model_id": model_id,
        "state": "code",
        "code": code,
        "interval_number": interval_number,
        "interval_type": interval_type,
        "active": active,
    }
    vals.pop("numbercall", None)
    return vals


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
    "encode_cron_vals",
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
