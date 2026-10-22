"""Compiler RAG reads the existing index in ``app.ai_rag``.

Do not add a second corpus, cache directory, or embedding store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app import ai_rag
from app.ai_rag import _cache_dir, retrieve_with_rag

retrieve = retrieve_with_rag


def index_root() -> Path:
    """Return the existing ``.cache/ai_rag`` directory from ``ai_rag``."""
    return _cache_dir()


def retrieve_from_existing_index(
    prompt: str,
    *,
    pack_loader: Callable[[], list[tuple[str, dict[str, Any]]]],
    jaccard_retrieve: Callable[[str], tuple[str, dict[str, Any], float] | None],
    min_cosine: float | None = None,
) -> tuple[str, dict[str, Any], float, str]:
    """Score packs through ``ai_rag.retrieve_with_rag``. No second store."""
    return ai_rag.retrieve_with_rag(
        prompt,
        pack_loader=pack_loader,
        jaccard_retrieve=jaccard_retrieve,
        min_cosine=min_cosine,
    )


__all__ = [
    "index_root",
    "retrieve",
    "retrieve_from_existing_index",
]
