"""Odoo 18 automation encoding — overlapping safe subset with v19.

M2: object_write ``update_path`` / related_write / object_create shapes match 19
for the declared capability set. Live smoke must stay green before promoting 18 to GA.
"""

from __future__ import annotations

from typing import Any

from odoo_client.compat.adapters.automation_v19 import (
    build_automation_record_vals as _build_v19,
)

# Re-export v19 encoders — encoding is shared for the safe subset.
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


def build_automation_record_vals(**kwargs: Any) -> dict[str, Any]:
    """v19 encoding, but this series has no ``trg_date_range_mode`` (added in 19):
    "before" is a negative ``trg_date_range``, as Odoo <=18 expects."""
    vals = _build_v19(**kwargs)
    mode = vals.pop("trg_date_range_mode", None)
    if mode == "before" and vals.get("trg_date_range"):
        vals["trg_date_range"] = -abs(int(vals["trg_date_range"]))
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
