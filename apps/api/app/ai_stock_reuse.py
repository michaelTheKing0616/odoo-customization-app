"""Deterministic noun → stock Odoo model inference (GEN-6)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.ai_domain_nouns import extract_prompt_nouns

# Tier-1 / protected targets — link-only (m2o), never mutation automations.
_LINK_ONLY_MODELS = frozenset(
    {
        "account.move",
        "account.payment",
        "sale.order",
        "purchase.order",
        "stock.picking",
        "stock.quant",
        "stock.warehouse",
    }
)


@dataclass(frozen=True)
class StockNounRule:
    nouns: tuple[str, ...]
    models: tuple[str, ...]
    modules: tuple[str, ...]
    reason: str
    forbid_parallel: tuple[str, ...] = ()
    link_only: bool = False
    also_match: re.Pattern[str] | None = None


STOCK_NOUN_RULES: tuple[StockNounRule, ...] = (
    StockNounRule(
        ("product", "sku", "catalog", "grocery", "merchandise", "supermarket", "store"),
        ("product.template", "product.product"),
        ("product",),
        "Products / catalog",
        forbid_parallel=("x_product", "x_product_template", "x_sku"),
        also_match=re.compile(r"\b(super[\s-]?market|grocery)\b", re.I),
    ),
    StockNounRule(
        ("supplier", "vendor", "procurement"),
        ("res.partner", "purchase.order"),
        ("purchase", "contacts"),
        "Suppliers and purchase orders",
        forbid_parallel=("x_supplier", "x_vendor"),
        link_only=True,
        also_match=re.compile(r"\b(purchase|procurement|replenish)\b", re.I),
    ),
    StockNounRule(
        ("staff", "employee", "cashier", "roster"),
        ("hr.employee",),
        ("hr",),
        "Staff / employees",
        forbid_parallel=("x_employee", "x_staff"),
    ),
    StockNounRule(
        ("inventory", "stock", "warehouse", "replenish"),
        ("stock.warehouse", "stock.quant"),
        ("stock",),
        "Inventory / warehouse (link-only)",
        forbid_parallel=("x_warehouse", "x_stock_location"),
        link_only=True,
    ),
    StockNounRule(
        ("invoice", "billing"),
        ("account.move",),
        ("account",),
        "Invoices / bills (link-only)",
        forbid_parallel=("x_invoice", "x_bill"),
        link_only=True,
    ),
    StockNounRule(
        ("sale", "order", "checkout"),
        ("sale.order",),
        ("sale",),
        "Sales orders (link-only)",
        forbid_parallel=("x_sale_order",),
        link_only=True,
        also_match=re.compile(r"\bsales?\s+order\b", re.I),
    ),
    StockNounRule(
        ("expense", "reimburse"),
        ("hr.expense",),
        ("hr_expense",),
        "Employee expenses",
        forbid_parallel=("x_expense",),
    ),
    StockNounRule(
        ("event", "appointment", "schedule"),
        ("calendar.event",),
        ("calendar",),
        "Calendar events / appointments",
        forbid_parallel=("x_event", "x_appointment"),
    ),
)


def _load_ce_modules() -> frozenset[str]:
    from app.protected_modules import load_vendored_community_modules

    return frozenset(load_vendored_community_modules("19.0"))


def _rule_matches(rule: StockNounRule, nouns: set[str], text: str) -> bool:
    low = text.lower()
    if any(n in nouns for n in rule.nouns):
        return True
    for noun in rule.nouns:
        if re.search(rf"\b{re.escape(noun)}\b", low):
            return True
    if rule.also_match and rule.also_match.search(text):
        return True
    return False


def infer_stock_reuse(
    user_prompt: str,
    *,
    available_models: list[str] | None = None,
    installed_modules: list[str] | None = None,
    pack_reuse_stock: list[dict[str, Any]] | None = None,
    rejected_models: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (inferred decision dicts, notes). Each decision has confirmed=False."""
    text = (user_prompt or "").strip()
    if not text:
        return [], []
    nouns = set(extract_prompt_nouns(text))
    available = set(available_models) if available_models is not None else None
    modules = set(installed_modules) if installed_modules else None
    connection = available is not None or modules is not None
    ce_modules = _load_ce_modules()
    rejected = set(rejected_models or [])
    notes: list[str] = []
    decisions: list[dict[str, Any]] = []
    seen_models: set[str] = set()

    def add_decision(
        model: str,
        *,
        reason: str,
        rule_modules: tuple[str, ...],
        forbid_parallel: tuple[str, ...],
        link_only: bool,
        source_tag: str = "inferred",
    ) -> None:
        if model in rejected:
            notes.append(
                f"reuse: skipped {model} (operator chose custom x_ model)"
            )
            return
        if model in seen_models:
            return
        installed = False
        installable = False
        if modules is not None:
            installed = any(m in modules for m in rule_modules)
        if available is not None and model in available:
            installed = True
        if not installed and rule_modules:
            installable = any(m in ce_modules for m in rule_modules)
        if connection:
            if installed:
                seen_models.add(model)
                decisions.append(
                    {
                        "model": model,
                        "reason": reason,
                        "source": source_tag,
                        "confirmed": False,
                        "forbid_parallel": list(forbid_parallel),
                        "link_only": link_only or model in _LINK_ONLY_MODELS,
                    }
                )
            elif installable:
                mod = rule_modules[0]
                seen_models.add(model)
                decisions.append(
                    {
                        "model": model,
                        "reason": reason,
                        "source": "installable",
                        "module": mod,
                        "confirmed": False,
                        "forbid_parallel": list(forbid_parallel),
                        "link_only": link_only or model in _LINK_ONLY_MODELS,
                    }
                )
                notes.append(
                    f"reuse: {model} available via module '{mod}' — "
                    f"install and reuse vs generate custom x_ model"
                )
            else:
                notes.append(
                    f"reuse: {model} not on instance — will generate custom model if needed"
                )
        else:
            seen_models.add(model)
            decisions.append(
                {
                    "model": model,
                    "reason": f"{reason} (offline — confirm on connection)",
                    "source": source_tag,
                    "confirmed": False,
                    "forbid_parallel": list(forbid_parallel),
                    "link_only": link_only or model in _LINK_ONLY_MODELS,
                }
            )

    # Domain-pack stock first — pack metadata wins over noun inference for the same model.
    for row in pack_reuse_stock or []:
        if not isinstance(row, dict) or not row.get("model"):
            continue
        mid = str(row["model"])
        mods = tuple(str(m) for m in (row.get("modules") or []) if m)
        add_decision(
            mid,
            reason=str(row.get("reason") or "Domain pack stock reuse"),
            rule_modules=mods or ("product",),
            forbid_parallel=tuple(str(x) for x in (row.get("forbid_parallel") or [])),
            link_only=bool(row.get("link_only")),
            source_tag="pack_reuse_stock",
        )

    for rule in STOCK_NOUN_RULES:
        if not _rule_matches(rule, nouns, text):
            continue
        for model in rule.models:
            add_decision(
                model,
                reason=rule.reason,
                rule_modules=rule.modules,
                forbid_parallel=rule.forbid_parallel,
                link_only=rule.link_only,
            )

    return decisions, notes


__all__ = [
    "STOCK_NOUN_RULES",
    "infer_stock_reuse",
    "_LINK_ONLY_MODELS",
]
