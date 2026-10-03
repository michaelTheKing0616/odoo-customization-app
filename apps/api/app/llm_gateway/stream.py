"""Assemble a canonical stream into the same response a non-stream call would return."""

from __future__ import annotations

from typing import Any

from app.llm_gateway.normalize import parse_tool_args
from app.llm_gateway.types import LLMResponse, ToolCall

IDLE_TIMEOUT_MS = 30_000


def events_from_step(step: dict[str, Any]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for character in str(step.get("text") or ""):
        events.append({"kind": "text_delta", "text": character})
    for index, call in enumerate(step.get("tool_calls") or []):
        call_id = str(call.get("id") or f"call_{index:04d}")
        name = str(call["name"])
        raw = str(call.get("raw_args") or "{}")
        events.append({"kind": "tool_call_start", "id": call_id, "name": name})
        for offset in range(0, len(raw), 4):
            events.append({"kind": "tool_call_args_delta", "id": call_id, "fragment": raw[offset : offset + 4]})
        events.append({"kind": "tool_call_end", "id": call_id})
    reason = "tool_calls" if step.get("tool_calls") else str(step.get("stop_reason") or "end")
    events.append({"kind": "stop", "reason": reason})
    return events


def assemble(events: list[dict[str, str]], *, idle_timeout_ms: int = IDLE_TIMEOUT_MS) -> LLMResponse:
    text: list[str] = []
    open_calls: dict[str, dict[str, str]] = {}
    finished: list[ToolCall] = []
    stop = "end"
    last_at: int | None = None
    for event in events:
        if "at_ms" in event:
            at_ms = int(event["at_ms"])
            if last_at is not None and at_ms - last_at > idle_timeout_ms:
                return LLMResponse(stop_reason="error", text="".join(text), tool_calls=tuple(finished))
            last_at = at_ms
        kind = event.get("kind")
        if kind == "text_delta":
            text.append(event.get("text") or "")
        elif kind == "tool_call_start":
            open_calls[event["id"]] = {"name": event.get("name") or "", "raw": ""}
        elif kind == "tool_call_args_delta":
            current = open_calls.get(event.get("id") or "")
            if current is None:
                return LLMResponse(stop_reason="malformed_tool_call")
            current["raw"] += event.get("fragment") or ""
        elif kind == "tool_call_end":
            current = open_calls.pop(event.get("id") or "", None)
            if current is None:
                return LLMResponse(stop_reason="malformed_tool_call")
            raw = current["raw"]
            try:
                args = parse_tool_args(raw)
            except Exception:
                return LLMResponse(
                    stop_reason="malformed_tool_call",
                    tool_calls=(ToolCall(event["id"], current["name"], None, raw),),
                )
            finished.append(ToolCall(event["id"], current["name"], args, raw))
        elif kind == "stop":
            stop = event.get("reason") or "end"
    if open_calls:
        call_id, current = next(iter(open_calls.items()))
        return LLMResponse(
            stop_reason="malformed_tool_call",
            text="".join(text),
            tool_calls=(ToolCall(call_id, current["name"], None, current["raw"]),),
        )
    if finished and stop == "end":
        stop = "tool_calls"
    return LLMResponse(stop_reason=stop, text="".join(text), tool_calls=tuple(finished))
