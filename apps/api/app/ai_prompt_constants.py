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
    "- Emit hollow catalog models (type/category/tag/stage/priority/status/kind as standalone models)."
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
) -> str:
    parts = [system.rstrip(), output_only_json_line(), closed_ttype_line()]
    if include_anti_pattern:
        parts.append(ANTI_PATTERN_BLOCK)
    if guardrail.strip():
        parts.append(guardrail.strip())
    return "\n\n".join(p for p in parts if p)


def few_shot_exemplar_block(matched_pack_id: str | None) -> str | None:
    """Return exemplar JSON text or None when it would duplicate the matched pack."""
    from app.ai_model_quality import few_shot_exemplar_json

    if matched_pack_id and matched_pack_id == FEW_SHOT_EXEMPLAR_SOURCE_PACK:
        return None
    return few_shot_exemplar_json()
