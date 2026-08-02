"""Live smoke: bulk create res.partner from CSV (skills/odoo-rpc-gate.md)."""

from __future__ import annotations

import os
import uuid

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

from app.data_import import dry_run_or_commit, parse_tabular, template_csv


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
        pytest.skip(f"Odoo 19 not reachable: {exc}")
    return c


@pytest.mark.integration
def test_bulk_import_partners_commit(client: OdooClient) -> None:
    suffix = uuid.uuid4().hex[:6]
    csv = (
        "name,email,phone,is_company\n"
        f"Import Smoke {suffix},smoke-{suffix}@example.com,,false\n"
    )
    headers, rows = parse_tabular(csv.encode(), "t.csv")
    mapping = {h: h for h in headers}
    dry = dry_run_or_commit(
        client,
        model="res.partner",
        rows=rows,
        mapping=mapping,
        mode="create",
        dry_run=True,
    )
    assert dry.created == 1
    live = dry_run_or_commit(
        client,
        model="res.partner",
        rows=rows,
        mapping=mapping,
        mode="create",
        dry_run=False,
    )
    assert live.ok
    assert live.created == 1
    assert live.results[0].record_id
    # cleanup
    client.execute_kw("res.partner", "unlink", [[live.results[0].record_id]])


@pytest.mark.integration
def test_template_roundtrip_parse() -> None:
    raw = template_csv("res.partner").encode()
    headers, rows = parse_tabular(raw, "partners.csv")
    assert headers and rows
