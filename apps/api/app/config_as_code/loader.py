"""Declarative config-as-code. Validates a spec and compiles an ordered plan.

This does not talk to Odoo. Apply stays behind classify_rpc and the dry-run gate.
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

SECTIONS: tuple[str, ...] = (
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

_TOP = frozenset({"version", "project", "description", "target", *SECTIONS})
_SECRET_PREFIX = "secret:"


class SpecError(ValueError):
    """The YAML spec is not safe to plan."""


class CustomField(BaseModel):
    model: str
    name: str
    field_description: str = ""
    ttype: str = "char"

    @model_validator(mode="after")
    def x_prefix(self) -> CustomField:
        if not self.name.startswith("x_") or self.name.startswith("x_studio_"):
            raise ValueError(f"custom field {self.name} must start with x_ and must not start with x_studio_")
        return self


class ConfigSpec(BaseModel):
    version: int = Field(ge=1)
    project: str = Field(min_length=1)
    description: str = ""
    target: str = "staging"
    modules: list[dict[str, Any]] = Field(default_factory=list)
    languages: list[dict[str, Any]] = Field(default_factory=list)
    currencies: list[dict[str, Any]] = Field(default_factory=list)
    companies: list[dict[str, Any]] = Field(default_factory=list)
    settings: list[dict[str, Any]] = Field(default_factory=list)
    users: list[dict[str, Any]] = Field(default_factory=list)
    sequences: list[dict[str, Any]] = Field(default_factory=list)
    mail_servers: list[dict[str, Any]] = Field(default_factory=list)
    tax_groups: list[dict[str, Any]] = Field(default_factory=list)
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    taxes: list[dict[str, Any]] = Field(default_factory=list)
    journals: list[dict[str, Any]] = Field(default_factory=list)
    payment_terms: list[dict[str, Any]] = Field(default_factory=list)
    fiscal_positions: list[dict[str, Any]] = Field(default_factory=list)
    analytic_plans: list[dict[str, Any]] = Field(default_factory=list)
    analytic_accounts: list[dict[str, Any]] = Field(default_factory=list)
    product_categories: list[dict[str, Any]] = Field(default_factory=list)
    product_attributes: list[dict[str, Any]] = Field(default_factory=list)
    warehouses: list[dict[str, Any]] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    operation_types: list[dict[str, Any]] = Field(default_factory=list)
    routes: list[dict[str, Any]] = Field(default_factory=list)
    products: list[dict[str, Any]] = Field(default_factory=list)
    pricelists: list[dict[str, Any]] = Field(default_factory=list)
    reorder_rules: list[dict[str, Any]] = Field(default_factory=list)
    putaway_rules: list[dict[str, Any]] = Field(default_factory=list)
    crm_stages: list[dict[str, Any]] = Field(default_factory=list)
    sales_teams: list[dict[str, Any]] = Field(default_factory=list)
    sale_templates: list[dict[str, Any]] = Field(default_factory=list)
    workcenters: list[dict[str, Any]] = Field(default_factory=list)
    boms: list[dict[str, Any]] = Field(default_factory=list)
    departments: list[dict[str, Any]] = Field(default_factory=list)
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    employees: list[dict[str, Any]] = Field(default_factory=list)
    leave_types: list[dict[str, Any]] = Field(default_factory=list)
    pos_payment_methods: list[dict[str, Any]] = Field(default_factory=list)
    pos_configs: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    task_stages: list[dict[str, Any]] = Field(default_factory=list)
    custom_fields: list[CustomField] = Field(default_factory=list)
    views: list[dict[str, Any]] = Field(default_factory=list)
    server_actions: list[dict[str, Any]] = Field(default_factory=list)
    automations: list[dict[str, Any]] = Field(default_factory=list)
    crons: list[dict[str, Any]] = Field(default_factory=list)
    access_rights: list[dict[str, Any]] = Field(default_factory=list)
    record_rules: list[dict[str, Any]] = Field(default_factory=list)
    records: list[dict[str, Any]] = Field(default_factory=list)


def _reject_literal_secrets(obj: object, path: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}" if path else str(key)
            if key in {"password", "api_key", "token", "secret"} and isinstance(value, str):
                if not value.startswith(_SECRET_PREFIX):
                    raise SpecError(f"{here} must be a secret: pointer, not a literal")
            _reject_literal_secrets(value, here)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _reject_literal_secrets(item, f"{path}[{index}]")


def load_spec(text: str) -> ConfigSpec:
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise SpecError("spec must be a mapping")
    unknown = set(raw) - _TOP
    if unknown:
        raise SpecError("unknown sections: " + ", ".join(sorted(unknown)))
    _reject_literal_secrets(raw)
    try:
        return ConfigSpec.model_validate(raw)
    except ValueError as exc:
        raise SpecError(str(exc)) from exc


def compile_plan(spec: ConfigSpec) -> list[dict[str, Any]]:
    """Ordered operations. res_id is never included, so the plan fingerprint is stable."""
    plan: list[dict[str, Any]] = []
    for section in SECTIONS:
        rows = getattr(spec, section)
        for index, row in enumerate(rows):
            body = row.model_dump() if isinstance(row, BaseModel) else dict(row)
            plan.append({"section": section, "index": index, "body": body})
    return plan
