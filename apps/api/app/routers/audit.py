"""Audit log listing."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_api_auth
from app.db import get_db
from app.db_models import AuditLog

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(require_api_auth)],
)


class AuditLogOut(BaseModel):
    id: str
    method: str
    path: str
    status_code: int
    client_ip: str | None
    api_key_prefix: str | None
    duration_ms: int | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("/logs", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [AuditLogOut.model_validate(r) for r in rows]
