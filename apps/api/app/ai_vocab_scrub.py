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


def _pack_vocab(pack: dict[str, Any] | None) -> dict[str, str]:
    if not pack:
        return {}
    raw = pack.get("vocab")
    if not isinstance(raw, dict):
        return {}
    return {str(k).lower(): str(v) for k, v in raw.items() if k and v}


def scrub_text(text: str, vocab: dict[str, str]) -> tuple[str, bool]:
    out = text
    changed = False
    mapping = {**_DEFAULT_NEUTRAL, **vocab}
    for term, repl in sorted(mapping.items(), key=lambda x: -len(x[0])):
        if term.lower() in out.lower():
            out = re.sub(re.escape(term), repl, out, flags=re.I)
            changed = True
    return out, changed


def scrub_draft_vocabulary(
    draft: dict[str, Any],
    *,
    pack: dict[str, Any] | None = None,
) -> list[str]:
    """Scrub banned law-firm terms from descriptions, labels, and seed names."""
    vocab = _pack_vocab(pack)
    notes: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for key in ("description", "string"):
            val = model.get(key)
            if isinstance(val, str):
                new, ch = scrub_text(val, vocab)
                if ch:
                    model[key] = new
                    notes.append(f"vocab: scrubbed {model.get('model')}.{key}")
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            for key in ("string", "name"):
                val = field.get(key)
                if isinstance(val, str):
                    new, ch = scrub_text(val, vocab)
                    if ch and key == "string":
                        field[key] = new
                        notes.append(
                            f"vocab: scrubbed {model.get('model')}.{field.get('name')}"
                        )
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
]
