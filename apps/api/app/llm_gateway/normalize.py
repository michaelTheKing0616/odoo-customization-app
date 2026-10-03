"""Parse tool arguments. Never eval. Reject duplicate keys, NaN, and deep payloads."""

from __future__ import annotations

import json
import unicodedata
from typing import Any

from app.llm_gateway.types import LLMError

MAX_ARGS_BYTES = 256 * 1024
MAX_DEPTH = 12

_ROLE_MAP = {
    "system": "system",
    "developer": "system",
    "user": "user",
    "human": "user",
    "assistant": "assistant",
    "model": "assistant",
    "tool": "tool",
    "function": "tool",
    "tool_result": "tool",
}

_STOP_REASON_MAP = {
    "end": "end",
    "stop": "end",
    "end_turn": "end",
    "stop_sequence": "end",
    "STOP": "end",
    "tool_calls": "tool_calls",
    "tool_use": "tool_calls",
    "max_tokens": "max_tokens",
    "length": "max_tokens",
    "MAX_TOKENS": "max_tokens",
    "refusal": "refusal",
    "content_filter": "content_filter",
    "SAFETY": "content_filter",
    "RECITATION": "content_filter",
    "malformed_tool_call": "malformed_tool_call",
    "MALFORMED_FUNCTION_CALL": "malformed_tool_call",
    "pause": "pause",
    "pause_turn": "pause",
    "error": "error",
}


class ArgsRejected(Exception):
    def __init__(self, reason: str, raw: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.raw = raw


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError("duplicate key")
        seen.add(key)
        out[key] = value
    return out


def _reject_constant(token: str) -> None:
    raise ValueError(token)


def _depth(value: Any, level: int = 0) -> None:
    if not isinstance(value, (dict, list)):
        return
    if level >= MAX_DEPTH:
        raise ValueError("depth")
    children = value.values() if isinstance(value, dict) else value
    for child in children:
        _depth(child, level + 1)


def parse_tool_args(raw: str) -> dict[str, Any]:
    if len(raw.encode("utf-8")) > MAX_ARGS_BYTES:
        raise ArgsRejected("size", raw)
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except RecursionError as exc:
        raise ArgsRejected("depth", raw) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise ArgsRejected("malformed", raw) from exc
    if not isinstance(value, dict):
        raise ArgsRejected("malformed", raw)
    try:
        _depth(value)
    except RecursionError as exc:
        raise ArgsRejected("depth", raw) from exc
    except ValueError as exc:
        raise ArgsRejected(str(exc) or "depth", raw) from exc
    return value


def synthesize_call_id(index: int) -> str:
    return f"call_{index:04d}"


def partition_tool_calls(calls: Any, write_names: set[str]) -> tuple[tuple[str, ...], ...]:
    batches: list[tuple[str, ...]] = []
    current: list[str] = []
    for call in calls:
        if call.name in write_names:
            if current:
                batches.append(tuple(current))
                current = []
            batches.append((call.id,))
        else:
            current.append(call.id)
    if current:
        batches.append(tuple(current))
    return tuple(batches)


def repair_roles(messages: list[Any]) -> list[dict[str, Any]]:
    repaired: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise LLMError("invalid_request", "message")
        raw_role = str(message.get("role") or "")
        if raw_role == "":
            role = "user"
        elif raw_role not in _ROLE_MAP:
            raise LLMError("invalid_request", "role")
        else:
            role = _ROLE_MAP[raw_role]
        if role == "tool" and not (repaired and repaired[-1]["role"] in {"assistant", "tool"}):
            role = "user"
        repaired.append({**message, "role": role})
    return repaired


def map_stop_reason(raw: str) -> str:
    return _STOP_REASON_MAP.get(raw, "error")


def record_usage(payload: dict[str, Any] | None) -> dict[str, int]:
    if not payload:
        return {}

    def pick(*keys: str) -> int:
        for key in keys:
            if payload.get(key) is not None:
                return int(payload[key])
        return 0

    return {
        "input_tokens": pick("input_tokens", "prompt_tokens", "promptTokenCount"),
        "output_tokens": pick("output_tokens", "completion_tokens", "candidatesTokenCount"),
    }


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def nfc_data(value: Any) -> Any:
    if isinstance(value, str):
        return nfc(value)
    if isinstance(value, dict):
        return {(nfc(key) if isinstance(key, str) else key): nfc_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [nfc_data(item) for item in value]
    return value


def nfc_message(message: dict[str, Any]) -> dict[str, Any]:
    content = message.get("content")
    if isinstance(content, str):
        return {**message, "content": nfc(content)}
    return message


def drop_foreign_reasoning(request: dict[str, Any]) -> dict[str, Any]:
    provider = str(request.get("provider") or "")
    source = str(request.get("reasoning_provider") or "")
    if not provider or not source or source == provider:
        return request
    cleaned = {key: value for key, value in request.items() if key != "reasoning"}
    messages = []
    for message in cleaned.get("messages") or []:
        if isinstance(message, dict) and "reasoning" in message:
            messages.append({key: value for key, value in message.items() if key != "reasoning"})
        else:
            messages.append(message)
    if "messages" in cleaned:
        cleaned["messages"] = messages
    return cleaned
