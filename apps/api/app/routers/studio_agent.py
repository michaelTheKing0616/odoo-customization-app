"""Agent mode: playback answers / assumption edits -> re-design in the same agent conversation.

The new design is stored server-side on the session (the client never supplies a design), and the
existing Build path then authorizes it like any other app design (AI proposes, code authorizes)."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_models import AiSession

router = APIRouter(tags=["studio-agent"])


class RedesignBody(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict, max_length=6)
    assumptions: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


@router.post("/ai/sessions/{session_id}/agent-redesign")
def agent_redesign(session_id: str, body: RedesignBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.ai_conversation import studio_agent as sa
    from app.ai_conversation.understand import dump_understanding, load_understanding

    row = db.get(AiSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    answers = json.loads(row.resolved_answers_json or "{}")
    und = load_understanding(answers)
    design = (und.app_design if und is not None else None) or {}
    conv_key = str(((design.get("playback") or {}).get("conv_key")) or "")
    if not conv_key:
        raise HTTPException(status_code=409, detail="This design was not made in agent mode, so it can't be re-designed here.")
    snap = None
    if row.connection_id:
        from app.odoo_service import get_connection_or_404
        from app.odoo_snapshot import snapshot_for_connection

        try:
            snap = snapshot_for_connection(get_connection_or_404(db, row.connection_id), row.prompt_original or "")
        except LookupError:
            snap = None
    clean_answers = {str(k)[:12]: str(v)[:200] for k, v in body.answers.items()}
    clean_asm = [{"id": str(a.get("id") or a.get("requirement_id") or "")[:24], "text": str(a.get("text") or "")[:200],
                  "chosen": str(a.get("chosen") or "")[:200]} for a in body.assumptions if isinstance(a, dict)]
    new, out = sa.redesign(conv_key, answers=clean_answers, assumptions=clean_asm, snapshot=snap)
    if new is None:
        raise HTTPException(status_code=422 if out.get("reason") == "no_edits" else 502,
                            detail={"reason": out.get("reason") or "redesign failed"})
    new.app_name = new.app_name or design.get("app_name") or ""
    new.model_budget = int(design.get("model_budget") or new.model_budget)
    stored = new.to_dict()
    und.app_design = stored
    dump_understanding(answers, und)
    row.resolved_answers_json = json.dumps(answers)
    db.commit()
    return {"design": stored, "outcome": {k: v for k, v in out.items() if k != "tools"}}
