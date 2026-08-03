"""Odoo Expert RAG — knowledge ingestion and retrieval."""

from __future__ import annotations

from typing import Any

__all__ = [
    "chunk_document",
    "chunk_file",
    "fetch_documentation",
    "retrieve_expert_chunks",
    "run_ingest",
    "upsert_chunks",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "chunk_document": ("app.expert.chunker", "chunk_document"),
    "chunk_file": ("app.expert.chunker", "chunk_file"),
    "fetch_documentation": ("app.expert.fetcher", "fetch_documentation"),
    "retrieve_expert_chunks": ("app.expert.retrieval", "retrieve_expert_chunks"),
    "run_ingest": ("app.expert.ingest", "run_ingest"),
    "upsert_chunks": ("app.expert.store", "upsert_chunks"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr = _LAZY_EXPORTS[name]
    import importlib

    module = importlib.import_module(module_path)
    value = getattr(module, attr)
    globals()[name] = value
    return value
