"""Stock Odoo model catalog — full instance surface for manual + AI reuse."""

from __future__ import annotations

import re
from typing import Any, Protocol

from app.ai_stock_reuse import _LINK_ONLY_MODELS

STOCK_CATALOG_LIMIT = 2000
PROMPT_MODEL_LIMIT = 400
CATALOG_INFER_MAX = 15
CATALOG_INFER_MIN_SCORE = 2

# Models that exist on every Odoo instance — always safe to suggest offline.
_UNIVERSAL_STOCK = frozenset(
    {
        "res.partner",
        "res.users",
        "res.company",
        "res.country",
        "res.country.state",
        "res.currency",
        "res.lang",
        "ir.attachment",
        "ir.sequence",
    }
)


class _ModelRow(Protocol):
    model: str
    name: str


def is_custom_model(model: str) -> bool:
    return model.startswith("x_")


def is_stock_model(model: str) -> bool:
    """Non-custom model (standard Odoo or third-party module, not x_*)."""
    return bool(model) and not is_custom_model(model)


def model_app_prefix(model: str) -> str:
    return model.split(".", 1)[0]


def is_link_only_model(model: str) -> bool:
    return model in _LINK_ONLY_MODELS


def stock_entry(model: str, name: str) -> dict[str, Any]:
    return {
        "model": model,
        "name": name or model,
        "app": model_app_prefix(model),
        "link_only": is_link_only_model(model),
    }


def entries_from_models(rows: list[_ModelRow]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        mid = str(getattr(row, "model", "") or "")
        if not mid or mid in seen:
            continue
        seen.add(mid)
        label = str(getattr(row, "name", "") or mid)
        out.append(stock_entry(mid, label))
    return out


def filter_stock_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in entries if is_stock_model(str(e.get("model") or ""))]


def load_connection_stock_catalog(
    client: Any,
    *,
    limit: int = STOCK_CATALOG_LIMIT,
) -> dict[str, Any]:
    """Load all models from a connection; split stock vs custom."""
    rows = client.list_models(limit=min(limit, STOCK_CATALOG_LIMIT))
    all_entries = entries_from_models(rows)
    stock = filter_stock_entries(all_entries)
    custom = [e for e in all_entries if is_custom_model(str(e["model"]))]
    return {
        "stock": stock,
        "custom": custom,
        "all": all_entries,
    }


def filter_catalog(
    entries: list[dict[str, Any]],
    *,
    q: str | None = None,
    stock_only: bool = True,
) -> list[dict[str, Any]]:
    out = filter_stock_entries(entries) if stock_only else list(entries)
    needle = (q or "").strip().lower()
    if not needle:
        return out
    filtered: list[dict[str, Any]] = []
    for row in out:
        model = str(row.get("model") or "")
        name = str(row.get("name") or "")
        app = str(row.get("app") or "")
        hay = f"{model} {name} {app}".lower()
        if needle in hay:
            filtered.append(row)
    return filtered


def _prompt_tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text)}


def score_model_for_prompt(model: str, name: str, app: str, tokens: set[str]) -> int:
    if not tokens:
        return 0
    score = 0
    low = " ".join(tokens)
    for part in re.split(r"[._]", model):
        if len(part) >= 3 and part.lower() in tokens:
            score += 3
    for word in re.findall(r"\w{3,}", name.lower()):
        if word in tokens:
            score += 2
    if app.lower() in tokens:
        score += 2
    # Phrase hints (e.g. "sales order" → sale.order)
    if app == "sale" and re.search(r"\b(sales?|order|checkout)\b", low):
        score += 2
    if app == "purchase" and re.search(r"\b(purchase|vendor|supplier|procurement)\b", low):
        score += 2
    if app == "stock" and re.search(r"\b(inventory|warehouse|stock|picking|delivery)\b", low):
        score += 2
    if app == "crm" and re.search(r"\b(crm|lead|pipeline|opportunity)\b", low):
        score += 2
    if app == "mrp" and re.search(r"\b(manufactur|production|bom|work\s*order)\b", low):
        score += 2
    if app == "fleet" and re.search(r"\b(fleet|vehicle)\b", low):
        score += 2
    if app == "helpdesk" and re.search(r"\b(helpdesk|ticket|support)\b", low):
        score += 2
    if app == "project" and re.search(r"\b(project|task|kanban)\b", low):
        score += 2
    if app == "hr" and re.search(r"\b(employee|staff|payroll|hr)\b", low):
        score += 2
    if app == "account" and re.search(r"\b(invoice|billing|accounting|payment)\b", low):
        score += 2
    return score


def rank_stock_models_for_prompt(
    entries: list[dict[str, Any]],
    prompt: str,
    *,
    limit: int = PROMPT_MODEL_LIMIT,
) -> list[str]:
    """Return stock model technical names ranked by prompt relevance."""
    tokens = _prompt_tokens(prompt)
    scored: list[tuple[int, str]] = []
    for row in entries:
        model = str(row.get("model") or "")
        if not is_stock_model(model):
            continue
        name = str(row.get("name") or model)
        app = str(row.get("app") or model_app_prefix(model))
        score = score_model_for_prompt(model, name, app, tokens)
        if model in _UNIVERSAL_STOCK:
            score += 1
        scored.append((score, model))
    scored.sort(key=lambda x: (-x[0], x[1]))
    if tokens:
        top = [m for s, m in scored if s > 0][:limit]
        if top:
            return top
    # No prompt overlap — stable app-grouped sample
    by_app: dict[str, list[str]] = {}
    for row in entries:
        model = str(row.get("model") or "")
        if not is_stock_model(model):
            continue
        by_app.setdefault(model_app_prefix(model), []).append(model)
    flat: list[str] = []
    for app in sorted(by_app):
        flat.extend(sorted(by_app[app]))
    return flat[:limit]


def format_stock_models_for_llm(
    entries: list[dict[str, Any]],
    prompt: str,
    *,
    limit: int = PROMPT_MODEL_LIMIT,
) -> str:
    """Compact grouped block for LLM context."""
    ranked = rank_stock_models_for_prompt(entries, prompt, limit=limit)
    if not ranked:
        return ""
    by_app: dict[str, list[str]] = {}
    name_by_model = {str(e["model"]): str(e.get("name") or e["model"]) for e in entries}
    for model in ranked:
        by_app.setdefault(model_app_prefix(model), []).append(model)
    lines = [
        "Stock Odoo models on this instance (reuse via many2one — do NOT clone as x_* when a row fits):"
    ]
    for app in sorted(by_app):
        labels = []
        for m in by_app[app][:40]:
            disp = name_by_model.get(m, m)
            labels.append(f"{m} ({disp})" if disp != m else m)
        lines.append(f"[{app}] " + ", ".join(labels))
    if prompt.strip():
        top = ranked[:25]
        lines.append(
            "Prompt-relevant stock models: "
            + ", ".join(top)
        )
    return "\n".join(lines)


def infer_catalog_reuse(
    user_prompt: str,
    stock_entries: list[dict[str, Any]],
    *,
    available_models: set[str] | None = None,
    installed_modules: set[str] | None = None,
    rejected: set[str] | None = None,
    max_results: int = CATALOG_INFER_MAX,
    min_score: int = CATALOG_INFER_MIN_SCORE,
) -> list[dict[str, Any]]:
    """Lexical match against full stock catalog (connection-aware)."""
    text = (user_prompt or "").strip()
    if not text or not stock_entries:
        return []
    tokens = _prompt_tokens(text)
    if not tokens:
        return []
    skip = rejected or set()
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in stock_entries:
        model = str(row.get("model") or "")
        if not model or model in skip or not is_stock_model(model):
            continue
        name = str(row.get("name") or model)
        app = str(row.get("app") or model_app_prefix(model))
        score = score_model_for_prompt(model, name, app, tokens)
        if score < min_score:
            continue
        if available_models is not None and model not in available_models:
            if installed_modules is None or app not in installed_modules:
                continue
        scored.append(
            (
                score,
                {
                    "model": model,
                    "reason": f"Catalog match: {name}",
                    "source": "catalog",
                    "confirmed": False,
                    "forbid_parallel": [],
                    "link_only": bool(row.get("link_only"))
                    or is_link_only_model(model),
                    "modules": (app,),
                },
            )
        )
    scored.sort(key=lambda x: (-x[0], x[1]["model"]))
    return [row for _, row in scored[:max_results]]


__all__ = [
    "STOCK_CATALOG_LIMIT",
    "PROMPT_MODEL_LIMIT",
    "load_connection_stock_catalog",
    "filter_catalog",
    "filter_stock_entries",
    "is_stock_model",
    "is_custom_model",
    "rank_stock_models_for_prompt",
    "format_stock_models_for_llm",
    "infer_catalog_reuse",
    "stock_entry",
]
