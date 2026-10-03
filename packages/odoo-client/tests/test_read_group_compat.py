"""Aggregate RPC method follows the read_group version-table row (V31)."""

from __future__ import annotations

from unittest.mock import patch

from odoo_client.client import OdooClient
from odoo_client.compat.read_group import (
    aggregate_rpc_method,
    build_aggregate_execute_kw,
    resolve_aggregate_rpc_method,
)
from odoo_client.models import ConnectionConfig
from odoo_client.transport.execute_kw_map import execute_kw_to_json2_body
from odoo_client.transport.json2 import Json2Transport


def test_aggregate_rpc_method_major18_uses_read_group() -> None:
    assert aggregate_rpc_method(18) == "read_group"
    assert resolve_aggregate_rpc_method("read_group", 18) == "read_group"
    assert resolve_aggregate_rpc_method("formatted_read_group", 18) == "read_group"


def test_aggregate_rpc_method_major20_uses_formatted_read_group() -> None:
    assert aggregate_rpc_method(20) == "formatted_read_group"
    assert resolve_aggregate_rpc_method("read_group", 20) == "formatted_read_group"
    assert resolve_aggregate_rpc_method("formatted_read_group", 20) == "formatted_read_group"


def test_build_aggregate_execute_kw_reads_method_from_version_table() -> None:
    method, args, kwargs = build_aggregate_execute_kw(
        [("active", "=", True)],
        ["amount_total:sum"],
        ["partner_id"],
        major=20,
        limit=5,
    )
    assert method == "formatted_read_group"
    assert args == [[("active", "=", True)], ["amount_total:sum"], ["partner_id"]]
    assert kwargs["limit"] == 5

    method18, _, _ = build_aggregate_execute_kw([], [], [], major=18)
    assert method18 == "read_group"


def test_read_group_json2_body_maps_domain_fields_groupby() -> None:
    body = execute_kw_to_json2_body(
        "formatted_read_group",
        [[], ["x_count"], ["state"]],
        {"limit": 10},
    )
    assert body == {"domain": [], "fields": ["x_count"], "groupby": ["state"], "limit": 10}


def test_json2_transport_major20_rewrites_read_group_method_name() -> None:
    transport = Json2Transport("http://odoo.test", "KEY", odoo_major=20)
    with patch.object(transport, "call", return_value=[]) as call:
        transport.execute_kw(
            "sale.order",
            "read_group",
            [[], ["amount_total:sum"], ["partner_id"]],
            {"limit": 3},
        )
    call.assert_called_once()
    assert call.call_args[0][1] == "formatted_read_group"
    assert call.call_args[0][2]["groupby"] == ["partner_id"]


def test_client_execute_kw_major20_never_sends_read_group_on_xmlrpc() -> None:
    cfg = ConnectionConfig(
        url="http://127.0.0.1:8069",
        db="odoo",
        username="admin",
        password="admin",
    )
    client = OdooClient(cfg)
    client.capabilities = client.capabilities.__class__(major=20, enabled=client.capabilities.enabled)
    client._uid = 1
    client._rpc_protocol = "xmlrpc"
    with patch.object(client._object, "execute_kw", return_value=[]) as xml:
        client.execute_kw(
            "res.partner",
            "read_group",
            [[], ["__count"], ["country_id"]],
        )
    assert xml.call_args[0][4] == "formatted_read_group"
