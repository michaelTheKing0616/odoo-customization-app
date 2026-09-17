"""Preview view enricher — rigorous coverage for OdooPreviewKit IR."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

import pytest

from app.ai_generation_engine import attach_generation_engine
from app.preview_views import (
    build_form_preview,
    build_preview_views,
    residual_form_preview,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "draft_supermarket5_2026-08-07.json"


@pytest.fixture
def supermarket_draft() -> dict:
    return json.loads(FIXTURE.read_text())


def test_primary_model_prefers_richest_workflow(supermarket_draft: dict) -> None:
    previews = build_preview_views(supermarket_draft)
    form = previews["form"]
    assert form is not None
    assert form["model"] == "x_store_order"
    assert form["type"] == "form"
    assert form["groupLayout"] == "two-column"
    assert len(form["groups"]) >= 2
    assert form["statusbar"] is not None
    assert form["statusbar"]["stages"] == ["draft", "confirmed", "picking", "delivered"]
    assert form["headerButtons"]
    assert any(b["variant"] == "primary" for b in form["headerButtons"])
    assert form["chatter"] == "stub"


def test_list_and_kanban_align_to_primary_model(supermarket_draft: dict) -> None:
    previews = build_preview_views(supermarket_draft)
    assert previews["list"] is not None
    assert previews["list"]["model"] == "x_store_order"
    assert len(previews["list"]["columns"]) >= 4
    assert previews["list"]["decorations"]["danger"]
    assert previews["kanban"] is not None
    assert previews["kanban"]["groupBy"] == "x_status"


def test_line_model_hides_statusbar_and_chatter(supermarket_draft: dict) -> None:
    form = build_form_preview(supermarket_draft, model="x_store_order_line")
    assert form is not None
    assert form["statusbar"] is None
    assert form["headerButtons"] == []
    assert form["chatter"] == "hidden"


def test_smart_buttons_capped_and_scoped(supermarket_draft: dict) -> None:
    form = build_form_preview(supermarket_draft, model="x_branch")
    assert form is not None
    assert 1 <= len(form["smartButtons"]) <= 6
    labels = [b["string"] for b in form["smartButtons"]]
    assert any("order" in s.lower() or "promotion" in s.lower() or "transfer" in s.lower() for s in labels)


def test_field_map_is_per_model_not_global_merge() -> None:
    """Same field name on two models must not leak strings across models."""
    draft = {
        "depends": ["mail"],
        "models": [
            {
                "model": "x_alpha",
                "description": "Alpha",
                "is_workflow": True,
                "state_field": {
                    "transitions": [["a", "b"], ["b", "c"]],
                    "statusbar_visible": ["a", "b", "c"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Alpha Name"},
                    {"name": "x_status", "ttype": "selection", "selection": [["a", "A"]]},
                ],
            },
            {
                "model": "x_beta",
                "description": "Beta",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Beta Name"},
                ],
            },
        ],
        "views": [
            {
                "type": "form",
                "model": "x_alpha",
                "arch": (
                    '<form string="Alpha">'
                    '<header><field name="x_status" widget="statusbar" '
                    'statusbar_visible="a,b,c"/></header>'
                    '<sheet><group string="Identity"><field name="x_name"/></group></sheet>'
                    "</form>"
                ),
            }
        ],
    }
    form = build_form_preview(draft)
    assert form is not None
    assert form["model"] == "x_alpha"
    names = {f["name"]: f["string"] for g in form["groups"] for f in g["fields"]}
    assert names["x_name"] == "Alpha Name"


def test_preview_two_column_unwraps_odoo_col2_sheet_groups() -> None:
    draft = {
        "models": [
            {
                "model": "x_ticket",
                "description": "Ticket",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Subject"},
                    {"name": "x_priority", "ttype": "selection", "string": "Priority"},
                ],
            }
        ],
        "views": [
            {
                "type": "form",
                "model": "x_ticket",
                "arch": (
                    '<form string="Ticket"><sheet>'
                    '<group col="2">'
                    '<group string="Identity"><field name="x_name"/></group>'
                    '<group string="Details"><field name="x_priority"/></group>'
                    "</group></sheet></form>"
                ),
            }
        ],
    }
    form = build_form_preview(draft)
    assert form is not None
    assert form["groupLayout"] == "two-column"
    labels = [g["string"] for g in form["groups"]]
    assert "Identity" in labels
    assert "Details" in labels
    names = {f["name"] for g in form["groups"] for f in g["fields"]}
    assert names == {"x_name", "x_priority"}


def test_arch_smart_buttons_fallback_when_draft_ir_empty() -> None:
    form_el = Element("form", {"string": "Ticket"})
    header = SubElement(form_el, "header")
    SubElement(
        header,
        "field",
        {"name": "x_status", "widget": "statusbar", "statusbar_visible": "new,done"},
    )
    sheet = SubElement(form_el, "sheet")
    box = SubElement(sheet, "div", {"name": "button_box", "class": "oe_button_box"})
    btn = SubElement(
        box,
        "button",
        {"type": "object", "class": "oe_stat_button", "icon": "fa-list", "name": "action_tasks"},
    )
    span = SubElement(btn, "span", {"class": "o_stat_text"})
    span.text = "Tasks"
    SubElement(SubElement(sheet, "group", {"string": "Identity"}), "field", {"name": "x_name"})
    arch = tostring(form_el, encoding="unicode")

    draft = {
        "depends": ["mail"],
        "models": [
            {
                "model": "x_ticket",
                "description": "Ticket",
                "is_workflow": True,
                "state_field": {
                    "transitions": [["new", "done"]],
                    "statusbar_visible": ["new", "done"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Subject"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": [["new", "New"], ["done", "Done"]],
                    },
                ],
            }
        ],
        "smart_buttons": [],
        "views": [{"type": "form", "model": "x_ticket", "arch": arch}],
    }
    form = build_form_preview(draft)
    assert form is not None
    assert form["smartButtons"]
    assert form["smartButtons"][0]["string"] == "Tasks"


def test_residual_form_preview_compat(supermarket_draft: dict) -> None:
    preview = residual_form_preview(supermarket_draft)
    assert preview is not None
    assert preview["type"] == "form"
    assert preview["groups"][0]["columns"] in (1, 2)


def test_attach_generation_engine_stamps_all_preview_slices(supermarket_draft: dict) -> None:
    draft = dict(supermarket_draft)
    draft.pop("_generation_engine", None)
    ir = attach_generation_engine(draft, "retail supermarket store orders")
    assert ir["form_preview"]["model"] == "x_store_order"
    assert ir["form_preview"]["groupLayout"] == "two-column"
    assert ir["list_preview"]["type"] == "list"
    assert ir["kanban_preview"]["type"] == "kanban"
    assert draft["_generation_engine"]["form_preview"]["statusbar"]["stages"]


def test_ttype_and_required_propagated_from_model(supermarket_draft: dict) -> None:
    form = build_form_preview(supermarket_draft)
    assert form is not None
    fields = {f["name"]: f for g in form["groups"] for f in g["fields"]}
    assert fields["x_name"]["ttype"] == "char"
    assert fields["x_name"]["required"] is True
    if "x_partner_id" in fields:
        assert fields["x_partner_id"]["ttype"] == "many2one"


def test_field_pack_inherit_preview_uses_host_form() -> None:
    from app.ai_component_builder import draft_component_from_prompt
    from app.ai_generation_engine import attach_generation_engine

    prompt = (
        "On vendor bills only, add Vendor TIN. Show it on the vendor bill form, "
        "required before Confirm. Do not add it on customer invoices."
    )
    draft, _, _ = draft_component_from_prompt(
        prompt,
        available_models=["account.move", "sale.order"],
    )
    draft["_user_prompt"] = prompt
    ir = attach_generation_engine(draft, prompt)
    form = ir.get("form_preview")
    assert form is not None
    assert form["model"] == "account.move"
    assert form["title"] == "Vendor bill"
    assert form["chatter"] == "hidden"
    labels = {f["string"] for g in form["groups"] for f in g["fields"]}
    assert any("tin" in s.lower() for s in labels)
    assert draft.get("display_name") == "Vendor bill fields"
    names = {f["name"] for g in form["groups"] for f in g["fields"]}
    assert any(n.startswith("x_") for n in names)
    built = build_form_preview(draft)
    assert built is not None
    assert built["model"] == "account.move"



def test_s1_contacts_inherit_preview_fidelity() -> None:
    """Contacts S1: Contact title, Delivery group, boolean checkbox field, host skeleton."""
    from app.ai_component_builder import draft_component_from_prompt
    from app.ai_generation_engine import attach_generation_engine

    prompt = (
        "On Contacts (res.partner), add checkbox Preferred for delivery and "
        "Delivery notes text under Delivery group. Do not create a new app."
    )
    draft, _, _ = draft_component_from_prompt(
        prompt,
        available_models=["res.partner", "sale.order", "account.move"],
    )
    draft["_user_prompt"] = prompt
    ir = attach_generation_engine(draft, prompt)
    form = ir.get("form_preview")
    assert form is not None
    assert form["model"] == "res.partner"
    assert form["title"] == "Contact"
    assert form.get("appLabel") == "Contacts"
    assert form["title"] != "Res"
    group_titles = [g.get("string") for g in form.get("groups") or []]
    assert "Delivery" in group_titles
    assert "Res" not in group_titles
    # Host skeleton chrome present
    group_ids = {g.get("id") for g in form.get("groups") or []}
    assert "host_identity" in group_ids
    assert "slot_named_group" in group_ids
    fields = {f["name"]: f for g in form["groups"] for f in g["fields"]}
    assert "x_preferred_for_delivery" in fields
    assert fields["x_preferred_for_delivery"]["ttype"] == "boolean"
    assert fields["x_preferred_for_delivery"]["string"] == "Preferred for delivery"
    assert "x_delivery_notes" in fields
    assert fields["x_delivery_notes"]["ttype"] == "text"
    # No x_studio_* / x_res leftovers
    assert not any(n.startswith("x_studio_") for n in fields)
    assert "x_res" not in fields
    # Delivery is a group title, not a selection field
    assert "Delivery" not in fields
    assert all(f.get("ttype") != "selection" or f.get("string") != "Delivery" for f in fields.values())


def test_preview_rewrites_x_studio_field_names() -> None:
    from app.preview_views import build_form_preview

    draft = {
        "_user_prompt": "On Contacts add a note",
        "models": [
            {
                "model": "res.partner",
                "mode": "inherit",
                "fields": [
                    {
                        "name": "x_studio_preferred_delivery",
                        "ttype": "boolean",
                        "string": "Preferred for delivery",
                    }
                ],
            }
        ],
        "_form_slots": {
            "host": "res.partner",
            "fields": {"x_studio_preferred_delivery": "new_tab"},
            "catalog": [],
            "tab_title": "Delivery",
            "group_title": "Delivery",
        },
    }
    form = build_form_preview(draft)
    assert form is not None
    names = {f["name"] for g in form["groups"] for f in g["fields"]}
    assert "x_preferred_delivery" in names or "x_studio_preferred_delivery" not in {
        n for n in names if n.startswith("x_")
    }
    assert all(not n.startswith("x_studio_") for n in names if n.startswith("x_"))
