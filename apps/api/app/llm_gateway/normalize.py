"""Parse tool arguments. Never eval. Reject duplicate keys, NaN, and deep payloads."""

from __future__ import annotations

import json
import secrets
import threading
import time
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


_CROCKFORD32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CALL_ID_PREFIX = "call_"
_ULID_TIMESTAMP_BITS = 48
_ULID_RANDOM_BITS = 80
_ULID_RANDOM_MASK = (1 << _ULID_RANDOM_BITS) - 1
_TIMESTAMP_MASK = (1 << _ULID_TIMESTAMP_BITS) - 1

_mint_lock = threading.Lock()
_last_timestamp_ms = -1
_last_randomness = 0


def _encode_crockford(value: int, length: int) -> str:
    chars = ["0"] * length
    for offset in range(length - 1, -1, -1):
        chars[offset] = _CROCKFORD32[value & 31]
        value >>= 5
    return "".join(chars)


def _encode_ulid(timestamp_ms: int, randomness: int) -> str:
    """10 Crockford chars of millisecond time, then 16 chars of 80-bit randomness."""
    return _encode_crockford(timestamp_ms & _TIMESTAMP_MASK, 10) + _encode_crockford(
        randomness & _ULID_RANDOM_MASK, 16
    )


def is_minted_call_id(value: str) -> bool:
    """True when ``value`` is ``call_`` plus 26 Crockford base32 characters."""
    if len(value) != 31 or not value.startswith(_CALL_ID_PREFIX):
        return False
    return all(character in _CROCKFORD32 for character in value[len(_CALL_ID_PREFIX) :])


def synthesize_call_id(index: int) -> str:
    """Mint ``call_`` plus a 26-character Crockford base32 ULID.

    ``index`` stays in the signature for existing callers. It is not encoded.
    A repeated millisecond increments the previous 80-bit random value so two
    mints in that millisecond cannot collide.
    """
    _ = index
    global _last_timestamp_ms, _last_randomness
    with _mint_lock:
        now = (time.time_ns() // 1_000_000) & _TIMESTAMP_MASK
        if now > _last_timestamp_ms:
            _last_timestamp_ms = now
            _last_randomness = secrets.randbits(_ULID_RANDOM_BITS)
        elif _last_randomness >= _ULID_RANDOM_MASK:
            while now <= _last_timestamp_ms:
                time.sleep(0.001)
                now = (time.time_ns() // 1_000_000) & _TIMESTAMP_MASK
            _last_timestamp_ms = now
            _last_randomness = secrets.randbits(_ULID_RANDOM_BITS)
        else:
            _last_randomness += 1
        timestamp_ms = _last_timestamp_ms
        randomness = _last_randomness
    return _CALL_ID_PREFIX + _encode_ulid(timestamp_ms, randomness)


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
