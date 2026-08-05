"""Odoo Expert — grounded Q&A (EXP-3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.expert.ask import ask_expert, expert_assist_enabled
from app.llm_provider import LLMError
from app.schemas import ExpertAskBody, ExpertAskOut, ExpertCitationOut

router = APIRouter(prefix="/expert", tags=["expert"])


@router.post("/ask", response_model=ExpertAskOut)
def expert_ask(body: ExpertAskBody, db: Session = Depends(get_db)) -> ExpertAskOut:
    if not expert_assist_enabled():
        raise HTTPException(
            status_code=503,
            detail="Expert requires AI_ASSIST enabled (ollama or openai-compatible)",
        )
    try:
        client = None
        if body.connection_id:
            from app.odoo_service import client_from_connection, get_connection_or_404

            try:
                row = get_connection_or_404(db, body.connection_id)
                client = client_from_connection(row)
            except Exception:  # noqa: BLE001 — best-effort live grounding
                client = None
        result = ask_expert(
            db,
            question=body.question,
            connection_id=body.connection_id,
            ui_context=body.ui_context,
            conversation=[t.model_dump() for t in body.conversation],
            client=client,
        )
    except LLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return ExpertAskOut(
        answer_markdown=result.answer_markdown,
        citations=[
            ExpertCitationOut(
                source=c.source,
                version=c.version,
                breadcrumb=c.breadcrumb,
                chunk_id=c.chunk_id,
                source_index=c.source_index,
            )
            for c in result.citations
        ],
        grounded=result.grounded,
        declined=result.declined,
        suggested_tools=result.suggested_tools,
        caution_flags=result.caution_flags,
        retrieval_version=result.retrieval_version,
        model_used=result.model_used,
        reasoning=result.reasoning,
        uncited_warning=result.uncited_warning,
    )
