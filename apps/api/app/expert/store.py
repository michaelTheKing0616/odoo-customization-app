"""Postgres store for Expert RAG chunks with content-hash upsert."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_rag import embed_texts
from app.db_models import ExpertChunk
from app.expert.chunker import DocChunk

logger = logging.getLogger(__name__)


@dataclass
class UpsertStats:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


def content_hash(source: str, version: str, breadcrumb: str, text: str) -> str:
    payload = f"{source}\0{version}\0{breadcrumb}\0{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _embed_chunk(text: str) -> list[float] | None:
    encoded = embed_texts([text])
    if encoded and encoded[0]:
        return encoded[0]
    return None


def upsert_chunks(
    db: Session,
    *,
    source: str,
    version: str,
    chunks: list[DocChunk],
    embed: bool = True,
) -> UpsertStats:
    """Insert or update chunks keyed by ``content_hash``."""
    stats = UpsertStats()
    if not chunks:
        return stats

    texts = [c.text for c in chunks]
    vectors: list[list[float] | None]
    if embed:
        batch = embed_texts(texts)
        if batch is None:
            vectors = [_embed_chunk(t) for t in texts]
        else:
            vectors = batch
    else:
        vectors = [None] * len(chunks)

    for chunk, vector in zip(chunks, vectors, strict=True):
        digest = content_hash(source, version, chunk.breadcrumb, chunk.text)
        existing = db.scalar(select(ExpertChunk).where(ExpertChunk.content_hash == digest))
        embedding_json = json.dumps(vector) if vector else None

        if existing is None:
            db.add(
                ExpertChunk(
                    source=source,
                    version=version,
                    breadcrumb=chunk.breadcrumb,
                    text=chunk.text,
                    content_hash=digest,
                    embedding_json=embedding_json,
                )
            )
            stats.inserted += 1
            continue

        needs_embedding = embed and not existing.embedding_json and embedding_json
        changed = (
            existing.text != chunk.text
            or existing.breadcrumb != chunk.breadcrumb
            or existing.embedding_json != embedding_json
        )
        if not changed and not needs_embedding:
            stats.skipped += 1
            continue

        existing.breadcrumb = chunk.breadcrumb
        existing.text = chunk.text
        if embedding_json or needs_embedding:
            existing.embedding_json = embedding_json
        stats.updated += 1

    db.commit()
    return stats


def count_chunks(db: Session, *, source: str | None = None, version: str | None = None) -> int:
    stmt = select(ExpertChunk)
    rows = db.scalars(stmt).all()
    total = 0
    for row in rows:
        if source is not None and row.source != source:
            continue
        if version is not None and row.version != version and row.version != "all":
            continue
        total += 1
    return total
