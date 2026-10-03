"""TRUST-3 — blast-radius limits (sample-first, caps, batch pacing)."""

from __future__ import annotations

from typing import Any, Literal

from app.safety_gate import RiskClass
from app.settings import settings

RunStatus = Literal["completed", "sample_paused", "aborted", "in_progress"]

# Non-L4 production apply cap (blueprint §5.6). Do not lower bulk_cap_* settings.
PRODUCTION_APPLY_RECORD_CAP = 200


class BlastRadiusExceeded(Exception):
    """A production apply asked for more records than the non-L4 cap."""


def changeset_record_count(changeset: list[dict[str, Any]]) -> int:
    """Count records an apply would touch. Listed ids win; otherwise one per op."""
    total = 0
    for op in changeset:
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        counted = False
        for key in ("ids", "record_ids"):
            value = params.get(key)
            if isinstance(value, list) and value:
                total += len(value)
                counted = True
                break
        if not counted:
            total += 1
    return total


def assert_production_apply_records(
    record_count: int,
    *,
    environment: str = "",
    write_mode: str = "",
) -> None:
    """Refuse a production apply above 200 records. Local/test/staging stay open.

    L4's 50-record cap lives on `L4_MAX_BLAST` and stays inactive.
    """
    env = str(environment or "").strip().lower()
    mode = str(write_mode or "").strip().lower()
    if env != "production" and mode != "production":
        return
    count = int(record_count)
    if count > PRODUCTION_APPLY_RECORD_CAP:
        raise BlastRadiusExceeded(
            f"production apply of {count} records exceeds {PRODUCTION_APPLY_RECORD_CAP}"
        )


def risk_record_cap(risk: RiskClass) -> int:
    if risk == "destructive":
        return max(1, settings.bulk_cap_destructive)
    return max(1, settings.bulk_cap_reversible)


def clamp_request_cap(requested: int, risk: RiskClass) -> int:
    """Apply per-risk hard cap (still bounded by API max 5000)."""
    return max(1, min(int(requested or risk_record_cap(risk)), risk_record_cap(risk), 5000))


def plan_execution_ids(
    record_ids: list[int],
    *,
    continue_after_sample: bool = False,
    sample_disabled: bool = False,
) -> tuple[list[int], list[int], bool]:
    """Return (execute_now, pending_after, sample_paused)."""
    if sample_disabled or continue_after_sample:
        return list(record_ids), [], False
    if not settings.bulk_sample_first_enabled:
        return list(record_ids), [], False
    threshold = max(1, settings.bulk_sample_first_threshold)
    sample_size = max(1, settings.bulk_sample_size)
    if len(record_ids) <= threshold:
        return list(record_ids), [], False
    execute = list(record_ids[:sample_size])
    pending = list(record_ids[sample_size:])
    return execute, pending, True
