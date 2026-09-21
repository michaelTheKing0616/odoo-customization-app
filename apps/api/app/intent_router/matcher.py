"""Deterministic keyword scoring for Intent → feature routing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.intent_router.loader import (
    FeatureEntry,
    UnsupportedPattern,
    catalog_honesty,
    deep_link,
    load_features,
    unsupported_patterns,
)

CanHandle = Literal["true", "false", "partial"]

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")
# Too generic alone — must ride with a stronger phrase/token.
_STOP_KEYWORDS = frozenset({
    "create", "upload", "bulk", "pack", "data", "setup", "use", "open",
    "many", "all", "the", "and", "for", "with", "from", "into", "via",
    "batch", "entries", "entry", "app", "new", "set", "run", "get",
})
_HIGH = 1.8
_MED = 0.75
_AMB_GAP = 0.55  # within this of top → ranked alternatives


@dataclass
class MatchHit:
    feature_id: str
    title: str
    confidence: float
    why: str
    route: str
    deep_link: str
    can_handle: CanHandle
    recipe: str | None = None
    source: str = "catalog"
    status: str = "complete"
    atlas_class: str | None = None
    risk: str | None = None
    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "title": self.title,
            "confidence": round(self.confidence, 3),
            "why": self.why,
            "route": self.route,
            "deep_link": self.deep_link,
            "can_handle": self.can_handle,
            "recipe": self.recipe,
            "source": self.source,
            "status": self.status,
            "atlas_class": self.atlas_class,
            "risk": self.risk,
            "matched_keywords": list(self.matched_keywords),
        }


def _normalize(prompt: str) -> str:
    return re.sub(r"\s+", " ", (prompt or "").strip().lower())


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text))


def _score_entry(prompt: str, tokens: set[str], entry: FeatureEntry) -> tuple[float, list[str]]:
    score = 0.0
    matched: list[str] = []
    for kw in entry.keywords:
        kw_l = kw.lower().strip()
        if not kw_l:
            continue
        if " " in kw_l or "." in kw_l:
            if kw_l in prompt:
                # Multi-word / technical model — strong signal
                score += 1.35 * entry.weight
                matched.append(kw_l)
            else:
                # Partial token overlap for multi-word
                parts = [p for p in _WORD_RE.findall(kw_l) if len(p) > 2]
                if parts and all(p in tokens or p in prompt for p in parts):
                    score += 0.55 * entry.weight
                    matched.append(kw_l)
        else:
            if kw_l in _STOP_KEYWORDS:
                continue
            if kw_l in tokens or re.search(rf"\b{re.escape(kw_l)}\b", prompt):
                score += 1.0 * entry.weight
                matched.append(kw_l)
    # Title phrase boost
    title_l = entry.title.lower()
    if title_l and title_l in prompt:
        score += 1.0 * entry.weight
        matched.append(title_l)
    return score, matched


def _entry_can_handle(entry: FeatureEntry, score: float) -> CanHandle:
    if entry.status in {"stub", "planned"} or not entry.can_handle:
        return "partial"
    if score >= _HIGH:
        return "true"
    if score >= _MED:
        return "partial"
    return "partial"


def _why(entry: FeatureEntry, matched: list[str], can: CanHandle) -> str:
    bits = matched[:4]
    base = (
        f"Matched {entry.title} via {', '.join(repr(b) for b in bits)}."
        if bits
        else f"Matched {entry.title}."
    )
    if entry.recipe:
        base += f" Recipe `{entry.recipe}`."
    if can == "partial" and entry.status != "complete":
        base += f" Status is {entry.status} — not a full path yet."
    elif can == "partial":
        base += " Closest fit; confirm this is what you meant."
    if "preview" in (entry.blurb or "").lower() or "≠" in (entry.blurb or ""):
        base += " Preview ≠ posted/written."
    return base


def match_unsupported(prompt: str) -> UnsupportedPattern | None:
    p = _normalize(prompt)
    for pat in unsupported_patterns():
        if any(kw in p for kw in pat.keywords):
            return pat
    return None


def score_features(
    prompt: str,
    *,
    connection_id: str,
    limit: int = 5,
) -> list[MatchHit]:
    p = _normalize(prompt)
    if not p:
        return []
    tokens = _tokens(p)
    scored: list[tuple[float, FeatureEntry, list[str]]] = []
    for entry in load_features():
        score, matched = _score_entry(p, tokens, entry)
        if score < _MED:
            continue
        scored.append((score, entry, matched))
    scored.sort(key=lambda t: (-t[0], t[1].id))

    # Collapse near-duplicates that share the same deep link / recipe —
    # prefer static catalog ids over atlas.*/recipe.* mirrors.
    hits: list[MatchHit] = []
    seen_routes: set[str] = set()
    seen_recipes: set[str] = set()
    for score, entry, matched in scored:
        route_key = entry.route
        if route_key in seen_routes and entry.source in {"atlas", "recipe"}:
            # Keep if recipe is distinct and high-scoring
            if entry.recipe and entry.recipe not in seen_recipes and score >= _HIGH:
                pass
            else:
                continue
        if entry.recipe and entry.recipe in seen_recipes and entry.source in {"atlas", "recipe"}:
            continue
        can = _entry_can_handle(entry, score)
        # Confidence 0–1 from score
        conf = min(0.99, score / 5.0)
        hits.append(
            MatchHit(
                feature_id=entry.id,
                title=entry.title,
                confidence=conf,
                why=_why(entry, matched, can),
                route=entry.route,
                deep_link=deep_link(connection_id, entry.route),
                can_handle=can,
                recipe=entry.recipe,
                source=entry.source,
                status=entry.status,
                atlas_class=entry.atlas_class,
                risk=entry.risk,
                matched_keywords=matched[:8],
            )
        )
        seen_routes.add(route_key)
        if entry.recipe:
            seen_recipes.add(entry.recipe)
        if len(hits) >= limit:
            break
    return hits


def build_route_result(
    prompt: str,
    *,
    connection_id: str,
    limit: int = 5,
) -> dict[str, Any]:
    """Pure deterministic route payload (no LLM)."""
    honesty = catalog_honesty()
    unsupported = match_unsupported(prompt)
    if unsupported:
        return {
            "prompt": prompt,
            "can_handle": "false",
            "message": unsupported.message,
            "matches": [],
            "alternatives": [],
            "ambiguous": False,
            "honesty": honesty,
            "source": "unsupported_catalog",
            "llm_used": False,
        }

    hits = score_features(prompt, connection_id=connection_id, limit=limit)
    if hits and len(hits) > 1:
        top_conf = hits[0].confidence
        hits = [hits[0]] + [h for h in hits[1:] if (top_conf - h.confidence) < 0.35 and h.confidence >= 0.28]
    if not hits:
        return {
            "prompt": prompt,
            "can_handle": "false",
            "message": (
                "ingenium does not have a shipped feature that clearly matches that goal. "
                "Try Journal batch, Master data, Config Atlas, App Studio, Bulk Suite, or "
                "describe the Odoo model/workflow you need."
            ),
            "matches": [],
            "alternatives": [],
            "ambiguous": False,
            "honesty": honesty,
            "source": "deterministic",
            "llm_used": False,
        }

    top = hits[0]
    alts = hits[1:]
    ambiguous = bool(alts) and (top.confidence - alts[0].confidence) < 0.18

    # Overall can_handle from top hit; partial if ambiguous among strong options
    overall: CanHandle = top.can_handle
    if top.can_handle == "true" and ambiguous:
        overall = "partial"

    if overall == "true":
        message = f"Best fit: {top.title}. {top.why}"
    elif overall == "partial":
        if ambiguous:
            message = (
                f"Several features could fit (top: {top.title}). "
                "Pick the closest below — ingenium will not guess past shipped routes."
            )
        elif top.status != "complete":
            message = (
                f"Closest feature is {top.title}, but it is {top.status} — "
                "not a complete path yet."
            )
        else:
            message = f"Partial match: {top.title}. {top.why}"
    else:
        message = top.why

    return {
        "prompt": prompt,
        "can_handle": overall,
        "message": message,
        "matches": [top.to_dict()],
        "alternatives": [h.to_dict() for h in alts],
        "ambiguous": ambiguous,
        "honesty": honesty,
        "source": "deterministic",
        "llm_used": False,
    }
