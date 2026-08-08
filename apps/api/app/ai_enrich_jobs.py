"""Background AI enrich jobs — retry failed LLM steps only (GEN2-2)."""

from __future__ import annotations

import copy
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.ai_draft_cache import save_draft_cache
from app.ai_llm_status import attach_llm_status, sanitize_draft_payload
from app.job_runner import create_job, enqueue, update_job_progress
from app.ollama_warm import warm_ollama_models

_ENRICH_STEPS = ("quality", "depth", "critique")
_STEP_LABELS = {
    "quality": "Re-running model quality…",
    "depth": "Re-running depth expansion…",
    "critique": "Re-running self-critique…",
}


def run_enrich_job_body(
    *,
    job_id: str,
    prompt: str,
    draft: dict[str, Any],
    failed_steps: list[str] | None,
    db_factory: Callable[[], Session],
    connection_id: str | None,
) -> dict[str, Any]:
    from app.ai_critique import run_self_critique
    from app.ai_depth import run_depth_pass
    from app.ai_model_quality import run_model_quality_pass
    from app.llm_provider import get_llm_provider

    warm_ollama_models()
    working = copy.deepcopy(draft)
    warnings: list[str] = []
    failed = set(failed_steps or [])
    status = working.get("_llm_status") if isinstance(working.get("_llm_status"), dict) else {}
    if not failed and status.get("failed_steps"):
        failed = set(status.get("failed_steps") or [])

    provider = get_llm_provider()
    steps = [s for s in _ENRICH_STEPS if s in failed]
    if not steps:
        steps = list(_ENRICH_STEPS)

    for i, step in enumerate(steps):
        update_job_progress(
            job_id,
            {
                "step": i,
                "step_total": len(steps),
                "step_label": _STEP_LABELS.get(step, step),
                "partial_draft": working,
            },
        )
        if not provider:
            warnings.append(f"enrich: skipped {step} — LLM unavailable")
            continue
        if step == "quality":
            try:
                working, q_w = run_model_quality_pass(
                    working,
                    user_prompt=prompt,
                    ambition=str(working.get("_ambition") or "standard"),
                    provider=provider,
                    expand_llm=True,
                )
                warnings.extend(q_w)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"enrich: quality step failed ({exc})")
        elif step == "depth":
            try:
                working, d_w = run_depth_pass(
                    working, user_prompt=prompt, provider=provider, expand_llm=True
                )
                warnings.extend(d_w)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"enrich: depth step failed ({exc})")
        elif step == "critique":
            try:
                working, c_w = run_self_critique(working, user_prompt=prompt, repair=True)
                warnings.extend(c_w)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"enrich: critique step failed ({exc})")

    working = sanitize_draft_payload(working)
    warnings = finalize_enriched_draft(
        working,
        prompt=prompt,
        warnings=warnings,
        llm_mode="llm_full",
        completed_steps=list(steps),
    )

    db = db_factory()
    try:
        save_draft_cache(
            db,
            connection_id=connection_id,
            prompt=prompt,
            draft=working,
            domain_pack=str(working.get("domain_pack") or "") or None,
        )
    finally:
        db.close()

    update_job_progress(
        job_id,
        {
            "step": len(steps),
            "step_total": len(steps),
            "step_label": "Enrichment complete",
            "partial_draft": working,
        },
    )
    return {"ok": True, "draft": working, "warnings": warnings}


def enqueue_enrich_job(
    db: Session,
    *,
    connection_id: str | None,
    prompt: str,
    draft: dict[str, Any],
    failed_steps: list[str] | None,
) -> str:
    row = create_job(db, kind="ai_enrich", connection_id=connection_id)
    job_id = row.id
    draft_copy = copy.deepcopy(draft)
    steps = list(failed_steps or [])

    def _fn() -> dict[str, Any]:
        from app.db import SessionLocal

        return run_enrich_job_body(
            job_id=job_id,
            prompt=prompt,
            draft=draft_copy,
            failed_steps=steps,
            db_factory=SessionLocal,
            connection_id=connection_id,
        )

    enqueue(job_id, _fn)
    return job_id


def finalize_enriched_draft(
    draft: dict[str, Any],
    *,
    prompt: str,
    warnings: list[str],
    llm_mode: str = "llm_full",
    completed_steps: list[str] | None = None,
) -> list[str]:
    """Shared tail for sync enrich-draft and async enrich jobs."""
    from app.ai_apply_readiness import filter_stale_enrich_warnings, finalize_draft_readiness_metadata
    from app.ai_critique import finalize_critique_block
    from app.ai_draft_scorecard import attach_scorecard
    from app.ai_enrich import sync_form_archs_to_models
    from app.ai_llm_status import attach_llm_status, finalize_llm_status
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    warnings.extend(sync_form_archs_to_models(draft))
    warnings.extend(run_post_critique_pipeline(draft, user_prompt=prompt))
    warnings.extend(run_production_shape_pass(draft))
    warnings.extend(finalize_critique_block(draft))
    warnings = filter_stale_enrich_warnings(warnings, draft)
    attach_scorecard(draft, user_prompt=prompt)
    finalize_draft_readiness_metadata(draft)
    attach_llm_status(draft, mode=llm_mode, completed_steps=list(completed_steps or []))
    finalize_llm_status(draft, mode=llm_mode)  # type: ignore[arg-type]
    return warnings


__all__ = ["enqueue_enrich_job", "finalize_enriched_draft", "run_enrich_job_body"]
