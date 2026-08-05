"""Persist AI-generated ModuleSpec drafts for recovery."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import AiDraftCache


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()[:32]


def save_draft_cache(
    db: Session,
    *,
    connection_id: str | None,
    prompt: str,
    draft: dict[str, Any],
    raw_response: str | None = None,
    domain_pack: str | None = None,
) -> AiDraftCache:
    ph = _prompt_hash(prompt)
    existing = (
        db.query(AiDraftCache)
        .filter(
            AiDraftCache.connection_id == connection_id,
            AiDraftCache.prompt_hash == ph,
        )
        .order_by(AiDraftCache.updated_at.desc())
        .first()
    )
    summary = str(draft.get("display_name") or draft.get("technical_name") or prompt[:80])
    payload = json.dumps(draft, ensure_ascii=False)
    if existing:
        existing.draft_json = payload
        existing.raw_response = raw_response
        existing.domain_pack = domain_pack
        existing.summary = summary[:200]
        existing.updated_at = datetime.now(timezone.utc)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    row = AiDraftCache(
        id=str(uuid.uuid4()),
        connection_id=connection_id,
        prompt_hash=ph,
        prompt_text=prompt.strip()[:4000],
        summary=summary[:200],
        draft_json=payload,
        raw_response=raw_response,
        domain_pack=domain_pack,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_draft_cache(
    db: Session,
    *,
    connection_id: str | None = None,
    limit: int = 20,
) -> list[AiDraftCache]:
    q = db.query(AiDraftCache).order_by(AiDraftCache.updated_at.desc())
    if connection_id:
        q = q.filter(AiDraftCache.connection_id == connection_id)
    return q.limit(limit).all()


def get_draft_cache(db: Session, cache_id: str) -> AiDraftCache | None:
    return db.get(AiDraftCache, cache_id)


def cache_to_dict(row: AiDraftCache) -> dict[str, Any]:
    draft: dict[str, Any] = {}
    try:
        parsed = json.loads(row.draft_json or "{}")
        if isinstance(parsed, dict):
            draft = parsed
    except json.JSONDecodeError:
        draft = {}
    return {
        "id": row.id,
        "connection_id": row.connection_id,
        "prompt": row.prompt_text,
        "summary": row.summary,
        "domain_pack": row.domain_pack,
        "draft": draft,
        "raw_response": row.raw_response,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


__all__ = [
    "cache_to_dict",
    "get_draft_cache",
    "list_draft_cache",
    "save_draft_cache",
]
