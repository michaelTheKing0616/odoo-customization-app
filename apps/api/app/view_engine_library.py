"""Builders stage 2b: component library, widgets, screen settings and checks.

Pure code (no Odoo calls). The router fetches facts from Odoo; this module
decides. AI never reaches here except as an already-validated proposal
(Tidy up sections), and every result is plain ops the compiler checks again.

Version facts come from the real Odoo source of 17-20 (data/widget_catalog),
not from memory: widgets offered are the ones Odoo itself names for people
(displayName) and that support the field's type.
"""

from __future__ import annotations

import difflib
import json
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.view_engine import LAYER_PREFIX, EngineError, _find, _slug

DATA_DIR = Path(__file__).resolve().parent / "data" / "widget_catalog"
FIELD_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")
ICON_RE = re.compile(r"^fa-[a-z0-9-]{1,30}$")
METHOD_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
LABEL_MAX = 80

# ----------------------------------------------------------------------------
# Widgets (per version, from Odoo's own registry)
# ----------------------------------------------------------------------------


@lru_cache(maxsize=8)
def widget_catalog(major: int) -> dict[str, Any]:
    versions = sorted(int(p.stem[1:]) for p in DATA_DIR.glob("v*.json"))
    if not versions:
        return {"version": major, "widgets": {}, "registered": []}
    pick = major if major in versions else max([v for v in versions if v <= major] or [versions[0]])
    return json.loads((DATA_DIR / f"v{pick}.json").read_text())


def widget_registered(name: str, major: int) -> bool:
    return name in set(widget_catalog(major).get("registered") or [])


def widgets_for(field_type: str, major: int) -> list[dict[str, str]]:
    """Widgets a person can pick for this field type on this Odoo version."""
    out = [
        {"name": name, "label": spec["label"]}
        for name, spec in (widget_catalog(major).get("widgets") or {}).items()
        if field_type in spec.get("types", [])
    ]
    return sorted(out, key=lambda w: w["label"].lower())


def check_widget(widget: str, field_type: str, major: int) -> None:
    if not widget:
        return
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", widget):
        raise EngineError("That display style isn't valid.")
    if not widget_registered(widget, major):
        raise EngineError(f"Odoo {major} doesn't have the display style '{widget}'.")
    spec = (widget_catalog(major).get("widgets") or {}).get(widget)
    if spec and field_type and field_type not in spec.get("types", []):
        raise EngineError(f"The display style '{spec['label']}' doesn't work with this kind of field.")


# ----------------------------------------------------------------------------
# New fields (Odoo Studio's set, plain names)
# ----------------------------------------------------------------------------

PRIORITY_CHOICES = [["0", "Normal"], ["1", "Good"], ["2", "Very good"], ["3", "Excellent"]]

NEW_FIELD_TYPES: list[dict[str, Any]] = [
    {"key": "text", "label": "Text", "ttype": "char"},
    {"key": "multiline", "label": "Multiline text", "ttype": "text"},
    {"key": "number", "label": "Whole number", "ttype": "integer"},
    {"key": "decimal", "label": "Decimal number", "ttype": "float"},
    {"key": "money", "label": "Amount of money", "ttype": "monetary", "needs": "currency"},
    {"key": "date", "label": "Date", "ttype": "date"},
    {"key": "datetime", "label": "Date and time", "ttype": "datetime"},
    {"key": "checkbox", "label": "Checkbox", "ttype": "boolean"},
    {"key": "choice", "label": "Choice list", "ttype": "selection", "needs": "choices"},
    {"key": "tags", "label": "Tags", "ttype": "many2many", "needs": "relation", "widget": "many2many_tags"},
    {"key": "priority", "label": "Priority stars", "ttype": "selection", "widget": "priority"},
    {"key": "file", "label": "File", "ttype": "binary"},
    {"key": "image", "label": "Image", "ttype": "binary", "widget": "image"},
    {"key": "signature", "label": "Signature", "ttype": "binary", "widget": "signature"},
    {"key": "html", "label": "Formatted text", "ttype": "html"},
    {"key": "link", "label": "Link to another record", "ttype": "many2one", "needs": "relation"},
    {"key": "lines", "label": "List of related records", "ttype": "one2many", "needs": "relation"},
    {"key": "related", "label": "Related field", "needs": "related"},
]
TYPE_BY_KEY = {t["key"]: t for t in NEW_FIELD_TYPES}


def field_types_for(major: int) -> list[dict[str, Any]]:
    """Types offered on this version (a type with a widget needs that widget)."""
    return [t for t in NEW_FIELD_TYPES if not t.get("widget") or widget_registered(t["widget"], major)]


def _norm_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def similar_fields(label: str, ttype: str | None, fields: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    """Stock first: fields already on the model that look like the one being made.
    String similarity of labels and names (not a word list), same type family first."""
    want = _norm_label(label)
    if not want:
        return []
    family = {"char": "text", "text": "text", "html": "text", "integer": "num", "float": "num", "monetary": "num"}
    scored: list[tuple[float, str]] = []
    for name, meta in fields.items():
        lbl = _norm_label(str(meta.get("string") or name))
        r = max(difflib.SequenceMatcher(None, want, lbl).ratio(),
                difflib.SequenceMatcher(None, want.replace(" ", "_"), name.lower()).ratio())
        if ttype and (meta.get("type") == ttype or family.get(meta.get("type") or "") == family.get(ttype, "-")):
            r += 0.05
        if r >= 0.82:
            scored.append((r, name))
    scored.sort(reverse=True)
    return [{"name": n, "label": str(fields[n].get("string") or n), "type": fields[n].get("type")} for _, n in scored[:limit]]


def new_field_name(label: str, fields: dict[str, Any]) -> str:
    base = "x_" + (_slug(label)[:40] or "field")
    name, n = base, 2
    while name in fields:
        name = f"{base}_{n}"
        n += 1
    return name


def plan_new_field(
    spec: dict[str, Any], fields: dict[str, Any], model_id: int, major: int,
    *, relation_models: set[str] | None = None, related_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validated values for ``ir.model.fields.create`` plus the widget to show it with.

    Raises EngineError with a plain reason. ``related_meta`` is the fields_get
    entry of the last field in a related path (looked up by the router)."""
    key = str(spec.get("type") or "")
    kind = TYPE_BY_KEY.get(key)
    if not kind:
        raise EngineError("Pick what kind of field to make.")
    if kind not in field_types_for(major):
        raise EngineError(f"Odoo {major} can't show a {kind['label'].lower()} field.")
    label = str(spec.get("label") or "").strip()
    if not label or len(label) > LABEL_MAX:
        raise EngineError("Give the field a name of 1 to 80 characters.")
    name = new_field_name(label, fields)
    vals: dict[str, Any] = {"name": name, "field_description": label, "model_id": int(model_id), "state": "manual"}
    widget = kind.get("widget")
    if key == "related":
        path = str(spec.get("related") or "")
        if not re.fullmatch(r"[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*){1,3}", path):
            raise EngineError("Pick a field of a linked record, like Customer > Country.")
        head = path.split(".")[0]
        if (fields.get(head) or {}).get("type") != "many2one":
            raise EngineError("Related fields start from a link to another record.")
        if not related_meta:
            raise EngineError("That linked field wasn't found in your database.")
        rtype = str(related_meta.get("type") or "")
        if rtype in {"one2many", "properties", "properties_definition", "json"}:
            raise EngineError("That kind of linked field can't be shown here.")
        vals.update({"ttype": rtype, "related": path, "readonly": True, "store": False})
        if rtype in {"many2one", "many2many"}:
            vals["relation"] = related_meta.get("relation")
        if rtype == "selection":
            vals["selection_ids"] = [[0, 0, {"value": str(k), "name": str(v), "sequence": i}]
                                     for i, (k, v) in enumerate(related_meta.get("selection") or [])]
        if rtype == "monetary":
            cur = next((f for f, m in fields.items() if m.get("type") == "many2one" and m.get("relation") == "res.currency"), None)
            if not cur:
                raise EngineError("Money fields need a currency on this record type.")
            vals["currency_field"] = cur
        return {"values": vals, "widget": None, "name": name}
    vals["ttype"] = kind["ttype"]
    if key == "money":
        cur = next((f for f, m in fields.items() if m.get("type") == "many2one" and m.get("relation") == "res.currency"), None)
        if not cur:
            raise EngineError("Money fields need a currency on this record type. Use a decimal number instead.")
        vals["currency_field"] = cur
    if key in {"choice", "priority"}:
        raw = PRIORITY_CHOICES if key == "priority" else spec.get("choices")
        if not isinstance(raw, list) or not 1 <= len(raw) <= 40:
            raise EngineError("Add 1 to 40 choices.")
        seen: set[str] = set()
        rows = []
        for i, c in enumerate(raw):
            lbl = str(c[1] if isinstance(c, list) and len(c) > 1 else c).strip()
            val = str(c[0] if isinstance(c, list) and len(c) > 1 else _slug(lbl)).strip()
            if not lbl or len(lbl) > 60 or val in seen:
                raise EngineError("Each choice needs a different name of 1 to 60 characters.")
            seen.add(val)
            rows.append([0, 0, {"value": val, "name": lbl, "sequence": i}])
        vals["selection_ids"] = rows
    if kind.get("needs") == "relation":
        rel = str(spec.get("relation") or "")
        if not re.fullmatch(r"[a-z_][a-z0-9_.]{1,127}", rel) or (relation_models is not None and rel not in relation_models):
            raise EngineError("Pick which kind of record it links to.")
        vals["relation"] = rel
        if key == "lines":
            inverse = str(spec.get("relation_field") or "")
            if not FIELD_RE.match(inverse):
                raise EngineError("Pick the field on the linked records that points back here.")
            vals["relation_field"] = inverse
    if widget and not widget_registered(widget, major):
        widget = None
    return {"values": vals, "widget": widget, "name": name}


def related_choices(fields: dict[str, Any], rel_fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """'Customer > Country' style paths, one level deep, for drag-to-add."""
    out: list[dict[str, Any]] = []
    for fname, meta in sorted(fields.items(), key=lambda kv: str(kv[1].get("string") or kv[0])):
        if meta.get("type") != "many2one" or meta.get("relation") not in rel_fields:
            continue
        sub = rel_fields[meta["relation"]]
        items = [
            {"path": f"{fname}.{s}", "label": f"{meta.get('string') or fname} > {sm.get('string') or s}", "type": sm.get("type")}
            for s, sm in sorted(sub.items(), key=lambda kv: str(kv[1].get("string") or kv[0]))
            if sm.get("type") not in {"one2many", "binary", "properties", "properties_definition", "json"}
            and not s.startswith("__") and s not in {"id", "display_name", "create_uid", "write_uid", "create_date", "write_date"}
        ]
        if items:
            out.append({"field": fname, "label": str(meta.get("string") or fname), "relation": meta["relation"], "items": items[:80]})
    return out[:30]


# ----------------------------------------------------------------------------
# Layout and button elements (component library)
# ----------------------------------------------------------------------------

LAYOUT_KINDS = ("separator", "group", "notebook", "page", "title", "header", "ribbon", "chatter", "button_box")
BUTTON_KINDS = ("smart_button", "action_button", "link_button", "statusbar")
RIBBON_COLORS = {"red": "text-bg-danger", "green": "text-bg-success", "blue": "text-bg-info", "amber": "text-bg-warning", "grey": "text-bg-secondary"}
BUTTON_STYLES = {"primary": "btn-primary", "secondary": "btn-secondary", "link": "btn-link"}

# Where each library element may be placed (parent tags), Odoo nesting.
ELEMENT_PARENTS: dict[str, frozenset[str]] = {
    "separator": frozenset({"group", "page", "sheet", "div"}),
    "group": frozenset({"sheet", "page", "group", "div", "form"}),
    "notebook": frozenset({"sheet", "page", "div", "form"}),
    "page": frozenset({"notebook"}),
    "title": frozenset({"sheet", "div", "form"}),
    "header": frozenset({"form"}),
    "ribbon": frozenset({"sheet", "form"}),
    "chatter": frozenset({"form"}),
    "button_box": frozenset({"sheet"}),
    "smart_button": frozenset({"div"}),
    "action_button": frozenset({"header", "div", "group", "list", "tree", "footer"}),
    "link_button": frozenset({"header", "div", "group", "sheet", "page"}),
    "statusbar": frozenset({"header"}),
}


def library(major: int, root_tag: str, fields: dict[str, Any]) -> dict[str, Any]:
    """What the left '+' panel offers on this screen and version."""
    has_mail = "message_ids" in fields
    layout = [
        {"kind": "separator", "label": "Separator"},
        {"kind": "group", "label": "Columns", "props": {"columns": 2}},
        {"kind": "group", "label": "Group"},
        {"kind": "notebook", "label": "Tabs"},
        {"kind": "page", "label": "Tab"},
        {"kind": "title", "label": "Title"},
        {"kind": "header", "label": "Header bar"},
        {"kind": "ribbon", "label": "Ribbon"},
        {"kind": "button_box", "label": "Button box"},
    ]
    if has_mail:
        layout.append({"kind": "chatter", "label": "Chatter (messages and activities)"})
    buttons = [
        {"kind": "smart_button", "label": "Smart button"},
        {"kind": "action_button", "label": "Action button"},
        {"kind": "link_button", "label": "Link"},
        {"kind": "statusbar", "label": "Status bar"},
    ]
    if root_tag != "form":
        layout, buttons = [], [b for b in buttons if b["kind"] == "action_button" and root_tag in {"list", "tree"}]
    return {"field_types": field_types_for(major), "layout": layout, "buttons": buttons}


def _label(props: dict[str, Any], default: str) -> str:
    text = str(props.get("label") or default).strip()
    if not text or len(text) > LABEL_MAX:
        raise EngineError("Labels need 1 to 80 characters.")
    return text


def _new_name(root: ET.Element, kind: str, label: str, seq: int) -> str:
    n = seq
    while True:
        name = f"{LAYER_PREFIX}_{kind}_{_slug(label)}_{n}"
        if not _find(root, f"//*[@name='{name}']") and not any(e.get("name") == name for e in root.iter()):
            return name
        n += 1


def build_element(kind: str, props: dict[str, Any], *, root: ET.Element, fields: dict[str, Any], major: int,
                  seq: int, actions: set[int] | None = None, methods: set[str] | None = None) -> ET.Element:
    """One library element as Odoo arch, validated. Names carry the Ingenium prefix."""
    props = props if isinstance(props, dict) else {}
    if kind == "separator":
        el = ET.Element("separator")
        el.set("string", _label(props, "Section"))
        el.set("name", _new_name(root, kind, el.get("string") or "", seq))
        return el
    if kind == "group":
        label = str(props.get("label") or "").strip()[:LABEL_MAX]
        el = ET.Element("group")
        el.set("name", _new_name(root, kind, label or "columns", seq))
        if label:
            el.set("string", label)
        if int(props.get("columns") or 1) == 2:
            for side in ("left", "right"):
                sub = ET.SubElement(el, "group")
                sub.set("name", f"{el.get('name')}_{side}")
        return el
    if kind == "notebook":
        el = ET.Element("notebook")
        el.set("name", _new_name(root, kind, "tabs", seq))
        page = ET.SubElement(el, "page")
        page.set("string", _label(props, "New tab"))
        page.set("name", f"{el.get('name')}_page")
        return el
    if kind == "page":
        el = ET.Element("page")
        el.set("string", _label(props, "New tab"))
        el.set("name", _new_name(root, kind, el.get("string") or "", seq))
        return el
    if kind == "title":
        fname = str(props.get("field") or "")
        if fname not in fields or fields[fname].get("type") not in {"char", "text", "many2one", "integer"}:
            raise EngineError("Pick a text field to use as the title.")
        el = ET.Element("div")
        el.set("class", "oe_title")
        el.set("name", _new_name(root, kind, fname, seq))
        h1 = ET.SubElement(el, "h1")
        f = ET.SubElement(h1, "field")
        f.set("name", fname)
        if props.get("placeholder"):
            f.set("placeholder", str(props["placeholder"])[:LABEL_MAX])
        return el
    if kind == "header":
        if root.find("header") is not None:
            raise EngineError("This screen already has a header bar.")
        return ET.Element("header")
    if kind == "ribbon":
        if not widget_registered("web_ribbon", major) and major < 17:
            raise EngineError("This Odoo version has no ribbons.")
        el = ET.Element("widget")
        el.set("name", "web_ribbon")
        el.set("title", _label(props, "Archived"))
        el.set("bg_color", RIBBON_COLORS.get(str(props.get("color") or "red"), "text-bg-danger"))
        if props.get("invisible"):
            el.set("invisible", str(props["invisible"]))
        return el
    if kind == "chatter":
        if "message_ids" not in fields:
            raise EngineError("This record type has no messages, so a chatter can't be added.")
        if root.find("chatter") is not None or any("oe_chatter" in (e.get("class") or "") for e in root.iter("div")):
            raise EngineError("This screen already has a chatter.")
        if major >= 18:
            return ET.Element("chatter")
        el = ET.Element("div")
        el.set("class", "oe_chatter")
        for fname in ("message_follower_ids", "activity_ids", "message_ids"):
            if fname in fields:
                ET.SubElement(el, "field").set("name", fname)
        return el
    if kind == "button_box":
        if _find(root, "//div[@name='button_box']"):
            raise EngineError("This screen already has a button box.")
        el = ET.Element("div")
        el.set("class", "oe_button_box")
        el.set("name", "button_box")
        return el
    if kind == "smart_button":
        label = _label(props, "Related")
        icon = str(props.get("icon") or "fa-list")
        if not ICON_RE.match(icon):
            raise EngineError("That icon isn't available.")
        action_id = props.get("action_id")
        if not isinstance(action_id, int) or isinstance(action_id, bool) or (actions is not None and action_id not in actions):
            raise EngineError("Pick which list the button opens.")
        el = ET.Element("button")
        el.set("name", str(action_id))
        el.set("type", "action")
        el.set("class", "oe_stat_button")
        el.set("icon", icon)
        count = str(props.get("count_field") or "")
        if count:
            if count not in fields or fields[count].get("type") not in {"integer", "float", "monetary"}:
                raise EngineError("The number on a smart button must come from a number field.")
            f = ET.SubElement(el, "field")
            f.set("name", count)
            f.set("widget", "statinfo")
            f.set("string", label)
        else:
            div = ET.SubElement(el, "div")
            div.set("class", "o_stat_info")
            span = ET.SubElement(div, "span")
            span.set("class", "o_stat_text")
            span.text = label
        return el
    if kind in {"action_button", "link_button"}:
        label = _label(props, "Run")
        el = ET.Element("button")
        el.set("string", label)
        method = str(props.get("method") or "")
        action_id = props.get("action_id")
        if method:
            if not METHOD_RE.match(method) or (methods is not None and method not in methods):
                raise EngineError("Pick one of the actions this record type already has.")
            el.set("name", method)
            el.set("type", "object")
        elif isinstance(action_id, int) and not isinstance(action_id, bool) and (actions is None or action_id in actions):
            el.set("name", str(action_id))
            el.set("type", "action")
        else:
            raise EngineError("Pick what the button does.")
        style = "link" if kind == "link_button" else str(props.get("style") or "secondary")
        el.set("class", BUTTON_STYLES.get(style, "btn-secondary"))
        confirm = str(props.get("confirm") or "").strip()
        if confirm:
            el.set("confirm", confirm[:200])
        return el
    if kind == "statusbar":
        fname = str(props.get("field") or "")
        meta = fields.get(fname) or {}
        if meta.get("type") not in {"selection", "many2one"}:
            raise EngineError("A status bar shows a choice list or a stage field.")
        el = ET.Element("field")
        el.set("name", fname)
        el.set("widget", "statusbar")
        if props.get("clickable", True):
            el.set("options", "{'clickable': '1'}")
        return el
    raise EngineError(f"'{kind}' isn't in the component library.")


# ----------------------------------------------------------------------------
# Screen settings (list, kanban, calendar roots) and column settings
# ----------------------------------------------------------------------------

DECORATIONS = ("danger", "warning", "success", "info", "muted", "primary", "bf", "it")
DECORATION_WORDS = {"danger": "red", "warning": "amber", "success": "green", "info": "blue", "muted": "grey",
                    "primary": "accent", "bf": "bold", "it": "italic"}
GROUPABLE = frozenset({"char", "selection", "many2one", "boolean", "date", "datetime", "integer", "many2many"})

ROOT_ATTRS: dict[str, tuple[str, ...]] = {
    "list": ("editable", "default_group_by", "default_order", "create", "delete", "multi_edit", "limit", "open_form_view"),
    "tree": ("editable", "default_group_by", "default_order", "create", "delete", "multi_edit", "limit"),
    "kanban": ("default_group_by", "default_order", "quick_create", "create", "group_create", "highlight_color"),
    "calendar": ("date_start", "date_stop", "date_delay", "color", "mode", "quick_create", "event_open_popup", "all_day"),
    "form": ("create", "edit", "delete", "duplicate"),
}
LIST_FIELD_ATTRS = ("width", "optional", "sum", "avg")


def check_root_attr(tag: str, attr: str, value: str, fields: dict[str, Any], major: int) -> None:
    allowed = ROOT_ATTRS.get(tag, ())
    if attr not in allowed:
        raise EngineError(f"'{attr}' can't be set on this kind of screen.")
    if attr == "highlight_color" and major < 18:
        raise EngineError("Card colours from a field need Odoo 18 or newer.")
    if value == "":
        return
    if attr in {"create", "delete", "multi_edit", "edit", "duplicate", "quick_create", "group_create", "event_open_popup", "open_form_view"}:
        if value not in {"0", "1", "true", "false", "True", "False"}:
            raise EngineError("Choose yes or no for this setting.")
        return
    if attr == "editable":
        if value not in {"top", "bottom"}:
            raise EngineError("Rows are edited at the top or the bottom of the list.")
        return
    if attr == "limit":
        if not value.isdigit() or not 1 <= int(value) <= 500:
            raise EngineError("Show between 1 and 500 rows per page.")
        return
    if attr == "mode":
        if value not in {"day", "week", "month", "year"}:
            raise EngineError("The calendar opens on day, week, month or year.")
        return
    if attr == "default_order":
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if not parts or len(parts) > 3:
            raise EngineError("Sort by 1 to 3 fields.")
        for p in parts:
            m = re.fullmatch(r"([a-z_][a-z0-9_]*)(?:\s+(asc|desc))?", p)
            if not m or m.group(1) not in fields or fields[m.group(1)].get("store") is False:
                raise EngineError("Sorting needs fields that are saved in the database.")
        return
    meta = fields.get(value) or {}
    if not FIELD_RE.match(value) or not meta:
        raise EngineError(f"There is no field called '{value}' on this record type.")
    if attr == "default_group_by":
        if meta.get("type") not in GROUPABLE or meta.get("store") is False:
            raise EngineError(f"Rows can't be grouped by '{meta.get('string') or value}'.")
    elif attr in {"date_start", "date_stop"}:
        if meta.get("type") not in {"date", "datetime"}:
            raise EngineError("The calendar needs a date field.")
    elif attr == "date_delay":
        if meta.get("type") not in {"float", "integer"}:
            raise EngineError("Duration needs a number field.")
    elif attr == "all_day":
        if meta.get("type") != "boolean":
            raise EngineError("'All day' needs a checkbox field.")
    elif attr == "highlight_color":
        if meta.get("type") != "integer":
            raise EngineError("Card colours come from a colour number field.")
    elif attr == "color":
        if meta.get("type") not in {"many2one", "integer", "selection"}:
            raise EngineError("Colours come from a link, choice or colour number field.")


def check_list_field_attr(attr: str, value: str) -> None:
    if value == "":
        return
    if attr == "width":
        if not re.fullmatch(r"\d{2,3}px", value) or not 30 <= int(value[:-2]) <= 800:
            raise EngineError("Column width is 30 to 800 pixels.")
    elif attr == "optional":
        if value not in {"show", "hide"}:
            raise EngineError("Optional columns start shown or hidden.")
    elif attr in {"sum", "avg"}:
        if len(value) > 40 or re.search(r"[<>{}]", value):
            raise EngineError("Totals need a short label.")


# ----------------------------------------------------------------------------
# Conditions in other places: search filters (domains) and kanban cards (QWeb)
# ----------------------------------------------------------------------------

def _dom_value(v: Any) -> str:
    return repr(v)


def compile_domain(cond: dict[str, Any]) -> str:
    """Validated condition tree -> Odoo domain text for a search filter."""
    leaves: list[str] = []
    for r in cond["rules"]:
        f, op, v = r["field"], r["op"], r.get("value")
        if op == "is_true":
            leaves.append(f"('{f}', '=', True)")
        elif op == "is_false":
            leaves.append(f"('{f}', '=', False)")
        elif op == "set":
            leaves.append(f"('{f}', '!=', False)")
        elif op == "not_set":
            leaves.append(f"('{f}', '=', False)")
        elif op == "is":
            leaves.append(f"('{f}', '=', {_dom_value(v)})")
        elif op == "is_not":
            leaves.append(f"('{f}', '!=', {_dom_value(v)})")
        elif op == "in":
            leaves.append(f"('{f}', 'in', {_dom_value(list(v))})")
        elif op == "not_in":
            leaves.append(f"('{f}', 'not in', {_dom_value(list(v))})")
        elif op == "contains":
            leaves.append(f"('{f}', 'ilike', {_dom_value(v)})")
        else:
            sym = {"eq": "=", "ne": "!=", "gt": ">", "ge": ">=", "lt": "<", "le": "<="}[op]
            leaves.append(f"('{f}', '{sym}', {_dom_value(v)})")
    if cond.get("match") == "any" and len(leaves) > 1:
        leaves = ["'|'"] * (len(leaves) - 1) + leaves
    return "[" + ", ".join(leaves) + "]"


def compile_qweb_condition(cond: dict[str, Any], fields: dict[str, Any]) -> str:
    """Validated condition tree -> kanban card QWeb expression (record.x.raw_value)."""
    parts: list[str] = []
    for r in cond["rules"]:
        f, op, v = r["field"], r["op"], r.get("value")
        t = (fields.get(f) or {}).get("type")
        if t in {"many2one", "many2many", "one2many"} and op not in {"set", "not_set"}:
            raise EngineError("Card colours can't compare linked records yet. Use a choice, number or checkbox field.")
        ref = f"record.{f}.raw_value"
        if op in {"is_true", "set"}:
            parts.append(ref if t not in {"many2many", "one2many"} else f"{ref}.length")
        elif op in {"is_false", "not_set"}:
            parts.append(f"!{ref}" if t not in {"many2many", "one2many"} else f"!{ref}.length")
        elif op == "is":
            parts.append(f"{ref} === {json.dumps(v)}")
        elif op == "is_not":
            parts.append(f"{ref} !== {json.dumps(v)}")
        elif op == "in":
            parts.append(f"{json.dumps(list(v))}.includes({ref})")
        elif op == "not_in":
            parts.append(f"!{json.dumps(list(v))}.includes({ref})")
        elif op == "contains":
            parts.append(f"({ref} || '').includes({json.dumps(v)})")
        else:
            sym = {"eq": "===", "ne": "!==", "gt": ">", "ge": ">=", "lt": "<", "le": "<="}[op]
            parts.append(f"{ref} {sym} {json.dumps(v)}")
    joiner = " || " if cond.get("match") == "any" else " &amp;&amp; "
    expr = joiner.join(f"({p})" for p in parts) if len(parts) > 1 else parts[0]
    return expr.replace("&amp;&amp;", "&&")


def kanban_card_anchor(root: ET.Element) -> tuple[str, str]:
    """(xpath, plain place) of the card body inside a kanban template."""
    for name in ("card", "kanban-card"):
        hits = _find(root, f"//t[@t-name='{name}']")
        if len(hits) == 1:
            return f"//t[@t-name='{name}']", "card"
    box = _find(root, "//t[@t-name='kanban-box']")
    if len(box) == 1:
        divs = [c for c in box[0] if isinstance(c.tag, str) and c.tag == "div"]
        if len(divs) == 1 and len(_find(root, "//t[@t-name='kanban-box']/div")) == 1:
            return "//t[@t-name='kanban-box']/div", "card"
    raise EngineError("This card layout can't be changed safely.")


KANBAN_ADD_KINDS = ("field", "tags", "progress", "cover", "badge", "colour")


def build_kanban_element(kind: str, props: dict[str, Any], fields: dict[str, Any], major: int) -> ET.Element:
    fname = str(props.get("field") or "")
    meta = fields.get(fname) or {}
    if kind != "colour" and (not FIELD_RE.match(fname) or not meta):
        raise EngineError(f"There is no field called '{fname}' on this record type.")
    if kind == "field":
        el = ET.Element("field")
        el.set("name", fname)
        return el
    if kind == "tags":
        if meta.get("type") != "many2many":
            raise EngineError("Tags need a tags field.")
        el = ET.Element("field")
        el.set("name", fname)
        el.set("widget", "many2many_tags")
        return el
    if kind == "progress":
        if meta.get("type") not in {"float", "integer"}:
            raise EngineError("A progress bar needs a number field.")
        el = ET.Element("field")
        el.set("name", fname)
        el.set("widget", "progressbar")
        return el
    if kind == "badge":
        if meta.get("type") not in {"selection", "many2one", "char"}:
            raise EngineError("Badges show a choice, a link or a short text.")
        el = ET.Element("field")
        el.set("name", fname)
        el.set("widget", "badge")
        return el
    if kind == "cover":
        if meta.get("type") not in {"binary", "many2one"}:
            raise EngineError("A cover needs an image field.")
        el = ET.Element("field")
        el.set("name", fname)
        el.set("widget", "image")
        el.set("class", "o_kanban_image_fill" if major >= 18 else "o_kanban_image")
        el.set("options", "{'size': [96, 96]}")
        if major >= 18:
            aside = ET.Element("aside")
            aside.set("class", "o_kanban_aside_full")
            aside.append(el)
            return aside
        return el
    if kind == "colour":
        expr = str(props.get("expression") or "")
        style = str(props.get("style") or "danger")
        if style not in DECORATIONS[:6]:
            raise EngineError("Pick a colour.")
        el = ET.Element("div")
        el.set("t-if", expr)
        el.set("class", f"o_ingenium_card_flag bg-{style}")
        el.set("style", "height: 4px; margin: -8px -8px 6px -8px;")
        return el
    raise EngineError(f"'{kind}' can't be added to a card.")


# ----------------------------------------------------------------------------
# Usage suggestions (counts only), layout checks, health score, tidy, speed
# ----------------------------------------------------------------------------

def _walk(node: dict[str, Any], parent: dict[str, Any] | None = None, hidden: bool = False):
    attrs = node.get("attrs") or {}
    me_hidden = hidden or str(attrs.get("invisible") or "").strip() in {"1", "True", "true"}
    yield node, parent, me_hidden
    for c in node.get("children") or []:
        yield from _walk(c, node, me_hidden)


def screen_fields(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """Top-level field nodes (not Odoo helpers) with whether they're always hidden."""
    out = []
    for n, parent, hidden in _walk(tree):
        if n.get("tag") == "field" and str(n.get("id", "")).startswith("field:") and not n.get("helper"):
            out.append({"node": n, "parent": parent, "hidden": hidden})
    return out


def countable(meta: dict[str, Any]) -> bool:
    return meta.get("store") is not False and meta.get("type") not in {"binary", "properties", "properties_definition", "json"}


def fill_domain(name: str, meta: dict[str, Any]) -> list[Any]:
    t = meta.get("type")
    if t == "boolean":
        return [(name, "=", True)]
    if t in {"integer", "float", "monetary"}:
        return [(name, "!=", 0)]
    return [(name, "!=", False)]


def pct(n: int, total: int) -> int:
    return round(100 * n / total) if total else 0


def usage_suggestions(tree: dict[str, Any], fields: dict[str, Any], counts: dict[str, int], total: int) -> list[dict[str, Any]]:
    """'Rarely filled', 'Most used first', 'Required but hidden'. Counts only, never record contents."""
    out: list[dict[str, Any]] = []
    sf = screen_fields(tree)
    for item in sf:
        n = item["node"]
        name = n.get("name") or ""
        meta = fields.get(name) or {}
        label = n.get("label") or name
        if item["hidden"] and meta.get("required") is True and not meta.get("readonly"):
            out.append({"kind": "required_hidden", "node": n["id"], "text": f"Required but hidden: {label}",
                        "detail": "People can't fill it in, so saving may fail.", "fix_label": "Show it",
                        "ops": [{"op": "set_attr", "node": n["id"], "attr": "invisible", "value": "False"}] if n.get("anchor") else []})
    if total < 20:
        if total:
            out.append({"kind": "note", "text": f"Only {total} records so far, so fill rates aren't shown yet.", "ops": []})
        return out
    for item in sf:
        n = item["node"]
        name = n.get("name") or ""
        if item["hidden"] or name not in counts:
            continue
        meta = fields.get(name) or {}
        rate = pct(counts[name], total)
        if rate < 5 and not meta.get("required") and meta.get("type") != "boolean" and n.get("anchor"):
            out.append({"kind": "rarely_filled", "node": n["id"], "rate": rate, "count": counts[name], "total": total,
                        "text": f"Rarely filled: {n.get('label') or name} ({rate}% of {total:,})",
                        "fix_label": "Hide it", "ops": [{"op": "hide", "node": n["id"]}]})
    # Most used first: inside one section, a much busier field sits below a quiet one.
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for item in sf:
        if item["parent"] is not None and not item["hidden"]:
            by_parent.setdefault(item["parent"]["id"], []).append(item)
    for siblings in by_parent.values():
        rated = [(s, pct(counts.get(s["node"].get("name") or "", 0), total)) for s in siblings if (s["node"].get("name") or "") in counts]
        for i, (s, r) in enumerate(rated):
            quiet_above = next(((q, qr) for q, qr in rated[:i] if qr + 50 <= r and q["node"].get("anchor")), None)
            if quiet_above and s["node"].get("anchor"):
                q, qr = quiet_above
                out.append({"kind": "most_used_first", "node": s["node"]["id"],
                            "text": f"Most used fields first: {s['node'].get('label')} ({r}%) sits below {q['node'].get('label')} ({qr}%)",
                            "fix_label": "Move it up",
                            "ops": [{"op": "move", "node": s["node"]["id"], "target": q["node"]["id"], "position": "before"}]})
                break
    return out


def _contrast(hex1: str, hex2: str = "#ffffff") -> float:
    def lum(h: str) -> float:
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    a, b = lum(hex1), lum(hex2)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _darken_to(hex1: str, target: float = 4.5) -> str:
    h = hex1.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    for _ in range(40):
        cur = "#" + "".join(f"{c:02x}" for c in rgb)
        if _contrast(cur) >= target:
            return cur
        rgb = [max(0, int(c * 0.9)) for c in rgb]
    return "#000000"


STYLE_COLOR_RE = re.compile(r"(?<![-\w])color\s*:\s*(#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?)\b")


def layout_checks(tree: dict[str, Any], fields: dict[str, Any], root_tag: str) -> list[dict[str, Any]]:
    """Rules in code, each with a one-click fix (ops) where a safe fix exists."""
    issues: list[dict[str, Any]] = []
    if root_tag != "form":
        return issues
    nodes = list(_walk(tree))

    def visible_fields(node: dict[str, Any]) -> list[dict[str, Any]]:
        return [n for n, _p, h in _walk(node) if n.get("tag") == "field" and not h and not n.get("helper") and n is not node]

    for n, parent, hidden in nodes:
        if hidden:
            continue
        tag = n.get("tag")
        if tag in {"page", "group"} and not (tag == "group" and parent is not None and parent.get("tag") == "group"):
            vf = visible_fields(n)
            if len(vf) > 12:
                kids = [c for c in n.get("children") or [] if c.get("anchor") and not c.get("helper")]
                half: list[str] = []
                running, goal = 0, len(vf) / 2
                for c in kids:
                    cnt = 1 if c.get("tag") == "field" else len(visible_fields(c))
                    if running >= goal:
                        half.append(c["id"])
                    running += cnt
                ops: list[dict[str, Any]] = []
                if tag == "page" and half:
                    ops = [{"op": "wrap", "nodes": half, "kind": "page", "label": f"{n.get('label') or 'More'} (more)"}]
                elif tag == "group" and half and len(half) < len(kids):
                    ops = [{"op": "wrap", "nodes": half, "kind": "group", "label": ""}]
                issues.append({"kind": "crowded", "node": n["id"], "severity": "warning", "count": len(vf),
                               "text": f"Too many fields in one {'tab' if tag == 'page' else 'section'}: {n.get('label') or 'Untitled'} has {len(vf)}",
                               "fix_label": "Split it in two" if ops else None, "ops": ops})
        if tag == "group" and len([c for c in n.get("children") or [] if c.get("tag") == "group"]) == 2 and \
                len([c for c in n.get("children") or [] if c.get("tag") != "group"]) == 0:
            left, right = [c for c in n["children"] if c.get("tag") == "group"]
            lf, rf = visible_fields(left), visible_fields(right)
            if abs(len(lf) - len(rf)) >= 4 and min(len(lf), len(rf)) >= 0:
                long_col, short_col = (left, right) if len(lf) > len(rf) else (right, left)
                movers = [f for f in (visible_fields(long_col)) if f.get("anchor") and f in long_col.get("children", [])]
                k = (abs(len(lf) - len(rf))) // 2
                ops = []
                if short_col.get("anchor"):
                    for f in movers[-k:] if long_col is left else movers[:k]:
                        ops.append({"op": "move", "node": f["id"], "target": short_col["id"], "position": "inside"})
                issues.append({"kind": "unbalanced", "node": n["id"], "severity": "info",
                               "text": f"Columns are unbalanced ({len(lf)} and {len(rf)} fields)",
                               "fix_label": "Balance columns" if ops else None, "ops": ops})
        if tag == "field" and not n.get("helper"):
            attrs = n.get("attrs") or {}
            meta = fields.get(n.get("name") or "") or {}
            if attrs.get("nolabel") in {"1", "True", "true"} and meta.get("type") in {"char", "text", "html"} \
                    and not attrs.get("placeholder") and n.get("anchor") and not any(
                        s.get("tag") == "label" for s in (parent or {}).get("children") or []):
                issues.append({"kind": "unlabeled", "node": n["id"], "severity": "warning",
                               "text": f"No label or hint on {n.get('label')}",
                               "detail": "People using screen readers can't tell what goes here.",
                               "fix_label": "Add a hint", "ops": [{"op": "set_attr", "node": n["id"], "attr": "placeholder", "value": str(n.get("label") or "")[:80]}]})
        if tag == "button" and not (n.get("attrs") or {}).get("string") and not n.get("label"):
            issues.append({"kind": "button_label", "node": n["id"], "severity": "warning",
                           "text": "A button has no text", "fix_label": None, "ops": []})
        style = (n.get("attrs") or {}).get("style") or ""
        for m in STYLE_COLOR_RE.finditer(style):
            ratio = _contrast(m.group(1))
            if ratio < 4.5:
                fixed = style.replace(m.group(1), _darken_to(m.group(1)))
                issues.append({"kind": "contrast", "node": n["id"], "severity": "warning",
                               "text": f"Custom colour is hard to read on {n.get('label') or 'an item'} ({ratio:.1f}:1, needs 4.5:1)",
                               "fix_label": "Darken the colour",
                               "ops": [{"op": "set_attr", "node": n["id"], "attr": "style", "value": fixed}] if n.get("anchor") else []})
    # Reading order: required fields on a later tab.
    for n, _parent, hidden in nodes:
        if n.get("tag") != "notebook" or hidden:
            continue
        pages = [c for c in n.get("children") or [] if c.get("tag") == "page"]
        main_target = next((c for c, _p, h in nodes if c.get("tag") == "group" and not h and c.get("anchor")
                            and c not in [x for p in pages for x, _q, _h in _walk(p)]), None)
        for p in pages[1:]:
            for f in visible_fields(p):
                meta = fields.get(f.get("name") or "") or {}
                if meta.get("required") is True and not meta.get("readonly") and f.get("anchor"):
                    issues.append({"kind": "reading_order", "node": f["id"], "severity": "info",
                                   "text": f"Required field {f.get('label')} is on a later tab ({p.get('label')})",
                                   "detail": "People fill screens top to bottom and miss it.",
                                   "fix_label": "Move it to the top" if main_target else None,
                                   "ops": [{"op": "move", "node": f["id"], "target": main_target["id"], "position": "inside"}] if main_target else []})
    return issues


def health_score(issues: list[dict[str, Any]], suggestions: list[dict[str, Any]], visible_count: int,
                 empty_count: int | None) -> dict[str, Any]:
    """0-100 with the parts that make it up, so the number is explainable."""
    crowd = [i for i in issues if i["kind"] in {"crowded", "unbalanced"}]
    access = [i for i in issues if i["kind"] in {"unlabeled", "button_label", "contrast"}]
    hidden_req = [s for s in suggestions if s["kind"] == "required_hidden"]
    order = [i for i in issues if i["kind"] == "reading_order"]
    parts = {
        "crowding": max(0, 100 - 25 * len([i for i in crowd if i["kind"] == "crowded"]) - 10 * len([i for i in crowd if i["kind"] == "unbalanced"])),
        "hidden_required": max(0, 100 - 50 * len(hidden_req)),
        "empty_fields": 100 if not empty_count or not visible_count else max(0, round(100 - 100 * empty_count / visible_count * 2)),
        "accessibility": max(0, 100 - 15 * len(access) - 10 * len(order)),
    }
    weights = {"crowding": 0.3, "hidden_required": 0.25, "empty_fields": 0.2, "accessibility": 0.25}
    score = round(sum(parts[k] * w for k, w in weights.items()))
    words = {"crowding": "Crowding", "hidden_required": "Hidden required fields", "empty_fields": "Empty fields", "accessibility": "Accessibility"}
    return {"score": score, "parts": [{"key": k, "label": words[k], "score": v} for k, v in parts.items()],
            "fixable": sum(1 for i in [*issues, *suggestions] if i.get("ops"))}


def tidy_plan(tree: dict[str, Any], fields: dict[str, Any], counts: dict[str, int], total: int,
              sections: dict[str, str] | None = None) -> dict[str, Any]:
    """Tidy up: balance two-column groups, then inside each section keep fields of
    one meaning together (sections proposed by AI, validated here) and put the
    busiest first. Returns ops; nothing is applied here."""
    ops: list[dict[str, Any]] = []
    words: list[str] = []
    for issue in layout_checks(tree, fields, "form"):
        if issue["kind"] == "unbalanced" and issue["ops"]:
            ops.extend(issue["ops"])
            words.append(issue["text"].replace("Columns are unbalanced", "Balance the columns"))
    moved = {o["node"] for o in ops}
    for n, _p, hidden in _walk(tree):
        if n.get("tag") != "group" or hidden:
            continue
        kids = [c for c in n.get("children") or [] if c.get("tag") == "field" and c.get("anchor") and not c.get("helper") and c["id"] not in moved]
        if len(kids) < 3:
            continue

        def key(c: dict[str, Any], idx: int) -> tuple[int, int, int]:
            sec = (sections or {}).get(c.get("name") or "")
            first = next((i for i, k in enumerate(kids) if (sections or {}).get(k.get("name") or "") == sec), idx) if sec else idx
            rate = pct(counts.get(c.get("name") or "", 0), total) if total >= 20 else 0
            return (first, -rate if total >= 20 else 0, idx)

        order = sorted(range(len(kids)), key=lambda i: key(kids[i], i))
        if order == list(range(len(kids))):
            continue
        new = [kids[i] for i in order]
        for prev, cur in zip(new, new[1:]):
            ops.append({"op": "move", "node": cur["id"], "target": prev["id"], "position": "after"})
        words.append(f"Reorder {n.get('label') or 'a section'}: {', '.join(c.get('label') or '' for c in new[:4])}{'…' if len(new) > 4 else ''}")
    return {"ops": ops, "descriptions": words}


def validate_sections(raw: Any, tree: dict[str, Any]) -> dict[str, str]:
    """AI proposal {"sections":[{"title","fields":[...]}]} -> field -> section, only fields on screen."""
    on_screen = {i["node"].get("name") for i in screen_fields(tree)}
    out: dict[str, str] = {}
    for sec in (raw or {}).get("sections") or []:
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title") or "")[:60]
        for f in sec.get("fields") or []:
            if isinstance(f, str) and f in on_screen and f not in out:
                out[f] = title
    return out


def performance_hints(tree: dict[str, Any], fields: dict[str, Any], root_tag: str,
                      line_stats: dict[str, dict[str, int]] | None = None) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    sf = [i for i in screen_fields(tree) if not i["hidden"]]
    is_list = root_tag in {"list", "tree"}
    for item in sf:
        n = item["node"]
        meta = fields.get(n.get("name") or "") or {}
        label = n.get("label") or n.get("name")
        t = meta.get("type")
        if t in {"one2many", "many2many"} and line_stats and (n.get("name") in line_stats):
            st = line_stats[n["name"]]
            if st.get("max", 0) >= 200:
                hints.append({"kind": "big_lines", "node": n["id"], "text": f"{label} can hold up to {st['max']:,} rows; opening a record loads them all",
                              "fix_label": None, "ops": []})
        if is_list and meta.get("store") is False and (meta.get("depends") or meta.get("related")):
            opt = (n.get("attrs") or {}).get("optional")
            hints.append({"kind": "computed_column", "node": n["id"],
                          "text": f"{label} is worked out every time the list loads (not saved), which slows big lists",
                          "fix_label": None if opt == "hide" else "Make it an optional column, hidden at first",
                          "ops": [] if opt == "hide" or not n.get("anchor") else [{"op": "set_attr", "node": n["id"], "attr": "optional", "value": "hide"}]})
        if is_list and t == "binary":
            hints.append({"kind": "binary_column", "node": n["id"], "text": f"{label} loads a file for every row",
                          "fix_label": "Hide the column" if n.get("anchor") else None,
                          "ops": [{"op": "hide", "node": n["id"]}] if n.get("anchor") else []})
    if is_list:
        cols = [i for i in sf if not (i["node"].get("attrs") or {}).get("optional")]
        if len(cols) > 15:
            extra = [i["node"] for i in cols[12:] if i["node"].get("anchor")]
            hints.append({"kind": "many_columns", "text": f"{len(cols)} columns always load; lists feel slow past 15",
                          "fix_label": "Make the last ones optional",
                          "ops": [{"op": "set_attr", "node": x["id"], "attr": "optional", "value": "hide"} for x in extra]})
    return hints


# ----------------------------------------------------------------------------
# Screen-level group limits (inherited screen parts only some roles get)
# ----------------------------------------------------------------------------

def added_fields(arch: str) -> set[str]:
    """Field names an inherited screen part adds (inside/before/after steps)."""
    try:
        root = ET.fromstring(arch or "<data/>")
    except ET.ParseError:
        return set()
    out: set[str] = set()
    specs = [root] if root.tag == "xpath" else list(root.iter("xpath")) + ([root] if root.tag == "field" else [])
    if root.tag not in {"data", "xpath"} and root.get("position"):
        specs.append(root)
    for spec in specs:
        if (spec.get("position") or "inside") in {"attributes", "replace", "move"}:
            continue
        for el in spec.iter("field"):
            if el is not spec and el.get("name") and el.get("position") is None:
                out.add(el.get("name") or "")
    return out


def restricted_parts(views: list[dict[str, Any]], base_id: int, member_of: set[str], xmlid_of: dict[int, str],
                     names: dict[str, str]) -> dict[str, Any]:
    """Which fields come only from screen parts the role doesn't get.

    ``views`` rows: id, inherit_id, arch, groups (ids), name. Fields also added by
    a part everyone gets, or present in the base screen, are not counted."""
    children: dict[int, list[dict[str, Any]]] = {}
    for v in views:
        if v.get("inherit_id"):
            children.setdefault(int(v["inherit_id"]), []).append(v)
    base = next((v for v in views if int(v["id"]) == int(base_id)), None)
    open_fields: set[str] = set()
    base_arch = str((base or {}).get("arch") or "")
    for m in re.finditer(r'<field\b[^>]*\bname="([^"]+)"', base_arch):
        open_fields.add(m.group(1))
    limited: dict[str, list[str]] = {}
    stack: list[tuple[int, bool, str]] = [(int(base_id), True, "")]
    while stack:
        vid, allowed, parent_who = stack.pop()
        for v in children.get(vid, []):
            gids = [int(g) for g in v.get("groups") or []]
            xml = [xmlid_of.get(g, "") for g in gids]
            mine_ok = not gids or any(x in member_of for x in xml)
            ok = allowed and mine_ok
            fields_added = added_fields(str(v.get("arch") or ""))
            who = parent_who if not mine_ok and not gids else (
                ", ".join(names.get(x, x) for x in xml if x) or parent_who or "some roles")
            if ok:
                open_fields |= fields_added
            else:
                for f in fields_added:
                    limited.setdefault(f, []).append(who if not mine_ok else parent_who or "some roles")
            stack.append((int(v["id"]), ok, who if not ok else ""))
    hidden = {f: sorted(set(w)) for f, w in limited.items() if f not in open_fields}
    base_groups = [xmlid_of.get(int(g), "") for g in (base or {}).get("groups") or []]
    base_ok = not base_groups or any(x in member_of for x in base_groups)
    return {"hidden_fields": hidden, "base_ok": base_ok,
            "base_for": [names.get(x, x) for x in base_groups if x]}
