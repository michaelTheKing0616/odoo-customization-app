"""Intent matcher goldens — class-wide routes (not Prefer defaults)."""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.intent_router import route_intent
from app.intent_router.loader import reload_catalog


@pytest.fixture(autouse=True)
def _reload():
    reload_catalog()
    yield
    reload_catalog()


def _top(prompt: str) -> dict:
    r = route_intent(prompt, connection_id="c1")
    assert r["matches"], f"expected match for {prompt!r}: {r.get('message')}"
    return r["matches"][0]


def test_fx_cbn_class_routes_to_studio_not_prefer():
    top = _top("pull CBN FX rates into Accounting Automatic Currency Rates")
    assert top["feature_id"] == "studio.app"
    assert top["route"] == "studio"
    assert top["can_handle"] in {"true", "partial"}


def test_markup_tax_class_routes_to_option_a_surface_not_prefer():
    top = _top(
        "add markup percent and withholding tax compute on Sales quotations"
    )
    assert top["feature_id"] in {"studio.app", "draft.studio"}
    assert top["route"] in {"studio", "wizard"}
    assert "journal" not in top["route"]
    assert top["feature_id"] != "designer"


def test_report_layout_scrub_not_contacts_prefer():
    top = _top(
        "remove customer name from the delivery slip shipping address block"
    )
    assert top["feature_id"] == "reports.layout"
    assert top["route"] == "reports"
    assert top["feature_id"] != "designer"
    assert top["feature_id"] != "journal.master"


def test_prefer_sales_field_still_prefer_designer():
    top = _top("add a field on Sales Orders for customer PO number")
    assert top["feature_id"] == "designer"
    assert top["route"] == "designer"


def test_prefer_contacts_delivery_notes_still_designer():
    top = _top(
        "Prefer for delivery checkbox and Delivery notes on Contacts under Delivery group"
    )
    assert top["feature_id"] == "designer"
    assert top["route"] == "designer"


def test_residual_new_app_routes_studio_not_prefer():
    top = _top("build a new app for leave requests")
    assert top["feature_id"] == "studio.app"
    assert top["route"] == "studio"


def test_python_owl_cues_route_option_a_studio():
    top = _top("custom python compute and owl widget on sale.order")
    assert top["feature_id"] == "studio.app"
    assert top["route"] == "studio"


def test_residual_not_prefer_reshaped_by_report_keywords():
    """Residual app brief must not be stolen by report layout keywords alone."""
    top = _top("build a visitor log app for office check-in requests")
    assert top["feature_id"] == "studio.app"
    assert top["route"] == "studio"
