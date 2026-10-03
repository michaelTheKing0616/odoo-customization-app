"""Parse tool arguments. Never eval. Reject duplicate keys, NaN, and deep payloads."""

from __future__ import annotations

import json
from typing import Any

MAX_ARGS_BYTES = 256 * 1024
MAX_DEPTH = 12


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
