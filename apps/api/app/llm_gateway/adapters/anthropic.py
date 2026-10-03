"""Anthropic Messages wire format. This module does not open a socket."""

from __future__ import annotations

from typing import Any

from app.llm_gateway.normalize import synthesize_call_id
from app.llm_gateway.schema_lowering import to_openai_strict
from app.llm_gateway.types import LLMError, LLMResponse, ToolCall


def anthropic_body(request: dict[str, Any]) -> dict[str, Any]:
    if "api_key" in request or "authorization" in request:
        raise LLMError("invalid_request", "credentials do not belong in the body")
    tools = []
    for tool in request.get("tools") or []:
        tools.append(
            {
                "name": tool["name"],
                "description": tool.get("description") or "",
                "input_schema": to_openai_strict(tool["input_schema"]) if tool.get("input_schema") else {"type": "object"},
            }
        )
    body: dict[str, Any] = {
        "model": request["model_id"],
        "max_tokens": request["max_output_tokens"],
        "system": request.get("system") or "",
        "messages": list(request.get("messages") or []),
    }
    if tools:
        body["tools"] = tools
    return body


def parse_anthropic(payload: dict[str, Any]) -> LLMResponse:
    reason = {
        "end_turn": "end",
        "tool_use": "tool_calls",
        "max_tokens": "max_tokens",
        "refusal": "refusal",
        "stop_sequence": "end",
        "pause_turn": "pause",
    }.get(str(payload.get("stop_reason") or ""), "error")
    calls: list[ToolCall] = []
    text: list[str] = []
    for index, block in enumerate(payload.get("content") or []):
        if block.get("type") == "text":
            text.append(str(block.get("text") or ""))
        elif block.get("type") == "tool_use":
            raw = block.get("input")
            if not isinstance(raw, dict):
                return LLMResponse(stop_reason="malformed_tool_call", text="".join(text))
            calls.append(
                ToolCall(
                    str(block.get("id") or synthesize_call_id(index)),
                    str(block.get("name") or ""),
                    raw,
                    str(raw),
                )
            )
    if calls and reason == "end":
        reason = "tool_calls"
    return LLMResponse(stop_reason=reason, text="".join(text), tool_calls=tuple(calls))


def anthropic_error(status: int) -> LLMError:
    if status == 429:
        return LLMError("rate_limit", "429")
    if status == 529:
        return LLMError("overloaded", "529")
    if status in {401, 403}:
        return LLMError("auth", str(status))
    if status == 400:
        return LLMError("invalid_request", "400")
    if status >= 500:
        return LLMError("server", str(status))
    return LLMError("unknown", str(status))
