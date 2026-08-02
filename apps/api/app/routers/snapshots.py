"""Snapshot list + rollback endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.snapshots import list_snapshots, rollback_snapshot

router = APIRouter(prefix="/connections/{connection_id}/snapshots", tags=["snapshots"])


class SnapshotOut(BaseModel):
    id: str
    resource_type: str
    resource_key: str
    label: str
    reversible: str
    created_at: datetime | None

    model_config = {"from_attributes": True}


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("", response_model=list[SnapshotOut])
def get_snapshots(connection_id: str, db: Session = Depends(get_db)) -> list[SnapshotOut]:
    rows = list_snapshots(db, connection_id)
    return [SnapshotOut.model_validate(r) for r in rows]


@router.post("/{snapshot_id}/rollback")
def post_rollback(
    connection_id: str, snapshot_id: str, db: Session = Depends(get_db)
) -> dict:
    # Authz first: wrong connection_id / missing snapshot → 404 before Odoo RPC.
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from app.db_models import MetadataSnapshot

    snap = db.get(MetadataSnapshot, snapshot_id)
    if snap is None or snap.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Snapshot not found for this connection")

    client = _client(connection_id, db)
    try:
        result = rollback_snapshot(db, client, snapshot_id, connection_id=connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **result}
