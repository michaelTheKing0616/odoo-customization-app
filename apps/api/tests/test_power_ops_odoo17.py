"""Live Power Ops dry-runs against optional Docker Odoo 17 (:8071).

Skip when the stack is down. Accounting recipe runs only if `account` / account.move
is present (see ``./docker/ensure-account-17.sh``).
"""

from __future__ import annotations

import os

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError


def _client17() -> OdooClient:
    config = ConnectionConfig(
        url=os.environ.get("ODOO17_URL", "http://127.0.0.1:8071"),
        db=os.environ.get("ODOO17_DB", "odoo17_dev"),
        username=os.environ.get("ODOO17_USER", "admin"),
        password=os.environ.get("ODOO17_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 17 not reachable: {exc}")
    if c.capabilities.major != 17:
        pytest.skip(f"Expected major 17, got {c.capabilities.major}")
    return c


def _account_installed(client: OdooClient) -> bool:
    if not client.model_exists("account.move"):
        return False
    row = client.get_module_state("account")
    return bool(row and row.get("state") in {"installed", "to upgrade", "to remove"})


@pytest.mark.integration
def test_power_ops_dry_run_generic_archive_odoo17() -> None:
    from app.power_ops_recipes import run_recipe

    client = _client17()
    result = run_recipe(
        client,
        recipe_id="mass_archive",
        model="res.partner",
        domain=[("id", "=", -1)],
        dry_run=True,
    )
    assert result.ok, result.message
    assert result.dry_run
    assert result.available
    assert result.processed == 0


@pytest.mark.integration
def test_power_ops_dry_run_accounting_when_account_odoo17() -> None:
    from app.power_ops_recipes import run_recipe

    client = _client17()
    if not _account_installed(client):
        pytest.skip(
            "account not installed on Odoo 17 — run ./docker/ensure-account-17.sh"
        )

    result = run_recipe(
        client,
        recipe_id="purge_journal_entries",
        domain=[("id", "=", -1)],
        dry_run=True,
    )
    assert result.ok, result.message
    assert result.dry_run
    assert result.available
    assert result.processed == 0
