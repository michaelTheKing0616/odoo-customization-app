"""Rule-based guidance for required fields and existing-record constraints."""

from __future__ import annotations

import re
from typing import Any

from app.expert.grounding import GroundingBundle

_REQUIRED_FIELD_RE = re.compile(
    r"(?i)\b("
    r"required\s+many2one|required\s+field|without setting a default|without a default|"
    r"existing records|module install|view save|will.*block"
    r")\b"
)

_MANY2ONE_RE = re.compile(r"(?i)\bmany2one\b")

_WHAT_IF_RE = re.compile(
    r"(?i)\b(what happens if|will existing|block module|block.*install|block.*save)\b"
)


def looks_like_required_field_question(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    if not _REQUIRED_FIELD_RE.search(text):
        return False
    return bool(_MANY2ONE_RE.search(text) or _WHAT_IF_RE.search(text))


def _extract_models(question: str) -> tuple[str, str]:
    """Best-effort source → comodel from question text."""
    src = "your model"
    comodel = "res.users"
    x_models = re.findall(r"\b(x_[a-z][a-z0-9_]*)\b", question, re.I)
    if x_models:
        src = x_models[0].lower()
    m2o = re.search(
        r"(?i)(?:from|on)\s+(x_[a-z][a-z0-9_]*)\s*(?:→|->|to)\s*(res\.[a-z][a-z0-9_]*)",
        question,
    )
    if m2o:
        src, comodel = m2o.group(1).lower(), m2o.group(2).lower()
    else:
        comodel_match = re.search(r"\b(res\.[a-z][a-z0-9_]*)\b", question, re.I)
        if comodel_match:
            comodel = comodel_match.group(1).lower()
    return src, comodel


def try_rule_based_required_field_guidance(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    del client
    if not looks_like_required_field_question(question):
        return None

    src, comodel = _extract_models(question)
    field_name = "x_assignee_id" if "user" in comodel else "x_link_id"

    lines = [
        f"Adding a **required Many2one** on **`{src}`** → **`{comodel}`** **without a default** "
        "behaves differently depending on whether rows already exist and which path creates the column.",
        "",
        "**When dependencies are met** (model exists, comodel exists, user has write access):",
        "",
        f"1. **Empty table (no rows on `{src}` yet)** — install / metadata save usually succeeds. "
        "PostgreSQL adds a nullable FK column first; Odoo enforces `required` at the **ORM/form** "
        "layer on create/write. Existing-record pressure is low.",
        "",
        "2. **Table already has rows** — this is where it breaks:",
        "   - **Module `-i` / column add with `NOT NULL` and no default** → database migration "
        "error (`column contains null values`) unless Odoo/your module supplies a default or "
        "staged migration.",
        "   - **Metadata save in Designer / Models & Fields** — Odoo typically **blocks** marking "
        "the field required until you provide a **default** or backfill existing rows (platform UI "
        "may prompt for a default value).",
        "   - **View save alone** does not create the required constraint on the column — but the "
        "form will refuse create/save when the required field is empty.",
        "",
        "3. **Existing records do not auto-block module install** if the field is added as "
        "nullable first and required only at UI/ORM level — but they **will block** promoting a "
        "DB-level NOT NULL without backfill.",
        "",
        "**Recommended safe sequence:**",
        f"1. Add optional Many2one `{field_name}` → `{comodel}` on `{src}`.",
        "2. Backfill existing rows (Bulk Suite or server action) if any exist.",
        "3. Set `required=True` (and optionally `ondelete` policy) once every row has a value.",
        "",
        "**View save vs module install:** view XML can show the field as required in the form "
        "(`required=\"1\"`) even when the field definition is not required — that affects UI "
        "validation only. Module/field metadata `required=True` affects ORM create/write.",
    ]

    if connection_id:
        lines.append(
            f"\nBuilder: `/connections/{connection_id}/designer?model={src}` — add the field "
            "optional first, backfill, then toggle required."
        )

    return {
        "answer_markdown": "\n".join(lines),
        "grounded": bool(connection_id and bundle.instance_summary),
        "caution_flags": ["rule_based_required_field_guidance"],
    }
