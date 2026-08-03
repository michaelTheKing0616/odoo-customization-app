"""Multi-company field + record-rule pack for workflow models (CMP-11 §21)."""

from __future__ import annotations

import copy
import re
from typing import Any

from odoo_client import CreateFieldRequest, CreateRecordRuleRequest, FieldType, OdooClient
from odoo_client.client import OdooClientError

# Verified against Odoo 17–19 ir.rule global dict (company_ids).
COMPANY_RULE_DOMAIN_MODULE = (
    "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]"
)
COMPANY_RULE_DOMAIN_LIVE = (
    "['|', ('x_company_id', '=', False), ('x_company_id', 'in', company_ids)]"
)

COMPANY_FIELD_MODULE: dict[str, Any] = {
    "name": "company_id",
    "ttype": "many2one",
    "string": "Company",
    "relation": "res.company",
    "on_delete": "restrict",
}

COMPANY_FIELD_LIVE_NAME = "x_company_id"


def _model_xml_id(model: str) -> str:
    return f"model_{model.replace('.', '_')}"


def _rule_technical(model: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", model.lower()).strip("_")
    return f"rule_{slug[:48]}_multi_company"


def apply_multi_company_to_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Enrich ModuleSpec-like draft with company_id + record rules on new x_* models."""
    out = copy.deepcopy(draft)
    models = out.setdefault("models", [])
    rules = out.setdefault("record_rules", [])
    existing_rule_models = {
        str(r.get("model") or r.get("model_xml_id") or "")
        for r in rules
        if isinstance(r, dict)
    }

    for entry in models:
        if not isinstance(entry, dict):
            continue
        model = str(entry.get("model") or "")
        if not model.startswith("x_") or str(entry.get("mode") or "new") != "new":
            continue
        fields = entry.setdefault("fields", [])
        names = {str(f.get("name")) for f in fields if isinstance(f, dict) and f.get("name")}
        if "company_id" not in names:
            fields.append(dict(COMPANY_FIELD_MODULE))
        xml_id = _model_xml_id(model)
        if xml_id not in existing_rule_models and model not in existing_rule_models:
            rules.append(
                {
                    "name": f"Multi-company ({model})",
                    "model": model,
                    "model_xml_id": xml_id,
                    "domain_force": COMPANY_RULE_DOMAIN_MODULE,
                    "technical_name": _rule_technical(model),
                }
            )
            existing_rule_models.add(xml_id)

    out["multi_company"] = True
    out.setdefault("review_notes", []).append(
        "Multi-company: company_id + ir.rule with company_ids domain on workflow models."
    )
    return out


def apply_multi_company_live(
    client: OdooClient,
    models: list[str],
) -> dict[str, Any]:
    """Live-metadata path: x_company_id + record rules (PCM-safe on custom models)."""
    created_fields = 0
    created_rules = 0
    warnings: list[str] = []

    for model in models:
        if not model.startswith("x_"):
            continue
        try:
            if not client.field_exists(model, COMPANY_FIELD_LIVE_NAME):
                client.create_field(
                    CreateFieldRequest(
                        model=model,
                        name=COMPANY_FIELD_LIVE_NAME,
                        field_description="Company",
                        ttype=FieldType.MANY2ONE,
                        relation="res.company",
                        on_delete="restrict",
                    )
                )
                created_fields += 1
            rule_name = f"Multi-company ({model})"
            existing = client.list_record_rules(model=model, limit=50)
            if any(r.name == rule_name for r in existing):
                warnings.append(f"Record rule {rule_name!r} exists — skipped")
                continue
            client.create_record_rule(
                CreateRecordRuleRequest(
                    model=model,
                    name=rule_name,
                    domain_force=COMPANY_RULE_DOMAIN_LIVE,
                )
            )
            created_rules += 1
        except OdooClientError as exc:
            warnings.append(f"{model}: {exc}")

    return {
        "ok": True,
        "models": models,
        "fields_created": created_fields,
        "rules_created": created_rules,
        "warnings": warnings,
    }


def multi_company_guidance() -> dict[str, str]:
    return {
        "title": "Multi-company field visibility",
        "body": (
            "Add company_id (module export) or x_company_id (live metadata) on workflow models. "
            "Pair with a global record rule: "
            "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]. "
            "Hide company_id on forms for single-company databases; show optional=hide on list views."
        ),
    }
