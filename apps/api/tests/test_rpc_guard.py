"""Pre-transport forbidden RPC guard on OdooClient."""

from __future__ import annotations

import pytest
from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

from app.rpc_guard import refuse_if_forbidden


def _client_with_guard() -> OdooClient:
    client = OdooClient(
        ConnectionConfig(
            url="http://127.0.0.1:9",
            db="t",
            username="u",
            password="p",
            write_mode="standard",
        )
    )
    client.rpc_guard = refuse_if_forbidden
    return client


def test_unlink_res_users_is_forbidden_before_transport() -> None:
    client = _client_with_guard()
    with pytest.raises(OdooClientError, match="forbidden"):
        client.execute_kw("res.users", "unlink", [[1]])


def test_search_read_partner_not_forbidden() -> None:
    client = _client_with_guard()
    try:
        client.execute_kw(
            "res.partner",
            "search_read",
            [[]],
            {"fields": ["name"], "limit": 1},
        )
    except OdooClientError as exc:
        assert "forbidden" not in str(exc).lower()


def test_apikeys_any_method_forbidden() -> None:
    client = _client_with_guard()
    with pytest.raises(OdooClientError, match="forbidden"):
        client.execute_kw("res.users.apikeys", "search_read", [[]], {})


def test_protected_param_in_kwargs_is_forbidden() -> None:
    client = _client_with_guard()
    with pytest.raises(OdooClientError, match="forbidden"):
        client.execute_kw(
            "ir.config_parameter",
            "write",
            [[1]],
            {"values": {"key": "database.secret", "value": "x"}},
        )
