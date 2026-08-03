"""Grain classification + host discovery for component-grain AI (AI-8)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

Grain = Literal["field_pack", "feature_slice", "full_app"]

# Depth floors scaled to grain — field_pack gets minimal scaffolding.
GRAIN_TARGETS: dict[Grain, dict[str, float]] = {
    "field_pack": {
        "min_models": 0,
        "min_fields_avg": 1,
        "min_m2o": 0,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 0,
        "max_entities_staged": 2,
        "allow_root_menu": 0,
        "allow_new_app": 0,
    },
    "feature_slice": {
        "min_models": 0,
        "min_fields_avg": 2,
        "min_m2o": 0,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 0,
        "max_entities_staged": 4,
        "allow_root_menu": 0,
        "allow_sub_menu": 1,
    },
    "full_app": {
        "min_models": 2,
        "min_fields_avg": 3,
        "min_m2o": 1,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 0,
        "max_entities_staged": 6,
        "allow_root_menu": 1,
        "allow_new_app": 1,
    },
}

_COMPONENT_RE = re.compile(
    r"\b("
    r"add(?:\s+a|\s+an|\s+the|\s+my)?|attach|extend|plug(?:\s+into)?|"
    r"on\s+(?:my\s+)?(?:sale|sales|order|orders|task|tasks|project|contact|partner|customer)s?|"
    r"to\s+(?:my\s+)?(?:sale|sales|order|orders|task|tasks|project|contact|partner|customer)s?|"
    r"tracker|checklist|warranty|inspection|compliance|expiry|component"
    r")\b",
    re.I,
)

_FULL_APP_RE = re.compile(
    r"\b("
    r"build\s+(?:an?\s+)?app|create\s+(?:an?\s+)?app|full\s+app|standalone|"
    r"new\s+application|from\s+scratch|entire\s+system|complete\s+platform|"
    r"library\s+management|car\s+rental|law\s+firm|hospital|clinic"
    r")\b",
    re.I,
)

_FIELD_PACK_RE = re.compile(
    r"\b(add\s+(?:a\s+)?field|single\s+field|just\s+(?:a\s+)?field|track\s+\w+\s+on)\b",
    re.I,
)

HOST_ALIASES: dict[str, str] = {
    "sale order": "sale.order",
    "sale orders": "sale.order",
    "sales order": "sale.order",
    "sales orders": "sale.order",
    "order": "sale.order",
    "orders": "sale.order",
    "quotation": "sale.order",
    "sales": "sale.order",
    "project task": "project.task",
    "project tasks": "project.task",
    "task": "project.task",
    "tasks": "project.task",
    "contact": "res.partner",
    "contacts": "res.partner",
    "partner": "res.partner",
    "partners": "res.partner",
    "customer": "res.partner",
    "customers": "res.partner",
}

MODEL_MODULE: dict[str, str] = {
    "sale.order": "sale",
    "project.task": "project",
    "res.partner": "base",
    "account.move": "account",
    "purchase.order": "purchase",
    "stock.picking": "stock",
}

INHERIT_FORM_XML: dict[str, str] = {
    "sale.order": "sale.view_order_form",
    "project.task": "project.view_task_form2",
    "res.partner": "base.view_partner_form",
}

HOST_LABELS: dict[str, str] = {
    "sale.order": "Sales",
    "project.task": "Project",
    "res.partner": "Contacts",
}


@dataclass
class HostCandidate:
    model: str
    label: str
    score: float
    module: str
    reason: str


def classify_grain(prompt: str) -> Grain:
    """Classify prompt grain: field_pack | feature_slice | full_app."""
    text = (prompt or "").strip().lower()
    if not text:
        return "full_app"
    if _FULL_APP_RE.search(text):
        return "full_app"
    if _FIELD_PACK_RE.search(text) and not _COMPONENT_RE.search(text):
        return "field_pack"
    if _COMPONENT_RE.search(text):
        if _FIELD_PACK_RE.search(text) and len(text.split()) < 12:
            return "field_pack"
        return "feature_slice"
    if re.search(r"\bmanage|management|system|platform|workflow|inventory\b", text):
        return "full_app"
    return "full_app"


def module_for_model(model: str) -> str:
    if model in MODEL_MODULE:
        return MODEL_MODULE[model]
    if model.startswith("x_"):
        return "base"
    parts = model.split(".")
    return parts[0] if parts else "base"


def discover_hosts(
    prompt: str,
    *,
    available_models: list[str] | None = None,
    saved_specs: list[dict[str, Any]] | None = None,
) -> list[HostCandidate]:
    """Rank candidate host models from prompt + introspection."""
    text = (prompt or "").lower()
    catalog = set(available_models or [])
    for spec in saved_specs or []:
        for m in spec.get("models") or []:
            if isinstance(m, dict) and m.get("model"):
                catalog.add(str(m["model"]))

    candidates: list[HostCandidate] = []

    def add(model: str, score: float, reason: str) -> None:
        if catalog and model not in catalog:
            return
        mod = module_for_model(model)
        candidates.append(
            HostCandidate(
                model=model,
                label=HOST_LABELS.get(model, model),
                score=score,
                module=mod,
                reason=reason,
            )
        )

    for phrase, model in HOST_ALIASES.items():
        if phrase in text:
            add(model, 0.95, f"prompt mentions {phrase!r}")

    for model in catalog:
        if not model or model.startswith("ir."):
            continue
        slug = model.replace(".", " ")
        if slug in text or model.replace(".", "_") in text:
            add(model, 0.7, "technical name in prompt")
        if model.startswith("x_") and any(tok in model for tok in text.split() if len(tok) > 3):
            add(model, 0.55, "custom model fuzzy match")

    # Default stock hosts when component phrasing but no explicit host
    if _COMPONENT_RE.search(text):
        for model in ("sale.order", "project.task", "res.partner"):
            if model not in {c.model for c in candidates}:
                add(model, 0.35, "default stock host candidate")

    candidates.sort(key=lambda c: -c.score)
    dedup: dict[str, HostCandidate] = {}
    for c in candidates:
        if c.model not in dedup or c.score > dedup[c.model].score:
            dedup[c.model] = c
    return list(dedup.values())[:8]


def grain_display(grain: Grain, host: HostCandidate | None) -> str:
    if grain == "full_app":
        return "Full app"
    host_part = host.label if host else "host TBD"
    if grain == "field_pack":
        return f"Field pack for {host_part}"
    return f"Component for {host_part}"
