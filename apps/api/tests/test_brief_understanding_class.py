"""Class-wide brief understanding — stated states, stock menu parent, no invent.

Root class (not Vehicle-only): Flash-off deterministic floor must honor every
explicit cue in the brief for ALL residuals:
1. Stated workflow states (incl. terminal Done) materialize end-to-end; Contract count matches.
2. Named stock parent («under Fleet|HR|…») → menu under that app; never orphan-only home tile.
3. No invented Type/Category/Kind/Rate/Unit/UOM/Priority compounds without clear cues.
4. Diagnosis Name + Contract chrome match primary noun (no Management/System/Build fluff).
5. Prefer Sales / real packs still Prefer-reshape (control).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.no_app_db

os.environ["AI_INTENT_LLM"] = "off"

from app.ai_brief_cues import (  # noqa: E402
    brief_has_rate_cue,
    brief_has_type_cue,
    honor_stated_brief_cues,
    model_is_equipment_roster,
    stated_menu_parent,
    stated_workflow_states,
)
from app.ai_document_shape import naming_from_residual  # noqa: E402
from app.ai_domain_briefing import build_domain_briefing  # noqa: E402
from app.ai_residual_identity import scrub_residual_display_name  # noqa: E402
from app.ai_conversation.understand import build_understanding  # noqa: E402
from app.ai_draft_jobs import _finish_seed_draft  # noqa: E402
from app.ai_pipeline import seed_studio_draft  # noqa: E402

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

ASSET_CHECKOUT = (
    "Build Asset checkout: employees check out a tool for a date range; "
    "manager approve/refuse. List/kanban by state "
    "(Draft → Submitted → Approved/Refused → Done). "
    "Menu under Inventory."
)

PREFER_SALES = (
    "Extend Sales Orders: add Customer PO reference and Required delivery window "
    "(date range or start/end dates). On the form, show a status hint when the order "
    "is confirmed but no delivery document is attached in Documents. Prefer inherit/extend "
    "— do not invent a parallel Sales app."
)

VISITOR_NO_TYPE = (
    "Build a tiny Visitor Log app: model with Name, Company (link to Contact), "
    "Visit date, Purpose (selection: Meeting / Delivery / Other), and Host (Employee). "
    "Simple list + form, menu under Services. No workflow beyond create/read."
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


def _state_keys(header: dict) -> list[str]:
    sf = header.get("state_field") if isinstance(header.get("state_field"), dict) else {}
    if sf.get("states"):
        return [str(s) for s in sf["states"]]
    for f in header.get("fields") or []:
        if not isinstance(f, dict):
            continue
        if str(f.get("name") or "") in {"x_state", "x_status"}:
            import re

            return re.findall(r"\(\s*'([^']+)'\s*,", str(f.get("selection") or ""))
    return []


@pytest.mark.parametrize(
    "prompt,expect_done,expect_parent_mod",
    [
        (VEHICLE, True, "fleet"),
        (LEAVE, True, "hr"),
        (ASSET_CHECKOUT, True, "stock"),
    ],
)
def test_stated_states_and_stock_menu_parent(
    prompt: str, expect_done: bool, expect_parent_mod: str
) -> None:
    assert "done" in stated_workflow_states(prompt)
    parent = stated_menu_parent(prompt)
    assert parent is not None
    assert parent[1] == expect_parent_mod

    out = _finish(prompt)
    header = _header(out)
    keys = _state_keys(header)
    assert "draft" in keys and "submitted" in keys
    if expect_done:
        assert "done" in keys
    # Single workflow field — no 4-vs-5 fight
    state_names = [
        str(f.get("name"))
        for f in (header.get("fields") or [])
        if isinstance(f, dict) and str(f.get("name") or "") in {"x_state", "x_status"}
    ]
    assert len(state_names) == 1

    grammar = out.get("_document_grammar") or {}
    g_states = [str(s) for s in (grammar.get("states") or [])]
    if g_states:
        assert "done" in g_states
        assert len(g_states) == len(keys)

    # Menu under stock parent — not orphan home tile
    menus = [m for m in (out.get("menus") or []) if isinstance(m, dict)]
    assert menus
    rooted = [
        m
        for m in menus
        if str(m.get("parent_xml_id") or "").startswith(expect_parent_mod + ".")
    ]
    assert rooted, f"expected menu under {expect_parent_mod}.*, got {menus}"
    orphan_roots = [
        m
        for m in menus
        if not m.get("parent_xml_id")
        and not m.get("parent_id")
        and not m.get("action_xml_id")
    ]
    assert not orphan_roots, f"orphan home tile still present: {orphan_roots}"

    depends = {str(d) for d in (out.get("depends") or [])}
    assert expect_parent_mod in depends or (
        expect_parent_mod == "hr" and ("hr" in depends or "hr_holidays" in depends)
    )

    surface = out.get("_operator_surface") or {}
    summary = str(surface.get("summary") or "").lower()
    assert "home / app switcher" not in summary or "under " in summary


@pytest.mark.parametrize("prompt", [VEHICLE, LEAVE, ASSET_CHECKOUT, VISITOR_NO_TYPE])
def test_no_type_without_cues(prompt: str) -> None:
    assert not brief_has_type_cue(prompt)
    out = _finish(prompt)
    for m in out.get("models") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model") or "")
        if model_is_equipment_roster(mid):
            continue
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                continue
            name = str(f.get("name") or "")
            string = str(f.get("string") or "").lower()
            assert name not in {"x_type", "x_category", "x_kind", "x_class", "x_vehicle_type"}
            assert string not in {"type", "category", "kind", "class"}
            assert " type" not in f" {string}" and not string.endswith(" type")
            assert name not in {"x_rate_unit", "x_rate_uom", "x_uom", "x_unit", "x_rate_type"}
            assert string not in {"rate unit", "rate uom", "unit", "uom", "rate type"}


def test_prefer_sales_still_field_pack() -> None:
    u = build_understanding(PREFER_SALES)
    assert getattr(u, "inherit_existing", False) is True or u.grain in {
        "field_pack",
        "feature_slice",
    }
    assert u.host_model == "sale.order"
    # Prefer path must not become a residual full_app with its own home tile
    assert u.grain != "full_app" or getattr(u, "inherit_existing", False)


def test_equipment_roster_still_may_receive_type() -> None:
    assert model_is_equipment_roster("x_equipment")
    assert model_is_equipment_roster("x_vehicle")
    assert not model_is_equipment_roster("x_vehicle_request")
    assert not model_is_equipment_roster("x_leave_request")


def test_honor_cues_idempotent_on_seed() -> None:
    draft = seed_studio_draft(VEHICLE)
    n1 = honor_stated_brief_cues(draft, prompt=VEHICLE)
    n2 = honor_stated_brief_cues(draft, prompt=VEHICLE)
    assert isinstance(n1, list) and isinstance(n2, list)
    header = _header(draft)
    assert "done" in _state_keys(header)

TYPE_CUE = (
    "Build Vehicle request: employees request a fleet vehicle; "
    "include Vehicle Type (Economy / SUV / Van). "
    "List/kanban by state (Draft → Submitted → Approved/Refused → Done). "
    "Menu under Fleet."
)

RATE_CUE = (
    "Build Equipment rental contract: customer, equipment, Rate Unit "
    "(Hour / Day / Week), and amount. Menu under Sales."
)


def test_vehicle_no_rate_unit_without_pricing_cue() -> None:
    assert not brief_has_rate_cue(VEHICLE)
    out = _finish(VEHICLE)
    for m in out.get("models") or []:
        if not isinstance(m, dict):
            continue
        for f in m.get("fields") or []:
            if not isinstance(f, dict):
                continue
            name = str(f.get("name") or "")
            string = str(f.get("string") or "").strip().lower()
            assert name not in {"x_rate_unit", "x_rate_uom", "x_uom", "x_unit", "x_rate_type"}
            assert string not in {"rate unit", "rate uom", "unit", "uom", "rate type"}


def test_compound_vehicle_type_dropped_without_cue() -> None:
    """Compound «Vehicle Type» is same invent family as bare Type."""
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
                        "name": "x_vehicle_type",
                        "ttype": "selection",
                        "string": "Vehicle Type",
                        "selection": "[('suv','SUV'),('van','Van')]",
                        "required": True,
                        "source": "density",
                    },
                    {
                        "name": "x_rate_unit",
                        "ttype": "selection",
                        "string": "Rate Unit",
                        "selection": "[('day','Day'),('week','Week')]",
                        "required": True,
                        "source": "pack_default",
                    },
                ],
            }
        ],
    }
    notes = honor_stated_brief_cues(draft, prompt=VEHICLE)
    names = {str(f.get("name")) for f in draft["models"][0]["fields"]}
    assert "x_vehicle_type" not in names
    assert "x_rate_unit" not in names
    assert any("Type" in n or "Rate" in n for n in notes)


def test_type_cue_keeps_vehicle_type() -> None:
    assert brief_has_type_cue(TYPE_CUE)
    draft = {
        "technical_name": "vehicle_request",
        "display_name": "Vehicle Request",
        "_user_prompt": TYPE_CUE,
        "models": [
            {
                "model": "x_vehicle_request",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_vehicle_type",
                        "ttype": "selection",
                        "string": "Vehicle Type",
                        "selection": "[('economy','Economy'),('suv','SUV'),('van','Van')]",
                    },
                ],
            }
        ],
    }
    honor_stated_brief_cues(draft, prompt=TYPE_CUE)
    names = {str(f.get("name")) for f in draft["models"][0]["fields"]}
    assert "x_vehicle_type" in names


def test_rate_cue_keeps_rate_unit() -> None:
    assert brief_has_rate_cue(RATE_CUE)
    draft = {
        "technical_name": "equipment_rental",
        "display_name": "Equipment Rental",
        "_user_prompt": RATE_CUE,
        "models": [
            {
                "model": "x_equipment_rental",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name"},
                    {
                        "name": "x_rate_unit",
                        "ttype": "selection",
                        "string": "Rate Unit",
                        "selection": "[('hour','Hour'),('day','Day'),('week','Week')]",
                    },
                ],
            }
        ],
    }
    honor_stated_brief_cues(draft, prompt=RATE_CUE)
    names = {str(f.get("name")) for f in draft["models"][0]["fields"]}
    assert "x_rate_unit" in names


def test_diagnosis_name_strips_management_fluff() -> None:
    """Diagnosis Name + Contract chrome match primary noun — no Management fluff."""
    u = build_understanding(VEHICLE)
    assert u.title == "Vehicle Request"
    assert "management" not in u.title.lower()
    assert "build" not in u.title.lower()
    assert not u.title.lower().startswith("fleet ")
    display, slug = naming_from_residual(VEHICLE)
    assert display == "Vehicle Request"
    assert slug == "vehicle_request"
    assert scrub_residual_display_name("Fleet Vehicle Request Management") == "Vehicle Request"
    assert scrub_residual_display_name("Build Vehicle Request System") == "Vehicle Request"


def test_vehicle_request_does_not_match_rental_briefing() -> None:
    """Bare «fleet» menu parent must not trigger vehicle_rental rate/type bleed."""
    brief = build_domain_briefing(VEHICLE)
    assert brief.collocation_id != "vehicle_rental"
