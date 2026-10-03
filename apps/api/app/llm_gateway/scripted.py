"""Scripted adapter. Tests never call a live provider."""

from __future__ import annotations

from typing import Any

from app.llm_gateway.normalize import map_stop_reason, parse_tool_args, record_usage, synthesize_call_id
from app.llm_gateway.types import LLMError, LLMResponse, ToolCall


class ScriptedAdapter:
    def __init__(self, steps: list[dict[str, Any]]) -> None:
        self._steps = list(steps)
        self.calls = 0
        self.last_request: dict[str, Any] | None = None

    def complete(self, request: dict[str, Any]) -> LLMResponse:
        self.last_request = request
        self.calls += 1
        if not self._steps:
            raise LLMError("server", "script exhausted")
        step = self._steps.pop(0)
        usage = record_usage(step.get("usage") if isinstance(step.get("usage"), dict) else None)
        if step.get("error"):
            raise LLMError(
                str(step["error"]),
                str(step.get("message") or step["error"]),
                retry_after_ms=step.get("retry_after_ms"),
            )
        if request.get("tool_choice") == "none":
            raw_calls = []
        else:
            raw_calls = step.get("tool_calls") or []
        calls: list[ToolCall] = []
        for index, item in enumerate(raw_calls):
            raw = str(item.get("raw_args") if item.get("raw_args") is not None else item.get("args_json") or "{}")
            call_id = str(item.get("id") or "") or synthesize_call_id(self.calls * 10 + index)
            try:
                args = parse_tool_args(raw) if item.get("args") is None else item["args"]
                if item.get("args") is None:
                    parse_tool_args(raw)
            except Exception:
                return LLMResponse(
                    stop_reason="malformed_tool_call",
                    tool_calls=(ToolCall(call_id, str(item.get("name") or ""), None, raw),),
                    usage=usage,
                )
            calls.append(ToolCall(call_id, str(item["name"]), args if isinstance(args, dict) else None, raw))
        reason = "tool_calls" if calls else map_stop_reason(str(step.get("stop_reason") or "end"))
        reasoning = str(request.get("reasoning") or "") if request.get("echo_reasoning") else str(step.get("reasoning") or "")
        return LLMResponse(
            stop_reason=reason,
            text=str(step.get("text") or ""),
            tool_calls=tuple(calls),
            usage=usage,
            reasoning=reasoning,
        )
