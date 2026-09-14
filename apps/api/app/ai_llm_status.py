"""Structured LLM run status — replaces top-level error leakage in drafts."""

from __future__ import annotations

from typing import Any, Literal

LlmMode = Literal["llm_full", "llm_partial", "pack_fallback", "seed_fallback"]

STEP_LABELS: tuple[str, ...] = (
    "Retrieving domain context",
    "Extracting entities",
    "Defining fields",
    "Mapping relationships",
    "Building workflow",
    "Adding automations",
    "Finalizing draft",
)

# ModuleSpec top-level keys (spec + internal metadata). Used to detect model dict spliced at root.
DRAFT_TOP_LEVEL_ALLOWLIST = frozenset(
    {
        "technical_name",
        "display_name",
        "depends",
        "models",
        "views",
        "menus",
        "actions",
        "access_rules",
        "smart_buttons",
        "automations",
        "reuse",
        "reuse_hints",
        "reuse_stock",
        "anti_patterns",
        "domain_pack",
        "multi_company",
        "grain",
        "grain_label",
        "connect_points",
        "host_candidates",
        "odoo_major",
        "json",
        "_meta",
        "_llm_status",
        "_depth",
        "_ambition",
        "_user_prompt",
        "_pipeline",
        "_completeness",
        "_critique",
        "_pack_reuse_stock",
        "_compute_suggestions",
        "_generation_incomplete",
        "_odoo_app_bar",
        "_scorecard",
        "_domain_briefing",
        "_pack_model_ids",
        "_live_apply",
        "_connection_catalog",
        "custom_code_blocks",
        "_capability_gaps",
        "_capability_primary_option_a",
        "_noun_skips",
        "_done_bar",
        "_go_live_ready",
        "_option_a_smoke",
        "_grain_display_kind",
        "_component",
        "_senior_shape",
        "_architecture_plan",
        "_architecture_drift",
        "_certification",
        "_static_odoo",
        "_failures",
        "_repair_count",
        "_repair_history",
        "_certified_artifacts",
        "_sandbox_install",
        "_planner_grounding",
        "_operator_brief",
        "_generation_engine",
        "_delivery_preference",
    }
)

# Keys that belong on a model entry, not on the draft root when models[] is present.
MODEL_SPLICE_KEYS = frozenset(
    {
        "model",
        "description",
        "is_workflow",
        "fields",
        "state_field",
        "mode",
    }
)


def empty_llm_status(*, mode: LlmMode = "llm_full") -> dict[str, Any]:
    return {
        "mode": mode,
        "failed_steps": [],
        "completed_steps": [],
        "reason": None,
        "step": 0,
        "step_total": len(STEP_LABELS),
        "step_label": STEP_LABELS[0],
    }


def attach_llm_status(
    draft: dict[str, Any],
    *,
    mode: LlmMode,
    failed_steps: list[str] | None = None,
    completed_steps: list[str] | None = None,
    reason: str | None = None,
    step: int | None = None,
    step_label: str | None = None,
) -> dict[str, Any]:
    status = empty_llm_status(mode=mode)
    if failed_steps:
        status["failed_steps"] = list(failed_steps)
    if completed_steps:
        status["completed_steps"] = list(completed_steps)
    if reason:
        status["reason"] = reason
    if step is not None:
        status["step"] = step
    if step_label:
        status["step_label"] = step_label
    draft["_llm_status"] = status
    return draft


def sanitize_draft_payload(draft: dict[str, Any]) -> dict[str, Any]:
    """Remove top-level error keys and fix model-level key leakage before returning drafts."""
    out = dict(draft)
    out.pop("error", None)
    if isinstance(out.get("json"), dict):
        nested = dict(out["json"])
        nested.pop("error", None)
        out["json"] = nested
    out, _ = validate_draft_response_shape(out)
    return out


def _looks_like_model_splice(draft: dict[str, Any]) -> bool:
    """True when a model dict was merged onto the spec root (GEN2-8 root payload leak)."""
    model = draft.get("model")
    return (
        isinstance(model, str)
        and model.startswith("x_")
        and isinstance(draft.get("models"), list)
        and len(draft.get("models") or []) > 0
    )


def refresh_draft_meta(draft: dict[str, Any]) -> None:
    """Keep _meta counts aligned with spec lists (fixes smart-button header drift)."""
    if not isinstance(draft.get("_meta"), dict):
        return
    draft["_meta"] = {
        **draft["_meta"],
        "model_count": len(draft.get("models") or []),
        "view_count": len(draft.get("views") or []),
        "menu_count": len(draft.get("menus") or []),
        "smart_button_count": len(draft.get("smart_buttons") or []),
        "automation_count": len(draft.get("automations") or []),
        "domain_pack": draft.get("domain_pack"),
    }


def validate_draft_response_shape(draft: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Strip model-level keys spliced at root; refresh _meta. Returns (draft, warnings)."""
    warnings: list[str] = []
    if not isinstance(draft, dict):
        return draft, warnings
    out = dict(draft)
    if not _looks_like_model_splice(out):
        refresh_draft_meta(out)
        return out, warnings

    leaked = sorted(k for k in MODEL_SPLICE_KEYS if k in out)
    for key in leaked:
        out.pop(key, None)
    if leaked:
        warnings.append(f"shape: stripped model-level root keys: {', '.join(leaked)}")

    unknown = sorted(
        k
        for k in out
        if k not in DRAFT_TOP_LEVEL_ALLOWLIST and not str(k).startswith("_")
    )
    if unknown:
        warnings.append(f"shape: unexpected top-level keys remain: {', '.join(unknown)}")

    refresh_draft_meta(out)
    return out, warnings


def finalize_llm_status(draft: dict[str, Any], *, mode: LlmMode | None = None) -> None:
    """Terminal payload: populate completed_steps and clear frozen progress labels."""
    status = draft.get("_llm_status")
    if not isinstance(status, dict):
        return
    if draft.get("_component"):
        status["step_total"] = 4
        status["step"] = 3
        status["step_label"] = "Ready"
        status["completed_steps"] = ["Host", "Fields", "View", "Ready"]
        if mode:
            status["mode"] = mode
        draft["_llm_status"] = status
        return
    total = int(status.get("step_total") or len(STEP_LABELS))
    final_step = max(0, total - 1)
    status["step"] = final_step
    status["step_label"] = STEP_LABELS[final_step] if final_step < len(STEP_LABELS) else "Complete"
    if mode:
        status["mode"] = mode
    completed = list(status.get("completed_steps") or [])
    if not completed:
        failed = set(status.get("failed_steps") or [])
        completed = [label for i, label in enumerate(STEP_LABELS) if label not in failed]
    status["completed_steps"] = completed
    resolved_mode = str(mode or status.get("mode") or "")
    try:
        from app.ai_document_shape import draft_needs_hygiene_repair, draft_needs_residual_recovery

        prompt = str(draft.get("_user_prompt") or "")
        needs = draft_needs_hygiene_repair(draft, prompt=prompt) or draft_needs_residual_recovery(
            draft, prompt=prompt
        )
    except Exception:  # noqa: BLE001
        needs = False
    failed = list(status.get("failed_steps") or [])
    status["retry_recommended"] = bool(
        needs
        or failed
        or resolved_mode in {"llm_partial", "pack_fallback", "seed_fallback"}
    )
    status["enrichment_clean"] = bool(
        resolved_mode == "llm_full" and not status["retry_recommended"]
    )
    # Always present so the wizard never treats omitted keys as "still dirty llm_full".
    draft["_llm_status"] = status


def merge_llm_status(
    existing: dict[str, Any] | None,
    *,
    mode: LlmMode | None = None,
    failed_step: str | None = None,
    completed_step: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    base = dict(existing or empty_llm_status())
    if mode:
        base["mode"] = mode
    if failed_step and failed_step not in base.get("failed_steps", []):
        base.setdefault("failed_steps", []).append(failed_step)
    if completed_step and completed_step not in base.get("completed_steps", []):
        base.setdefault("completed_steps", []).append(completed_step)
    if reason:
        base["reason"] = reason
    if base.get("failed_steps"):
        if base["mode"] == "llm_full":
            base["mode"] = "llm_partial"
    return base


def banner_for_mode(
    mode: str | None,
    *,
    seeded: bool | None = None,
    reason: str | None = None,
) -> str | None:
    if mode == "llm_partial":
        return (
            "Some AI steps timed out; the draft was finished from your prompt. "
            "Click Retry AI enrichment to wake AI, re-run missed steps, and "
            "complete residual fields from your brief if AI stays down."
        )
    if mode == "pack_fallback":
        if reason == "residual_recovered":
            return (
                "Residual completed from your brief "
                "(AI was unavailable). Review fields, then Apply. "
                "Click Retry AI enrichment again to wake AI and polish when a model is back."
            )
        if reason in {"timeout", "unavailable", "honesty_seed"}:
            return (
                "AI was unavailable on Create draft. Click Retry AI enrichment — "
                "it wakes Flash/local/cloud, re-runs missed AI steps, and still "
                "completes residual fields from your brief if AI stays down."
            )
        return (
            "Draft Studio used the domain pack (not a retail template). "
            "Click Retry AI enrichment to wake AI and tailor when available."
        )
    if mode == "seed_fallback":
        if seeded is False:
            return None
        return (
            "Depth targets were met via generic operational seeds — "
            "review entities before apply."
        )
    return None


__all__ = [
    "STEP_LABELS",
    "DRAFT_TOP_LEVEL_ALLOWLIST",
    "MODEL_SPLICE_KEYS",
    "attach_llm_status",
    "banner_for_mode",
    "empty_llm_status",
    "finalize_llm_status",
    "merge_llm_status",
    "refresh_draft_meta",
    "sanitize_draft_payload",
    "validate_draft_response_shape",
]
