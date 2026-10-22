"""Best-effort stage emits for long HTTP/RQ paths."""

from __future__ import annotations

from app.progress.store import get_stage_bus


def stage_emit(run_id: str | None, stage: str, *, detail: str = "") -> None:
    if not run_id:
        return
    get_stage_bus().emit(run_id, stage, detail=detail)
