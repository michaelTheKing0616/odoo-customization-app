"""Typed models for form-bound actions (Odoo 19) — safe no-code subset only.

Form buttons use ``type="action"`` with ``name`` = action database id.
``type="object"`` (Python methods) is out of scope for pure RPC custom models
without Option A module packaging.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from odoo_client.automation import BLOCKED_SERVER_STATES


SAFE_BUTTON_SERVER_STATES = frozenset(
    {
        "object_write",
        "object_create",
        "object_copy",
        "next_activity",
        "mail_post",
        "followers",
        "remove_followers",
    }
)


class ServerActionInfo(BaseModel):
    id: int
    name: str
    model: str
    model_id: int
    state: str
    binding_model_id: int | None = None
    binding_type: str | None = None


class WindowActionInfo(BaseModel):
    id: int
    name: str
    res_model: str
    view_mode: str
    domain: str | None = None
    context: str | None = None


class CreateUpdateFieldServerAction(BaseModel):
    """Create ir.actions.server state=object_write bound for form buttons."""

    name: str = Field(..., min_length=1, max_length=200)
    model: str
    field_name: str = Field(..., description="Technical field to update (update_path)")
    value: str = Field(..., description="Literal value (evaluation_type=value)")
    bind_to_model: bool = Field(
        default=True,
        description="Also expose under Action menu via binding_model_id",
    )

    @field_validator("field_name")
    @classmethod
    def non_empty_field(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field_name is required")
        return cleaned


class CreateNextActivityServerAction(BaseModel):
    """Create ir.actions.server state=next_activity (requires mail.activity on model)."""

    name: str = Field(..., min_length=1, max_length=200)
    model: str
    activity_type_id: int
    summary: str = "Follow up"
    note: str | None = None
    user_type: Literal["specific", "generic"] = "generic"
    user_id: int | None = None
    user_field_name: str | None = Field(
        default=None,
        description="res.users field on model for generic assignee; auto-picks create_uid if missing",
    )
    bind_to_model: bool = True


class CreateMailPostServerAction(BaseModel):
    """Create ir.actions.server state=mail_post (requires mail.thread or email template)."""

    name: str = Field(..., min_length=1, max_length=200)
    model: str
    template_id: int | None = Field(
        default=None,
        description="mail.template id; if omitted a minimal template is created",
    )
    mail_post_method: Literal["email", "comment", "note"] = "email"
    subject: str | None = None
    body_html: str | None = None
    email_to: str | None = Field(
        default=None,
        description="Template email_to expression when auto-creating a template",
    )
    bind_to_model: bool = True


class CreateRelatedWindowAction(BaseModel):
    """Window action for related records (smart / header buttons)."""

    name: str = Field(..., min_length=1, max_length=200)
    source_model: str = Field(..., description="Model that owns the button")
    target_model: str = Field(..., description="Model opened by the action")
    relation_field: str = Field(
        ...,
        description="Field on target_model pointing at source (many2one)",
    )
    view_mode: str = "list,form"

    @field_validator("relation_field")
    @classmethod
    def non_empty_relation(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("relation_field is required")
        return cleaned


class CreateRelatedCountField(BaseModel):
    """Non-stored computed integer counting a one2many / related lines.

    Uses ir.model.fields compute (Community 19 supports this for manual fields).
    Treated as advanced (equation/compute) — API must require confirm.
    """

    model: str
    name: str = Field(..., description="x_… count field name")
    field_description: str = "Count"
    one2many_field: str = Field(
        ...,
        description="Existing one2many (or similar) field to len()",
    )

    @field_validator("name")
    @classmethod
    def x_prefix(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith("x_"):
            raise ValueError("Count field must start with x_")
        return cleaned


class SmartButtonBundle(BaseModel):
    """Related window action + optional computed count field for a smart button."""

    window_action: WindowActionInfo
    count_field: str | None = None
    count_field_id: int | None = None
    button_spec: dict[str, Any] = Field(default_factory=dict)


class CreateSmartButtonBundle(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source_model: str
    target_model: str
    relation_field: str
    one2many_field: str | None = Field(
        default=None,
        description="If set with create_count_field, build len(one2many) compute",
    )
    count_field_name: str | None = None
    create_count_field: bool = False
    icon: str = "fa-list"
    view_mode: str = "list,form"


class BindableActionInfo(BaseModel):
    """Unified picker row for Designer button binding."""

    id: int
    name: str
    action_type: Literal["ir.actions.server", "ir.actions.act_window"]
    model: str
    detail: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


def assert_safe_server_state(state: str) -> None:
    if state in BLOCKED_SERVER_STATES:
        raise ValueError(
            f"Server action state {state!r} is blocked from the no-code path "
            "(use Option A module packaging for Python/webhook)"
        )
    if state not in SAFE_BUTTON_SERVER_STATES:
        raise ValueError(f"Unsupported server action state for buttons: {state!r}")
