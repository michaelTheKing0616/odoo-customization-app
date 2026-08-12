"""LLM cited narratives for draft review findings (EXP2-2)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.expert.ask import (
    ExpertCitation,
    _enforce_citation_markers,
    _format_sources,
    expert_assist_enabled,
)
from app.expert.draft_review import DraftReviewFinding
from app.expert.retrieval import RetrievedChunk, retrieve_expert_chunks
from app.llm_provider import LLMError, get_llm_provider
from app.settings import settings

FINDING_NARRATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "narratives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "priority": {"type": "integer"},
                    "paragraph": {"type": "string"},
                    "citation_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["priority", "paragraph", "citation_ids"],
            },
        },
    },
    "required": ["narratives"],
}

_NARRATIVE_RULES = """
Write one short paragraph (2–4 sentences) per finding listed below.
Rules:
- Explain WHY the finding matters for Odoo Community customization quality.
- Use inline citation markers [1], [2], … matching SOURCE EXCERPT numbers exactly.
- Every paragraph MUST end with at least one [n] marker.
- Be specific to the finding detail; do not invent fixes not supported by sources.
- Plain tone; no bullet lists inside paragraphs.
""".strip()


@dataclass
class FindingNarrative:
    priority: int
    paragraph: str
    citations: list[ExpertCitation] = field(default_factory=list)


def _finding_query(finding: DraftReviewFinding, *, user_prompt: str = "") -> str:
    parts = [
        "Odoo draft scorecard",
        finding.summary,
        finding.detail,
        finding.element,
    ]
    if user_prompt:
        parts.append(user_prompt[:200])
    return " ".join(p for p in parts if p)


def _fallback_paragraph(finding: DraftReviewFinding) -> str:
    tag = "This is auto-fixable" if finding.deterministic else "Consider improving"
    cite = finding.citation or "GEN2-12 scorecard rubric"
    return (
        f"{tag}: {finding.detail} "
        f"(Scorecard: {finding.summary}; source: {cite}.)"
    )


def _citations_from_ids(
    citation_ids: list[int],
    index_map: dict[int, RetrievedChunk],
) -> list[ExpertCitation]:
    cited: list[ExpertCitation] = []
    seen: set[str] = set()
    for raw_id in citation_ids:
        try:
            idx = int(raw_id)
        except (TypeError, ValueError):
            continue
        chunk = index_map.get(idx)
        if chunk and chunk.chunk_id not in seen:
            seen.add(chunk.chunk_id)
            cited.append(
                ExpertCitation(
                    source=chunk.source,
                    version=chunk.version,
                    breadcrumb=chunk.breadcrumb,
                    chunk_id=chunk.chunk_id,
                    source_index=idx,
                )
            )
    return cited


def generate_finding_narratives(
    db: Session | None,
    findings: list[DraftReviewFinding],
    *,
    user_prompt: str = "",
    version: str | None = None,
    top_n: int = 5,
) -> list[FindingNarrative]:
    """Generate one cited paragraph per top finding; template fallback when LLM unavailable."""
    ranked = sorted(findings, key=lambda f: f.priority)[:top_n]
    if not ranked:
        return []

    if db is None or not expert_assist_enabled():
        return [
            FindingNarrative(priority=f.priority, paragraph=_fallback_paragraph(f))
            for f in ranked
        ]

    all_chunks: list[RetrievedChunk] = []
    seen_chunk_ids: set[str] = set()
    for finding in ranked:
        query = _finding_query(finding, user_prompt=user_prompt)
        for chunk in retrieve_expert_chunks(
            db,
            query,
            version=version,
            top_k=3,
            min_score=float(settings.ai_rag_min_score or 0.35),
        ):
            if chunk.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.chunk_id)
                all_chunks.append(chunk)

    if not all_chunks:
        return [
            FindingNarrative(priority=f.priority, paragraph=_fallback_paragraph(f))
            for f in ranked
        ]

    llm = get_llm_provider()
    if llm is None:
        return [
            FindingNarrative(priority=f.priority, paragraph=_fallback_paragraph(f))
            for f in ranked
        ]

    sources_text, index_map = _format_sources(all_chunks[:12])
    finding_lines = "\n".join(
        f"{f.priority}. [{f.summary}] {f.detail}" for f in ranked
    )
    prompt = (
        f"USER PROMPT CONTEXT:\n{user_prompt[:400] or '(none)'}\n\n"
        f"FINDINGS:\n{finding_lines}\n\n"
        f"SOURCE EXCERPTS:\n{sources_text}\n\n"
        f"{_NARRATIVE_RULES}\n\n"
        "Return JSON with narratives array — one entry per finding priority."
    )

    try:
        raw = llm.generate_json(
            prompt,
            system="You are the Odoo Expert draft reviewer. Cite sources strictly.",
            reasoning=False,
            temperature=0.1,
            format_schema=FINDING_NARRATIVE_SCHEMA,
            timeout_s=settings.expert_llm_timeout_s,
        )
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError, LLMError, ValueError):
        return [
            FindingNarrative(priority=f.priority, paragraph=_fallback_paragraph(f))
            for f in ranked
        ]

    by_priority: dict[int, FindingNarrative] = {}
    narratives = data.get("narratives") or []
    if isinstance(narratives, list):
        for row in narratives:
            if not isinstance(row, dict):
                continue
            try:
                priority = int(row.get("priority"))
            except (TypeError, ValueError):
                continue
            paragraph = str(row.get("paragraph") or "").strip()
            if not paragraph:
                continue
            raw_ids = row.get("citation_ids") or []
            ids: list[int] = []
            if isinstance(raw_ids, list):
                for raw_id in raw_ids:
                    try:
                        ids.append(int(raw_id))
                    except (TypeError, ValueError):
                        continue
            paragraph, enforced_ids = _enforce_citation_markers(
                paragraph,
                index_map=index_map,
                citation_ids=ids,
            )
            by_priority[priority] = FindingNarrative(
                priority=priority,
                paragraph=paragraph,
                citations=_citations_from_ids(enforced_ids or ids, index_map),
            )

    out: list[FindingNarrative] = []
    for finding in ranked:
        narrative = by_priority.get(finding.priority)
        if narrative:
            out.append(narrative)
        else:
            out.append(
                FindingNarrative(
                    priority=finding.priority,
                    paragraph=_fallback_paragraph(finding),
                )
            )
    return out


__all__ = ["FindingNarrative", "generate_finding_narratives"]
