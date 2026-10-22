"""Intent → feature router HTTP surface (Expert + Batch OS aliases)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.intent_router import route_intent

router = APIRouter(tags=["intent-router"])


class IntentRouteBody(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(5, ge=1, le=10)
    progress_run_id: str | None = Field(default=None, max_length=128)


@router.post("/connections/{connection_id}/expert/route")
def expert_intent_route(connection_id: str, body: IntentRouteBody) -> dict[str, Any]:
    """Expert home: route a plain-language goal to the best-fitting feature."""
    from app.progress.emit import stage_emit

    run_id = body.progress_run_id or f"intent-{connection_id}"
    stage_emit(run_id, "expert_classify", detail=body.prompt[:160])
    out = route_intent(body.prompt, connection_id=connection_id, limit=body.limit)
    stage_emit(run_id, "expert_answer", detail="Route catalog")
    return out


@router.get("/connections/{connection_id}/expert/route/catalog")
def expert_route_catalog(connection_id: str) -> dict[str, Any]:
    """Debug/list merged catalog (static + Atlas + recipes)."""
    del connection_id
    from app.intent_router.loader import catalog_honesty, load_features

    features = [f.to_dict() for f in load_features()]
    return {"count": len(features), "honesty": catalog_honesty(), "features": features}


class BuildSpineBody(BaseModel):
    prompt: str = Field("", max_length=8000)
    understanding: dict[str, Any] | None = None
    contract: dict[str, Any] | None = None
    generation_ir: dict[str, Any] | None = None


@router.post("/connections/{connection_id}/build-spine/resolve")
def build_spine_resolve(connection_id: str, body: BuildSpineBody) -> dict[str, Any]:
    """P2 Build spine — mode chips + handoff IR (brief + Diagnosis/Contract + stamps)."""
    from app.ai_build_spine import build_spine_payload

    return build_spine_payload(
        prompt=body.prompt or "",
        connection_id=connection_id,
        understanding=body.understanding,
        contract=body.contract,
        generation_ir=body.generation_ir,
    )

