"""Deterministic Expert fallbacks when RAG retrieval is thin."""

from __future__ import annotations

import re
from typing import Any

from app.expert.grounding import GroundingBundle
from app.protected_modules import safe_alternative_for

_BULK_QUESTION_RE = re.compile(
    r"(?i)\b("
    r"bulk|mass edit|many records|duplicate|dedupe|transition|recompute|"
    r"bulk suite|bulk rpc|housekeeping"
    r")\b"
)

_FIELD_TYPE_QUESTION_RE = re.compile(
    r"(?i)\b("
    r"many2one|many2many|one2many|field type|computed field|related field|"
    r"stored field|onchange|domain filter"
    r")\b"
)

_FIELD_TYPE_ANSWERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)many2one.*many2many|many2many.*many2one|versus|vs\.?|difference"),
        (
            "**Many2one** links one record on this model to a single related record "
            "(foreign key). **Many2many** links multiple records through a relation table.\n\n"
            "Use many2one for a single owner, customer, or parent; use many2many for tags, "
            "shared categories, or multi-select relationships."
        ),
    ),
    (
        re.compile(r"(?i)computed.*stored|stored.*computed|store=true"),
        (
            "Computed fields can set **`store=True`** to persist values in the database, "
            "which enables searching and grouping. Without `store=True`, values are computed "
            "on the fly and not searchable via domain filters."
        ),
    ),
    (
        re.compile(r"(?i)related field|related="),
        (
            "A **related field** mirrors a field on a linked record using a dotted path "
            "(e.g. `partner_id.email`). It avoids duplicating data and stays read-only unless "
            "`readonly=False` with an inverse is configured."
        ),
    ),
    (
        re.compile(r"(?i)onchange"),
        (
            "**Onchange** methods (`@api.onchange`) update form UI client-side before save. "
            "Use them for UX hints and defaults — not for durable business invariants "
            "(use constraints, automations, or write logic instead)."
        ),
    ),
    (
        re.compile(r"(?i)domain filter|act_window.*domain"),
        (
            "**Domain filters** on `ir.actions.act_window` use Polish notation lists "
            "(e.g. `[('state', '=', 'draft')]`) to restrict records shown in list/form views."
        ),
    ),
)


def try_rule_based_bulk_routing(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    """Answer bulk-suite routing questions from grounded tool links."""
    del client
    tools = list(bundle.suggested_tools or [])
    if not tools or not _BULK_QUESTION_RE.search(question):
        return None

    lines = [
        "Use the **Bulk Suite** tools on this connection (safe bulk RPC with operator review):"
    ]
    for idx, tool in enumerate(tools, start=1):
        label = tool.get("label") or tool.get("id") or "Tool"
        link = tool.get("deep_link") or ""
        hint = tool.get("hint") or ""
        bit = f" — {hint}" if hint else ""
        if link:
            lines.append(f"{idx}. **{label}**: `{link}`{bit}")
        else:
            lines.append(f"{idx}. **{label}**{bit}")

    if connection_id:
        lines.append(
            f"\nOpen `/connections/{connection_id}/bulk-suite` from the connection sidebar."
        )

    return {
        "answer_markdown": "\n".join(lines),
        "grounded": bool(connection_id),
        "caution_flags": ["rule_based_bulk_routing"],
    }


def try_rule_based_field_type_guidance(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    """Answer common Odoo field-type questions without doc retrieval."""
    del connection_id, client
    if not _FIELD_TYPE_QUESTION_RE.search(question):
        return None

    for pattern, answer in _FIELD_TYPE_ANSWERS:
        if pattern.search(question):
            return {
                "answer_markdown": answer,
                "grounded": bool(bundle.instance_summary),
                "caution_flags": ["rule_based_field_guidance"],
            }
    return None


def try_rule_based_protected_guidance(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    """Link-only guidance for tier-1 protected models when retrieval is thin."""
    del client
    flags = list(bundle.protected_flags or [])
    if not flags:
        return None

    q = question.lower()
    if not re.search(r"(?i)(invoice|account\.move|relate|link|many2one|safe|protected|tier)", q):
        return None

    lines = [
        "Protected tier-1 models on your connection require **link-only** customization "
        "from custom models — do not mutate core accounting logic via metadata or ad-hoc code."
    ]
    for flag in flags[:4]:
        model = str(flag.get("model") or "")
        tier = str(flag.get("tier") or "protected")
        alt = str(flag.get("safe_alternative") or safe_alternative_for(model))
        lines.append(f"- **`{model}`** ({tier}): {alt}")

    if connection_id:
        lines.append(
            f"\nUse `/connections/{connection_id}/builder` to add many2one links from your "
            "`x_*` models without touching tier-1 write paths."
        )

    return {
        "answer_markdown": "\n".join(lines),
        "grounded": True,
        "caution_flags": [f"protected_{f.get('tier')}:{f.get('model')}" for f in flags[:4]]
        + ["rule_based_protected_guidance"],
    }
