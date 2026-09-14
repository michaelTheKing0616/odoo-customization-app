"""Deterministic prompt-noun coverage — no LLM required (GEN-2)."""

from __future__ import annotations

import re
from typing import Any

from app.ai_post_critique import NOUN_STOPWORDS as _STOPWORDS

# Nouns that are too generic to require a dedicated model when alone.
_GENERIC_NOUNS = frozenset(
    {
        "order",
        "item",
        "line",
        "record",
        "data",
        "user",
        "company",
        "code",
        "click",
        "button",
        "directly",
        "dynamic",
        "pdf",
        "print",
        "extra",
        "extras",
    }
)

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
    "attorney": "hr.employee",
    "lawyer": "hr.employee",
    "counsel": "hr.employee",
    "invoice": "account.move",
    "quotation": "sale.order",
    "user": "res.users",
    "company": "res.company",
    "product": "product.product",
}

# Prompt spelling / near-synonyms → model-leaf tokens (artiste → x_artist).
_NOUN_SYNONYMS: dict[str, str] = {
    "artiste": "artist",
    "recording": "studio",
    "booth": "studio",
    "host": "employee",
}


def noun_search_tokens(noun: str) -> set[str]:
    """Tokens that count as covering `noun` (canonical + aliases)."""
    raw = str(noun or "").strip().lower()
    if not raw:
        return set()
    tokens = {raw, _NOUN_SYNONYMS.get(raw, raw)}
    for alias, target in _NOUN_SYNONYMS.items():
        if raw == target:
            tokens.add(alias)
    return {t for t in tokens if t}


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
    # Markdown headings ("## Goal", "# Operator brief") are chrome, not domain nouns.
    body = "\n".join(
        ln
        for ln in user_prompt.splitlines()
        if not re.match(r"^#{1,3}\s+", ln.strip())
    )
    tokens = re.findall(r"[a-zA-Z']+", (body or user_prompt).lower())
    out: list[str] = []
    seen: set[str] = set()
    for raw in tokens:
        parts = [p for p in re.split(r"['’]+", raw) if p]
        for tok in parts:
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
    cp = draft.get("connect_points") if isinstance(draft.get("connect_points"), dict) else {}
    parts: list[str] = [
        str(draft.get("display_name") or ""),
        str(cp.get("host_model") or ""),
        str(cp.get("host_label") or ""),
    ]
    for m in draft.get("models") or []:
        if not isinstance(m, dict):
            continue
        parts.append(str(m.get("model") or ""))
        parts.append(str(m.get("description") or ""))
        parts.append(str(m.get("inherit") or ""))
        for f in m.get("fields") or []:
            if isinstance(f, dict):
                parts.append(str(f.get("string") or ""))
                parts.append(str(f.get("name") or ""))
                parts.append(str(f.get("relation") or ""))
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
    for branch_model in ("x_branch", "x_og_facility"):
        for m in draft.get("models") or []:
            if not isinstance(m, dict) or str(m.get("model") or "") != branch_model:
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
    candidates = noun_search_tokens(noun)
    for cand in candidates:
        if cand in blob:
            return True
        if cand.endswith("y") and f"{cand[:-1]}i" in blob:
            return True
    reuse = list(reuse_models or [])
    if not reuse:
        reuse_block = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
        reuse = [str(m) for m in (reuse_block.get("models") or []) if m]
        for hint in draft.get("reuse_hints") or []:
            if isinstance(hint, dict) and hint.get("model"):
                reuse.append(str(hint["model"]))
    mapped = _REUSE_NOUN_MAP.get(noun) or next(
        (_REUSE_NOUN_MAP[c] for c in candidates if c in _REUSE_NOUN_MAP),
        None,
    )
    known_models = {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    if mapped and mapped in known_models:
        return True
    if mapped and mapped in reuse:
        return True
    # Contacts/customer covered by any res.partner M2O on the residual.
    if noun in {"contact", "customer", "client", "partner", "vendor", "supplier"}:
        for model in draft.get("models") or []:
            if not isinstance(model, dict):
                continue
            for field in model.get("fields") or []:
                if isinstance(field, dict) and field.get("relation") == "res.partner":
                    return True
        if "res.partner" in reuse or "contacts" in {
            str(d).lower() for d in (draft.get("depends") or [])
        }:
            return True
    if noun in {"alert", "activity", "deadline", "mail", "notification", "notifications"}:
        depends = {str(d).lower() for d in (draft.get("depends") or [])}
        if "mail" in depends:
            return True
        for model in draft.get("models") or []:
            if not isinstance(model, dict):
                continue
            mixins = {str(x) for x in (model.get("mixins") or [])}
            if mixins & {"mail.thread", "mail.activity.mixin"}:
                return True
        for auto in draft.get("automations") or []:
            if not isinstance(auto, dict):
                continue
            trig = str(auto.get("trigger") or auto.get("trg") or "")
            if trig == "on_time":
                return True
            for act in auto.get("safe_actions") or []:
                if isinstance(act, dict) and act.get("kind") in {
                    "next_activity",
                    "mail_post",
                }:
                    return True
    for rm in reuse:
        leaf = rm.split(".")[-1].replace("_", " ")
        low = rm.lower()
        if any(c in leaf or c in low for c in candidates):
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
    extra_stop: set[str] = set()
    brief = draft.get("_operator_brief") if isinstance(draft.get("_operator_brief"), dict) else {}
    scope = " ".join(str(x) for x in (brief.get("out_of_scope") or [])).lower()
    if "python" in scope:
        extra_stop.add("python")
    for item in list(brief.get("out_of_scope") or []) + list(brief.get("forbidden_bridges") or []):
        for tok in re.findall(r"[a-zA-Z']+", str(item).lower()):
            lemma = _lemmatize(tok)
            if len(lemma) >= 3:
                extra_stop.add(lemma)
                extra_stop.add(tok)
    if extra_stop & {"invoicing", "invoice", "invoices", "account"}:
        extra_stop.update({"invoice", "invoices", "invoicing"})
    country = str(brief.get("country") or "").strip().lower()
    if country:
        extra_stop.update(country.split())
    from app.ai_operator_brief import gazetteer_place_tokens

    extra_stop.update(gazetteer_place_tokens())
    # Lemmatizer turns Lagos → lago; keep place stems out of domain_fit.
    for place in list(gazetteer_place_tokens()):
        if place.endswith("s") and len(place) > 3:
            extra_stop.add(place[:-1])
    key_nouns = [
        n
        for n in nouns
        if n not in _GENERIC_NOUNS and n not in extra_stop and len(n) >= 4
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
    "noun_search_tokens",
]
