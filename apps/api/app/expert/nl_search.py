"""Natural-language navigation + Expert query routing inside the app."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NLSearchHit:
    id: str
    kind: str  # navigate | expert | model
    label: str
    description: str = ""
    href: str | None = None
    expert_question: str | None = None
    score: float = 0.0


@dataclass
class NLSearchResult:
    query: str
    hits: list[NLSearchHit] = field(default_factory=list)


_ROUTE_PATTERNS: list[tuple[re.Pattern[str], str, str, str]] = [
    (re.compile(r"\b(wizard|draft|ai|generate|nl)\b", re.I), "wizard", "AI Wizard", "Create or enrich drafts with natural language"),
    (re.compile(r"\b(builder|designer|model|field|view)\b", re.I), "builder", "Designer", "Edit models, fields, and views"),
    (re.compile(r"\b(bulk|mass|batch)\b", re.I), "bulk", "Bulk tools", "Mass edit, export, and batch operations"),
    (re.compile(r"\b(automation|trigger|server action)\b", re.I), "automations", "Automations", "base.automation and server actions"),
    (re.compile(r"\b(import|csv|ingest|data)\b", re.I), "ingest", "Data import", "CSV ingest and field mapping"),
    (re.compile(r"\b(deploy|install|module|promote)\b", re.I), "deploy", "Deploy", "Sandbox test and module install"),
    (re.compile(r"\b(validate|readiness|go.?live)\b", re.I), "validate", "Validate", "Live validation and readiness"),
    (re.compile(r"\b(expert|ask|help|how)\b", re.I), "expert", "Odoo Expert", "Grounded Q&A with citations"),
]


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 2}


def _score_overlap(query_tokens: set[str], *corpora: str) -> float:
    if not query_tokens:
        return 0.0
    best = 0.0
    for corpus in corpora:
        ct = _tokenize(corpus)
        if not ct:
            continue
        overlap = len(query_tokens & ct) / len(query_tokens)
        best = max(best, overlap)
    return best


def nl_search(
    query: str,
    *,
    connection_id: str,
    models: list[dict[str, Any]] | None = None,
) -> NLSearchResult:
    """Resolve NL query to in-app navigation and Expert questions."""
    q = (query or "").strip()
    if not q:
        return NLSearchResult(query=q)

    hits: list[NLSearchHit] = []
    q_lower = q.lower()
    tokens = _tokenize(q)

    for pattern, slug, label, desc in _ROUTE_PATTERNS:
        if pattern.search(q_lower):
            href = f"/connections/{connection_id}/{slug}" if slug != "expert" else None
            hits.append(
                NLSearchHit(
                    id=f"nav-{slug}",
                    kind="navigate" if slug != "expert" else "expert",
                    label=label,
                    description=desc,
                    href=href,
                    expert_question=q if slug == "expert" else None,
                    score=0.85,
                )
            )

    for row in models or []:
        model = str(row.get("model") or "")
        name = str(row.get("name") or model)
        if not model:
            continue
        score = _score_overlap(tokens, model, name)
        if model.lower() in q_lower or score >= 0.4:
            hits.append(
                NLSearchHit(
                    id=f"model-{model}",
                    kind="model",
                    label=f"Open {model}",
                    description=name,
                    href=f"/connections/{connection_id}/builder?model={model}",
                    expert_question=f"Explain model `{model}` on this connection.",
                    score=max(score, 0.7 if model.lower() in q_lower else score),
                )
            )

    # Expert catch-all when question-shaped
    if "?" in q or re.search(r"\b(how|why|what|when|can i)\b", q_lower):
        hits.append(
            NLSearchHit(
                id="expert-ask",
                kind="expert",
                label="Ask Odoo Expert",
                description=q[:120],
                expert_question=q,
                score=0.75,
            )
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    deduped: list[NLSearchHit] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.id in seen:
            continue
        seen.add(hit.id)
        deduped.append(hit)
        if len(deduped) >= 10:
            break

    return NLSearchResult(query=q, hits=deduped)


__all__ = ["NLSearchHit", "NLSearchResult", "nl_search"]
