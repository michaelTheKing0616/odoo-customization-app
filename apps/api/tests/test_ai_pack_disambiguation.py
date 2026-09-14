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


def test_invoice_sla_field_is_not_restaurant_pack() -> None:
    from app.ai_domain_packs import match_domain_pack

    prompt = (
        "Single extra field on customer invoices: SLA due date and time. "
        "Do not create a new Invoices app. Cashiers shouldn't see a new menu."
    )
    assert match_domain_pack(prompt) is None
    assert retrieve_domain_pack_lexical(prompt) is None


VISITOR_LOG_PROMPT = (
    "Front desk still uses a paper book. I want a simple visitor log in Odoo: "
    "visitor name, who they came to see (an employee), purpose, time in, time out, "
    "optional ID number. This is not CRM and not a second Contacts app — the host "
    "is an Employee, the visitor can just be a name unless they're already a contact. "
    "We're a 40-person office in Accra. Don't invent invoicing. Mail notifications "
    "if someone sits in reception more than two hours would be nice but only if "
    "that's safe no-code, not Python."
)


def test_office_visitor_log_is_not_hotel_pack() -> None:
    from app.ai_domain_packs import match_domain_pack

    assert match_domain_pack(VISITOR_LOG_PROMPT) is None
    assert retrieve_domain_pack_lexical(VISITOR_LOG_PROMPT) is None


def test_subscription_and_project_tracker_distinct() -> None:
    sub = retrieve_domain_pack_lexical("SaaS membership subscription renewal workflow")
    proj = retrieve_domain_pack_lexical("Project tracker with milestones and time entries")
    assert sub is not None and sub[0] == "subscription"
    assert proj is not None and proj[0] == "project_tracker"
