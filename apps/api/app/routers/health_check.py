"""Post-upgrade health check endpoints (TIER-4)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_models import HealthCheckRun, OdooConnection
from app.health_check import queue_health_check_job
from app.odoo_service import OdooClientError, client_from_connection
from app.schemas import HealthCheckItemOut, HealthCheckRunOut, HealthCheckTriggerOut

router = APIRouter(prefix="/connections", tags=["health-check"])


def _items_from_json(raw: str) -> list[HealthCheckItemOut]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[HealthCheckItemOut] = []
    for row in data:
        if isinstance(row, dict):
            out.append(HealthCheckItemOut(**row))
    return out


def _run_out(row: HealthCheckRun) -> HealthCheckRunOut:
    return HealthCheckRunOut(
        id=row.id,
        connection_id=row.connection_id,
        job_id=row.job_id,
        trigger=row.trigger,
        status=row.status,
        previous_version=row.previous_version,
        current_version=row.current_version,
        ok_count=row.ok_count,
        broken_count=row.broken_count,
        message=row.message,
        items=_items_from_json(row.report_json),
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


@router.get("/{connection_id}/health-check/latest", response_model=HealthCheckRunOut | None)
def get_latest_health_check(
    connection_id: str, db: Session = Depends(get_db)
) -> HealthCheckRunOut | None:
    if db.get(OdooConnection, connection_id) is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    row = (
        db.query(HealthCheckRun)
        .filter(HealthCheckRun.connection_id == connection_id)
        .order_by(HealthCheckRun.created_at.desc())
        .first()
    )
    if row is None:
        return None
    return _run_out(row)


@router.get("/{connection_id}/health-check/runs", response_model=list[HealthCheckRunOut])
def list_health_check_runs(
    connection_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[HealthCheckRunOut]:
    if db.get(OdooConnection, connection_id) is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    rows = (
        db.query(HealthCheckRun)
        .filter(HealthCheckRun.connection_id == connection_id)
        .order_by(HealthCheckRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_run_out(r) for r in rows]


@router.post("/{connection_id}/health-check/run", response_model=HealthCheckTriggerOut)
def trigger_health_check(
    connection_id: str,
    async_job: bool = Query(True, description="Run in background job thread"),
    db: Session = Depends(get_db),
) -> HealthCheckTriggerOut:
    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    previous = row.last_seen_version
    current = row.server_version

    if async_job:
        job_id = queue_health_check_job(
            db,
            connection_id=connection_id,
            trigger="manual",
            previous_version=previous,
            current_version=current,
        )
        run = (
            db.query(HealthCheckRun)
            .filter(HealthCheckRun.job_id == job_id)
            .order_by(HealthCheckRun.created_at.desc())
            .first()
        )
        return HealthCheckTriggerOut(
            job_id=job_id,
            run_id=run.id if run else None,
            async_job=True,
            message="Health sweep queued — poll GET /api/jobs/{job_id}",
        )

    try:
        client = client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    from app.health_check import run_health_check_sync

    run = run_health_check_sync(
        db,
        connection_id=connection_id,
        client=client,
        trigger="manual",
        previous_version=previous,
        current_version=current,
    )
    return HealthCheckTriggerOut(
        job_id=None,
        run_id=run.id,
        async_job=False,
        message=run.message,
        report=_run_out(run),
    )
