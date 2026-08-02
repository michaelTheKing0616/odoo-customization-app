"""Law-firm domain pack — teaching scaffold + merge floor for legal ops prompts.

Built from `law_firm_gold_spec` with canonical model names the LLM already emits
(`x_attorney`, `x_matter`, …) so merge deepens AI drafts instead of adding parallel
`x_lf_*` trees. The pack is injected into the LLM prompt (teach) and merged after
(generation floor) — never a substitute for MODEL_CREATION_RULES.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from app.ai_reference_law_firm import law_firm_gold_spec

# Gold → names the generator / depth seeds already use
_MODEL_RENAME = {
    "x_lf_attorney": "x_attorney",
    "x_lf_matter": "x_matter",
    "x_lf_matter_party": "x_matter_party",
    "x_lf_time_entry": "x_matter_line",
    "x_lf_expense": "x_expense",
    "x_lf_task": "x_task",
    "x_lf_hearing": "x_event",
    "x_lf_document": "x_document",
    "x_lf_conflict": "x_compliance",
    "x_lf_invoice": "x_bill",
    "x_lf_payment": "x_payment",
    "x_lf_trust": "x_deposit",
}

_FIELD_RENAME = {
    "x_client_id": "x_partner_id",
    "x_invoice_id": "x_bill_id",
}


def _rewrite_value(val: Any) -> Any:
    if isinstance(val, str):
        out = val
        for old, new in _MODEL_RENAME.items():
            out = out.replace(old, new)
        for old, new in _FIELD_RENAME.items():
            out = out.replace(old, new)
        return out
    if isinstance(val, list):
        return [_rewrite_value(v) for v in val]
    if isinstance(val, dict):
        return {k: _rewrite_value(v) for k, v in val.items()}
    return val


def law_firm_pack() -> dict[str, Any]:
    """Curated comprehensive law-firm ModuleSpec scaffold."""
    gold = _rewrite_value(copy.deepcopy(law_firm_gold_spec()))
    gold["domain_pack"] = "law_firm"
    gold["display_name"] = gold.get("display_name") or "Law Firm Management"
    gold["technical_name"] = gold.get("technical_name") or "law_firm_management"
    gold["tags"] = [
        "law",
        "legal",
        "lawyer",
        "attorney",
        "matter",
        "case",
        "litigation",
        "law firm",
        "practice management",
        "retainer",
        "trust",
        "billable",
        "counsel",
    ]
    gold["anti_patterns"] = [
        "Do NOT invent x_client / x_customer mini-CRM — use res.partner + x_party roles",
        "Do NOT add case_type / practice_area / priority as separate models — selections",
        "Do NOT emit Python code automations",
        "Hearings/events are one model; conflict checks are compliance workflow",
    ]
    for m in gold.get("models") or []:
        if not isinstance(m, dict):
            continue
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                continue
            if f.get("name") == "x_partner_id" and f.get("relation") == "res.partner":
                f.setdefault("string", f.get("string") or "Contact")
    return gold


def scaffold_teaching_blob(
    scaffold: dict[str, Any] | None, *, max_chars: int = 7500
) -> str:
    """Compact world-class scaffold for the LLM prompt (teach before merge)."""
    if not scaffold:
        return ""
    models_out: list[dict[str, Any]] = []
    for m in scaffold.get("models") or []:
        if not isinstance(m, dict) or not m.get("model"):
            continue
        fields_out: list[dict[str, Any]] = []
        for f in (m.get("fields") or [])[:22]:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            row: dict[str, Any] = {
                "name": f.get("name"),
                "ttype": f.get("ttype"),
                "string": f.get("string"),
            }
            if f.get("relation"):
                row["relation"] = f["relation"]
            if f.get("relation_field"):
                row["relation_field"] = f["relation_field"]
            if f.get("selection"):
                row["selection"] = str(f["selection"])[:140]
            if f.get("required"):
                row["required"] = True
            fields_out.append(row)
        models_out.append(
            {
                "model": m.get("model"),
                "description": m.get("description"),
                "is_workflow": bool(m.get("is_workflow")),
                "fields": fields_out,
            }
        )
    payload = {
        "instruction": (
            "Study this world-class ops scaffold. Produce a ModuleSpec for the USER "
            "request with EQUAL OR GREATER operational depth: rich selections (not "
            "specialty_a placeholders), parent one2many for children, line→bill links, "
            "party roles, financial hold/deposit statuses, safe automations only. "
            "REQUIRED: models[] MUST include EVERY technical model name listed below "
            "(you may deepen fields; do not omit attorney/staff, bill/invoice, "
            "compliance/conflict, or deposit/trust when they appear in the scaffold). "
            "Fee-earner/counsel many2ones must relation the staff model (x_attorney), "
            "NOT res.users (res.users is only for login x_user_id). "
            "Party/role-link models are NOT is_workflow. "
            "Matter/job status MUST include terminal stages (closed/done/on_hold). "
            "Adapt labels to the user domain; do not invent hollow type/tag models."
        ),
        "required_models": [m["model"] for m in models_out],
        "domain_pack": scaffold.get("domain_pack"),
        "models": models_out,
        "automations": (scaffold.get("automations") or [])[:8],
        "smart_buttons": (scaffold.get("smart_buttons") or [])[:12],
        "anti_patterns": scaffold.get("anti_patterns") or [],
    }
    return json.dumps(payload, indent=None)[:max_chars]


__all__ = ["law_firm_pack", "scaffold_teaching_blob"]
