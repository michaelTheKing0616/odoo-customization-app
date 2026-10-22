"""Edition detection: Odoo Enterprise (incl. Online) must never read as Community."""

from __future__ import annotations

import pytest

from app.capabilities import capabilities_from_version
from app.expert.grounding import _edition_from_version
from app.stock_app_install import InstallFacts, match_stock_app, proposal_for
from app.tier_matrix import build_tier_context, detect_edition


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("20.0+e", "enterprise"),
        ("saas~19.2+e", "enterprise"),
        ("saas~20.1+e", "enterprise"),
        ("19.0+e-20250802", "enterprise"),
        ("20.0", "community"),
        ("19.0", "community"),
        (None, "unknown"),
        ("", "unknown"),
        ("garbage", "unknown"),
    ],
)
def test_detect_edition_from_server_version(version, expected):
    assert detect_edition(version) == expected


def test_server_version_info_final_e_is_enterprise():
    assert detect_edition("20.0", server_version_info=[20, 0, 0, "final", 0, "e"]) == "enterprise"
    assert detect_edition("20.0", server_version_info=(20, 0, 0, "final", 0, "")) == "community"


def test_web_enterprise_installed_is_enterprise():
    assert detect_edition("20.0", {"base", "web_enterprise"}) == "enterprise"


def test_odoo_online_host_is_always_enterprise():
    assert detect_edition("20.0", url="https://acme.odoo.com") == "enterprise"
    assert detect_edition(None, url="https://acme.odoo.com") == "enterprise"
    assert detect_edition("20.0", url="https://erp.example.com") == "community"
    ctx = build_tier_context(url="https://acme.odoo.com", server_version="20.0")
    assert ctx.edition == "enterprise"


def test_capability_matrix_reports_enterprise_for_plus_e_and_online():
    plus_e = capabilities_from_version("19.0+e", url="https://erp.example.com")
    assert plus_e.edition == "enterprise"
    assert capabilities_from_version("19.0", url="https://acme.odoo.com").edition == "enterprise"
    assert capabilities_from_version("19.0", url="https://erp.example.com").edition == "community"


def test_grounding_edition_uses_shared_detector():
    assert _edition_from_version("20.0+e") == "enterprise"
    assert _edition_from_version("20.0", "https://acme.odoo.com") == "enterprise"
    assert _edition_from_version(None) == "unknown"


def _helpdesk():
    match = match_stock_app("add a priority field to helpdesk tickets")
    assert match is not None and not match.app.is_community
    return match


def test_enterprise_app_offered_on_enterprise_db():
    facts = InstallFacts(model_present=False, module_state="uninstalled", edition="enterprise")
    proposal = proposal_for(_helpdesk(), facts)
    assert proposal is not None and proposal.installable
    assert "Community" not in proposal.question


def test_enterprise_app_unknown_edition_not_refused_as_community():
    match = _helpdesk()
    offered = proposal_for(match, InstallFacts(model_present=False, module_state="uninstalled"))
    assert offered is not None and offered.installable
    missing = proposal_for(match, InstallFacts(model_present=False, module_state=None))
    assert missing is not None and not missing.installable
    assert "Community" not in missing.question


def test_enterprise_app_refused_on_confirmed_community():
    facts = InstallFacts(model_present=False, module_state=None, edition="community")
    proposal = proposal_for(_helpdesk(), facts)
    assert proposal is not None and not proposal.installable
    assert "cannot be installed on Community" in proposal.question
