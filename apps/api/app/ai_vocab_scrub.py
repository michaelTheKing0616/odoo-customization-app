"""Domain vocabulary scrub — ban law-firm lexicon on non-legal packs (GEN2-4)."""

from __future__ import annotations

import re
from typing import Any

_BANNED_TERMS = (
    "retainer",
    "trust account",
    "disbursement",
    "conflict check",
    "conflict_check",
    "hearing",
    "matter",
    "multi-party",
    "multi party",
)

_DEFAULT_NEUTRAL = {
    "retainer": "deposit",
    "trust account": "escrow account",
    "disbursement": "expense",
    "conflict check": "compliance check",
    "conflict_check": "compliance_check",
    "hearing": "appointment",
    "matter": "case record",
    "multi-party": "multi-contact",
    "multi party": "multi contact",
}

_DUP_LABEL_RE = re.compile(r"\b(\w[\w\s]*?)\s*/\s*\1\b", re.I)


def _pack_vocab(pack: dict[str, Any] | None) -> dict[str, str]:
    if not pack:
        return {}
    raw = pack.get("vocab")
    if not isinstance(raw, dict):
        return {}
    return {str(k).lower(): str(v) for k, v in raw.items() if k and v}


def _preserve_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def scrub_text(text: str, vocab: dict[str, str]) -> tuple[str, bool]:
    out = text
    changed = False
    mapping = {**_DEFAULT_NEUTRAL, **vocab}
    for term, repl in sorted(mapping.items(), key=lambda x: -len(x[0])):
        if term.lower() == repl.lower():
            continue
        pattern = re.compile(re.escape(term), re.I)

        def _sub(m: re.Match[str]) -> str:
            return _preserve_case(m.group(0), repl)

        new_out, n = pattern.subn(_sub, out)
        if n:
            out = new_out
            changed = True
    deduped, n = _DUP_LABEL_RE.subn(r"\1", out)
    if n:
        out = deduped.strip()
        changed = True
    return out, changed


def _scrub_string_fields(obj: dict[str, Any], keys: tuple[str, ...], vocab: dict[str, str]) -> bool:
    changed = False
    for key in keys:
        val = obj.get(key)
        if isinstance(val, str):
            new, ch = scrub_text(val, vocab)
            if ch:
                obj[key] = new
                changed = True
    return changed


def scrub_draft_vocabulary(
    draft: dict[str, Any],
    *,
    pack: dict[str, Any] | None = None,
) -> list[str]:
    """Scrub banned law-firm terms from all user-visible draft surfaces."""
    vocab = _pack_vocab(pack)
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        if _scrub_string_fields(model, ("description", "string"), vocab):
            notes.append(f"vocab: scrubbed {model.get('model')} description")
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if _scrub_string_fields(field, ("string",), vocab):
                notes.append(
                    f"vocab: scrubbed {model.get('model')}.{field.get('name')}"
                )
    for action in draft.get("actions") or []:
        if isinstance(action, dict) and _scrub_string_fields(action, ("name",), vocab):
            notes.append(f"vocab: scrubbed action {action.get('technical_name')}")
    for menu in draft.get("menus") or []:
        if isinstance(menu, dict) and _scrub_string_fields(menu, ("name",), vocab):
            notes.append(f"vocab: scrubbed menu {menu.get('technical_name')}")
    for btn in draft.get("smart_buttons") or []:
        if isinstance(btn, dict) and _scrub_string_fields(btn, ("label",), vocab):
            notes.append(f"vocab: scrubbed smart_button {btn.get('label')}")
    for view in draft.get("views") or []:
        if not isinstance(view, dict):
            continue
        arch = view.get("arch")
        if isinstance(arch, str):
            new, ch = scrub_text(arch, vocab)
            if ch:
                view["arch"] = new
                notes.append(f"vocab: scrubbed view {view.get('name')}")
    return notes


def derive_domain_prefix(prompt: str, *, pack: dict[str, Any] | None = None) -> str:
    """Multi-word head noun — never truncate to first word only."""
    if pack and pack.get("display_prefix"):
        return str(pack["display_prefix"])
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]*", prompt.strip())
    if not words:
        return "App"
    # Skip leading articles/adjectives
    skip = {"a", "an", "the", "large", "mega", "small", "simple", "comprehensive"}
    meaningful = [w for w in words if w.lower() not in skip]
    if not meaningful:
        meaningful = words
    if len(meaningful) >= 2:
        head = " ".join(meaningful[:2])
    else:
        head = meaningful[0]
    # Title-case short label
    return head.title()[:40]


def find_hub_model(draft: dict[str, Any]) -> str | None:
    """Model most referenced by many2one fields."""
    counts: dict[str, int] = {}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if field.get("ttype") != "many2one":
                continue
            rel = str(field.get("relation") or "")
            if rel.startswith("x_"):
                counts[rel] = counts.get(rel, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


__all__ = [
    "derive_domain_prefix",
    "find_hub_model",
    "scrub_draft_vocabulary",
    "scrub_text",
]
