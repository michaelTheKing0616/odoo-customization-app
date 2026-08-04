"""DEV-3 — Script Runner API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.code_studio_gating import assert_code_studio_entitlement, assert_developer_role
from app.db import get_db
from app.db_models import SavedScript, ScriptRun
from app.odoo_service import get_connection_or_404
from app.script_runner.service import (
    audit_detail_for_run,
    enqueue_script_run,
    list_templates,
    require_script_confirm,
    run_script_sync,
    script_hash,
)
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired
from app.workspace_auth import WorkspaceAuth, require_app_auth

router = APIRouter(prefix="/connections/{connection_id}/script-runner", tags=["script-runner"])


class RunScriptBody(BaseModel):
    script: str
    saved_script_id: str | None = None
    count_writes: bool = True
    async_job: bool = True
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class SavedScriptBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    script_content: str
    shared: bool = True


class SavedScriptOut(BaseModel):
    id: str
    name: str
    description: str | None
    script_content: str
    shared: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}


class ScriptRunOut(BaseModel):
    id: str
    job_id: str | None
    status: str
    script_content: str
    script_hash: str
    stdout: str | None
    stderr: str | None
    write_counts: dict[str, Any] = Field(default_factory=dict)
    error: str | None
    created_at: datetime | None
    finished_at: datetime | None


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


def _run_out(row: ScriptRun) -> ScriptRunOut:
    import json

    counts: dict[str, Any] = {}
    if row.write_counts_json:
        try:
            counts = json.loads(row.write_counts_json)
        except json.JSONDecodeError:
            counts = {}
    return ScriptRunOut(
        id=row.id,
        job_id=row.job_id,
        status=row.status,
        script_content=row.script_content,
        script_hash=row.script_hash,
        stdout=row.stdout,
        stderr=row.stderr,
        write_counts=counts,
        error=row.error,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


@router.get("/templates")
def script_templates() -> dict[str, Any]:
    return {"templates": list_templates()}


@router.get("/runs", response_model=list[ScriptRunOut])
def list_runs(connection_id: str, db: Session = Depends(get_db), limit: int = 30) -> list[ScriptRunOut]:
    rows = (
        db.query(ScriptRun)
        .filter(ScriptRun.connection_id == connection_id)
        .order_by(ScriptRun.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [_run_out(r) for r in rows]


@router.get("/runs/{run_id}", response_model=ScriptRunOut)
def get_run(connection_id: str, run_id: str, db: Session = Depends(get_db)) -> ScriptRunOut:
    row = db.get(ScriptRun, run_id)
    if row is None or row.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_out(row)


@router.get("/library", response_model=list[SavedScriptOut])
def list_saved_scripts(
    connection_id: str,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> list[SavedScriptOut]:
    row = get_connection_or_404(db, connection_id)
    if not row.workspace_id:
        return []
    q = db.query(SavedScript).filter(SavedScript.workspace_id == row.workspace_id)
    if auth.workspace_scoped and not auth.is_superadmin:
        q = q.filter(SavedScript.shared.is_(True))
    rows = q.order_by(SavedScript.updated_at.desc()).limit(100).all()
    return [SavedScriptOut.model_validate(r) for r in rows]


@router.post("/library", response_model=SavedScriptOut)
def save_script(
    connection_id: str,
    body: SavedScriptBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> SavedScriptOut:
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    conn = get_connection_or_404(db, connection_id)
    if not conn.workspace_id:
        raise HTTPException(status_code=422, detail="Connection must belong to a workspace")
    saved = SavedScript(
        workspace_id=conn.workspace_id,
        name=body.name,
        description=body.description,
        script_content=body.script_content,
        shared=body.shared,
        created_by=auth.user_id,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return SavedScriptOut.model_validate(saved)


@router.post("/run")
def run_script(
    connection_id: str,
    body: RunScriptBody,
    request: Request,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict[str, Any]:
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    conn = get_connection_or_404(db, connection_id)
    try:
        require_script_confirm(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            script=body.script,
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    workspace_id = conn.workspace_id or auth.workspace_id
    if body.async_job:
        run, job_id = enqueue_script_run(
            db,
            connection=conn,
            script=body.script,
            workspace_id=workspace_id,
            saved_script_id=body.saved_script_id,
            count_writes=body.count_writes,
        )
        request.state.audit_detail = audit_detail_for_run(script=body.script, run_id=run.id)
        return {"ok": True, "async": True, "job_id": job_id, "run_id": run.id}

    run = run_script_sync(
        db,
        connection=conn,
        script=body.script,
        workspace_id=workspace_id,
        count_writes=body.count_writes,
    )
    request.state.audit_detail = audit_detail_for_run(script=body.script, run_id=run.id)
    return {"ok": run.status == "succeeded", "async": False, "run": _run_out(run).model_dump()}
