"""Rule-based Odoo access-rights guidance (ACL, record rules, field groups)."""

from __future__ import annotations

import re
from typing import Any

from app.expert.grounding import GroundingBundle, extract_model_field_refs, looks_like_rpc_error

_ACCESS_TOPIC_RE = re.compile(
    r"(?i)\b("
    r"accesserror|access error|ir\.model\.access|record rule|ir\.rule|"
    r"access matrix|access rights?|permission|field-level group|groups=|"
    r"can read but|cannot write|not allowed to (?:access|modify|write)"
    r")\b"
)

_EVAL_ORDER_RE = re.compile(
    r"(?i)\b("
    r"what order|in what order|evaluation order|checked first|walk me through"
    r")\b"
)


def looks_like_access_rights_question(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    if _ACCESS_TOPIC_RE.search(text):
        return True
    # RPC logs: only access failures — not view validation / model-not-found noise.
    if looks_like_rpc_error(text) and re.search(
        r"(?i)\b(accesserror|access error|not allowed to (?:access|modify|write|create|delete))\b",
        text,
    ):
        return True
    return False


def _target_models(question: str, bundle: GroundingBundle) -> list[str]:
    models: list[str] = []
    x_write = re.search(r"(?i)\b(?:writing|modify|access)\s+(x_[a-z0-9_]+)\b", question)
    if x_write:
        models.append(x_write.group(1).lower())
    for model, _field in extract_model_field_refs(question):
        if not model or model.startswith("ir."):
            continue
        if model not in models:
            models.append(model)
    ui_model = (bundle.ui_context or {}).get("model")
    if ui_model and str(ui_model) not in models and not str(ui_model).startswith("ir."):
        models.append(str(ui_model))
    return models[:4]


def try_rule_based_access_guidance(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    """Explain ACL vs record rules vs field groups — priority over generic RAG."""
    del client
    if not looks_like_access_rights_question(question):
        return None

    models = _target_models(question, bundle)
    model_hint = models[0] if models else "the model"
    wants_order = bool(_EVAL_ORDER_RE.search(question))

    lines: list[str] = []

    if wants_order:
        lines.extend(
            [
                "Odoo checks permissions in roughly this order for an ORM operation:",
                "",
                "1. **`ir.model.access` (model ACL)** — per group, per model: `perm_read`, "
                "`perm_write`, `perm_create`, `perm_unlink`. If write is off here, you get "
                "**AccessError on every write**, regardless of record rules.",
                "2. **`ir.rule` (record rules)** — domain filters applied per operation "
                "(separate read / write / create / unlink rules). You can **read** rows that "
                "match the read rule but **fail write** on specific records when the write "
                "rule domain excludes them.",
                "3. **Field-level groups & view attrs** — `groups` on fields, `readonly`, "
                "`force_save`, etc. These gate the **UI/form** (what users see or edit). They "
                "are not a substitute for ACL, but a readonly required field can block saving "
                "even when ORM write would otherwise pass.",
            ]
        )
    else:
        lines.append(
            "For **AccessError** issues, check model ACL first, then record rules, then "
            "view field groups/readonly attrs."
        )

    lines.extend(
        [
            "",
            f"**Read works but write fails on `{model_hint}` — usual causes:**",
            f"- Missing **`perm_write`** on `ir.model.access` for the user's groups on `{model_hint}`.",
            f"- A **write record rule** domain on `{model_hint}` that excludes the target row "
            "(read rule is wider than write rule).",
            "- **Multi-company** rules (`company_id` / `company_ids`) hiding or blocking writes.",
            "- Form **readonly** / field `groups` preventing the client from sending the field "
            "(looks like a write failure in the UI).",
        ]
    )

    lines.extend(
        [
            "",
            "**Where to fix (Community, public ORM/RPC):**",
            "1. Odoo → **Settings → Users & Companies → Groups** — confirm the user has a group "
            "with the right access.",
            f"2. Inspect **`ir.model.access`** rows for `{model_hint}` (read/write/create/unlink).",
            f"3. Inspect **`ir.rule`** on `{model_hint}` — compare read vs write domains.",
            "4. In this app → **Access Matrix** on the connection to review/adjust ACLs safely.",
        ]
    )

    if connection_id:
        lines.append(
            f"5. Open `/connections/{connection_id}/access-matrix` and filter to `{model_hint}`."
        )

    return {
        "answer_markdown": "\n".join(lines),
        "grounded": bool(connection_id and bundle.instance_summary),
        "caution_flags": ["rule_based_access_guidance"],
    }
