"""Migration assist panel tests (TIER-3)."""

from __future__ import annotations

from app.migration_assist import migration_assist_for_connection
from app.tier_matrix import build_tier_context


def test_migration_assist_online_shows_unlocks() -> None:
    ctx = build_tier_context(
        url="https://tenant.odoo.com",
        server_version="19.0",
        installed_modules=["base"],
    )
    panel = migration_assist_for_connection(
        url="https://tenant.odoo.com",
        server_version="19.0",
        installed_modules=["base"],
    )
    assert panel.eligible is True
    assert ctx.hosting == "online"
    keys = {u.key for u in panel.unlocks}
    assert "module_deploy" in keys
    assert "python_module_install" in keys
    assert "sandbox_parity" in keys


def test_migration_assist_onprem_not_eligible() -> None:
    panel = migration_assist_for_connection(
        url="http://127.0.0.1:8069",
        server_version="19.0",
    )
    assert panel.eligible is False
