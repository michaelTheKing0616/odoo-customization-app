"""Locked full_app must never Prefer-reshape via craft / Expert / refine / contract.

Root class (Vehicle Request Generate regression):
- Diagnosis locks full_app on residual x_* (x_vehicle_request)
- Craft «Vehicle Requests» on Employees is a smart button — not a host flip
- Expert / Repair with Expert / surface repair must keep residual full_app
- Never stamp «hr.employee fields» or Prefer-for-delivery junk
- Foreign pack headers (x_purchase_request) must not bleed into Vehicle IR
- Prefer Sales / Prefer Contacts still Prefer-reshape as before
"""

from __future__ import annotations

import copy
import os

import pytest

pytestmark = pytest.mark.no_app_db

os.environ["AI_INTENT_LLM"] = "off"

from app.ai_conversation.refine import (  # noqa: E402
    apply_refinement,
    wants_structural_repair,
)
from app.ai_conversation.understand import build_understanding  # noqa: E402
from app.ai_craft_smart_buttons import apply_confirmed_craft_smart_buttons  # noqa: E402
from app.ai_domain_packs import match_domain_pack  # noqa: E402
from app.ai_residual_identity import (  # noqa: E402
    draft_mismatches_residual_identity,
    enforce_residual_draft_identity,
)
from app.ai_studio_contract import (  # noqa: E402
    build_studio_contract,
    evaluate_studio_contract,
    fulfill_studio_contract,
)
from app.ai_surface_invariants import surface_invariant_findings  # noqa: E402

VEHICLE = (
    "Build Vehicle request: employees request a fleet vehicle for a date range; "
    "manager approve/refuse; on approve, optionally link/create a Fleet vehicle "
    "assignment note. List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet or HR — pick the more natural parent."
)

REPAIR = (
    "Fix surface findings that block Install. Ground the app title in the operator brief "
    "(never a placeholder like Contact extras). Keep inherit-only on the named stock host — "
    "no new home-screen app. Preserve Must-do wiring."
)

PREFER = (
    "Prefer for delivery + Delivery notes on res.partner already persist. "
    "Extend so they matter in workflows: surface preferred-delivery Contacts on "
    "pickings/transfers (domain or smart button), optional filter on Delivery/Inventory "
    "lists, and/or a light automation when the box is checked. Still inherit-only — "
    "no new app tile."
)


def _vehicle_draft(*, with_purchase_bleed: bool = False, craft_employees: bool = False) -> dict:
    fields = [
        {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
        {
            "name": "x_employee_id",
            "ttype": "many2one",
            "string": "Employee",
            "relation": "hr.employee",
        },
        {"name": "x_start_date", "ttype": "date", "string": "Start Date"},
        {"name": "x_end_date", "ttype": "date", "string": "End Date"},
        {
            "name": "x_state",
            "ttype": "selection",
            "string": "State",
            "selection": (
                "[('draft','Draft'),('submitted','Submitted'),"
                "('approved','Approved'),('refused','Refused'),('done','Done')]"
            ),
        },
    ]
    models = [
        {
            "model": "x_vehicle_request",
            "mode": "new",
            "description": "Vehicle Request",
            "fields": fields,
        }
    ]
    if with_purchase_bleed:
        models.append(
            {
                "model": "x_purchase_request",
                "mode": "new",
                "description": "Purchase Requests",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_amount",
                        "ttype": "monetary",
                        "string": "Amount",
                        "currency_field": "x_currency_id",
                    },
                ],
            }
        )
    draft: dict = {
        "display_name": "Vehicle Request",
        "technical_name": "vehicle_request",
        "grain": "full_app",
        "_user_prompt": VEHICLE,
        "_understanding": {
            "title": "Vehicle Request",
            "grain": "full_app",
            "inherit_existing": False,
            "host_model": None,
            "capability": "residual_app",
            "craft_smart_buttons": (
                [
                    {
                        "on_model": "hr.employee",
                        "label": "Vehicle Requests",
                        "related_model": "x_vehicle_request",
                        "relation_field": "x_employee_id",
                        "confirmed": True,
                    }
                ]
                if craft_employees
                else []
            ),
        },
        "models": models,
        "menus": [{"name": "Vehicle Requests", "parent_xml_id": "fleet.menu_root"}],
        "actions": [{"name": "Vehicle Requests", "model": "x_vehicle_request"}],
        "smart_buttons": [],
    }
    return draft


def test_vehicle_diagnosis_stays_full_app_on_x_vehicle_request() -> None:
    u = build_understanding(VEHICLE)
    assert u.grain == "full_app"
    assert u.host_model is None
    assert u.title == "Vehicle Request"
    assert "x_vehicle_request" in " | ".join(u.constraints).lower()


def test_vehicle_does_not_match_purchase_request_pack() -> None:
    hit = match_domain_pack(VEHICLE)
    assert hit is None or hit[0] != "purchase_request"


def test_purchase_bleed_detected_and_scrubbed() -> None:
    draft = _vehicle_draft(with_purchase_bleed=True)
    assert draft_mismatches_residual_identity(draft, prompt=VEHICLE)
    notes = enforce_residual_draft_identity(
        draft,
        prompt=VEHICLE,
        locked=draft["_understanding"],
        prefer_locked=True,
    )
    assert notes
    models = [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    ]
    assert "x_vehicle_request" in models
    assert "x_purchase_request" not in models


def test_craft_employees_does_not_flip_grain_or_host() -> None:
    draft = _vehicle_draft(craft_employees=True)
    apply_confirmed_craft_smart_buttons(draft, prompt=VEHICLE)
    assert draft.get("grain") == "full_app"
    assert draft["_understanding"]["grain"] == "full_app"
    assert draft["_understanding"].get("host_model") in (None, "")
    customs = [
        m
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and str(m.get("mode") or "new") != "inherit"
    ]
    assert any(m.get("model") == "x_vehicle_request" for m in customs)
    # Craft may add smart button on Employees — not convert models to inherit hr.employee.
    assert not any(
        isinstance(m, dict)
        and m.get("model") == "hr.employee"
        and m.get("mode") == "inherit"
        and any(
            "prefer" in str(f.get("name") or "").lower()
            for f in (m.get("fields") or [])
            if isinstance(f, dict)
        )
        for m in (draft.get("models") or [])
    )


def test_expert_repair_keeps_vehicle_full_app() -> None:
    draft = _vehicle_draft(with_purchase_bleed=True, craft_employees=True)
    # Contaminated title that Prefer-reshape used to stamp.
    draft["display_name"] = "hr.employee fields"
    assert wants_structural_repair(REPAIR)
    result = apply_refinement(draft, REPAIR, prompt=VEHICLE, provider=None)
    assert result.get("ok") is True
    assert result.get("structural") is True
    out = result["draft"]
    assert out.get("grain") == "full_app"
    assert out.get("display_name") == "Vehicle Request"
    assert "hr.employee fields" not in str(out.get("display_name") or "").lower()
    models = [m for m in (out.get("models") or []) if isinstance(m, dict)]
    x_new = [
        m
        for m in models
        if str(m.get("model") or "").startswith("x_")
        and str(m.get("mode") or "new") != "inherit"
    ]
    assert any(m.get("model") == "x_vehicle_request" for m in x_new)
    assert not any(m.get("model") == "x_purchase_request" for m in x_new)
    # No Prefer junk
    labels = {
        str(f.get("string") or "")
        for m in x_new
        for f in (m.get("fields") or [])
        if isinstance(f, dict)
    }
    assert "Prefer for delivery" not in labels
    assert "Delivery notes" not in labels
    # Manager slotted on residual header when approval is in the brief
    header = next(m for m in x_new if m.get("model") == "x_vehicle_request")
    assert any(
        str(f.get("relation")) == "res.users"
        for f in (header.get("fields") or [])
        if isinstance(f, dict)
    )
    # Contract must not claim inherit-only reshape
    contract = out.get("_studio_contract") or {}
    assert contract.get("inherit_only") is not True
    assert contract.get("grain") == "full_app"
    summary = str(result.get("patch_summary") or "").lower()
    assert "reshaped residual into inherit-only" not in summary


def test_contract_evaluate_no_reshape_repair_for_full_app() -> None:
    draft = _vehicle_draft()
    contract = build_studio_contract(VEHICLE, grain="full_app")
    assert contract.get("inherit_only") is False
    assert contract.get("grain") == "full_app"
    draft["_studio_contract"] = contract
    score = evaluate_studio_contract(draft)
    repairs = " | ".join(score.get("repairs") or [])
    assert "reshape residual → inherit-only" not in repairs


def test_fulfill_does_not_reshape_full_app_even_if_contract_wrong() -> None:
    draft = _vehicle_draft()
    draft["_studio_contract"] = {
        "inherit_only": True,
        "grain": "field_pack",
        "host_model": "hr.employee",
        "host_label": "Employees",
        "title": "hr.employee fields",
        "fields": [],
        "surfaces": [],
    }
    notes = fulfill_studio_contract(draft, VEHICLE)
    assert draft.get("grain") == "full_app"
    assert any("kept residual full_app" in n.lower() for n in notes)
    models = [
        m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model") == "x_vehicle_request"
    ]
    assert models
    assert not any(
        isinstance(m, dict) and m.get("model") == "hr.employee" and m.get("mode") == "inherit"
        for m in (draft.get("models") or [])
    )


def test_prefer_sales_still_reshapes() -> None:
    """Regression: Prefer inherit-only Expert repair still Prefer-reshapes."""
    residual = {
        "display_name": "Contacts extension",
        "technical_name": "x_prefer",
        "grain": "full_app",
        "models": [
            {
                "model": "x_prefer",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            }
        ],
        "menus": [{"name": "Prefer"}],
        "_user_prompt": PREFER,
    }
    result = apply_refinement(residual, REPAIR, prompt=PREFER, provider=None)
    assert result.get("ok") is True
    assert result.get("structural") is True
    draft = result["draft"]
    assert draft.get("grain") == "field_pack"
    models = draft.get("models") or []
    assert len(models) == 1
    assert models[0]["model"] == "res.partner"
    assert models[0]["mode"] == "inherit"
    labels = {str(f.get("string")) for f in models[0].get("fields") or []}
    assert "Prefer for delivery" in labels
    assert "Delivery notes" in labels


def test_surface_gate_after_scrub_not_dual_header() -> None:
    draft = _vehicle_draft(with_purchase_bleed=True)
    enforce_residual_draft_identity(
        draft, prompt=VEHICLE, locked=draft["_understanding"], prefer_locked=True
    )
    # Slot manager so approval finding clears
    header = next(
        m
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model") == "x_vehicle_request"
    )
    fields = list(header.get("fields") or [])
    fields.append(
        {
            "name": "x_manager_id",
            "ttype": "many2one",
            "string": "Manager",
            "relation": "res.users",
            "required": True,
        }
    )
    header["fields"] = fields
    draft["_document_shape"] = "register"
    findings = surface_invariant_findings(draft)
    blob = " | ".join(findings).lower()
    assert "x_purchase_request" not in blob
    assert "thin document shape" not in blob or "x_purchase_request" not in blob
