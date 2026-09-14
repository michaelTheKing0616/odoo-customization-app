"""Persisted AI conversation sessions — prompt, turns, artifact, metrics."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import AiSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_session(
    db: Session,
    *,
    connection_id: str | None,
    feature: str,
    prompt: str,
    status: str = "clarifying",
    resolved_answers: dict[str, str] | None = None,
    provider_used: str | None = None,
    fallback_used: bool = False,
) -> AiSession:
    answers = dict(resolved_answers or {})
    row = AiSession(
        id=str(uuid.uuid4()),
        connection_id=connection_id,
        feature=feature,
        prompt_original=prompt,
        prompt_resolved=prompt,
        conversation_json=json.dumps([]),
        artifact_json=json.dumps({}),
        status=status,
        resolved_answers_json=json.dumps(answers),
        provider_used=provider_used,
        fallback_used=fallback_used,
        metrics_json=json.dumps(
            {
                "clarify_count": 0,
                "refine_attempts": 0,
                "refine_landed": 0,
                "provider_fallbacks": 1 if fallback_used else 0,
            }
        ),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_session(db: Session, session_id: str) -> AiSession | None:
    return db.get(AiSession, session_id)


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def session_to_dict(row: AiSession) -> dict[str, Any]:
    conversation = _loads(row.conversation_json, [])
    artifact = _loads(row.artifact_json, {})
    resolved = _loads(row.resolved_answers_json, {})
    metrics = _loads(row.metrics_json, {})
    pending_clarification = _loads(row.pending_clarification_json, None)
    apply_meta = artifact.get("_studio_apply") if isinstance(artifact, dict) else None
    apply_meta = apply_meta if isinstance(apply_meta, dict) else {}
    understanding = None
    if isinstance(pending_clarification, dict) and pending_clarification.get("understanding"):
        understanding = pending_clarification.get("understanding")
    elif isinstance(resolved, dict):
        from app.ai_conversation.understand import load_understanding

        locked = load_understanding(resolved)
        if locked:
            understanding = locked.to_dict()
    return {
        "id": row.id,
        "connection_id": row.connection_id,
        "feature": row.feature,
        "status": row.status,
        "prompt_original": row.prompt_original,
        "prompt_resolved": row.prompt_resolved,
        "conversation": conversation if isinstance(conversation, list) else [],
        "artifact": artifact if isinstance(artifact, dict) else {},
        "resolved_answers": resolved if isinstance(resolved, dict) else {},
        "pending_clarification": pending_clarification,
        "job_id": row.job_id,
        "draft_cache_id": row.draft_cache_id,
        "provider_used": row.provider_used,
        "fallback_used": bool(row.fallback_used),
        "artifact_hash": row.artifact_hash,
        "metrics": metrics if isinstance(metrics, dict) else {},
        "root_menu_id": apply_meta.get("root_menu_id"),
        "open_action_id": apply_meta.get("open_action_id"),
        "host_model": apply_meta.get("host_model"),
        "understanding": understanding,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def append_turn(
    db: Session,
    row: AiSession,
    *,
    role: str,
    kind: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    turns = _loads(row.conversation_json, [])
    if not isinstance(turns, list):
        turns = []
    turns.append(
        {
            "role": role,
            "kind": kind,
            "content": content,
            "metadata": metadata or {},
            "at": _now().isoformat(),
        }
    )
    row.conversation_json = json.dumps(turns)
    db.add(row)
    db.commit()


def update_session(
    db: Session,
    row: AiSession,
    **fields: Any,
) -> AiSession:
    for key, val in fields.items():
        if key == "conversation" and isinstance(val, list):
            row.conversation_json = json.dumps(val)
        elif key == "artifact" and isinstance(val, dict):
            row.artifact_json = json.dumps(val, default=str)
        elif key == "resolved_answers" and isinstance(val, dict):
            row.resolved_answers_json = json.dumps(val)
        elif key == "metrics" and isinstance(val, dict):
            row.metrics_json = json.dumps(val)
        elif key == "pending_clarification":
            row.pending_clarification_json = json.dumps(val) if val else None
        elif hasattr(row, key):
            setattr(row, key, val)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


__all__ = [
    "append_turn",
    "create_session",
    "get_session",
    "session_to_dict",
    "update_session",
]
