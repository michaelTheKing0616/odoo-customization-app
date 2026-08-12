"""Version-filtered Expert chunk retrieval with source weighting."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai_rag import cosine_similarity, embed_texts, rag_enabled
from app.db_models import ExpertChunk
from app.expert.vertical_catalog import expand_expert_query
from app.settings import settings

PROJECT_SOURCE_BOOST = 1.25
VERTICAL_SOURCE_BOOST = 1.45
COMMUNITY_SOURCE_BOOST = 1.35
ODOO_SOURCE_BOOST = 1.30
_DEFAULT_MIN_SCORE = 0.35
_DEFAULT_JACCARD_MIN_SCORE = 0.12


@dataclass
class RetrievedChunk:
    chunk_id: str
    source: str
    version: str
    breadcrumb: str
    text: str
    score: float
    method: str


def _token_set(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 2}


def _jaccard(a: str, b: str) -> float:
    sa, sb = _token_set(a), _token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _parse_embedding(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, list) and data:
            return [float(x) for x in data]
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def _source_weight(source: str) -> float:
    if source == "vertical":
        return VERTICAL_SOURCE_BOOST
    if source == "community":
        return COMMUNITY_SOURCE_BOOST
    if source == "odoo_source":
        return ODOO_SOURCE_BOOST
    if source == "project":
        return PROJECT_SOURCE_BOOST
    return 1.0


def _embedding_threshold(min_score: float | None) -> float:
    if min_score is not None:
        return min_score
    return float(settings.ai_rag_min_score or _DEFAULT_MIN_SCORE)


def _jaccard_threshold() -> float:
    return float(settings.ai_rag_min_score_jaccard or _DEFAULT_JACCARD_MIN_SCORE)


def passes_generation_threshold(
    chunks: list[RetrievedChunk],
    *,
    min_score: float | None = None,
) -> bool:
    """True when the best retrieved chunk clears the bar for its scoring method."""
    if not chunks:
        return False
    best = max(chunks, key=lambda c: c.score)
    if best.method == "embedding":
        return best.score >= _embedding_threshold(min_score)
    return best.score >= _jaccard_threshold()


def retrieve_expert_chunks(
    db: Session,
    query: str,
    *,
    version: str | None = None,
    top_k: int = 8,
    min_score: float | None = None,
) -> list[RetrievedChunk]:
    """Return top-k chunks filtered by version with project-source boost."""
    embed_threshold = _embedding_threshold(min_score)
    jaccard_threshold = _jaccard_threshold()
    q = query.strip()
    if not q:
        return []

    retrieval_query = expand_expert_query(q)

    stmt = select(ExpertChunk)
    if version:
        stmt = stmt.where(or_(ExpertChunk.version == version, ExpertChunk.version == "all"))
    rows = list(db.scalars(stmt).all())
    if not rows:
        return []

    query_vec: list[float] | None = None
    if rag_enabled():
        encoded = embed_texts([retrieval_query])
        if encoded and encoded[0]:
            query_vec = encoded[0]

    scored: list[RetrievedChunk] = []
    for row in rows:
        weight = _source_weight(row.source)
        embedding = _parse_embedding(row.embedding_json)
        if query_vec and embedding:
            score = cosine_similarity(query_vec, embedding) * weight
            method = "embedding"
            threshold = embed_threshold
        else:
            score = _jaccard(retrieval_query, f"{row.breadcrumb} {row.text}") * weight
            method = "jaccard"
            threshold = jaccard_threshold

        if score >= threshold:
            scored.append(
                RetrievedChunk(
                    chunk_id=row.id,
                    source=row.source,
                    version=row.version,
                    breadcrumb=row.breadcrumb,
                    text=row.text,
                    score=score,
                    method=method,
                )
            )

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]
