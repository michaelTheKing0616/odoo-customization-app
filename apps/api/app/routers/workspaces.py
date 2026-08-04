"""Workspace-level settings (TRUST-2 kill switch)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.account_models import Workspace
from app.db import get_db
from app.schemas import WritesPausedUpdate
from app.workspace_auth import WorkspaceAuth, require_admin

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceSettingsOut(BaseModel):
    id: str
    name: str
    writes_paused: bool


@router.patch("/writes-paused", response_model=WorkspaceSettingsOut)
def update_workspace_writes_paused(
    body: WritesPausedUpdate,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_admin),
) -> WorkspaceSettingsOut:
    ws: Workspace | None = None
    if auth.workspace_id:
        ws = db.get(Workspace, auth.workspace_id)
    elif auth.mode == "off":
        ws = db.query(Workspace).order_by(Workspace.created_at).first()
    if ws is None:
        raise HTTPException(status_code=400, detail="No workspace in session")
    ws.writes_paused = body.writes_paused
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return WorkspaceSettingsOut(id=ws.id, name=ws.name, writes_paused=ws.writes_paused)
