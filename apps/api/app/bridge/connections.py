"""Bridge connection verification and Tier I gate."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def verify_connection(row: Any, *, probe_ok: bool) -> Any:
    """Update connection status from a probe result."""
    if probe_ok:
        row.status = "verified"
        row.verified_at = datetime.now(UTC)
    else:
        row.status = "failed"
        row.verified_at = None
    return row


def connection_may_leave_tier_i(row: Any) -> bool:
    """A contract cannot pass Tier I usage until the connection is verified."""
    return getattr(row, "status", None) == "verified"
