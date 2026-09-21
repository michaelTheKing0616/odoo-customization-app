"""One notes surface per cue — class-wide (not Vehicle-only).

When the brief names Assignment Note / Remarks / … OR implies a single free-text
note, Generate must not also keep a generic Notes/Description sibling from packs
or padding.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.no_app_db

os.environ["AI_INTENT_LLM"] = "off"

from app.ai_brief_cues import (  # noqa: E402
    brief_asks_description,
    brief_asks_generic_notes,
    brief_has_named_notes_cue,
    brief_has_priority_cue,
    dedupe_notes_surfaces,
    honor_stated_brief_cues,
    is_bare_generic_notes_field,
    is_named_notes_field,
)
from app.ai_conversation.understand import build_understanding  # noqa: E402
from app.ai_draft_jobs import _finish_seed_draft  # noqa: E402
from app.ai_pipeline import seed_studio_draft  # noqa: E402

VEHICLE = (
    "Build Vehicle request: employees request a fleet vehicle for a date range; "
    "manager approve/refuse; on approve, optionally link/create a Fleet vehicle "
    "assignment note. List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet or HR — pick the more natural parent."
)

NOTES_ONLY = (
    "Build Incident Log: model with Name, Date, and notes. "
    "Simple list + form, menu under Services. No workflow beyond create/read."
)

REMARKS = (
    "Build Ticket Desk: Name, Subject, and Remarks. "
    "Simple list + form. No other notes or description fields."
)

PREFER_SALES = (
    "Extend Sales Orders: add Customer PO reference and Required delivery window "
    "(date range or start/end dates). On the form, show a status hint when the order "
    "is confirmed but no delivery document is attached in Documents. Prefer inherit/extend "
    "— do not invent a parallel Sales app."
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


def _primary(draft: dict) -> dict:
    return next(
        m
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and not str(m.get("model")).endswith(("_line", "_party"))
    )


def _textish(header: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for f in header.get("fields") or []:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name") or "")
        string = str(f.get("string") or "")
        ttype = str(f.get("ttype") or "")
        blob = f"{name} {string}".lower()
        if ttype in {"text", "html"} or "note" in blob or string.lower() in {
            "notes",
            "description",
            "remarks",
            "comments",
            "assignment note",
        }:
            out.append((name, string))
    return out


def test_cue_helpers_named_vs_bare() -> None:
    assert brief_has_named_notes_cue(VEHICLE)
    assert not brief_asks_generic_notes(VEHICLE)
    assert brief_asks_generic_notes("Build X with notes")
    assert not brief_asks_generic_notes("Remarks field only")
    assert brief_asks_description("description and notes")
    assert is_named_notes_field(
        {"name": "x_assignment_note", "ttype": "text", "string": "Assignment Note"}
    )
    assert is_bare_generic_notes_field(
        {"name": "x_notes", "ttype": "text", "string": "Notes"}
    )
    assert is_named_notes_field(
        {"name": "x_remarks", "ttype": "text", "string": "Remarks"}
    )
    assert not is_bare_generic_notes_field(
        {"name": "x_remarks", "ttype": "text", "string": "Remarks"}
    )


def test_vehicle_assignment_note_no_generic_notes() -> None:
    out = _finish(VEHICLE)
    header = _primary(out)
    textish = _textish(header)
    names = {n for n, _ in textish}
    labels = {s.lower() for _, s in textish}
    assert "x_assignment_note" in names or "assignment note" in labels
    assert "x_notes" not in names
    assert "notes" not in labels
    assert "x_description" not in names
    assert "description" not in labels


def test_vehicle_dedupe_drops_injected_generic_sibling() -> None:
    draft = seed_studio_draft(VEHICLE)
    header = _primary(draft)
    header.setdefault("fields", []).append(
        {"name": "x_notes", "ttype": "text", "string": "Notes", "source": "pad"}
    )
    header["fields"].append(
        {"name": "x_description", "ttype": "text", "string": "Description", "source": "pad"}
    )
    notes = honor_stated_brief_cues(draft, prompt=VEHICLE)
    assert any("dropped generic notes" in n for n in notes)
    textish = _textish(header)
    names = {n for n, _ in textish}
    assert "x_assignment_note" in names
    assert "x_notes" not in names
    assert "x_description" not in names


def test_notes_only_residual_single_notes() -> None:
    assert brief_asks_generic_notes(NOTES_ONLY)
    assert not brief_has_named_notes_cue(NOTES_ONLY) or brief_asks_generic_notes(NOTES_ONLY)
    # Force the class polish on a dual-injected draft.
    draft = {
        "technical_name": "incident_log",
        "display_name": "Incident Log",
        "_user_prompt": NOTES_ONLY,
        "models": [
            {
                "model": "x_incident_log",
                "description": "Incident Log",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {"name": "x_date", "ttype": "date", "string": "Date"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                    {"name": "x_description", "ttype": "text", "string": "Description"},
                ],
            }
        ],
    }
    notes = dedupe_notes_surfaces(draft, prompt=NOTES_ONLY)
    assert notes
    header = draft["models"][0]
    names = {str(f.get("name")) for f in header["fields"]}
    assert "x_notes" in names
    assert "x_description" not in names


def test_remarks_named_drops_generic_notes() -> None:
    draft = {
        "technical_name": "ticket_desk",
        "display_name": "Ticket Desk",
        "_user_prompt": REMARKS,
        "models": [
            {
                "model": "x_ticket_desk",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {"name": "x_subject", "ttype": "char", "string": "Subject"},
                    {"name": "x_remarks", "ttype": "text", "string": "Remarks"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            }
        ],
    }
    notes = dedupe_notes_surfaces(draft, prompt=REMARKS)
    assert any("dropped generic notes" in n for n in notes)
    names = {str(f.get("name")) for f in draft["models"][0]["fields"]}
    assert "x_remarks" in names
    assert "x_notes" not in names


def test_prefer_sales_unchanged_grain() -> None:
    u = build_understanding(PREFER_SALES)
    assert getattr(u, "inherit_existing", False) is True or u.grain in {
        "field_pack",
        "feature_slice",
    }
    assert u.host_model == "sale.order"


def test_cross_ttype_assignment_note_keeps_one() -> None:
    """Same named cue must not materialize as both M2O and Multiline."""
    draft = {
        "technical_name": "vehicle_request",
        "display_name": "Vehicle Request",
        "_user_prompt": VEHICLE,
        "models": [
            {
                "model": "x_vehicle_request",
                "description": "Vehicle Request",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_assignment_note_id",
                        "ttype": "many2one",
                        "string": "Assignment Note",
                        "relation": "fleet.vehicle.assign",
                        "source": "stock_link",
                    },
                    {
                        "name": "x_assignment_note",
                        "ttype": "text",
                        "string": "Assignment Note",
                        "source": "notes_cue",
                    },
                ],
            }
        ],
    }
    notes = dedupe_notes_surfaces(draft, prompt=VEHICLE)
    assert any("cross-ttype" in n for n in notes)
    fields = draft["models"][0]["fields"]
    note_fields = [
        f
        for f in fields
        if "assignment note" in f"{f.get('name')} {f.get('string')}".lower()
    ]
    assert len(note_fields) == 1
    assert note_fields[0]["ttype"] == "text"
    assert note_fields[0]["name"] == "x_assignment_note"


def test_vehicle_no_priority_without_cue() -> None:
    out = _finish(VEHICLE)
    header = _primary(out)
    pri = [
        f
        for f in (header.get("fields") or [])
        if isinstance(f, dict)
        and (
            str(f.get("name") or "") in {"x_priority", "x_urgency", "x_importance"}
            or str(f.get("string") or "").strip().lower()
            in {"priority", "urgency", "importance"}
        )
    ]
    assert pri == []


def test_priority_cue_keeps_priority() -> None:
    """Sibling residual that names Priority must keep the Selection."""
    prompt = (
        "Build Support Ticket: Name, Subject, Priority (Low / Normal / High), "
        "and Description. Simple list + form, menu under Services."
    )
    assert brief_has_priority_cue(prompt)
    draft = {
        "technical_name": "support_ticket",
        "display_name": "Support Ticket",
        "_user_prompt": prompt,
        "models": [
            {
                "model": "x_support_ticket",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {"name": "x_subject", "ttype": "char", "string": "Subject"},
                    {
                        "name": "x_priority",
                        "ttype": "selection",
                        "string": "Priority",
                        "selection": "[('low','Low'),('normal','Normal'),('high','High')]",
                    },
                    {"name": "x_description", "ttype": "text", "string": "Description"},
                ],
            }
        ],
    }
    honor_stated_brief_cues(draft, prompt=prompt)
    names = {str(f.get("name")) for f in draft["models"][0]["fields"]}
    assert "x_priority" in names


def test_uncued_priority_dropped_by_honor() -> None:
    draft = {
        "technical_name": "vehicle_request",
        "display_name": "Vehicle Request",
        "_user_prompt": VEHICLE,
        "models": [
            {
                "model": "x_vehicle_request",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_priority",
                        "ttype": "selection",
                        "string": "Priority",
                        "selection": "[('low','Low'),('high','High')]",
                        "source": "density",
                    },
                ],
            }
        ],
    }
    notes = honor_stated_brief_cues(draft, prompt=VEHICLE)
    assert any("Priority" in n for n in notes)
    names = {str(f.get("name")) for f in draft["models"][0]["fields"]}
    assert "x_priority" not in names

