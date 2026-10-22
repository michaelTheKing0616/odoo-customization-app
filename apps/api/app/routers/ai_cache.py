"""AI cost dashboard data: cache hit rate, money saved, guard flags."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.ai_client import ai_cache

router = APIRouter(prefix="/ai/cache", tags=["ai-cache"])


@router.get("/stats")
def ai_cache_stats() -> dict[str, Any]:
    return ai_cache.stats()


@router.post("/invalidate/{db}")
def ai_cache_invalidate(db: str) -> dict[str, Any]:
    return {"removed": ai_cache.invalidate_db(db)}


@router.post("/clear")
def ai_cache_clear() -> dict[str, Any]:
    ai_cache.clear_all()
    return {"ok": True}
