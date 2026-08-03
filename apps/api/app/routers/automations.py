"""Automation builder — safe defaults + advanced (confirmed) + Option A Python module export."""

from __future__ import annotations

import base64
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from module_generator import ModuleSpec, PythonAutomationSpec, build_module_zip
from odoo_client import (
    CreateActivityAction,
    CreateAutomationRequest,
    CreateRecordAction,
    FollowersAction,
    RelatedWriteAction,
    RemoveFollowersAction,
    SmsAction,
    UpdateFieldAction,
    WebhookAction,
)
from odoo_client.automation import AutomationTrigger, MailPostAction

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import AutomationsGateOut, AutomationTriggersOut, GatingCalloutOut, GatingOptionOut
from app.capabilities import probe_web_base_url, sample_installed_modules
from app.tier_gating import approvals_gating, automations_gating, gating_context_for_connection

from app.schemas import AutomationsGateOut, AutomationTriggersOut, GatingCalloutOut, GatingOptionOut
from app.capabilities import probe_web_base_url, sample_installed_modules
from app.tier_gating import approvals_gating, automations_gating, gating_context_for_connection

from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
    snapshot_automation,
)

router = APIRouter(prefix="/connections/{connection_id}/automations", tags=["automations"])

ADVANCED_ACTION_KINDS = frozenset(
    {"code_live", "webhook", "sms", "followers", "remove_followers"}
)

_ADVANCED_WARNINGS: dict[str, tuple[str, list[str]]] = {
    "code_live": (
        "Live Python server actions run with admin privileges on this database.",
        [
            "Can modify or destroy any data the Odoo user can access",
            "Harder to audit than declarative actions",
            "Rollback may only deactivate/unlink the automation — not undo side effects",
        ],
    ),
    "webhook": (
        "Webhook automations POST record data to an external URL.",
        [
            "May exfiltrate business data to a third party",
            "URL must be trusted; payloads can include field values you select",
            "Rollback removes the rule — not data already sent",
        ],
    ),
    "sms": (
        "SMS automations send messages via the Odoo SMS provider.",
        [
            "May incur carrier / IAP costs",
            "Messages go to phone numbers on matching records",
            "Rollback removes the rule — not messages already sent",
        ],
    ),
    "followers": (
        "Follower automations change who follows records (notifications / chatter).",
        [
            "Can subscribe partners without their explicit consent in-app",
            "May increase notification noise for subscribed users",
            "Rollback removes the rule — not follower links already added",
        ],
    ),
    "remove_followers": (
        "Remove-followers automations unsubscribe partners from records.",
        [
            "Users may stop receiving important notifications",
            "Hard to reverse at scale once applied",
            "Rollback removes the rule — not follower removals already done",
        ],
    ),
}


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class AutomationOut(BaseModel):
    id: int
    name: str
    model: str
    model_id: int
    trigger: str
    active: bool
    filter_domain: str | None = None
    action_server_ids: list[int] = Field(default_factory=list)
    snapshot_id: str | None = None


class ModuleExportOut(BaseModel):
    technical_name: str
    filename: str
    content_base64: str
    note: str


class CreateAutomationBody(BaseModel):
    name: str
    model: str
    trigger: str
    filter_domain: str | None = None
    filter_pre_domain: str | None = None
    trigger_field_names: list[str] = Field(default_factory=list)
    trg_date_field_name: str | None = None
    trg_date_range: int | None = 0
    trg_date_range_type: Literal["minutes", "hour", "day", "month"] | None = "day"
    trg_date_range_mode: Literal["after", "before"] | None = "after"
    active: bool = True
    action_kind: Literal[
        "update_field",
        "related_write",
        "create_activity",
        "create_record",
        "mail_post",
        "python_module",  # Option A — zip only
        "code_live",  # Advanced — live state=code, requires confirm
        "webhook",
        "sms",
        "followers",
        "remove_followers",
    ]
    field_name: str | None = None
    value: str | None = None
    relation_field: str | None = None  # related_write: M2O on trigger model
    activity_type_id: int | None = None
    activity_summary: str | None = "Follow up"
    activity_note: str | None = None
    activity_user_type: Literal["specific", "generic"] = "generic"
    activity_user_id: int | None = None
    activity_user_field_name: str | None = None
    # create_record
    target_model: str | None = None
    field_values: dict[str, str] | None = None
    # mail_post
    mail_template_id: int | None = None
    mail_post_method: Literal["email", "comment", "note"] = "email"
    mail_subject: str | None = None
    mail_body_html: str | None = None
    mail_email_to: str | None = None
    # webhook
    webhook_url: str | None = None
    webhook_field_names: list[str] = Field(default_factory=list)
    # sms
    sms_template_id: int | None = None
    sms_body: str | None = None
    sms_method: Literal["sms", "comment", "note"] = "sms"
    # followers / remove_followers
    partner_ids: list[int] = Field(default_factory=list)
    followers_type: Literal["specific", "generic"] = "specific"
    followers_partner_field_name: str | None = None
    # Python
    python_code: str | None = None
    module_technical_name: str | None = None
    # Advanced confirmation
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class ActivityTypeOut(BaseModel):
    id: int
    name: str


class UpdateAutomationBody(BaseModel):
    active: bool


class ConfirmAdvancedBody(BaseModel):
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class DeleteAutomationOut(BaseModel):
    ok: bool = True
    automation_id: int
    snapshot_id: str | None = None


def _confirm_http(exc: ConfirmationRequired) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "requires_confirmation": True,
            "confirm_phrase": CONFIRM_PHRASE,
            "warning": exc.warning,
            "risks": exc.risks,
        },
    )


def _gating_http(gating: Any) -> HTTPException:
    payload = gating.to_dict() if hasattr(gating, "to_dict") else gating
    return HTTPException(
        status_code=409,
        detail={"gating": payload, "message": payload.get("title", "Feature gated")},
    )


def _gating_out(gating: Any) -> GatingCalloutOut:
    data = gating.to_dict() if hasattr(gating, "to_dict") else gating
    return GatingCalloutOut(
        feature=data["feature"],
        title=data["title"],
        why=data["why"],
        options=list(data.get("options") or []),
        available=bool(data.get("available")),
        capability_key=data["capability_key"],
        gating_choices=[
            GatingOptionOut(id=c["id"], label=c["label"])
            for c in data.get("gating_choices") or []
        ],
    )


def _tier_context_for_connection(connection_id: str, db: Session):
    row = get_connection_or_404(db, connection_id)
    mods: list[str] = []
    web_base_url: str | None = None
    try:
        client = client_from_connection(row)
        mods = sample_installed_modules(client)
        web_base_url = probe_web_base_url(client)
    except OdooClientError:
        pass
    return gating_context_for_connection(
        url=row.url,
        server_version=row.server_version,
        installed_modules=mods,
        web_base_url=web_base_url,
    )


@router.get("/gate", response_model=AutomationsGateOut)
def automations_gate(connection_id: str, db: Session = Depends(get_db)) -> AutomationsGateOut:
    try:
        ctx = _tier_context_for_connection(connection_id, db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AutomationsGateOut(
        automations=_gating_out(automations_gating(ctx)),
        approvals=_gating_out(approvals_gating(ctx)),
    )


def _gating_http(gating: Any) -> HTTPException:
    payload = gating.to_dict() if hasattr(gating, "to_dict") else gating
    return HTTPException(
        status_code=409,
        detail={"gating": payload, "message": payload.get("title", "Feature gated")},
    )


def _gating_out(gating: Any) -> GatingCalloutOut:
    data = gating.to_dict() if hasattr(gating, "to_dict") else gating
    return GatingCalloutOut(
        feature=data["feature"],
        title=data["title"],
        why=data["why"],
        options=list(data.get("options") or []),
        available=bool(data.get("available")),
        capability_key=data["capability_key"],
        gating_choices=[
            GatingOptionOut(id=c["id"], label=c["label"])
            for c in data.get("gating_choices") or []
        ],
    )


def _tier_context_for_connection(connection_id: str, db: Session):
    row = get_connection_or_404(db, connection_id)
    mods: list[str] = []
    web_base_url: str | None = None
    try:
        client = client_from_connection(row)
        mods = sample_installed_modules(client)
        web_base_url = probe_web_base_url(client)
    except OdooClientError:
        pass
    return gating_context_for_connection(
        url=row.url,
        server_version=row.server_version,
        installed_modules=mods,
        web_base_url=web_base_url,
    )


@router.get("/gate", response_model=AutomationsGateOut)
def automations_gate(connection_id: str, db: Session = Depends(get_db)) -> AutomationsGateOut:
    try:
        ctx = _tier_context_for_connection(connection_id, db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AutomationsGateOut(
        automations=_gating_out(automations_gating(ctx)),
        approvals=_gating_out(approvals_gating(ctx)),
    )


@router.get("/triggers", response_model=AutomationTriggersOut)
def automation_triggers(connection_id: str, db: Session = Depends(get_db)) -> AutomationTriggersOut:
    from app.automation_trigger_probe import probe_automation_triggers

    client = _client(connection_id, db)
    try:
        data = probe_automation_triggers(client)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AutomationTriggersOut.model_validate(data)


def _require_advanced_kind(action_kind: str, body: CreateAutomationBody) -> None:
    warning, risks = _ADVANCED_WARNINGS[action_kind]
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=warning,
            risks=risks,
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc


@router.get("", response_model=list[AutomationOut])
def list_automations(
    connection_id: str,
    model: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[AutomationOut]:
    client = _client(connection_id, db)
    try:
        rows = client.list_automations(model=model)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [AutomationOut.model_validate(r.model_dump()) for r in rows]


@router.get("/activity-types", response_model=list[ActivityTypeOut])
def list_activity_types(
    connection_id: str, db: Session = Depends(get_db)
) -> list[ActivityTypeOut]:
    client = _client(connection_id, db)
    try:
        rows = client.list_activity_types()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [ActivityTypeOut.model_validate(r) for r in rows]


@router.post("", response_model=AutomationOut | ModuleExportOut, status_code=201)
def create_automation(
    connection_id: str, body: CreateAutomationBody, db: Session = Depends(get_db)
) -> AutomationOut | ModuleExportOut:
    # Validate request shape before any Odoo RPC (also gates Option A zip-only path).
    if body.action_kind == "python_module":
        if not body.python_code or not body.python_code.strip():
            raise HTTPException(status_code=422, detail="python_module requires python_code")
        try:
            get_connection_or_404(db, connection_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        tech = body.module_technical_name or "custom_automation_code"
        try:
            zip_bytes = build_module_zip(
                ModuleSpec(
                    technical_name=tech,
                    display_name=body.name,
                    python_automations=[
                        PythonAutomationSpec(
                            name=body.name,
                            model=body.model,
                            trigger=body.trigger,
                            code=body.python_code,
                            filter_domain=body.filter_domain,
                        )
                    ],
                )
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ModuleExportOut(
            technical_name=tech,
            filename=f"{tech}.zip",
            content_base64=base64.b64encode(zip_bytes).decode("ascii"),
            note=(
                "Option A: module generated. Test in sandbox, then install on the target "
                "instance to make the Python automation live. It is not applied yet."
            ),
        )

    if body.action_kind == "update_field":
        if not body.field_name or body.value is None:
            raise HTTPException(
                status_code=422, detail="update_field requires field_name and value"
            )
    elif body.action_kind == "related_write":
        if not body.relation_field or not body.field_name or body.value is None:
            raise HTTPException(
                status_code=422,
                detail="related_write requires relation_field, field_name, and value",
            )
    elif body.action_kind == "create_activity":
        if not body.activity_type_id:
            raise HTTPException(
                status_code=422, detail="create_activity requires activity_type_id"
            )
    elif body.action_kind == "create_record":
        if not body.target_model:
            raise HTTPException(
                status_code=422, detail="create_record requires target_model"
            )
    elif body.action_kind == "mail_post":
        pass
    elif body.action_kind in ADVANCED_ACTION_KINDS:
        _require_advanced_kind(body.action_kind, body)
        if body.action_kind == "code_live" and not body.python_code:
            raise HTTPException(status_code=422, detail="code_live requires python_code")
        if body.action_kind == "webhook" and not (body.webhook_url or "").strip():
            raise HTTPException(status_code=422, detail="webhook requires webhook_url")
        if body.action_kind == "sms":
            if body.sms_template_id is None and not (body.sms_body or "").strip():
                raise HTTPException(
                    status_code=422, detail="sms requires sms_template_id or sms_body"
                )
    else:
        raise HTTPException(status_code=422, detail=f"Unknown action_kind {body.action_kind}")

    client = _client(connection_id, db)
    try:
        trigger = AutomationTrigger(body.trigger)

        if body.action_kind == "code_live":
            created = client.create_code_automation(
                name=body.name,
                model=body.model,
                trigger=body.trigger,
                code=body.python_code or "",
                filter_domain=body.filter_domain,
                active=body.active,
            )
            snap = snapshot_automation(db, connection_id, client, created.id)
            out = AutomationOut.model_validate(created.model_dump())
            out.snapshot_id = snap.id
            return out

        if body.action_kind == "update_field":
            action: Any = UpdateFieldAction(field_name=body.field_name or "", value=body.value or "")
        elif body.action_kind == "related_write":
            action = RelatedWriteAction(
                relation_field=body.relation_field or "",
                field_name=body.field_name or "",
                value=body.value or "",
            )
        elif body.action_kind == "create_activity":
            action = CreateActivityAction(
                activity_type_id=body.activity_type_id or 0,
                summary=body.activity_summary or "Follow up",
                note=body.activity_note,
                user_type=body.activity_user_type,
                user_id=body.activity_user_id,
                user_field_name=body.activity_user_field_name,
            )
        elif body.action_kind == "mail_post":
            action = MailPostAction(
                template_id=body.mail_template_id,
                mail_post_method=body.mail_post_method,
                subject=body.mail_subject,
                body_html=body.mail_body_html,
                email_to=body.mail_email_to,
            )
        elif body.action_kind == "webhook":
            action = WebhookAction(
                webhook_url=body.webhook_url or "",
                webhook_field_names=list(body.webhook_field_names or []),
            )
        elif body.action_kind == "sms":
            action = SmsAction(
                sms_template_id=body.sms_template_id,
                body=body.sms_body,
                sms_method=body.sms_method,
            )
        elif body.action_kind == "followers":
            action = FollowersAction(
                partner_ids=list(body.partner_ids or []),
                followers_type=body.followers_type,
                followers_partner_field_name=body.followers_partner_field_name,
            )
        elif body.action_kind == "remove_followers":
            action = RemoveFollowersAction(partner_ids=list(body.partner_ids or []))
        else:  # create_record
            action = CreateRecordAction(
                target_model=body.target_model or "",
                field_values=body.field_values or {},
            )

        created = client.create_automation(
            CreateAutomationRequest(
                name=body.name,
                model=body.model,
                trigger=trigger,
                filter_domain=body.filter_domain,
                filter_pre_domain=body.filter_pre_domain,
                trigger_field_names=body.trigger_field_names,
                trg_date_field_name=body.trg_date_field_name,
                trg_date_range=body.trg_date_range,
                trg_date_range_type=body.trg_date_range_type,
                trg_date_range_mode=body.trg_date_range_mode,
                active=body.active,
                action=action,
            )
        )
        snap = snapshot_automation(db, connection_id, client, created.id)
        out = AutomationOut.model_validate(created.model_dump())
        out.snapshot_id = snap.id
        return out
    except HTTPException:
        raise
    except (OdooClientError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{automation_id}", response_model=AutomationOut)
def update_automation(
    connection_id: str,
    automation_id: int,
    body: UpdateAutomationBody,
    db: Session = Depends(get_db),
) -> AutomationOut:
    client = _client(connection_id, db)
    try:
        updated = client.set_automation_active(automation_id, body.active)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AutomationOut.model_validate(updated.model_dump())


@router.delete("/{automation_id}", response_model=DeleteAutomationOut)
def delete_automation(
    connection_id: str,
    automation_id: int,
    body: ConfirmAdvancedBody,
    db: Session = Depends(get_db),
) -> DeleteAutomationOut:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Deleting an automation permanently removes the rule and its server actions.",
            risks=[
                "Automation will no longer run on matching records",
                "Server action side effects already applied are not undone",
                "A snapshot is taken so definition restore may be possible",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        snap = snapshot_automation(db, connection_id, client, automation_id)
        client.delete_automation(automation_id)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DeleteAutomationOut(
        ok=True, automation_id=automation_id, snapshot_id=snap.id
    )
