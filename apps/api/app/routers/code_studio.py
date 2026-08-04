"""DEV-1 — Code Studio API (live state=code server actions)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.code_studio_gating import (
    assert_code_studio_entitlement,
    assert_developer_role,
    assert_probe_available,
    code_studio_gate_payload,
    load_or_probe,
)
from app.code_studio_service import (
    SNIPPETS,
    bind_code_action,
    context_reference,
    test_run_code,
    validate_code,
)
from app.db import get_db
from app.entitlements import require_feature
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import GatingCalloutOut, GatingOptionOut
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired
from app.workspace_auth import WorkspaceAuth, get_workspace_auth, require_app_auth

router = APIRouter(prefix="/connections/{connection_id}/code-studio", tags=["code-studio"])


class CodeStudioGateOut(BaseModel):
    probe: dict[str, Any]
    gating: GatingCalloutOut
    developer_role_required: bool = True
    entitlement_key: str = "dev_tools"


class ValidateCodeBody(BaseModel):
    code: str = ""


class ValidateCodeOut(BaseModel):
    ok: bool
    syntax_ok: bool
    warnings: list[dict[str, str]] = Field(default_factory=list)
    error: str | None = None


class TestRunBody(BaseModel):
    model: str
    record_id: int | None = None
    code: str


class BindCodeBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    model: str
    code: str
    bind_kind: Literal["standalone", "model_button", "automation"] = "standalone"
    bind_to_model: bool = True
    trigger: str | None = None
    filter_domain: str | None = None
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class BindCodeOut(BaseModel):
    ok: bool = True
    bind_kind: str
    code: str
    snapshot_id: str | None = None
    server_action_id: int | None = None
    automation_id: int | None = None


def _connection(db: Session, connection_id: str):
    try:
        return get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _client_or_502(row):
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _gating_out(data: dict[str, Any]) -> GatingCalloutOut:
    return GatingCalloutOut(
        feature="code_studio",
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


def _set_audit_detail(request: Request, detail: dict[str, Any]) -> None:
    request.state.audit_detail = detail


@router.get("/gate", response_model=CodeStudioGateOut)
def code_studio_gate(
    connection_id: str,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> CodeStudioGateOut:
    row = _connection(db, connection_id)
    probe = load_or_probe(db, row, force=False)
    return CodeStudioGateOut(
        probe=probe,
        gating=_gating_out(code_studio_gate_payload(probe)),
    )


@router.post("/probe")
def code_studio_probe(
    connection_id: str,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict[str, Any]:
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    row = _connection(db, connection_id)
    return load_or_probe(db, row, force=True)


@router.get("/context")
def code_studio_context(
    connection_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = _connection(db, connection_id)
    major = None
    if row.server_version and row.server_version[:2].isdigit():
        try:
            major = int(row.server_version.split(".")[0])
        except ValueError:
            major = None
    return {"major": major, "symbols": context_reference(major)}


@router.get("/snippets")
def code_studio_snippets() -> dict[str, Any]:
    return {"snippets": SNIPPETS}


@router.post("/validate", response_model=ValidateCodeOut)
def code_studio_validate(
    connection_id: str,
    body: ValidateCodeBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> ValidateCodeOut:
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    _connection(db, connection_id)
    data = validate_code(body.code)
    return ValidateCodeOut(**data)


@router.post("/test-run")
def code_studio_test_run(
    connection_id: str,
    body: TestRunBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict[str, Any]:
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    row = _connection(db, connection_id)
    probe = load_or_probe(db, row, force=False)
    assert_probe_available(probe)
    client = _client_or_502(row)
    return test_run_code(
        client,
        model=body.model,
        record_id=body.record_id,
        code=body.code,
    )


@router.post("/bind", response_model=BindCodeOut)
def code_studio_bind(
    connection_id: str,
    body: BindCodeBody,
    request: Request,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> BindCodeOut:
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    row = _connection(db, connection_id)
    probe = load_or_probe(db, row, force=False)
    assert_probe_available(probe)
    client = _client_or_502(row)
    try:
        result = bind_code_action(
            db,
            client,
            connection_id=connection_id,
            name=body.name,
            model=body.model,
            code=body.code,
            bind_kind=body.bind_kind,
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            trigger=body.trigger,
            filter_domain=body.filter_domain,
            bind_to_model=body.bind_to_model,
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    _set_audit_detail(
        request,
        {
            "operation": "code_studio_bind",
            "bind_kind": body.bind_kind,
            "model": body.model,
            "name": body.name,
            "code": body.code,
            "snapshot_id": result.get("snapshot_id"),
        },
    )
    return BindCodeOut(
        bind_kind=result["bind_kind"],
        code=result["code"],
        snapshot_id=result.get("snapshot_id"),
        server_action_id=result.get("server_action_id"),
        automation_id=result.get("automation_id"),
    )
