"""CMP-3 niche widget catalog and arch emission."""

from __future__ import annotations

from odoo_client.niche_widget_catalog import COLOR_PALETTE, niche_widgets_for_view
from odoo_client.view_arch import FieldNode, FormViewSpec, GroupNode, render_form_arch
from odoo_client.widget_catalog import validate_widget_for_ttype


def test_color_palette_has_eleven_named_indices() -> None:
    assert len(COLOR_PALETTE) == 11
    assert COLOR_PALETTE[0]["name"] == "no_color"
    assert COLOR_PALETTE[10]["name"] == "brown"


def test_kanban_includes_activity_exception() -> None:
    ids = {w.id for w in niche_widgets_for_view("kanban")}
    assert "activity_exception" in ids
    assert "kanban_state" in ids


def test_list_excludes_kanban_only_widgets() -> None:
    ids = {w.id for w in niche_widgets_for_view("list")}
    assert "activity_exception" in ids
    assert "boolean_favorite" in ids


def test_validate_accepts_niche_widgets() -> None:
    assert validate_widget_for_ttype("boolean", "boolean_favorite") == "boolean_favorite"
    assert validate_widget_for_ttype("integer", "color") == "color"
    assert validate_widget_for_ttype("selection", "state_selection") == "state_selection"


def test_form_arch_emits_niche_widget_attrs() -> None:
    arch = render_form_arch(
        FormViewSpec(
            string="Niche",
            children=[
                GroupNode(
                    children=[
                        FieldNode(name="x_favorite", widget="boolean_favorite"),
                        FieldNode(name="x_color", widget="color"),
                        FieldNode(name="x_stage", widget="state_selection"),
                    ]
                )
            ],
        )
    )
    assert 'widget="boolean_favorite"' in arch
    assert 'widget="color"' in arch
    assert 'widget="state_selection"' in arch
