"""Version differences that the client must not guess past.

Each row is the expected shape for a major. Live instances still have to be probed.
Facts marked ``same`` or ``verify`` are copied from the T9 card; they are not
upgraded into field names.
"""

from __future__ import annotations

# V-row id -> DIFFERENCES key. One key per card row V01–V32.
V_ROW_KEYS: dict[str, str] = {
    "V01": "routes_model",
    "V02": "account_type",
    "V03": "account_company",
    "V04": "analytic",
    "V05": "tax_repartition",
    "V06": "tax_included",
    "V07": "payment_term_lines",
    "V08": "product_type",
    "V09": "uom_po",
    "V10": "stock_done_qty",
    "V11": "automation",
    "V12": "cron_numbercall",
    "V13": "user_groups_field",
    "V14": "name_search_kw",
    "V15": "web_urls",
    "V16": "api",
    "V17": "fiscal_position_tax_map",
    "V18": "access",
    "V19": "account_groups",
    "V20": "root_product_category",
    "V21": "uom_categories_packaging",
    "V22": "pricelist_types",
    "V23": "report_layouts",
    "V24": "account_payment_state",
    "V25": "company_type",
    "V26": "partner_mobile",
    "V27": "company_registry",
    "V28": "bom_consumption",
    "V29": "return_wizard",
    "V30": "tracking_values_model",
    "V31": "read_group",
    "V32": "user_role",
}

# area -> major -> short fact
DIFFERENCES: dict[str, dict[int, str]] = {
    "routes_model": {
        16: "stock.route",
        17: "stock.route",
        18: "stock.route",
        19: "stock.route",
        20: "stock.route",
    },
    "account_type": {
        16: "account_type",
        17: "account_type",
        18: "account_type",
        19: "account_type",
        20: "account_type",
    },
    "account_company": {
        16: "company_id",
        17: "company_id",
        18: "company_ids",
        19: "company_ids",
        20: "company_ids",
    },
    "analytic": {
        16: "plans + analytic_distribution",
        17: "plans + analytic_distribution",
        18: "plans + analytic_distribution",
        19: "plans + analytic_distribution",
        20: "same",
    },
    "tax_repartition": {
        16: "repartition_line_ids + document_type (17+)",
        17: "repartition_line_ids + document_type",
        18: "repartition_line_ids + document_type",
        19: "repartition_line_ids + document_type",
        20: "same",
    },
    "tax_included": {
        16: "price_include",
        17: "price_include",
        18: "verify override",
        19: "verify override",
        20: "override + document-level switch",
    },
    "payment_term_lines": {
        16: "nb_days (17+)",
        17: "nb_days",
        18: "nb_days",
        19: "nb_days",
        20: "nb_days",
    },
    "product_type": {
        16: "detailed_type",
        17: "detailed_type",
        18: "type + is_storable",
        19: "type + is_storable",
        20: "same as 18",
    },
    "uom_po": {
        16: "uom_po_id",
        17: "uom_po_id",
        18: "uom_po_id",
        19: "removed",
        20: "removed",
    },
    "stock_done_qty": {
        16: "quantity + picked (17+)",
        17: "quantity + picked",
        18: "quantity + picked",
        19: "quantity + picked",
        20: "same",
    },
    "automation": {
        16: "separate ir.actions.server (17+)",
        17: "separate ir.actions.server",
        18: "separate ir.actions.server",
        19: "separate ir.actions.server",
        20: "same",
    },
    "cron_numbercall": {
        16: "present",
        17: "present",
        18: "removed",
        19: "removed",
        20: "removed",
    },
    "user_groups_field": {
        16: "groups_id",
        17: "groups_id",
        18: "groups_id",
        19: "group_ids",
        20: "group_ids",
    },
    "name_search_kw": {
        16: "args",
        17: "args",
        18: "args",
        19: "domain",
        20: "domain",
    },
    "web_urls": {
        16: "/web#action= (17), /odoo/... (18+)",
        17: "/web#action=",
        18: "/odoo/...",
        19: "/odoo/...",
        20: "/odoo/...",
    },
    "api": {
        16: "JSON-2 added in 19",
        17: "JSON-2 added in 19",
        18: "JSON-2 added in 19",
        19: "JSON-2 added in 19",
        20: "JSON-2 preferred; db removed",
    },
    "fiscal_position_tax_map": {
        16: "separate model",
        17: "separate model",
        18: "separate model",
        19: "on the tax",
        20: "on the tax",
    },
    "access": {
        16: "ir.model.access + ir.rule",
        17: "ir.model.access + ir.rule",
        18: "ir.model.access + ir.rule",
        19: "ir.model.access + ir.rule",
        20: "ir.access",
    },
    "account_groups": {
        16: "account.group",
        17: "account.group",
        18: "account.group",
        19: "account.group",
        20: "parent_id; group model gone",
    },
    "root_product_category": {
        16: "product.product_category_all",
        17: "product.product_category_all",
        18: "product.product_category_all",
        19: "Goods/Services/Expenses",
        20: "same as 19",
    },
    "uom_categories_packaging": {
        16: "present",
        17: "present",
        18: "present",
        19: "removed",
        20: "removed",
    },
    "pricelist_types": {
        16: "fixed/percentage/formula",
        17: "fixed/percentage/formula",
        18: "fixed/percentage/formula",
        19: "fixed/percentage/formula",
        20: "fixed/discount/markup",
    },
    "report_layouts": {
        16: "standard/boxed/bold/striped",
        17: "standard/boxed/bold/striped",
        18: "standard/boxed/bold/striped",
        19: "standard/boxed/bold/striped (+ bubble/wave/folder on 19)",
        20: "standard, bubble, center, compact, dual, folder, lines, wave + report_tables_id",
    },
    "account_payment_state": {
        17: "verify",
        18: "draft/in_process/paid",
        19: "verify",
        20: "draft/paid/reconciled",
    },
    "company_type": {
        16: "present",
        17: "present",
        18: "present",
        19: "present",
        20: "removed",
    },
    "partner_mobile": {
        16: "present",
        17: "present",
        18: "present",
        19: "verify",
        20: "absent from base",
    },
    "company_registry": {
        16: "company_registry",
        17: "company_registry",
        18: "company_registry",
        19: "company_registry",
        20: "additional_identifiers JSON",
    },
    "bom_consumption": {
        16: "present",
        17: "present",
        18: "present",
        19: "verify",
        20: "removed",
    },
    "return_wizard": {
        16: "stock.return.picking",
        17: "stock.return.picking",
        18: "stock.return.picking",
        19: "verify",
        20: "removed",
    },
    "tracking_values_model": {
        16: "mail.tracking.value",
        17: "mail.tracking.value",
        18: "mail.tracking.value",
        19: "verify",
        20: "removed",
    },
    "read_group": {
        16: "legacy",
        17: "legacy",
        18: "legacy",
        19: "formatted added",
        20: "aggregates and tuples",
    },
    "user_role": {
        16: "—",
        17: "—",
        18: "—",
        19: "group_user / system",
        20: "light / regular / system",
    },
    # Extra keys already encoded before O20-06 (not V-rows).
    "access_model": {
        16: "ir.model.access",
        17: "ir.model.access",
        18: "ir.model.access",
        19: "ir.model.access",
        20: "ir.access",
    },
    "record_rule_model": {
        16: "ir.rule",
        17: "ir.rule",
        18: "ir.rule",
        19: "ir.rule",
        20: "absent",
    },
    "db_service": {19: "present", 20: "removed"},
    "json2_default": {19: "online_only", 20: "default"},
    "list_root": {19: "list", 20: "list"},
}


class UnknownVersionFact(Exception):
    """Named when an area is missing from the version table."""


class VersionFactUnavailable(Exception):
    """Named when a fact is removed or absent on the requested major."""


def _is_removed_or_absent(value: str) -> bool:
    text = value.strip().lower()
    return text == "removed" or text.startswith("absent")


def difference(area: str, major: int) -> str:
    """Return the encoded fact for ``area`` at ``major``.

    A 20 value of ``removed`` or ``absent`` is returned as-is. The lookup
    must not fall back to 19 (or earlier) and hide the removal.
    """
    try:
        row = DIFFERENCES[area]
    except KeyError as exc:
        raise UnknownVersionFact(f"unknown version-table area {area!r}") from exc
    if major in row:
        return row[major]
    # Prefer the latest removed/absent fact at or before this major so a
    # missing exact key cannot hide an encoded removal (e.g. 20 removed).
    removed_here_or_earlier = [
        key for key in row if key <= major and _is_removed_or_absent(row[key])
    ]
    if removed_here_or_earlier:
        return row[max(removed_here_or_earlier)]
    earlier = [key for key in row if key <= major]
    if not earlier:
        raise UnknownVersionFact(f"{area} has no fact at or before major {major}")
    return row[max(earlier)]


def require_present(area: str, major: int) -> str:
    """Return the fact, or raise a named error when it is removed/absent."""
    value = difference(area, major)
    if _is_removed_or_absent(value):
        raise VersionFactUnavailable(f"{area} is {value} on Odoo {major}")
    return value


def native_mcp_present(module_names: list[str]) -> bool:
    """Community images have no ai* modules, so native MCP is absent."""
    return any(name.startswith("ai") for name in module_names)
