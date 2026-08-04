"""Snapshot list + rollback endpoints."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_models import MetadataSnapshot
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
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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


@router.get("/{snapshot_id}/artifact.json")
def download_snapshot_artifact_json(
    connection_id: str,
    snapshot_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snap = db.get(MetadataSnapshot, snapshot_id)
    if snap is None or snap.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Snapshot not found for this connection")
    payload = json.loads(snap.payload_json)
    fmt = payload.get("format")
    if fmt == "model_records_json" and "json" in payload:
        body = str(payload["json"])
        filename = f"{payload.get('model', 'model')}_records.json".replace("/", "_")
    elif fmt == "dedupe_merge" or snap.resource_type == "dedupe_merge":
        body = json.dumps(payload, indent=2, default=str)
        filename = f"dedupe_merge_{payload.get('model', 'records')}.json".replace("/", "_")
    elif "losers" in payload or "loser_ids" in payload:
        body = json.dumps(payload, indent=2, default=str)
        filename = "merge_backup.json"
    else:
        body = json.dumps(payload, indent=2, default=str)
        filename = f"snapshot_{snapshot_id[:8]}.json"
    return StreamingResponse(
        iter([body.encode("utf-8")]),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{snapshot_id}/artifact.csv")
def download_snapshot_artifact_csv(
    connection_id: str,
    snapshot_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snap = db.get(MetadataSnapshot, snapshot_id)
    if snap is None or snap.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Snapshot not found for this connection")
    payload = json.loads(snap.payload_json)
    if payload.get("format") != "csv" or "csv" not in payload:
        raise HTTPException(status_code=404, detail="No CSV artifact on this snapshot")
    model = str(payload.get("model") or "export")
    field_name = str(payload.get("field_name") or "data")
    filename = f"{model}_{field_name}.csv".replace("/", "_")
    csv_text = str(payload["csv"])
    return StreamingResponse(
        iter([csv_text.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
