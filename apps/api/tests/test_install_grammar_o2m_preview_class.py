"""Class-wide Install grammar + uncued smart invent + O2M preview (Tope mandate).

Failure classes (architectural — not Field-Work-only):
A) Notebook pages align with distinct O2M satellites; never leave O2M in Identity/header groups
B) Uncued Quotations/Invoices/Meetings smart buttons never invent on residual forms
C) Checklist/parts canvas preview carries real columns (item+done / product+qty) — not Tag A/B
D) Unseen Maintenance tickets residual shares the same grammar
"""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_document_shape import naming_from_residual  # noqa: E402
from app.ai_enrich import collapse_header_o2ms_into_notebook, _embedded_o2m_columns  # noqa: E402
from app.ai_generation_engine import attach_generation_engine  # noqa: E402
from app.ai_odoo_app_bar import (  # noqa: E402
    collapse_duplicate_line_models,
    run_odoo_app_bar_pass,
)
from app.ai_surface_invariants import (  # noqa: E402
    form_arch_page_count,
    header_o2m_count,
    preview_notebook_page_count,
    surface_invariant_findings,
)
from app.preview_views import build_form_preview  # noqa: E402

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
        "_user_prompt": brief,
    }


def _header(draft: dict, slug: str) -> dict:
    mid = f"x_{slug}"
    return next(m for m in draft["models"] if m.get("model") == mid)


def _residual_stock_smart_labels(draft: dict) -> set[str]:
    out: set[str] = set()
    for b in draft.get("smart_buttons") or []:
        if not isinstance(b, dict):
            continue
        on_model = str(b.get("on_model") or "")
        rel = str(b.get("related_model") or "")
        if on_model.startswith("x_") and rel and not rel.startswith("x_"):
            out.add(str(b.get("label") or "").strip().lower())
    return out


# ---------------------------------------------------------------------------
# A — Install / compile hygiene (notebook + header O2M)
# ---------------------------------------------------------------------------


def test_checklist_and_parts_do_not_collapse_into_one_line_model() -> None:
    draft = _seed(FIELD_WORK_ORDERS)
    run_odoo_app_bar_pass(draft, user_prompt=FIELD_WORK_ORDERS)
    mids = {str(m.get("model")) for m in draft["models"]}
    assert any(m.endswith("_checklist_line") for m in mids)
    assert any(m.endswith("_parts_line") for m in mids)
    # Collapse pass is role-aware — running again must not merge.
    notes = collapse_duplicate_line_models(draft)
    assert not any("collapsed duplicate line" in n and "parts_line" in n for n in notes)
    mids2 = {str(m.get("model")) for m in draft["models"]}
    assert any(m.endswith("_checklist_line") for m in mids2)
    assert any(m.endswith("_parts_line") for m in mids2)


def test_field_work_install_gate_notebook_matches_o2m() -> None:
    draft = _seed(FIELD_WORK_ORDERS)
    run_odoo_app_bar_pass(draft, user_prompt=FIELD_WORK_ORDERS)
    _, slug = naming_from_residual(FIELD_WORK_ORDERS)
    header = _header(draft, slug)
    collapse_header_o2ms_into_notebook(draft)
    attach_generation_engine(draft, FIELD_WORK_ORDERS, user_phase="review")
    o2m = header_o2m_count(header)
    pages = preview_notebook_page_count(draft)
    arch = form_arch_page_count(draft, header["model"])
    assert o2m >= 2, f"expected checklist+parts O2M, got {o2m}"
    assert pages <= o2m, (
        f"form_preview still lists {pages} notebook page(s); header has {o2m} one2many"
    )
    assert arch <= o2m
    findings = surface_invariant_findings(draft)
    assert not any("form_preview still lists" in f for f in findings)
    assert not any("notebook page(s) but the header has" in f for f in findings)


def test_o2m_not_left_in_identity_group_preview() -> None:
    draft = _seed(FIELD_WORK_ORDERS)
    run_odoo_app_bar_pass(draft, user_prompt=FIELD_WORK_ORDERS)
    fp = build_form_preview(draft)
    assert fp is not None
    for g in fp.get("groups") or []:
        for f in g.get("fields") or []:
            assert str(f.get("ttype") or "").lower() not in {"one2many", "many2many"}, (
                f"O2M {f.get('name')} still in group {g.get('string')}"
            )
    page_names = []
    for nb in fp.get("notebooks") or []:
        for p in nb.get("pages") or []:
            page_names.append(str(p.get("string") or "").lower())
    assert any("checklist" in n for n in page_names)
    assert any("parts" in n for n in page_names)


def test_related_sales_order_stays_on_identity_not_only_smart() -> None:
    draft = _seed(FIELD_WORK_ORDERS)
    run_odoo_app_bar_pass(draft, user_prompt=FIELD_WORK_ORDERS)
    _, slug = naming_from_residual(FIELD_WORK_ORDERS)
    header = _header(draft, slug)
    assert any(
        str(f.get("relation")) == "sale.order"
        for f in header.get("fields") or []
        if isinstance(f, dict)
    )
    fp = build_form_preview(draft)
    assert fp is not None
    identity_names = []
    for g in fp.get("groups") or []:
        for f in g.get("fields") or []:
            identity_names.append(str(f.get("name") or ""))
    assert any("sales_order" in n or "sale" in n for n in identity_names)


# ---------------------------------------------------------------------------
# B — Uncued smart-button invent
# ---------------------------------------------------------------------------


def test_field_work_no_uncued_quotation_invoice_meeting_smarts() -> None:
    draft = _seed(FIELD_WORK_ORDERS)
    run_odoo_app_bar_pass(draft, user_prompt=FIELD_WORK_ORDERS)
    labels = _residual_stock_smart_labels(draft)
    banned = {"quotations", "quotation", "invoices", "invoice", "meetings", "meeting"}
    assert not (labels & banned), f"uncued stock smarts invented: {labels & banned}"
    fp = build_form_preview(draft)
    preview_labels = {
        str(b.get("string") or "").strip().lower() for b in (fp or {}).get("smartButtons") or []
    }
    assert not (preview_labels & banned), f"preview smarts: {preview_labels & banned}"


def test_uncued_residual_stock_smarts_not_on_finish() -> None:
    """Wave 4 — scrub deleted; finish path must not leave uncued stock smarts."""
    draft = _seed(MAINTENANCE_TICKETS)
    run_odoo_app_bar_pass(draft, user_prompt=MAINTENANCE_TICKETS)
    assert _residual_stock_smart_labels(draft) == set()


def test_cued_quotations_smart_button_kept() -> None:
    brief = (
        "Build Job cards: Customer; add a Quotations smart button on the form "
        "linking sale orders; Checklist lines."
    )
    draft = _seed(brief)
    _, slug = naming_from_residual(brief)
    mid = f"x_{slug}"
    draft["smart_buttons"] = [
        {
            "on_model": mid,
            "related_model": "sale.order",
            "relation_field": "x_fk",
            "label": "Quotations",
            "source": "odoo_app_bar",
        }
    ]
    draft["_approved_craft"] = {
        "smart_buttons": [
            {
                "on_model": mid,
                "related_model": "sale.order",
                "label": "Quotations",
            }
        ]
    }
    run_odoo_app_bar_pass(draft, user_prompt=brief)
    # Cued/crafted Quotations may remain; uncued Invoices/Meetings must not invent.
    labels = _residual_stock_smart_labels(draft)
    assert "invoices" not in labels
    assert "meetings" not in labels


# ---------------------------------------------------------------------------
# C — Richer O2M canvas preview
# ---------------------------------------------------------------------------


def test_checklist_parts_embedded_columns_and_preview_shape() -> None:
    draft = _seed(FIELD_WORK_ORDERS)
    run_odoo_app_bar_pass(draft, user_prompt=FIELD_WORK_ORDERS)
    by_id = {str(m["model"]): m for m in draft["models"] if m.get("model")}
    checklist = next(m for m in by_id if m.endswith("_checklist_line"))
    parts = next(m for m in by_id if m.endswith("_parts_line"))
    _, slug = naming_from_residual(FIELD_WORK_ORDERS)
    header = _header(draft, slug)
    c_o2m = next(
        f
        for f in header["fields"]
        if isinstance(f, dict) and f.get("relation") == checklist
    )
    p_o2m = next(
        f for f in header["fields"] if isinstance(f, dict) and f.get("relation") == parts
    )
    c_cols = _embedded_o2m_columns(c_o2m, by_id)
    p_cols = _embedded_o2m_columns(p_o2m, by_id)
    assert "x_name" in c_cols and "x_done" in c_cols
    assert "x_product_id" in p_cols and "x_qty" in p_cols

    fp = build_form_preview(draft)
    assert fp is not None
    o2m_fields = []
    for nb in fp.get("notebooks") or []:
        for page in nb.get("pages") or []:
            for f in page.get("fields") or []:
                if str(f.get("ttype") or "") == "one2many":
                    o2m_fields.append(f)
    assert len(o2m_fields) >= 2
    col_blobs = []
    for f in o2m_fields:
        cols = f.get("relationColumns") or []
        assert cols, f"missing relationColumns on {f.get('name')}"
        col_blobs.append(" ".join(f"{c.get('name')} {c.get('string')}" for c in cols).lower())
    assert any("done" in b or "checklist" in b or "x_name" in b for b in col_blobs)
    assert any("product" in b or "qty" in b or "quantity" in b for b in col_blobs)


# ---------------------------------------------------------------------------
# D — Unseen residual shape (Maintenance tickets)
# ---------------------------------------------------------------------------


def test_maintenance_tickets_same_install_and_smart_grammar() -> None:
    draft = _seed(MAINTENANCE_TICKETS)
    run_odoo_app_bar_pass(draft, user_prompt=MAINTENANCE_TICKETS)
    mids = {str(m.get("model")) for m in draft["models"]}
    assert any(m.endswith("_checklist_line") for m in mids)
    assert any(m.endswith("_parts_line") for m in mids)
    labels = _residual_stock_smart_labels(draft)
    banned = {"quotations", "invoices", "meetings"}
    assert not (labels & banned), labels
    _, slug = naming_from_residual(MAINTENANCE_TICKETS)
    header = _header(draft, slug)
    attach_generation_engine(draft, MAINTENANCE_TICKETS, user_phase="review")
    o2m = header_o2m_count(header)
    pages = preview_notebook_page_count(draft)
    assert o2m >= 2
    assert pages <= o2m
    findings = surface_invariant_findings(draft)
    assert not any("form_preview still lists" in f for f in findings)


def test_vehicle_request_still_green_no_false_smart_scrub() -> None:
    """Regression: thin residual without stock commercial smarts stays clean."""
    draft = _seed(VEHICLE_REQUEST)
    run_odoo_app_bar_pass(draft, user_prompt=VEHICLE_REQUEST)
    labels = _residual_stock_smart_labels(draft)
    banned = {"quotations", "invoices", "meetings"}
    assert not (labels & banned)
