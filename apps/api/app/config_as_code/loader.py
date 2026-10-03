"""Declarative config-as-code. Validates a spec and compiles an ordered plan.

This does not talk to Odoo. Apply stays behind classify_rpc and the dry-run gate.
"""

from __future__ import annotations

from typing import Any, Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.changeset.ops import OP_CATALOG

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
_REF_PREFIXES: Final[tuple[str, ...]] = ("key:", "ref:", "find:", "name:", "secret:")

# Closed catalog only. Sections without a dedicated op use the closest existing name.
SECTION_OP: Final[dict[str, str]] = {
    "modules": "module.install",
    "languages": "config_record.upsert",
    "currencies": "config_record.upsert",
    "companies": "company.update",
    "settings": "setting.set",
    "users": "user.create",
    "sequences": "sequence.create",
    "mail_servers": "config_record.upsert",
    "tax_groups": "config_record.upsert",
    "accounts": "config_record.upsert",
    "taxes": "config_record.upsert",
    "journals": "config_record.upsert",
    "payment_terms": "config_record.upsert",
    "fiscal_positions": "config_record.upsert",
    "analytic_plans": "config_record.upsert",
    "analytic_accounts": "config_record.upsert",
    "product_categories": "config_record.upsert",
    "product_attributes": "config_record.upsert",
    "warehouses": "config_record.upsert",
    "locations": "config_record.upsert",
    "operation_types": "config_record.upsert",
    "routes": "config_record.upsert",
    "products": "config_record.upsert",
    "pricelists": "config_record.upsert",
    "reorder_rules": "config_record.upsert",
    "putaway_rules": "config_record.upsert",
    "crm_stages": "stage.upsert",
    "sales_teams": "config_record.upsert",
    "sale_templates": "config_record.upsert",
    "workcenters": "config_record.upsert",
    "boms": "config_record.upsert",
    "departments": "config_record.upsert",
    "jobs": "config_record.upsert",
    "employees": "config_record.upsert",
    "leave_types": "config_record.upsert",
    "pos_payment_methods": "config_record.upsert",
    "pos_configs": "config_record.upsert",
    "projects": "config_record.upsert",
    "task_stages": "stage.upsert",
    "custom_fields": "field.create",
    "views": "view.inherit.create",
    "server_actions": "server_action.create",
    "automations": "automation.create",
    "crons": "cron.create",
    "access_rights": "access.create",
    "record_rules": "rule.create",
    "records": "config_record.upsert",
}


class SpecError(ValueError):
    """The YAML spec is not safe to plan."""


class CompileError(SpecError):
    """Named compile failure (no_matching_op)."""

    def __init__(self, name: str, detail: str = "") -> None:
        self.name = name
        message = name if not detail else f"{name}: {detail}"
        super().__init__(message)


class CustomField(BaseModel):
    model_config = ConfigDict(extra="allow")

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


def _collect_defined_keys(raw: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for section in SECTIONS:
        rows = raw.get(section)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("key") is not None:
                keys.add(str(row["key"]))
    return keys


def _reject_duplicate_keys(raw: dict[str, Any]) -> None:
    for section in SECTIONS:
        rows = raw.get(section)
        if not isinstance(rows, list):
            continue
        seen: dict[str, int] = {}
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            key = row.get("key")
            if key is None:
                continue
            text = str(key)
            if text in seen:
                raise SpecError(
                    f"duplicate key {text} in {section} (rows {seen[text]} and {index})"
                )
            seen[text] = index


def _validate_key_references(obj: object, known_keys: set[str], path: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}" if path else str(key)
            _validate_key_references(value, known_keys, here)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _validate_key_references(item, known_keys, f"{path}[{index}]")
    elif isinstance(obj, str):
        optional = obj.startswith("?")
        rest = obj[1:] if optional else obj
        if rest.startswith("key:"):
            target = rest[4:]
            if not optional and target not in known_keys:
                raise SpecError(f"{path} references unknown key {target}")


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
    _reject_duplicate_keys(raw)
    known_keys = _collect_defined_keys(raw)
    _validate_key_references(raw, known_keys)
    try:
        return ConfigSpec.model_validate(raw)
    except ValueError as exc:
        raise SpecError(str(exc)) from exc


def op_for_section(section: str) -> str:
    """Map a spec section to a catalog op. Missing or unknown names fail closed."""
    op_type = SECTION_OP.get(section)
    if not op_type or op_type not in OP_CATALOG:
        raise CompileError("no_matching_op", section)
    return op_type


def _xmlid_for(project: str, section: str, index: int, body: dict[str, Any]) -> str:
    if body.get("xmlid"):
        return str(body["xmlid"])
    key = body.get("key")
    if key:
        text = str(key)
        return text if "." in text else f"{project}.{text}"
    name = body.get("name")
    model = body.get("model")
    prefix = project or "ingenium"
    if name and model:
        return f"{prefix}.{section}_{model}_{name}"
    if name:
        return f"{prefix}.{section}_{name}"
    return f"{prefix}.{section}_{index}"


def compile_plan(spec: ConfigSpec) -> list[dict[str, Any]]:
    """Ordered catalog ops. res_id is never included, so the plan fingerprint is stable."""
    plan: list[dict[str, Any]] = []
    project = spec.project
    for section in SECTIONS:
        rows = getattr(spec, section)
        op_type = op_for_section(section)
        for index, row in enumerate(rows):
            body = row.model_dump() if isinstance(row, BaseModel) else dict(row)
            plan.append(
                {
                    "section": section,
                    "index": index,
                    "type": op_type,
                    "xmlid": _xmlid_for(project, section, index, body),
                    "body": body,
                }
            )
    return plan
