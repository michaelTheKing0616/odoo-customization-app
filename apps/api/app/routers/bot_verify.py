"""BV-01: verify-run routes (contract only).

Each handler calls exactly one injected engine. The default engines say plainly
that verify runs are not available yet; BV-02+ replace them. Nothing here calls
Odoo: the live layer is read-only and walkthrough/flows touch only a disposable
clone, decided by the engine. Every error leaves as the B5 envelope.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.bot_verify.contract import (
    ArtifactFn,
    BVError,
    BVErrorEnvelope,
    GetFn,
    StartFn,
    VerifyRun,
    VerifyRunRequest,
)
from app.db import get_db
from app.routers.scans import ScanEnvelopeRoute
from app.scans.contract import ScanScope
from app.workspace_auth import WorkspaceAuth, get_scoped_connection_or_404, get_workspace_auth

_ERRORS: dict[int | str, dict[str, Any]] = {s: {"model": BVErrorEnvelope} for s in (403, 404, 422)}
_START_ERRORS: dict[int | str, dict[str, Any]] = {409: {"model": BVErrorEnvelope}}

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
