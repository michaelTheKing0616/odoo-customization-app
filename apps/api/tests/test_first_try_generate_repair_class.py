"""Class-wide first-try Generate repair — satellite O2M, M2O de-dupe, sign-off, UI gates.

Failure classes (Tope mandate — architectural, not Field-Work-only):
A) Checklist/parts Must-do → real O2M line models; never literal «Satellite O2M: …» Char labels
B) Same stock comodel once on Identity; brief-cued Related Sales Order / Fleet kept
C) Sign-off → boolean Customer signed (+ attachment); handoff note stays Text
D) Studio contract scorecard blocks Apply with Repair-with-Expert path for these gaps
"""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_constraint_ast import ast_to_must_do, parse_det  # noqa: E402
from app.ai_conversation.understand import build_understanding  # noqa: E402
from app.ai_document_shape import (  # noqa: E402
    classify_document_shape,
    honor_operator_brief,
    is_transactional_line_document,
    naming_from_residual,
)
from app.ai_field_ir import fields_from_residual_brief  # noqa: E402
from app.ai_grain import classify_grain, preferred_inherit_host  # noqa: E402
from app.ai_model_quality import dedupe_identity_same_comodel_fields  # noqa: E402
from app.ai_odoo_app_bar import ensure_cued_o2m_satellites  # noqa: E402
from app.ai_studio_contract import (  # noqa: E402
    attach_studio_contract,
    evaluate_studio_contract,
    residual_generate_hygiene_gaps,
)

FIELD_WORK_ORDERS = (
    "Build Field work orders a mid-market firm could sell next to Odoo: "
    "Work order: Customer (Contact), Related Sales Order (optional), "
    "Asset/Vehicle (Fleet, optional), Scheduled slot, Priority, State "
    "(Draft → Scheduled → In progress → Done → Invoiced); Checklist lines; "
    "Parts used; Sign-off; Menus list/kanban/calendar; consultant handoff note; "
    "prefer working Online metadata over fake Studio parity."
)

MAINTENANCE_TICKETS = (
    "Build Maintenance tickets for a service desk: "
    "Ticket: Customer (Contact), Related Sales Order (optional), "
    "State (Draft → Scheduled → In progress → Done); Checklist lines; "
    "Parts used; Sign-off; consultant handoff note."
)

INSPECTION_SIGNOFF = (
    "Build Inspection forms: Customer (Contact), State "
    "(Draft → In progress → Done); Sign-off; Menus list/form; "
    "consultant handoff note."
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

VEHICLE_REQUEST = (
    "Build Vehicle request: employees request a fleet vehicle for a date range; "
    "manager approve/refuse; on approve, optionally link/create a Fleet vehicle "
    "assignment note. List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet or HR — pick the more natural parent."
)


def _seed_and_honor(brief: str) -> dict:
    display, slug = naming_from_residual(brief)
    draft = {
        "display_name": display,
        "technical_name": slug,
        "grain": "full_app",
        "_user_prompt": brief,
        "models": [
            {
                "model": f"x_{slug}",
                "mode": "new",
                "description": display,
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True}
                ],
            }
        ],
        "depends": ["base", "mail"],
    }
    honor_operator_brief(draft, user_prompt=brief)
    ensure_cued_o2m_satellites(draft, prompt=brief)
    return draft


# ---------------------------------------------------------------------------
# A — Satellite O2M Generate grammar
# ---------------------------------------------------------------------------


def test_field_work_is_transactional_not_register() -> None:
    assert is_transactional_line_document(FIELD_WORK_ORDERS)
    assert classify_document_shape(FIELD_WORK_ORDERS, {}) == "transactional_header"
    assert classify_grain(FIELD_WORK_ORDERS) == "full_app"


def test_field_work_must_do_o2m_meta_not_char_labels() -> None:
    u = build_understanding(FIELD_WORK_ORDERS)
    joined = " | ".join(u.constraints)
    assert "O2M satellite: Checklist lines" in joined
    assert "O2M satellite: Parts used" in joined
    assert "Satellite O2M: Checklist lines (not flat" not in joined
    fields = fields_from_residual_brief(FIELD_WORK_ORDERS)
    labels = [str(f.get("string") or "") for f in fields]
    assert not any(lab.lower().startswith("satellite o2m") for lab in labels)
    assert not any(lab.lower().startswith("o2m satellite") for lab in labels)
    assert not any(lab.lower().startswith("menus:") for lab in labels)


def test_field_work_generate_materializes_checklist_and_parts_o2m() -> None:
    draft = _seed_and_honor(FIELD_WORK_ORDERS)
    mids = {str(m.get("model") or "") for m in draft["models"]}
    assert any(m.endswith("_checklist_line") for m in mids)
    assert any(m.endswith("_parts_line") for m in mids)
    primary = next(
        m
        for m in draft["models"]
        if str(m.get("model") or "").startswith("x_")
        and not str(m.get("model") or "").endswith(("_line", "_party"))
        and "_checklist_line" not in str(m.get("model") or "")
        and "_parts_line" not in str(m.get("model") or "")
    )
    fields = [f for f in primary.get("fields") or [] if isinstance(f, dict)]
    o2ms = {
        str(f.get("string") or "").lower(): f
        for f in fields
        if str(f.get("ttype") or "") == "one2many"
    }
    assert any("checklist" in k for k in o2ms)
    assert any("parts" in k for k in o2ms)
    # No literal stamp Char leftovers
    for f in fields:
        lab = str(f.get("string") or "")
        assert not lab.lower().startswith("satellite o2m")
        assert not lab.lower().startswith("o2m satellite")
        assert not lab.lower().startswith("menus:")
    # Checklist line has done flag; parts line has product+qty
    checklist = next(m for m in draft["models"] if str(m.get("model")).endswith("_checklist_line"))
    parts = next(m for m in draft["models"] if str(m.get("model")).endswith("_parts_line"))
    c_names = {str(f.get("name")) for f in checklist.get("fields") or [] if isinstance(f, dict)}
    p_names = {str(f.get("name")) for f in parts.get("fields") or [] if isinstance(f, dict)}
    assert "x_done" in c_names
    assert "x_product_id" in p_names
    assert "x_qty" in p_names
    assert residual_generate_hygiene_gaps(draft, prompt=FIELD_WORK_ORDERS) == []


def test_maintenance_tickets_unseen_shape_first_try_o2m() -> None:
    """Unseen noun — Maintenance tickets — same class behavior first try."""
    assert classify_document_shape(MAINTENANCE_TICKETS, {}) == "transactional_header"
    display, slug = naming_from_residual(MAINTENANCE_TICKETS)
    assert "maintenance" in display.lower()
    assert "ticket" in display.lower()
    assert slug.startswith("maintenance_ticket")
    draft = _seed_and_honor(MAINTENANCE_TICKETS)
    mids = {str(m.get("model") or "") for m in draft["models"]}
    assert any(m.endswith("_checklist_line") for m in mids)
    assert any(m.endswith("_parts_line") for m in mids)
    primary = next(
        m
        for m in draft["models"]
        if str(m.get("model") or "") == f"x_{slug}"
        or (
            str(m.get("model") or "").startswith("x_")
            and "_line" not in str(m.get("model") or "")
            and "_party" not in str(m.get("model") or "")
        )
    )
    labels = [
        str(f.get("string") or "")
        for f in primary.get("fields") or []
        if isinstance(f, dict)
    ]
    assert any("checklist" in x.lower() for x in labels)
    assert any("parts" in x.lower() for x in labels)
    assert not any(x.lower().startswith("satellite") for x in labels)


# ---------------------------------------------------------------------------
# B — Residual M2O / related de-dupe
# ---------------------------------------------------------------------------


def test_identity_keeps_one_customer_and_related_sales_order() -> None:
    draft = _seed_and_honor(FIELD_WORK_ORDERS)
    primary = next(
        m
        for m in draft["models"]
        if str(m.get("model") or "").startswith("x_field_work")
        and "_line" not in str(m.get("model") or "")
    )
    partner = [
        f
        for f in primary.get("fields") or []
        if isinstance(f, dict) and f.get("relation") == "res.partner"
    ]
    so = [
        f
        for f in primary.get("fields") or []
        if isinstance(f, dict) and f.get("relation") == "sale.order"
    ]
    fleet = [
        f
        for f in primary.get("fields") or []
        if isinstance(f, dict) and f.get("relation") == "fleet.vehicle"
    ]
    assert len(partner) == 1
    assert len(so) == 1
    assert len(fleet) == 1
    assert "sales" in str(so[0].get("string") or "").lower()


def test_dedupe_collapses_duplicate_customer_keeps_sales_order() -> None:
    draft = {
        "_user_prompt": FIELD_WORK_ORDERS,
        "models": [
            {
                "model": "x_field_work_orders",
                "mode": "new",
                "fields": [
                    {
                        "name": "x_customer_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Customer",
                    },
                    {
                        "name": "x_contact_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Contact",
                    },
                    {
                        "name": "x_sale_order_id",
                        "ttype": "many2one",
                        "relation": "sale.order",
                        "string": "Sales Order",
                    },
                ],
            }
        ],
    }
    notes = dedupe_identity_same_comodel_fields(draft, prompt=FIELD_WORK_ORDERS)
    assert notes
    fields = draft["models"][0]["fields"]
    partners = [f for f in fields if f.get("relation") == "res.partner"]
    sos = [f for f in fields if f.get("relation") == "sale.order"]
    assert len(partners) == 1
    assert len(sos) == 1
    assert "related" in str(sos[0].get("string") or "").lower() or "sales" in str(
        sos[0].get("string") or ""
    ).lower()


# ---------------------------------------------------------------------------
# C — Sign-off / signature field class
# ---------------------------------------------------------------------------


def test_signoff_is_boolean_plus_attachment_not_multiline() -> None:
    ast = parse_det(FIELD_WORK_ORDERS, host=None, inherit=False, grain="full_app")
    by = {f.label.lower(): f for f in ast.fields}
    assert "customer signed" in by
    assert by["customer signed"].ttype == "boolean"
    assert "signature attachment" in by
    assert by["signature attachment"].ttype == "binary"
    assert "sign-off" not in by
    # Handoff stays text — distinct from sign-off
    assert "handoff note" in by
    assert by["handoff note"].ttype == "text"

    fields = fields_from_residual_brief(FIELD_WORK_ORDERS)
    by_s = {str(f.get("string") or "").lower(): f for f in fields}
    assert by_s["customer signed"]["ttype"] == "boolean"
    assert by_s["signature attachment"]["ttype"] == "binary"
    assert by_s["handoff note"]["ttype"] == "text"
    assert "sign-off" not in by_s


def test_inspection_signoff_unseen_shape() -> None:
    """Unseen Inspection brief — sign-off class without checklist/parts."""
    assert classify_grain(INSPECTION_SIGNOFF) == "full_app"
    fields = fields_from_residual_brief(INSPECTION_SIGNOFF)
    by_s = {str(f.get("string") or "").lower(): f for f in fields}
    assert by_s.get("customer signed", {}).get("ttype") == "boolean"
    assert "sign-off" not in by_s
    draft = _seed_and_honor(INSPECTION_SIGNOFF)
    primary = next(
        m
        for m in draft["models"]
        if str(m.get("model") or "").startswith("x_")
        and "_line" not in str(m.get("model") or "")
    )
    signed = [
        f
        for f in primary.get("fields") or []
        if isinstance(f, dict)
        and str(f.get("ttype")) == "boolean"
        and "signed" in str(f.get("string") or "").lower()
    ]
    assert signed
    bad = [
        f
        for f in primary.get("fields") or []
        if isinstance(f, dict)
        and str(f.get("string") or "").strip().lower() == "sign-off"
    ]
    assert not bad


# ---------------------------------------------------------------------------
# D — Elite repair surfaced (contract scorecard)
# ---------------------------------------------------------------------------


def test_hygiene_gaps_detect_literal_stamps_and_signoff_text() -> None:
    draft = {
        "_user_prompt": FIELD_WORK_ORDERS,
        "models": [
            {
                "model": "x_field_work_orders",
                "mode": "new",
                "fields": [
                    {
                        "name": "x_satellite_o2m_checklist_lines_not_flat",
                        "ttype": "char",
                        "string": "Satellite O2M: Checklist lines (not flat Product/Quantity on primary)",
                    },
                    {
                        "name": "x_sign_off",
                        "ttype": "text",
                        "string": "Sign-off",
                    },
                    {
                        "name": "x_customer_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Customer",
                    },
                    {
                        "name": "x_contact_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Contact",
                    },
                ],
            }
        ],
    }
    gaps = residual_generate_hygiene_gaps(draft, prompt=FIELD_WORK_ORDERS)
    codes = {g["code"] for g in gaps}
    assert "literal_satellite_stamp" in codes
    assert "signoff_as_text" in codes
    assert "duplicate_identity_m2o" in codes
    assert "missing_checklist_o2m" in codes or "missing_parts_o2m" in codes

    attach_studio_contract(draft, FIELD_WORK_ORDERS)
    score = evaluate_studio_contract(draft)
    assert score["pass"] is False
    assert score["blocking"] is True
    assert any("Repair with Expert" in r for r in score.get("repairs") or [])


def test_clean_field_work_contract_passes() -> None:
    draft = _seed_and_honor(FIELD_WORK_ORDERS)
    attach_studio_contract(draft, FIELD_WORK_ORDERS)
    score = evaluate_studio_contract(draft)
    assert score["pass"] is True
    assert score["blocking"] is False


# ---------------------------------------------------------------------------
# Regressions — Prefer Project + Vehicle
# ---------------------------------------------------------------------------


def test_project_commercial_prefer_still_green() -> None:
    assert preferred_inherit_host(PROJECT_COMMERCIAL) == "project.project"
    assert classify_grain(PROJECT_COMMERCIAL) == "field_pack"
    u = build_understanding(PROJECT_COMMERCIAL)
    assert u.host_model == "project.project"
    assert u.grain == "field_pack"
    assert u.inherit_existing is True
    joined = " | ".join(u.constraints).lower()
    assert "project.project" in joined
    assert "sale.order" not in joined


def test_vehicle_request_residual_still_green() -> None:
    assert classify_grain(VEHICLE_REQUEST) == "full_app"
    display, slug = naming_from_residual(VEHICLE_REQUEST)
    assert display == "Vehicle Request"
    assert slug == "vehicle_request"
    u = build_understanding(VEHICLE_REQUEST)
    assert u.grain == "full_app"
    assert "x_vehicle_request" in " | ".join(u.constraints).lower()
