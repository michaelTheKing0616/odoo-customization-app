"""Tests for view xpath guidance and answer relevance guards."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.expert.answer_relevance import (  # noqa: E402
    answer_matches_question,
    conversation_is_on_topic,
)
from app.expert.grounding import GroundingBundle  # noqa: E402
from app.expert.view_guidance import (  # noqa: E402
    looks_like_view_inheritance_question,
    try_rule_based_view_guidance,
)

XPATH_Q = (
    "I need to add a readonly x_contract_ref char field to the sale order form below "
    "partner_id without breaking Studio-inherited views. What xpath position should I "
    "use, and what are the failure modes if the anchor node is missing on Odoo 19?"
)

ACCESS_Q = (
    "A user gets AccessError writing x_matter but can read it. Walk me through "
    "checking ir.model.access vs record rules."
)


def test_view_question_detected() -> None:
    assert looks_like_view_inheritance_question(XPATH_Q)
    assert not looks_like_view_inheritance_question("What is xpath inheritance?")


def test_view_guidance_mentions_xpath_and_partner() -> None:
    payload = try_rule_based_view_guidance(
        XPATH_Q,
        GroundingBundle(instance_summary={"server_version": "19.0"}),
        connection_id="c1",
    )
    assert payload is not None
    body = payload["answer_markdown"]
    assert "xpath" in body.lower()
    assert "partner_id" in body
    assert 'position="after"' in body


def test_rejects_prompt_example_echo() -> None:
    bad = "Install **Contacts** for students [1].\n\nUse **CRM** for admissions [1]."
    assert not answer_matches_question(XPATH_Q, bad)


def test_rejects_access_leak_on_xpath_question() -> None:
    bad = (
        "Odoo evaluates access control: ir.model.access [1]. Record rules ir.rule [2]. "
        "When AccessError writing x_matter..."
    )
    assert not answer_matches_question(XPATH_Q, bad)


def test_conversation_topic_drift_dropped() -> None:
    history = [
        {"role": "user", "content": ACCESS_Q},
        {"role": "assistant", "content": "Check ir.model.access first."},
    ]
    assert not conversation_is_on_topic(XPATH_Q, history)


def test_conversation_same_topic_kept() -> None:
    history = [{"role": "user", "content": "How do I xpath inherit sale order form views?"}]
    assert conversation_is_on_topic(XPATH_Q, history)


def test_setup_question_drops_conversation_history() -> None:
    history = [
        {"role": "user", "content": "library management Odoo DB setup"},
        {"role": "assistant", "content": "Install CRM and website for library"},
    ]
    q = "What do I need to setup an oil and gas company's internal management Odoo DB?"
    assert not conversation_is_on_topic(q, history)


def test_answer_rejects_real_estate_for_oil_gas_question() -> None:
    q = "What do I need to setup an oil and gas company's internal management Odoo DB?"
    bad = "To implement a custom real estate management system, install CRM and website [1]."
    assert not answer_matches_question(q, bad)
