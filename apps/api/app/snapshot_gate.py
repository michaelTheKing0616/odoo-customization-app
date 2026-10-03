"""Production destructive/code applies require a connection-scoped snapshot."""

from __future__ import annotations


class SnapshotRequired(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def require_production_snapshot(
    *,
    write_mode: str,
    risk: str,
    snapshot_id: str | None,
    snapshot_exists: bool,
) -> None:
    """Raise SnapshotRequired if a production destructive/code apply has no snapshot.

    write_mode other than production returns immediately.
    risk not in {destructive, code} returns immediately.
    """
    if write_mode != "production":
        return
    if risk not in {"destructive", "code"}:
        return
    if not snapshot_id or not snapshot_exists:
        raise SnapshotRequired(
            "A snapshot recorded for this connection is required before a destructive production apply."
        )
