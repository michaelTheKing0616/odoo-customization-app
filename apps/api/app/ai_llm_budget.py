"""Per-step LLM budget ladder — timeout, downshift, fallback tracking."""

from __future__ import annotations

from typing import Any

from app.llm_provider import (
    LLMError,
    LLMProvider,
    generate_json_with_timeout_retry,
    resolve_bulk_model,
)

# Seconds per pipeline step (request-scoped budget, not HTTP timeout)
STEP_BUDGETS: dict[str, float] = {
    "retrieve": 30.0,
    "entities": 90.0,
    "fields": 120.0,
    "relationships": 90.0,
    "workflow": 120.0,
    "automations": 90.0,
    "draft_json": 180.0,
    "quality": 180.0,
    "depth": 300.0,
    "critique": 180.0,
}

MODEL_DOWNSHIFT_LADDER: tuple[str, ...] = (
    "qwen3:14b",
    "qwen3:8b",
    "qwen2.5:7b",
    "llama3.2:3b",
)


def next_smaller_model(current: str) -> str | None:
    cur = current.strip()
    if cur not in MODEL_DOWNSHIFT_LADDER:
        return MODEL_DOWNSHIFT_LADDER[-1] if MODEL_DOWNSHIFT_LADDER else None
    idx = MODEL_DOWNSHIFT_LADDER.index(cur)
    if idx + 1 >= len(MODEL_DOWNSHIFT_LADDER):
        return None
    return MODEL_DOWNSHIFT_LADDER[idx + 1]


def llm_json_with_budget(
    provider: LLMProvider,
    step: str,
    prompt: str,
    *,
    system: str | None = None,
    reasoning: bool = False,
    format_schema: dict[str, Any] | None = None,
    temperature: float | None = None,
    model: str | None = None,
) -> tuple[str, str | None]:
    """Run one LLM JSON step; retry once with smaller model on timeout.

    Returns (raw_json_text, downshift_model_or_none).
    """
    budget = STEP_BUDGETS.get(step, 120.0)
    try:
        raw = generate_json_with_timeout_retry(
            provider,
            prompt,
            system=system,
            timeout_s=budget,
            reasoning=reasoning,
            format_schema=format_schema,
            temperature=temperature,
            model=model,
        )
        return raw, None
    except LLMError as exc:
        msg = str(exc).lower()
        if "timed out" not in msg and "timeout" not in msg:
            raise
        smaller = next_smaller_model(model or resolve_bulk_model())
        if not smaller:
            raise
        raw = generate_json_with_timeout_retry(
            provider,
            prompt[: min(len(prompt), 6000)],
            system=system,
            timeout_s=max(45.0, budget * 0.6),
            reasoning=False,
            format_schema=format_schema,
            temperature=temperature,
            model=smaller,
        )
        return raw, smaller


__all__ = [
    "STEP_BUDGETS",
    "llm_json_with_budget",
    "next_smaller_model",
]
