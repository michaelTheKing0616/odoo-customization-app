"""S1 Contacts field IR — multi-field extract, no junk, Delivery group."""

from __future__ import annotations

import pytest

from app.ai_component_builder import draft_component_from_prompt
from app.ai_conversation.understand import (
    Understanding,
    append_locked_diagnosis,
    attach_understanding,
    build_understanding,
)
from app.ai_field_ir import extract_field_ir, sanitize_inherit_extension_fields
from app.ai_form_slots import named_group_title, tab_title
from app.ai_grain import preferred_inherit_host
from app.ai_senior_shape import infer_extension_fields

pytestmark = pytest.mark.no_app_db

S1 = (
    "On Contacts (res.partner), add checkbox Preferred for delivery and "
    "Delivery notes text under Delivery group. Do not create a new app."
)
S1_ARTICLES = (
    "On Contacts, add checkbox Preferred for delivery and a Delivery notes text "
    "under a Delivery group. Do not create a new app."
)


def test_s1_exactly_two_fields_boolean_text_no_articles() -> None:
    fields = infer_extension_fields(S1_ARTICLES, pad=True)
    assert len(fields) == 2
    by = {f["name"]: f for f in fields}
    assert set(by) == {"x_preferred_for_delivery", "x_delivery_notes"}
    assert by["x_preferred_for_delivery"]["ttype"] == "boolean"
    assert by["x_preferred_for_delivery"]["string"] == "Preferred for delivery"
    assert by["x_delivery_notes"]["ttype"] == "text"
    assert by["x_delivery_notes"]["string"] == "Delivery notes"
    assert "x_new" not in by and "x_res" not in by


def test_s1_group_title_delivery_not_a_delivery() -> None:
    assert named_group_title(S1_ARTICLES) == "Delivery"
    assert tab_title(S1_ARTICLES) == "Delivery"
    draft, hosts, _ = draft_component_from_prompt(
        S1_ARTICLES, available_models=["res.partner", "stock.picking"]
    )
    assert hosts[0].model == "res.partner"
    assert draft["_form_slots"]["group_title"] == "Delivery"
    assert draft["_form_slots"]["tab_title"] == "Delivery"
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert names == {"x_preferred_for_delivery", "x_delivery_notes"}


def test_s1_must_do_constraints_alone_same_ir() -> None:
    constraints = [
        "On Contacts (res.partner)",
        "Checkbox: Preferred for delivery",
        "Text field: Delivery notes",
        "Place under Delivery group",
        "Do not create a new home-screen app",
    ]
    fields = extract_field_ir("", constraints=constraints)
    assert [(f["name"], f["ttype"], f["string"]) for f in fields] == [
        ("x_preferred_for_delivery", "boolean", "Preferred for delivery"),
        ("x_delivery_notes", "text", "Delivery notes"),
    ]


def test_no_new_app_does_not_create_field() -> None:
    assert extract_field_ir("Do not create a new app.") == []
    assert infer_extension_fields("Do not create a new app.", pad=True) == []
    names = {
        f["name"]
        for f in infer_extension_fields(
            "On Contacts (res.partner). Do not create a new app.", pad=True
        )
    }
    assert "x_new" not in names
    assert "x_app" not in names


def test_host_contradiction_absent_when_understanding_partner() -> None:
    assert preferred_inherit_host(S1) == "res.partner"
    draft, _, _ = draft_component_from_prompt(
        S1, available_models=["res.partner", "stock.picking"]
    )
    u = build_understanding(S1)
    assert u.host_model == "res.partner"
    locked = append_locked_diagnosis(S1, u)
    attach_understanding(draft, locked)
    assert draft["_understanding"]["contradictions"] == []
    assert draft["_understanding"]["host_model"] == "res.partner"


def test_sanitize_drops_a_new_and_article_labels() -> None:
    draft = {
        "_user_prompt": S1_ARTICLES,
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [
                    {"name": "x_new", "ttype": "char", "string": "a new"},
                    {"name": "x_a_delivery_notes", "ttype": "text", "string": "a Delivery notes"},
                    {
                        "name": "x_preferred_for_delivery",
                        "ttype": "boolean",
                        "string": "Preferred for delivery",
                    },
                ],
            }
        ],
        "_form_slots": {
            "host": "res.partner",
            "fields": {},
            "catalog": [],
            "tab_title": "A Delivery",
            "group_title": "A Delivery",
        },
    }
    notes = sanitize_inherit_extension_fields(draft, prompt=S1_ARTICLES)
    assert notes
    by = {f["name"]: f for f in draft["models"][0]["fields"]}
    assert "x_new" not in by
    assert by["x_delivery_notes"]["string"] == "Delivery notes"
    assert draft["_form_slots"]["group_title"] == "Delivery"


def test_where_on_catalog_shows_delivery_group_not_new_tab() -> None:
    """Where-on picker must show Delivery group, not New tab, for S1 briefs."""
    from app.ai_form_slots import apply_form_slots, named_group_title, slot_catalog

    assert named_group_title(
        'under a small "Delivery" group'
    ) == "Delivery"
    catalog = slot_catalog("res.partner", group_title="Delivery")
    named = next(row for row in catalog if row["id"] == "new_tab")
    assert named["label"] == "Delivery group"
    assert "New tab" not in named["label"]
    assert named["phrase"] == "under Delivery group"

    draft, _, _ = draft_component_from_prompt(
        S1_ARTICLES, available_models=["res.partner", "stock.picking"]
    )
    apply_form_slots(draft, prompt=S1_ARTICLES)
    stamp = draft["_form_slots"]
    assert stamp["group_title"] == "Delivery"
    labeled = next(row for row in stamp["catalog"] if row["id"] == "new_tab")
    assert labeled["label"] == "Delivery group"
    fields = stamp["fields"]
    assert set(fields.values()) == {"new_tab"}
