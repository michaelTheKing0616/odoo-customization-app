"""Root Date vs Datetime classifier — prefer Date unless time is stated/implied."""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

from app.ai_conversation.refine import _guess_ttype
from app.ai_conversation.understand import _brief_full_app_must_do
from app.ai_document_shape import ensure_residual_must_do_fields, seed_register_from_brief
from app.ai_field_ir import (
    infer_date_or_datetime,
    typed_fields_from_constraints,
)
from app.ai_pipeline import seed_studio_draft
from app.preview_views import _coerce_preview_ttype

pytestmark = pytest.mark.no_app_db


@pytest.mark.parametrize(
    "label,want",
    [
        ("Visit date", "date"),
        ("Birth date", "date"),
        ("Due date", "date"),
        ("Expiry date", "date"),
        ("Start date", "date"),
        ("End date", "date"),
        ("Date", "date"),
        ("Visit datetime", "datetime"),
        ("Check-in time", "datetime"),
        ("check-in", "datetime"),
        ("Check-out time", "datetime"),
        ("Appointment start", "datetime"),
        ("Appointment end", "datetime"),
        ("Clock-in", "datetime"),
        ("Clock-out", "datetime"),
        ("Time in", "datetime"),
        ("Time out", "datetime"),
        ("Start time", "datetime"),
        ("date and time", "datetime"),
        ("SLA due date and time", "datetime"),
        ("Name", None),
        ("Purpose", None),
        ("Host", None),
    ],
)
def test_infer_date_or_datetime_both_sides(label: str, want: str | None) -> None:
    assert infer_date_or_datetime(label) == want


def test_must_do_constraints_visit_date_is_date() -> None:
    rows = ["Name", "Company→Contact", "Visit date", "Purpose selection (Meeting / Other)", "Host→Employee"]
    by = {f["string"]: f for f in typed_fields_from_constraints(rows)}
    assert by["Visit date"]["ttype"] == "date"
    assert by["Visit date"]["name"] == "x_visit_date"


def test_must_do_constraints_check_in_time_is_datetime() -> None:
    rows = ["Name", "Check-in time", "Check-out time"]
    by = {f["string"]: f for f in typed_fields_from_constraints(rows)}
    assert by["Check-in time"]["ttype"] == "datetime"
    assert by["Check-out time"]["ttype"] == "datetime"


def test_parenthetical_datetime_hint_preserved() -> None:
    prompt = (
        "Build a Gate Pass app. Model with Name, Arrival (datetime), "
        "Departure (datetime). Simple create/read. List + form."
    )
    must = _brief_full_app_must_do(prompt)
    joined = " | ".join(must).lower()
    assert "arrival" in joined and "datetime" in joined
    by = {f["name"]: f for f in typed_fields_from_constraints(must)}
    assert by["x_arrival_datetime"]["ttype"] == "datetime" or by.get("x_arrival", {}).get("ttype") == "datetime"
    # Accept either naming; ttype must be datetime for arrival/departure
    arrivals = [f for f in by.values() if "arrival" in f["name"]]
    assert arrivals and all(f["ttype"] == "datetime" for f in arrivals)


def test_visitor_log_seed_visit_date_is_date_not_datetime() -> None:
    prompt = (
        "Build a Visitor Log app. Model with Name, Company (link to Contact), "
        "Visit date, Purpose (selection: Meeting / Delivery / Other), and Host (Employee). "
        "Simple create/read. Menu under Employees. List + form."
    )
    draft = seed_studio_draft(prompt)
    fields = {
        f["name"]: f
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        for f in (m.get("fields") or [])
        if isinstance(f, dict)
    }
    assert "x_visit_date" in fields
    assert fields["x_visit_date"]["ttype"] == "date"
    assert fields["x_visit_date"]["string"] == "Visit date"


def test_must_do_corrects_wrong_datetime_to_date() -> None:
    draft = {
        "models": [
            {
                "model": "x_visitor_log",
                "description": "Visitor Log",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {"name": "x_visit_date", "ttype": "datetime", "string": "Visit date"},
                ],
            }
        ],
        "_user_prompt": (
            "Build a Visitor Log app. Model with Name, Company (link to Contact), "
            "Visit date, Purpose (selection: Meeting / Delivery / Other), and Host (Employee)."
        ),
    }
    notes = ensure_residual_must_do_fields(
        draft,
        prompt=draft["_user_prompt"],
    )
    fields = {f["name"]: f for f in draft["models"][0]["fields"]}
    assert fields["x_visit_date"]["ttype"] == "date"
    assert any("x_visit_date" in n and "date" in n for n in notes) or fields["x_visit_date"]["ttype"] == "date"


def test_field_pack_birth_date_and_check_in_guess() -> None:
    assert _guess_ttype("Birth date") == "date"
    assert _guess_ttype("Due date") == "date"
    assert _guess_ttype("Check-in time") == "datetime"
    assert _guess_ttype("Appointment start") == "datetime"


def test_preview_coerce_honest_date_sample_type() -> None:
    assert (
        _coerce_preview_ttype(
            "x_visit_date",
            {"ttype": "date", "string": "Visit date"},
        )
        == "date"
    )
    assert (
        _coerce_preview_ttype(
            "x_check_in_time",
            {"ttype": "datetime", "string": "Check-in time"},
        )
        == "datetime"
    )
    # Weak IR char + date label → date for honest preview chrome
    assert (
        _coerce_preview_ttype(
            "x_visit_date",
            {"ttype": "char", "string": "Visit date"},
        )
        == "date"
    )


def test_register_seed_merges_visit_date_even_with_partial_columns() -> None:
    prompt = (
        "Visitor Log: Name, Company (link to Contact), Visit date, "
        "Purpose (selection: Meeting / Delivery / Other), Host (Employee)."
    )
    draft: dict = {"models": [], "_user_prompt": prompt}
    seed_register_from_brief(draft, prompt=prompt)
    fields = {f["name"]: f for f in draft["models"][0]["fields"]}
    assert fields["x_visit_date"]["ttype"] == "date"


def test_feature_slice_appointment_range_datetime() -> None:
    rows = typed_fields_from_constraints(
        ["Appointment start", "Appointment end", "Due date"]
    )
    by = {f["string"]: f["ttype"] for f in rows}
    assert by["Appointment start"] == "datetime"
    assert by["Appointment end"] == "datetime"
    assert by["Due date"] == "date"
