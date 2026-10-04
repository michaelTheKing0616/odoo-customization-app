"""Production DESTRUCTIVE/BILLABLE/code applies require a fresh connection snapshot."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.rpc_classify import _is_billable_method

FRESHNESS_WINDOW = timedelta(minutes=10)
_GATED_RISKS = frozenset({"destructive", "code", "billable"})


class SnapshotRequired(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _requires_snapshot(*, risk: str, method: str | None) -> bool:
    if risk.lower() in _GATED_RISKS:
        return True
    return bool(method) and _is_billable_method(method)


def require_production_snapshot(
    *,
    write_mode: str,
    risk: str,
    snapshot_id: str | None,
    snapshot_exists: bool,
    snapshot_created_at: datetime | None = None,
    last_write_audited_at: datetime | None = None,
    snapshot_connection_id: str | None = None,
    connection_id: str | None = None,
    method: str | None = None,
    odoo_major: int | None = None,
    snapshot_kind: str = "metadata",
    require_web_database_backup: bool = False,
    now: datetime | None = None,
) -> None:
    """Raise SnapshotRequired if a production gated apply has no immediate snapshot.

    write_mode other than production returns immediately.
    Gated risks: destructive, code, billable (any case). BILLABLE methods
    (button_install family, iap_*, *_iap_*, action_buy_*) are gated even when
    risk is not already named billable.
    On Odoo 20 and later a metadata snapshot is enough; ``/web/database`` backup is not required.
    """
    if write_mode != "production":
        return
    if not _requires_snapshot(risk=risk, method=method):
        return
    if not snapshot_id or not snapshot_exists:
        raise SnapshotRequired(
            "A snapshot recorded for this connection is required before a "
            "destructive or billable production apply."
        )
    if connection_id is not None and snapshot_connection_id != connection_id:
        raise SnapshotRequired("Snapshot belongs to a different connection.")
    # Odoo 20 and later removed the db service. A metadata_snapshots row is
    # accepted; do not require /web/database backup even if a caller asks for one.
    # None and any non-int stay off this path.
    if isinstance(odoo_major, int) and odoo_major >= 20:
        require_web_database_backup = False
    if require_web_database_backup and snapshot_kind != "database":
        raise SnapshotRequired(
            "A /web/database backup is required for this major; Odoo 20 and later accept a metadata snapshot instead."
        )
    if snapshot_created_at is None:
        raise SnapshotRequired(
            "Snapshot created_at is required to prove it was taken immediately before the apply."
        )
    clock = _aware(now or datetime.now(timezone.utc))
    created = _aware(snapshot_created_at)
    age = clock - created
    if age < timedelta(0) or age > FRESHNESS_WINDOW:
        raise SnapshotRequired(
            "Snapshot is older than the 10-minute freshness window."
        )
    if last_write_audited_at is not None and created <= _aware(last_write_audited_at):
        raise SnapshotRequired(
            "Snapshot is not newer than the last write audited for this connection."
        )
