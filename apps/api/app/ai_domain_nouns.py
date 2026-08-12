"""Deterministic prompt-noun coverage — no LLM required (GEN-2)."""

from __future__ import annotations

import re
from typing import Any

from app.ai_post_critique import NOUN_STOPWORDS as _STOPWORDS

# Nouns that are too generic to require a dedicated model when alone.
_GENERIC_NOUNS = frozenset({"order", "item", "line", "record", "data", "user", "company"})

_GLOBAL_NOUNS = frozenset({"worldwide", "global", "international"})

_GLOBAL_PROMPT_RE = re.compile(
    r"\b(around\s+the\s+world|international|global|worldwide|multi[\s-]?country|"
    r"across\s+countries|multiple\s+countries|multiple\s+branches)\b",
    re.I,
)

_REUSE_NOUN_MAP = {
    "partner": "res.partner",
    "customer": "res.partner",
    "client": "res.partner",
    "contact": "res.partner",
    "vendor": "res.partner",
    "supplier": "res.partner",
    "employee": "hr.employee",
    "staff": "hr.employee",
    "user": "res.users",
    "company": "res.company",
    "product": "product.product",
}


def _lemmatize(token: str) -> str:
    t = token.lower().strip("'")
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 5 and t.endswith("ches"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def extract_prompt_nouns(user_prompt: str) -> list[str]:
    """Simple noun-ish tokens from the prompt (lemmatized, deduped)."""
    if not user_prompt.strip():
        return []
    tokens = re.findall(r"[a-zA-Z']+", user_prompt.lower())
    out: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        if tok in _STOPWORDS:
            continue
        lemma = _lemmatize(tok)
        if lemma in _STOPWORDS or lemma in seen:
            continue
        if len(lemma) < 3:
            continue
        seen.add(lemma)
        out.append(lemma)
    return out


def _model_text_blob(draft: dict[str, Any]) -> str:
    parts: list[str] = [str(draft.get("display_name") or "")]
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        parts.append(str(m.get("model") or ""))
        parts.append(str(m.get("description") or ""))
        for f in m.get("fields") or []:
            if isinstance(f, dict):
                parts.append(str(f.get("string") or ""))
                parts.append(str(f.get("name") or ""))
    for hint in draft.get("reuse_hints") or []:
        if isinstance(hint, dict):
            parts.append(str(hint.get("model") or ""))
            parts.append(str(hint.get("reason") or ""))
    for key in ("mail_templates", "cron_jobs", "reports"):
        for item in draft.get(key) or []:
            if not isinstance(item, dict):
                continue
            for field in ("name", "subject", "body_html", "code", "report_name"):
                parts.append(str(item.get(field) or ""))
    for block in draft.get("custom_code_blocks") or []:
        if isinstance(block, dict):
            parts.append(str(block.get("reason") or ""))
    return " ".join(parts).lower()


def _branch_has_country(draft: dict[str, Any]) -> bool:
    for m in draft.get("models") or []:
        if not isinstance(m, dict) or str(m.get("model") or "") != "x_branch":
            continue
        names = {
            str(f.get("name"))
            for f in (m.get("fields") or [])
            if isinstance(f, dict) and f.get("name")
        }
        if "x_country_id" in names or "x_region" in names:
            return True
    return False


def _noun_resolved(
    noun: str,
    draft: dict[str, Any],
    *,
    reuse_models: list[str] | None = None,
) -> bool:
    if noun in _GLOBAL_NOUNS:
        prompt = str(draft.get("_user_prompt") or "")
        if _GLOBAL_PROMPT_RE.search(prompt) and _branch_has_country(draft):
            return True
    blob = _model_text_blob(draft)
    if noun in blob:
        return True
    if noun.endswith("y") and f"{noun[:-1]}i" in blob:
        return True
    reuse = reuse_models or []
    mapped = _REUSE_NOUN_MAP.get(noun)
    if mapped and mapped in reuse:
        return True
    for rm in reuse:
        leaf = rm.split(".")[-1].replace("_", " ")
        if noun in leaf or noun in rm.lower():
            return True
    skips = draft.get("_noun_skips") or []
    if isinstance(skips, list) and noun in skips:
        return True
    return False


def domain_noun_coverage(
    draft: dict[str, Any],
    user_prompt: str,
    *,
    reuse_models: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Return (checklist rows, uncovered nouns, draft warnings)."""
    nouns = extract_prompt_nouns(user_prompt)
    key_nouns = [
        n
        for n in nouns
        if n not in _GENERIC_NOUNS and len(n) >= 4
    ]
    items: list[dict[str, Any]] = []
    uncovered: list[str] = []
    warnings: list[str] = []
    for noun in key_nouns:
        ok = _noun_resolved(noun, draft, reuse_models=reuse_models)
        detail = (
            f"covered by model/reuse"
            if ok
            else f"Prompt mentions '{noun}' but no {noun} model or reuse decision exists."
        )
        items.append({"id": f"noun_uncovered:{noun}", "ok": ok, "detail": detail})
        if not ok:
            uncovered.append(noun)
            warnings.append(
                f"Prompt mentions '{noun}' but no {noun} model or reuse decision exists."
            )
    return items, uncovered, warnings


_NOUN_MODEL_TEMPLATES: dict[str, dict[str, Any]] = {
    "branch": {
        "model": "x_branch",
        "description": "Branch / location",
        "fields": [
            {"name": "x_name", "ttype": "char", "string": "Branch", "required": True},
            {"name": "x_code", "ttype": "char", "string": "Code"},
            {"name": "x_address", "ttype": "char", "string": "Address"},
            {
                "name": "x_company_id",
                "ttype": "many2one",
                "relation": "res.company",
                "string": "Company",
            },
        ],
    },
    "promotion": {
        "model": "x_promotion",
        "description": "Promotion / campaign",
        "fields": [
            {"name": "x_name", "ttype": "char", "string": "Promotion", "required": True},
            {"name": "x_date_start", "ttype": "date", "string": "Start"},
            {"name": "x_date_end", "ttype": "date", "string": "End"},
            {"name": "x_discount_pct", "ttype": "float", "string": "Discount %"},
        ],
    },
    "transfer": {
        "model": "x_branch_transfer",
        "description": "Inter-branch transfer",
        "fields": [
            {"name": "x_name", "ttype": "char", "string": "Transfer", "required": True},
            {
                "name": "x_branch_from_id",
                "ttype": "many2one",
                "relation": "x_branch",
                "string": "From branch",
            },
            {
                "name": "x_branch_to_id",
                "ttype": "many2one",
                "relation": "x_branch",
                "string": "To branch",
            },
            {"name": "x_qty", "ttype": "float", "string": "Quantity"},
        ],
    },
}


def expand_uncovered_noun_models(
    draft: dict[str, Any],
    user_prompt: str,
    *,
    reuse_models: list[str] | None = None,
) -> list[str]:
    """Deterministically add minimal x_* models for uncovered prompt nouns."""
    notes: list[str] = []
    _items, uncovered, _w = domain_noun_coverage(
        draft, user_prompt, reuse_models=reuse_models
    )
    if not uncovered:
        return notes
    existing = {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    for noun in uncovered:
        template = _NOUN_MODEL_TEMPLATES.get(noun)
        if not template:
            continue
        mid = str(template["model"])
        if mid in existing:
            continue
        draft.setdefault("models", []).append(
            {
                **template,
                "mode": "new",
                "source": "noun_expand",
            }
        )
        existing.add(mid)
        notes.append(f"noun_expand: added {mid} for uncovered '{noun}'")
    return notes


__all__ = [
    "extract_prompt_nouns",
    "domain_noun_coverage",
    "expand_uncovered_noun_models",
]
