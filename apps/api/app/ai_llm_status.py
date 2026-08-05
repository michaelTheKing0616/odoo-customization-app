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
    """Remove top-level error keys that must never ship in successful responses."""
    out = dict(draft)
    out.pop("error", None)
    if isinstance(out.get("json"), dict):
        nested = dict(out["json"])
        nested.pop("error", None)
        out["json"] = nested
    return out


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


def banner_for_mode(mode: str | None, *, seeded: bool | None = None) -> str | None:
    if mode == "llm_partial":
        return (
            "Some AI steps timed out; pack templates filled in. "
            "Retry AI enrichment?"
        )
    if mode == "pack_fallback":
        return (
            "Built from the retail template — the AI model was unavailable. "
            "Retry AI enrichment for tailored results."
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
    "attach_llm_status",
    "banner_for_mode",
    "empty_llm_status",
    "merge_llm_status",
    "sanitize_draft_payload",
]
