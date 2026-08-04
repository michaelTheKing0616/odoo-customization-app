"""TRUST-8 production readiness checklist API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import get_connection_or_404
from app.production_readiness import (
    ack_first_write,
    confirm_least_privilege,
    evaluate_production_readiness,
    run_snapshot_drill,
    verify_backup_artifact,
)
from app.schemas import LeastPrivilegeConfirmBody, ProductionReadinessItemOut, ProductionReadinessOut
from app.workspace_auth import WorkspaceAuth, require_admin

router = APIRouter(
    prefix="/connections/{connection_id}/production-readiness",
    tags=["production-readiness"],
)


def _report_out(db: Session, connection_id: str) -> ProductionReadinessOut:
    try:
        conn = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    report = evaluate_production_readiness(db, conn)
    from app.db_models import ConnectionProductionReadiness

    state = db.get(ConnectionProductionReadiness, connection_id)
    return ProductionReadinessOut(
        passed=report.passed,
        items=[
            ProductionReadinessItemOut(
                key=i.key,
                label=i.label,
                status=i.status,
                detail=i.detail,
            )
            for i in report.items
        ],
        drill_snapshot_id=report.drill_snapshot_id,
        updated_at=report.updated_at,
        first_write_acknowledged=bool(state and state.first_write_ack_at),
    )


@router.get("", response_model=ProductionReadinessOut)
def get_production_readiness(
    connection_id: str,
    db: Session = Depends(get_db),
) -> ProductionReadinessOut:
    return _report_out(db, connection_id)


class SnapshotDrillOut(BaseModel):
    ok: bool
    snapshot_id: str
    report: ProductionReadinessOut


@router.post("/snapshot-drill", response_model=SnapshotDrillOut)
def post_snapshot_drill(
    connection_id: str,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_admin),
) -> SnapshotDrillOut:
    try:
        conn = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snap_id = run_snapshot_drill(db, conn)
    report = _report_out(db, connection_id)
    return SnapshotDrillOut(ok=True, snapshot_id=snap_id, report=report)


@router.post("/confirm-least-privilege", response_model=ProductionReadinessOut)
def post_confirm_least_privilege(
    connection_id: str,
    body: LeastPrivilegeConfirmBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_admin),
) -> ProductionReadinessOut:
    try:
        conn = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        confirm_least_privilege(db, conn, acknowledge_admin=body.acknowledge_admin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _report_out(db, connection_id)


@router.post("/verify-backup-artifact", response_model=ProductionReadinessOut)
def post_verify_backup_artifact(
    connection_id: str,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_admin),
) -> ProductionReadinessOut:
    try:
        verify_backup_artifact(db, connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _report_out(db, connection_id)


@router.post("/ack-first-write", response_model=ProductionReadinessOut)
def post_ack_first_write(
    connection_id: str,
    db: Session = Depends(get_db),
) -> ProductionReadinessOut:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    ack_first_write(db, connection_id)
    return _report_out(db, connection_id)
