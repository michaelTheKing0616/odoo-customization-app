"""Builtin forbidden policy cannot be disabled by leaving rpc_guard unset."""

from __future__ import annotations

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError
from odoo_client.rpc_policy import scrub_config_param_result


def _client() -> OdooClient:
    return OdooClient(
        ConnectionConfig(
            url="http://127.0.0.1:9",
            db="t",
            username="u",
            password="p",
            write_mode="standard",
        )
    )


def test_unlink_users_forbidden_without_guard() -> None:
    client = _client()
    assert client.rpc_guard is None
    try:
        client.execute_kw("res.users", "unlink", [[1]])
    except OdooClientError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("unlink of res.users reached the transport")


def test_scrub_drops_protected_config_rows() -> None:
    rows = [
        {"id": 1, "key": "web.base.url", "value": "http://secret"},
        {"id": 2, "key": "mail.catchall.domain", "value": "example.com"},
    ]
    kept = scrub_config_param_result("ir.config_parameter", "search_read", rows)
    assert kept == [{"id": 2, "key": "mail.catchall.domain", "value": "example.com"}]
    assert scrub_config_param_result("res.partner", "search_read", rows) == rows
