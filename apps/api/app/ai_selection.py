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


_ANTONYM_PAIRS = frozenset(
    {
        frozenset({"active", "inactive"}),
        frozenset({"open", "closed"}),
        frozenset({"yes", "no"}),
        frozenset({"true", "false"}),
        frozenset({"on", "off"}),
        frozenset({"enabled", "disabled"}),
        frozenset({"available", "unavailable"}),
    }
)
_TERMINAL_ALIASES = {"completed": "done", "complete": "done"}


def snake_selection_key(key: str) -> str:
    """Odoo selection keys are snake_case identifiers, not Title Case labels."""
    raw = str(key or "").strip()
    if not raw:
        return raw
    if re.search(r"[\s-]", raw):
        return re.sub(r"[\s-]+", "_", raw).lower()
    if raw[:1].isupper():
        return raw.lower()
    return raw


def canonicalize_selection_pairs(
    pairs: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], dict[str, str], bool]:
    """Snake keys, fold Draft/draft, and unswap antonym value/label pairs.

    Domain-agnostic: no industry vocab. Antonym pairs are generic status words.
    """
    mapping: dict[str, str] = {}
    rebuilt: list[tuple[str, str]] = []
    for key, label in pairs:
        new_key = snake_selection_key(key)
        folded_terminal = new_key in _TERMINAL_ALIASES
        if folded_terminal:
            new_key = _TERMINAL_ALIASES[new_key]
        new_label = str(label or "").strip() or new_key.replace("_", " ").title()
        if (folded_terminal or new_key == "done") and snake_selection_key(
            new_label
        ) in _TERMINAL_ALIASES:
            new_label = "Done"
        label_as_key = snake_selection_key(new_label)
        if (
            frozenset({new_key.lower(), label_as_key.lower()}) in _ANTONYM_PAIRS
            and new_key.lower() != label_as_key.lower()
        ):
            new_label = new_key.replace("_", " ").title()
        mapping[str(key)] = new_key
        rebuilt.append((new_key, new_label))
    deduped, duped = dedupe_selection_pairs(rebuilt)
    changed = duped or deduped != list(pairs)
    return deduped, mapping, changed


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
        bare: list[str] | None = None
        for candidate in (raw, raw.replace("(", "[").replace(")", "]")):
            try:
                val = ast.literal_eval(candidate)
            except (ValueError, SyntaxError):
                continue
            if isinstance(val, (list, tuple)) and val and all(isinstance(x, str) for x in val):
                bare = [str(x) for x in val]
                break
        if bare:
            pairs = [(k, k.replace("_", " ").title()) for k in bare]
            field["selection"] = serialize_selection(pairs)
            notes.append(f"quality: coerced bare string selection on {context}")
        else:
            notes.append(f"quality: unparsable selection on {context} — left unchanged")
            return notes
    canonical_pairs, mapping, changed = canonicalize_selection_pairs(pairs)
    canonical = serialize_selection(canonical_pairs)
    if canonical != str(raw).strip() or changed:
        field["selection"] = canonical
        notes.append(f"quality: canonicalized selection on {context}")
    default = field.get("default")
    if isinstance(default, str) and default in mapping and mapping[default] != default:
        field["default"] = mapping[default]
    field.pop("selection_values", None)
    return notes


__all__ = [
    "parse_selection_literal",
    "serialize_selection",
    "dedupe_selection_pairs",
    "selection_keys",
    "snake_selection_key",
    "canonicalize_selection_pairs",
    "normalize_selection_field",
]
