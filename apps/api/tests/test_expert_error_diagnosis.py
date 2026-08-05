"""Rule-based Expert error diagnosis tests."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.expert.error_diagnosis import try_rule_based_error_diagnosis  # noqa: E402
from app.expert.grounding import GroundingBundle  # noqa: E402


def test_model_not_found_view_validation() -> None:
    question = (
        "Diagnose this error on my connection\n\nError log:\n"
        "<Fault 2: 'Error while validating view near:\\n\\nModel not found: x_ticket'>"
    )
    result = try_rule_based_error_diagnosis(
        question,
        GroundingBundle(),
        connection_id="conn-1",
    )
    assert result is not None
    assert "x_ticket" in result["answer_markdown"]
    assert "Models & Fields" in result["answer_markdown"]
    assert result["declined"] is False
    assert "rule_based_diagnosis" in result["caution_flags"]


def test_live_model_missing_diagnostic() -> None:
    bundle = GroundingBundle(
        error_diagnostics=[
            {"model": "x_ticket", "field": None, "status": "model_missing"},
        ],
        instance_summary={"server_version": "19.0"},
    )
    result = try_rule_based_error_diagnosis(
        "Model not found: x_ticket",
        bundle,
        connection_id="conn-1",
    )
    assert result is not None
    assert "does not exist" in result["answer_markdown"]
    assert result["grounded"] is True


def test_non_error_question_returns_none() -> None:
    assert try_rule_based_error_diagnosis("How do I add a field?", GroundingBundle()) is None
