"""Builders stage 2b: new screens, reusable sections, upgrade guard, packages.

Pure code. The router reads Odoo and writes through the same checked publish
path as every other change; stock views are never written.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from typing import Any

from app.view_engine import LAYER_PREFIX, EngineError, _find, _parents, _slug, parse_arch

SCREEN_PREFIX = "ingenium_screen"
SCREEN_PRIORITY = 1000  # never becomes the default screen; opened through its own menu item or action
PACKAGE_FORMAT = "ingenium-layout/1"
SKIP_FIELDS = frozenset({"id", "display_name", "create_uid", "create_date", "write_uid", "write_date", "__last_update"})

# ----------------------------------------------------------------------------
# New screens from blank or a starter template
# ----------------------------------------------------------------------------

TEMPLATES: dict[str, list[dict[str, str]]] = {
    "form": [{"key": "blank", "label": "Blank"}, {"key": "two_columns", "label": "Title and two columns"},
             {"key": "tabs", "label": "Title, details and tabs"}],
    "list": [{"key": "blank", "label": "Name only"}, {"key": "basic", "label": "Main columns"}],
    "kanban": [{"key": "card", "label": "Card with title and details"}],
    "search": [{"key": "basic", "label": "Search by name with filters"}],
    "calendar": [{"key": "basic", "label": "Calendar by date"}],
}


def title_field(fields: dict[str, Any]) -> str:
    for cand in ("name", "x_name", "display_name"):
        if cand in fields and (fields[cand].get("store") is not False or cand == "name"):
            return cand
    for n, m in fields.items():
        if m.get("type") == "char" and m.get("store") is not False and n not in SKIP_FIELDS:
            return n
    raise EngineError("This record type has no text field to use as a title.")


def detail_fields(fields: dict[str, Any], exclude: set[str], limit: int) -> list[str]:
    """Required fields first, then common stored ones; deterministic order."""
    usable = {n: m for n, m in fields.items()
              if n not in SKIP_FIELDS and n not in exclude and not n.startswith("message_") and not n.startswith("activity_")
              and m.get("store") is not False and m.get("type") not in {"binary", "one2many", "properties", "properties_definition", "json", "html"}
              and not m.get("readonly")}
    req = sorted(n for n, m in usable.items() if m.get("required"))
    rest = sorted((n for n in usable if n not in req), key=lambda n: (usable[n].get("type") not in {"many2one", "selection", "date", "char"}, n))
    return (req + rest)[:limit]


def date_fields(fields: dict[str, Any]) -> list[str]:
    return sorted(n for n, m in fields.items() if m.get("type") in {"date", "datetime"} and m.get("store") is not False and n not in SKIP_FIELDS)


def screen_templates(fields: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for vt, items in TEMPLATES.items():
        for t in items:
            reason = None
            if vt == "calendar" and not date_fields(fields):
                reason = "This record type has no date field, so it can't have a calendar."
            out.append({"view_type": vt, **t, "available": reason is None, "reason": reason})
    return out


def build_screen_arch(view_type: str, template: str, fields: dict[str, Any], major: int, label: str) -> str:
    keys = {t["key"] for t in TEMPLATES.get(view_type, [])}
    if template not in keys:
        raise EngineError("Pick one of the starting layouts.")
    title = title_field(fields)
    esc = lambda t: (t or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")  # noqa: E731
    if view_type == "form":
        details = detail_fields(fields, {title}, 8)
        parts = [f'<form string="{esc(label)}"><sheet>',
                 f'<div class="oe_title" name="{SCREEN_PREFIX}_title"><h1><field name="{title}"/></h1></div>']
        if template == "blank":
            parts.append(f'<group name="{SCREEN_PREFIX}_main"/>')
        else:
            half = (len(details) + 1) // 2
            left = "".join(f'<field name="{f}"/>' for f in details[:half])
            right = "".join(f'<field name="{f}"/>' for f in details[half:])
            parts.append(f'<group name="{SCREEN_PREFIX}_main"><group name="{SCREEN_PREFIX}_left">{left}</group>'
                         f'<group name="{SCREEN_PREFIX}_right">{right}</group></group>')
            if template == "tabs":
                parts.append(f'<notebook name="{SCREEN_PREFIX}_tabs"><page name="{SCREEN_PREFIX}_details" string="Details">'
                             f'<group name="{SCREEN_PREFIX}_details_group"/></page></notebook>')
        parts.append("</sheet>")
        if "message_ids" in fields:
            if major >= 18:
                parts.append("<chatter/>")
            else:
                inner = "".join(f'<field name="{f}"/>' for f in ("message_follower_ids", "activity_ids", "message_ids") if f in fields)
                parts.append(f'<div class="oe_chatter">{inner}</div>')
        parts.append("</form>")
        return "".join(parts)
    if view_type == "list":
        root = "list" if major >= 18 else "tree"
        cols = [title] + ([] if template == "blank" else detail_fields(fields, {title}, 5))
        return f'<{root} string="{esc(label)}">' + "".join(f'<field name="{f}"/>' for f in cols) + f"</{root}>"
    if view_type == "kanban":
        details = detail_fields(fields, {title}, 2)
        body = f'<field name="{title}" class="fw-bold"/>' + "".join(f'<field name="{f}"/>' for f in details)
        if major >= 18:
            return f'<kanban string="{esc(label)}"><templates><t t-name="card">{body}</t></templates></kanban>'
        fields_decl = "".join(f'<field name="{f}"/>' for f in [title, *details])
        return (f'<kanban string="{esc(label)}">{fields_decl}<templates><t t-name="kanban-box">'
                f'<div class="oe_kanban_global_click">{body}</div></t></templates></kanban>')
    if view_type == "search":
        parts = [f'<search string="{esc(label)}"><field name="{title}"/>']
        if "active" in fields:
            parts.append(f'<filter name="{SCREEN_PREFIX}_archived" string="Archived" domain="[(\'active\', \'=\', False)]"/>')
        groupable = [n for n in detail_fields(fields, {title}, 20) if fields[n].get("type") in {"many2one", "selection"}][:1]
        for g in groupable:
            parts.append(f'<filter name="{SCREEN_PREFIX}_by_{g}" string="{esc(str(fields[g].get("string") or g))}" '
                         f'context="{{\'group_by\': \'{g}\'}}"/>')
        parts.append("</search>")
        return "".join(parts)
    if view_type == "calendar":
        dates = date_fields(fields)
        if not dates:
            raise EngineError("This record type has no date field, so it can't have a calendar.")
        return f'<calendar string="{esc(label)}" date_start="{dates[0]}" mode="month"><field name="{title}"/></calendar>'
    raise EngineError("Choose a form, list, card, search or calendar screen.")


def screen_view_name(model: str, view_type: str, label: str) -> str:
    return f"{SCREEN_PREFIX} {model} {view_type} {_slug(label)}"


# ----------------------------------------------------------------------------
# Reusable sections
# ----------------------------------------------------------------------------

SECTION_TAGS = frozenset({"group", "page", "notebook", "separator", "field", "label", "newline", "div"})
SECTION_ATTRS = frozenset({"name", "string", "widget", "placeholder", "nolabel", "colspan", "col", "for", "help", "optional"})
SECTION_CONTAINERS = frozenset({"group", "page", "notebook", "div"})


def _clean_copy(el: ET.Element) -> ET.Element:
    out = ET.Element(el.tag)
    for k, v in el.attrib.items():
        if k in SECTION_ATTRS:
            out.set(k, v)
    for child in el:
        if isinstance(child.tag, str) and child.tag in SECTION_TAGS:
            out.append(_clean_copy(child))
    return out


def extract_section(el: ET.Element, fields: dict[str, Any]) -> dict[str, Any]:
    """Portable copy of a section: structure, labels and field names only.
    Show/hide rules and role limits are left behind (they may not fit elsewhere)."""
    if el.tag not in SECTION_CONTAINERS:
        raise EngineError("Save a group, a tab or a set of tabs as a section.")
    clean = _clean_copy(el)
    names = [f.get("name") for f in clean.iter("field") if f.get("name")]
    if not names:
        raise EngineError("That section has no fields to reuse.")
    return {"xml": ET.tostring(clean, encoding="unicode"),
            "fields": [{"name": n, "type": (fields.get(n) or {}).get("type"), "label": (fields.get(n) or {}).get("string") or n}
                       for n in dict.fromkeys(names)],
            "tag": clean.tag}


def section_fit(section: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    missing = [f for f in section.get("fields") or [] if f["name"] not in fields]
    wrong = [f for f in section.get("fields") or [] if f["name"] in fields and f.get("type") and fields[f["name"]].get("type") != f["type"]]
    return {"missing": missing, "wrong_type": wrong, "fits": not missing and not wrong}


def validate_section_xml(xml: str, fields: dict[str, Any], root: ET.Element, seq: int, skip: set[str] | None = None,
                         left_out: list[dict[str, str]] | None = None) -> ET.Element:
    """Strictly re-check a saved section before it goes into a screen: allowed tags
    and attributes only, fresh names for containers. Fields already on the screen
    (or not on this record type) are left out and reported in ``left_out``; groups
    and tabs left empty are dropped."""
    try:
        el = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise EngineError("That saved section couldn't be read.") from exc
    skip = skip or set()
    out = left_out if left_out is not None else []

    def why_out(fname: str) -> str | None:
        if fname not in fields:
            return "not on this record type"
        if fname in skip or _find(root, f"//field[@name='{fname}']"):
            return "already on this screen"
        return None

    def walk(node: ET.Element) -> None:
        if node.tag not in SECTION_TAGS:
            raise EngineError("That saved section has something that can't go on a screen.")
        for k in list(node.attrib):
            if k not in SECTION_ATTRS:
                del node.attrib[k]
        for child in list(node):
            if node.tag == "field" or not isinstance(child.tag, str):
                node.remove(child)
                continue
            if child.tag == "field":
                fname = child.get("name") or ""
                reason = why_out(fname)
                if reason:
                    out.append({"field": fname, "label": str((fields.get(fname) or {}).get("string") or fname), "reason": reason})
                    node.remove(child)
                    continue
            walk(child)
            if child.tag in SECTION_CONTAINERS and child.tag != "field" and not list(child.iter("field")):
                node.remove(child)  # nothing left inside
        if node.tag == "field":
            fname = node.get("name") or ""
            reason = why_out(fname)
            if reason == "not on this record type":
                raise EngineError(f"The field '{fname}' isn't on this record type.")
            if reason:
                raise EngineError(f"'{fields[fname].get('string') or fname}' is already on this screen.")
        elif node.tag in SECTION_CONTAINERS and node.get("name"):
            node.set("name", f"{LAYER_PREFIX}_sec_{_slug(node.get('name') or '')[:24]}_{seq}_{abs(hash(node.get('name'))) % 10000}")

    walk(el)
    if not list(el.iter("field")):
        if out:
            raise EngineError("Everything in that section is already on this screen (or not on this record type), so there is nothing to add.")
        raise EngineError("None of the section's fields are on this record type.")
    return el


# ----------------------------------------------------------------------------
# Upgrade guard: is every step of the layer still doing what it did?
# ----------------------------------------------------------------------------

def layer_specs(layer_arch: str | None) -> list[ET.Element]:
    if not layer_arch:
        return []
    root = parse_arch(layer_arch)
    return list(root) if root.tag == "data" else [root]


def _describe_spec(spec: ET.Element) -> str:
    expr = spec.get("expr") or ""
    m = re.search(r"@name='([^']+)'", expr)
    what = m.group(1) if m else expr.split("/")[-1][:40]
    pos = spec.get("position") or "inside"
    if pos == "attributes":
        names = ", ".join(a.get("name") or "" for a in spec if a.tag == "attribute")
        return f"Change {names} of {what}"
    moves = [c for c in spec if c.tag == "xpath" and c.get("position") == "move"]
    if moves:
        mm = re.search(r"@name='([^']+)'", moves[0].get("expr") or "")
        return f"Move {mm.group(1) if mm else 'an item'} {pos} {what}"
    adds = [c for c in spec if c.tag != "xpath"]
    if adds:
        return f"Add {adds[0].get('name') or adds[0].get('string') or adds[0].tag} {pos} {what}"
    return f"Change near {what}"


def step_status(spec: ET.Element, combined: ET.Element) -> tuple[str, str]:
    """('ok' | 'overridden' | 'missing', plain reason) for one layer step against
    the screen Odoo combines now (raw, before user pruning)."""
    expr = spec.get("expr") or ""
    pos = spec.get("position") or "inside"
    targets = _find(combined, expr)
    if pos == "attributes":
        if not targets:
            return "missing", "The item it changed is no longer on Odoo's screen."
        t = targets[0]
        for a in spec:
            if a.tag != "attribute":
                continue
            want = (a.text or "").strip()
            have = (t.get(a.get("name") or "") or "").strip()
            if want != have:
                return "overridden", "Something else now changes the same setting after it."
        return "ok", ""
    parents = _parents(combined)
    for child in spec:
        if child.tag == "xpath" and child.get("position") == "move":
            moved = _find(combined, child.get("expr") or "")
            if not moved:
                return "missing", "The item it moved is no longer on Odoo's screen."
            if not targets:
                return "missing", "The place it moved to is no longer on Odoo's screen."
            m, t = moved[0], targets[0]
            if pos == "inside" and parents.get(m) is not t:
                return "overridden", "Something else moved it again afterwards."
            if pos in {"before", "after"}:
                p = parents.get(m)
                if p is None or p is not parents.get(t):
                    return "overridden", "Something else moved it again afterwards."
                kids = list(p)
                if (kids.index(m) < kids.index(t)) != (pos == "before"):
                    return "overridden", "Something else moved it again afterwards."
            continue
        name = child.get("name")
        if name:
            if not [e for e in combined.iter(child.tag) if e.get("name") == name]:
                return "missing", "What it added isn't on Odoo's screen any more."
        elif not list(combined.iter(child.tag)):
            return "missing", "What it added isn't on Odoo's screen any more."
    return "ok", ""


def _spec_keys(spec: ET.Element) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    if spec.get("position") == "attributes":
        for a in spec:
            if a.tag == "attribute":
                keys.add(("attr", f"{spec.get('expr')}|{a.get('name')}"))
    for c in spec:
        if c.tag == "xpath" and c.get("position") == "move":
            keys.add(("move", c.get("expr") or ""))
    return keys


def _superseded(spec: ET.Element, later: list[ET.Element]) -> bool:
    mine = _spec_keys(spec)
    if not mine:
        return False
    theirs: set[tuple[str, str]] = set()
    for s in later:
        theirs |= _spec_keys(s)
    return mine <= theirs


def guard_report(layer_arch: str | None, combined_raw: str | None) -> list[dict[str, Any]]:
    if not layer_arch:
        return []
    if not combined_raw:
        return [{"index": i, "status": "missing", "text": _describe_spec(s), "reason": "Odoo can't show this screen right now."}
                for i, s in enumerate(layer_specs(layer_arch))]
    combined = parse_arch(combined_raw)
    specs = layer_specs(layer_arch)
    out = []
    for i, spec in enumerate(specs):
        if _superseded(spec, specs[i + 1:]):
            out.append({"index": i, "status": "ok", "text": _describe_spec(spec), "reason": "Replaced by a later change of yours."})
            continue
        status, reason = step_status(spec, combined)
        out.append({"index": i, "status": status, "text": _describe_spec(spec), "reason": reason})
    return out


def stock_signature(hashes: dict[int, str]) -> str:
    return hashlib.sha256(json.dumps(sorted((int(k), v) for k, v in hashes.items())).encode()).hexdigest()


# ----------------------------------------------------------------------------
# Portable package (staging -> production)
# ----------------------------------------------------------------------------

def referenced_fields(layer_arch: str) -> set[str]:
    out: set[str] = set()
    for spec in layer_specs(layer_arch):
        for el in spec.iter("field"):
            if el.get("name"):
                out.add(el.get("name") or "")
        for x in spec.iter("xpath"):
            for m in re.finditer(r"field\[@name='([^']+)'\]", x.get("expr") or ""):
                out.add(m.group(1))
    return out


# -- things a package must carry by meaning, not by database id --

_COUNT_RE = re.compile(r"for record in self:\n    record\['(x_\w+)'\] = record\.env\['([a-z0-9_.]+)'\]\.search_count\(\[\('([a-z_][a-z0-9_]*)', '=', record\.id\)\]\)")
_LINK_DOMAIN_RE = re.compile(r"^\[\('([a-z_][a-z0-9_]*)', '=', active_id\)\]$")


def count_compute(name: str, relation: str, link_field: str) -> str:
    """The only calculation a package can bring: "how many <relation> point here through <link_field>".
    Written by us from checked names, never taken from the file."""
    for v in (name, link_field):
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", v):
            raise EngineError("That count field has an odd name, so it can't be made.")
    if not re.fullmatch(r"[a-z0-9_.]+", relation):
        raise EngineError("That count field points at an odd record type, so it can't be made.")
    return f"for record in self:\n    record['{name}'] = record.env['{relation}'].search_count([('{link_field}', '=', record.id)])"


def count_spec(name: str, compute: str | None) -> dict[str, str] | None:
    m = _COUNT_RE.fullmatch((compute or "").strip())
    if not m or m.group(1) != name:
        return None
    return {"relation": m.group(2), "link_field": m.group(3)}


def link_action_spec(action: dict[str, Any]) -> dict[str, str] | None:
    """A smart-button list made by Ingenium: records of res_model whose link field points at this record."""
    m = _LINK_DOMAIN_RE.match(str(action.get("domain") or "").strip())
    if not m or not action.get("res_model"):
        return None
    return {"name": str(action.get("name") or "")[:80], "res_model": str(action["res_model"]), "link_field": m.group(1)}


def action_refs(layer_arch: str) -> set[int]:
    out: set[int] = set()
    for spec in layer_specs(layer_arch):
        for el in spec.iter("button"):
            if el.get("type") == "action" and re.fullmatch(r"\d+", el.get("name") or ""):
                out.add(int(el.get("name") or 0))
    return out


def rewrite_action_ids(layer_arch: str, mapping: dict[int, int]) -> str:
    root = parse_arch(layer_arch)
    for el in root.iter("button"):
        if el.get("type") == "action" and re.fullmatch(r"\d+", el.get("name") or "") and int(el.get("name") or 0) in mapping:
            el.set("name", str(int(mapping[int(el.get("name") or 0)])))
    return ET.tostring(root, encoding="unicode")


def adapt_layer(layer_arch: str, from_major: int, to_major: int) -> str:
    """Make a layer from one Odoo version fit another where the difference is
    known and safe (list root naming). Refuse where it isn't."""
    out = layer_arch
    if from_major >= 18 > to_major:
        if "<chatter" in out or "t-name='card'" in out:
            raise EngineError("This layout uses parts Odoo 17 doesn't have (new chatter or card layout).")
        out = out.replace("//list", "//tree").replace("<list", "<tree").replace("</list>", "</tree>")
    elif from_major < 18 <= to_major:
        if "kanban-box" in out or "oe_chatter" in out:
            raise EngineError("This layout uses parts newer Odoo versions changed (old chatter or card layout).")
        out = out.replace("//tree", "//list").replace("<tree", "<list").replace("</tree>", "</list>")
    return out


def package_checksum(pkg: dict[str, Any]) -> str:
    body = {k: v for k, v in pkg.items() if k != "checksum"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def check_package(pkg: Any) -> dict[str, Any]:
    if not isinstance(pkg, dict) or pkg.get("format") != PACKAGE_FORMAT:
        raise EngineError("That file isn't an Ingenium layout package.")
    if pkg.get("checksum") != package_checksum(pkg):
        raise EngineError("The package was changed after it was made, so it can't be trusted.")
    for key in ("model", "view_type", "layer_arch", "odoo_major"):
        if not pkg.get(key):
            raise EngineError("The package is missing part of the layout.")
    parse_arch(str(pkg["layer_arch"]))
    if not all(s.tag == "xpath" for s in layer_specs(str(pkg["layer_arch"]))):
        raise EngineError("The package contains something other than screen changes.")
    if "position=\"replace\"" in pkg["layer_arch"] or "position='replace'" in pkg["layer_arch"]:
        raise EngineError("The package replaces parts of Odoo's screen, which isn't allowed.")
    acts = pkg.get("actions") or []
    if not isinstance(acts, list) or not all(isinstance(a, dict) and isinstance(a.get("id"), int)
                                               and ((isinstance(a.get("xmlid"), str) and str(a.get("model") or "").startswith("ir.actions.")) or isinstance(a.get("define"), dict))
                                               for a in acts):
        raise EngineError("The package's button actions can't be read.")
    if action_refs(str(pkg["layer_arch"])) - {int(a["id"]) for a in acts}:
        raise EngineError("A button in the package opens something the package doesn't describe, so it can't be moved.")
    for d in pkg.get("custom_fields") or []:
        if isinstance(d, dict) and (d.get("compute") or d.get("depends")):
            raise EngineError("A package can't carry calculation code.")
    return pkg
