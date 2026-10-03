"""OpenAI Responses wire format. The gateway stays stateless. This module does not open a socket."""

from __future__ import annotations

from typing import Any

from app.llm_gateway.normalize import ArgsRejected, parse_tool_args, synthesize_call_id
from app.llm_gateway.schema_lowering import canonical_tool_issues, to_openai_strict
from app.llm_gateway.types import LLMError, LLMResponse, ToolCall


def openai_body(request: dict[str, Any]) -> dict[str, Any]:
    if "api_key" in request:
        raise LLMError("invalid_request", "credentials do not belong in the body")
    tools = []
    for tool in request.get("tools") or []:
        issues = canonical_tool_issues(str(tool.get("name") or ""), str(tool.get("description") or ""))
        if issues:
            raise LLMError("invalid_request", issues[0])
        schema = tool.get("input_schema") or {"type": "object", "properties": {}}
        tools.append(
            {
                "type": "function",
                "name": tool["name"],
                "description": tool.get("description") or "",
                "parameters": to_openai_strict(schema),
                "strict": True,
            }
        )
    return {
        "model": request["model_id"],
        "input": list(request.get("messages") or []),
        "tools": tools,
        "store": False,
        "max_output_tokens": request["max_output_tokens"],
    }


def parse_openai(payload: dict[str, Any]) -> LLMResponse:
    calls: list[ToolCall] = []
    text: list[str] = []
    for index, item in enumerate(payload.get("output") or []):
        kind = item.get("type")
        if kind == "message":
            for part in item.get("content") or []:
                if part.get("type") in {"output_text", "text"}:
                    text.append(str(part.get("text") or ""))
        elif kind == "function_call":
            raw = str(item.get("arguments") or "")
            call_id = str(item.get("call_id") or synthesize_call_id(index))
            try:
                args = parse_tool_args(raw)
            except ArgsRejected:
                return LLMResponse(
                    stop_reason="malformed_tool_call",
                    text="".join(text),
                    tool_calls=(ToolCall(call_id, str(item.get("name") or ""), None, raw),),
                )
            calls.append(ToolCall(call_id, str(item.get("name") or ""), args, raw))
    status = str(payload.get("status") or "")
    if calls:
        reason = "tool_calls"
    elif status == "incomplete":
        reason = "max_tokens"
    else:
        reason = "end"
    return LLMResponse(stop_reason=reason, text="".join(text), tool_calls=tuple(calls))


def openai_error(status: int, retry_after_ms: int | None = None) -> LLMError:
    if status == 429:
        return LLMError("rate_limit", "429", retry_after_ms=retry_after_ms)
    if status in {401, 403}:
        return LLMError("auth", str(status))
    if status == 400:
        return LLMError("invalid_request", "400")
    if status >= 500:
        return LLMError("server", str(status))
    return LLMError("unknown", str(status))
