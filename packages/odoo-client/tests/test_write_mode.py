"""Observer write-mode guard tests."""

from __future__ import annotations

import pytest

from odoo_client.client import ObserverModeError, OdooClient
from odoo_client.models import ConnectionConfig
from odoo_client.write_mode import observer_allows_method


def test_observer_allows_read_methods() -> None:
    for method in ("search_read", "read", "fields_get", "search_count"):
        assert observer_allows_method(method) is True


def test_observer_blocks_mutations() -> None:
    for method in ("create", "write", "unlink", "copy"):
        assert observer_allows_method(method) is False


def test_observer_blocks_action_prefix() -> None:
    assert observer_allows_method("action_confirm") is False
    assert observer_allows_method("button_install") is False


def test_execute_kw_refuses_mutation_in_observer_without_network() -> None:
    client = OdooClient(
        ConnectionConfig(
            url="http://127.0.0.1:8069",
            db="odoo",
            username="admin",
            password="admin",
            write_mode="observer",
        )
    )
    client._uid = 1
    with pytest.raises(ObserverModeError):
        client.execute_kw("res.partner", "write", [[1], {"name": "x"}])


def test_execute_kw_allows_search_read_in_observer_without_network() -> None:
    client = OdooClient(
        ConnectionConfig(
            url="http://127.0.0.1:8069",
            db="odoo",
            username="admin",
            password="admin",
            write_mode="observer",
        )
    )
    client._uid = 1

    class FakeObject:
        def execute_kw(self, *args, **kwargs):
            return [{"id": 1}]

    client._object = FakeObject()
    rows = client.execute_kw("res.partner", "search_read", [[]], {"fields": ["name"], "limit": 1})
    assert rows == [{"id": 1}]


def test_standard_mode_does_not_block_before_rpc() -> None:
    client = OdooClient(
        ConnectionConfig(
            url="http://127.0.0.1:8069",
            db="odoo",
            username="admin",
            password="admin",
            write_mode="standard",
        )
    )
    client._uid = 1

    class FakeObject:
        def execute_kw(self, *args, **kwargs):
            return 42

    client._object = FakeObject()
    assert client.execute_kw("res.partner", "write", [[1], {"name": "x"}]) == 42
