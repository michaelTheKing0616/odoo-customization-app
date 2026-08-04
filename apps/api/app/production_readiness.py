"""TRUST-8 — per-connection production readiness checklist."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.db_models import ConnectionProductionReadiness, HealthCheckRun, MetadataSnapshot, OdooConnection

CheckStatus = Literal["pass", "fail", "warn"]

ADMIN_USERNAMES = frozenset({"admin", "administrator"})


@dataclass(frozen=True)
class ChecklistItem:
    key: str
    label: str
    status: CheckStatus
    detail: str


@dataclass(frozen=True)
class ProductionReadinessReport:
    passed: bool
    items: tuple[ChecklistItem, ...]
    drill_snapshot_id: str | None
    updated_at: datetime | None


def _get_or_create_state(db: Session, connection_id: str) -> ConnectionProductionReadiness:
    row = db.get(ConnectionProductionReadiness, connection_id)
    if row is None:
        row = ConnectionProductionReadiness(connection_id=connection_id)
        db.add(row)
        db.flush()
    return row


def _is_admin_username(username: str) -> bool:
    return username.strip().lower() in ADMIN_USERNAMES


def _latest_health_check(db: Session, connection_id: str) -> HealthCheckRun | None:
    return (
        db.query(HealthCheckRun)
        .filter(HealthCheckRun.connection_id == connection_id)
        .order_by(HealthCheckRun.created_at.desc())
        .first()
    )


def validate_drill_snapshot(snap: MetadataSnapshot) -> None:
    payload = json.loads(snap.payload_json)
    if payload.get("drill") is not True:
        raise ValueError("Not a production readiness drill snapshot")
    if payload.get("format") != "csv" or "csv" not in payload:
        raise ValueError("Drill snapshot missing CSV artifact payload")


def run_snapshot_drill(db: Session, connection: OdooConnection) -> str:
    """Create a reversible drill snapshot (app DB only — no Odoo RPC)."""
    state = _get_or_create_state(db, connection.id)
    payload = {
        "drill": True,
        "format": "csv",
        "model": "production_readiness",
        "field_name": "drill",
        "csv": "id,note\n1,production-readiness-drill\n",
        "view": {"id": 0, "arch": "<form string=\"Drill\"><field name=\"name\"/></form>"},
    }
    snap = MetadataSnapshot(
        connection_id=connection.id,
        resource_type="view",
        resource_key="drill:production-readiness",
        label="Production readiness drill",
        payload_json=json.dumps(payload),
        reversible="yes",
    )
    db.add(snap)
    db.flush()
    validate_drill_snapshot(snap)
    now = datetime.now(timezone.utc)
    state.snapshot_drill_at = now
    state.snapshot_drill_id = snap.id
    state.updated_at = now
    db.add(state)
    db.commit()
    db.refresh(snap)
    return snap.id


def confirm_least_privilege(
    db: Session,
    connection: OdooConnection,
    *,
    acknowledge_admin: bool,
) -> None:
    if _is_admin_username(connection.username) and not acknowledge_admin:
        raise ValueError(
            "Connection uses an admin-style Odoo user — acknowledge the least-privilege warning."
        )
    state = _get_or_create_state(db, connection.id)
    now = datetime.now(timezone.utc)
    state.least_privilege_confirmed_at = now
    state.updated_at = now
    db.add(state)
    db.commit()


def verify_backup_artifact(db: Session, connection_id: str) -> None:
    state = _get_or_create_state(db, connection_id)
    if not state.snapshot_drill_id:
        raise ValueError("Run the snapshot drill before verifying backup artifact download.")
    snap = db.get(MetadataSnapshot, state.snapshot_drill_id)
    if snap is None or snap.connection_id != connection_id:
        raise ValueError("Drill snapshot missing — re-run the snapshot drill.")
    validate_drill_snapshot(snap)
    now = datetime.now(timezone.utc)
    state.backup_artifact_verified_at = now
    state.updated_at = now
    db.add(state)
    db.commit()


def ack_first_write(db: Session, connection_id: str) -> None:
    state = _get_or_create_state(db, connection_id)
    now = datetime.now(timezone.utc)
    state.first_write_ack_at = now
    state.updated_at = now
    db.add(state)
    db.commit()


def evaluate_production_readiness(db: Session, connection: OdooConnection) -> ProductionReadinessReport:
    state = db.get(ConnectionProductionReadiness, connection.id)
    items: list[ChecklistItem] = []

    if state and state.snapshot_drill_at and state.snapshot_drill_id:
        snap = db.get(MetadataSnapshot, state.snapshot_drill_id)
        if snap is not None:
            try:
                validate_drill_snapshot(snap)
                items.append(
                    ChecklistItem(
                        key="snapshot_restore_drill",
                        label="Snapshot + restore drill",
                        status="pass",
                        detail="Drill snapshot created and payload validated.",
                    )
                )
            except ValueError as exc:
                items.append(
                    ChecklistItem(
                        key="snapshot_restore_drill",
                        label="Snapshot + restore drill",
                        status="fail",
                        detail=str(exc),
                    )
                )
        else:
            items.append(
                ChecklistItem(
                    key="snapshot_restore_drill",
                    label="Snapshot + restore drill",
                    status="fail",
                    detail="Drill snapshot record missing — re-run drill.",
                )
            )
    else:
        items.append(
            ChecklistItem(
                key="snapshot_restore_drill",
                label="Snapshot + restore drill",
                status="fail",
                detail="Run the snapshot drill on this connection.",
            )
        )

    hc = _latest_health_check(db, connection.id)
    if hc and hc.status == "complete" and hc.broken_count == 0:
        items.append(
            ChecklistItem(
                key="health_check_green",
                label="Health check passed",
                status="pass",
                detail=f"Latest run: {hc.ok_count} OK, 0 broken.",
            )
        )
    elif hc and hc.status == "running":
        items.append(
            ChecklistItem(
                key="health_check_green",
                label="Health check passed",
                status="fail",
                detail="Health check still running — wait for completion.",
            )
        )
    else:
        detail = "Run a health check and resolve broken artifacts."
        if hc and hc.broken_count:
            detail = f"Latest run has {hc.broken_count} broken item(s)."
        items.append(
            ChecklistItem(
                key="health_check_green",
                label="Health check passed",
                status="fail",
                detail=detail,
            )
        )

    if connection.server_version:
        items.append(
            ChecklistItem(
                key="capability_matrix_probed",
                label="Capability matrix probed",
                status="pass",
                detail=f"Server version {connection.server_version} recorded.",
            )
        )
    else:
        items.append(
            ChecklistItem(
                key="capability_matrix_probed",
                label="Capability matrix probed",
                status="fail",
                detail="Probe the connection from Overview (records server version).",
            )
        )

    if state and state.least_privilege_confirmed_at:
        if _is_admin_username(connection.username):
            items.append(
                ChecklistItem(
                    key="least_privilege_confirmed",
                    label="Least-privilege credential",
                    status="warn",
                    detail=(
                        f"Confirmed, but Odoo user '{connection.username}' looks like admin — "
                        "prefer a dedicated scoped user."
                    ),
                )
            )
        else:
            items.append(
                ChecklistItem(
                    key="least_privilege_confirmed",
                    label="Least-privilege credential",
                    status="pass",
                    detail=f"Confirmed for user '{connection.username}'.",
                )
            )
    else:
        admin_hint = ""
        if _is_admin_username(connection.username):
            admin_hint = f" User '{connection.username}' looks like admin — acknowledge the warning."
        items.append(
            ChecklistItem(
                key="least_privilege_confirmed",
                label="Least-privilege credential",
                status="fail",
                detail=f"Confirm least-privilege setup.{admin_hint}",
            )
        )

    if state and state.backup_artifact_verified_at:
        items.append(
            ChecklistItem(
                key="backup_artifact_verified",
                label="Backup artifact download",
                status="pass",
                detail="Drill CSV artifact download verified.",
            )
        )
    else:
        items.append(
            ChecklistItem(
                key="backup_artifact_verified",
                label="Backup artifact download",
                status="fail",
                detail="Download the drill snapshot CSV, then mark verified.",
            )
        )

    passed = all(item.status in {"pass", "warn"} for item in items)
    return ProductionReadinessReport(
        passed=passed,
        items=tuple(items),
        drill_snapshot_id=state.snapshot_drill_id if state else None,
        updated_at=state.updated_at if state else None,
    )


def production_readiness_passed(db: Session, connection: OdooConnection) -> bool:
    return evaluate_production_readiness(db, connection).passed
