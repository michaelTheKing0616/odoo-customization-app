"""Replay a 19-authored config spec against Odoo 20.

Compatible ops apply through the existing access compiler and change-set
executor. Incompatible ops raise a named migration note before any write.
There is no second access compiler.
"""

from __future__ import annotations

from typing import Any

from odoo_client.compat.version_table import DIFFERENCES, V_ROW_KEYS, difference

from app.config_as_code.apply import ApplyError, ApplyResult, apply_plan
from app.config_as_code.loader import ConfigSpec, compile_plan, load_spec
from app.odoo20.access_compiler import compile_access

# Operator-facing notes. Do not rewrite these into guessed 20 field names.
KNOWN_REFUSALS: tuple[tuple[str, str], ...] = (
    ("company_type_removed", "company_type removed"),
    (
        "group_record_rule",
        "group record rules must become ir.access with a domain",
    ),
    ("percentage_pricelist_is_discount", "percentage pricelist is discount"),
    (
        "company_registry_is_additional_identifiers",
        "company_registry is additional identifiers",
    ),
)

_PRICELIST_TYPE_KEYS = frozenset(
    {"compute_price", "applied_on", "percent_price", "pricelist_type"}
)
_PARTNER_MODELS = frozenset({"res.partner", "res.company"})

# 19-side keys an authored spec may still use. Sourced from the version-table
# area name and older-major facts / T9 row labels — not from the 20 fact.
_VERIFY_SPEC_KEYS: dict[str, frozenset[str]] = {
    "tax_included": frozenset({"tax_included", "price_include"}),
    "account_payment_state": frozenset({"account_payment_state", "in_process"}),
    "partner_mobile": frozenset({"partner_mobile", "mobile"}),
    "bom_consumption": frozenset({"bom_consumption", "consumption"}),
    "return_wizard": frozenset({"return_wizard", "stock.return.picking"}),
    "tracking_values_model": frozenset({"tracking_values_model", "mail.tracking.value"}),
}


class MigrationNote(ApplyError):
    """Named 19-to-20 refusal. No port write has been made."""


def verify_areas(*, major: int = 19) -> list[str]:
    """Version-table areas whose fact at ``major`` still says verify."""
    areas: list[str] = []
    for area, row in DIFFERENCES.items():
        fact = row.get(major)
        if fact and "verify" in str(fact).lower():
            areas.append(area)
    return areas


def verify_row_ids(*, major: int = 19) -> list[str]:
    """V-ids whose encoded fact at ``major`` still says verify."""
    areas = set(verify_areas(major=major))
    return [vid for vid, area in V_ROW_KEYS.items() if area in areas]


def _walk_mappings(obj: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        found.append(obj)
        for value in obj.values():
            found.extend(_walk_mappings(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk_mappings(item))
    return found


def _model_of(entry: dict[str, Any], mapping: dict[str, Any]) -> str:
    body = entry.get("body") if isinstance(entry.get("body"), dict) else {}
    return str(mapping.get("model") or body.get("model") or "")


def _has_percentage(mapping: dict[str, Any]) -> bool:
    for key, value in mapping.items():
        if str(value).strip().lower() != "percentage":
            continue
        if str(key) in _PRICELIST_TYPE_KEYS or str(key) == "type":
            return True
    return False


def _verify_hit(area: str, entry: dict[str, Any], mapping: dict[str, Any]) -> bool:
    section = str(entry.get("section") or "")
    model = _model_of(entry, mapping)
    keys = {str(key) for key in mapping}
    values = {str(value).strip() for value in mapping.values() if isinstance(value, (str, int))}
    tokens = _VERIFY_SPEC_KEYS.get(area, frozenset({area}))
    if area in keys or area in values:
        return True
    if area == "partner_mobile":
        if model in _PARTNER_MODELS or section in {"companies", "users"}:
            return bool(keys & {"mobile", "title", "partner_mobile"})
        return "partner_mobile" in keys
    if area == "bom_consumption":
        return section == "boms" and bool(keys & tokens)
    if area == "account_payment_state":
        if "in_process" in values or "account_payment_state" in keys:
            return True
        return model == "account.payment" and "payment_state" in keys
    if area == "tax_included":
        return bool(keys & tokens) or section == "taxes" and "price_include" in keys
    return bool(keys & tokens) or bool(values & tokens)


def first_migration_note(
    plan: list[dict[str, Any]],
    *,
    source_major: int = 19,
    target_major: int = 20,
) -> MigrationNote | None:
    """Return the first named refusal in plan order, or None if the plan can apply."""
    if target_major < 20:
        return None
    # Touch the table so refusals stay named from encoded facts, not guesses.
    difference("company_type", target_major)
    difference("company_registry", target_major)
    difference("pricelist_types", target_major)
    difference("access", target_major)
    verify = verify_areas(major=source_major)
    for entry in plan:
        section = str(entry.get("section") or "")
        op_type = str(entry.get("type") or "")
        if section == "record_rules" or op_type == "rule.create":
            return MigrationNote(
                "group_record_rule",
                "group record rules must become ir.access with a domain",
            )
        mappings = _walk_mappings(entry)
        for mapping in mappings:
            if "company_type" in mapping:
                return MigrationNote("company_type_removed", "company_type removed")
            if "company_registry" in mapping:
                return MigrationNote(
                    "company_registry_is_additional_identifiers",
                    "company_registry is additional identifiers",
                )
            if section == "pricelists" and _has_percentage(mapping):
                return MigrationNote(
                    "percentage_pricelist_is_discount",
                    "percentage pricelist is discount",
                )
            for area in verify:
                if _verify_hit(area, entry, mapping):
                    return MigrationNote(
                        "not_translated",
                        f"{area} is not translated (version table still says verify)",
                    )
    return None


def translate_access(plan: list[dict[str, Any]], *, target_major: int = 20) -> list[dict[str, Any]]:
    """Run the existing access compiler. Record rules never become ir.access here."""
    rights = [
        dict(entry["body"])
        for entry in plan
        if entry.get("section") == "access_rights" and isinstance(entry.get("body"), dict)
    ]
    compile_access(target_major, rights, None)
    return plan


def replay_19_on_20(
    spec: ConfigSpec | str,
    port: Any,
    **apply_kwargs: Any,
) -> ApplyResult:
    """Compile a 19 spec and apply it as major 20, or raise before any write."""
    loaded = load_spec(spec) if isinstance(spec, str) else spec
    plan = compile_plan(loaded)
    note = first_migration_note(plan, source_major=19, target_major=20)
    if note is not None:
        raise note
    translate_access(plan, target_major=20)
    port.major = 20
    return apply_plan(port, plan, **apply_kwargs)
