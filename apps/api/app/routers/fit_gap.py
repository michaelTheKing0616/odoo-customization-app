"""FITGAP-01: fit-gap routes (contract only).

Each handler calls exactly one injected engine function. The default engines say
plainly that fit-gap is not available yet; engine cards replace them. Nothing here
calls Odoo. Every error leaves as the B5 envelope (shared SCAN-01 route class).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.delivery.fit_gap_types import (
    CreateFitGapFn,
    FitGapDoc,
    FitGapLine,
    FitGapRequest,
    GetFitGapFn,
    LineOverride,
    OverrideLineFn,
)
from app.routers.scans import ScanEnvelopeRoute
from app.scans.contract import ScanError, ScanErrorEnvelope, ScanScope
from app.workspace_auth import WorkspaceAuth, get_scoped_connection_or_404, get_workspace_auth

_ERRORS: dict[int | str, dict[str, Any]] = {
    s: {"model": ScanErrorEnvelope} for s in (403, 404, 409, 422, 429)
}

router = APIRouter(
    prefix="/connections/{connection_id}",
    tags=["fit-gap"],
    route_class=ScanEnvelopeRoute,
    responses=_ERRORS,
)


def fitgap_scope(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ScanScope:
    """404 unless the connection belongs to the caller's workspace (or client grant)."""
    auth: WorkspaceAuth = get_workspace_auth(request)
    row = get_scoped_connection_or_404(db, connection_id, auth)
    return ScanScope(workspace_id=getattr(row, "workspace_id", None), connection_id=row.id)


def _not_ready(*_a: Any) -> Any:
    raise ScanError("NOT_FOUND", "Fit-gap isn't available on this server yet.")


def create_engine() -> CreateFitGapFn:
    return _not_ready


def get_engine() -> GetFitGapFn:
    return _not_ready


def override_engine() -> OverrideLineFn:
    return _not_ready


@router.post("/fitgap", response_model=FitGapDoc, status_code=202)
def create_fitgap(
    body: FitGapRequest,
    response: Response,
    scope: ScanScope = Depends(fitgap_scope),
    engine: CreateFitGapFn = Depends(create_engine),
) -> FitGapDoc:
    doc, created = engine(scope, body)
    if not created:
        response.status_code = 200  # idempotent on (doc_sha256, catalog_version)
    return doc


@router.get("/fitgap/{doc_id}", response_model=FitGapDoc)
def get_fitgap(
    doc_id: str,
    scope: ScanScope = Depends(fitgap_scope),
    engine: GetFitGapFn = Depends(get_engine),
) -> FitGapDoc:
    return engine(scope, doc_id)


@router.patch("/fitgap/{doc_id}/lines/{lid}", response_model=FitGapLine)
def override_line(
    doc_id: str,
    lid: str,
    body: LineOverride,
    scope: ScanScope = Depends(fitgap_scope),
    engine: OverrideLineFn = Depends(override_engine),
) -> FitGapLine:
    return engine(scope, doc_id, lid, body)
