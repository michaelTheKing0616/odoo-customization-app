"""Read-only fleet counts for the consultant command center (/command)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_models import BackgroundJob, OdooConnection, PlanCardRecord
from app.workspace_auth import WorkspaceAuth, get_workspace_auth, scoped_connection_query

router = APIRouter(prefix="/command", tags=["command"])


class TileCountOut(BaseModel):
    count: int


def _require_consultant_home(auth: WorkspaceAuth) -> None:
    if auth.client_limited:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": "Client accounts use the approval inbox, not the command center.",
                "role": auth.role,
            },
        )


def _scoped_connection_ids(db: Session, auth: WorkspaceAuth) -> list[str]:
    rows = scoped_connection_query(db, auth).with_entities(OdooConnection.id).all()
    return [row[0] for row in rows]


@router.get("/tiles/clients", response_model=TileCountOut)
def tile_clients(
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(get_workspace_auth),
) -> TileCountOut:
    _require_consultant_home(auth)
    count = scoped_connection_query(db, auth).count()
    return TileCountOut(count=count)


@router.get("/tiles/pending-approvals", response_model=TileCountOut)
def tile_pending_approvals(
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(get_workspace_auth),
) -> TileCountOut:
    _require_consultant_home(auth)
    ids = _scoped_connection_ids(db, auth)
    if not ids:
        return TileCountOut(count=0)
    count = (
        db.query(PlanCardRecord)
        .filter(
            PlanCardRecord.connection_id.in_(ids),
            PlanCardRecord.status == "pending",
        )
        .count()
    )
    return TileCountOut(count=count)


@router.get("/tiles/failed-jobs", response_model=TileCountOut)
def tile_failed_jobs(
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(get_workspace_auth),
) -> TileCountOut:
    _require_consultant_home(auth)
    ids = _scoped_connection_ids(db, auth)
    if not ids:
        return TileCountOut(count=0)
    count = (
        db.query(BackgroundJob)
        .filter(
            BackgroundJob.connection_id.in_(ids),
            BackgroundJob.status == "failed",
        )
        .count()
    )
    return TileCountOut(count=count)


@router.get("/tiles/drift", response_model=TileCountOut)
def tile_drift(
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(get_workspace_auth),
) -> TileCountOut:
    _require_consultant_home(auth)
    count = (
        scoped_connection_query(db, auth)
        .filter(OdooConnection.upgrade_detected.is_(True))
        .count()
    )
    return TileCountOut(count=count)
