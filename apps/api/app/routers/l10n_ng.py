"""NG-01: Nigeria pack routes (contract only).

Each handler calls exactly one injected engine function. The default engines say
plainly that the Nigeria pack is not available yet; engine cards replace them.
Nothing here calls Odoo. Every error leaves as the B5 envelope (SCAN-01 route class).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.l10n_ng.contract import (
    BankConvert,
    BankConvertFn,
    BankConvertRequest,
    DetectFn,
    EinvoiceReadiness,
    NgDetect,
    NgPlanResponse,
    PayrollCompute,
    PayrollComputeRequest,
    PayrollFn,
    PlanFn,
    ReadinessFn,
)
from app.routers.scans import ScanEnvelopeRoute
from app.scans.contract import ScanError, ScanErrorEnvelope, ScanScope
from app.workspace_auth import WorkspaceAuth, get_scoped_connection_or_404, get_workspace_auth

_ERRORS: dict[int | str, dict[str, Any]] = {
    s: {"model": ScanErrorEnvelope} for s in (403, 404, 422)
}

router = APIRouter(
    prefix="/connections/{connection_id}/l10n-ng",
    tags=["l10n-ng"],
    route_class=ScanEnvelopeRoute,
    responses=_ERRORS,
)


def ng_scope(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ScanScope:
    """404 unless the connection belongs to the caller's workspace (or client grant)."""
    auth: WorkspaceAuth = get_workspace_auth(request)
    row = get_scoped_connection_or_404(db, connection_id, auth)
    return ScanScope(workspace_id=getattr(row, "workspace_id", None), connection_id=row.id)


def _not_ready(*_a: Any) -> Any:
    raise ScanError("NOT_FOUND", "The Nigeria pack isn't available on this server yet.")


def detect_engine() -> DetectFn:
    return _not_ready


def plan_engine() -> PlanFn:
    return _not_ready


def readiness_engine() -> ReadinessFn:
    return _not_ready


def payroll_engine() -> PayrollFn:
    return _not_ready


def bank_engine() -> BankConvertFn:
    return _not_ready


@router.get("/detect", response_model=NgDetect)
def detect(
    scope: ScanScope = Depends(ng_scope),
    engine: DetectFn = Depends(detect_engine),
) -> NgDetect:
    return engine(scope)


@router.post("/plan", response_model=NgPlanResponse)
def plan(
    scope: ScanScope = Depends(ng_scope),
    engine: PlanFn = Depends(plan_engine),
) -> NgPlanResponse:
    return engine(scope)


@router.get("/einvoice-readiness", response_model=EinvoiceReadiness)
def einvoice_readiness(
    scope: ScanScope = Depends(ng_scope),
    engine: ReadinessFn = Depends(readiness_engine),
) -> EinvoiceReadiness:
    return engine(scope)


@router.post("/payroll-compute", response_model=PayrollCompute)
def payroll_compute(
    body: PayrollComputeRequest,
    scope: ScanScope = Depends(ng_scope),
    engine: PayrollFn = Depends(payroll_engine),
) -> PayrollCompute:
    return engine(scope, body)


@router.post("/bank/convert", response_model=BankConvert)
def bank_convert(
    body: BankConvertRequest,
    scope: ScanScope = Depends(ng_scope),
    engine: BankConvertFn = Depends(bank_engine),
) -> BankConvert:
    return engine(scope, body)
