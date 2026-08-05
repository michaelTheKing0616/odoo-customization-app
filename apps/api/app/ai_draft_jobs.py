"""Background AI draft jobs with step progress (GEN2-1)."""

from __future__ import annotations

import copy
import json
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.ai_draft_cache import save_draft_cache
from app.ai_llm_status import STEP_LABELS, attach_llm_status, sanitize_draft_payload
from app.ai_ollama import draft_module_from_prompt
from app.job_runner import create_job, enqueue, update_job_progress
from app.ollama_warm import warm_ollama_models


ProgressFn = Callable[[int, str, dict[str, Any] | None], None]


def _default_progress(job_id: str) -> ProgressFn:
    def emit(step: int, label: str, partial: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {
            "step": step,
            "step_total": len(STEP_LABELS),
            "step_label": label,
        }
        if partial is not None:
            payload["partial_draft"] = partial
        update_job_progress(job_id, payload)

    return emit


def run_draft_job_body(
    *,
    job_id: str,
    prompt: str,
    available_models: list[str] | None,
    installed_modules: list[str] | None,
    stock_catalog: list[dict] | None,
    reuse_models: list[str] | None,
    rejected_reuse_models: list[str] | None,
    reuse_views: list[dict] | None,
    reuse_actions: list[dict] | None,
    expand: bool,
    pipeline: str | None,
    protected_manifest: dict[str, Any] | None,
    odoo_version: str | None,
    grain_override: str | None,
    gallery_id: str | None,
    host_model_override: str | None,
    connect_points_override: dict[str, Any] | None,
    client: Any | None,
    db_factory: Callable[[], Session],
    connection_id: str | None,
) -> dict[str, Any]:
    warm_ollama_models()
    progress = _default_progress(job_id)
    progress(0, STEP_LABELS[0])

    draft, raw, warnings, refusals = draft_module_from_prompt(
        prompt,
        available_models=available_models,
        installed_modules=installed_modules,
        reuse_models=reuse_models,
        rejected_reuse_models=rejected_reuse_models,
        stock_catalog=stock_catalog,
        reuse_views=reuse_views,
        reuse_actions=reuse_actions,
        expand=expand,
        pipeline=pipeline,
        protected_manifest=protected_manifest,
        odoo_version=odoo_version,
        grain_override=grain_override,
        gallery_id=gallery_id,
        host_model_override=host_model_override,
        connect_points_override=connect_points_override,
        client=client,
        progress_callback=progress,
    )
    progress(len(STEP_LABELS) - 1, STEP_LABELS[-1], draft)
    draft = sanitize_draft_payload(draft)
    if "_llm_status" not in draft:
        attach_llm_status(draft, mode="llm_full")

    db = db_factory()
    try:
        save_draft_cache(
            db,
            connection_id=connection_id,
            prompt=prompt,
            draft=draft,
            raw_response=raw,
            domain_pack=str(draft.get("domain_pack") or "") or None,
        )
    finally:
        db.close()

    return {
        "ok": True,
        "draft": draft,
        "raw_response": raw,
        "warnings": warnings,
        "refusals": refusals,
        "domain_pack": draft.get("domain_pack"),
        "grain": draft.get("grain"),
        "grain_label": draft.get("grain_label"),
        "connect_points": draft.get("connect_points"),
        "host_candidates": draft.get("host_candidates") or [],
    }


def enqueue_draft_job(db: Session, *, connection_id: str | None, body_kwargs: dict[str, Any]) -> str:
    row = create_job(db, kind="ai_draft", connection_id=connection_id)
    job_id = row.id
    kwargs = copy.deepcopy(body_kwargs)

    def _fn() -> dict[str, Any]:
        from app.db import SessionLocal

        return run_draft_job_body(job_id=job_id, db_factory=SessionLocal, **kwargs)

    enqueue(job_id, _fn)
    return job_id


__all__ = ["enqueue_draft_job", "run_draft_job_body"]
