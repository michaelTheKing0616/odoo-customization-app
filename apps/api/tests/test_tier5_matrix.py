"""TIER-5 matrix gating tests."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)

from app.tier_matrix import (  # noqa: E402
    TierCapabilityKey,
    build_tier_context,
    evaluate_tier_matrix,
)


def test_ee_playbook_matrix_keys_present() -> None:
    ctx = build_tier_context(
        url="http://127.0.0.1:8069",
        server_version="19.0+e",
        installed_modules=["sign", "documents", "spreadsheet_dashboard"],
    )
    caps = evaluate_tier_matrix(ctx)
    keys = {c.key for c in caps}
    assert TierCapabilityKey.EE_PLAYBOOK_SIGN.value in keys
    assert TierCapabilityKey.EE_PLAYBOOK_DOCUMENTS.value in keys
    assert TierCapabilityKey.EE_PLAYBOOK_SPREADSHEET.value in keys


def test_ee_playbook_sign_no_when_module_absent() -> None:
    ctx = build_tier_context(url="http://127.0.0.1:8069", server_version="19.0", installed_modules=["base"])
    caps = evaluate_tier_matrix(ctx)
    sign = next(c for c in caps if c.key == TierCapabilityKey.EE_PLAYBOOK_SIGN.value)
    assert sign.available == "no"


def test_enterprise_view_types_yes_on_ee() -> None:
    ee = build_tier_context(url="http://127.0.0.1:8069", server_version="19.0+e")
    comm = build_tier_context(url="http://127.0.0.1:8069", server_version="19.0")
    ee_cap = next(
        c for c in evaluate_tier_matrix(ee) if c.key == TierCapabilityKey.VIEWS_ENTERPRISE_TYPES.value
    )
    comm_cap = next(
        c for c in evaluate_tier_matrix(comm) if c.key == TierCapabilityKey.VIEWS_ENTERPRISE_TYPES.value
    )
    assert ee_cap.available == "yes"
    assert comm_cap.available == "no"
