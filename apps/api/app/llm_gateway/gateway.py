"""Gateway. Validates tool arguments. Does not execute tools and does not import Odoo."""

from __future__ import annotations

from typing import Any

from app.llm_gateway.retries import delay_ms, should_stop
from app.llm_gateway.schema_lowering import canonical_issues
from app.llm_gateway.scripted import ScriptedAdapter
from app.llm_gateway.types import LLMError, LLMResponse, ToolCall


def _default_sleep(delay_ms: int) -> None:
    import time

    time.sleep(delay_ms / 1000)


class Gateway:
    def __init__(self, adapter: ScriptedAdapter, *, max_calls: int = 40, sleep: Any | None = None) -> None:
        self._adapter = adapter
        self._max_calls = max_calls
        self._sleep = sleep if sleep is not None else _default_sleep
        self.calls = 0
        self.last_delay_ms: int | None = None

    def complete(self, request: dict[str, Any], schemas: dict[str, dict[str, Any]] | None = None) -> LLMResponse:
        if request.get("cancelled"):
            return LLMResponse(stop_reason="pause")
        if request.get("images") and not request.get("vision", True):
            raise LLMError("unsupported_feature", "vision is not available")
        attempt = 0
        while True:
            if self.calls >= self._max_calls:
                raise LLMError("budget", "max calls")
            self.calls += 1
            attempt += 1
            try:
                response = self._adapter.complete(request)
                break
            except LLMError as exc:
                if should_stop(attempt, exc.kind):
                    raise
                waited = delay_ms(attempt, retry_after_ms=exc.retry_after_ms)
                self.last_delay_ms = waited
                self._sleep(waited)
                continue
        return self._check(response, schemas or {})

    def _check(self, response: LLMResponse, schemas: dict[str, dict[str, Any]]) -> LLMResponse:
        if response.stop_reason == "malformed_tool_call":
            return response
        checked: list[ToolCall] = []
        for call in response.tool_calls:
            schema = schemas.get(call.name)
            if schema is None or canonical_issues(call.args, schema):
                return LLMResponse(
                    stop_reason="malformed_tool_call",
                    tool_calls=(ToolCall(call.id, call.name, None, call.raw_args),),
                )
            checked.append(call)
        return LLMResponse(
            stop_reason=response.stop_reason,
            text=response.text,
            tool_calls=tuple(checked),
            usage=response.usage,
            reasoning=response.reasoning,
        )
