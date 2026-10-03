"""Canonical LLM types. No provider SDK and no Odoo imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RETRYABLE = frozenset({"rate_limit", "overloaded", "timeout", "network", "server"})
STOP_REASONS = frozenset(
    {
        "end",
        "tool_calls",
        "max_tokens",
        "refusal",
        "content_filter",
        "malformed_tool_call",
        "pause",
        "error",
    }
)


class LLMError(Exception):
    def __init__(self, kind: str, message: str, *, retry_after_ms: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retry_after_ms = retry_after_ms


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any] | None
    raw_args: str


@dataclass(frozen=True, slots=True)
class LLMResponse:
    stop_reason: str
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: dict[str, int] = field(default_factory=dict)
    reasoning: str = ""

    def __post_init__(self) -> None:
        if self.stop_reason not in STOP_REASONS:
            raise LLMError("unknown", f"unknown stop reason {self.stop_reason}")
