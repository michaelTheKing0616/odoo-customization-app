"""Odoo 16 automation encoding.

Dotted ``update_path`` / related_write are **not** in ODOO_16_CAPABILITIES.
Create-record / activity / mail_post encoders still reuse v19 shapes where the
capability is enabled.

Even if a caller skips ``capabilities.require``, related/update_path encoders
hard-raise here so v16 cannot accidentally emit update_path-shaped vals.
"""

from __future__ import annotations

from typing import Any

from odoo_client.automation import (
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
from odoo_client.compat.adapters.automation_v19 import (  # noqa: F401
    assert_server_state_allowed,
    build_automation_record_vals,
    encode_create_activity_server_vals,
    encode_create_record_server_vals,
    encode_followers_server_vals,
    encode_mail_post_server_vals,
    encode_object_write_button_vals,
    encode_remove_followers_server_vals,
    encode_sms_server_vals,
    encode_webhook_server_vals,
)


class UnsupportedOnOdoo16Error(ValueError):
    """Raised when an encoder for a capability omitted on Odoo 16 is invoked."""


def related_write_update_path(relation_field: str, field_name: str) -> str:
    raise UnsupportedOnOdoo16Error(
        "related_write / dotted update_path is not supported on Odoo 16 "
        f"(refused path {relation_field!r}.{field_name!r})"
    )


def encode_update_field_server_vals(
    *,
    name: str,
    model_id: int,
    action: UpdateFieldAction,
) -> dict[str, Any]:
    raise UnsupportedOnOdoo16Error(
        "object_write update_path (literal field update) is not supported on Odoo 16 "
        f"(refused field {action.field_name!r} for action {name!r}, model_id={model_id})"
    )


def encode_related_write_server_vals(
    *,
    name: str,
    model_id: int,
    action: RelatedWriteAction,
) -> dict[str, Any]:
    raise UnsupportedOnOdoo16Error(
        "related_write (dotted update_path) is not supported on Odoo 16 "
        f"(refused {action.relation_field!r}.{action.field_name!r} "
        f"for action {name!r}, model_id={model_id})"
    )


__all__ = [
    "CreateActivityAction",
    "CreateRecordAction",
    "FollowersAction",
    "MailPostAction",
    "RelatedWriteAction",
    "RemoveFollowersAction",
    "SmsAction",
    "UnsupportedOnOdoo16Error",
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
