"""AI-9 live smoke — project installed, overlap finding for task tracker prompt."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")

from app.ai_overlap import check_overlap  # noqa: E402


@pytest.mark.integration
def test_overlap_live_project_installed_finding() -> None:
    if not os.environ.get("ODOO_URL"):
        pytest.skip("ODOO_URL not set")
    from odoo_client import ConnectionConfig, OdooClient

    client = OdooClient(
        ConnectionConfig(
            url=os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            db=os.environ.get("ODOO_DB", "odoo_dev"),
            username=os.environ.get("ODOO_USER", "admin"),
            password=os.environ.get("ODOO_PASSWORD", "admin"),
        )
    )
    try:
        client.connect()
        client.ensure_module_installed("project")
        installed = [
            str(r["name"])
            for r in client.execute_kw(
                "ir.module.module",
                "search_read",
                [[("state", "=", "installed")]],
                {"fields": ["name"], "limit": 500},
            )
        ]
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Odoo unavailable: {exc}")

    result = check_overlap(
        "track tasks per client",
        grain="full_app",
        installed_modules=installed,
        client=client,
        connection_id="live",
        semantic_fn=lambda _p, xs: xs,
    )
    assert any(f["source"] == "installed_module" and "project" in f["id"] for f in result["findings"])
