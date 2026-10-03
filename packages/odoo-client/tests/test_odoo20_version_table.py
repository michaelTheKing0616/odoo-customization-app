"""Odoo 20 version table, list root, JSON-2 default, and MCP absence."""

from __future__ import annotations

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.compat.adapters.views_v20 import list_arch_root, normalize_view_mode
from odoo_client.compat.version_table import DIFFERENCES, difference, native_mcp_present


def test_every_listed_difference_resolves() -> None:
    assert len(DIFFERENCES) >= 20
    assert difference("access_model", 20) == "ir.access"
    assert difference("record_rule_model", 20) == "absent"
    assert difference("record_rule_model", 19) == "ir.rule"
    assert difference("name_search_kw", 20) == "domain"
    assert difference("name_search_kw", 17) == "args"
    assert difference("db_service", 20) == "removed"
    assert difference("json2_default", 20) == "default"
    assert difference("company_type", 20) == "removed"
    assert difference("pricelist_types", 20) == "fixed/discount/markup"
    assert difference("read_group", 20) == "formatted_read_group"
    assert difference("user_groups_field", 19) == "group_ids"


def test_odoo20_list_root_is_list_not_tree() -> None:
    assert list_arch_root("list") == "list"
    assert list_arch_root("tree") == "list"
    assert normalize_view_mode("tree,form") == "list,form"


def test_major_20_auto_selects_json2_even_when_local() -> None:
    client = OdooClient(
        ConnectionConfig(url="http://127.0.0.1:9", db="t", username="u", password="p")
    )
    assert client._should_use_json2(major=20, hosting="local") is True
    assert client._should_use_json2(major=19, hosting="local") is False
    assert client._should_use_json2(major=19, hosting="online") is True


def test_community_without_ai_modules_has_no_native_mcp() -> None:
    assert native_mcp_present(["sale", "account"]) is False
    assert native_mcp_present(["ai_agent"]) is True
