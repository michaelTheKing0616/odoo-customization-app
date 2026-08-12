"""Odoo Expert — grounded Q&A (EXP-3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.expert.ask import ask_expert, expert_assist_enabled
from app.expert.chatter_bridge import post_expert_note_to_chatter
from app.expert.explain import explain_model_or_field
from app.expert.nl_search import nl_search
from app.expert.suggested_prompts import suggested_prompts_for_context
from app.llm_provider import LLMError
from app.schemas import ExpertAskBody, ExpertAskOut, ExpertCitationOut
from app.schemas import (
    ExpertDraftReviewBody,
    ExpertDraftReviewFindingOut,
    ExpertDraftReviewOut,
    ExpertExplainModelBody,
    ExpertNLSearchBody,
    ExpertNLSearchHitOut,
    ExpertNLSearchOut,
    ExpertPostChatterBody,
    ExpertPostChatterOut,
    ExpertSuggestedPromptOut,
)

router = APIRouter(prefix="/expert", tags=["expert"])


def _expert_citation_out(c) -> ExpertCitationOut:
    return ExpertCitationOut(
        source=c.source,
        version=c.version,
        breadcrumb=c.breadcrumb,
        chunk_id=c.chunk_id,
        source_index=c.source_index,
    )


def _ask_out_from_result(result) -> ExpertAskOut:
    return ExpertAskOut(
        answer_markdown=result.answer_markdown,
        citations=[_expert_citation_out(c) for c in result.citations],
        grounded=result.grounded,
        declined=result.declined,
        suggested_tools=result.suggested_tools,
        caution_flags=result.caution_flags,
        retrieval_version=result.retrieval_version,
        model_used=result.model_used,
        reasoning=result.reasoning,
        uncited_warning=result.uncited_warning,
    )


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

    return _ask_out_from_result(result)


@router.post("/explain-model", response_model=ExpertAskOut)
def expert_explain_model(body: ExpertExplainModelBody, db: Session = Depends(get_db)) -> ExpertAskOut:
    if not expert_assist_enabled():
        raise HTTPException(
            status_code=503,
            detail="Expert requires AI_ASSIST enabled (ollama or openai-compatible)",
        )
    client = None
    version: str | None = None
    if body.connection_id:
        from app.odoo_service import client_from_connection, get_connection_or_404

        try:
            row = get_connection_or_404(db, body.connection_id)
            client = client_from_connection(row)
            version = str(row.odoo_version) if getattr(row, "odoo_version", None) else None
        except Exception:  # noqa: BLE001
            client = None
    try:
        result = explain_model_or_field(
            db,
            model=body.model,
            field=body.field,
            draft=body.draft,
            user_prompt=body.user_prompt,
            connection_id=body.connection_id,
            client=client,
        )
    except LLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _ask_out_from_result(result)


@router.post("/post-to-chatter", response_model=ExpertPostChatterOut)
def expert_post_to_chatter(body: ExpertPostChatterBody, db: Session = Depends(get_db)) -> ExpertPostChatterOut:
    result = post_expert_note_to_chatter(
        db,
        connection_id=body.connection_id,
        model=body.model,
        res_id=body.res_id,
        body_markdown=body.body_markdown,
        subject=body.subject,
        confirmed=body.confirmed,
    )
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message)
    return ExpertPostChatterOut(ok=result.ok, posted=result.posted, message=result.message)


@router.get("/suggested-prompts", response_model=list[ExpertSuggestedPromptOut])
def expert_suggested_prompts(
    route: str | None = Query(default=None),
    model: str | None = Query(default=None),
    view_type: str | None = Query(default=None),
    draft_summary: str | None = Query(default=None),
) -> list[ExpertSuggestedPromptOut]:
    rows = suggested_prompts_for_context(
        route=route,
        model=model,
        view_type=view_type,
        draft_summary=draft_summary,
    )
    return [ExpertSuggestedPromptOut(**row) for row in rows]


@router.post("/nl-search", response_model=ExpertNLSearchOut)
def expert_nl_search(body: ExpertNLSearchBody, db: Session = Depends(get_db)) -> ExpertNLSearchOut:
    models: list[dict] = []
    try:
        from app.odoo_service import client_from_connection, get_connection_or_404

        row = get_connection_or_404(db, body.connection_id)
        client = client_from_connection(row)
        models = [
            {"model": m.model, "name": m.name}
            for m in client.list_models(custom_only=False, limit=400)
        ]
    except Exception:  # noqa: BLE001
        models = []
    result = nl_search(body.query, connection_id=body.connection_id, models=models)
    return ExpertNLSearchOut(
        query=result.query,
        hits=[
            ExpertNLSearchHitOut(
                id=h.id,
                kind=h.kind,
                label=h.label,
                description=h.description,
                href=h.href,
                expert_question=h.expert_question,
                score=h.score,
            )
            for h in result.hits
        ],
    )


@router.post("/review-draft", response_model=ExpertDraftReviewOut)
def expert_review_draft(body: ExpertDraftReviewBody, db: Session = Depends(get_db)) -> ExpertDraftReviewOut:
    from app.expert.draft_review import review_draft

    overlap_notes: list[str] = []
    version: str | None = None
    if body.connection_id:
        try:
            from app.odoo_service import get_connection_or_404

            row = get_connection_or_404(db, body.connection_id)
            version = str(row.odoo_version) if getattr(row, "odoo_version", None) else None
            installed = set((row.installed_modules_json or "").split(",")) if hasattr(row, "installed_modules_json") else set()
            reuse = body.draft.get("reuse") if isinstance(body.draft.get("reuse"), dict) else {}
            for mid in reuse.get("models") or []:
                mod = str(mid).split(".")[0]
                if mod and mod in installed:
                    overlap_notes.append(
                        f"You reuse {mid} and {mod} is installed — consider linking instead of parallel models."
                    )
        except Exception:  # noqa: BLE001
            pass

    result = review_draft(
        body.draft,
        user_prompt=body.user_prompt,
        apply_fixes=body.apply_fixes,
        overlap_notes=overlap_notes or None,
        db=db,
        version=version,
        include_narratives=True,
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
                narrative_paragraph=f.narrative_paragraph,
                narrative_citations=[
                    ExpertCitationOut(
                        source=c.get("source", ""),
                        version=c.get("version", ""),
                        breadcrumb=c.get("breadcrumb", ""),
                        chunk_id=c.get("chunk_id", ""),
                        source_index=int(c.get("source_index") or 0),
                    )
                    for c in (f.narrative_citations or [])
                ],
            )
            for f in result.findings
        ],
        repairs=result.repairs,
        suggestions=result.suggestions,
        draft=result.draft,
    )
