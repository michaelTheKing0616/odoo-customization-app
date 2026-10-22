"""Dashboard Studio progress stub — full product surface is T4-DASH."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.progress.emit import stage_emit

router = APIRouter(prefix="/dashboard-studio", tags=["dashboard-studio"])


class DashboardPreviewBody(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    progress_run_id: str | None = Field(default=None, max_length=128)


class DashboardPreviewOut(BaseModel):
    run_id: str
    status: str
    message: str


@router.post("/preview", response_model=DashboardPreviewOut)
def dashboard_preview(body: DashboardPreviewBody) -> DashboardPreviewOut:
    run_id = (body.progress_run_id or "").strip() or str(uuid.uuid4())
    stage_emit(run_id, "dash_plan", detail=body.prompt[:160])
    stage_emit(run_id, "dash_query", detail="read-only aggregate (stub)")
    stage_emit(run_id, "dash_render", detail="interactive shell (stub)")
    stage_emit(run_id, "dash_save", detail="persistence ships with T4-DASH")
    return DashboardPreviewOut(
        run_id=run_id,
        status="stub",
        message="Dashboard Studio persistence and charts ship in T4-DASH; progress stages are wired.",
    )
