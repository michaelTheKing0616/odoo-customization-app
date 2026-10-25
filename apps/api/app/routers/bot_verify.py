"""BV-01: verify-run routes (contract only).

Each handler calls exactly one injected engine. The default engines say plainly
that verify runs are not available yet; BV-02+ replace them. Nothing here calls
Odoo: the live layer is read-only and walkthrough/flows touch only a disposable
clone, decided by the engine. Every error leaves as the B5 envelope.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_models import WorkspaceMembership
from app.bot_verify.contract import (
    ArtifactFn,
    BVError,
    BVErrorEnvelope,
    GetFn,
    StartFn,
    VerifyRun,
    VerifyRunRequest,
)
from app.bot_verify.targets import ensure_audit_store
from app.db import get_db
from app.routers.scans import ScanEnvelopeRoute
from app.scans.contract import ScanScope
from app.workspace_auth import WorkspaceAuth, get_scoped_connection_or_404, get_workspace_auth

_ERRORS: dict[int | str, dict[str, Any]] = {s: {"model": BVErrorEnvelope} for s in (403, 404, 422)}
_START_ERRORS: dict[int | str, dict[str, Any]] = {409: {"model": BVErrorEnvelope}}

_log = logging.getLogger("ingenium.bot_verify.approval")

router = APIRouter(
    prefix="/connections/{connection_id}/verify-runs",
    tags=["verify-runs"],
    route_class=ScanEnvelopeRoute,
    responses=_ERRORS,
)


def bv_scope(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ScanScope:
    """404 unless the connection belongs to the caller's workspace (or client grant)."""
    auth: WorkspaceAuth = get_workspace_auth(request)
    row = get_scoped_connection_or_404(db, connection_id, auth)
    return ScanScope(workspace_id=getattr(row, "workspace_id", None), connection_id=row.id)


def _not_ready(*_a: Any) -> Any:
    raise BVError("NOT_FOUND", "Verify runs aren't available on this server yet.")


def start_engine() -> StartFn:
    return _not_ready


def get_engine() -> GetFn:
    return _not_ready


def artifact_engine() -> ArtifactFn:
    return _not_ready


@router.post("", response_model=VerifyRun, status_code=202, responses=_START_ERRORS)
def start_verify_run(
    body: VerifyRunRequest,
    scope: ScanScope = Depends(bv_scope),
    engine: StartFn = Depends(start_engine),
) -> VerifyRun:
    return engine(scope, body)


@router.get("/{run_id}", response_model=VerifyRun)
def get_verify_run(
    run_id: str,
    scope: ScanScope = Depends(bv_scope),
    engine: GetFn = Depends(get_engine),
) -> VerifyRun:
    return engine(scope, run_id)


@router.get(
    "/{run_id}/artifacts/{artifact_id}",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def get_verify_artifact(
    run_id: str,
    artifact_id: str,
    scope: ScanScope = Depends(bv_scope),
    engine: ArtifactFn = Depends(artifact_engine),
) -> Response:
    return Response(content=engine(scope, run_id, artifact_id), media_type="image/png")


class WalkApprovalRequest(BaseModel):
    """Only the decision; owner and approver always come from the server."""

    allowed: bool


class WalkApprovalOut(BaseModel):
    connection_id: str
    walkthrough_allowed: bool


@router.put("/walk-approval", response_model=WalkApprovalOut)
def set_walk_approval(
    connection_id: str,
    body: WalkApprovalRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> WalkApprovalOut:
    """BV-AUDIT-WIRE AC4/AC5: the workspace owner grants or revokes production walks."""
    auth: WorkspaceAuth = get_workspace_auth(request)
    row = get_scoped_connection_or_404(db, connection_id, auth)
    if auth.mode != "accounts" or auth.api_key_authenticated or not auth.user_id:
        raise BVError(
            "ROLE_DENIED", "Only the workspace owner, signed in, can approve walkthroughs."
        )
    is_owner = db.execute(
        select(WorkspaceMembership.id).where(
            WorkspaceMembership.workspace_id == row.workspace_id,
            WorkspaceMembership.user_id == auth.user_id,
            WorkspaceMembership.role == "owner",
        )
    ).first()
    owner_id = auth.user_id
    if is_owner is None:
        raise BVError("ROLE_DENIED", "Only the workspace owner can approve walkthroughs.")
    store = ensure_audit_store()
    if store is None:
        raise BVError(
            "TARGET_NOT_ALLOWED", "Walkthrough approvals aren't available on this server yet."
        )
    decision = "approval_granted" if body.allowed else "approval_revoked"
    try:
        store.set_approval(
            row.id,
            allowed=body.allowed,
            approved_by=auth.user_id,
            owner_id=owner_id,
            audit=(row.db_name, decision, "owner walkthrough approval"),
        )
    except Exception as exc:  # noqa: BLE001 - unaudited approval must not stand
        _log.error("walk approval save failed: %s", type(exc).__name__)
        raise BVError("TARGET_NOT_ALLOWED", "Couldn't save the approval. Try again.") from exc
    return WalkApprovalOut(connection_id=row.id, walkthrough_allowed=body.allowed)
