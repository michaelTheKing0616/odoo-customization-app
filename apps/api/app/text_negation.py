"""Negation-aware needle matching for briefs that say 'not X' / 'no Y'."""

from __future__ import annotations

import re

_NEG_WORD = re.compile(
    r"(?i)\b(not|no|never|without|don't|do\s+not|doesn['’]t|"
    r"shouldn['’]t|should\s+not|won['’]t|can['’]t|cannot|nothing)\b"
)
_CLAUSE_SPLIT = re.compile(r"[!?\n;:]+|(?<![A-Za-z0-9_])\.|\.(?![A-Za-z0-9_])")


def span_is_negated(text: str, start: int, *, window: int = 96) -> bool:
    """True when `text[start:]` sits in a 'no/not/never …' clause.

    Dotted technical names (``project.task``) stay in the same clause so
    “Don’t clone project.task” still negates the trailing ``task`` / ``Project``.
    """
    if start <= 0 or not text:
        return False
    prefix = text[max(0, start - window) : start]
    clause = _CLAUSE_SPLIT.split(prefix)[-1] if prefix else ""
    return bool(_NEG_WORD.search(clause))


def iter_positive_matches(pattern: re.Pattern[str], text: str):
    blob = text or ""
    for match in pattern.finditer(blob):
        if not span_is_negated(blob, match.start()):
            yield match


def has_positive_match(pattern: re.Pattern[str], text: str) -> bool:
    return next(iter_positive_matches(pattern, text), None) is not None


def has_positive_needle(text: str, needle: str) -> bool:
    """True when `needle` occurs outside a negation window (word-ish)."""
    raw = (needle or "").strip()
    if not raw or not text:
        return False
    escaped = re.escape(raw.lower())
    if " " in raw.lower() or len(raw) <= 3:
        pat = re.compile(rf"(?i)\b{escaped}\b")
    else:
        pat = re.compile(rf"(?i)\b{escaped}[a-z]*\b")
    return has_positive_match(pat, text)


__all__ = [
    "has_positive_match",
    "has_positive_needle",
    "iter_positive_matches",
    "span_is_negated",
]
