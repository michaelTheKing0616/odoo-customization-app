"""Gateway. Validates tool arguments. Does not execute tools and does not import Odoo."""

from __future__ import annotations

from typing import Any

from app.llm_gateway.normalize import drop_foreign_reasoning, nfc, nfc_data, nfc_message, partition_tool_calls, repair_roles
from app.llm_gateway.retries import delay_ms, should_stop
from app.llm_gateway.schema_lowering import canonical_issues
from app.llm_gateway.scripted import ScriptedAdapter
from app.llm_gateway.stream import IDLE_TIMEOUT_MS
from app.llm_gateway.types import LLMError, LLMResponse, ToolCall


def _default_sleep(delay_ms: int) -> None:
    import time

    time.sleep(delay_ms / 1000)


def _write_names(request: dict[str, Any]) -> frozenset[str]:
    names: set[str] = set()
    for tool in request.get("tools") or []:
        if isinstance(tool, dict) and tool.get("class") == "write" and tool.get("name"):
            names.add(str(tool["name"]))
    return frozenset(names)


class Gateway:
    def __init__(self, adapter: ScriptedAdapter, *, max_calls: int = 40, sleep: Any | None = None) -> None:
        self._adapter = adapter
        self._max_calls = max_calls
        self._sleep = sleep if sleep is not None else _default_sleep
        self.calls = 0
        self.last_delay_ms: int | None = None
        self.idle_timeout_ms = IDLE_TIMEOUT_MS

    def complete(self, request: dict[str, Any], schemas: dict[str, dict[str, Any]] | None = None) -> LLMResponse:
        if request.get("cancelled"):
            return LLMResponse(stop_reason="pause")
        if request.get("images") and not request.get("vision", True):
            raise LLMError("unsupported_feature", "vision is not available")
        prepared = _prepare(request)
        attempt = 0
        while True:
            if self.calls >= self._max_calls:
                raise LLMError("budget", "max calls")
            self.calls += 1
            attempt += 1
            try:
                response = self._adapter.complete(prepared)
                break
            except LLMError as exc:
                if should_stop(attempt, exc.kind):
                    raise
                waited = delay_ms(attempt, retry_after_ms=exc.retry_after_ms)
                self.last_delay_ms = waited
                self._sleep(waited)
                continue
        return self._check(_finish(prepared, response), schemas or {}, _write_names(prepared))

    def _check(
        self,
        response: LLMResponse,
        schemas: dict[str, dict[str, Any]],
        write_names: frozenset[str],
    ) -> LLMResponse:
        if response.stop_reason == "malformed_tool_call":
            return response
        checked: list[ToolCall] = []
        for call in response.tool_calls:
            schema = schemas.get(call.name)
            if schema is None or canonical_issues(call.args, schema):
                return LLMResponse(
                    stop_reason="malformed_tool_call",
                    tool_calls=(ToolCall(call.id, call.name, None, call.raw_args),),
                    usage=response.usage,
                    reasoning=response.reasoning,
                )
            checked.append(call)
        return LLMResponse(
            stop_reason=response.stop_reason,
            text=response.text,
            tool_calls=tuple(checked),
            usage=response.usage,
            reasoning=response.reasoning,
            tool_batches=partition_tool_calls(checked, set(write_names)),
        )


def _prepare(request: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(request)
    if prepared.get("stream") and prepared.get("stream_tools") is False:
        prepared["stream"] = False
    messages = prepared.get("messages")
    if isinstance(messages, list):
        prepared["messages"] = [nfc_message(message) for message in repair_roles(messages)]
    return drop_foreign_reasoning(prepared)


def _finish(request: dict[str, Any], response: LLMResponse) -> LLMResponse:
    source = str(request.get("reasoning_provider") or "")
    target = str(request.get("provider") or "")
    reasoning = "" if source and target and source != target else response.reasoning
    calls = tuple(
        ToolCall(
            call.id,
            call.name,
            nfc_data(call.args) if isinstance(call.args, dict) else call.args,
            call.raw_args,
        )
        for call in response.tool_calls
    )
    return LLMResponse(
        stop_reason=response.stop_reason,
        text=nfc(response.text),
        tool_calls=calls,
        usage=response.usage,
        reasoning=reasoning,
        tool_batches=response.tool_batches,
    )
