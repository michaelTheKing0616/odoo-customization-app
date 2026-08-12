"""Preload sentence-transformers on API boot so first Expert ask is fast."""

from __future__ import annotations

import logging

from app.ai_rag import embed_texts, rag_enabled

logger = logging.getLogger(__name__)


def warm_expert_rag_model() -> dict[str, str | bool]:
    """Load the embedding model once at startup when RAG is enabled."""
    if not rag_enabled():
        return {"skipped": True, "reason": "ai_rag disabled"}

    try:
        vectors = embed_texts(["expert rag warmup"])
        if vectors and vectors[0]:
            logger.info("Expert RAG embedding model warmed (%s dims)", len(vectors[0]))
            return {"skipped": False, "ready": True, "dims": str(len(vectors[0]))}
        logger.warning("Expert RAG warmup: embed_texts returned no vectors")
        return {"skipped": False, "ready": False, "reason": "no_vectors"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Expert RAG warmup failed: %s", exc)
        return {"skipped": False, "ready": False, "reason": str(exc)[:120]}


__all__ = ["warm_expert_rag_model"]
