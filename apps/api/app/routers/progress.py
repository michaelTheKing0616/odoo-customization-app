"""Poll stage events emitted during long runs (T4-PROG)."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.progress.store import get_stage_bus

router = APIRouter(prefix="/progress", tags=["progress"])


class StageEventOut(BaseModel):
    run_id: str
    stage: str
    detail: str = ""


class StageEventsOut(BaseModel):
    run_id: str
    events: list[StageEventOut]
    total: int


@router.get("/runs/{run_id}/events", response_model=StageEventsOut)
def list_stage_events(run_id: str, after: int = Query(0, ge=0)) -> StageEventsOut:
    bus = get_stage_bus()
    matched = [e for e in bus.events if e.get("run_id") == run_id]
    slice_ = matched[after:]
    return StageEventsOut(
        run_id=run_id,
        events=[StageEventOut(**e) for e in slice_],
        total=len(matched),
    )
