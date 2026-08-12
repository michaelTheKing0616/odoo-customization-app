"""Rule-based stock model name lookup when RAG retrieval is thin."""

from __future__ import annotations

import re
from typing import Any

from app.ai_grain import HOST_ALIASES, HOST_LABELS, module_for_model
from app.ai_stock_catalog import _UNIVERSAL_STOCK
from app.expert.grounding import GroundingBundle

_MODEL_QUESTION_RE = re.compile(
    r"(?i)\b("
    r"what(?:'s|\s+is)\s+(?:the\s+)?(?:model|technical\s+name|orm\s+model)"
    r"|model\s+(?:for|of|name\s+for)"
    r"|which\s+model"
    r"|called\s+in\s+odoo"
    r"|technical\s+name"
    r")\b"
)

_EXTRA_ALIASES: dict[str, str] = {
    "invoice": "account.move",
    "invoices": "account.move",
    "bill": "account.move",
    "bills": "account.move",
    "journal entry": "account.move",
    "product": "product.product",
    "products": "product.product",
    "employee": "hr.employee",
    "employees": "hr.employee",
    "user": "res.users",
    "users": "res.users",
    "company": "res.company",
    "companies": "res.company",
    "sales order": "sale.order",
    "sale order": "sale.order",
    "purchase order": "purchase.order",
    "lead": "crm.lead",
    "leads": "crm.lead",
    "opportunity": "crm.lead",
    "project": "project.project",
    "task": "project.task",
    "picking": "stock.picking",
    "delivery": "stock.picking",
}


def _alias_map() -> dict[str, str]:
    merged = dict(HOST_ALIASES)
    merged.update(_EXTRA_ALIASES)
    return merged


def looks_like_model_name_question(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    if not _MODEL_QUESTION_RE.search(text):
        return False
    # Must mention a mappable business noun — not ir.model.access / "in order does".
    if _match_alias(text) is None:
        return False
    if looks_like_access_rights_question(text):
        return False
    return True


def looks_like_access_rights_question(question: str) -> bool:
    """Imported lazily to avoid circular imports in tests."""
    from app.expert.access_guidance import looks_like_access_rights_question as _check

    return _check(question)


def _match_alias(text: str) -> tuple[str, str] | None:
    lowered = text.lower()
    # Skip "order" when used as English ordering, not sale.order.
    if re.search(r"(?i)\b(in what order|what order|evaluation order|in order)\b", lowered):
        lowered = lowered.replace("order", "\x00")
    for phrase, model in sorted(_alias_map().items(), key=lambda item: -len(item[0])):
        if phrase in lowered:
            return phrase, model
    return None


def try_rule_based_model_lookup(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    """Return answer fields for common stock model name questions."""
    del connection_id  # reserved for future instance-specific labels
    if not looks_like_model_name_question(question):
        return None

    hit = _match_alias(question)
    if not hit:
        return None

    phrase, model = hit
    label = HOST_LABELS.get(model, model.split(".")[-1].replace("_", " ").title())
    module = module_for_model(model)

    verified = False
    if client is not None and hasattr(client, "model_exists"):
        try:
            verified = bool(client.model_exists(model))
        except Exception:  # noqa: BLE001 — optional live check
            verified = False

    instance_note = ""
    if verified:
        instance_note = " I confirmed this model exists on your connected instance."
    elif bundle.instance_summary:
        instance_note = " This is standard Odoo Community metadata (not instance-specific)."

    answer = (
        f"In Odoo Community, **{phrase}** uses the technical model **`{model}`** "
        f"(UI label is usually **{label}**; core module **`{module}`**).{instance_note}\n\n"
        f"Extend it with `_inherit = \"{model}\"` in Python, relate via many2one fields, "
        f"or customize views/automations on `{model}` in the Builder."
    )

    return {
        "answer_markdown": answer,
        "grounded": verified or model in _UNIVERSAL_STOCK or bool(bundle.instance_summary),
        "caution_flags": ["rule_based_model_lookup"],
    }
