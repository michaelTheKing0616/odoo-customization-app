"""Odoo Expert — grounded Q&A (EXP-3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.expert.ask import ask_expert, expert_assist_enabled
from app.llm_provider import LLMError
from app.schemas import ExpertAskBody, ExpertAskOut, ExpertCitationOut
from app.schemas import (
    ExpertDraftReviewBody,
    ExpertDraftReviewFindingOut,
    ExpertDraftReviewOut,
)

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


@router.post("/review-draft", response_model=ExpertDraftReviewOut)
def expert_review_draft(body: ExpertDraftReviewBody) -> ExpertDraftReviewOut:
    from app.expert.draft_review import review_draft

    overlap_notes: list[str] = []
    if body.connection_id:
        try:
            from app.db import SessionLocal
            from app.odoo_service import get_connection_or_404

            db = SessionLocal()
            try:
                row = get_connection_or_404(db, body.connection_id)
                installed = set((row.installed_modules_json or "").split(",")) if hasattr(row, "installed_modules_json") else set()
                reuse = body.draft.get("reuse") if isinstance(body.draft.get("reuse"), dict) else {}
                for mid in reuse.get("models") or []:
                    mod = str(mid).split(".")[0]
                    if mod and mod in installed:
                        overlap_notes.append(
                            f"You reuse {mid} and {mod} is installed — consider linking instead of parallel models."
                        )
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            pass

    result = review_draft(
        body.draft,
        user_prompt=body.user_prompt,
        apply_fixes=body.apply_fixes,
        overlap_notes=overlap_notes or None,
    )
    return ExpertDraftReviewOut(
        score_before=result.score_before,
        score_after=result.score_after,
        verdict=result.verdict,
        review_markdown=result.review_markdown,
        findings=[
            ExpertDraftReviewFindingOut(
                priority=f.priority,
                element=f.element,
                summary=f.summary,
                detail=f.detail,
                deterministic=f.deterministic,
                repair_hint=f.repair_hint,
                citation=f.citation,
            )
            for f in result.findings
        ],
        repairs=result.repairs,
        suggestions=result.suggestions,
        draft=result.draft,
    )
