"""Parse/repair JSON text from LLM responses (markdown fences, trailing commas, truncation)."""

from __future__ import annotations

import json
import re
from typing import Any


def strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def repair_json_text(text: str) -> str:
    """Best-effort fixes for common LLM JSON mistakes."""
    s = text.strip()
    # Trailing commas before } or ]
    s = re.sub(r",\s*([}\]])", r"\1", s)
    # Missing comma between adjacent properties (common LLM slip)
    string_value = r'"(?:[^"\\]|\\.)*"'
    key = rf'{string_value}\s*:'
    s = re.sub(rf"({string_value})\s+({key})", r"\1, \2", s)
    s = re.sub(
        rf"(true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+({key})",
        r"\1, \2",
        s,
    )
    s = re.sub(rf"([}}\]])\s+({key})", r"\1, \2", s)
    return s


def _in_unterminated_json_string(text: str) -> tuple[bool, bool]:
    """Return (inside_string, dangling_escape) using JSON string rules."""
    in_string = False
    escape = False
    for ch in text:
        if not in_string:
            if ch == '"':
                in_string = True
            continue
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = False
    return in_string, escape


def close_unterminated_string(text: str) -> str:
    """Close a JSON string that was cut off at the token limit."""
    s = text.rstrip()
    in_string, escape = _in_unterminated_json_string(s)
    if escape and s.endswith("\\"):
        s = s[:-1]
        in_string, escape = _in_unterminated_json_string(s)
    if in_string:
        s += '"'
    return s


def close_truncated_json(text: str) -> str:
    """Close unbalanced brackets/braces when the model hit token limits."""
    s = close_unterminated_string(text.rstrip())
    if not s:
        return s
    in_string, _escape = _in_unterminated_json_string(s)
    if not in_string:
        tail = re.search(r",\s*\"[^\"]*$", s)
        if tail:
            s = s[: tail.start()]
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in s:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()
    closers = {"{": "}", "[": "]"}
    return s + "".join(closers[ch] for ch in reversed(stack))


def parse_llm_json(text: str) -> Any:
    """Parse JSON object or array from LLM output; raise ValueError if unrecoverable."""
    base = strip_markdown_fence(text)
    candidates: list[str] = [base]
    for opener, closer in (("{", "}"), ("[", "]")):
        start = base.find(opener)
        end = base.rfind(closer)
        if start >= 0 and end > start:
            candidates.append(base[start : end + 1])

    seen: set[str] = set()
    variants: list[str] = []
    for candidate in candidates:
        for variant in (
            candidate,
            repair_json_text(candidate),
            close_truncated_json(repair_json_text(candidate)),
            close_unterminated_string(candidate),
        ):
            if variant and variant not in seen:
                seen.add(variant)
                variants.append(variant)

    last_err: json.JSONDecodeError | None = None
    for variant in variants:
        for strict in (True, False):
            try:
                return json.loads(variant, strict=strict)
            except json.JSONDecodeError as exc:
                last_err = exc
                continue

    detail = str(last_err) if last_err else "invalid JSON"
    raise ValueError(
        "AI returned malformed JSON and could not be repaired automatically. "
        f"({detail}) Click Create draft again, simplify the prompt, or use a ready-made template."
    )


def parse_llm_json_object(text: str) -> dict[str, Any]:
    data = parse_llm_json(text)
    if not isinstance(data, dict):
        raise ValueError("AI response was JSON but not an object (expected a ModuleSpec draft).")
    return data
