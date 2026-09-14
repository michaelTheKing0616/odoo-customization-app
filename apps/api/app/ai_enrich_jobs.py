"""Background AI enrich jobs — production Retry (revive LLM + missed work + residual).

Retry AI enrichment:
1. Revive providers (warm local Ollama, probe Flash/cloud/fallbacks)
2. Deterministic residual recovery from the operator brief
3. Re-run missed LLM draft generation when Create draft fell back / timed out
4. Re-run quality / depth / critique for any remaining failed steps
5. Always close with residual recover so hollow shells never ship
"""

from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.ai_draft_cache import save_draft_cache
from app.ai_llm_status import attach_llm_status, sanitize_draft_payload
from app.job_runner import create_job, enqueue, update_job_progress

_ENRICH_STEPS = ("quality", "depth", "critique")
_PIPELINE_FAIL_MARKERS = frozenset(
    {
        "step1",
        "step2",
        "step3",
        "step4",
        "step5",
        "step6",
        "entities",
        "fields",
        "relationships",
        "workflow",
        "automations",
        "draft_json",
        "draft_llm",
    }
)
# Shorter than Create-draft 900s budget — Retry already has a residual seed.
RETRY_DRAFT_LLM_BUDGET_S = 420.0

_STEP_LABELS = {
    "revive": "Waking AI providers…",
    "recover": "Completing residual from your brief…",
    "draft_llm": "Re-running missed AI draft steps…",
    "quality": "Re-running model quality…",
    "depth": "Re-running depth expansion…",
    "critique": "Re-running self-critique…",
}


def needs_draft_llm_retry(
    draft: dict[str, Any],
    *,
    prompt: str = "",
    failed_steps: list[str] | None = None,
) -> bool:
    """True when Create draft never got a full LLM ModuleSpec (or staged steps failed)."""
    from app.ai_document_shape import draft_needs_residual_recovery

    status = draft.get("_llm_status") if isinstance(draft.get("_llm_status"), dict) else {}
    reason = str(status.get("reason") or "")
    mode = str(status.get("mode") or "")
    if reason in {"honesty_seed", "timeout", "unavailable"}:
        return True
    if mode in {"pack_fallback", "llm_partial"}:
        return True
    if draft.get("_pipeline") == "honesty_seed":
        return True
    failed = [str(s) for s in (failed_steps or [])]
    if any(s in _PIPELINE_FAIL_MARKERS or s.startswith("step") for s in failed):
        return True
    return draft_needs_residual_recovery(draft, prompt=prompt)


def enrich_steps_for_draft(
    draft: dict[str, Any],
    *,
    prompt: str,
    failed_steps: list[str] | None,
    provider: Any | None,
) -> list[str]:
    """Pick post-draft LLM polish steps. Thin honesty seeds skip depth."""
    from app.ai_document_shape import (
        THIN_SHAPES,
        classify_document_shape,
        draft_needs_residual_recovery,
    )

    failed = [s for s in (failed_steps or []) if s in _ENRICH_STEPS]
    needs_recover = draft_needs_residual_recovery(draft, prompt=prompt)
    shape = classify_document_shape(prompt or str(draft.get("_user_prompt") or ""), draft)
    thin = shape in THIN_SHAPES

    if not provider:
        return []

    if failed:
        if thin and needs_recover:
            return [s for s in failed if s != "depth"] or ["quality"]
        return failed

    if needs_recover and thin:
        return ["quality"]
    if needs_recover:
        return ["quality", "critique"]
    return list(_ENRICH_STEPS)


def _field_count(draft: dict[str, Any]) -> int:
    total = 0
    for model in draft.get("models") or []:
        if isinstance(model, dict):
            total += len([f for f in (model.get("fields") or []) if isinstance(f, dict)])
    return total


def _merge_llm_draft_retry(
    working: dict[str, Any],
    llm_draft: dict[str, Any],
    *,
    prompt: str,
) -> tuple[dict[str, Any], list[str]]:
    """Prefer a richer LLM ModuleSpec when Retry succeeded; keep residual otherwise."""
    notes: list[str] = []
    llm_fields = _field_count(llm_draft)
    base_fields = _field_count(working)
    llm_models = [
        m
        for m in (llm_draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    ]
    if not llm_models:
        notes.append("enrich: draft_llm returned no x_* models — keeping residual seed")
        return working, notes
    if llm_fields < max(2, base_fields):
        notes.append(
            f"enrich: draft_llm thinner ({llm_fields} fields < {base_fields}) — keeping residual"
        )
        return working, notes

    # Preserve operator prompt + connection catalog on the LLM result.
    for key in ("_user_prompt", "_connection_catalog", "_operator_brief"):
        if working.get(key) and not llm_draft.get(key):
            llm_draft[key] = working[key]
    if prompt and not llm_draft.get("_user_prompt"):
        llm_draft["_user_prompt"] = prompt
    notes.append(
        f"enrich: draft_llm replaced residual with LLM ModuleSpec ({llm_fields} fields)"
    )
    return llm_draft, notes


def _run_draft_llm_retry(
    *,
    prompt: str,
    working: dict[str, Any],
    connection_id: str | None,
    db_factory: Callable[[], Session],
    progress: Callable[[dict[str, Any]], None],
) -> tuple[dict[str, Any], list[str]]:
    """Re-attempt full ModuleSpec LLM path that Create draft missed."""
    from app.ai_draft_jobs import _load_catalog_for_connection, _resolve_odoo_client
    from app.ai_ollama import draft_module_from_prompt

    warnings: list[str] = []
    available_models = None
    installed_modules = None
    stock_catalog: list[dict[str, Any]] = []
    client = None
    if connection_id:
        try:
            client = _resolve_odoo_client(connection_id, db_factory)
            available_models, installed_modules, stock_catalog = _load_catalog_for_connection(
                connection_id, db_factory
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"enrich: catalog probe skipped ({exc})")

    reuse_models = []
    if isinstance(working.get("reuse"), dict):
        reuse_models = [
            str(m) for m in (working["reuse"].get("models") or []) if m
        ]

    def _cb(step: int, label: str, partial: dict[str, Any] | None) -> None:
        progress(
            {
                "step_label": f"Re-running AI draft — {label}",
                "partial_draft": partial or working,
            }
        )

    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai_enrich_draft_llm")
    future = pool.submit(
        draft_module_from_prompt,
        prompt,
        available_models=available_models,
        installed_modules=installed_modules,
        reuse_models=reuse_models or None,
        stock_catalog=stock_catalog or None,
        expand=True,
        progress_callback=_cb,
        client=client,
    )
    try:
        result = future.result(timeout=RETRY_DRAFT_LLM_BUDGET_S)
    except FuturesTimeoutError:
        warnings.append(
            f"enrich: draft_llm exceeded {RETRY_DRAFT_LLM_BUDGET_S:.0f}s — keeping residual"
        )
        pool.shutdown(wait=False, cancel_futures=True)
        return working, warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"enrich: draft_llm failed ({exc}) — keeping residual")
        pool.shutdown(wait=False, cancel_futures=True)
        return working, warnings
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    llm_draft, _raw, llm_warnings, _refusals = result
    warnings.extend(llm_warnings)
    merged, merge_notes = _merge_llm_draft_retry(working, llm_draft, prompt=prompt)
    warnings.extend(merge_notes)
    return sanitize_draft_payload(merged), warnings


def _import_enrich_runtime():
    """Import enrich deps; reload if :8001 was started before symbols landed on disk.

    uvicorn without --reload keeps old module objects. Lazy-loading a newer
    ai_enrich_jobs against a stale ai_document_shape raises ImportError and
    finishes Retry in ~2s with a hollow snapshot — reload once and retry.
    """
    import importlib

    from app.ai_critique import run_self_critique
    from app.ai_depth import run_depth_pass
    from app.ai_model_quality import run_model_quality_pass

    try:
        from app.ai_document_shape import (
            THIN_SHAPES,
            classify_document_shape,
            draft_needs_residual_recovery,
            recover_residual_draft,
        )
        from app.ollama_warm import revive_llm_providers
    except ImportError:
        import app.ai_document_shape as _shape_mod
        import app.ollama_warm as _warm_mod

        importlib.reload(_shape_mod)
        importlib.reload(_warm_mod)
        from app.ai_document_shape import (
            THIN_SHAPES,
            classify_document_shape,
            draft_needs_residual_recovery,
            recover_residual_draft,
        )
        from app.ollama_warm import revive_llm_providers

    return {
        "run_self_critique": run_self_critique,
        "run_depth_pass": run_depth_pass,
        "run_model_quality_pass": run_model_quality_pass,
        "THIN_SHAPES": THIN_SHAPES,
        "classify_document_shape": classify_document_shape,
        "draft_needs_residual_recovery": draft_needs_residual_recovery,
        "recover_residual_draft": recover_residual_draft,
        "revive_llm_providers": revive_llm_providers,
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
    _rt = _import_enrich_runtime()
    run_self_critique = _rt["run_self_critique"]
    run_depth_pass = _rt["run_depth_pass"]
    run_model_quality_pass = _rt["run_model_quality_pass"]
    THIN_SHAPES = _rt["THIN_SHAPES"]
    classify_document_shape = _rt["classify_document_shape"]
    draft_needs_residual_recovery = _rt["draft_needs_residual_recovery"]
    recover_residual_draft = _rt["recover_residual_draft"]
    revive_llm_providers = _rt["revive_llm_providers"]

    working = copy.deepcopy(draft)
    warnings: list[str] = []
    status = working.get("_llm_status") if isinstance(working.get("_llm_status"), dict) else {}
    failed_in = list(failed_steps or [])
    if not failed_in and status.get("failed_steps"):
        failed_in = [str(s) for s in (status.get("failed_steps") or [])]

    completed: list[str] = []
    phase = 0

    def _progress(payload: dict[str, Any]) -> None:
        update_job_progress(
            job_id,
            {
                "step": phase,
                "step_total": max(4, phase + 1),
                "step_label": payload.get("step_label") or "Enriching…",
                "partial_draft": payload.get("partial_draft") or working,
            },
        )

    # --- 1. Revive AI ---
    phase = 0
    _progress({"step_label": _STEP_LABELS["revive"], "partial_draft": working})
    provider, revive_notes = revive_llm_providers()
    warnings.extend(revive_notes)
    completed.append("revive")
    if provider:
        warnings.append(
            f"enrich: using revived provider {getattr(provider, 'name', type(provider).__name__)}"
        )

    # --- 2. Deterministic residual (always) ---
    phase = 1
    _progress({"step_label": _STEP_LABELS["recover"], "partial_draft": working})
    warnings.extend(recover_residual_draft(working, prompt=prompt))
    completed.append("recover")
    recovered_before_llm = draft_needs_residual_recovery(draft, prompt=prompt)

    # --- 3. Re-run missed draft LLM ---
    do_draft_llm = bool(provider) and needs_draft_llm_retry(
        draft, prompt=prompt, failed_steps=failed_in
    )
    if do_draft_llm:
        phase = 2
        _progress({"step_label": _STEP_LABELS["draft_llm"], "partial_draft": working})

        def _draft_progress(payload: dict[str, Any]) -> None:
            update_job_progress(
                job_id,
                {
                    "step": phase,
                    "step_total": 6,
                    "step_label": str(payload.get("step_label") or _STEP_LABELS["draft_llm"]),
                    "partial_draft": payload.get("partial_draft") or working,
                },
            )

        working, draft_w = _run_draft_llm_retry(
            prompt=prompt,
            working=working,
            connection_id=connection_id,
            db_factory=db_factory,
            progress=_draft_progress,
        )
        warnings.extend(draft_w)
        warnings.extend(recover_residual_draft(working, prompt=prompt))
        completed.append("draft_llm")
    elif not provider and needs_draft_llm_retry(draft, prompt=prompt, failed_steps=failed_in):
        warnings.append(
            "enrich: draft_llm skipped — no provider reachable after revive; "
            "residual from brief is ready for review"
        )

    # --- 4. Polish steps (quality / depth / critique) ---
    # Re-probe if revive failed earlier but Ollama finished warming mid-job.
    if provider is None:
        provider, more = revive_llm_providers(timeout_s=2.0)
        warnings.extend(more)
    steps = enrich_steps_for_draft(
        working, prompt=prompt, failed_steps=failed_in, provider=provider
    )
    for i, step in enumerate(steps):
        phase = 3 + i
        _progress({"step_label": _STEP_LABELS.get(step, step), "partial_draft": working})
        if not provider:
            warnings.append(f"enrich: skipped {step} — LLM unavailable")
            continue
        if step == "quality":
            try:
                from app.ai_stock_first import is_reuse_rich

                thin = (
                    classify_document_shape(prompt, working) in THIN_SHAPES
                    or is_reuse_rich(working)
                )
                working, q_w = run_model_quality_pass(
                    working,
                    user_prompt=prompt,
                    ambition=str(working.get("_ambition") or "standard"),
                    provider=provider,
                    expand_llm=not thin,
                )
                warnings.extend(q_w)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"enrich: quality step failed ({exc})")
        elif step == "depth":
            try:
                from app.ai_stock_first import is_reuse_rich

                working, d_w = run_depth_pass(
                    working,
                    user_prompt=prompt,
                    provider=provider,
                    expand_llm=not is_reuse_rich(working),
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
        from app.ai_stock_first import clip_to_stock_first_floor

        warnings.extend(clip_to_stock_first_floor(working, user_prompt=prompt))
        warnings.extend(recover_residual_draft(working, prompt=prompt))
        completed.append(step)

    working = sanitize_draft_payload(working)
    llm_hit = "draft_llm" in completed or any(s in completed for s in _ENRICH_STEPS)
    llm_mode = "llm_full" if (llm_hit and provider) else "residual_recovered"
    if llm_hit and provider and any(
        "failed" in w.lower() or "unavailable" in w.lower() or "exceeded" in w.lower()
        for w in warnings
    ):
        llm_mode = "llm_partial"
    if recovered_before_llm and not provider:
        llm_mode = "residual_recovered"

    warnings = finalize_enriched_draft(
        working,
        prompt=prompt,
        warnings=warnings,
        llm_mode=llm_mode,
        completed_steps=completed,
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
            "step": phase + 1,
            "step_total": phase + 1,
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
    from app.ai_document_shape import additive_model_growth_blocked, honor_operator_brief, recover_residual_draft
    from app.ai_domain_packs import load_domain_pack, merge_domain_pack
    from app.ai_draft_scorecard import attach_scorecard
    from app.ai_enrich import sync_form_archs_to_models
    from app.ai_llm_status import finalize_llm_status
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass
    from app.ai_odoo_app_bar import close_odoo_architecture, run_odoo_app_bar_pass
    from app.ai_stock_first import clip_to_stock_first_floor, restore_pack_identity

    warnings.extend(recover_residual_draft(draft, prompt=prompt))
    warnings.extend(honor_operator_brief(draft, user_prompt=prompt))
    warnings.extend(restore_pack_identity(draft, user_prompt=prompt))
    pack = load_domain_pack(str(draft.get("domain_pack") or ""))
    if pack and not additive_model_growth_blocked(draft, prompt=prompt):
        merged, merge_notes = merge_domain_pack(draft, pack)
        warnings.extend(merge_notes)
        draft.clear()
        draft.update(merged)
    warnings.extend(clip_to_stock_first_floor(draft, user_prompt=prompt))
    warnings.extend(honor_operator_brief(draft, user_prompt=prompt))
    warnings.extend(sync_form_archs_to_models(draft))
    warnings.extend(run_post_critique_pipeline(draft, user_prompt=prompt))
    warnings.extend(run_odoo_app_bar_pass(draft, user_prompt=prompt))
    warnings.extend(run_production_shape_pass(draft))
    warnings.extend(close_odoo_architecture(draft, user_prompt=prompt))
    warnings.extend(clip_to_stock_first_floor(draft, user_prompt=prompt))
    warnings.extend(recover_residual_draft(draft, prompt=prompt))
    warnings.extend(finalize_critique_block(draft))
    warnings = filter_stale_enrich_warnings(warnings, draft)
    attach_scorecard(draft, user_prompt=prompt)
    finalize_draft_readiness_metadata(draft)
    try:
        from app.ai_operator_surface import attach_operator_surface

        warnings.extend(attach_operator_surface(draft))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"operator_surface: skipped ({exc})")
    from app.ai_document_shape import (
        draft_needs_hygiene_repair,
        draft_needs_residual_recovery,
    )

    needs_retry = (
        llm_mode in {"llm_partial", "pack_fallback", "seed_fallback", "residual_recovered"}
        or draft_needs_hygiene_repair(draft, prompt=prompt)
        or draft_needs_residual_recovery(draft, prompt=prompt)
    )
    if llm_mode == "residual_recovered":
        attach_llm_status(
            draft,
            mode="pack_fallback",
            reason="residual_recovered",
            completed_steps=list(completed_steps or []),
        )
        finalize_llm_status(draft, mode="pack_fallback")
    else:
        attach_llm_status(draft, mode=llm_mode, completed_steps=list(completed_steps or []))  # type: ignore[arg-type]
        finalize_llm_status(draft, mode=llm_mode)  # type: ignore[arg-type]
    status = draft.get("_llm_status") if isinstance(draft.get("_llm_status"), dict) else {}
    status["retry_recommended"] = bool(needs_retry)
    # Clean llm_full with no hygiene → Retry may stay visible but disabled in the wizard.
    status["enrichment_clean"] = bool(
        llm_mode == "llm_full" and not needs_retry and not status.get("failed_steps")
    )
    draft["_llm_status"] = status
    return warnings


__all__ = [
    "RETRY_DRAFT_LLM_BUDGET_S",
    "enqueue_enrich_job",
    "enrich_steps_for_draft",
    "finalize_enriched_draft",
    "needs_draft_llm_retry",
    "run_enrich_job_body",
]
