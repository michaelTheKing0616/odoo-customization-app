"""Gemini generateContent wire format. Missing call ids are synthesized. This module does not open a socket."""

from __future__ import annotations

from typing import Any

from app.llm_gateway.normalize import synthesize_call_id
from app.llm_gateway.schema_lowering import canonical_tool_issues, to_gemini
from app.llm_gateway.types import LLMError, LLMResponse, ToolCall


def gemini_body(request: dict[str, Any]) -> dict[str, Any]:
    if "api_key" in request:
        raise LLMError("invalid_request", "credentials do not belong in the body")
    declarations = []
    for tool in request.get("tools") or []:
        issues = canonical_tool_issues(str(tool.get("name") or ""), str(tool.get("description") or ""))
        if issues:
            raise LLMError("invalid_request", issues[0])
        declarations.append(
            {
                "name": tool["name"],
                "description": tool.get("description") or "",
                "parameters": to_gemini(tool.get("input_schema") or {"type": "object"}),
            }
        )
    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": request.get("system") or ""}]},
        "contents": list(request.get("messages") or []),
    }
    if declarations:
        body["tools"] = [{"functionDeclarations": declarations}]
    return body


def parse_gemini(payload: dict[str, Any]) -> LLMResponse:
    candidates = payload.get("candidates") or [{}]
    content = (candidates[0] or {}).get("content") or {}
    finish = str((candidates[0] or {}).get("finishReason") or "STOP")
    reason = {
        "STOP": "end",
        "MAX_TOKENS": "max_tokens",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
        "MALFORMED_FUNCTION_CALL": "malformed_tool_call",
    }.get(finish, "error")
    text: list[str] = []
    calls: list[ToolCall] = []
    for index, part in enumerate(content.get("parts") or []):
        if "text" in part:
            text.append(str(part.get("text") or ""))
        function_call = part.get("functionCall")
        if isinstance(function_call, dict):
            args = function_call.get("args")
            if not isinstance(args, dict):
                return LLMResponse(stop_reason="malformed_tool_call", text="".join(text))
            calls.append(
                ToolCall(
                    str(function_call.get("id") or synthesize_call_id(index)),
                    str(function_call.get("name") or ""),
                    args,
                    str(args),
                )
            )
    if calls and reason == "end":
        reason = "tool_calls"
    return LLMResponse(stop_reason=reason, text="".join(text), tool_calls=tuple(calls))


def gemini_error(status: int) -> LLMError:
    if status == 429:
        return LLMError("rate_limit", "429")
    if status in {401, 403}:
        return LLMError("auth", str(status))
    if status == 400:
        return LLMError("invalid_request", "400")
    if status >= 500:
        return LLMError("server", str(status))
    return LLMError("unknown", str(status))
