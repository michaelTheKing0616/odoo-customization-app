"""Parse, normalize, and dedupe Odoo selection field literals on ModuleSpec drafts."""

from __future__ import annotations

import ast
import re
from typing import Any

_PAIR_RE = re.compile(r"\(\s*'([^']+)'\s*,\s*'([^']*)'\s*\)")


def parse_selection_literal(selection: Any) -> list[tuple[str, str]] | None:
    """Parse python-literal or regex fallback into ordered (key, label) pairs."""
    if selection is None:
        return None
    if isinstance(selection, list):
        pairs: list[tuple[str, str]] = []
        for row in selection:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                pairs.append((str(row[0]), str(row[1])))
            elif isinstance(row, dict) and row.get("value") is not None:
                val = str(row["value"])
                pairs.append((val, str(row.get("name") or row.get("label") or val)))
        return pairs or None
    if not isinstance(selection, str) or not selection.strip():
        return None
    raw = selection.strip()
    for candidate in (raw, raw.replace("(", "[").replace(")", "]")):
        try:
            val = ast.literal_eval(candidate)
        except (ValueError, SyntaxError):
            continue
        if isinstance(val, (list, tuple)):
            pairs = []
            for row in val:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    pairs.append((str(row[0]), str(row[1])))
                elif isinstance(row, dict) and row.get("value") is not None:
                    val_s = str(row["value"])
                    pairs.append(
                        (
                            val_s,
                            str(row.get("name") or row.get("label") or val_s),
                        )
                    )
            if pairs:
                return pairs
    found = _PAIR_RE.findall(raw)
    if found:
        return [(k, lbl or k.replace("_", " ").title()) for k, lbl in found]
    return None


def serialize_selection(pairs: list[tuple[str, str]]) -> str:
    return "[" + ",".join(f"('{k}','{lbl}')" for k, lbl in pairs) + "]"


def dedupe_selection_pairs(
    pairs: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], bool]:
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    changed = False
    for key, label in pairs:
        if key in seen:
            changed = True
            continue
        seen.add(key)
        out.append((key, label))
    return out, changed


def selection_keys(selection: Any) -> list[str]:
    pairs = parse_selection_literal(selection)
    if not pairs:
        return []
    return [k for k, _ in pairs]


def normalize_selection_field(
    field: dict[str, Any],
    *,
    context: str = "",
) -> list[str]:
    """Coerce selection to canonical string; dedupe keys. Returns warning notes."""
    notes: list[str] = []
    if field.get("ttype") != "selection":
        return notes
    raw = field.get("selection")
    if raw is None and field.get("selection_values"):
        vals = field.get("selection_values")
        if isinstance(vals, list):
            parts: list[str] = []
            for row in vals:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    parts.append(f"('{row[0]}','{row[1]}')")
                elif isinstance(row, dict) and row.get("value") is not None:
                    parts.append(
                        f"('{row.get('value')}','{row.get('name') or row.get('value')}')"
                    )
            if parts:
                raw = "[" + ",".join(parts) + "]"
                field["selection"] = raw
                field.pop("selection_values", None)
                notes.append(f"quality: normalized selection_values on {context}")
    if not raw:
        return notes
    pairs = parse_selection_literal(raw)
    if pairs is None:
        notes.append(f"quality: unparsable selection on {context} — left unchanged")
        return notes
    deduped, duped = dedupe_selection_pairs(pairs)
    canonical = serialize_selection(deduped)
    if canonical != str(raw).strip() or duped:
        field["selection"] = canonical
        notes.append(f"quality: deduped/normalized selection on {context}")
    field.pop("selection_values", None)
    return notes


__all__ = [
    "parse_selection_literal",
    "serialize_selection",
    "dedupe_selection_pairs",
    "selection_keys",
    "normalize_selection_field",
]
