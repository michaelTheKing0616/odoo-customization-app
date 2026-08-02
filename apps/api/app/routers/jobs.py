"""Background job status + audit purge."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_api_auth
from app.db import get_db
from app.db_models import AuditLog, BackgroundJob
from app.jobs import cancel_job, get_job
from app.settings import settings

router = APIRouter(tags=["jobs"], dependencies=[Depends(require_api_auth)])


class JobOut(BaseModel):
    id: str
    kind: str
    connection_id: str | None
    status: str
    result: dict | None = None
    error: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job_status(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    row = get_job(db, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    result = None
    if row.result_json:
        try:
            result = json.loads(row.result_json)
        except json.JSONDecodeError:
            result = {"raw": row.result_json}
    return JobOut(
        id=row.id,
        kind=row.kind,
        connection_id=row.connection_id,
        status=row.status,
        result=result,
        error=row.error,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job_endpoint(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    row = cancel_job(db, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    result = None
    if row.result_json:
        try:
            result = json.loads(row.result_json)
        except json.JSONDecodeError:
            result = {"raw": row.result_json}
    return JobOut(
        id=row.id,
        kind=row.kind,
        connection_id=row.connection_id,
        status=row.status,
        result=result,
        error=row.error,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


@router.post("/audit/purge")
def purge_audit_logs(
    days: int | None = Query(None, ge=1, le=3650),
    db: Session = Depends(get_db),
) -> dict:
    retain = days if days is not None else settings.audit_retention_days
    if retain <= 0:
        return {"deleted": 0, "note": "retention disabled (AUDIT_RETENTION_DAYS=0)"}
    cutoff = datetime.now(timezone.utc) - timedelta(days=retain)
    q = db.query(AuditLog).filter(AuditLog.created_at < cutoff)
    deleted = q.delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted, "older_than_days": retain}
