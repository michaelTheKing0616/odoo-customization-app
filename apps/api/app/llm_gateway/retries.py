"""Retry policy. The gateway retries calls. It never retries a tool execution."""

from __future__ import annotations

from app.llm_gateway.types import RETRYABLE, LLMError


def is_retryable(kind: str) -> bool:
    return kind in RETRYABLE


def delay_ms(attempt: int, *, retry_after_ms: int | None, base_ms: int = 500, max_ms: int = 20_000) -> int:
    if attempt < 1:
        raise LLMError("invalid_request", "attempt starts at 1")
    if retry_after_ms is not None and retry_after_ms < 0:
        raise LLMError("invalid_request", "retry-after cannot be negative")
    if retry_after_ms is not None:
        return min(retry_after_ms, max_ms)
    grown = base_ms * (2 ** (attempt - 1))
    return min(grown, max_ms)


def should_stop(attempt: int, kind: str, *, max_attempts: int = 4) -> bool:
    if not is_retryable(kind):
        return True
    return attempt >= max_attempts
