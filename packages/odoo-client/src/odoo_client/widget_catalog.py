"""Curated Odoo field widgets per ttype (compendium §4 — not the full registry)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WidgetOption:
    id: str
    label: str
    hint: str = ""


WIDGETS_BY_TTYPE: dict[str, tuple[WidgetOption, ...]] = {
    "char": (
        WidgetOption("email", "Email", "widget=email"),
        WidgetOption("phone", "Phone", "widget=phone"),
        WidgetOption("url", "URL", "widget=url"),
        WidgetOption("barcode", "Barcode", "widget=barcode"),
    ),
    "integer": (
        WidgetOption("priority", "Priority", "widget=priority"),
    ),
    "float": (
        WidgetOption("float_time", "Float time", "widget=float_time"),
        WidgetOption("progressbar", "Progress bar", "widget=progressbar"),
        WidgetOption("percentage", "Percentage", "widget=percentage"),
    ),
    "selection": (
        WidgetOption("radio", "Radio", "widget=radio"),
        WidgetOption("priority", "Priority", "widget=priority"),
        WidgetOption("selection_badge", "Badge", "widget=selection_badge"),
    ),
    "many2many": (
        WidgetOption("many2many_tags", "Tags", "widget=many2many_tags"),
        WidgetOption("many2many_checkboxes", "Checkboxes", "widget=many2many_checkboxes"),
    ),
    "many2one": (
        WidgetOption("many2one_avatar", "Avatar", "widget=many2one_avatar"),
        WidgetOption("many2one_avatar_user", "User avatar", "widget=many2one_avatar_user"),
    ),
    "binary": (
        WidgetOption("image", "Image", "widget=image"),
        WidgetOption("pdf_viewer", "PDF viewer", "widget=pdf_viewer"),
        WidgetOption("signature", "Signature", "widget=signature"),
    ),
    "html": (
        WidgetOption("html", "HTML", "widget=html"),
    ),
}


def widgets_for_ttype(ttype: str) -> tuple[WidgetOption, ...]:
    return WIDGETS_BY_TTYPE.get(ttype, ())


def validate_widget_for_ttype(ttype: str, widget: str | None) -> str | None:
    if not widget:
        return None
    from odoo_client.niche_widget_catalog import NICHE_WIDGETS

    allowed = {w.id for w in widgets_for_ttype(ttype)}
    for nw in NICHE_WIDGETS:
        if ttype in nw.recommended_ttypes:
            allowed.add(nw.id)
    if widget not in allowed:
        raise ValueError(f"Widget {widget!r} is not in the curated set for ttype {ttype!r}")
    return widget
