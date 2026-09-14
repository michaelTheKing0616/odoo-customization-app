"""Session instrumentation for premium-model decision (Phase 6)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.ai_conversation.session_store import get_session, update_session


def log_session_metrics(db: Session, session_id: str, **delta: int) -> dict[str, Any]:
    row = get_session(db, session_id)
    if row is None:
        return {}
    try:
        metrics = json.loads(row.metrics_json or "{}")
    except json.JSONDecodeError:
        metrics = {}
    if not isinstance(metrics, dict):
        metrics = {}
    for key, inc in delta.items():
        metrics[key] = int(metrics.get(key) or 0) + int(inc)
    update_session(db, row, metrics=metrics)
    return metrics


def session_metrics_summary(metrics: dict[str, Any] | None) -> str:
    m = metrics or {}
    return (
        f"clarify={m.get('clarify_count', 0)} "
        f"refine={m.get('refine_attempts', 0)}/{m.get('refine_landed', 0)} "
        f"fallbacks={m.get('provider_fallbacks', 0)}"
    )


__all__ = ["log_session_metrics", "session_metrics_summary"]
