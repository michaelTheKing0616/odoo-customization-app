"""Class-wide Generate spray + install grammar (Tope mandate 2026-09-22).

Production path (seed → depth → finalize) must not re-inject:
- uncued company / Contact / Purchase Order Identity M2Os
- uncued Rate/service/generic _line O2M when checklist + parts are cued
- header O2Ms / empty notebook clone tabs
- 2 sibling apps on thin residual
- Datetime when brief says Date (or implies no time)

Uses full finalize path — thin _generate alone is insufficient (scrub was
already green while production_shape re-injected).
"""

from __future__ import annotations

import os
import re

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_brief_cues import honor_stated_brief_cues  # noqa: E402
from app.ai_constraint_ast import ast_to_must_do, parse_det  # noqa: E402
from app.ai_depth import classify_ambition, apply_deterministic_depth  # noqa: E402
from app.ai_document_shape import naming_from_residual  # noqa: E402
from app.ai_generation_engine import attach_generation_engine  # noqa: E402
from app.ai_generate_ir import ir_closure_violations  # noqa: E402
from app.ai_generate_ir_lint import invent_outside_admit_violations  # noqa: E402
from app.ai_pipeline import seed_studio_draft  # noqa: E402
from app.preview_views import build_form_preview  # noqa: E402

MAINTENANCE_EXACT = (
    "Build Maintenance tickets: checklist lines with done flags, parts used (product + qty), "
    "state Draft→Done; Online-honest on stock moves."
)

# Unseen sibling — same class, not Maintenance-named
SERVICE_CARDS = (
    "Build Service cards: technician; state Draft→Done; "
    "checklist lines with done flags; parts used (product + qty); "
    "Online-honest on stock moves."
)

FIELD_WORK_ORDERS = (
    "Build Field work orders a mid-market firm could sell next to Odoo: "
    "Work order: Customer (Contact), Related Sales Order (optional), "
    "Asset/Vehicle (Fleet, optional), Scheduled slot, Priority, State "
    "(Draft → Scheduled → In progress → Done → Invoiced); Checklist lines; "
    "Parts used; Sign-off; Menus list/kanban/calendar; consultant handoff note; "
    "prefer working Online metadata over fake Studio parity."
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

TOPE_SALES_PREFER = (
    "Extend Sales Orders: add Customer PO reference and Required delivery window "
    "on the order form. Prefer/Extend stock sale.order — no second sales app."
)

VEHICLE_REQUEST = (
    "Build Vehicle request: employees request a fleet vehicle for a date range; "
    "manager approve/refuse; on approve, optionally link/create a Fleet vehicle "
    "assignment note. List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet or HR — pick the more natural parent."
)


def _produce(brief: str) -> dict:
    """Exact Studio Generate finish path: seed → depth → ``_finish_seed_draft``.

    Matches ``POST /ai/sessions/{id}/generate`` → ``run_draft_job_body`` closer
    (handoff §4 step 6) — not Diagnosis/`understand` alone.
    """
    from app.ai_draft_jobs import _finish_seed_draft
    from app.ai_pipeline import seed_studio_draft

    draft = seed_studio_draft(brief)
    draft, _ = apply_deterministic_depth(draft, user_prompt=brief)
    out = _finish_seed_draft(brief, draft, warnings=[])
    honor_stated_brief_cues(out, prompt=brief)
    attach_generation_engine(out, brief, user_phase="review")
    return out


def _primary(draft: dict) -> dict:
    slug = str(draft.get("technical_name") or "")
    want = f"x_{slug}" if slug and not slug.startswith("x_") else slug
    for m in draft.get("models") or []:
        if str(m.get("model")) == want:
            return m
    for m in draft.get("models") or []:
        mid = str(m.get("model") or "")
        if (
            mid.startswith("x_")
            and not mid.endswith("_line")
            and not mid.endswith("_party")
            and "checklist" not in mid
            and "parts" not in mid
        ):
            return m
    return (draft.get("models") or [{}])[0]


def _header_o2m_count(header: dict) -> int:
    return sum(
        1
        for f in header.get("fields") or []
        if isinstance(f, dict) and str(f.get("ttype") or "") == "one2many"
    )


def _form_header_o2m_count(draft: dict, mid: str) -> int:
    for v in draft.get("views") or []:
        if not isinstance(v, dict) or str(v.get("model") or "") != mid:
            continue
        arch = str(v.get("arch") or "")
        if "<form" not in arch and str(v.get("type") or v.get("view_type") or "") != "form":
            continue
        if "<notebook" not in arch:
            return len(re.findall(r'name=["\']([^"\']+_ids)["\']', arch))
        before = arch.split("<notebook", 1)[0]
        return len(re.findall(r'name=["\']([^"\']+_ids)["\']', before))
    return -1


def _assert_no_spray(draft: dict, *, allow_partner: bool = False) -> None:
    header = _primary(draft)
    names = {str(f.get("name") or "") for f in header.get("fields") or []}
    rels = {str(f.get("relation") or "") for f in header.get("fields") or []}
    assert "x_company_id" not in names
    assert "company_id" not in names
    assert "res.company" not in rels
    assert "purchase.order" not in rels
    assert "x_purchase_order_id" not in names
    assert "account.move" not in rels
    assert "x_invoice_id" not in names
    if not allow_partner:
        assert "res.partner" not in rels
    # No rate / generic service line invent
    mids = {str(m.get("model") or "") for m in draft.get("models") or []}
    assert "x_rate" not in mids
    assert not any(mid.endswith("_rate") or mid.endswith("_rate_line") for mid in mids)
    labels = {
        str(f.get("string") or "").lower()
        for m in draft.get("models") or []
        for f in (m.get("fields") or [])
        if isinstance(f, dict)
    }
    assert not any("rate line" in lab for lab in labels)
    # Bare depth-seed party hub must not survive
    assert "x_party" not in mids


# --- Ambition: thin residual, not comprehensive depth floor ---


def test_thin_residual_ambition_not_comprehensive() -> None:
    assert classify_ambition(MAINTENANCE_EXACT) == "thin"
    assert classify_ambition(SERVICE_CARDS) == "thin"


# --- Must-do shape ---


def test_maintenance_must_do_state_plus_two_o2ms() -> None:
    rows = ast_to_must_do(parse_det(MAINTENANCE_EXACT, grain="full_app"))
    joined = " | ".join(rows)
    assert "State selection" in joined
    assert "Draft" in joined and "Done" in joined
    assert "Checklist" in joined
    assert "Parts" in joined
    assert "Company" not in joined
    assert "Purchase" not in joined
    assert "Rate" not in joined


def test_service_cards_must_do_same_class() -> None:
    rows = ast_to_must_do(parse_det(SERVICE_CARDS, grain="full_app"))
    joined = " | ".join(rows)
    assert "State selection" in joined
    assert "Checklist" in joined
    assert "Parts" in joined


# --- Full production Generate ---


def test_maintenance_produce_no_company_po_rate_party() -> None:
    draft = _produce(MAINTENANCE_EXACT)
    assert draft["display_name"] == "Maintenance Tickets"
    _assert_no_spray(draft)
    header = _primary(draft)
    o2ms = [
        f
        for f in header.get("fields") or []
        if isinstance(f, dict) and str(f.get("ttype")) == "one2many"
    ]
    assert len(o2ms) == 2, [f.get("string") for f in o2ms]
    strings = {str(f.get("string") or "").lower() for f in o2ms}
    assert any("checklist" in s for s in strings)
    assert any("parts" in s for s in strings)
    # Generic _line third satellite must not exist
    mids = {str(m.get("model") or "") for m in draft.get("models") or []}
    assert "x_maintenance_tickets_line" not in mids
    depends = {str(d).lower() for d in (draft.get("depends") or [])}
    assert "purchase" not in depends
    assert "stock" not in depends
    honesty = draft.get("_honesty") or {}
    assert honesty.get("online_stock_moves") is True


def test_service_cards_produce_same_class_no_spray() -> None:
    draft = _produce(SERVICE_CARDS)
    display, slug = naming_from_residual(SERVICE_CARDS)
    assert "build" not in display.lower()
    _assert_no_spray(draft)
    header = _primary(draft)
    o2ms = [
        f
        for f in header.get("fields") or []
        if isinstance(f, dict) and str(f.get("ttype")) == "one2many"
    ]
    assert len(o2ms) == 2, [f.get("string") for f in o2ms]
    mids = {str(m.get("model") or "") for m in draft.get("models") or []}
    assert f"x_{slug}_line" not in mids if slug else True
    assert "x_party" not in mids
    assert "x_rate" not in mids


def test_finish_gate_leaves_no_invent_outside_admit() -> None:
    """Wave 4 — scrub deleted; invent-outside-admit + closure own the gate."""
    for brief in (MAINTENANCE_EXACT, SERVICE_CARDS):
        draft = _produce(brief)
        assert invent_outside_admit_violations(draft) == []
        assert ir_closure_violations(draft) == []


def test_service_cards_matches_maintenance_class_shape() -> None:
    """Sibling golden — zero Maintenance-specific code (handoff §4 step 7)."""
    maint = _produce(MAINTENANCE_EXACT)
    svc = _produce(SERVICE_CARDS)
    for draft in (maint, svc):
        _assert_no_spray(draft)
        header = _primary(draft)
        o2ms = [
            f
            for f in header.get("fields") or []
            if isinstance(f, dict) and str(f.get("ttype")) == "one2many"
        ]
        assert len(o2ms) == 2
        honesty = draft.get("_honesty") or {}
        assert honesty.get("online_stock_moves") is True
        roots = [
            m
            for m in (draft.get("menus") or [])
            if isinstance(m, dict) and not m.get("parent_xml_id")
        ]
        assert len(roots) == 1


def test_maintenance_form_o2ms_in_notebook_not_header() -> None:
    draft = _produce(MAINTENANCE_EXACT)
    header = _primary(draft)
    mid = str(header.get("model") or "")
    assert _form_header_o2m_count(draft, mid) == 0
    prev = build_form_preview(draft)
    pages: list[str] = []
    for nb in prev.get("notebooks") or []:
        for p in nb.get("pages") or []:
            pages.append(str(p.get("string") or ""))
    assert len(pages) == 2, pages
    assert any("checklist" in p.lower() for p in pages)
    assert any("parts" in p.lower() for p in pages)
    # Identity has no Purchase order / Company
    for g in prev.get("groups") or []:
        if str(g.get("string") or "") == "Identity":
            labs = [str(f.get("string") or "") for f in g.get("fields") or []]
            assert "Purchase order" not in labs
            assert "Company" not in labs
            assert "Contact" not in labs


def test_maintenance_thin_one_document_menu() -> None:
    draft = _produce(MAINTENANCE_EXACT)
    roots = [
        m
        for m in (draft.get("menus") or [])
        if isinstance(m, dict) and not m.get("parent_xml_id")
    ]
    assert len(roots) == 1, [m.get("name") for m in roots]
    # No sibling root for party/rate
    action_models = {
        str(a.get("model") or "")
        for a in (draft.get("actions") or [])
        if isinstance(a, dict)
    }
    assert "x_party" not in action_models
    assert "x_rate" not in action_models
    # Find-it must not advertise Contact/Company/PO from depth spray
    op = draft.get("_operator_surface") if isinstance(draft.get("_operator_surface"), dict) else {}
    links = op.get("stock_links") or []
    stock_models = {str(l.get("stock_model") or "") for l in links if isinstance(l, dict)}
    assert "purchase.order" not in stock_models
    assert "res.company" not in stock_models
    # Contact find-it only OK if brief cued contact — Maintenance did not
    assert "res.partner" not in stock_models


def test_date_fields_are_date_not_datetime() -> None:
    draft = _produce(MAINTENANCE_EXACT)
    for m in draft.get("models") or []:
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                continue
            if str(f.get("ttype") or "") == "datetime":
                lab = str(f.get("string") or f.get("name") or "")
                # Scheduled slot / time cues may be datetime; bare Date must not
                assert re.search(
                    r"(?i)\b(?:time|slot|schedule|appointment|check[\s-]?in|timestamp)\b",
                    lab,
                ), f"uncued datetime: {m.get('model')}.{f.get('name')} ({lab})"


def test_field_work_keeps_customer_no_uncued_po_invoice() -> None:
    draft = _produce(FIELD_WORK_ORDERS)
    header = _primary(draft)
    rels = {str(f.get("relation") or "") for f in header.get("fields") or []}
    names = {str(f.get("name") or "") for f in header.get("fields") or []}
    assert "res.partner" in rels
    assert "purchase.order" not in rels
    assert "x_purchase_order_id" not in names
    assert "account.move" not in rels
    assert "x_invoice_id" not in names


def test_prefer_host_locks_still_prefer() -> None:
    from app.ai_conversation.understand import build_understanding
    from app.ai_grain import named_host_from_prompt, preferred_inherit_host

    assert named_host_from_prompt(PROJECT_COMMERCIAL) == "project.project"
    assert preferred_inherit_host(PROJECT_COMMERCIAL) == "project.project"
    u = build_understanding(PROJECT_COMMERCIAL)
    assert u.host_model == "project.project"
    assert preferred_inherit_host(TOPE_SALES_PREFER) == "sale.order"


def test_vehicle_must_do_regression() -> None:
    v = " | ".join(ast_to_must_do(parse_det(VEHICLE_REQUEST, grain="full_app")))
    assert "State selection" in v
    assert "Approved" in v and "Refused" in v
