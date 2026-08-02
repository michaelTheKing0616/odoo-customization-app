"""Unit/live helper: Power Ops capability probe against optional Odoo 18."""

from __future__ import annotations

import os

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError


def _client18() -> OdooClient:
    config = ConnectionConfig(
        url=os.environ.get("ODOO18_URL", "http://127.0.0.1:8070"),
        db=os.environ.get("ODOO18_DB", "odoo18_dev"),
        username=os.environ.get("ODOO18_USER", "admin"),
        password=os.environ.get("ODOO18_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 18 not reachable: {exc}")
    return c


@pytest.mark.integration
def test_power_ops_recipes_available_after_account() -> None:
    """Requires account installed on odoo18_dev (see init / ensure_module_installed)."""
    from app.power_ops_recipes import probe_connection_capabilities

    client = _client18()
    try:
        client.ensure_module_installed("account")
    except OdooClientError as exc:
        pytest.skip(f"Cannot install account on Odoo 18: {exc}")

    probe = probe_connection_capabilities(client)
    recipes = probe["power_ops_recipes"]
    assert recipes
    unavailable = [r for r in recipes if not r["available"]]
    assert not unavailable, f"Unexpected unavailable recipes: {unavailable}"
    assert any(r["id"] == "purge_journal_entries" and r["available"] for r in recipes)
