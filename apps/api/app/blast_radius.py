"""TRUST-3 — blast-radius limits (sample-first, caps, batch pacing)."""

from __future__ import annotations

from typing import Literal

from app.safety_gate import RiskClass
from app.settings import settings

RunStatus = Literal["completed", "sample_paused", "aborted", "in_progress"]


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
