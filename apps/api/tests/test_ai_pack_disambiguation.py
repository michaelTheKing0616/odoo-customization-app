"""Disambiguation — hotel vs real_estate vs restaurant prompts."""

from __future__ import annotations

from app.ai_domain_packs import retrieve_domain_pack_lexical


def test_hotel_prompt_not_real_estate_or_restaurant() -> None:
    hit = retrieve_domain_pack_lexical(
        "Hotel PMS front desk check-in workflow with housekeeping for guest rooms"
    )
    assert hit is not None
    assert hit[0] == "hotel"


def test_real_estate_prompt_not_hotel_or_restaurant() -> None:
    hit = retrieve_domain_pack_lexical(
        "Real estate unit lease management with property viewings and tenant deposits"
    )
    assert hit is not None
    assert hit[0] == "real_estate"


def test_restaurant_prompt_not_hotel_or_real_estate() -> None:
    hit = retrieve_domain_pack_lexical(
        "Restaurant dining menu with kitchen order tickets and table reservations"
    )
    assert hit is not None
    assert hit[0] == "restaurant"


def test_subscription_and_project_tracker_distinct() -> None:
    sub = retrieve_domain_pack_lexical("SaaS membership subscription renewal workflow")
    proj = retrieve_domain_pack_lexical("Project tracker with milestones and time entries")
    assert sub is not None and sub[0] == "subscription"
    assert proj is not None and proj[0] == "project_tracker"
