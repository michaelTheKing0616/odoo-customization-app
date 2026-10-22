"""A4 — one History for everything.

Every write Ingenium makes for a connection already leaves a stored trail: a metadata snapshot
(the undo point), a bulk run, or a suite change run. This endpoint merges them into one plain
timeline with filters, and undo always goes through the same snapshot rollback.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_models import BulkRun, MetadataSnapshot
from app.odoo_service import get_connection_or_404

router = APIRouter(prefix="/connections/{connection_id}/history", tags=["history"])

# Snapshot resource type -> (page in plain words, record type label)
PAGE_OF: dict[str, str] = {
    "view": "Screens",
    "report": "Documents & emails",
    "paperformat": "Documents & emails",
    "automation": "Automations",
    "action": "Automations",
    "ir_cron": "Automations",
    "server_action": "Automations",
    "field": "Models & fields",
    "model": "Models & fields",
    "ir_default": "Models & fields",
    "menu": "Menus",
    "access": "Access",
    "rule": "Access",
    "script_run": "Code runner",
    "code_studio_test": "Code runner",
    "config_parameter": "Settings",
    "config_packet": "Settings",
    "dedupe_merge": "Data",
    "model_data_export": "Data",
    "field_data_export": "Data",
    "power_ops_pre_export": "Data",
    "record_values": "Data",
    "self_approval": "Approvals",
    "portal_access": "Access",
}


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def _record_type(snap: MetadataSnapshot) -> str | None:
    try:
        payload = json.loads(snap.payload_json or "{}")
    except (TypeError, ValueError):
        return None
    if isinstance(payload, dict):
        for k in ("model", "res_model", "model_name"):
            v = payload.get(k)
            if isinstance(v, str) and v:
                return v
    return None


def history_entries(db: Session, connection_id: str, limit: int = 200) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    snaps = (
        db.query(MetadataSnapshot)
        .filter(MetadataSnapshot.connection_id == connection_id)
        .order_by(MetadataSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )
    for s in snaps:
        out.append(
            {
                "id": f"snap:{s.id}",
                "kind": "snapshot",
                "page": PAGE_OF.get(s.resource_type, "Other"),
                "resource_type": s.resource_type,
                "record_type": _record_type(s),
                "label": s.label,
                "at": _iso(s.created_at),
                "undo": None if s.reversible == "no" else {"snapshot_id": s.id, "partial": s.reversible == "partial"},
                "receipt": {"resource_key": s.resource_key, "reversible": s.reversible},
            }
        )
    runs = (
        db.query(BulkRun)
        .filter(BulkRun.connection_id == connection_id, BulkRun.dry_run == "no")
        .order_by(BulkRun.created_at.desc())
        .limit(limit)
        .all()
    )
    for r in runs:
        out.append(
            {
                "id": f"bulk:{r.id}",
                "kind": "bulk_run",
                "page": "Run & look after",
                "resource_type": r.operation,
                "record_type": r.model,
                "label": f"{r.operation.replace('_', ' ').capitalize()}: {r.succeeded} of {r.total} updated"
                + (f", {r.failed} need you" if r.failed else ""),
                "at": _iso(r.created_at),
                "undo": None,
                "receipt": {"total": r.total, "succeeded": r.succeeded, "failed": r.failed},
            }
        )
    out.sort(key=lambda e: e["at"] or "", reverse=True)
    return out[:limit]


@router.get("")
def get_history(
    connection_id: str,
    page: str | None = Query(default=None, description="Plain page name, e.g. Access"),
    record_type: str | None = Query(default=None),
    resource_type: list[str] | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rows = history_entries(db, connection_id, limit=max(limit, 200))
    if page:
        rows = [r for r in rows if r["page"] == page]
    if record_type:
        rows = [r for r in rows if r["record_type"] == record_type]
    if resource_type:
        rows = [r for r in rows if r["resource_type"] in set(resource_type)]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in (r["label"] or "").lower() or ql in (r["record_type"] or "").lower()]
    pages = sorted({r["page"] for r in history_entries(db, connection_id)})
    return {"entries": rows[:limit], "pages": pages}
