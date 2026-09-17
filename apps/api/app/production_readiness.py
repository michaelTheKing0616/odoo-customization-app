"""TRUST-8 — per-connection production readiness checklist."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.db_models import ConnectionProductionReadiness, HealthCheckRun, MetadataSnapshot, OdooConnection

CheckStatus = Literal["pass", "fail", "warn", "todo"]

ADMIN_USERNAMES = frozenset({"admin", "administrator"})
DRILL_RESOURCE_KEY = "drill:production-readiness"


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



def _rows_to_csv(headers: list[str], rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({h: row.get(h, "") for h in headers})
    return buf.getvalue()


def _m2o_label(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[1])
    if value in (False, None):
        return ""
    return str(value)


def _csv_from_tracked_snapshot(snap: MetadataSnapshot) -> tuple[str, str, str] | None:
    try:
        payload = json.loads(snap.payload_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    for key in ("view", "field", "model", "menu", "report", "access", "rule", "automation"):
        node = payload.get(key)
        if isinstance(node, dict) and node:
            headers = sorted(str(k) for k in node.keys() if k != "arch")
            row: dict[str, Any] = {}
            for h in headers:
                val = node.get(h)
                if isinstance(val, (dict, list)) and not (
                    isinstance(val, (list, tuple))
                    and len(val) == 2
                    and not isinstance(val[0], (dict, list))
                ):
                    val = json.dumps(val, ensure_ascii=False)[:200]
                elif str(h).endswith("_id"):
                    val = _m2o_label(val)
                row[h] = val
            if "arch" in node:
                headers = [*headers, "arch_present"]
                row["arch_present"] = "yes" if node.get("arch") else "no"
            if not headers:
                continue
            return (
                _rows_to_csv(headers, [row]),
                snap.resource_type or key,
                f"tracked:{snap.resource_key}",
            )

    flat = {k: v for k, v in payload.items() if not isinstance(v, (dict, list))}
    if not flat:
        return None
    headers = sorted(str(k) for k in flat.keys())[:12]
    return (
        _rows_to_csv(headers, [{h: flat.get(h) for h in headers}]),
        snap.resource_type or "snapshot",
        f"tracked:{snap.resource_key}",
    )


def _find_tracked_reversible_snapshot(db: Session, connection_id: str) -> MetadataSnapshot | None:
    return (
        db.query(MetadataSnapshot)
        .filter(
            MetadataSnapshot.connection_id == connection_id,
            MetadataSnapshot.reversible.in_(("yes", "partial")),
            MetadataSnapshot.resource_key != DRILL_RESOURCE_KEY,
        )
        .order_by(MetadataSnapshot.created_at.desc())
        .first()
    )


def _live_export_csv(connection: OdooConnection) -> tuple[str, str, str]:
    """Read-only live export when the connection has no tracked customizations yet."""
    from app.odoo_service import client_from_connection

    client = client_from_connection(connection)
    try:
        rows = client.execute_kw(
            "res.company",
            "search_read",
            [[]],
            {"fields": ["id", "name", "currency_id"], "limit": 5},
        )
        if rows:
            out_rows = [
                {
                    "id": r.get("id"),
                    "name": r.get("name") or "",
                    "currency_id": _m2o_label(r.get("currency_id")),
                }
                for r in rows
            ]
            return (
                _rows_to_csv(["id", "name", "currency_id"], out_rows),
                "res.company",
                "live:res.company",
            )
    except Exception:
        pass

    rows = client.execute_kw(
        "ir.model",
        "search_read",
        [[("transient", "=", False)]],
        {"fields": ["id", "model", "name"], "limit": 5, "order": "id asc"},
    )
    if not rows:
        raise RuntimeError("Live drill export returned no rows from res.company or ir.model")
    out_rows = [
        {"id": r.get("id"), "model": r.get("model") or "", "name": r.get("name") or ""}
        for r in rows
    ]
    return _rows_to_csv(["id", "model", "name"], out_rows), "ir.model", "live:ir.model"


def build_drill_csv_artifact(
    db: Session, connection: OdooConnection
) -> tuple[str, str, str, str]:
    """Return (csv_text, model, source, detail) for the drill download artifact."""
    tracked = _find_tracked_reversible_snapshot(db, connection.id)
    if tracked is not None:
        built = _csv_from_tracked_snapshot(tracked)
        if built is not None:
            csv_text, model, source = built
            detail = (
                f"Exported tracked reversible snapshot {tracked.resource_key} "
                f"({tracked.label})."
            )
            return csv_text, model, source, detail

    csv_text, model, source = _live_export_csv(connection)
    detail = f"Live read-only export of {model} from this connection."
    return csv_text, model, source, detail


def validate_drill_snapshot(snap: MetadataSnapshot) -> None:
    payload = json.loads(snap.payload_json)
    if payload.get("drill") is not True:
        raise ValueError("Not a production readiness drill snapshot")
    if payload.get("format") != "csv" or "csv" not in payload:
        raise ValueError("Drill snapshot missing CSV artifact payload")


def run_snapshot_drill(db: Session, connection: OdooConnection) -> str:
    """Create a reversible drill snapshot whose CSV is a real connection artifact.

    Prefer an existing tracked reversible MetadataSnapshot. Otherwise perform a
    read-only live Odoo export (res.company, else ir.model). Never writes to Odoo.
    """
    state = _get_or_create_state(db, connection.id)
    csv_text, model, source, detail = build_drill_csv_artifact(db, connection)
    payload = {
        "drill": True,
        "format": "csv",
        "model": model,
        "source": source,
        "detail": detail,
        "field_name": "drill",
        "csv": csv_text,
        "view": {"id": 0, "arch": '<form string="Drill"><field name="name"/></form>'},
    }
    snap = MetadataSnapshot(
        connection_id=connection.id,
        resource_type="view",
        resource_key=DRILL_RESOURCE_KEY,
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
                detail = (
                    json.loads(snap.payload_json).get("detail")
                    or "Drill snapshot created and payload validated."
                )
                items.append(
                    ChecklistItem(
                        key="snapshot_restore_drill",
                        label="Snapshot + restore drill",
                        status="pass",
                        detail=str(detail),
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
                status="todo",
                detail="Run the snapshot drill on this connection (exports a real CSV from your DB).",
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
    elif hc and (hc.broken_count or 0) > 0:
        items.append(
            ChecklistItem(
                key="health_check_green",
                label="Health check passed",
                status="fail",
                detail=f"Latest run has {hc.broken_count} broken item(s).",
            )
        )
    else:
        items.append(
            ChecklistItem(
                key="health_check_green",
                label="Health check passed",
                status="todo",
                detail="Run a health check and resolve any broken artifacts.",
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
                status="todo",
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
                status="todo",
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
                status="todo",
                detail="Download the drill CSV (real export from this connection), then mark verified.",
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
