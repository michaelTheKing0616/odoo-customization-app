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


def close_truncated_json(text: str) -> str:
    """Close unbalanced brackets/braces when the model hit token limits."""
    s = text.rstrip()
    if not s:
        return s
    # Drop a trailing partial key/value (after last comma at top level-ish)
    s = re.sub(r",\s*[^,\]\}]*$", "", s)
    open_brackets = max(0, s.count("[") - s.count("]"))
    open_braces = max(0, s.count("{") - s.count("}"))
    return s + ("]" * open_brackets) + ("}" * open_braces)


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
        ):
            if variant and variant not in seen:
                seen.add(variant)
                variants.append(variant)

    last_err: json.JSONDecodeError | None = None
    for variant in variants:
        try:
            return json.loads(variant)
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
