"""Map labeled sketch regions onto an app plan-like draft.

This is not a second compiler. The output is the same app plan JSON
the existing draft/apply path already consumes.
"""

from __future__ import annotations

import re
from typing import Any

from odoo_client.widget_catalog import validate_widget_for_ttype

from app.wireframe.reader import Sketch, SketchRegion

_HINT_TTYPE: dict[str, str] = {
    "char": "char",
    "text": "text",
    "date": "date",
    "datetime": "datetime",
    "integer": "integer",
    "float": "float",
    "boolean": "boolean",
    "selection": "selection",
    "many2one": "many2one",
    "many2many": "many2many",
    "one2many": "one2many",
    "binary": "binary",
    "html": "html",
    "email": "char",
    "phone": "char",
    "url": "char",
    "image": "binary",
    "photo": "binary",
    "priority": "selection",
    "tags": "many2many",
    "user": "many2one",
    "host": "many2one",
    "partner": "many2one",
}

_HINT_WIDGET: dict[str, str] = {
    "email": "email",
    "phone": "phone",
    "url": "url",
    "image": "image",
    "photo": "image",
    "priority": "priority",
    "tags": "many2many_tags",
    "user": "many2one_avatar_user",
    "host": "many2one_avatar_user",
    "partner": "many2one_avatar",
}

_HINT_RELATION: dict[str, str] = {
    "user": "res.users",
    "host": "res.users",
    "partner": "res.partner",
    "many2one": "res.partner",
    "tags": "res.partner",
    "many2many": "res.partner",
}

_PRIORITY_SELECTION = [["0", "Low"], ["1", "Normal"], ["2", "High"]]


def regions_to_draft(sketch: Sketch) -> dict[str, Any]:
    """Build an app plan-like dict. Does not mark Stage H complete."""
    unclear = sketch.first_unclear()
    if unclear is not None:
        raise ValueError(f"Region {unclear.id} is unclear — clarify before compile")

    technical = _slug(sketch.title, prefix="")
    model = _slug(sketch.title, prefix="x_")
    fields: list[dict[str, Any]] = []
    used: set[str] = set()
    for region in sketch.regions:
        field = _field_from_region(region, used)
        fields.append(field)
        used.add(str(field["name"]))

    form_arch = _form_arch(sketch.title, fields)
    list_arch = _list_arch(sketch.title, fields)
    draft: dict[str, Any] = {
        "technical_name": technical or "custom_app",
        "display_name": sketch.title,
        "depends": ["base", "mail"],
        "models": [
            {
                "model": model,
                "description": sketch.title,
                "mode": "new",
                "fields": fields,
            }
        ],
        "views": [
            {
                "name": f"{model}.form",
                "model": model,
                "type": "form",
                "arch": form_arch,
            },
            {
                "name": f"{model}.list",
                "model": model,
                "type": "list",
                "arch": list_arch,
            },
        ],
        "actions": [
            {
                "name": sketch.title,
                "model": model,
                "view_mode": "list,form",
            }
        ],
        "menus": [
            {
                "name": sketch.title,
                "sequence": 10,
            }
        ],
        "_user_prompt": sketch.prompt,
        "_wireframe": {
            "source": "sketch",
            "media": sketch.source,
            "stage_h": False,
        },
    }
    return draft


def _field_from_region(region: SketchRegion, used: set[str]) -> dict[str, Any]:
    hint = (region.hint or "").strip().lower()
    label = region.label.strip()
    ttype = _HINT_TTYPE.get(hint) or _ttype_from_label(label)
    widget = region.widget or _HINT_WIDGET.get(hint)
    if widget:
        widget = validate_widget_for_ttype(ttype, widget)
    name = _unique_name(_slug(label, prefix="x_"), used)
    field: dict[str, Any] = {
        "name": name,
        "ttype": ttype,
        "string": label,
        "required": name.endswith("_name") or label.lower() in {"name", "subject", "title"},
    }
    if widget:
        field["widget"] = widget
    relation = region.relation or _HINT_RELATION.get(hint)
    if ttype in {"many2one", "many2many", "one2many"}:
        field["relation"] = relation or "res.partner"
    if ttype == "selection" or widget == "priority":
        field["selection"] = list(_PRIORITY_SELECTION)
        field["ttype"] = "selection"
    return field


def _ttype_from_label(label: str) -> str:
    text = label.lower()
    if re.search(r"\b(email|e-mail)\b", text):
        return "char"
    if re.search(r"\b(phone|tel|mobile)\b", text):
        return "char"
    if re.search(r"\b(photo|image|picture)\b", text):
        return "binary"
    if re.search(r"\b(date|when|day)\b", text):
        return "date"
    if re.search(r"\b(host|user|owner|assignee)\b", text):
        return "many2one"
    if re.search(r"\b(priority|urgency)\b", text):
        return "selection"
    return "char"


def _form_arch(title: str, fields: list[dict[str, Any]]) -> str:
    nodes: list[str] = []
    for field in fields:
        name = field["name"]
        widget = field.get("widget")
        if widget:
            nodes.append(f'<field name="{name}" widget="{widget}"/>')
        else:
            nodes.append(f'<field name="{name}"/>')
    inner = "".join(nodes)
    return (
        f'<form string="{_xml(title)}"><sheet>'
        f'<group string="Details">{inner}</group>'
        "</sheet></form>"
    )


def _list_arch(title: str, fields: list[dict[str, Any]]) -> str:
    shown = fields[:4]
    nodes = "".join(f'<field name="{f["name"]}"/>' for f in shown)
    return f'<list string="{_xml(title)}">{nodes}</list>'


def _slug(text: str, *, prefix: str) -> str:
    body = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_") or "field"
    name = f"{prefix}{body}" if prefix else body
    return name[:63]


def _unique_name(name: str, used: set[str]) -> str:
    if name not in used:
        return name
    index = 2
    while f"{name}_{index}" in used:
        index += 1
    return f"{name}_{index}"


def _xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
