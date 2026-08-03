"""Conditional live Enterprise driver verification (TIER-5).

Set ODOO_EE_TEST_URL (+ DB/user/password env vars) to run against a real EE instance.
"""

from __future__ import annotations

import os

import pytest

EE_URL = os.environ.get("ODOO_EE_TEST_URL", "").strip()
EE_DB = os.environ.get("ODOO_EE_TEST_DB", "").strip()
EE_USER = os.environ.get("ODOO_EE_TEST_USER", "admin").strip()
EE_PASSWORD = os.environ.get("ODOO_EE_TEST_PASSWORD", "").strip()

pytestmark = pytest.mark.skipif(
    not EE_URL or not EE_DB or not EE_PASSWORD,
    reason="ODOO_EE_TEST_URL/DB/PASSWORD not configured — live EE verification skipped",
)


@pytest.fixture
def ee_client():
    from odoo_client import ConnectionConfig, OdooClient

    client = OdooClient(
        ConnectionConfig(url=EE_URL, db=EE_DB, username=EE_USER, password=EE_PASSWORD)
    )
    client.connect()
    return client


def test_live_approval_rule_model_probe(ee_client) -> None:
    from app.ee_drivers import probe_approval_rules_driver

    status = probe_approval_rules_driver(ee_client)
    if not status.available:
        pytest.skip(f"studio.approval.rule unavailable: {status.reason}")
    assert status.verify_state in {"live", "pending-live"}
    assert len(status.verified_fields) >= 1
