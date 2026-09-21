"""Optional LLM enrich for Intent → feature router.

Gated by AI_INTENT_LLM (same env as Studio intent). When off/missing, this
module is a no-op — tests must never require an LLM.
"""

from __future__ import annotations

import os
from typing import Any


def intent_llm_enabled() -> bool:
    raw = (os.environ.get("AI_INTENT_LLM") or "off").strip().lower()
    return raw not in {"", "0", "false", "off", "no"}


def enrich_route_result(prompt: str, result: dict[str, Any], *, connection_id: str) -> dict[str, Any]:
    """Best-effort LLM re-rank when deterministic is weak.

    Never invents features absent from the catalog. On any failure, returns
    ``result`` unchanged. Unit tests keep AI_INTENT_LLM=off.
    """
    if not intent_llm_enabled():
        return result
    if result.get("can_handle") == "true" and not result.get("ambiguous"):
        return result

    try:
        from app.intent_router.loader import deep_link, load_features
    except Exception:  # noqa: BLE001
        return result

    try:
        from app.llm_provider import complete_json  # type: ignore
    except Exception:  # noqa: BLE001
        out = dict(result)
        out["llm_used"] = False
        return out

    catalog = [
        {
            "id": f.id,
            "title": f.title,
            "blurb": f.blurb,
            "route": f.route,
            "status": f.status,
            "recipe": f.recipe,
        }
        for f in load_features()
        if f.status == "complete"
    ][:40]
    try:
        payload = complete_json(
            system=(
                "You route user goals to ingenium features. "
                "Only pick ids from the provided catalog. Never invent features. "
                "Return JSON: {feature_id, confidence 0-1, why}."
            ),
            user=f"Goal: {prompt}\nCatalog: {catalog!r}",
        )
    except Exception:  # noqa: BLE001
        return result

    fid = str((payload or {}).get("feature_id") or "")
    if not fid:
        return result
    entry = next((f for f in load_features() if f.id == fid), None)
    if entry is None:
        return result

    conf = float((payload or {}).get("confidence") or 0.5)
    why = str((payload or {}).get("why") or f"LLM suggested {entry.title}.")
    can = "true" if entry.status == "complete" and conf >= 0.55 else "partial"
    hit = {
        "feature_id": entry.id,
        "title": entry.title,
        "confidence": round(min(0.99, conf), 3),
        "why": why + " Preview honesty preserved.",
        "route": entry.route,
        "deep_link": deep_link(connection_id, entry.route),
        "can_handle": can,
        "recipe": entry.recipe,
        "source": "llm+" + entry.source,
        "status": entry.status,
        "atlas_class": entry.atlas_class,
        "risk": entry.risk,
        "matched_keywords": [],
    }
    out = dict(result)
    out["matches"] = [hit]
    out["can_handle"] = can
    out["message"] = why
    out["llm_used"] = True
    out["source"] = "llm_enrich"
    out["ambiguous"] = False
    return out
