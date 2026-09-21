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


@router.post("/connections/{connection_id}/expert/route")
def expert_intent_route(connection_id: str, body: IntentRouteBody) -> dict[str, Any]:
    """Expert home: route a plain-language goal to the best-fitting feature."""
    return route_intent(body.prompt, connection_id=connection_id, limit=body.limit)


@router.get("/connections/{connection_id}/expert/route/catalog")
def expert_route_catalog(connection_id: str) -> dict[str, Any]:
    """Debug/list merged catalog (static + Atlas + recipes)."""
    del connection_id
    from app.intent_router.loader import catalog_honesty, load_features

    features = [f.to_dict() for f in load_features()]
    return {"count": len(features), "honesty": catalog_honesty(), "features": features}
