"""Rule-based view inheritance / xpath guidance when retrieval+LLM would misfire."""

from __future__ import annotations

import re
from typing import Any

from app.expert.grounding import GroundingBundle

_VIEW_TOPIC_RE = re.compile(
    r"(?i)\b("
    r"xpath|view inherit|inheritance|ir\.ui\.view|form view|list view|"
    r"position=|anchor node|studio|readonly|attrs=|arch\b"
    r")\b"
)

_XPATH_INTENT_RE = re.compile(
    r"(?i)\b("
    r"xpath|position should|what position|below|after|before|inside|replace|"
    r"anchor|failure mode|missing.*node|inherit"
    r")\b"
)

_FIELD_ANCHOR_RE = re.compile(
    r"(?i)(?:field\s+)?[@\']?name['\"]?\s*=\s*['\"]([a-z_][a-z0-9_]*)['\"]|"
    r"\b([a-z_][a-z0-9_]{2,}_id)\b"
)

_MODEL_HINT_RE = re.compile(
    r"(?i)\b(sale\.order|sale order|res\.partner|partner_id|account\.move|project\.task)\b"
)


def looks_like_view_inheritance_question(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    if not (_VIEW_TOPIC_RE.search(text) and _XPATH_INTENT_RE.search(text)):
        return False
    # Concrete placement / anchor / failure-mode asks — not generic "what is xpath?"
    if re.search(
        r"(?i)\b(failure mode|anchor node|anchor|below|above|position should|"
        r"partner_id|field\[@name|readonly|char field|without breaking)\b",
        text,
    ):
        return True
    return bool(
        re.search(r"(?i)\bxpath\b", text)
        and re.search(r"(?i)\b(add|insert|extend|inherit)\b", text)
        and re.search(r"(?i)\b(field|form view|sale order|partner_id)\b", text)
    )


def _anchor_field(question: str) -> str:
    for match in _FIELD_ANCHOR_RE.finditer(question):
        field = match.group(1) or match.group(2)
        if field and field not in {"char", "field", "readonly"}:
            return field
    if re.search(r"(?i)\bpartner_id\b", question):
        return "partner_id"
    return "partner_id"


def _host_model(question: str) -> str:
    if re.search(r"(?i)\bsale\.order|sale order", question):
        return "sale.order"
    if re.search(r"(?i)\bres\.partner|\bpartner form", question):
        return "res.partner"
    if re.search(r"(?i)\baccount\.move|invoice form", question):
        return "account.move"
    return "the target model"


def try_rule_based_view_guidance(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    del client
    if not looks_like_view_inheritance_question(question):
        return None

    anchor = _anchor_field(question)
    model = _host_model(question)
    placement = "after"
    if re.search(r"(?i)\bbelow\b", question):
        placement = "after"
    elif re.search(r"(?i)\babove\b", question):
        placement = "before"

    lines = [
        f"To add a readonly `x_contract_ref` char on **`{model}`** immediately **{placement}** "
        f"**`{anchor}`** without replacing the parent arch, inherit the form view and use **xpath** "
        f"with **`position=\"{placement}\"`**:",
        "",
        "```xml",
        f'<xpath expr="//field[@name=\'{anchor}\']" position="{placement}">',
        '  <field name="x_contract_ref" readonly="1"/>',
        "</xpath>",
        "```",
        "",
        "**Recommended `position` values:**",
        f"- **`after`** — insert your field directly below `{anchor}` (best match for “below partner_id”).",
        "- **`before`** — insert above the anchor.",
        "- **`inside`** — append inside the anchor element (useful for groups, not usually for fields).",
        "- **`attributes`** — tweak attrs on the anchor (readonly/invisible) without adding siblings.",
        "",
        "**Failure modes when the anchor is missing (Odoo 19):**",
        f"1. **View validation error on upgrade/install** — if `//field[@name='{anchor}']` matches "
        "nothing in the combined inherited arch, Odoo rejects the view.",
        "2. **Silent no-op** — rare on strict validation, but a wrong inherit target or inactive "
        "parent view can make your xpath apply to an unexpected form variant.",
        "3. **Studio / third-party inherit chain** — another module may have renamed, moved, or "
        f"replaced `{anchor}`; your xpath must target a node that exists in **your** instance's "
        "effective arch (check via Developer Mode → Edit View: Architecture).",
        "4. **Priority conflicts** — lower-priority inheriting views run earlier; a later view can "
        "still break if it assumes your new field exists — keep inherit order and `priority` sane.",
        "",
        "**Practical checks on your connection:**",
        f"1. Open the `{model}` form in Odoo → Developer tools → **Edit View: Form** and confirm "
        f"`{anchor}` exists in the effective arch.",
        "2. In this app, inherit `sale.view_order_form` (or the active form xml id) in **Designer** "
        "and save with standard write mode enabled.",
        "3. If Studio customized the form, inherit the **same** base view the Studio view extends — "
        "do not xpath against nodes Studio removed.",
    ]

    if connection_id:
        lines.append(
            f"\nBuilder: `/connections/{connection_id}/designer?model={model}` — add the field, "
            "then inspect generated xpath before promote."
        )

    return {
        "answer_markdown": "\n".join(lines),
        "grounded": bool(connection_id and bundle.instance_summary),
        "caution_flags": ["rule_based_view_guidance"],
    }
