"""P3 continuous invent — multi-brief class goldens (not Vehicle-only).

AI_INTENT_LLM=off deterministic floor. A complete draft is not the same as certified ≠ Autopilot.
"""

from __future__ import annotations

import os
import re

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_brief_cues import (  # noqa: E402
    brief_has_channel_cue,
    brief_has_priority_cue,
    brief_has_rate_cue,
    brief_has_severity_cue,
    brief_has_stage_cue,
    brief_has_type_cue,
    honor_stated_brief_cues,
    scrub_uncued_invent_from_llm_ast,
    scrub_uncued_invent_must_do_rows,
)
from app.ai_constraint_ast import ConstraintAST, ConstraintField  # noqa: E402
from app.ai_continuous_invent import continuous_invent_stamp  # noqa: E402
from app.ai_conversation.understand import build_understanding  # noqa: E402
from app.ai_document_shape import (  # noqa: E402
    classify_document_shape,
    may_add_line_satellite,
    may_add_party_satellite,
)
from app.ai_draft_jobs import _finish_seed_draft  # noqa: E402
from app.ai_operator_brief import build_operator_brief  # noqa: E402
from app.ai_pipeline import seed_studio_draft  # noqa: E402
from app.ai_residual_identity import scrub_residual_display_name  # noqa: E402


VEHICLE = (
    "Build Vehicle request: employees request a fleet vehicle for a date range; "
    "manager approve/refuse; on approve, optionally link/create a Fleet vehicle "
    "assignment note. List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet."
)
LEAVE = (
    "Build Leave request: employees request leave for a date range; "
    "manager approve/refuse; on approve, optionally link/create a calendar block note. "
    "List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Time Off."
)
INCIDENT = (
    "Build Incident Log: Name, Date, and notes. Simple list + form. Menu under Employees."
)
TICKET = (
    "Build Support Ticket: Name, Subject, Description. "
    "Simple list + form. Menu under Helpdesk or Services."
)
VISITOR = (
    "Build a tiny Visitor Log app: model with Name, Company (link to Contact), "
    "Visit date, Purpose (selection: Meeting / Delivery / Other), and Host (Employee). "
    "Simple list + form, menu under Services. No workflow beyond create/read."
)
DINING = (
    "Dining Tables for our restaurant. Name, Capacity, "
    "Status (selection: Free / Seated / Reserved). Simple list + form."
)
ASSET = (
    "Build Asset checkout: employees check out a tool for a date range; "
    "manager approve/refuse. List/kanban by state "
    "(Draft → Submitted → Approved/Refused → Done). Menu under Inventory."
)
PREFER_SALES = (
    "Extend Sales Orders: add Customer PO reference and Required delivery window "
    "(date range or start/end dates). Prefer inherit/extend — do not invent a parallel Sales app."
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


def _header(draft: dict) -> dict:
    return next(
        m
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and not str(m.get("model")).endswith(("_line", "_party"))
    )


def _x_models(draft: dict) -> list[str]:
    return [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    ]


def _selection_labels(header: dict) -> set[str]:
    out: set[str] = set()
    for f in header.get("fields") or []:
        if not isinstance(f, dict):
            continue
        if str(f.get("ttype") or "") != "selection":
            continue
        out.add(str(f.get("string") or f.get("name") or "").strip().lower())
    return out


def _note_fields(header: dict) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for f in header.get("fields") or []:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name") or "")
        string = str(f.get("string") or "")
        blob = f"{name} {string}".lower()
        if re.search(r"note|remark|comment|description", blob):
            rows.append((name, string, str(f.get("ttype") or "")))
    return rows


def test_continuous_invent_stamp() -> None:
    stamp = continuous_invent_stamp(prove_status="passed")
    assert stamp["class_id"] == "continuous_invent"
    assert stamp["phase"] == "P3"
    assert stamp["flash_free_floor"] is True
    assert "uncued_selection" in stamp["gates"]
    assert stamp["promote_human"] is True


@pytest.mark.parametrize(
    "prompt,title,note_substr",
    [
        (VEHICLE, "Vehicle Request", "assignment"),
        (LEAVE, "Leave Request", "calendar block"),
        (INCIDENT, "Incident Log", "notes"),
        (ASSET, "Asset Checkout", None),
        (VISITOR, "Visitor Log", None),
        (TICKET, "Support Ticket", "description"),
        (DINING, "Dining Tables", None),
    ],
)
def test_diagnosis_name_and_primary_canvas(
    prompt: str, title: str, note_substr: str | None
) -> None:
    u = build_understanding(prompt)
    assert u.title == title
    assert "management" not in u.title.lower()
    draft = _finish(prompt)
    assert draft.get("display_name") == title
    assert scrub_residual_display_name(f"{title} Management") == title
    xmods = _x_models(draft)
    # One primary residual — no party/line invent, no foreign pack canvas.
    assert len([m for m in xmods if not m.endswith(("_line", "_party"))]) == 1
    assert not any(m.endswith("_line") or m.endswith("_party") for m in xmods)
    header = _header(draft)
    assert str(header.get("model") or "").startswith("x_")
    if note_substr:
        notes = _note_fields(header)
        assert notes, f"expected note surface containing {note_substr}"
        assert any(note_substr in f"{n} {s}".lower() for n, s, _ in notes)
        # One cue → one field
        assert len(notes) == 1


def test_leave_note_is_calendar_block_not_assignment() -> None:
    u = build_understanding(LEAVE)
    joined = " | ".join(u.constraints or [])
    assert "Calendar Block Note" in joined
    assert "Assignment Note" not in joined
    draft = _finish(LEAVE)
    header = _header(draft)
    names = {str(f.get("name")) for f in header.get("fields") or []}
    assert "x_calendar_block_note" in names
    assert "x_assignment_note" not in names
    # calendar block note is a Notes surface — not calendar.event stock invent
    assert "calendar" not in build_operator_brief(LEAVE).stock_reuse
    assert not any(
        str(m.get("model")) == "calendar.event"
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
    )


def test_incident_notes_not_and_notes_char() -> None:
    u = build_understanding(INCIDENT)
    assert any(c == "Text field: Notes" or c == "Notes" for c in (u.constraints or []))
    assert not any("and notes" in c.lower() for c in (u.constraints or []))
    draft = _finish(INCIDENT)
    header = _header(draft)
    by_name = {
        str(f.get("name")): f
        for f in (header.get("fields") or [])
        if isinstance(f, dict)
    }
    assert "x_notes" in by_name
    assert by_name["x_notes"]["ttype"] == "text"
    assert "x_and_notes" not in by_name


def test_thin_ticket_no_party_line_satellites() -> None:
    draft = _finish(TICKET)
    assert classify_document_shape(TICKET, draft) == "transactional_header"
    assert may_add_line_satellite(draft, prompt=TICKET) is False
    assert may_add_party_satellite(draft, prompt=TICKET) is False
    xmods = _x_models(draft)
    assert xmods == ["x_support_ticket"]


def test_thin_dining_no_restaurant_workspace_bleed() -> None:
    draft = _finish(DINING)
    assert draft.get("domain_pack") in (None, "", "restaurant")  # seed may skip
    # Shape must not explode party/line even if pack matched lexically.
    assert may_add_line_satellite(draft, prompt=DINING) is False
    assert may_add_party_satellite(draft, prompt=DINING) is False
    assert not any(
        str(m.get("model") or "").endswith(("_line", "_party"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
    )
    header = _header(draft)
    labels = {str(f.get("string") or "") for f in header.get("fields") or []}
    assert "Capacity" in labels or any("capacity" in x.lower() for x in labels)
    assert "Status" in labels or any("status" in x.lower() for x in labels)


@pytest.mark.parametrize("prompt", [VEHICLE, LEAVE, ASSET, INCIDENT, TICKET, VISITOR, DINING])
def test_no_uncued_type_priority_rate(prompt: str) -> None:
    assert not brief_has_type_cue(prompt)
    assert not brief_has_priority_cue(prompt)
    assert not brief_has_rate_cue(prompt)
    draft = _finish(prompt)
    header = _header(draft)
    sels = _selection_labels(header)
    # State / Purpose / Status (cued) may remain; invent family must not.
    banned = {
        "type",
        "category",
        "kind",
        "class",
        "priority",
        "urgency",
        "importance",
        "rate unit",
        "rate uom",
        "uom",
        "unit",
        "vehicle type",
        "severity",
        "channel",
        "stage",
    }
    assert not (sels & banned), sels
    assert not brief_has_severity_cue(prompt)
    assert not brief_has_channel_cue(prompt)
    assert not brief_has_stage_cue(prompt)


@pytest.mark.parametrize("prompt", [VEHICLE, LEAVE, ASSET])
def test_date_range_is_date_not_datetime(prompt: str) -> None:
    draft = _finish(prompt)
    header = _header(draft)
    dates = [
        f
        for f in (header.get("fields") or [])
        if isinstance(f, dict) and f.get("ttype") in {"date", "datetime"}
    ]
    assert dates
    assert all(f.get("ttype") == "date" for f in dates)


def test_visitor_purpose_kept_meeting_not_calendar_reuse() -> None:
    """Purpose (Meeting / …) is a cued Selection — not calendar.event stock invent."""
    assert "calendar" not in build_operator_brief(VISITOR).stock_reuse
    draft = _finish(VISITOR)
    header = _header(draft)
    sels = _selection_labels(header)
    assert "purpose" in sels
    assert not any(
        str(m.get("model")) == "calendar.event"
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
    )


def test_prefer_sales_still_prefer() -> None:
    u = build_understanding(PREFER_SALES)
    assert getattr(u, "inherit_existing", False) is True or u.grain in {
        "field_pack",
        "feature_slice",
    }
    assert u.host_model == "sale.order"


def test_honor_drops_injected_uncued_priority_on_leave() -> None:
    draft = {
        "display_name": "Leave Request",
        "_user_prompt": LEAVE,
        "models": [
            {
                "model": "x_leave_request",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_priority",
                        "ttype": "selection",
                        "string": "Priority",
                        "selection": "[('0','Low'),('1','Normal')]",
                        "source": "density",
                    },
                    {
                        "name": "x_calendar_block_note",
                        "ttype": "text",
                        "string": "Calendar Block Note",
                    },
                ],
            }
        ],
    }
    notes = honor_stated_brief_cues(draft, prompt=LEAVE)
    assert any("Priority" in n or "priority" in n.lower() for n in notes)
    names = {str(f.get("name")) for f in draft["models"][0]["fields"]}
    assert "x_priority" not in names
    assert "x_calendar_block_note" in names


SEVERITY_CUE = (
    "Build Incident Log: Name, Date, Severity (selection: Low / Medium / High / Critical), "
    "and notes. Simple list + form. Menu under Employees."
)
CHANNEL_CUE = (
    "Build Support Ticket: Name, Subject, Channel (selection: Email / Phone / Chat / Web), "
    "Description. Simple list + form. Menu under Helpdesk."
)
STAGE_CUE = (
    "Build Deal Tracker: Name, Amount, Stage (selection: New / Qualified / Won / Lost). "
    "Simple list + form. Menu under CRM."
)


def test_honor_drops_uncued_severity_channel_stage_on_ticket() -> None:
    """Class-wide invent family — Severity/Channel/Stage drop when uncued."""
    draft = {
        "display_name": "Support Ticket",
        "_user_prompt": TICKET,
        "models": [
            {
                "model": "x_support_ticket",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_severity",
                        "ttype": "selection",
                        "string": "Severity",
                        "selection": "[('low','Low'),('high','High')]",
                        "source": "pack_default",
                    },
                    {
                        "name": "x_channel",
                        "ttype": "selection",
                        "string": "Channel",
                        "selection": "[('email','Email'),('phone','Phone')]",
                        "source": "density",
                    },
                    {
                        "name": "x_stage",
                        "ttype": "selection",
                        "string": "Stage",
                        "selection": "[('new','New'),('won','Won')]",
                        "source": "llm",
                    },
                    {
                        "name": "x_description",
                        "ttype": "text",
                        "string": "Description",
                    },
                ],
            }
        ],
    }
    notes = honor_stated_brief_cues(draft, prompt=TICKET)
    names = {str(f.get("name")) for f in draft["models"][0]["fields"]}
    assert "x_severity" not in names
    assert "x_channel" not in names
    assert "x_stage" not in names
    assert "x_description" in names
    blob = " | ".join(notes).lower()
    assert "severity" in blob and "channel" in blob and "stage" in blob


def test_severity_cue_keeps_severity() -> None:
    assert brief_has_severity_cue(SEVERITY_CUE)
    draft = {
        "display_name": "Incident Log",
        "_user_prompt": SEVERITY_CUE,
        "models": [
            {
                "model": "x_incident_log",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_severity",
                        "ttype": "selection",
                        "string": "Severity",
                        "selection": "[('low','Low'),('critical','Critical')]",
                    },
                ],
            }
        ],
    }
    honor_stated_brief_cues(draft, prompt=SEVERITY_CUE)
    names = {str(f.get("name")) for f in draft["models"][0]["fields"]}
    assert "x_severity" in names


def test_channel_cue_keeps_channel() -> None:
    assert brief_has_channel_cue(CHANNEL_CUE)
    draft = {
        "display_name": "Support Ticket",
        "_user_prompt": CHANNEL_CUE,
        "models": [
            {
                "model": "x_support_ticket",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_channel",
                        "ttype": "selection",
                        "string": "Channel",
                        "selection": "[('email','Email'),('phone','Phone')]",
                    },
                ],
            }
        ],
    }
    honor_stated_brief_cues(draft, prompt=CHANNEL_CUE)
    assert "x_channel" in {str(f.get("name")) for f in draft["models"][0]["fields"]}


def test_stage_cue_keeps_stage_not_confused_with_state() -> None:
    assert brief_has_stage_cue(STAGE_CUE)
    assert not brief_has_stage_cue(VEHICLE)  # by state ≠ Stage invent
    draft = {
        "display_name": "Deal Tracker",
        "_user_prompt": STAGE_CUE,
        "models": [
            {
                "model": "x_deal_tracker",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_stage",
                        "ttype": "selection",
                        "string": "Stage",
                        "selection": "[('new','New'),('won','Won')]",
                    },
                ],
            }
        ],
    }
    honor_stated_brief_cues(draft, prompt=STAGE_CUE)
    assert "x_stage" in {str(f.get("name")) for f in draft["models"][0]["fields"]}


def test_flash_on_honor_drops_uncued_invent_source_llm() -> None:
    """Flash-on path: source=llm/flash still dropped when cues absent (P3 gap)."""
    draft = {
        "display_name": "Leave Request",
        "_user_prompt": LEAVE,
        "models": [
            {
                "model": "x_leave_request",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_type",
                        "ttype": "selection",
                        "string": "Type",
                        "selection": "[('a','A'),('b','B')]",
                        "source": "flash",
                    },
                    {
                        "name": "x_severity",
                        "ttype": "char",
                        "string": "Severity",
                        "source": "llm",
                    },
                    {
                        "name": "x_channel",
                        "ttype": "selection",
                        "string": "Channel",
                        "source": "enrich",
                    },
                    {
                        "name": "x_stage",
                        "ttype": "selection",
                        "string": "Stage",
                        "source": "proposal",
                    },
                    {
                        "name": "x_calendar_block_note",
                        "ttype": "text",
                        "string": "Calendar Block Note",
                    },
                ],
            }
        ],
    }
    notes = honor_stated_brief_cues(draft, prompt=LEAVE)
    names = {str(f.get("name")) for f in draft["models"][0]["fields"]}
    assert "x_type" not in names
    assert "x_severity" not in names
    assert "x_channel" not in names
    assert "x_stage" not in names
    assert "x_calendar_block_note" in names
    assert notes


def test_flash_ast_scrub_drops_uncued_severity_channel_stage_type() -> None:
    """Flash ConstraintAST invent fields scrubbed before Must-do merge."""
    llm = ConstraintAST(
        grain="full_app",
        fields=[
            ConstraintField(label="Name", ttype="char"),
            ConstraintField(label="Severity", ttype="selection"),
            ConstraintField(label="Channel", ttype="selection"),
            ConstraintField(label="Stage", ttype="selection"),
            ConstraintField(label="Type", ttype="selection"),
            ConstraintField(label="Subject", ttype="char"),
        ],
        source="llm",
    )
    scrubbed = scrub_uncued_invent_from_llm_ast(llm, prompt=TICKET)
    labels = {f.label.lower() for f in scrubbed.fields}
    assert "severity" not in labels
    assert "channel" not in labels
    assert "stage" not in labels
    assert "type" not in labels
    assert "name" in labels and "subject" in labels

    rows = scrub_uncued_invent_must_do_rows(
        [
            "Field: Name",
            "Field: Severity",
            "Selection field: Channel",
            "Field: Stage",
            "Field: Type",
            "Field: Subject",
        ],
        prompt=TICKET,
    )
    joined = " | ".join(rows).lower()
    assert "severity" not in joined
    assert "channel" not in joined
    assert "stage" not in joined
    assert "type" not in joined
    assert "name" in joined and "subject" in joined


def test_flash_ast_keeps_cued_severity() -> None:
    llm = ConstraintAST(
        grain="full_app",
        fields=[
            ConstraintField(label="Name", ttype="char"),
            ConstraintField(label="Severity", ttype="selection"),
        ],
        source="llm",
    )
    scrubbed = scrub_uncued_invent_from_llm_ast(llm, prompt=SEVERITY_CUE)
    labels = {f.label.lower() for f in scrubbed.fields}
    assert "severity" in labels
