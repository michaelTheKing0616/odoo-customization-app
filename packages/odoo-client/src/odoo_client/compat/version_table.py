"""Version differences that the client must not guess past.

Each row is the expected shape for a major. Live instances still have to be probed.
"""

from __future__ import annotations

# area -> major -> short fact
DIFFERENCES: dict[str, dict[int, str]] = {
    "routes_model": {16: "stock.route", 17: "stock.route", 18: "stock.route", 19: "stock.route", 20: "stock.route"},
    "account_type": {16: "account_type", 17: "account_type", 18: "account_type", 19: "account_type", 20: "account_type"},
    "account_company": {17: "company_id", 18: "company_ids", 19: "company_ids", 20: "company_ids"},
    "user_groups_field": {17: "groups_id", 18: "groups_id", 19: "group_ids", 20: "group_ids"},
    "name_search_kw": {17: "args", 18: "args", 19: "domain", 20: "domain"},
    "access_model": {17: "ir.model.access", 18: "ir.model.access", 19: "ir.model.access", 20: "ir.access"},
    "record_rule_model": {17: "ir.rule", 18: "ir.rule", 19: "ir.rule", 20: "absent"},
    "company_type": {19: "present", 20: "removed"},
    "company_registry": {19: "company_registry", 20: "additional_identifiers"},
    "pricelist_types": {19: "fixed/percentage/formula", 20: "fixed/discount/markup"},
    "cron_numbercall": {17: "present", 18: "removed", 19: "removed", 20: "removed"},
    "read_group": {18: "read_group", 19: "formatted_read_group", 20: "formatted_read_group"},
    "db_service": {19: "present", 20: "removed"},
    "json2_default": {19: "online_only", 20: "default"},
    "list_root": {19: "list", 20: "list"},
    "uom_po": {18: "present", 19: "removed", 20: "removed"},
    "bom_consumption": {19: "verify", 20: "removed"},
    "return_wizard": {19: "stock.return.picking", 20: "removed"},
    "partner_mobile": {19: "verify", 20: "absent"},
    "user_role": {19: "group_user", 20: "light/regular/system"},
}


def difference(area: str, major: int) -> str:
    row = DIFFERENCES[area]
    if major in row:
        return row[major]
    earlier = [key for key in row if key <= major]
    if not earlier:
        raise KeyError(area)
    return row[max(earlier)]


def native_mcp_present(module_names: list[str]) -> bool:
    """Community images have no ai* modules, so native MCP is absent."""
    return any(name.startswith("ai") for name in module_names)
