"""Odoo 20 version table, list root, JSON-2 default, and MCP absence."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError
from odoo_client.transport.json2 import Json2TransportError
from odoo_client.compat.adapters.views_v20 import list_arch_root, normalize_view_mode
from odoo_client.compat.version_table import (
    DIFFERENCES,
    V_ROW_KEYS,
    VersionFactUnavailable,
    difference,
    native_mcp_present,
    require_present,
)

# (V-id, older major) — older value is whatever the card encoded for that major.
_FAKE_ROW_CASES = [
    ("V01", 16),
    ("V02", 16),
    ("V03", 16),
    ("V04", 19),
    ("V05", 17),
    ("V06", 16),
    ("V07", 17),
    ("V08", 18),
    ("V09", 18),
    ("V10", 17),
    ("V11", 17),
    ("V12", 17),
    ("V13", 18),
    ("V14", 18),
    ("V15", 17),
    ("V16", 19),
    ("V17", 18),
    ("V18", 19),
    ("V19", 19),
    ("V20", 18),
    ("V21", 18),
    ("V22", 19),
    ("V23", 16),
    ("V24", 18),
    ("V25", 19),
    ("V26", 16),
    ("V27", 19),
    ("V28", 16),
    ("V29", 16),
    ("V30", 16),
    ("V31", 18),
    ("V32", 19),
]


def test_every_listed_difference_resolves() -> None:
    assert len(V_ROW_KEYS) == 32
    assert set(V_ROW_KEYS) == {f"V{i:02d}" for i in range(1, 33)}
    for v_id, area in V_ROW_KEYS.items():
        assert area in DIFFERENCES, v_id
        assert 20 in DIFFERENCES[area], v_id
    assert difference("access_model", 20) == "ir.access"
    assert difference("record_rule_model", 20) == "absent"
    assert difference("record_rule_model", 19) == "ir.rule"
    assert difference("name_search_kw", 20) == "domain"
    assert difference("name_search_kw", 17) == "args"
    assert difference("db_service", 20) == "removed"
    assert difference("json2_default", 20) == "default"
    assert difference("company_type", 20) == "removed"
    assert difference("pricelist_types", 20) == "fixed/discount/markup"
    assert difference("read_group", 20) == "aggregates and tuples"
    assert difference("user_groups_field", 19) == "group_ids"


@pytest.mark.parametrize("v_id,older_major", _FAKE_ROW_CASES, ids=[c[0] for c in _FAKE_ROW_CASES])
def test_fake_version_row(v_id: str, older_major: int) -> None:
    area = V_ROW_KEYS[v_id]
    row = DIFFERENCES[area]
    assert 20 in row
    assert older_major in row
    assert difference(area, 20) == row[20]
    assert difference(area, older_major) == row[older_major]
    assert difference(area, 20) != ""


def test_v25_company_type_on_20_fails_with_named_message() -> None:
    assert difference("company_type", 20) == "removed"
    assert difference("company_type", 19) == "present"
    with pytest.raises(VersionFactUnavailable, match="company_type is removed on Odoo 20") as caught:
        require_present("company_type", 20)
    assert not isinstance(caught.value, KeyError)


def test_removed_or_absent_on_20_does_not_fall_back_to_19() -> None:
    assert difference("company_type", 20) == "removed"
    assert difference("partner_mobile", 20) == "absent from base"
    assert difference("uom_po", 20) == "removed"
    assert difference("bom_consumption", 20) == "removed"
    assert difference("return_wizard", 20) == "removed"
    assert difference("tracking_values_model", 20) == "removed"
    assert difference("record_rule_model", 20) == "absent"
    assert difference("db_service", 20) == "removed"
    assert difference("cron_numbercall", 20) == "removed"
    assert difference("uom_categories_packaging", 20) == "removed"


@pytest.mark.parametrize("v_id", list(V_ROW_KEYS), ids=list(V_ROW_KEYS))
def test_live_na_until_odoo20_url(v_id: str) -> None:
    pytest.skip("live N/A until ODOO20_URL is set.")


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


def test_major_20_json2_password_auth_error_does_not_suggest_auto_xmlrpc() -> None:
    client = OdooClient(
        ConnectionConfig(url="http://127.0.0.1:9", db="t", username="u", password="p")
    )
    with patch(
        "odoo_client.client.Json2Transport.context_get",
        side_effect=Json2TransportError(
            "Invalid apikey", status=401, body={"message": "Invalid apikey"}
        ),
    ):
        with pytest.raises(OdooClientError) as caught:
            client._connect_json2(major=20)
    msg = str(caught.value)
    assert "JSON-2 requires an API key" in msg
    assert "Odoo 19" not in msg
    assert "non-Online" not in msg
    assert "rpc_protocol=xmlrpc" in msg


def test_community_without_ai_modules_has_no_native_mcp() -> None:
    assert native_mcp_present(["sale", "account"]) is False
    assert native_mcp_present(["ai_agent"]) is True
