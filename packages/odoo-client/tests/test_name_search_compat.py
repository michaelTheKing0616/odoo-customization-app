"""name_search execute_kw / JSON-2 mapping follows the version table."""

from __future__ import annotations

from odoo_client.compat.name_search import build_name_search_execute_kw
from odoo_client.transport.execute_kw_map import execute_kw_to_json2_body


def test_name_search_major18_execute_kw_uses_args_not_domain_kw() -> None:
    args, kwargs = build_name_search_execute_kw("Acme", major=18, limit=2)
    assert args == ["Acme"]
    assert kwargs == {"limit": 2}
    assert "domain" not in kwargs


def test_name_search_major20_execute_kw_uses_domain_kw() -> None:
    args, kwargs = build_name_search_execute_kw("Acme", major=20, limit=2)
    assert args == ["Acme"]
    assert kwargs == {"limit": 2, "domain": []}
    assert "args" not in kwargs


def test_name_search_major18_json2_body_maps_second_positional_to_args() -> None:
    body = execute_kw_to_json2_body(
        "name_search",
        ["Acme", [("active", "=", True)]],
        {"limit": 2},
        major=18,
    )
    assert body["name"] == "Acme"
    assert body["args"] == [("active", "=", True)]
    assert "domain" not in body


def test_name_search_major20_json2_body_uses_domain_from_kwargs() -> None:
    body = execute_kw_to_json2_body(
        "name_search",
        ["Acme"],
        {"limit": 2, "domain": []},
        major=20,
    )
    assert body["name"] == "Acme"
    assert body["domain"] == []
    assert "args" not in body
