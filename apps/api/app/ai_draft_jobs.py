"""Background AI draft jobs with step progress (GEN2-1)."""

from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.ai_draft_cache import save_draft_cache
from app.ai_llm_status import STEP_LABELS, attach_llm_status, finalize_llm_status, sanitize_draft_payload
from app.ai_ollama import draft_module_from_prompt
from app.ai_pipeline import seed_studio_draft
from app.job_runner import create_job, enqueue, update_job_progress
from app.llm_provider import ai_provider_enabled
from app.ollama_warm import warm_ollama_models


ProgressFn = Callable[[int, str, dict[str, Any] | None], None]

_NON_SERIALIZABLE_KWARGS = frozenset({"client"})

_DRAFT_JOB_KWARG_DEFAULTS: dict[str, Any] = {
    "reuse_models": None,
    "rejected_reuse_models": None,
    "reuse_views": None,
    "reuse_actions": None,
    "expand": True,
    "pipeline": None,
    "protected_manifest": None,
    "odoo_version": None,
    "grain_override": None,
    "gallery_id": None,
    "host_model_override": None,
    "connect_points_override": None,
    "locked_understanding": None,
}


def build_draft_job_kwargs(
    *,
    prompt: str,
    connection_id: str | None,
    available_models: list[str] | None,
    installed_modules: list[str] | None,
    stock_catalog: list[dict] | None,
    reuse_views: list[dict] | None = None,
    reuse_actions: list[dict] | None = None,
    protected_manifest: dict[str, Any] | None = None,
    odoo_version: str | None = None,
    reuse_models: list[str] | None = None,
    rejected_reuse_models: list[str] | None = None,
    expand: bool = True,
    pipeline: str | None = None,
    grain_override: str | None = None,
    gallery_id: str | None = None,
    host_model_override: str | None = None,
    connect_points_override: dict[str, Any] | None = None,
    ai_session_id: str | None = None,
    locked_understanding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Keyword args for ``run_draft_job_body`` (excluding job_id, db_factory, client)."""
    kwargs: dict[str, Any] = {
        "prompt": prompt,
        "connection_id": connection_id,
        "available_models": available_models,
        "installed_modules": installed_modules,
        "stock_catalog": stock_catalog,
        "reuse_models": reuse_models,
        "rejected_reuse_models": rejected_reuse_models,
        "reuse_views": reuse_views,
        "reuse_actions": reuse_actions,
        "expand": expand,
        "pipeline": pipeline,
        "protected_manifest": protected_manifest,
        "odoo_version": odoo_version,
        "grain_override": grain_override,
        "gallery_id": gallery_id,
        "host_model_override": host_model_override,
        "connect_points_override": connect_points_override,
        "locked_understanding": locked_understanding,
    }
    if ai_session_id:
        kwargs["ai_session_id"] = ai_session_id
    return kwargs
# Headroom under JOB_TIMEOUTS["ai_draft"] (1800s): pack seed must still be returned.
LLM_ENRICH_BUDGET_S = 900.0
_PACK_SEED_LLM_NOTE = (
    "Draft Studio used the domain-pack seed. Click Retry AI enrichment to tailor with the LLM."
)
_COMPONENT_GRAIN_NOTE = (
    "Inherit-and-wire on the stock host. Live Apply lands metadata; no new app menu."
)


def pack_seed_skips_llm(seed: dict[str, Any]) -> bool:
    """Create draft returns the pack immediately; LLM belongs on Retry AI enrichment."""
    from app.ai_generation_engine import (
        is_component_grain_draft,
        is_gold_option_a_draft,
        is_option_a_authored_draft,
        is_refuse_draft,
        is_stock_reuse_draft,
    )

    if is_gold_option_a_draft(seed) or is_refuse_draft(seed) or is_stock_reuse_draft(seed):
        return True
    if is_option_a_authored_draft(seed):
        return True
    if is_component_grain_draft(seed):
        return True
    if not str(seed.get("domain_pack") or ""):
        return False
    return any(
        isinstance(row, dict) and row.get("model") for row in (seed.get("models") or [])
    )



def _load_locked_understanding_from_session(
    ai_session_id: str | None,
    db_factory: Callable[[], Session] | None,
) -> dict[str, Any] | None:
    """Pull Diagnosis-confirmed understanding_json from the AI session."""
    if not ai_session_id or db_factory is None:
        return None
    try:
        from app.ai_conversation.session_store import get_session
        from app.ai_conversation.understand import load_understanding

        db = db_factory()
        try:
            row = get_session(db, ai_session_id)
            if row is None:
                return None
            import json as _json

            resolved = _json.loads(row.resolved_answers_json or "{}")
            if not isinstance(resolved, dict):
                return None
            locked = load_understanding(resolved)
            return locked.to_dict() if locked else None
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        return None


def _stamp_locked_understanding(
    draft: dict[str, Any],
    prompt: str,
    *,
    locked_understanding: dict[str, Any] | None = None,
) -> None:
    """Stamp session/locked Contract IR before stock-host apply + find-it."""
    from app.ai_conversation.understand import attach_understanding

    attach_understanding(draft, prompt, locked=locked_understanding)


def _apply_locked_craft_and_surface(
    draft: dict[str, Any],
    prompt: str,
    *,
    locked_understanding: dict[str, Any] | None = None,
) -> list[str]:
    """Re-stamp craft + find-it after closer/LLM so session IR always wins."""
    notes: list[str] = []
    _stamp_locked_understanding(draft, prompt, locked_understanding=locked_understanding)
    try:
        from app.ai_stock_host_smart_buttons import apply_stock_host_smart_buttons

        notes.extend(apply_stock_host_smart_buttons(draft, prompt=prompt))
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ai_operator_surface import attach_operator_surface

        notes.extend(attach_operator_surface(draft))
    except Exception:  # noqa: BLE001
        pass
    return notes


def complete_matched_pack_draft(
    *,
    prompt: str,
    seed: dict[str, Any],
    db_factory: Callable[[], Session],
    connection_id: str | None,
    progress: ProgressFn | None = None,
    available_models: list[str] | None = None,
    installed_modules: list[str] | None = None,
    stock_catalog: list[dict[str, Any]] | None = None,
    locked_understanding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score/close a domain pack and cache it. No LLM, no background job."""
    warnings: list[str] = []
    emit = progress or (lambda *_a, **_k: None)
    _stamp_locked_understanding(seed, prompt, locked_understanding=locked_understanding)
    emit(1, "Pack seeded", seed)
    _cache_draft(
        db_factory,
        connection_id=connection_id,
        prompt=prompt,
        draft=seed,
        raw="",
        locked_understanding=locked_understanding,
    )
    draft = _finish_seed_draft(
        prompt,
        seed,
        warnings,
        available_models=available_models,
        installed_modules=installed_modules,
        stock_catalog=stock_catalog,
        connection_id=connection_id,
        db_factory=db_factory,
        locked_understanding=locked_understanding,
    )
    from app.ai_generation_engine import (
        is_component_grain_draft,
        is_option_a_authored_draft,
        is_stock_reuse_draft,
    )

    if is_option_a_authored_draft(draft):
        emit(3, "Authoring Option A module", draft)
        from app.ai_option_a_author import author_option_a_module

        client = _resolve_odoo_client(connection_id, db_factory)
        author_option_a_module(draft, prompt=prompt, client=client)
        warnings.append(
            "Option A module is LLM-authored. Zip and sandbox stay locked until the gate passes."
        )
        attach_llm_status(draft, mode="pack_fallback", reason="option_a_authored")
        emit(len(STEP_LABELS) - 1, STEP_LABELS[-1], draft)
        _cache_draft(
            db_factory,
            connection_id=connection_id,
            prompt=prompt,
            draft=draft,
            raw="",
            locked_understanding=locked_understanding,
        )
        rec = draft.get("_option_a_authoring") if isinstance(draft.get("_option_a_authoring"), dict) else {}
        note = (
            "Authoring gate passed — download zip and sandbox prove are unlocked."
            if rec.get("status") == "pass"
            else "Authoring gate blocked zip/sandbox — review findings."
        )
        return {
            "ok": True,
            "draft": draft,
            "raw_response": "",
            "note": note,
            "warnings": warnings,
            "refusals": [],
            "domain_pack": draft.get("domain_pack"),
            "grain": draft.get("grain"),
            "grain_label": draft.get("grain_label"),
            "connect_points": draft.get("connect_points"),
            "host_candidates": draft.get("host_candidates") or [],
        }

    emit(2, "Pack closed", draft)

    if is_stock_reuse_draft(draft):
        reuse_note = (
            "No custom residual — use Job Autopilot for sandbox install and process smoke."
        )
        warnings.append(reuse_note)
        attach_llm_status(draft, mode="seed_fallback", reason="stock_reuse")
    elif is_component_grain_draft(draft):
        reuse_note = _COMPONENT_GRAIN_NOTE
        warnings.append(reuse_note)
        attach_llm_status(draft, mode="seed_fallback", reason="component_grain")
    elif draft.get("domain_pack"):
        reuse_note = _PACK_SEED_LLM_NOTE
        warnings.append(reuse_note)
        attach_llm_status(draft, mode="pack_fallback", reason="pack_seed")
    else:
        reuse_note = (
            "Flash unavailable — showing the locked residual, not a padded workspace."
        )
        warnings.append(reuse_note)
        attach_llm_status(draft, mode="pack_fallback", reason="honesty_seed")
    warnings.extend(
        _apply_locked_craft_and_surface(
            draft, prompt, locked_understanding=locked_understanding
        )
    )
    emit(len(STEP_LABELS) - 1, STEP_LABELS[-1], draft)
    _cache_draft(
        db_factory,
        connection_id=connection_id,
        prompt=prompt,
        draft=draft,
        raw="",
        locked_understanding=locked_understanding,
    )
    return {
        "ok": True,
        "draft": draft,
        "raw_response": "",
        "note": reuse_note,
        "warnings": warnings,
        "refusals": [],
        "domain_pack": draft.get("domain_pack"),
        "grain": draft.get("grain"),
        "grain_label": draft.get("grain_label"),
        "connect_points": draft.get("connect_points"),
        "host_candidates": draft.get("host_candidates") or [],
    }


def _resolve_odoo_client(connection_id: str | None, db_factory: Callable[[], Session]) -> Any | None:
    if not connection_id:
        return None
    from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404

    db = db_factory()
    try:
        conn = get_connection_or_404(db, connection_id)
        return client_from_connection(conn)
    except (LookupError, OdooClientError):
        return None
    finally:
        db.close()


def _default_progress(job_id: str) -> ProgressFn:
    def emit(step: int, label: str, partial: dict[str, Any] | None = None) -> None:
        from app.ai_generation_engine import USER_PHASE_LABELS, user_phase_for_step

        phase = user_phase_for_step(step)
        payload: dict[str, Any] = {
            "step": step,
            "step_total": len(STEP_LABELS),
            "step_label": label,
            "user_phase": phase,
            "user_phase_label": USER_PHASE_LABELS[phase],
        }
        if partial is not None:
            payload["partial_draft"] = partial
            ir = partial.get("_generation_engine") if isinstance(partial, dict) else None
            if isinstance(ir, dict) and ir.get("user_phase_label"):
                payload["user_phase"] = ir.get("user_phase") or phase
                payload["user_phase_label"] = ir["user_phase_label"]
        update_job_progress(job_id, payload)

    return emit


def _finish_seed_draft(
    prompt: str,
    draft: dict[str, Any],
    warnings: list[str],
    *,
    available_models: list[str] | None = None,
    installed_modules: list[str] | None = None,
    stock_catalog: list[dict[str, Any]] | None = None,
    connection_id: str | None = None,
    db_factory: Callable[[], Session] | None = None,
    locked_understanding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score and close a pack/seed draft so the wizard can apply it without LLM."""
    from app.ai_architecture_plan import stamp_architecture_plan
    from app.ai_draft_scorecard import attach_scorecard
    from app.ai_generation_engine import (
        attach_generation_engine,
        is_component_grain_draft,
        is_gold_option_a_draft,
        is_refuse_draft,
        is_stock_reuse_draft,
    )
    from app.ai_live_apply_contract import attach_live_apply_contract
    from app.ai_odoo_app_bar import close_odoo_architecture
    from app.ai_planner_tools import stamp_planner_grounding
    from app.ai_stock_first import attach_reuse_plan_to_draft, stamp_connection_catalog

    if (
        available_models is None
        and installed_modules is None
        and not stock_catalog
        and connection_id
        and db_factory
    ):
        available_models, installed_modules, stock_catalog = _load_catalog_for_connection(
            connection_id, db_factory
        )
    from app.ai_operator_brief import attach_operator_brief

    # Session Contract IR before closer — craft must reach apply_stock_host_smart_buttons.
    # Purge foreign pack IR when locked residual Contract noun diverges (Restaurant→Visitor).
    try:
        from app.ai_residual_identity import enforce_residual_draft_identity

        warnings.extend(
            enforce_residual_draft_identity(
                draft,
                prompt=prompt,
                locked=locked_understanding,
                prefer_locked=bool(locked_understanding),
            )
        )
    except Exception:  # noqa: BLE001
        pass
    _stamp_locked_understanding(draft, prompt, locked_understanding=locked_understanding)
    attach_operator_brief(draft, user_prompt=prompt)
    if is_refuse_draft(draft):
        attach_generation_engine(draft, prompt, user_phase="review")
        draft.pop("_generation_incomplete", None)
        return sanitize_draft_payload(draft)

    stamp_connection_catalog(
        draft,
        available_models=available_models,
        installed_modules=installed_modules,
        stock_catalog=stock_catalog,
    )

    if is_stock_reuse_draft(draft):
        attach_scorecard(
            draft,
            user_prompt=prompt,
            catalog=stock_catalog,
            installed_modules=installed_modules,
        )
        try:
            warnings.extend(attach_live_apply_contract(draft))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Live-apply stamp skipped: {exc}")
        attach_generation_engine(draft, prompt, user_phase="review")
        draft.pop("_generation_incomplete", None)
        return sanitize_draft_payload(draft)

    if is_gold_option_a_draft(draft) and not draft.get("domain_pack"):
        try:
            warnings.extend(attach_live_apply_contract(draft))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Live-apply stamp skipped: {exc}")
        attach_scorecard(
            draft,
            user_prompt=prompt,
            catalog=stock_catalog,
            installed_modules=installed_modules,
        )
        attach_generation_engine(draft, prompt, user_phase="review")
        draft.pop("_generation_incomplete", None)
        return sanitize_draft_payload(draft)

    if is_component_grain_draft(draft):
        stamp_architecture_plan(draft, prompt=prompt, rebuild=True)
        warnings.extend(
            attach_reuse_plan_to_draft(
                draft,
                user_prompt=prompt,
                available_models=available_models,
                installed_modules=installed_modules,
                stock_catalog=stock_catalog,
            )
        )
        stamp_planner_grounding(
            draft,
            catalog=stock_catalog,
            installed_modules=installed_modules,
        )
        try:
            warnings.extend(attach_live_apply_contract(draft))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Live-apply stamp skipped: {exc}")
        attach_scorecard(
            draft,
            user_prompt=prompt,
            catalog=stock_catalog,
            installed_modules=installed_modules,
        )
        attach_generation_engine(draft, prompt, user_phase="review")
        draft.pop("_generation_incomplete", None)
        return sanitize_draft_payload(draft)

    # Plan IR before closer / score (Phase 1) — stock-first before model spam scoring
    stamp_architecture_plan(draft, prompt=prompt, rebuild=True)
    warnings.extend(
        attach_reuse_plan_to_draft(
            draft,
            user_prompt=prompt,
            available_models=available_models,
            installed_modules=installed_modules,
            stock_catalog=stock_catalog,
        )
    )
    stamp_planner_grounding(
        draft,
        catalog=stock_catalog,
        installed_modules=installed_modules,
    )
    warnings.extend(close_odoo_architecture(draft, user_prompt=prompt))
    try:
        warnings.extend(attach_live_apply_contract(draft))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Live-apply stamp skipped: {exc}")
    attach_scorecard(
        draft,
        user_prompt=prompt,
        catalog=stock_catalog,
        installed_modules=installed_modules,
    )
    attach_generation_engine(draft, prompt, user_phase="review")
    draft.pop("_generation_incomplete", None)
    return sanitize_draft_payload(draft)


def _load_catalog_for_connection(
    connection_id: str,
    db_factory: Callable[[], Session],
) -> tuple[list[str] | None, list[str] | None, list[dict[str, Any]]]:
    from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404

    db = db_factory()
    available: list[str] | None = None
    installed: list[str] | None = None
    stock: list[dict[str, Any]] = []
    try:
        conn = get_connection_or_404(db, connection_id)
        client = client_from_connection(conn)
        try:
            from app.ai_stock_catalog import STOCK_CATALOG_LIMIT, load_connection_stock_catalog

            catalog = load_connection_stock_catalog(client, limit=STOCK_CATALOG_LIMIT)
            available = [str(e["model"]) for e in catalog["all"]]
            stock = list(catalog["stock"])
        except Exception:  # noqa: BLE001
            available = []
        try:
            from app.capabilities import sample_installed_modules

            installed = sample_installed_modules(client, limit=300)
        except Exception:  # noqa: BLE001
            installed = []
        return available, installed, stock
    except (LookupError, OdooClientError):
        return None, None, []
    finally:
        db.close()


def _llm_draft_with_budget(
    *,
    timeout_s: float,
    progress: ProgressFn,
    kwargs: dict[str, Any],
) -> tuple[dict[str, Any], str, list[str], list[dict[str, Any]]] | None:
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai_draft_llm")
    future = pool.submit(draft_module_from_prompt, **kwargs, progress_callback=progress)
    try:
        return future.result(timeout=timeout_s)
    except FuturesTimeoutError:
        return None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _cache_draft(
    db_factory: Callable[[], Session],
    *,
    connection_id: str | None,
    prompt: str,
    draft: dict[str, Any],
    raw: str,
    locked_understanding: dict[str, Any] | None = None,
) -> None:
    prior = draft.get("_understanding") if isinstance(draft.get("_understanding"), dict) else None
    _stamp_locked_understanding(
        draft,
        prompt,
        locked_understanding=locked_understanding if locked_understanding is not None else prior,
    )
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


def _complete_component_draft(
    *,
    prompt: str,
    grain: str,
    available_models: list[str] | None,
    gallery_id: str | None,
    host_model_override: str | None,
    connect_points_override: dict[str, Any] | None,
    client: Any | None,
    db_factory: Callable[[], Session],
    connection_id: str | None,
    progress: ProgressFn | None = None,
    locked_understanding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Senior inherit-and-wire path — no pack seed, no LLM, no residual satellites."""
    from app.ai_component_builder import draft_component_from_prompt
    from app.ai_draft_scorecard import attach_scorecard
    from app.ai_live_apply_contract import attach_live_apply_contract

    warnings: list[str] = []
    emit = progress or (lambda *_a, **_k: None)
    emit(0, "Building component")
    draft, _hosts, comp_warnings = draft_component_from_prompt(
        prompt,
        grain=grain,  # type: ignore[arg-type]
        available_models=available_models,
        gallery_id=gallery_id,
        host_model_override=host_model_override,
        connect_points_override=connect_points_override,
        client=client,
    )
    warnings.extend(comp_warnings)
    # Stamp Diagnosis Contract BEFORE senior finishers re-run via cache — Prefer
    # field_pack Must-do must win over heuristic x_po / Status / JSON leakage.
    if locked_understanding is not None:
        _stamp_locked_understanding(
            draft, prompt, locked_understanding=locked_understanding
        )
        from app.ai_senior_shape import finish_senior_component

        warnings.extend(
            finish_senior_component(draft, prompt=prompt, grain=grain)  # type: ignore[arg-type]
        )
    from app.ai_architecture_plan import stamp_architecture_plan
    from app.ai_planner_tools import stamp_planner_grounding

    stamp_architecture_plan(draft, prompt=prompt, rebuild=True)
    from app.ai_stock_first import stamp_connection_catalog

    stock = [
        {"model": m, "name": m, "app": m.split(".", 1)[0]}
        for m in (available_models or [])
        if m
    ]
    stamp_connection_catalog(
        draft,
        available_models=available_models,
        stock_catalog=stock,
    )
    stamp_planner_grounding(draft, catalog=stock)
    try:
        warnings.extend(attach_live_apply_contract(draft))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Live-apply stamp skipped: {exc}")
    attach_scorecard(draft, user_prompt=prompt)
    attach_llm_status(draft, mode="llm_full", reason="component_grain")
    finalize_llm_status(draft, mode="llm_full")
    from app.ai_generation_engine import attach_generation_engine

    attach_generation_engine(draft, prompt, user_phase="review")
    draft = sanitize_draft_payload(draft)
    warnings = [
        w
        for w in warnings
        if not str(w).startswith("senior: ")
        and not (str(w).startswith("live_apply:") and "gap" not in str(w).lower())
    ]
    emit(len(STEP_LABELS) - 1, STEP_LABELS[-1], draft)
    _cache_draft(db_factory, connection_id=connection_id, prompt=prompt, draft=draft, raw="")
    return {
        "ok": True,
        "draft": draft,
        "raw_response": "",
        "warnings": warnings,
        "refusals": [],
        "domain_pack": draft.get("domain_pack"),
        "grain": draft.get("grain"),
        "grain_label": draft.get("grain_label"),
        "connect_points": draft.get("connect_points"),
        "host_candidates": draft.get("host_candidates") or [],
    }


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
    locked_understanding: dict[str, Any] | None = None,
    ai_session_id: str | None = None,
) -> dict[str, Any]:
    progress = _default_progress(job_id)
    warnings: list[str] = []
    refusals: list[dict[str, Any]] = []
    raw = ""

    from app.ai_grain import classify_grain
    from app.ai_generation_engine import maybe_seed_from_capability
    from app.ai_operator_brief import intent_corpus, stated_residual_kind

    if locked_understanding is None and ai_session_id:
        locked_understanding = _load_locked_understanding_from_session(
            ai_session_id, db_factory
        )

    capability_seed = maybe_seed_from_capability(prompt)
    if capability_seed:
        return complete_matched_pack_draft(
            prompt=prompt,
            seed=capability_seed,
            db_factory=db_factory,
            connection_id=connection_id,
            progress=progress,
            available_models=available_models,
            installed_modules=installed_modules,
            stock_catalog=stock_catalog,
            locked_understanding=locked_understanding,
        )

    grain = grain_override or classify_grain(intent_corpus(prompt) or prompt)
    if stated_residual_kind(prompt)[0] == "named":
        grain = "full_app"
    # Locked Diagnosis residual full_app must not fork into feature_slice because
    # Diagnosis chrome ("Craft smart button", "Inherit existing form: no") matches
    # component/slice cues in classify_grain.
    if (
        isinstance(locked_understanding, dict)
        and str(locked_understanding.get("grain") or "") == "full_app"
        and not locked_understanding.get("inherit_existing")
    ):
        grain = "full_app"
    if grain != "full_app":
        return _complete_component_draft(
            prompt=prompt,
            grain=grain,
            available_models=available_models,
            gallery_id=gallery_id,
            host_model_override=host_model_override,
            connect_points_override=connect_points_override,
            client=client,
            db_factory=db_factory,
            connection_id=connection_id,
            progress=progress,
            locked_understanding=locked_understanding,
        )

    progress(0, "Seeding domain pack")
    seed = seed_studio_draft(prompt)
    try:
        from app.ai_residual_identity import enforce_residual_draft_identity

        enforce_residual_draft_identity(
            seed,
            prompt=prompt,
            locked=locked_understanding,
            prefer_locked=bool(locked_understanding),
        )
    except Exception:  # noqa: BLE001
        pass
    from app.ai_architecture_plan import stamp_architecture_plan

    stamp_architecture_plan(seed, prompt=prompt, rebuild=True)
    if pack_seed_skips_llm(seed):
        return complete_matched_pack_draft(
            prompt=prompt,
            seed=seed,
            db_factory=db_factory,
            connection_id=connection_id,
            progress=progress,
            available_models=available_models,
            installed_modules=installed_modules,
            stock_catalog=stock_catalog,
            locked_understanding=locked_understanding,
        )
    # Snapshot immediately so Saved snapshots is populated even if closer/LLM later hits the cap.
    _stamp_locked_understanding(seed, prompt, locked_understanding=locked_understanding)
    progress(1, "Pack seeded", seed)
    _cache_draft(
        db_factory,
        connection_id=connection_id,
        prompt=prompt,
        draft=seed,
        raw="",
        locked_understanding=locked_understanding,
    )
    seed = _finish_seed_draft(
        prompt,
        seed,
        warnings,
        available_models=available_models,
        installed_modules=installed_modules,
        stock_catalog=stock_catalog,
        connection_id=connection_id,
        db_factory=db_factory,
        locked_understanding=locked_understanding,
    )
    progress(2, "Pack closed", seed)
    _cache_draft(
        db_factory,
        connection_id=connection_id,
        prompt=prompt,
        draft=seed,
        raw="",
        locked_understanding=locked_understanding,
    )

    draft = seed

    llm_kwargs = {
        "prompt": prompt,
        "available_models": available_models,
        "installed_modules": installed_modules,
        "reuse_models": reuse_models,
        "rejected_reuse_models": rejected_reuse_models,
        "stock_catalog": stock_catalog,
        "reuse_views": reuse_views,
        "reuse_actions": reuse_actions,
        "expand": expand,
        "pipeline": pipeline,
        "protected_manifest": protected_manifest,
        "odoo_version": odoo_version,
        "grain_override": grain_override,
        "gallery_id": gallery_id,
        "host_model_override": host_model_override,
        "connect_points_override": connect_points_override,
        "client": client,
    }
    if ai_provider_enabled():
        warm_ollama_models()
        progress(2, "LLM enrich (budgeted)")
        try:
            llm_result = _llm_draft_with_budget(
                timeout_s=LLM_ENRICH_BUDGET_S,
                progress=progress,
                kwargs=llm_kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"LLM enrich failed ({exc}) — keeping domain-pack seed.")
            llm_result = None
        if llm_result is None:
            warnings.append(
                f"LLM enrich exceeded {LLM_ENRICH_BUDGET_S:.0f}s — keeping domain-pack seed."
            )
            from app.ai_document_shape import recover_residual_draft

            warnings.extend(recover_residual_draft(draft, prompt=prompt))
            attach_llm_status(draft, mode="pack_fallback", reason="honesty_seed")
        else:
            draft, raw, llm_warnings, refusals = llm_result
            warnings.extend(llm_warnings)
            draft = sanitize_draft_payload(draft)
            if "_llm_status" not in draft:
                attach_llm_status(draft, mode="llm_full")
    else:
        warnings.append("AI assist off — Draft Studio used the domain-pack seed.")

    from app.ai_generation_engine import attach_generation_engine

    attach_generation_engine(draft, prompt, user_phase="review")
    warnings.extend(
        _apply_locked_craft_and_surface(
            draft, prompt, locked_understanding=locked_understanding
        )
    )
    progress(len(STEP_LABELS) - 1, STEP_LABELS[-1], draft)
    _cache_draft(
        db_factory,
        connection_id=connection_id,
        prompt=prompt,
        draft=draft,
        raw=raw,
        locked_understanding=locked_understanding,
    )

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
    serializable = {k: v for k, v in body_kwargs.items() if k not in _NON_SERIALIZABLE_KWARGS}
    kwargs = copy.deepcopy(serializable)
    for key, default in _DRAFT_JOB_KWARG_DEFAULTS.items():
        kwargs.setdefault(key, default)
    ai_session_id = kwargs.get("ai_session_id")
    conn_id = kwargs.get("connection_id") or connection_id

    def _fn() -> dict[str, Any]:
        from app.db import SessionLocal

        client = _resolve_odoo_client(conn_id, SessionLocal)
        result = run_draft_job_body(job_id=job_id, db_factory=SessionLocal, client=client, **kwargs)
        if ai_session_id:
            _sync_ai_session_artifact(ai_session_id, job_id, result, SessionLocal)
        return result

    enqueue(job_id, _fn)
    return job_id


def _sync_ai_session_artifact(
    session_id: str,
    job_id: str,
    result: dict[str, Any],
    db_factory: Callable[[], Session],
) -> None:
    from app.ai_conversation.refine import artifact_hash
    from app.ai_conversation.session_store import get_session, update_session

    db = db_factory()
    try:
        row = get_session(db, session_id)
        if row is None:
            return
        draft = result.get("draft") if isinstance(result, dict) else {}
        if not isinstance(draft, dict):
            draft = {}
        ahash = artifact_hash(draft) if draft else None
        # Keep session Contract IR aligned with draft (clear stale Visitor Log on Restaurant).
        resolved = {}
        try:
            import json as _json

            resolved = _json.loads(row.resolved_answers_json or "{}")
        except Exception:  # noqa: BLE001
            resolved = {}
        if not isinstance(resolved, dict):
            resolved = {}
        understanding = draft.get("_understanding") if isinstance(draft.get("_understanding"), dict) else None
        if understanding:
            from app.ai_conversation.understand import (
                Understanding,
                dump_understanding,
                load_understanding,
            )

            locked = Understanding.from_dict(understanding)
            prior = load_understanding(resolved)
            # Keep Diagnosis-confirmed residual title when draft stamped reconciled_draft.
            if (
                locked
                and prior
                and prior.grain == "full_app"
                and not prior.inherit_existing
                and locked.source == "reconciled_draft"
                and prior.title
                and locked.title
                and prior.title.lower() != locked.title.lower()
            ):
                locked = prior
            if locked:
                dump_understanding(resolved, locked)
        update_session(
            db,
            row,
            artifact=draft,
            artifact_hash=ahash,
            status="review" if draft else "failed",
            job_id=job_id,
            resolved_answers=resolved,
        )
    finally:
        db.close()


__all__ = [
    "LLM_ENRICH_BUDGET_S",
    "build_draft_job_kwargs",
    "complete_matched_pack_draft",
    "enqueue_draft_job",
    "pack_seed_skips_llm",
    "run_draft_job_body",
]
