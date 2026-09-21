"""Public Intent → feature router service."""

from __future__ import annotations

from typing import Any

from app.intent_router.llm_enrich import enrich_route_result, intent_llm_enabled
from app.intent_router.matcher import build_route_result


def route_intent(
    prompt: str,
    *,
    connection_id: str,
    limit: int = 5,
    allow_llm: bool | None = None,
) -> dict[str, Any]:
    """Route a plain-language goal to shipped ingenium features.

    Deterministic catalog matching always runs. Optional LLM enrich only when
    ``AI_INTENT_LLM`` is enabled (or ``allow_llm=True``) and must not be
    required for tests.
    """
    result = build_route_result(prompt, connection_id=connection_id, limit=limit)
    use_llm = intent_llm_enabled() if allow_llm is None else bool(allow_llm)
    if use_llm:
        result = enrich_route_result(prompt, result, connection_id=connection_id)
    return result
