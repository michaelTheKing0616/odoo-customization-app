"""Typed models for base.automation (Odoo 19) — safe no-code subset + confirmed advanced."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


SAFE_TRIGGERS = {
    "on_create",
    "on_write",
    "on_create_or_write",
    "on_unlink",
    "on_archive",
    "on_unarchive",
    "on_time",
    "on_time_created",
    "on_time_updated",
    "on_message_received",
    "on_message_sent",
    "on_webhook",
    "on_change",
}

# Always refused on the safe encode / button path (code_live uses a separate API).
BLOCKED_SERVER_STATES = {"code", "webhook", "sms", "multi"}

# Allowed in build_automation_record_vals only when allow_advanced=True (API confirm).
ADVANCED_SERVER_STATES = frozenset({"webhook", "sms", "followers", "remove_followers"})


class AutomationTrigger(str, Enum):
    ON_CREATE = "on_create"
    ON_WRITE = "on_write"
    ON_CREATE_OR_WRITE = "on_create_or_write"
    ON_UNLINK = "on_unlink"
    ON_ARCHIVE = "on_archive"
    ON_UNARCHIVE = "on_unarchive"
    ON_TIME = "on_time"
    ON_TIME_CREATED = "on_time_created"
    ON_TIME_UPDATED = "on_time_updated"
    ON_MESSAGE_RECEIVED = "on_message_received"
    ON_MESSAGE_SENT = "on_message_sent"
    ON_WEBHOOK = "on_webhook"
    ON_CHANGE = "on_change"


class AutomationActionKind(str, Enum):
    UPDATE_FIELD = "update_field"
    RELATED_WRITE = "related_write"
    CREATE_ACTIVITY = "create_activity"
    CREATE_RECORD = "create_record"
    MAIL_POST = "mail_post"
    WEBHOOK = "webhook"
    SMS = "sms"
    FOLLOWERS = "followers"
    REMOVE_FOLLOWERS = "remove_followers"


class UpdateFieldAction(BaseModel):
    kind: Literal["update_field"] = "update_field"
    field_name: str = Field(..., description="Technical field name to update")
    value: str = Field(..., description="Literal value written to the field")


class RelatedWriteAction(BaseModel):
    """Write a field on a related Many2one record (dotted object_write path)."""

    kind: Literal["related_write"] = "related_write"
    relation_field: str = Field(
        ..., description="Many2one on the trigger model, e.g. x_vehicle_id"
    )
    field_name: str = Field(
        ..., description="Field on the related record, e.g. x_status"
    )
    value: str = Field(..., description="Literal value written on the related record")


class CreateActivityAction(BaseModel):
    kind: Literal["create_activity"] = "create_activity"
    activity_type_id: int
    summary: str = "Follow up"
    note: str | None = None
    user_type: Literal["specific", "generic"] = "generic"
    user_id: int | None = None
    user_field_name: str | None = Field(
        default=None,
        description="Record field used when user_type=generic; falls back to create_uid",
    )


class CreateRecordAction(BaseModel):
    """Create a related record via ir.actions.server state=object_create."""

    kind: Literal["create_record"] = "create_record"
    target_model: str = Field(..., description="Model to create, e.g. mail.activity")
    # JSON object of field → literal value (stringified for Odoo value fields)
    field_values: dict[str, str] = Field(default_factory=dict)


class MailPostAction(BaseModel):
    """Post email/comment/note via ir.actions.server state=mail_post."""

    kind: Literal["mail_post"] = "mail_post"
    template_id: int | None = None
    mail_post_method: Literal["email", "comment", "note"] = "email"
    # When template_id is omitted, create a minimal template with these:
    subject: str | None = "Notification"
    body_html: str | None = "<p>Automated message</p>"
    email_to: str | None = None


class WebhookAction(BaseModel):
    """Call an external URL via ir.actions.server state=webhook (advanced)."""

    kind: Literal["webhook"] = "webhook"
    webhook_url: str = Field(..., min_length=1, description="HTTPS URL to POST to")
    webhook_field_names: list[str] = Field(
        default_factory=list,
        description="Optional model field names included in the webhook payload",
    )


class SmsAction(BaseModel):
    """Send SMS via ir.actions.server state=sms (advanced; needs sms module)."""

    kind: Literal["sms"] = "sms"
    sms_template_id: int | None = None
    body: str | None = Field(
        default=None,
        description="SMS body when creating a template (sms_template_id omitted)",
    )
    sms_method: Literal["sms", "comment", "note"] = "sms"

    @model_validator(mode="after")
    def require_template_or_body(self) -> SmsAction:
        if self.sms_template_id is None and not (self.body or "").strip():
            raise ValueError("sms requires sms_template_id or body")
        return self


class FollowersAction(BaseModel):
    """Add followers via ir.actions.server state=followers (advanced)."""

    kind: Literal["followers"] = "followers"
    partner_ids: list[int] = Field(default_factory=list)
    followers_type: Literal["specific", "generic"] = "specific"
    followers_partner_field_name: str | None = Field(
        default=None,
        description="Partner field on the record when followers_type=generic",
    )

    @model_validator(mode="after")
    def validate_followers_shape(self) -> FollowersAction:
        if self.followers_type == "generic" and not self.followers_partner_field_name:
            raise ValueError(
                "followers with followers_type=generic requires followers_partner_field_name"
            )
        return self


class RemoveFollowersAction(BaseModel):
    """Remove followers via ir.actions.server state=remove_followers (advanced)."""

    kind: Literal["remove_followers"] = "remove_followers"
    partner_ids: list[int] = Field(default_factory=list)


AutomationAction = (
    UpdateFieldAction
    | RelatedWriteAction
    | CreateActivityAction
    | CreateRecordAction
    | MailPostAction
    | WebhookAction
    | SmsAction
    | FollowersAction
    | RemoveFollowersAction
)


class CreateAutomationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    model: str = Field(..., description="Technical model name, e.g. res.partner")
    trigger: AutomationTrigger
    filter_domain: str | None = Field(
        default=None,
        description="Odoo domain as string, e.g. [('is_company','=',True)]",
    )
    filter_pre_domain: str | None = Field(
        default=None,
        description="Before-update domain (Odoo filter_pre_domain) as string",
    )
    trigger_field_names: list[str] = Field(
        default_factory=list,
        description="For on_write: fields that trigger the rule",
    )
    trg_date_field_name: str | None = Field(
        default=None,
        description="Date/datetime field for on_time trigger",
    )
    trg_date_range: int | None = 0
    trg_date_range_type: Literal["minutes", "hour", "day", "month"] | None = "day"
    trg_date_range_mode: Literal["after", "before"] | None = "after"
    active: bool = True
    action: AutomationAction

    @field_validator("trigger")
    @classmethod
    def safe_trigger_only(cls, value: AutomationTrigger) -> AutomationTrigger:
        if value.value not in SAFE_TRIGGERS:
            raise ValueError(f"Trigger {value.value!r} is not allowed in the no-code builder")
        return value

    @model_validator(mode="after")
    def validate_trigger_requirements(self) -> CreateAutomationRequest:
        if self.trigger in {
            AutomationTrigger.ON_TIME,
        } and not self.trg_date_field_name:
            raise ValueError("on_time trigger requires trg_date_field_name")
        if (
            self.trigger == AutomationTrigger.ON_WRITE
            and not self.trigger_field_names
        ):
            # Allowed but warn via empty — Odoo fires on any write; optional filter fields.
            pass
        return self


class AutomationInfo(BaseModel):
    id: int
    name: str
    model: str
    model_id: int
    trigger: str
    active: bool
    filter_domain: str | None = None
    action_server_ids: list[int] = Field(default_factory=list)

    @field_validator("filter_domain", mode="before")
    @classmethod
    def coerce_false_domain(cls, value: object) -> str | None:
        if value is False or value is None:
            return None
        return str(value)
