"""Stage 1 — cheap continuous filter: question boundary + Odoo/ERP relevance."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Curated trigger vocabulary (Document 8-ish terms + live-demo phrases).
_ODOO_TERMS = (
    "odoo",
    "erp",
    "module",
    "modules",
    "studio",
    "workflow",
    "automation",
    "automations",
    "approval",
    "approvals",
    "inventory",
    "accounting",
    "invoice",
    "invoices",
    "crm",
    "sales",
    "purchase",
    "manufacturing",
    "mrp",
    "pos",
    "payroll",
    "hr",
    "employee",
    "multi-company",
    "multicompany",
    "multi company",
    "warehouse",
    "stock",
    "bom",
    "bom's",
    "kanban",
    "form view",
    "list view",
    "tree view",
    "ir.model",
    "res.partner",
    "access rights",
    "security group",
    "xpath",
    "inherit",
    "custom field",
    "custom model",
    "module spec",
    "modulespec",
    "job autopilot",
    "draft studio",
    "app studio",
    "view designer",
)

_QUESTION_START = re.compile(
    r"(?i)^\s*(?:can|could|would|will|does|do|is|are|was|were|how|what|when|where|why|which|"
    r"who|whom|whose|should|may|might|shall|is it possible|any way to|is there a way)\b"
)
_QUESTION_MARK = re.compile(r"\?\s*$")
_LIVE_PHRASE = re.compile(
    r"(?i)\b("
    r"can odoo|does odoo|does it support|is it possible|can it|will it|"
    r"how (?:do|does|can) (?:i|we|you|odoo)|"
    r"support(?:s)? (?:multi|approval|workflow|invoice|inventory)|"
    r"out of the box|native(?:ly)?\b"
    r")"
)


@dataclass(frozen=True)
class Stage1Result:
    is_question: bool
    is_odoo_relevant: bool
    triggered: bool
    reason: str
    score: float


def looks_like_question(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) < 8:
        return False
    if _QUESTION_MARK.search(t):
        return True
    if _QUESTION_START.search(t):
        return True
    # Soft: "tell me if odoo…"
    if re.search(r"(?i)\b(tell me|curious|wondering|need to know)\b", t) and "?" in t:
        return True
    return False


def odoo_relevance_score(text: str) -> tuple[float, str]:
    t = (text or "").lower()
    if not t:
        return 0.0, "empty"
    hits: list[str] = []
    for term in _ODOO_TERMS:
        if term in t:
            hits.append(term)
    phrase = bool(_LIVE_PHRASE.search(t))
    score = min(1.0, 0.15 * len(hits) + (0.45 if phrase else 0.0))
    if hits:
        return score, "terms:" + ",".join(hits[:6])
    if phrase:
        return score, "live_phrase"
    return 0.0, "no_odoo_signal"


def stage1_filter(text: str, *, min_relevance: float = 0.3) -> Stage1Result:
    q = looks_like_question(text)
    score, reason = odoo_relevance_score(text)
    relevant = score >= min_relevance
    if q and relevant:
        return Stage1Result(True, True, True, reason, score)
    if not q:
        return Stage1Result(False, relevant, False, "not_a_question", score)
    return Stage1Result(True, False, False, "question_not_odoo_relevant", score)


def is_likely_bot_or_system_speaker(speaker_name: str | None, bot_name: str | None = None) -> bool:
    s = (speaker_name or "").strip().lower()
    if not s:
        return False
    if "co-pilot" in s or "copilot" in s or "attendee" in s or s == "bot":
        return True
    if bot_name and bot_name.strip().lower() == s:
        return True
    return False

def normalize_speaker(name: str | None) -> str:
    return " ".join((name or "").strip().lower().split())


def parse_presenter_speakers(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        items = raw
    else:
        s = str(raw).strip()
        if not s:
            return []
        if s.startswith("["):
            import json

            try:
                data = json.loads(s)
                items = data if isinstance(data, list) else []
            except json.JSONDecodeError:
                items = [p.strip() for p in s.split(",")]
        else:
            items = [p.strip() for p in s.split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        n = normalize_speaker(str(item))
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def is_presenter_speaker(speaker_name: str | None, presenter_speakers: list[str] | None) -> bool:
    """True when the utterance is from a configured presenter (skip Stage 1/2)."""
    if not presenter_speakers:
        return False
    s = normalize_speaker(speaker_name)
    if not s:
        return False
    for p in presenter_speakers:
        if not p:
            continue
        if s == p or p in s or s in p:
            return True
    return False
