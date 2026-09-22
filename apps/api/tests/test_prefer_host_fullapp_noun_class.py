"""Class-wide Prefer host lock + full_app business-noun naming.

Failure classes (Tope mandate — architectural, not domain-hard):
A) Prefer/Extend on Project must Prefer-lock project.project; linked Sales Order
   warnings must NOT steal host onto sale.order; Online-safe phase+cap; Option A
   honesty only for Python bits — never residual_app tile for this Extend.
B) Residual full_app Diagnosis Name / model from brief BUSINESS NOUN — never
   Studio grain words Full / New / Prefer / Extend / full_app → x_full.
"""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_constraint_ast import ast_to_must_do, parse_det  # noqa: E402
from app.ai_conversation.understand import build_understanding  # noqa: E402
from app.ai_document_shape import naming_from_residual  # noqa: E402
from app.ai_grain import (  # noqa: E402
    classify_grain,
    named_host_from_prompt,
    preferred_inherit_host,
)

PROJECT_COMMERCIAL = (
    "For professional-services firms: on Project, add Commercial phase "
    "(Discovery / Delivery / Hypercare / Closed) and Billable cap (hours). "
    "On project form, show actual hours vs cap (read-only from existing "
    "timesheet/project hours if available). When phase moves to Hypercare, "
    "require a linked Sales Order or show a clear warning. Extend stock "
    "Project/Sale — no second PM suite. Say what’s Online-safe vs what needs "
    "Option A / sh if Python is required."
)

FIELD_WORK_ORDERS = (
    "Build Field work orders a mid-market firm could sell next to Odoo: "
    "Work order: Customer (Contact), Related Sales Order (optional), "
    "Asset/Vehicle (Fleet, optional), Scheduled slot, Priority, State "
    "(Draft → Scheduled → In progress → Done → Invoiced); Checklist lines; "
    "Parts used; Sign-off; Menus list/kanban/calendar; consultant handoff note; "
    "prefer working Online metadata over fake Studio parity."
)

TOPE_SALES_PREFER = (
    "Extend Sales Orders: add Customer PO reference and Required delivery window "
    "(start and end dates). Show a status hint when PO is set but delivery window "
    "is incomplete. Do not create a new app — inherit sale.order. Place under Other "
    "Info / Documents."
)

VEHICLE_REQUEST = (
    "Build Vehicle request: employees request a fleet vehicle for a date range; "
    "manager approve/refuse; on approve, optionally link/create a Fleet vehicle "
    "assignment note. List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet or HR — pick the more natural parent."
)

_GRAIN_NOUNS = {
    "full",
    "new",
    "prefer",
    "extend",
    "full_app",
    "residual",
    "app",
    "field_pack",
    "feature_slice",
}


# ---------------------------------------------------------------------------
# A — Prefer/Extend host steal (Project → sale.order)
# ---------------------------------------------------------------------------


def test_project_commercial_prefer_locks_project_not_sale() -> None:
    assert named_host_from_prompt(PROJECT_COMMERCIAL) == "project.project"
    assert preferred_inherit_host(PROJECT_COMMERCIAL) == "project.project"
    assert classify_grain(PROJECT_COMMERCIAL) == "field_pack"

    u = build_understanding(PROJECT_COMMERCIAL)
    assert u.host_model == "project.project"
    assert u.grain == "field_pack"
    assert u.inherit_existing is True
    joined = " | ".join(u.constraints).lower()
    assert "project.project" in joined
    assert "sale.order" not in joined
    assert "on sales" not in joined
    assert "commercial phase" in joined
    assert "billable cap" in joined
    # Prompt crumb must not glue «On project form» into the Billable cap label.
    assert "billable cap (hours). on project" not in joined
    assert "option a" in joined or "python" in joined
    # No residual full_app tile for this Prefer/Extend.
    assert u.inherit_existing
    assert any("new home-screen app" in x.lower() or "parallel project" in x.lower() for x in (u.out_of_scope or []) + u.constraints)


def test_project_commercial_ast_phase_selection_and_cap_float() -> None:
    ast = parse_det(
        PROJECT_COMMERCIAL, host="project.project", inherit=True, grain="field_pack"
    )
    assert ast.host == "project.project"
    by_label = {f.label.lower(): f for f in ast.fields}
    assert "commercial phase" in by_label
    phase = by_label["commercial phase"]
    assert phase.ttype == "selection"
    assert phase.selection_options and "hypercare" in phase.selection_options.lower()
    assert "billable cap" in by_label
    assert by_label["billable cap"].ttype in {"float", "integer"}
    rows = " | ".join(ast_to_must_do(ast)).lower()
    assert "sale.order" not in rows
    assert "option a" in rows or "python" in rows


def test_prefer_sale_order_packs_still_prefer_sale() -> None:
    """Regression: Customer PO + delivery window Prefer-locks sale.order."""
    assert preferred_inherit_host(TOPE_SALES_PREFER) == "sale.order"
    assert classify_grain(TOPE_SALES_PREFER) == "field_pack"
    u = build_understanding(TOPE_SALES_PREFER)
    assert u.host_model == "sale.order"
    assert u.grain == "field_pack"
    assert u.inherit_existing is True
    joined = " | ".join(u.constraints).lower()
    assert "sale.order" in joined
    assert "customer po" in joined or "delivery window" in joined


# ---------------------------------------------------------------------------
# B — full_app noun collapse (grain Full → Name Full / x_full)
# ---------------------------------------------------------------------------


def test_field_work_orders_noun_not_full_or_x_full() -> None:
    assert classify_grain(FIELD_WORK_ORDERS) == "full_app"
    display, slug = naming_from_residual(FIELD_WORK_ORDERS)
    assert display.lower() not in _GRAIN_NOUNS
    assert slug not in {"full", "x_full", "new", "prefer", "extend"}
    assert "full" != display.lower()
    assert "field" in display.lower() and "order" in display.lower()
    assert slug.startswith("field_work_order")

    u = build_understanding(FIELD_WORK_ORDERS)
    assert u.grain == "full_app"
    assert u.host_model is None
    assert u.inherit_existing is False
    assert u.title.lower() not in _GRAIN_NOUNS
    assert "full" != u.title.lower()
    assert "field" in u.title.lower() and "order" in u.title.lower()
    joined = " | ".join(u.constraints).lower()
    assert "x_full" not in joined
    assert "x_field_work_order" in joined
    assert "priority" in joined  # cued — invent honor must keep
    assert "checklist" in joined or "parts used" in joined
    # Honest satellites — not flat Product*/Quantity* Identity.
    assert "flat product" in joined or "satellite" in joined or "o2m" in joined
    assert not any(
        x.lower().startswith("field: product") or x.lower().startswith("field: quantity")
        for x in u.constraints
    )


def test_studio_grain_words_never_become_residual_noun() -> None:
    """Class-wide: Full / New / Prefer / Extend are grain chrome, not app nouns."""
    for brief, _forbidden in (
        ("Build a Full app", "full"),
        ("Build a New app", "new"),
        ("Full app — Build Visitor Log: Name, Company", None),
    ):
        display, slug = naming_from_residual(brief)
        assert display.lower() not in _GRAIN_NOUNS, brief
        assert slug not in {"full", "new", "prefer", "extend", "x_full"}, brief


def test_full_app_for_noun_keeps_business_noun() -> None:
    display, slug = naming_from_residual("Build a Full app for Field work orders")
    assert "field" in display.lower() and "order" in display.lower()
    assert display.lower() not in _GRAIN_NOUNS
    assert slug.startswith("field_work_order")


def test_vehicle_request_residual_still_green() -> None:
    """Regression: Vehicle Request residual lock + naming stay green."""
    assert classify_grain(VEHICLE_REQUEST) == "full_app"
    display, slug = naming_from_residual(VEHICLE_REQUEST)
    assert display == "Vehicle Request"
    assert slug == "vehicle_request"
    u = build_understanding(VEHICLE_REQUEST)
    assert u.grain == "full_app"
    assert u.host_model is None
    assert u.title == "Vehicle Request"
    joined = " | ".join(u.constraints).lower()
    assert "x_vehicle_request" in joined
    assert "employees" in joined or "employee" in joined
