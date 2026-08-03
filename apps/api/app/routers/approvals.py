"""Button approval rules — Community + Studio engines (CMP-5)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.approval_service import (
    check_action,
    create_rule,
    delete_rule,
    deploy_community_rule,
    get_rule,
    list_entries,
    list_rules,
    resolve_engine,
    resolve_entry,
    update_rule,
)
from app.bulk_suite.transitions import BulkSuiteError, discover_transitions
from app.db import get_db
from app.db_models import ApprovalEntry, OdooConnection
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired, require_advanced_confirmation
from app.tier_gating import approvals_gating, gating_context_for_connection

router = APIRouter(prefix="/connections/{connection_id}/approvals", tags=["approvals"])


def _client_row(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        client = client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return row, client


class ApprovalStepIn(BaseModel):
    order: int = 1
    approver_user_ids: list[int] = Field(default_factory=list)
    approver_group_id: int | None = None
    exclusive: bool = False
    domain: str | None = None


class ApprovalRuleIn(BaseModel):
    name: str
    target_model: str
    button_method: str
    button_label: str | None = None
    steps: list[ApprovalStepIn] = Field(default_factory=list)
    engine: str | None = None
    active: bool | None = None


class ApprovalRuleOut(BaseModel):
    id: str
    connection_id: str
    engine: str
    name: str
    target_model: str
    button_method: str
    button_label: str | None = None
    steps: list[dict[str, Any]]
    active: bool
    deployed: bool
    odoo_wrapper_action_id: int | None = None
    odoo_view_inherit_id: int | None = None
    odoo_studio_rule_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ApprovalEntryOut(BaseModel):
    id: str
    rule_id: str
    record_model: str
    record_id: int
    step_order: int
    status: str
    approver_user_id: int | None = None
    activity_id: int | None = None
    message: str
    created_at: datetime | None = None
    resolved_at: datetime | None = None


class ApprovalsGateOut(BaseModel):
    engine: str
    studio_available: bool
    studio_verify_state: str
    community_available: bool = True
    studio_note: str | None = None
    gating: dict[str, Any]


class ButtonOut(BaseModel):
    name: str
    label: str
    bulk_safe: bool
    reason: str
    in_header: bool


class DeployBody(BaseModel):
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class CheckActionBody(BaseModel):
    record_id: int
    actor_user_id: int | None = None


class ResolveEntryBody(BaseModel):
    actor_user_id: int = 2
    approve: bool = True


def _rule_out(row) -> ApprovalRuleOut:
    try:
        steps = json.loads(row.steps_json or "[]")
    except json.JSONDecodeError:
        steps = []
    return ApprovalRuleOut(
        id=row.id,
        connection_id=row.connection_id,
        engine=row.engine,
        name=row.name,
        target_model=row.target_model,
        button_method=row.button_method,
        button_label=row.button_label,
        steps=steps if isinstance(steps, list) else [],
        active=bool(row.active),
        deployed=bool(row.deployed),
        odoo_wrapper_action_id=row.odoo_wrapper_action_id,
        odoo_view_inherit_id=row.odoo_view_inherit_id,
        odoo_studio_rule_id=row.odoo_studio_rule_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _entry_out(row: ApprovalEntry) -> ApprovalEntryOut:
    return ApprovalEntryOut(
        id=row.id,
        rule_id=row.rule_id,
        record_model=row.record_model,
        record_id=row.record_id,
        step_order=row.step_order,
        status=row.status,
        approver_user_id=row.approver_user_id,
        activity_id=row.activity_id,
        message=row.message,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


@router.get("/gate", response_model=ApprovalsGateOut)
def approvals_gate(connection_id: str, db: Session = Depends(get_db)) -> ApprovalsGateOut:
    row, client = _client_row(connection_id, db)
    info = resolve_engine(client)
    ctx = gating_context_for_connection(url=row.url, server_version=row.server_version)
    gating = approvals_gating(ctx)
    note = None
    if info.studio_verify_state == "pending-live":
        note = "[SKIPPED-LIVE-VERIFY] Studio approval fields not fully verified on live Enterprise."
    return ApprovalsGateOut(
        engine=info.engine,
        studio_available=info.studio_available,
        studio_verify_state=info.studio_verify_state,
        community_available=True,
        studio_note=note,
        gating=gating.to_dict(),
    )


@router.get("/buttons", response_model=list[ButtonOut])
def list_buttons(
    connection_id: str,
    model: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
) -> list[ButtonOut]:
    row, client = _client_row(connection_id, db)
    try:
        buttons = discover_transitions(
            client,
            connection_id=connection_id,
            model=model.strip(),
            odoo_version=row.server_version,
        )
    except BulkSuiteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        ButtonOut(
            name=b.name,
            label=b.label,
            bulk_safe=b.bulk_safe,
            reason=b.reason,
            in_header=b.in_header,
        )
        for b in buttons
    ]


@router.get("/rules", response_model=list[ApprovalRuleOut])
def get_rules(connection_id: str, db: Session = Depends(get_db)) -> list[ApprovalRuleOut]:
    if db.get(OdooConnection, connection_id) is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return [_rule_out(r) for r in list_rules(db, connection_id)]


@router.post("/rules", response_model=ApprovalRuleOut, status_code=201)
def post_rule(
    connection_id: str, body: ApprovalRuleIn, db: Session = Depends(get_db)
) -> ApprovalRuleOut:
    _, client = _client_row(connection_id, db)
    engine = body.engine
    if engine not in {None, "community", "studio"}:
        raise HTTPException(status_code=422, detail="engine must be community or studio")
    try:
        row = create_rule(
            db,
            client,
            connection_id=connection_id,
            name=body.name,
            target_model=body.target_model.strip(),
            button_method=body.button_method.strip(),
            button_label=body.button_label,
            steps=[s.model_dump() for s in body.steps],
            engine=engine,  # type: ignore[arg-type]
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _rule_out(row)


@router.patch("/rules/{rule_id}", response_model=ApprovalRuleOut)
def patch_rule(
    connection_id: str, rule_id: str, body: ApprovalRuleIn, db: Session = Depends(get_db)
) -> ApprovalRuleOut:
    _, client = _client_row(connection_id, db)
    row = get_rule(db, connection_id, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    try:
        updated = update_rule(
            db,
            client,
            row,
            name=body.name,
            steps=[s.model_dump() for s in body.steps] if body.steps else None,
            active=body.active,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _rule_out(updated)


@router.delete("/rules/{rule_id}", status_code=204)
def remove_rule(connection_id: str, rule_id: str, db: Session = Depends(get_db)) -> None:
    _, client = _client_row(connection_id, db)
    row = get_rule(db, connection_id, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    try:
        delete_rule(db, client, row)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/rules/{rule_id}/deploy", response_model=ApprovalRuleOut)
def deploy_rule(
    connection_id: str,
    rule_id: str,
    body: DeployBody,
    db: Session = Depends(get_db),
) -> ApprovalRuleOut:
    _, client = _client_row(connection_id, db)
    row = get_rule(db, connection_id, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                "Deploy creates a live state=code server action and rebinds the form button "
                "via view inherit on the target Odoo instance."
            ),
            risks=[
                "Live Python (state=code) executes on the target database",
                "View inherit modifies the form button binding",
                "Snapshot taken before view change — use Journal Undo when reversible",
            ],
        )
    except ConfirmationRequired as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "requires_confirmation": True,
                "confirm_phrase": CONFIRM_PHRASE,
                "warning": exc.warning,
                "risks": exc.risks,
            },
        ) from exc
    try:
        updated = deploy_community_rule(db, client, connection_id=connection_id, row=row)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _rule_out(updated)


@router.post("/rules/{rule_id}/check")
def check_rule_action(
    connection_id: str,
    rule_id: str,
    body: CheckActionBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _, client = _client_row(connection_id, db)
    row = get_rule(db, connection_id, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    try:
        return check_action(
            db,
            client,
            row=row,
            record_id=body.record_id,
            actor_user_id=body.actor_user_id,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/entries", response_model=list[ApprovalEntryOut])
def get_entries(
    connection_id: str,
    rule_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[ApprovalEntryOut]:
    if db.get(OdooConnection, connection_id) is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return [_entry_out(e) for e in list_entries(db, connection_id, rule_id=rule_id)]


@router.post("/entries/{entry_id}/approve", response_model=ApprovalEntryOut)
def approve_entry(
    connection_id: str,
    entry_id: str,
    body: ResolveEntryBody,
    db: Session = Depends(get_db),
) -> ApprovalEntryOut:
    _, client = _client_row(connection_id, db)
    entry = db.get(ApprovalEntry, entry_id)
    if entry is None or entry.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    try:
        resolved = resolve_entry(
            db, client, entry=entry, approve=body.approve, actor_user_id=body.actor_user_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _entry_out(resolved)


class ProcessGateOut(BaseModel):
    engine: str
    enterprise_available: bool
    verify_state: str
    enterprise_note: str | None = None
    community_models_ready: bool


class ProcessTypeIn(BaseModel):
    name: str
    chain: list[dict[str, Any]] = Field(default_factory=list)


class ProcessRequestIn(BaseModel):
    type_id: int
    subject: str
    amount: float = 0.0
    requester_id: int = 2


class ProcessActionIn(BaseModel):
    actor_user_id: int = 2
    reason: str = ""


class ProcessScaffoldBody(BaseModel):
    confirm_advanced: bool = False
    confirm_phrase: str | None = None
    display_name: str | None = None


@router.get("/processes/gate", response_model=ProcessGateOut)
def processes_gate(connection_id: str, db: Session = Depends(get_db)) -> ProcessGateOut:
    from app.approval_process_service import REQUEST_MODEL, TYPE_MODEL, resolve_process_engine

    _, client = _client_row(connection_id, db)
    info = resolve_process_engine(client)
    ready = client.model_exists(TYPE_MODEL) and client.model_exists(REQUEST_MODEL)
    return ProcessGateOut(
        engine=info.engine,
        enterprise_available=info.enterprise_available,
        verify_state=info.verify_state,
        enterprise_note=info.enterprise_note,
        community_models_ready=ready,
    )


@router.get("/processes/types")
def list_process_types(connection_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    from app.approval_process_service import list_types

    _, client = _client_row(connection_id, db)
    return list_types(client)


@router.post("/processes/types", status_code=201)
def create_process_type(
    connection_id: str, body: ProcessTypeIn, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.approval_process_service import create_type

    _, client = _client_row(connection_id, db)
    try:
        return create_type(client, name=body.name.strip(), chain=body.chain)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/processes/requests")
def list_process_requests(connection_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    from app.approval_process_service import list_requests

    _, client = _client_row(connection_id, db)
    return list_requests(client)


@router.post("/processes/requests", status_code=201)
def create_process_request(
    connection_id: str, body: ProcessRequestIn, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.approval_process_service import create_request

    _, client = _client_row(connection_id, db)
    try:
        return create_request(
            client,
            type_id=body.type_id,
            subject=body.subject.strip(),
            amount=body.amount,
            requester_id=body.requester_id,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/processes/requests/{request_id}/submit")
def submit_process_request(
    connection_id: str, request_id: int, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.approval_process_service import submit_request

    _, client = _client_row(connection_id, db)
    try:
        return submit_request(client, request_id=request_id)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/processes/requests/{request_id}/approve")
def approve_process_request(
    connection_id: str,
    request_id: int,
    body: ProcessActionIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.approval_process_service import approve_request

    _, client = _client_row(connection_id, db)
    try:
        return approve_request(client, request_id=request_id, actor_user_id=body.actor_user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/processes/requests/{request_id}/refuse")
def refuse_process_request(
    connection_id: str,
    request_id: int,
    body: ProcessActionIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.approval_process_service import refuse_request

    _, client = _client_row(connection_id, db)
    try:
        return refuse_request(
            client,
            request_id=request_id,
            actor_user_id=body.actor_user_id,
            reason=body.reason,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/processes/scaffold")
def scaffold_process_template(
    connection_id: str,
    body: ProcessScaffoldBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.app_templates import scaffold_approval_requests

    _, client = _client_row(connection_id, db)
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Scaffold Approval Requests mini-app on live Odoo (models, fields, menus).",
            risks=[
                "Creates x_approval_type and x_approval_request models",
                "Seeds a two-level demo approval type when missing",
                "Prefer sandbox before production",
            ],
        )
    except ConfirmationRequired as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "requires_confirmation": True,
                "confirm_phrase": CONFIRM_PHRASE,
                "warning": exc.warning,
                "risks": exc.risks,
            },
        ) from exc
    try:
        result = scaffold_approval_requests(
            client,
            display_name=body.display_name or "Approval Requests",
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "template_id": result.template_id,
        "models": result.models,
        "models_created": result.models_created,
        "fields_created": result.fields_created,
        "menus_created": result.menus_created,
        "warnings": result.warnings,
        "message": result.message,
    }


class ProcessGateOut(BaseModel):
    engine: str
    enterprise_available: bool
    verify_state: str
    enterprise_note: str | None = None
    community_models_ready: bool


class ProcessTypeIn(BaseModel):
    name: str
    chain: list[dict[str, Any]] = Field(default_factory=list)


class ProcessRequestIn(BaseModel):
    type_id: int
    subject: str
    amount: float = 0.0
    requester_id: int = 2


class ProcessActionIn(BaseModel):
    actor_user_id: int = 2
    reason: str = ""


class ProcessScaffoldBody(BaseModel):
    confirm_advanced: bool = False
    confirm_phrase: str | None = None
    display_name: str | None = None


@router.get("/processes/gate", response_model=ProcessGateOut)
def processes_gate(connection_id: str, db: Session = Depends(get_db)) -> ProcessGateOut:
    from app.approval_process_service import REQUEST_MODEL, TYPE_MODEL, resolve_process_engine

    _, client = _client_row(connection_id, db)
    info = resolve_process_engine(client)
    ready = client.model_exists(TYPE_MODEL) and client.model_exists(REQUEST_MODEL)
    return ProcessGateOut(
        engine=info.engine,
        enterprise_available=info.enterprise_available,
        verify_state=info.verify_state,
        enterprise_note=info.enterprise_note,
        community_models_ready=ready,
    )


@router.get("/processes/types")
def list_process_types(connection_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    from app.approval_process_service import list_types

    _, client = _client_row(connection_id, db)
    return list_types(client)


@router.post("/processes/types", status_code=201)
def create_process_type(
    connection_id: str, body: ProcessTypeIn, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.approval_process_service import create_type

    _, client = _client_row(connection_id, db)
    try:
        return create_type(client, name=body.name.strip(), chain=body.chain)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/processes/requests")
def list_process_requests(connection_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    from app.approval_process_service import list_requests

    _, client = _client_row(connection_id, db)
    return list_requests(client)


@router.post("/processes/requests", status_code=201)
def create_process_request(
    connection_id: str, body: ProcessRequestIn, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.approval_process_service import create_request

    _, client = _client_row(connection_id, db)
    try:
        return create_request(
            client,
            type_id=body.type_id,
            subject=body.subject.strip(),
            amount=body.amount,
            requester_id=body.requester_id,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/processes/requests/{request_id}/submit")
def submit_process_request(
    connection_id: str, request_id: int, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.approval_process_service import submit_request

    _, client = _client_row(connection_id, db)
    try:
        return submit_request(client, request_id=request_id)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/processes/requests/{request_id}/approve")
def approve_process_request(
    connection_id: str,
    request_id: int,
    body: ProcessActionIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.approval_process_service import approve_request

    _, client = _client_row(connection_id, db)
    try:
        return approve_request(client, request_id=request_id, actor_user_id=body.actor_user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/processes/requests/{request_id}/refuse")
def refuse_process_request(
    connection_id: str,
    request_id: int,
    body: ProcessActionIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.approval_process_service import refuse_request

    _, client = _client_row(connection_id, db)
    try:
        return refuse_request(
            client,
            request_id=request_id,
            actor_user_id=body.actor_user_id,
            reason=body.reason,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/processes/scaffold")
def scaffold_process_template(
    connection_id: str,
    body: ProcessScaffoldBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.app_templates import scaffold_approval_requests

    _, client = _client_row(connection_id, db)
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Scaffold Approval Requests mini-app on live Odoo (models, fields, menus).",
            risks=[
                "Creates x_approval_type and x_approval_request models",
                "Seeds a two-level demo approval type when missing",
                "Prefer sandbox before production",
            ],
        )
    except ConfirmationRequired as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "requires_confirmation": True,
                "confirm_phrase": CONFIRM_PHRASE,
                "warning": exc.warning,
                "risks": exc.risks,
            },
        ) from exc
    try:
        result = scaffold_approval_requests(
            client,
            display_name=body.display_name or "Approval Requests",
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "template_id": result.template_id,
        "models": result.models,
        "models_created": result.models_created,
        "fields_created": result.fields_created,
        "menus_created": result.menus_created,
        "warnings": result.warnings,
        "message": result.message,
    }
