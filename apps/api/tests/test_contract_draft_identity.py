"""Contract ↔ draft identity — no Visitor Log banner on Restaurant draft."""

from __future__ import annotations


import pytest

pytestmark = pytest.mark.no_app_db

from app.ai_conversation.understand import (
    Understanding,
    attach_understanding,
    reconcile_contract_with_draft,
    understanding_contradictions,
)


def test_reconcile_visitor_contract_on_restaurant_draft() -> None:
    draft = {
        "display_name": "Restaurant Management",
        "grain": "full_app",
        "models": [{"model": "x_dining_table", "mode": "new", "fields": []}],
    }
    locked = Understanding(
        capability="residual_app",
        grain="full_app",
        host_model=None,
        inherit_existing=False,
        title="Visitor Log",
        summary="Old session IR",
        source="locked",
    )
    rebuilt = reconcile_contract_with_draft(draft, locked)
    assert rebuilt.title == "Restaurant Management"
    assert rebuilt.host_model is None
    assert rebuilt.grain == "full_app"
    assert rebuilt.source == "reconciled_draft"


def test_attach_understanding_rebuilds_mismatched_contract() -> None:
    draft = {
        "display_name": "Dining Tables",
        "grain": "full_app",
        "models": [{"model": "x_dining_table", "mode": "new", "fields": []}],
        "_user_prompt": "Dining Tables for our restaurant. Name, Capacity, Status.",
    }
    # Locked Visitor Log block in prompt would normally win — reconcile to draft.
    prompt = (
        "Dining Tables for our restaurant.\n\n"
        "## Diagnosis (locked)\n"
        "- Host: none\n"
        "- Inherit existing form: no\n"
        "- Needs module: no\n"
        "- Capability: residual_app\n"
        "- Title: Visitor Log\n"
        "- Gold: none\n"
    )
    attach_understanding(draft, prompt)
    u = draft["_understanding"]
    assert u["title"] == "Dining Tables"
    assert u.get("host_model") in (None, "", "none") or not u.get("host_model")


def test_prefer_contacts_inherit_contract_kept() -> None:
    draft = {
        "display_name": "Contacts field",
        "grain": "field_pack",
        "models": [{"model": "res.partner", "mode": "inherit", "fields": []}],
    }
    locked = Understanding(
        capability="residual_app",
        grain="field_pack",
        host_model="res.partner",
        inherit_existing=True,
        title="Contacts field",
        source="locked",
    )
    out = reconcile_contract_with_draft(draft, locked)
    assert out.host_model == "res.partner"
    assert out.inherit_existing is True
    assert out.title == "Contacts field"


def test_contradiction_flags_title_mismatch_before_reconcile() -> None:
    draft = {
        "display_name": "Restaurant Management",
        "grain": "full_app",
        "models": [{"model": "x_order", "mode": "new", "fields": []}],
    }
    locked = Understanding(
        title="Visitor Log",
        grain="full_app",
        inherit_existing=False,
        capability="residual_app",
    )
    findings = understanding_contradictions(draft, locked)
    assert any("does not match draft" in f for f in findings)
