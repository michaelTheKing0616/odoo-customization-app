"""REG-NP-5B: 47 config sections stay in apply order; custom fields stay x_-prefixed."""

from __future__ import annotations

import pytest

from app.config_as_code.loader import SECTIONS, CustomField, SpecError, load_spec

# Apply order from T5B_CONFIG. Deleting or reordering a name in loader.SECTIONS fails this.
_APPLY_ORDER = (
    "modules",
    "languages",
    "currencies",
    "companies",
    "settings",
    "users",
    "sequences",
    "mail_servers",
    "tax_groups",
    "accounts",
    "taxes",
    "journals",
    "payment_terms",
    "fiscal_positions",
    "analytic_plans",
    "analytic_accounts",
    "product_categories",
    "product_attributes",
    "warehouses",
    "locations",
    "operation_types",
    "routes",
    "products",
    "pricelists",
    "reorder_rules",
    "putaway_rules",
    "crm_stages",
    "sales_teams",
    "sale_templates",
    "workcenters",
    "boms",
    "departments",
    "jobs",
    "employees",
    "leave_types",
    "pos_payment_methods",
    "pos_configs",
    "projects",
    "task_stages",
    "custom_fields",
    "views",
    "server_actions",
    "automations",
    "crons",
    "access_rights",
    "record_rules",
    "records",
)


def _field_spec(name: str) -> str:
    return (
        "version: 1\n"
        "project: demo\n"
        "custom_fields:\n"
        "  - model: res.partner\n"
        f"    name: {name}\n"
    )


def test_sections_are_47_in_apply_order() -> None:
    assert len(SECTIONS) == 47
    assert SECTIONS[0] == "modules"
    assert SECTIONS[-1] == "records"
    assert SECTIONS == _APPLY_ORDER


def test_custom_field_prefix_rules() -> None:
    with pytest.raises(SpecError, match="must start with x_"):
        load_spec(_field_spec("note"))

    with pytest.raises(SpecError, match="x_studio_"):
        load_spec(_field_spec("x_studio_note"))

    spec = load_spec(_field_spec("x_rc_number"))
    field = spec.custom_fields[0]
    assert isinstance(field, CustomField)
    assert field.name == "x_rc_number"
