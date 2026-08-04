"""TRUST-9 — self-hosted trust telemetry for GA evidence (no external SaaS)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.account_models import Workspace
from app.db_models import AuditLog, BulkRun, OdooConnection, TrustAnomalyEvent
from app.settings import settings

_CONNECTION_PATH = re.compile(r"/api/connections/([0-9a-f-]{36})")


@dataclass(frozen=True)
class WorkspaceTrustTelemetry:
    workspace_id: str
    workspace_name: str
    beta_partner: bool
    bulk_runs: int
    bulk_aborts: int
    safety_refusals: int
    snapshot_restores: int
    anomaly_trips: int


def _connection_workspace_map(db: Session) -> dict[str, str | None]:
    rows = db.query(OdooConnection.id, OdooConnection.workspace_id).all()
    return {cid: ws_id for cid, ws_id in rows}


def _workspace_for_audit_path(path: str, conn_map: dict[str, str | None]) -> str | None:
    match = _CONNECTION_PATH.search(path)
    if not match:
        return None
    return conn_map.get(match.group(1))


def summarize_workspace_telemetry(db: Session, workspace_id: str) -> WorkspaceTrustTelemetry:
    ws = db.get(Workspace, workspace_id)
    name = ws.name if ws else workspace_id
    beta = bool(getattr(ws, "beta_partner", False)) if ws else False

    conn_ids = [
        r[0]
        for r in db.query(OdooConnection.id).filter(OdooConnection.workspace_id == workspace_id).all()
    ]

    bulk_runs = 0
    bulk_aborts = 0
    if conn_ids:
        bulk_runs = (
            db.query(func.count(BulkRun.id))
            .filter(BulkRun.connection_id.in_(conn_ids), BulkRun.dry_run == "no")
            .scalar()
            or 0
        )
        abort_rows = (
            db.query(BulkRun.result_json)
            .filter(BulkRun.connection_id.in_(conn_ids))
            .all()
        )
        for (raw,) in abort_rows:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if payload.get("aborted") or payload.get("abort_requested"):
                bulk_aborts += 1

    anomaly_trips = (
        db.query(func.count(TrustAnomalyEvent.id))
        .filter(TrustAnomalyEvent.workspace_id == workspace_id)
        .scalar()
        or 0
    )

    conn_map = _connection_workspace_map(db)
    audit_rows = (
        db.query(AuditLog.path, AuditLog.method, AuditLog.status_code)
        .filter(
            AuditLog.method == "POST",
            AuditLog.path.like("%/snapshots/%/rollback"),
            AuditLog.status_code == 200,
        )
        .all()
    )
    restores = sum(
        1
        for path, _method, _status in audit_rows
        if _workspace_for_audit_path(path, conn_map) == workspace_id
    )

    refusal_rows = (
        db.query(AuditLog.path, AuditLog.status_code)
        .filter(AuditLog.status_code.in_([403, 409]), AuditLog.path.like("/api/%"))
        .all()
    )
    refusals = sum(
        1
        for path, _status in refusal_rows
        if _workspace_for_audit_path(path, conn_map) == workspace_id
    )

    return WorkspaceTrustTelemetry(
        workspace_id=workspace_id,
        workspace_name=name,
        beta_partner=beta,
        bulk_runs=int(bulk_runs),
        bulk_aborts=int(bulk_aborts),
        safety_refusals=int(refusals),
        snapshot_restores=int(restores),
        anomaly_trips=int(anomaly_trips),
    )


def summarize_all_workspaces(db: Session, *, limit: int = 200) -> list[WorkspaceTrustTelemetry]:
    rows = db.query(Workspace).order_by(Workspace.created_at.desc()).limit(limit).all()
    return [summarize_workspace_telemetry(db, ws.id) for ws in rows]


def ga_evidence_summary(db: Session) -> dict:
    """Roll-up against default GA thresholds (tunable via env)."""
    telemetry = summarize_all_workspaces(db)
    beta_rows = [t for t in telemetry if t.beta_partner]
    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "beta_partner_workspaces": len(beta_rows),
        "threshold_workspaces": settings.beta_ga_min_workspaces,
        "threshold_weeks_per_workspace": settings.beta_ga_min_weeks,
        "totals": {
            "bulk_runs": sum(t.bulk_runs for t in beta_rows),
            "bulk_aborts": sum(t.bulk_aborts for t in beta_rows),
            "safety_refusals": sum(t.safety_refusals for t in beta_rows),
            "snapshot_restores": sum(t.snapshot_restores for t in beta_rows),
            "anomaly_trips": sum(t.anomaly_trips for t in beta_rows),
        },
        "workspaces": [
            {
                "workspace_id": t.workspace_id,
                "name": t.workspace_name,
                "beta_partner": t.beta_partner,
                "bulk_runs": t.bulk_runs,
                "bulk_aborts": t.bulk_aborts,
                "safety_refusals": t.safety_refusals,
                "snapshot_restores": t.snapshot_restores,
                "anomaly_trips": t.anomaly_trips,
            }
            for t in telemetry
        ],
    }
