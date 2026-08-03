"""Compendium §15 niche widgets — designer palette (extends §4 curated catalog)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NicheWidget:
    id: str
    label: str
    recommended_ttypes: tuple[str, ...]
    view_types: tuple[str, ...] = ("form", "list", "kanban")
    hint: str = ""
    supporting_field: dict[str, object] | None = None


# Stable contract: names + indices only (hexes sampled live per instance — not hardcoded truth).
COLOR_PALETTE: tuple[dict[str, object], ...] = (
    {"index": 0, "name": "no_color"},
    {"index": 1, "name": "red"},
    {"index": 2, "name": "orange"},
    {"index": 3, "name": "yellow"},
    {"index": 4, "name": "lightblue"},
    {"index": 5, "name": "green"},
    {"index": 6, "name": "magenta"},
    {"index": 7, "name": "purple"},
    {"index": 8, "name": "blue"},
    {"index": 9, "name": "lightgreen"},
    {"index": 10, "name": "brown"},
)

NICHE_WIDGETS: tuple[NicheWidget, ...] = (
    NicheWidget(
        "kanban_state",
        "Kanban state",
        ("selection",),
        ("form", "kanban"),
        "widget=kanban_state on selection (e.g. x_kanban_state)",
    ),
    NicheWidget(
        "color",
        "Color index",
        ("integer",),
        view_types=("form", "list", "kanban"),
        hint="widget=color — uses Odoo 11-color palette",
        supporting_field={
            "name": "x_color",
            "ttype": "integer",
            "string": "Color",
        },
    ),
    NicheWidget(
        "boolean_favorite",
        "Favorite star",
        ("boolean",),
        hint="widget=boolean_favorite",
        supporting_field={"name": "x_favorite", "ttype": "boolean", "string": "Favorite"},
    ),
    NicheWidget(
        "boolean_toggle",
        "Toggle",
        ("boolean",),
        hint="widget=boolean_toggle",
    ),
    NicheWidget(
        "many2many_tags_avatar",
        "Tags with avatars",
        ("many2many",),
        hint="widget=many2many_tags_avatar",
    ),
    NicheWidget(
        "many2one_avatar_user",
        "User avatar",
        ("many2one",),
        hint="widget=many2one_avatar_user — relation res.users",
        supporting_field={
            "name": "x_user_id",
            "ttype": "many2one",
            "string": "User",
            "relation": "res.users",
        },
    ),
    NicheWidget(
        "activity_exception",
        "Activity exception",
        ("char", "selection"),
        view_types=("list", "kanban"),
        hint="Decorates rows with activity_exception (list/kanban)",
    ),
    NicheWidget(
        "state_selection",
        "State selection",
        ("selection",),
        ("form", "list", "kanban"),
        hint="widget=state_selection",
    ),
)


def niche_widgets_for_view(view_type: str) -> tuple[NicheWidget, ...]:
    vt = view_type if view_type != "tree" else "list"
    return tuple(w for w in NICHE_WIDGETS if vt in w.view_types)


def niche_widget_by_id(widget_id: str) -> NicheWidget | None:
    for w in NICHE_WIDGETS:
        if w.id == widget_id:
            return w
    return None


def merge_widget_catalog_ttype(ttype: str) -> tuple[str, ...]:
    """Widget ids valid for ttype including niche palette entries."""
    from odoo_client.widget_catalog import widgets_for_ttype

    base = {w.id for w in widgets_for_ttype(ttype)}
    for nw in NICHE_WIDGETS:
        if ttype in nw.recommended_ttypes:
            base.add(nw.id)
    return tuple(sorted(base))
