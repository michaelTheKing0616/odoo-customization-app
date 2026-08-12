"""Rule-based guidance: extension inherit vs primary form views."""

from __future__ import annotations

import re
from typing import Any

from app.expert.grounding import GroundingBundle

_VIEW_MODE_TOPIC_RE = re.compile(
    r"(?i)\b("
    r"mode\s*=\s*extension|mode\s*=\s*primary|_inherit|inherit_id|primary form|"
    r"extension view|new primary|ir\.ui\.view"
    r")\b"
)

_VIEW_MODE_INTENT_RE = re.compile(
    r"(?i)\b("
    r"difference|explain|when would|versus|vs\.?|compare|break on upgrade|"
    r"which approach|primary form|extension"
    r")\b"
)

_CUSTOM_MODEL_RE = re.compile(r"\b(x_[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?)\b", re.I)


def looks_like_view_mode_question(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    return bool(_VIEW_MODE_TOPIC_RE.search(text) and _VIEW_MODE_INTENT_RE.search(text))


def _target_model(question: str) -> str:
    for match in _CUSTOM_MODEL_RE.finditer(question):
        token = match.group(1).lower()
        if token not in {"ir.ui.view"}:
            return token
    if re.search(r"(?i)\bsale\.order|sale order", question):
        return "sale.order"
    return "your custom model"


def try_rule_based_view_mode_guidance(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    del client
    if not looks_like_view_mode_question(question):
        return None

    model = _target_model(question)

    lines = [
        "**Extension inherit (`mode=\"extension\"` + `inherit_id`)** patches an existing "
        "view's combined arch. You keep the parent xml id and menu/action wiring; your module "
        "only adds xpath/field nodes. This is the default safe path for Community metadata "
        "customization and Studio-like extensions.",
        "",
        "**Primary form (`mode=\"primary\"`)** creates a new root view for the model. It does "
        "not patch the standard form — it competes to become (or be selected as) the form "
        "view for that model. Use only when you intentionally replace the whole layout or "
        "ship a standalone app UI.",
        "",
        f"For **`{model}`**:",
        "- Prefer **extension** inheriting the active form view (or the Studio parent) when "
        "adding/removing fields or groups.",
        "- Use **primary** only if you own the full form layout and will update actions/menus "
        "to point at your view xml id.",
        "",
        "**When each breaks on upgrade:**",
        "",
        "- **Extension** — parent arch changed upstream: your xpath anchor disappears → "
        "**view validation error** on `-u`. Studio or another module removed/moved the node "
        "you target.",
        "- **Primary** — Odoo or another module still opens the **old** default form action → "
        "users never see your primary view. Duplicate primaries with similar priority cause "
        "unpredictable default selection. Module uninstall can leave orphaned actions.",
        "",
        "**Practical rule:** extend the standard form; avoid new primaries unless you control "
        "the menu/action and accept re-merge work each major upgrade.",
    ]

    if connection_id:
        lines.append(
            f"\nInspect effective views: `/connections/{connection_id}/designer?model={model}` "
            "→ confirm which form xml id is active before choosing inherit target."
        )

    return {
        "answer_markdown": "\n".join(lines),
        "grounded": bool(connection_id and bundle.instance_summary),
        "caution_flags": ["rule_based_view_mode_guidance"],
    }
