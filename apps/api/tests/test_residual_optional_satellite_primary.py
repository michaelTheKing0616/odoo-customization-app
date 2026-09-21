"""Residual full_app: optional secondary noun must never become Generate primary.

Class (Vehicle Request Generate regression + Leave Request sibling):
- Brief main document noun locks canvas primary (Vehicle Request / Leave Request)
- Optional «link/create X» / «also Y» stay secondary craft on the primary —
  never retitle canvas, never replace primary model, never explode domain satellites
- Stated workflow states win (not helpdesk draft/on_hold/closed)
- Date range → Date when no time-of-day
- AI_INTENT_LLM=off must pass
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.no_app_db

os.environ["AI_INTENT_LLM"] = "off"

from app.ai_conversation.understand import build_understanding  # noqa: E402
from app.ai_depth import classify_ambition  # noqa: E402
from app.ai_document_shape import (  # noqa: E402
    classify_document_shape,
    naming_from_residual,
)
from app.ai_draft_jobs import _finish_seed_draft  # noqa: E402
from app.ai_field_ir import typed_fields_from_constraints  # noqa: E402
from app.ai_pipeline import seed_studio_draft  # noqa: E402
from app.ai_residual_identity import (  # noqa: E402
    draft_mismatches_residual_identity,
    enforce_residual_draft_identity,
)
from app.preview_views import _pick_primary_model  # noqa: E402

VEHICLE = (
    "Build Vehicle request: employees request a fleet vehicle for a date range; "
    "manager approve/refuse; on approve, optionally link/create a Fleet vehicle "
    "assignment note. List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet or HR — pick the more natural parent."
)

LEAVE = (
    "Build Leave request: employees request leave for a date range; "
    "manager approve/refuse; on approve, optionally link/create a calendar block note. "
    "List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Time Off or HR — pick the more natural parent."
)


def _locked(prompt: str) -> dict:
    u = build_understanding(prompt)
    return {
        "title": u.title,
        "grain": u.grain,
        "inherit_existing": getattr(u, "inherit_existing", False),
        "host_model": u.host_model,
        "constraints": list(u.constraints or []),
    }


def _finish(prompt: str) -> dict:
    return _finish_seed_draft(
        prompt,
        seed_studio_draft(prompt),
        [],
        locked_understanding=_locked(prompt),
    )


@pytest.mark.parametrize(
    "prompt,title,slug",
    [
        (VEHICLE, "Vehicle Request", "vehicle_request"),
        (LEAVE, "Leave Request", "leave_request"),
    ],
)
def test_residual_naming_and_ambition_thin(prompt: str, title: str, slug: str) -> None:
    display, tech = naming_from_residual(prompt)
    assert display == title
    assert tech == slug
    assert classify_ambition(prompt) == "thin"
    shape = classify_document_shape(prompt, {})
    assert shape != "workspace"


@pytest.mark.parametrize(
    "prompt,mid,title",
    [
        (VEHICLE, "x_vehicle_request", "Vehicle Request"),
        (LEAVE, "x_leave_request", "Leave Request"),
    ],
)
def test_generate_primary_is_brief_noun(prompt: str, mid: str, title: str) -> None:
    out = _finish(prompt)
    assert out.get("display_name") == title
    models = [
        m.get("model")
        for m in (out.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    ]
    headers = [
        m
        for m in models
        if not str(m).endswith("_line") and not str(m).endswith("_party")
    ]
    assert mid in headers
    assert not any("assignment" in str(m) for m in headers)
    assert not any("calendar" in str(m) or "block" in str(m) for m in headers)
    picked = _pick_primary_model(out)
    assert picked is not None and picked[0] == mid
    grammar = out.get("_document_grammar") or {}
    assert int(grammar.get("extra_apps") or 0) == 0
    assert mid in str(grammar.get("header_model") or "")


@pytest.mark.parametrize("prompt", [VEHICLE, LEAVE])
def test_stated_states_and_dates(prompt: str) -> None:
    out = _finish(prompt)
    header = next(
        m
        for m in (out.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and not str(m.get("model")).endswith(("_line", "_party"))
    )
    fields = [f for f in (header.get("fields") or []) if isinstance(f, dict)]
    dates = [f for f in fields if f.get("ttype") in {"date", "datetime"}]
    assert dates, "expected date-range fields"
    assert all(f.get("ttype") == "date" for f in dates)
    state = next(
        (
            f
            for f in fields
            if f.get("ttype") == "selection"
            and "state" in str(f.get("name") or "").lower()
        ),
        None,
    )
    assert state is not None
    sel = str(state.get("selection") or "").lower()
    assert "draft" in sel and "submitted" in sel and "done" in sel
    assert "on_hold" not in sel and "closed" not in sel


def test_contaminated_assignment_notes_primary_is_rebuilt() -> None:
    draft = {
        "display_name": "Vehicle Assignment Notes",
        "technical_name": "vehicle_assignment_note",
        "grain": "full_app",
        "_user_prompt": VEHICLE,
        "models": [
            {
                "model": "x_vehicle_assignment_note",
                "description": "Vehicle Assignment Notes",
                "mode": "new",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": (
                            "[('draft','Draft'),('on_hold','On Hold'),"
                            "('closed','Closed')]"
                        ),
                    },
                ],
            },
            {
                "model": "x_vehicle_request",
                "description": "Vehicle Request",
                "mode": "new",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char", "string": "Name"}],
            },
            {
                "model": "x_vehicle_delivery",
                "description": "Vehicle Deliveries",
                "mode": "new",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_fleet_vehicle",
                "description": "Fleet Vehicles",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_vehicle_booking",
                "description": "Vehicle Bookings",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_vehicle_agreement",
                "description": "Vehicle Agreements",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_vehicle_unavailability",
                "description": "Track Vehicle Unavailability Dates",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
        ],
    }
    locked = {"title": "Vehicle Request", "grain": "full_app"}
    assert draft_mismatches_residual_identity(
        draft, prompt=VEHICLE, locked=locked, prefer_locked=True
    )
    notes = enforce_residual_draft_identity(
        draft, prompt=VEHICLE, locked=locked, prefer_locked=True
    )
    assert notes
    assert draft.get("display_name") == "Vehicle Request"
    models = [
        m.get("model") for m in (draft.get("models") or []) if isinstance(m, dict)
    ]
    assert "x_vehicle_request" in models
    assert not any("assignment" in str(m) for m in models)
    assert not any("delivery" in str(m) for m in models)
    picked = _pick_primary_model(draft)
    assert picked and picked[0] == "x_vehicle_request"


def test_same_stem_optional_peer_alone_mismatches() -> None:
    draft = {
        "display_name": "Vehicle Request",
        "technical_name": "vehicle_request",
        "grain": "full_app",
        "_user_prompt": VEHICLE,
        "models": [
            {
                "model": "x_vehicle_request",
                "description": "Vehicle Request",
                "mode": "new",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_vehicle_assignment_note",
                "description": "Vehicle Assignment Notes",
                "mode": "new",
                "is_workflow": True,
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
        ],
    }
    assert draft_mismatches_residual_identity(draft, prompt=VEHICLE) is True
    enforce_residual_draft_identity(draft, prompt=VEHICLE)
    models = [
        m.get("model") for m in (draft.get("models") or []) if isinstance(m, dict)
    ]
    assert "x_vehicle_request" in models
    assert "x_vehicle_assignment_note" not in models


def test_assignment_note_is_secondary_field_not_model() -> None:
    rows = [
        "New model x_vehicle_request (Vehicle Request)",
        "Employee→Employee",
        "Vehicle→Fleet Vehicle",
        "Start Date",
        "End Date",
        "State selection (Draft / Submitted / Approved / Refused / Done)",
        "Assignment Note→Fleet Vehicle Assignment",
        "Menu under Fleet",
        "Buttons: Submit, Approve, Refuse, Mark Done",
        "List + kanban by State",
        "Optional: link or create Assignment Note on Approve",
    ]
    fields = typed_fields_from_constraints(rows)
    by_name = {str(f.get("name")): f for f in fields}
    assert by_name["x_vehicle_id"]["ttype"] == "many2one"
    assert by_name["x_vehicle_id"]["relation"] == "fleet.vehicle"
    assert by_name["x_assignment_note"]["ttype"] == "text"
    assert by_name["x_start_date"]["ttype"] == "date"
    assert by_name["x_end_date"]["ttype"] == "date"
    assert "x_buttons_submit_approve_refuse_mark_don" not in by_name
    assert "x_list_kanban_by_state" not in by_name
    assert "x_optional_link_or_create_assignment_not" not in by_name
