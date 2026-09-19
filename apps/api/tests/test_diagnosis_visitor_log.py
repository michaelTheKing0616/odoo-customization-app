"""full_app Diagnosis: structural Must-do + host scrub; Prefer briefs stay Contacts.

Visitor Log is one regression; Asset Checkout proves the parser is not
Visitor-shaped. Prefer / Option A host paths must stay green.
"""

from __future__ import annotations

import pytest

from app.settings import settings

pytestmark = pytest.mark.no_app_db


@pytest.fixture(autouse=True)
def _intent_llm_off(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.ai_intent_llm = "off"
    yield
    settings.ai_intent_llm = "auto"


from app.ai_conversation.understand import (  # noqa: E402
    build_understanding,
    diagnosis_clarification,
)
from app.ai_grain import (  # noqa: E402
    classify_grain,
    named_host_from_prompt,
    preferred_inherit_host,
)

VISITOR_LOG = (
    "Build a tiny Visitor Log app: model with Name, Company (link to Contact), "
    "Visit date, Purpose (selection: Meeting / Delivery / Other), and Host (Employee). "
    "Simple list + form, menu under Services. No workflow beyond create/read."
)

ASSET_CHECKOUT = (
    "Build a tiny Asset Checkout app: model with Asset name, Asset (link to Product), "
    "Checkout date, Status (selection: Out / In / Maintenance), and Custodian (Employee). "
    "Simple list + form, menu under Inventory. No workflow beyond create/read."
)

PREFER_FIELDS = (
    "On Contacts, add checkbox Preferred for delivery and Delivery notes text "
    "under Delivery group. Do not create a new app."
)
PREFER_AUTO = (
    "On res.partner, when Preferred for delivery is checked, create a light "
    "follow-up activity. Fields already exist. Inherit-only — no new app."
)
PREFER_FILTER = (
    "Preferred for delivery already exists on Contacts. Add an optional filter "
    "on Delivery/Inventory (stock.picking) lists for preferred-delivery partners. "
    "No new app tile."
)


def test_visitor_log_grain_is_full_app() -> None:
    assert classify_grain(VISITOR_LOG) == "full_app"


def test_visitor_log_does_not_steal_host_from_purpose_or_host_field() -> None:
    assert named_host_from_prompt(VISITOR_LOG) is None
    assert preferred_inherit_host(VISITOR_LOG) is None


def test_visitor_log_understanding_new_app_tile() -> None:
    u = build_understanding(VISITOR_LOG)
    assert u.grain == "full_app"
    assert u.host_model is None
    assert u.inherit_existing is False
    assert u.needs_module is False
    assert u.capability == "residual_app"
    assert "visitor" in u.title.lower()
    joined = " | ".join(u.constraints).lower()
    assert "visitor" in joined or "x_visitor" in joined
    assert "name" in joined
    assert "company" in joined and "contact" in joined
    assert "visit date" in joined or "visit" in joined
    assert "purpose" in joined and ("selection" in joined or "meeting" in joined)
    assert "host" in joined and "employee" in joined
    assert "services" in joined or "menu" in joined
    assert "list" in joined and "form" in joined
    assert "preferred for delivery" not in joined
    assert "stock.picking" not in joined
    assert not any(row.lower().startswith("on employees") for row in u.constraints)
    assert u.host_model != "hr.employee"
    card = diagnosis_clarification(u)
    assert card["kind"] == "diagnosis"
    assert card["understanding"]["inherit_existing"] is False
    assert card["understanding"]["host_model"] in (None, "", "none")


def test_visitor_log_must_do_has_visitor_model() -> None:
    u = build_understanding(VISITOR_LOG)
    blob = " | ".join(u.constraints).lower()
    assert "x_visitor_log" in blob or "visitor log" in blob


def test_asset_checkout_grain_is_full_app() -> None:
    assert classify_grain(ASSET_CHECKOUT) == "full_app"


def test_asset_checkout_does_not_steal_host_from_product_or_employee() -> None:
    assert named_host_from_prompt(ASSET_CHECKOUT) is None
    assert preferred_inherit_host(ASSET_CHECKOUT) is None


def test_asset_checkout_structural_must_do() -> None:
    """Second brief — different fields/options — no Visitor Log special cases."""
    u = build_understanding(ASSET_CHECKOUT)
    assert u.grain == "full_app"
    assert u.host_model is None
    assert u.inherit_existing is False
    assert u.needs_module is False
    assert "asset" in u.title.lower()
    joined = " | ".join(u.constraints).lower()
    assert "x_asset_checkout" in joined or "asset checkout" in joined
    assert "asset name" in joined
    assert "asset" in joined and "product" in joined
    assert "checkout date" in joined or "checkout" in joined
    assert "status" in joined and ("selection" in joined or "out" in joined)
    assert "custodian" in joined and "employee" in joined
    assert "inventory" in joined or "menu" in joined
    assert "list" in joined and "form" in joined
    assert "visitor" not in joined
    assert "purpose" not in joined
    assert "meeting" not in joined
    assert u.host_model != "hr.employee"
    assert not any(row.lower().startswith("on employees") for row in u.constraints)


def test_field_relation_scrub_any_target() -> None:
    assert named_host_from_prompt(
        "Track gear with Owner (User) and Site (link to Warehouse) fields only"
    ) is None
    assert named_host_from_prompt("On Contacts (res.partner), add a note") == "res.partner"


@pytest.mark.parametrize("prompt", [PREFER_FIELDS, PREFER_AUTO, PREFER_FILTER])
def test_prefer_briefs_still_host_res_partner(prompt: str) -> None:
    assert preferred_inherit_host(prompt) == "res.partner"
    u = build_understanding(prompt)
    assert u.host_model == "res.partner"
    assert u.inherit_existing is True
    assert u.grain == "field_pack"
    joined = " | ".join(u.constraints).lower()
    assert "contacts" in joined or "res.partner" in joined
    assert not any(row.lower().startswith("on inventory") for row in u.constraints)
