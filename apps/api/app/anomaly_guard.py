"""TRUST-3 anomaly guard — hourly mutation budget per connection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.account_models import Workspace
from app.db_models import ConnectionMutationHourly, OdooConnection, TrustAnomalyEvent
from app.settings import settings


def _hour_bucket(now: datetime | None = None) -> datetime:
    ts = now or datetime.now(timezone.utc)
    return ts.replace(minute=0, second=0, microsecond=0)


def _plan_exempt(plan: str | None) -> bool:
    if not settings.bulk_anomaly_exempt_internal:
        return False
    return (plan or "").strip().lower() == "internal"


def record_connection_mutations(
    db: Session,
    *,
    connection_id: str,
    mutation_count: int,
    workspace: Workspace | None = None,
) -> TrustAnomalyEvent | None:
    """Increment hourly counter; auto-pause connection when threshold exceeded."""
    if mutation_count <= 0:
        return None
    plan = workspace.plan if workspace is not None else None
    if _plan_exempt(plan):
        return None

    bucket = _hour_bucket()
    row = (
        db.query(ConnectionMutationHourly)
        .filter(
            ConnectionMutationHourly.connection_id == connection_id,
            ConnectionMutationHourly.hour_bucket == bucket,
        )
        .first()
    )
    if row is None:
        row = ConnectionMutationHourly(
            id=str(uuid.uuid4()),
            connection_id=connection_id,
            hour_bucket=bucket,
            mutation_count=0,
        )
        db.add(row)
    row.mutation_count = int(row.mutation_count or 0) + mutation_count
    db.add(row)

    limit = max(1, settings.bulk_anomaly_hourly_limit)
    if row.mutation_count < limit:
        db.commit()
        return None

    conn = db.get(OdooConnection, connection_id)
    if conn is not None and not conn.writes_paused:
        conn.writes_paused = True
        db.add(conn)

    event = TrustAnomalyEvent(
        id=str(uuid.uuid4()),
        connection_id=connection_id,
        workspace_id=workspace.id if workspace is not None else None,
        mutation_count=row.mutation_count,
        threshold=limit,
        hour_bucket=bucket,
        action="writes_paused",
    )
    db.add(event)
    db.commit()
    return event
