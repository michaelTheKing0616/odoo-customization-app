"""Fallback only after retryable failure, and only at a step boundary."""

from __future__ import annotations

from dataclasses import dataclass

from app.llm_gateway.gateway import Gateway
from app.llm_gateway.retries import is_retryable
from app.llm_gateway.types import LLMError, LLMResponse


_RANK = {"C": 1, "B": 2, "A": 3}


@dataclass(frozen=True, slots=True)
class Endpoint:
    name: str
    gateway: Gateway
    tier: str | None


def tier_meets(have: str | None, required: str) -> bool:
    if have not in _RANK or required not in _RANK:
        return False
    return _RANK[have] >= _RANK[required]


def call_with_fallback(
    endpoints: list[Endpoint],
    request: dict,
    *,
    required_tier: str,
    schemas: dict | None = None,
) -> tuple[LLMResponse, list[str]]:
    if not endpoints:
        raise LLMError("invalid_request", "no endpoint")
    trace: list[str] = []
    last_error: LLMError | None = None
    for index, endpoint in enumerate(endpoints):
        try:
            response = endpoint.gateway.complete(request, schemas)
        except LLMError as exc:
            last_error = exc
            trace.append(endpoint.name)
            if not is_retryable(exc.kind) or index == len(endpoints) - 1:
                raise
            continue
        trace.append(endpoint.name)
        if index > 0 and not tier_meets(endpoint.tier, required_tier):
            return LLMResponse(stop_reason="end", text="degraded to read-only"), trace
        return response, trace
    if last_error is not None:
        raise last_error
    raise LLMError("server", "fallback failed")
