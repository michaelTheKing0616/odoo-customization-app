"""Continuous invent hardening CLASS (P3) — Studio/Draft/Generate quality gates.

Class-wide (not Vehicle-only). Any residual / Prefer brief must stay honest:

1. Uncued Selection invent — never invent Type/Priority/Rate/Severity/Channel/Stage without cues
2. One cue → one field — no duplicate Notes/Assignment Note parallels
3. Satellite ≠ primary — optional peers never steal canvas; no uncued party/line
4. Pack bleed — packs only when prompt clearly asks (shape + adoption cues)
5. Stated brief cues honored (states, menu parents, fields, satellites)
6. Diagnosis Name matches brief/canvas noun — no Management fluff
7. Date default (not Datetime) unless time stated/implied

Flash-free / ``AI_INTENT_LLM=off`` must fully deliver Apply guarantees.
A complete draft is not the same as certified, and neither means Autopilot-ready. Publishing stays a step you confirm.
"""

from __future__ import annotations

from typing import Any

CONTINUOUS_INVENT_GATES: tuple[str, ...] = (
    "uncued_selection",
    "one_cue_one_field",
    "satellite_ne_primary",
    "pack_bleed",
    "stated_brief_cues",
    "diagnosis_name",
    "date_default",
)


def continuous_invent_stamp(*, prove_status: str = "pending") -> dict[str, Any]:
    """IR stamp for continuous invent class acceptance."""
    return {
        "class_id": "continuous_invent",
        "phase": "P3",
        "gates": list(CONTINUOUS_INVENT_GATES),
        "prove_status": prove_status,
        "promote_human": True,
        "flash_free_floor": True,
        "ai_intent_llm": "off",
    }


def assert_no_uncued_selection_invent(
    fields: list[dict[str, Any]],
    *,
    allowed_names: set[str] | None = None,
) -> list[str]:
    """Return invent findings for Type/Priority/Rate/Severity/Channel/Stage without cues."""
    allowed = allowed_names or set()
    findings: list[str] = []
    banned_exact = {
        "x_type",
        "x_category",
        "x_kind",
        "x_class",
        "x_priority",
        "x_urgency",
        "x_importance",
        "x_rate_unit",
        "x_rate_uom",
        "x_uom",
        "x_unit",
        "x_severity",
        "x_channel",
        "x_stage",
    }
    banned_strings = {
        "type",
        "category",
        "kind",
        "class",
        "priority",
        "urgency",
        "importance",
        "rate unit",
        "rate uom",
        "uom",
        "unit",
        "severity",
        "channel",
        "stage",
    }
    for field in fields or []:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "")
        string = str(field.get("string") or "").strip().lower()
        if name in allowed or name in {a for a in allowed}:
            continue
        if name in banned_exact or string in banned_strings:
            if str(field.get("ttype") or "") == "selection" or not field.get("source"):
                findings.append(f"uncued_selection:{name or string}")
    return findings


__all__ = [
    "CONTINUOUS_INVENT_GATES",
    "assert_no_uncued_selection_invent",
    "continuous_invent_stamp",
]
