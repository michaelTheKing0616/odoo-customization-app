"""Live RPC smoke — TIER-1 capability matrix on Docker Odoo 19."""

from __future__ import annotations

import os

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

from app.capabilities import probe_web_base_url, sample_installed_modules, tier_matrix_response
from app.tier_matrix import TierCapabilityKey


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@pytest.fixture(scope="module")
def client() -> OdooClient:
    config = ConnectionConfig(
        url=_env("ODOO_URL", "http://127.0.0.1:8069"),
        db=_env("ODOO_DB", "odoo_dev"),
        username=_env("ODOO_USER", "admin"),
        password=_env("ODOO_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 19 not reachable for TIER-1 smoke: {exc}")
    version = c.server_version()
    if not str(version.get("server_version", "")).startswith("19"):
        pytest.skip(f"Expected Odoo 19, got {version.get('server_version')}")
    return c


@pytest.mark.integration
def test_capability_matrix_live_odoo19(client: OdooClient) -> None:
    version = client.server_version()
    server_version = str(version.get("server_version") or "")
    mods = sample_installed_modules(client, limit=80)
    web_base_url = probe_web_base_url(client)
    matrix = tier_matrix_response(
        connection_id="live-smoke",
        url=_env("ODOO_URL", "http://127.0.0.1:8069"),
        server_version=server_version,
        installed_modules=mods,
        web_base_url=web_base_url,
        use_cache=False,
    )
    assert matrix is not None
    assert matrix.hosting == "onprem"
    assert matrix.edition == "community"
    assert matrix.major == 19
    keys = {c.key for c in matrix.capabilities}
    assert TierCapabilityKey.DIRECT_SQL.value in keys
    deploy = next(c for c in matrix.capabilities if c.key == TierCapabilityKey.MODULE_DEPLOY.value)
    assert deploy.available == "yes"
    sql = next(c for c in matrix.capabilities if c.key == TierCapabilityKey.DIRECT_SQL.value)
    assert sql.available == "no"
