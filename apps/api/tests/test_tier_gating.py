"""TIER-2 gating messages and tier combos."""

from __future__ import annotations

import pytest

from app.tier_gating import (
    automations_gating,
    approvals_gating,
    deployment_panel,
    gating_context_for_connection,
    online_python_promote_gating,
    sandbox_approximation_label,
)
from app.tier_matrix import TierCapabilityKey, build_tier_context, evaluate_tier_matrix


@pytest.mark.parametrize(
    ("url", "modules", "hosting", "auto_available"),
    [
        ("http://127.0.0.1:8069", ["base_automation"], "onprem", True),
        ("http://127.0.0.1:8069", ["base"], "onprem", False),
        ("https://x.odoo.com", ["base"], "online", False),
        ("https://x.odoo.sh", ["base_automation"], "sh", True),
    ],
)
def test_automations_gating_per_hosting(
    url: str, modules: list[str], hosting: str, auto_available: bool
) -> None:
    ctx = build_tier_context(url=url, server_version="19.0", installed_modules=modules)
    assert ctx.hosting == hosting
    gate = automations_gating(ctx)
    assert gate.available is auto_available
    if not auto_available:
        assert gate.title.startswith("Automations aren't available")
        assert len(gate.options) == 3
        assert len(gate.choices) >= 2


def test_online_gating_copy_guide_exact_why() -> None:
    ctx = build_tier_context(
        url="https://tenant.odoo.com", server_version="19.0", installed_modules=["base"]
    )
    gate = automations_gating(ctx)
    assert "Odoo Online" in gate.why
    assert "Custom plan" in gate.why
    assert any("Upgrade" in o for o in gate.options)


def test_onprem_gating_install_module_option() -> None:
    ctx = build_tier_context(
        url="http://127.0.0.1:8069", server_version="19.0", installed_modules=["base"]
    )
    gate = automations_gating(ctx)
    assert any(c.id == "install_module" for c in gate.choices)


def test_approvals_community_unavailable() -> None:
    ctx = build_tier_context(url="http://127.0.0.1:8069", server_version="19.0")
    gate = approvals_gating(ctx)
    assert gate.available is False
    assert "Enterprise" in gate.why


def test_deployment_panel_sh_includes_doc_flag() -> None:
    ctx = build_tier_context(url="https://proj.odoo.sh", server_version="19.0")
    panel = deployment_panel(ctx, technical_name="demo_mod")
    assert panel["tier"] == "sh"
    assert panel["include_deploy_doc"] is True


def test_deployment_panel_online_portable() -> None:
    ctx = build_tier_context(url="https://x.odoo.com", server_version="19.0")
    panel = deployment_panel(ctx)
    assert panel["tier"] == "online"
    assert "metadata/data" in panel["body"]


def test_online_python_promote_gating() -> None:
    gate = online_python_promote_gating()
    assert gate.available is False
    assert "Odoo Online" in gate.why


def test_sandbox_approximation_label_includes_major() -> None:
    label = sandbox_approximation_label(19)
    assert "19" in label
    assert "Approximate validation" in label
