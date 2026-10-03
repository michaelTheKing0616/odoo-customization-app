"""Class-wide State Must-do + Build-title + Identity spray (Tope mandate).

Failure classes (architectural — not Maintenance-only):
A) state Draft→Done / Draft to Done range cues → State in Must-do + matching selection
B) Build-verb / grain title pollution — Diagnosis/canvas from business noun
C) Uncued x_company_id / Purchase Order / Invoice Identity M2O never invent
D) Online-honest on stock moves → honesty stamp; Parts stay structured data
"""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_brief_cues import (  # noqa: E402
    honor_stated_brief_cues,
    stated_workflow_states,
)
from app.ai_constraint_ast import ast_to_must_do, parse_det  # noqa: E402
from app.ai_conversation.understand import build_understanding  # noqa: E402
from app.ai_document_shape import naming_from_residual  # noqa: E402
from app.ai_generation_engine import attach_generation_engine  # noqa: E402
from app.ai_odoo_app_bar import (  # noqa: E402
    run_odoo_app_bar_pass,
    stamp_online_stock_honesty,
)
from app.ai_residual_identity import scrub_residual_display_name  # noqa: E402
from app.preview_views import build_form_preview  # noqa: E402

# Exact Maintenance brief from Tope grades
MAINTENANCE_EXACT = (
    "Build Maintenance tickets: checklist lines with done flags, parts used (product + qty), "
    "state Draft→Done; Online-honest on stock moves."
)

FIELD_WORK_ORDERS = (
    "Build Field work orders a mid-market firm could sell next to Odoo: "
    "Work order: Customer (Contact), Related Sales Order (optional), "
    "Asset/Vehicle (Fleet, optional), Scheduled slot, Priority, State "
    "(Draft → Scheduled → In progress → Done → Invoiced); Checklist lines; "
    "Parts used; Sign-off; Menus list/kanban/calendar; consultant handoff note; "
    "prefer working Online metadata over fake Studio parity."
)

# Unseen thin residual with Draft→Done
SERVICE_CARDS = (
    "Build Service cards: technician; state Draft→Done; "
    "checklist lines with done flags; Online-honest on stock moves."
)

VEHICLE_REQUEST = (
    "Build Vehicle request: employees request a fleet vehicle for a date range; "
    "manager approve/refuse; on approve, optionally link/create a Fleet vehicle "
    "assignment note. List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet or HR — pick the more natural parent."
)


def _seed(brief: str) -> dict:
    display, slug = naming_from_residual(brief)
    return {
        "display_name": display,
        "technical_name": slug,
        "grain": "full_app",
        "_user_prompt": brief,
        "models": [
            {
                "model": f"x_{slug}",
                "description": display,
                "mode": "new",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True}
                ],
            }
        ],
        "views": [],
        "menus": [],
        "smart_buttons": [],
        "depends": ["base", "mail"],
    }


def _generate(brief: str) -> dict:
    from app.ai_document_shape import stamp_document_shape

    draft = _seed(brief)
    stamp_document_shape(draft, prompt=brief)
    attach_generation_engine(draft, prompt=brief)
    run_odoo_app_bar_pass(draft, user_prompt=brief)
    honor_stated_brief_cues(draft, prompt=brief)
    return draft


def _header(draft: dict) -> dict:
    slug = str(draft.get("technical_name") or "")
    want = f"x_{slug}"
    for m in draft.get("models") or []:
        if str(m.get("model")) == want:
            return m
    return next(m for m in draft["models"] if str(m.get("model", "")).startswith("x_"))


# --- A: State Must-do from range cues ---


def test_stated_workflow_states_draft_arrow_done() -> None:
    assert stated_workflow_states(MAINTENANCE_EXACT) == ["draft", "done"]
    assert stated_workflow_states("state Draft to Done") == ["draft", "done"]
    assert stated_workflow_states(
        "State (Draft → Scheduled → In progress → Done)"
    ) == ["draft", "scheduled", "in_progress", "done"]


def test_maintenance_exact_must_do_includes_state_draft_done() -> None:
    rows = ast_to_must_do(parse_det(MAINTENANCE_EXACT, grain="full_app"))
    joined = " | ".join(rows)
    assert "State selection" in joined
    assert "Draft" in joined and "Done" in joined
    assert "Cancel" not in joined
    # Only model + State + two O2Ms — not Contact/Company spray
    assert "Company" not in joined
    assert "Purchase" not in joined


def test_unseen_service_cards_state_in_must_do() -> None:
    rows = ast_to_must_do(parse_det(SERVICE_CARDS, grain="full_app"))
    joined = " | ".join(rows)
    assert "State selection" in joined
    assert "Draft" in joined and "Done" in joined


def test_maintenance_generate_carries_draft_done_selection() -> None:
    draft = _generate(MAINTENANCE_EXACT)
    header = _header(draft)
    state = next(
        (
            f
            for f in header.get("fields") or []
            if str(f.get("name")) in {"x_state", "x_status"}
        ),
        None,
    )
    assert state is not None, "State field missing on residual"
    sel = str(state.get("selection") or "")
    assert "draft" in sel.lower() and "done" in sel.lower()
    assert "cancel" not in sel.lower()


# --- B: Build-verb / grain title pollution ---


def test_maintenance_title_not_build_maintenance() -> None:
    display, slug = naming_from_residual(MAINTENANCE_EXACT)
    assert display == "Maintenance Tickets"
    assert "build" not in display.lower()
    assert slug == "maintenance_tickets"
    u = build_understanding(MAINTENANCE_EXACT)
    assert u.title == "Maintenance Tickets"
    assert not u.title.lower().startswith("build")


def test_scrub_strips_build_verb_title() -> None:
    assert scrub_residual_display_name("Build Maintenance") == "Maintenance"
    assert scrub_residual_display_name("Build Build Maintenance Tickets") == (
        "Maintenance Tickets"
    )


def test_canvas_preview_title_is_business_noun() -> None:
    draft = _generate(MAINTENANCE_EXACT)
    assert draft["display_name"] == "Maintenance Tickets"
    prev = build_form_preview(draft)
    assert prev.get("title") == "Maintenance Tickets"
    assert "build" not in str(prev.get("title") or "").lower()


# --- C: Identity spray + uncued PO/Invoice ---


def test_maintenance_no_company_po_invoice_spray() -> None:
    draft = _generate(MAINTENANCE_EXACT)
    header = _header(draft)
    names = {str(f.get("name") or "") for f in header.get("fields") or []}
    rels = {str(f.get("relation") or "") for f in header.get("fields") or []}
    assert "x_company_id" not in names
    assert "company_id" not in names
    assert "res.company" not in rels
    assert "purchase.order" not in rels
    assert "account.move" not in rels
    assert "x_purchase_order_id" not in names
    assert "x_invoice_id" not in names
    # Thin Maintenance brief did not cue Contact
    assert "res.partner" not in rels


def test_field_work_keeps_customer_so_no_uncued_invoice_po() -> None:
    draft = _generate(FIELD_WORK_ORDERS)
    header = _header(draft)
    names = {str(f.get("name") or "") for f in header.get("fields") or []}
    rels = {str(f.get("relation") or "") for f in header.get("fields") or []}
    assert "res.partner" in rels  # Customer cued
    assert any("sale" in n for n in names) or "sale.order" in rels
    assert "purchase.order" not in rels
    assert "x_purchase_order_id" not in names
    assert "x_invoice_id" not in names
    assert "account.move" not in rels


def test_scrub_drops_invented_po_invoice_company() -> None:
    draft = _seed(MAINTENANCE_EXACT)
    header = draft["models"][0]
    header["fields"].extend(
        [
            {
                "name": "x_company_id",
                "ttype": "many2one",
                "relation": "res.company",
                "string": "Company",
            },
            {
                "name": "x_purchase_order_id",
                "ttype": "many2one",
                "relation": "purchase.order",
                "string": "Purchase order",
            },
            {
                "name": "x_invoice_id",
                "ttype": "many2one",
                "relation": "account.move",
                "string": "Invoice",
            },
        ]
    )
    from app.ai_generate_ir_enforce import purge_unadmitted_spray

    purge_notes = purge_unadmitted_spray(draft)
    assert purge_notes
    names = {str(f.get("name") or "") for f in header["fields"]}
    assert "x_company_id" not in names
    assert "x_purchase_order_id" not in names
    assert "x_invoice_id" not in names


# --- D: Online stock honesty ---


def test_online_honest_stock_stamp_no_po_invent() -> None:
    draft = _generate(MAINTENANCE_EXACT)
    honesty = draft.get("_honesty") or {}
    assert honesty.get("online_stock_moves") is True
    notes = draft.get("_consultant_notes") or []
    assert any("stock" in str(n).lower() for n in notes)
    depends = {str(d).lower() for d in (draft.get("depends") or [])}
    assert "purchase" not in depends
    assert "stock" not in depends
    # Parts still structured
    mids = {str(m.get("model") or "") for m in draft.get("models") or []}
    assert any("parts" in mid for mid in mids)


def test_stamp_online_stock_honesty_idempotent() -> None:
    draft = _seed(MAINTENANCE_EXACT)
    n1 = stamp_online_stock_honesty(draft, prompt=MAINTENANCE_EXACT)
    n2 = stamp_online_stock_honesty(draft, prompt=MAINTENANCE_EXACT)
    assert n1
    assert draft["_honesty"]["online_stock_moves"] is True
    # Second pass should not duplicate consultant notes
    assert len(draft["_consultant_notes"]) == 1
    assert n2 == [] or "clipped" in " ".join(n2)


# --- Regressions: Vehicle + Field Work Must-do stay green ---


def test_vehicle_and_field_must_do_regressions() -> None:
    v = " | ".join(ast_to_must_do(parse_det(VEHICLE_REQUEST, grain="full_app")))
    assert "State selection" in v
    assert "Approved" in v and "Refused" in v
    f = " | ".join(ast_to_must_do(parse_det(FIELD_WORK_ORDERS, grain="full_app")))
    assert "State selection" in f
    assert "Invoiced" in f
    assert "Related Sales Order" in f
