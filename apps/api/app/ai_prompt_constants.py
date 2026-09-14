"""Doc 4 prompt engineering constants — temperatures, vocab, anti-patterns, exemplar rules."""

from __future__ import annotations

# Per-step temperatures (Doc 4 §5) — single module-level table
TEMP_ENTITIES = 0.6
TEMP_FIELDS = 0.15
TEMP_RELATIONSHIPS = 0.15
TEMP_AUTOMATIONS = 0.6
TEMP_CRITIQUE = 0.15
TEMP_VALIDATION = 0.15  # scaffold-gap repair, field-deepen, depth expand
TEMP_SINGLE_PIPELINE = 0.3

STEP_TEMPERATURES: dict[str, float] = {
    "pipeline.entities": TEMP_ENTITIES,
    "pipeline.fields": TEMP_FIELDS,
    "pipeline.relationships": TEMP_RELATIONSHIPS,
    "pipeline.automations": TEMP_AUTOMATIONS,
    "critique": TEMP_CRITIQUE,
    "quality.scaffold_gap": TEMP_VALIDATION,
    "quality.field_deepen": TEMP_VALIDATION,
    "depth.expand": TEMP_VALIDATION,
    "single_pipeline": TEMP_SINGLE_PIPELINE,
}

# Closed Odoo field ttype vocabulary (Doc 4 §2)
CLOSED_TTYPE_VOCAB = (
    "char|text|html|integer|float|boolean|date|datetime|selection|many2one|one2many|many2many"
)

# Doc 4 §7 anti-pattern block (+ PCM-3 protected one-liner appended at call sites with guardrail)
ANTI_PATTERN_BLOCK = (
    "DO NOT:\n"
    "- Invent ttypes outside the closed vocabulary.\n"
    "- Add many2one/one2many relations to models not listed in the entity/model context.\n"
    "- Name custom fields `id` or `name` without the x_ prefix.\n"
    "- Wrap JSON in markdown or add prose before/after the JSON payload.\n"
    "- Emit hollow catalog models (type/category/tag/stage/priority/status/kind as standalone models).\n"
    "- many2one to pos.order / pos.session: OK only as pick-existing — set field "
    "`options` with no_create + no_create_edit (backend create is blocked by Odoo; "
    "real PoS DBs already have orders to select). Strip pos.order.line / pos.payment "
    "as form FKs. Prefer res.partner + punch counts when the brief does not need a ticket link."
)

# Operator UX — every residual field should teach the cashier/clerk what to enter.
OPERATOR_UX_BLOCK = (
    "OPERATOR UX (priority):\n"
    "- Every operator-facing field SHOULD include a short `help` tooltip "
    "(what to enter, why it matters for the cashier/clerk).\n"
    "- Prefer useful smart_buttons on stock hosts the residual already links "
    "(Contacts, Employees, sale.order, account.move, pos.order, …) — "
    "on_model = stock host, related_model = x_* residual, relation_field = the M2O. "
    "Never invent parallel x_customer/x_employee. Skip Contacts buttons on visitor/"
    "key/call logs (not a second Contacts app).\n"
    "- Tooltips and smart buttons raise usability; Completeness ≠ Certification."
)


# Pack id whose shape the generic few-shot exemplar mirrors — skip when that pack matched (Doc 4 §3)
FEW_SHOT_EXEMPLAR_SOURCE_PACK = "car_rental"


def output_only_json_line() -> str:
    return "Output ONLY the JSON — no markdown, no commentary."


def closed_ttype_line() -> str:
    return f"Allowed ttypes (closed vocabulary): {CLOSED_TTYPE_VOCAB}."


def append_prompt_blocks(
    system: str,
    *,
    guardrail: str = "",
    include_anti_pattern: bool = True,
    user_prompt: str = "",
    brief_contract: str = "",
) -> str:
    contract = (brief_contract or "").strip()
    if not contract and (user_prompt or "").strip():
        from app.ai_operator_brief import brief_llm_contract

        contract = brief_llm_contract(user_prompt)
    parts = [system.rstrip(), output_only_json_line(), closed_ttype_line()]
    if contract:
        parts.insert(1, contract)
    if include_anti_pattern:
        parts.append(ANTI_PATTERN_BLOCK)
    parts.append(OPERATOR_UX_BLOCK)
    if guardrail.strip():
        parts.append(guardrail.strip())
    return "\n\n".join(p for p in parts if p)


def few_shot_exemplar_block(
    matched_pack_id: str | None,
    *,
    document_shape: str | None = None,
) -> str | None:
    """Return exemplar JSON text or None when it would duplicate the matched pack."""
    from app.ai_model_quality import few_shot_exemplar_json

    if document_shape == "register":
        return few_shot_exemplar_json(document_shape="register")
    if matched_pack_id and matched_pack_id == FEW_SHOT_EXEMPLAR_SOURCE_PACK:
        return None
    return few_shot_exemplar_json()
