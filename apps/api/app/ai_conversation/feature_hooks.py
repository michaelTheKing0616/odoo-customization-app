"""Shared conversational hooks for Expert and Job Autopilot."""

from __future__ import annotations

from typing import Any

from app.ai_conversation.clarify import build_clarification
from app.ai_conversation.intent_gate import assess_intent, should_block_generation


def intent_clarification_for_prompt(
    prompt: str,
    *,
    resolved_answers: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Return a clarifying question when intent is ambiguous (deterministic gate)."""
    assessment = assess_intent(prompt, resolved_answers=resolved_answers)
    if assessment.clear or not should_block_generation(assessment):
        return None
    return build_clarification(assessment, prompt=prompt)


def intent_assessment_payload(prompt: str, *, resolved_answers: dict[str, str] | None = None) -> dict[str, Any]:
    assessment = assess_intent(prompt, resolved_answers=resolved_answers)
    return {
        "clear": assessment.clear,
        "blocked": should_block_generation(assessment),
        "triggers": assessment.triggers,
        "ir_confidence": assessment.ir_confidence,
        "capability_path": assessment.capability_path,
        "notes": assessment.notes,
    }


__all__ = ["intent_assessment_payload", "intent_clarification_for_prompt"]
