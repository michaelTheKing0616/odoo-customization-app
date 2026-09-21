"""full_app Must-do hygiene — Vehicle Request golden + Create/Make siblings + Visitor Log.

Root mandate (all residual / full_app briefs, not Vehicle-only):
1. Strip leading imperatives (Build/Create/Make/…) from app noun / model / title.
2. Never emit Python/dict/JSON reprs into Must-do.
3. Date range → Start Date + End Date.
4. «Menu under A or B — pick natural» → one domain-natural parent (Fleet for vehicle).
5. Workflow approve/refuse → structured selection + buttons.
6. Optional assignment note → one Text field on primary (not M2O+text dual).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.no_app_db

os.environ["AI_INTENT_LLM"] = "off"

from app.ai_constraint_ast import ast_to_must_do, parse_det  # noqa: E402
from app.ai_conversation.understand import build_understanding  # noqa: E402
from app.ai_document_shape import naming_from_residual  # noqa: E402

VEHICLE_PROMPT = (
    "Build Vehicle request: employees request a fleet vehicle for a date range; "
    "manager approve/refuse; on approve, optionally link/create a Fleet vehicle assignment note. "
    "List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet or HR — pick the more natural parent."
)

VISITOR_LOG = (
    "Build a tiny Visitor Log app: model with Name, Company (link to Contact), "
    "Visit date, Purpose (selection: Meeting / Delivery / Other), and Host (Employee). "
    "Simple list + form, menu under Services. No workflow beyond create/read."
)


def _vehicle_prompt(verb: str) -> str:
    return VEHICLE_PROMPT.replace("Build", verb, 1)


@pytest.mark.parametrize("verb", ["Build", "Create", "Make"])
def test_vehicle_request_naming_strips_imperative(verb: str) -> None:
    display, slug = naming_from_residual(_vehicle_prompt(verb))
    assert display == "Vehicle Request"
    assert slug == "vehicle_request"
    assert verb.lower() not in display.lower()
    assert verb.lower() not in slug


@pytest.mark.parametrize("verb", ["Build", "Create", "Make"])
def test_vehicle_request_must_do_structured(verb: str) -> None:
    prompt = _vehicle_prompt(verb)
    u = build_understanding(prompt)
    assert u.grain == "full_app"
    assert u.host_model is None
    assert u.title == "Vehicle Request"
    assert verb.lower() not in u.title.lower()

    joined = " | ".join(u.constraints)
    low = joined.lower()
    assert "x_vehicle_request" in low
    assert "vehicle request" in low
    assert "start date" in low and "end date" in low
    assert "state" in low and "draft" in low and "submitted" in low
    assert "approve" in low or "refuse" in low
    assert "assignment note" in low
    assert "menu under fleet" in low
    assert "fleet or hr" not in low
    assert "menu under hr" not in low
    # No imperative glued into model slug / raw prompt dump / dict leak
    assert f"x_{verb.lower()}_vehicle" not in low
    assert "employees request a fleet vehicle" not in low
    assert "host_model" not in low
    assert "{" not in joined
    assert "pick the more natural" not in low

    ast = parse_det(prompt, inherit=False, grain="full_app")
    assert ast.model_id == "x_vehicle_request"
    assert ast.model_label == "Vehicle Request"
    labels = {f.label.lower() for f in ast.fields}
    assert "start date" in labels and "end date" in labels
    assert "state" in labels
    assert any("fleet" in s.lower() and "or" not in s.lower() for s in ast.structural)


def test_vehicle_request_expected_clean_must_do_shape() -> None:
    rows = ast_to_must_do(parse_det(VEHICLE_PROMPT, inherit=False, grain="full_app"))
    assert rows[0] == "New model x_vehicle_request (Vehicle Request)"
    blob = " | ".join(rows).lower()
    assert "employee→employee" in blob or "employee" in blob
    assert "vehicle→fleet vehicle" in blob
    assert "start date" in blob and "end date" in blob
    assert "state selection" in blob
    # One materialization: free-text Assignment Note (not M2O arrow + text).
    assert "text field: assignment note" in blob
    assert "assignment note→" not in blob
    assert "menu under fleet" in blob
    assert all("{" not in r and "host_model" not in r.lower() for r in rows)


def test_visitor_log_regression_untouched() -> None:
    u = build_understanding(VISITOR_LOG)
    assert u.grain == "full_app"
    assert u.title == "Visitor Log"
    joined = " | ".join(u.constraints).lower()
    assert "x_visitor_log" in joined
    assert "name" in joined
    assert "company" in joined and "contact" in joined
    assert "purpose" in joined
    assert "services" in joined
    assert "build" not in u.title.lower()
