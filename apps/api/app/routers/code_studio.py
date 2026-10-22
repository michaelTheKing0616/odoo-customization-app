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
from app.audit_chain import append_entry
from app.code_studio_service import (
    SNIPPETS,
    CodeStudioRuleError,
    bind_code_action,
    context_reference,
    export_option_a_zip,
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
    line: int | None = None


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


class OptionABody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    model: str = Field(..., min_length=1, max_length=200)
    code: str
    technical_name: str | None = None
    depends: list[str] | None = None
    as_extension: bool = False


class ExtensionScaffoldBody(BaseModel):
    model: str = Field(..., min_length=1, max_length=200)
    kind: Literal["selection_options", "computed_field", "behaviour"]
    field_name: str | None = None
    label: str | None = None
    options: list[dict[str, str]] | None = None


class ExtensionScaffoldOut(BaseModel):
    code: str
    depends: list[str]
    technical_name: str


class OptionAOut(BaseModel):
    ok: bool = True
    installed: bool = False
    promoted: bool = False
    technical_name: str
    filename: str
    content_base64: str
    note: str


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


def _audit_chain(db: Session, auth: WorkspaceAuth, kind: str, payload: dict[str, Any]) -> None:
    actor = auth.email or auth.user_id or "code_studio"
    append_entry(db, actor=str(actor), kind=kind, payload=payload)


def _rule_http(exc: CodeStudioRuleError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "error": exc.rule,
            "message": str(exc),
            "line": exc.line,
            "snapshot_id": exc.snapshot_id,
        },
    )


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
        db=db,
        connection_id=connection_id,
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
    except CodeStudioRuleError as exc:
        raise _rule_http(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    snapshot_id = result.get("snapshot_id")
    if not snapshot_id:
        raise HTTPException(status_code=500, detail="Bind finished without a snapshot id.")

    _set_audit_detail(
        request,
        {
            "operation": "code_studio_bind",
            "bind_kind": body.bind_kind,
            "model": body.model,
            "name": body.name,
            "code": body.code,
            "snapshot_id": snapshot_id,
        },
    )
    _audit_chain(
        db,
        auth,
        "change",
        {
            "operation": "code_studio_bind",
            "bind_kind": body.bind_kind,
            "model": body.model,
            "name": body.name,
            "snapshot_id": snapshot_id,
            "server_action_id": result.get("server_action_id"),
            "automation_id": result.get("automation_id"),
        },
    )
    _audit_chain(
        db,
        auth,
        "apply",
        {
            "operation": "code_studio_bind",
            "snapshot_id": snapshot_id,
            "confirm_phrase_accepted": True,
        },
    )
    return BindCodeOut(
        bind_kind=result["bind_kind"],
        code=result["code"],
        snapshot_id=result.get("snapshot_id"),
        server_action_id=result.get("server_action_id"),
        automation_id=result.get("automation_id"),
    )


@router.post("/option-a", response_model=OptionAOut)
def code_studio_option_a(
    connection_id: str,
    body: OptionABody,
    request: Request,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> OptionAOut:
    """Package Python as a module zip. Does not install or promote it."""
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    row = _connection(db, connection_id)
    try:
        major = int(str(getattr(row, "server_version", "") or "").split(".")[0])
    except ValueError:
        major = None
    try:
        exported = export_option_a_zip(
            name=body.name,
            model=body.model,
            code=body.code,
            technical_name=body.technical_name,
            depends=body.depends,
            as_extension=body.as_extension,
            odoo_major=major,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_audit_detail(
        request,
        {
            "operation": "code_studio_option_a",
            "technical_name": exported["technical_name"],
            "filename": exported["filename"],
            "installed": False,
            "promoted": False,
        },
    )
    _audit_chain(
        db,
        auth,
        "module",
        {
            "operation": "code_studio_option_a",
            "technical_name": exported["technical_name"],
            "filename": exported["filename"],
            "installed": False,
            "promoted": False,
        },
    )
    return OptionAOut(**exported)


def _model_depends(client: Any, model: str) -> list[str]:
    """Modules that define a built-in model, so the extension installs after them."""
    try:
        rows = client.execute_kw("ir.model", "search_read", [[["model", "=", model]]], {"fields": ["modules"], "limit": 1})
    except Exception:  # noqa: BLE001
        return ["base"]
    raw = str((rows[0].get("modules") if rows else "") or "")
    mods = [m.strip() for m in raw.split(",") if m.strip()]
    return mods or ["base"]


@router.post("/extension-scaffold", response_model=ExtensionScaffoldOut)
def code_studio_extension_scaffold(
    connection_id: str,
    body: ExtensionScaffoldBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> ExtensionScaffoldOut:
    """Draft a small _inherit module for a built-in model. Writes nothing to Odoo."""
    from app.code_studio_service import _slug_model, stock_extension_scaffold

    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    row = _connection(db, connection_id)
    if body.model.startswith("x_"):
        raise HTTPException(status_code=400, detail="This is for Odoo's own models. Change your own models from the Fields tab.")
    try:
        code = stock_extension_scaffold(
            model=body.model, kind=body.kind, field_name=body.field_name,
            label=body.label, options=body.options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    client = _client_or_502(row)
    return ExtensionScaffoldOut(
        code=code,
        depends=_model_depends(client, body.model),
        technical_name=_slug_model(body.model)[:60],
    )
