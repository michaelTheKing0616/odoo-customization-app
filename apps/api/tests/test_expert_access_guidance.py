"""Tests for access guidance and model lookup false-positive guards."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.expert.access_guidance import try_rule_based_access_guidance  # noqa: E402
from app.expert.grounding import GroundingBundle  # noqa: E402
from app.expert.model_lookup import (  # noqa: E402
    looks_like_model_name_question,
    try_rule_based_model_lookup,
)


def test_access_error_question_not_model_lookup() -> None:
    q = (
        "A user gets AccessError writing x_matter but can read it. Walk me through "
        "checking ir.model.access vs record rules vs field-level groups — "
        "in what order does Odoo evaluate them?"
    )
    assert not looks_like_model_name_question(q)
    assert try_rule_based_model_lookup(q, GroundingBundle()) is None


def test_access_guidance_covers_evaluation_order() -> None:
    q = (
        "A user gets AccessError writing x_matter but can read it. Walk me through "
        "checking ir.model.access vs record rules — in what order does Odoo evaluate them?"
    )
    payload = try_rule_based_access_guidance(
        q,
        GroundingBundle(instance_summary={"server_version": "19.0"}),
        connection_id="c1",
    )
    assert payload is not None
    body = payload["answer_markdown"]
    assert "ir.model.access" in body
    assert "ir.rule" in body
    assert "x_matter" in body
    assert "perm_write" in body


def test_contacts_model_question_still_matches() -> None:
    q = "what's the model for contacts called in Odoo?"
    assert looks_like_model_name_question(q)
