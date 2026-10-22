"""Shared view engine (Builders stage 1).

Loads the combined arch Odoo really uses, normalizes it into one tree with stable
node ids, compiles visual edit operations into the smallest inherited view
(xpath, never ``replace``, never positional), simulates that inheritance locally
so the result can be checked against what Odoo returns after publish.

Pure functions only: no Odoo calls here. The router owns RPC.
AI never reaches this module; it only sees validated ops from the UI.
"""

from __future__ import annotations

import copy
import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Literal

from odoo_client.xpath_locator import is_positional

LAYER_PREFIX = "ingenium_layer"
# Excludes copies inside embedded lines tables (one2many subviews). Odoo evaluates it with lxml.
TOP_LEVEL = "[not(ancestor::field)]"
LAYER_PRIORITY = 990

# Tags the canvas knows how to draw. Anything else becomes a labelled block.
CONTAINER_TAGS = frozenset({"form", "list", "tree", "kanban", "search", "calendar", "searchpanel", "sheet", "header", "group", "notebook", "page", "div", "footer"})
LEAF_TAGS = frozenset({"field", "button", "label", "separator", "newline", "widget", "h1", "h2", "h3", "span", "p", "a", "i", "img", "chatter", "filter"})
OPAQUE_TAGS = frozenset({"templates", "t"})
ROOT_TAGS = frozenset({"form", "list", "tree", "kanban", "search", "calendar"})

SHOWN_ATTRS = ("string", "invisible", "readonly", "required", "widget", "groups", "class", "placeholder", "nolabel", "help", "column_invisible", "optional",
               "width", "sum", "avg", "options", "style", "domain", "context", "type", "icon",
               "editable", "default_group_by", "default_order", "create", "delete", "multi_edit", "limit", "quick_create",
               "date_start", "date_stop", "color", "mode", "highlight_color",
               "decoration-danger", "decoration-warning", "decoration-success", "decoration-info", "decoration-muted",
               "decoration-primary", "decoration-bf", "decoration-it")
SETTABLE_ATTRS: dict[str, tuple[str, ...]] = {
    "field": ("string", "invisible", "readonly", "required", "widget", "placeholder", "nolabel", "help", "options", "style",
              "width", "optional", "sum", "avg"),
    "separator": ("string", "invisible"),
    "filter": ("string", "invisible"),
    "widget": ("title", "bg_color", "invisible"),
    "group": ("string", "invisible"),
    "page": ("string", "invisible"),
    "button": ("string", "invisible"),
    "notebook": ("invisible",),
    "div": ("invisible",),
}
BOOL_ATTRS = frozenset({"invisible", "readonly", "required", "nolabel"})
BOOL_VALUES = frozenset({"1", "0", "True", "False"})
WIDGET_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
FIELD_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")

# Where each kind may live (parent tag). Mirrors Odoo nesting rules.
ALLOWED_PARENTS: dict[str, frozenset[str]] = {
    "field": frozenset({"group", "page", "sheet", "div", "list", "tree", "kanban", "header", "form", "search", "calendar", "h1", "h2"}),
    "group": frozenset({"sheet", "page", "group", "div", "form"}),
    "page": frozenset({"notebook"}),
    "notebook": frozenset({"sheet", "page", "div", "form"}),
    "button": frozenset({"header", "div", "group", "list", "tree"}),
    "separator": frozenset({"group", "page", "sheet", "div"}),
    "label": frozenset({"group", "page", "sheet", "div"}),
    "div": frozenset({"sheet", "page", "group", "div", "form"}),
}

Position = Literal["before", "after", "inside"]


class EngineError(ValueError):
    """Plain-language problem with an edit. Message is shown to the user."""


# ----------------------------------------------------------------------------
# Parsing and normalizing
# ----------------------------------------------------------------------------

def parse_arch(arch: str) -> ET.Element:
    try:
        return ET.fromstring((arch or "").strip())
    except ET.ParseError as exc:
        raise EngineError(f"Odoo sent a screen layout that could not be read ({exc}).") from exc


def arch_hash(arch: str) -> str:
    return hashlib.sha256((arch or "").encode("utf-8")).hexdigest()


def _parents(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


def _in_subview(el: ET.Element, parents: dict[ET.Element, ET.Element], root: ET.Element) -> bool:
    """True when el sits inside an embedded list/form of a one2many field."""
    cur = parents.get(el)
    while cur is not None and cur is not root:
        if cur.tag == "field":
            return True
        cur = parents.get(cur)
    return False


def _count(root: ET.Element, expr: str) -> int:
    found = _find(root, expr)
    return len(found)


def _split_steps(expr: str) -> list[tuple[str, str]]:
    """Split an xpath into (axis, step) pairs; axis is '//' or '/'. Brackets and quotes respected."""
    out: list[tuple[str, str]] = []
    i, n = 0, len(expr)
    while i < n:
        if expr.startswith("//", i):
            axis, i = "//", i + 2
        elif expr[i] == "/":
            axis, i = "/", i + 1
        else:
            raise SyntaxError(expr)
        depth, quote, start = 0, "", i
        while i < n:
            ch = expr[i]
            if quote:
                if ch == quote:
                    quote = ""
            elif ch in "'\"":
                quote = ch
            elif ch in "[(":
                depth += 1
            elif ch in "])":
                depth -= 1
            elif ch == "/" and depth == 0:
                break
            i += 1
        step = expr[start:i]
        if not step:
            raise SyntaxError(expr)
        out.append((axis, step))
    return out


_STEP_RE = re.compile(r"^(\.\.|\*|[a-zA-Z_][\w.-]*)((?:\[.*\])*)$", re.S)


def _split_preds(text: str) -> list[str]:
    preds: list[str] = []
    depth, quote, start = 0, "", -1
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "[":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                preds.append(text[start:i].strip())
    return preds


def _eval_pred(el: ET.Element, pred: str, parents: dict[ET.Element, ET.Element]) -> bool:
    pred = pred.strip()
    m = re.fullmatch(r"not\((.*)\)", pred, re.S)
    if m:
        return not _eval_pred(el, m.group(1), parents)
    m = re.fullmatch(r"@([\w:-]+)\s*=\s*'([^']*)'", pred) or re.fullmatch(r'@([\w:-]+)\s*=\s*"([^"]*)"', pred)
    if m:
        return el.get(m.group(1)) == m.group(2)
    m = re.fullmatch(r"@([\w:-]+)", pred)
    if m:
        return m.group(1) in el.attrib
    m = re.fullmatch(r"hasclass\((.*)\)", pred, re.S)
    if m:
        wanted = re.findall(r"'([^']*)'", m.group(1))
        have = set((el.get("class") or "").split())
        return bool(wanted) and all(w in have for w in wanted)
    m = re.fullmatch(r"ancestor::([a-zA-Z_][\w-]*)", pred)
    if m:
        cur = parents.get(el)
        while cur is not None:
            if cur.tag == m.group(1):
                return True
            cur = parents.get(cur)
        return False
    raise SyntaxError(pred)


def _find(root: ET.Element, expr: str) -> list[ET.Element]:
    """Resolve the xpath subset the engine emits (named steps, attribute tests,
    hasclass, not(), ancestor::, ``..``) against an ElementTree root. Odoo
    evaluates the same expressions with lxml."""
    raw = (expr or "").strip()
    if not raw.startswith("/"):
        return []
    try:
        steps = _split_steps(raw)
    except SyntaxError:
        return []
    parents = _parents(root)
    doc = object()  # virtual document node above the root
    ctx: list[Any] = [doc]
    for axis, step in steps:
        m = _STEP_RE.match(step)
        if not m:
            return []
        test, preds = m.group(1), _split_preds(m.group(2) or "")
        found: list[ET.Element] = []
        seen: set[int] = set()
        for node in ctx:
            if test == "..":
                cand = [] if node is doc else ([parents[node]] if node in parents else [])
            elif axis == "//":
                if node is doc:
                    cand = list(root.iter())
                else:
                    cand = [d for d in node.iter() if d is not node]
            else:
                cand = [root] if node is doc else list(node)
            for c in cand:
                if not isinstance(c.tag, str):
                    continue
                if test not in {"..", "*"} and c.tag != test:
                    continue
                try:
                    if not all(_eval_pred(c, p, parents) for p in preds):
                        continue
                except SyntaxError:
                    return []
                if id(c) not in seen:
                    seen.add(id(c))
                    found.append(c)
        ctx = found
        if not ctx:
            return []
    order = {id(e): i for i, e in enumerate(root.iter())}
    return sorted(ctx, key=lambda e: order.get(id(e), 0))


def _matches_pred(el: ET.Element, pred: str) -> bool:
    m = re.fullmatch(r"\[@([\w-]+)='([^']*)'\]", pred)
    return bool(m and el.get(m.group(1)) == m.group(2))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:40] or "x"


def _label_for(el: ET.Element, fields: dict[str, Any]) -> str:
    if el.tag == "field":
        name = el.get("name") or ""
        return el.get("string") or str((fields.get(name) or {}).get("string") or name)
    if el.get("string"):
        return el.get("string") or ""
    if el.tag in {"h1", "h2", "h3", "span", "p", "label", "a"}:
        text = "".join(el.itertext()).strip()
        if text:
            return text[:60]
    if el.get("name"):
        return el.get("name") or ""
    return ""


def _kind(tag: str) -> str:
    if tag in ROOT_TAGS:
        return "root"
    if tag in CONTAINER_TAGS or tag in LEAF_TAGS:
        return "list" if tag == "tree" else tag
    if tag in OPAQUE_TAGS:
        return "template"
    return "block"


# Attributes that tell copies of one element apart (stage 2a unlock). Never
# ``string``: labels are translated and Odoo refuses them as selectors.
DISTINGUISH_ATTRS = ("widget", "readonly", "groups", "invisible", "required", "nolabel", "context", "options", "mode", "for", "id")
SETTINGS_NOTE = "Found by its settings, not its name. Ingenium re-checks it before every publish."


def _safe_value(value: str | None) -> bool:
    return value is not None and "'" not in value and len(value) <= 120


def _class_tokens(el: ET.Element) -> list[str]:
    return [c for c in (el.get("class") or "").split() if re.fullmatch(r"[\w-]{2,60}", c)]


def anchor_for(root: ET.Element, el: ET.Element, parents: dict[ET.Element, ET.Element]) -> tuple[str | None, str]:
    """Upgrade-safe xpath for el, or (None, reason). Never positional, never by label.

    Order of preference: unique name; name scoped by a named or uniquely classed
    ancestor; name plus a distinguishing setting; unique id/class; a uniquely
    reachable child (``/..``). Settings-based anchors are flagged by the caller."""
    anchor, why, _note = anchor_with_note(root, el, parents)
    return anchor, why


def anchor_with_note(root: ET.Element, el: ET.Element, parents: dict[ET.Element, ET.Element]) -> tuple[str | None, str, str]:
    tag = el.tag
    if el is root:
        return f"//{tag}", "", ""
    if tag in OPAQUE_TAGS:
        return None, "Odoo template code, changed as a whole only.", ""
    if tag == "field" and _in_subview(el, parents, root):
        return None, "Inside a lines table. Edit the table in a later stage.", ""
    name = el.get("name")

    def unique(expr: str) -> str | None:
        hits = _find(root, expr)
        if len(hits) == 1:
            return expr if hits[0] is el else None
        top = [h for h in hits if not _in_subview(h, parents, root)]
        if len(top) == 1 and top[0] is el:
            return expr + TOP_LEVEL
        return None

    def ancestors() -> list[ET.Element]:
        out: list[ET.Element] = []
        cur = parents.get(el)
        while cur is not None and cur is not root:
            out.append(cur)
            cur = parents.get(cur)
        return out

    if name and _safe_value(name):
        found = unique(f"//{tag}[@name='{name}']")
        if found:
            return found, "", ""
        base = f"{tag}[@name='{name}']"
        # Scoped by a named ancestor.
        for cur in ancestors():
            cname = cur.get("name")
            if cname and _safe_value(cname) and cur.tag in {"group", "page", "div", "notebook", "header", "sheet"}:
                scoped = unique(f"//{cur.tag}[@name='{cname}']//{base}")
                if scoped:
                    return scoped, "", ""
        # Scoped by an ancestor with a unique class or id.
        for cur in ancestors():
            if _safe_value(cur.get("id")):
                scoped = unique(f"//{cur.tag}[@id='{cur.get('id')}']//{base}")
                if scoped:
                    return scoped, "", SETTINGS_NOTE
            for cls in _class_tokens(cur):
                scoped = unique(f"//{cur.tag}[hasclass('{cls}')]//{base}")
                if scoped:
                    return scoped, "", SETTINGS_NOTE
        # Name plus a setting that only this copy has (or lacks).
        for attr in DISTINGUISH_ATTRS:
            val = el.get(attr)
            if val is not None and _safe_value(val):
                found = unique(f"//{base}[@{attr}='{val}']")
            elif val is None:
                found = unique(f"//{base}[not(@{attr})]")
            else:
                found = None
            if found:
                return found, "", SETTINGS_NOTE
        for cls in _class_tokens(el):
            found = unique(f"//{base}[hasclass('{cls}')]")
            if found:
                return found, "", SETTINGS_NOTE
        if tag != "field":
            pass  # fall through to unnamed strategies below
        else:
            return None, "This appears more than once with the same settings, so it can't be targeted safely.", ""
    if tag in {"sheet", "header", "notebook", "footer", "chatter"}:
        found = unique(f"//{tag}")
        if found:
            return found, "", ""
    if tag == "label" and _safe_value(el.get("for")):
        found = unique(f"//label[@for='{el.get('for')}']")
        if found:
            return found, "", SETTINGS_NOTE
    if _safe_value(el.get("id")):
        found = unique(f"//{tag}[@id='{el.get('id')}']")
        if found:
            return found, "", SETTINGS_NOTE
    tokens = _class_tokens(el)
    for cls in tokens:
        found = unique(f"//{tag}[hasclass('{cls}')]")
        if found:
            return found, "", SETTINGS_NOTE
    for i, c1 in enumerate(tokens):
        for c2 in tokens[i + 1:]:
            found = unique(f"//{tag}[hasclass('{c1}', '{c2}')]")
            if found:
                return found, "", SETTINGS_NOTE
    # Unnamed container: reach it through a uniquely targeted child directly inside it.
    if tag in {"group", "page", "div", "notebook", "header", "footer", "span", "h1", "h2", "h3"}:
        for child in el:
            if not isinstance(child.tag, str) or child.tag in OPAQUE_TAGS:
                continue
            cname = child.get("name")
            if child.tag in {"field", "group", "page", "button", "widget", "div"} and cname and _safe_value(cname):
                hits = _find(root, f"//{child.tag}[@name='{cname}']")
                top = [h for h in hits if not _in_subview(h, parents, root)]
                if len(top) == 1 and top[0] is child:
                    b = f"//{child.tag}[@name='{cname}']"
                    return (b if len(hits) == 1 else b + TOP_LEVEL) + "/..", "", ""
    if name:
        return None, "This appears more than once, so it can't be targeted safely.", ""
    return None, "Odoo gives this no name, so it can't be targeted safely.", ""


@dataclass
class Normalized:
    tree: dict[str, Any]
    by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    el_by_id: dict[str, ET.Element] = field(default_factory=dict)


def normalize(arch: str, fields: dict[str, Any] | None = None, *, root: ET.Element | None = None) -> Normalized:
    """Arch -> one tree for every Odoo major (17-20). Unknown tags are kept as blocks."""
    fields = fields or {}
    root = root if root is not None else parse_arch(arch)
    parents = _parents(root)
    out = Normalized(tree={})
    used: set[str] = set()

    def node_id(el: ET.Element, parent_id: str) -> str:
        if el is root:
            base = "root"
        elif el.tag == "field" and el.get("name") and not _in_subview(el, parents, root):
            base = f"field:{el.get('name')}"
        elif el.get("name"):
            base = f"{el.tag}:{el.get('name')}"
        else:
            hint = el.get("string") or next((c.get("name") for c in el if c.get("name")), "") or _label_for(el, fields)
            base = f"{parent_id}/{el.tag}:{_slug(hint) if hint else 'part'}"
        nid, n = base, 2
        while nid in used:
            nid = f"{base}~{n}"
            n += 1
        used.add(nid)
        return nid

    def walk(el: ET.Element, parent_id: str) -> dict[str, Any]:
        nid = node_id(el, parent_id)
        anchor, why, note = anchor_with_note(root, el, parents)
        if anchor and is_positional(anchor):
            anchor, why, note = None, "Only reachable by position, which breaks on upgrade.", ""
        kind = _kind(el.tag)
        attrs = {k: el.get(k) for k in SHOWN_ATTRS if el.get(k) is not None}
        node: dict[str, Any] = {
            "id": nid,
            "tag": el.tag,
            "kind": kind,
            "name": el.get("name"),
            "label": _label_for(el, fields),
            "attrs": attrs,
            "anchor": anchor,
            "locked_reason": None if anchor else why,
            "children": [],
        }
        if el.get("data-used-by") is not None:
            node["helper"] = True  # added by Odoo for values the screen needs
        if anchor and note:
            node["anchor_note"] = note
        if el.tag == "field":
            meta = fields.get(el.get("name") or "") or {}
            node["field_type"] = meta.get("type")
            node["relation"] = meta.get("relation")
            node["has_subview"] = any(child.tag in {"list", "tree", "form", "kanban"} for child in el)
            node["known_field"] = bool(meta) or not fields
        if kind == "block":
            node["label"] = node["label"] or f"Odoo element: {el.tag}"
        out.by_id[nid] = node
        out.el_by_id[nid] = el
        if el.tag == "field" or kind == "template":
            return node  # embedded subviews and QWeb stay opaque in stage 1
        for child in el:
            if not isinstance(child.tag, str):
                continue
            node["children"].append(walk(child, nid))
        return node

    out.tree = walk(root, "")
    return out


def signature(node: dict[str, Any]) -> list[Any]:
    """Structure + the attributes edits can change. Used for the fidelity check."""
    attrs = node.get("attrs") or {}
    keep = {k: attrs[k] for k in ("string", "invisible", "readonly", "required", "widget") if k in attrs}
    # Odoo appends hidden helper fields (marked data-used-by) for values other
    # parts of the screen need, e.g. when every visible copy is role-limited.
    # They aren't part of the design, so the check ignores them.
    kids = [c for c in node.get("children") or [] if not c.get("helper")]
    return [node.get("tag"), node.get("name") or "", keep, [signature(c) for c in kids]]


def diff_signatures(expected: list[Any], actual: list[Any], path: str = "") -> list[str]:
    """Plain-language list of where Odoo's result differs from what we expected."""
    out: list[str] = []
    etag, ename, eattrs, ekids = expected
    atag, aname, aattrs, akids = actual
    here = f"{path}/{etag}{'[' + ename + ']' if ename else ''}"
    if (etag, ename) != (atag, aname):
        return [f"{here}: Odoo shows {atag}{'[' + aname + ']' if aname else ''} here instead."]
    if eattrs != aattrs:
        out.append(f"{here}: settings differ (expected {eattrs}, Odoo has {aattrs}).")
    if len(ekids) != len(akids):
        out.append(f"{here}: expected {len(ekids)} items inside, Odoo shows {len(akids)}.")
    for e, a in zip(ekids, akids):
        out.extend(diff_signatures(e, a, here))
        if len(out) > 20:
            break
    return out


# ----------------------------------------------------------------------------
# Local inheritance (what Odoo will do with our layer)
# ----------------------------------------------------------------------------

def apply_inherit_local(base_arch: str, inherit_arch: str) -> str:
    """Apply an xpath inherit arch to base_arch the way Odoo's inheritance does
    for the subset the engine emits: inside / before / after / attributes, with
    nested ``position="move"`` specs."""
    root = parse_arch(base_arch)
    spec_root = parse_arch(inherit_arch)
    specs = list(spec_root) if spec_root.tag == "data" else [spec_root]
    for spec in specs:
        if spec.tag != "xpath":
            raise EngineError("Layer contains something other than xpath steps.")
        expr = spec.get("expr") or ""
        pos = spec.get("position") or "inside"
        hits = _find(root, expr)
        if not hits:
            raise EngineError(f"Can't find the place to change ({expr}).")
        target = hits[0]
        parents = _parents(root)
        if pos == "attributes":
            for attr in spec:
                if attr.tag != "attribute":
                    continue
                name = attr.get("name") or ""
                value = (attr.text or "").strip()
                if value:
                    target.set(name, value)
                elif name in target.attrib:
                    del target.attrib[name]
            continue
        new_nodes: list[ET.Element] = []
        for child in spec:
            if child.tag == "xpath" and child.get("position") == "move":
                moving = _find(root, child.get("expr") or "")
                if not moving:
                    raise EngineError(f"Can't find what to move ({child.get('expr')}).")
                el = moving[0]
                parents = _parents(root)
                parent = parents.get(el)
                if parent is None:
                    raise EngineError("Can't move the whole screen.")
                parent.remove(el)
                el.tail = None
                new_nodes.append(el)
            else:
                new_nodes.append(copy.deepcopy(child))
        parents = _parents(root)
        if pos == "inside":
            for n in new_nodes:
                target.append(n)
        elif pos in {"before", "after"}:
            parent = parents.get(target)
            if parent is None:
                raise EngineError("Can't place anything outside the whole screen.")
            idx = list(parent).index(target)
            if pos == "after":
                idx += 1
            for offset, n in enumerate(new_nodes):
                parent.insert(idx + offset, n)
        else:
            raise EngineError(f"Change type '{pos}' is not allowed.")
    return ET.tostring(root, encoding="unicode")


def merge_layers(old_layer: str | None, new_specs: str) -> str:
    """Append new xpath steps to an existing layer arch (one layer per view)."""
    new_root = parse_arch(new_specs)
    if not old_layer or not old_layer.strip():
        return ET.tostring(new_root, encoding="unicode")
    old_root = parse_arch(old_layer)
    if old_root.tag != "data":
        wrapper = ET.Element("data")
        wrapper.append(old_root)
        old_root = wrapper
    for spec in list(new_root):
        old_root.append(spec)
    return ET.tostring(old_root, encoding="unicode")


# ----------------------------------------------------------------------------
# Compile ops -> minimal inherit arch
# ----------------------------------------------------------------------------

@dataclass
class CompileResult:
    arch: str
    expected_arch: str
    steps: list[dict[str, Any]]
    dropped: list[str]
    warnings: list[str]
    expect: list[str] = field(default_factory=list)


def _xpath_el(expr: str, position: str) -> ET.Element:
    el = ET.Element("xpath")
    el.set("expr", expr)
    el.set("position", position)
    return el


def _require_node(norm: Normalized, nid: Any, what: str) -> tuple[dict[str, Any], ET.Element]:
    node = norm.by_id.get(str(nid or ""))
    if node is None:
        raise EngineError(f"The {what} you picked is no longer on this screen. Reload and try again.")
    if not node.get("anchor"):
        raise EngineError(f"'{node.get('label') or node.get('tag')}' can't be changed safely: {node.get('locked_reason')}")
    return node, norm.el_by_id[node["id"]]


def _check_parent(kind_tag: str, parent_tag: str, label: str) -> None:
    allowed = ALLOWED_PARENTS.get(kind_tag)
    if allowed is not None and parent_tag not in allowed:
        raise EngineError(f"'{label}' can't go inside a {_plain_tag(parent_tag)} in Odoo.")


def _plain_tag(tag: str) -> str:
    return {
        "group": "group", "page": "tab", "notebook": "set of tabs", "sheet": "form body",
        "header": "header bar", "div": "box", "list": "list", "tree": "list", "kanban": "card view",
        "form": "form", "field": "field",
    }.get(tag, tag)


def collapse_ops(ops: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Drop redundant ops: repeated moves of one node keep the last, repeated
    set_attr keep the last, insert followed by hide of the same field cancels."""
    dropped: list[str] = []
    last_move: dict[str, int] = {}
    last_attr: dict[tuple[str, str], int] = {}
    last_cond: dict[tuple[str, str], int] = {}
    last_access: dict[str, int] = {}
    hides: dict[str, int] = {}
    inserted: dict[str, int] = {}
    for i, op in enumerate(ops):
        kind = op.get("op")
        if kind == "move":
            last_move[str(op.get("node"))] = i
        elif kind == "set_attr":
            last_attr[(str(op.get("node")), str(op.get("attr")))] = i
        elif kind == "set_condition":
            last_cond[(str(op.get("node")), str(op.get("attr")))] = i
        elif kind == "set_access":
            last_access[str(op.get("node"))] = i
        elif kind == "set_decoration":
            last_cond[(str(op.get("node")), "decoration-" + str(op.get("style")))] = i
        elif kind == "hide":
            hides.setdefault(str(op.get("node")), i)
        elif kind == "insert_field":
            inserted[f"field:{op.get('field')}"] = i
    cancelled = {fid for fid in inserted if fid in hides}
    keep: list[dict[str, Any]] = []
    for i, op in enumerate(ops):
        kind = op.get("op")
        node = str(op.get("node"))
        if kind == "insert_field" and f"field:{op.get('field')}" in cancelled:
            dropped.append(f"Added {op.get('field')} then hid it, so neither is saved.")
            continue
        if node in cancelled and kind in {"hide", "move", "set_attr", "set_condition", "set_access"}:
            continue
        if kind == "set_condition" and last_cond.get((node, str(op.get("attr")))) != i:
            dropped.append(f"Earlier rule on {node} replaced by a later one.")
            continue
        if kind == "set_decoration" and last_cond.get((node, "decoration-" + str(op.get("style")))) != i:
            dropped.append(f"Earlier colour rule on {node} replaced by a later one.")
            continue
        if kind == "set_access" and last_access.get(node) != i:
            dropped.append(f"Earlier 'Who can see it' change on {node} replaced by a later one.")
            continue
        if kind == "move" and last_move.get(node) != i:
            dropped.append(f"Earlier move of {node} replaced by a later one.")
            continue
        if kind == "set_attr" and last_attr.get((node, str(op.get("attr")))) != i:
            dropped.append(f"Earlier {op.get('attr')} change on {node} replaced by a later one.")
            continue
        if kind == "hide" and hides.get(node) != i:
            dropped.append(f"{node} was already hidden.")
            continue
        keep.append(op)
    return keep, dropped


def compile_ops(
    combined_arch: str,
    fields: dict[str, Any],
    ops: list[dict[str, Any]],
    *,
    record_names: dict[str, dict[int, str]] | None = None,
    known_groups: set[str] | None = None,
    major: int = 0,
    actions: set[int] | None = None,
    methods: set[str] | None = None,
) -> CompileResult:
    """Fold ops into one ``<data>`` of xpath steps against the combined arch.

    Each op is validated against the *current* working tree (after earlier ops),
    so later ops may target groups/fields created by earlier ones.
    """
    if not isinstance(ops, list) or not ops:
        raise EngineError("There are no changes to save.")
    if len(ops) > 200:
        raise EngineError("Too many changes at once. Publish what you have, then continue.")
    ops, dropped = collapse_ops(ops)
    working = combined_arch
    out = ET.Element("data")
    steps: list[dict[str, Any]] = []
    warnings: list[str] = []
    wrap_seq = 0
    expect: list[str] = []
    from app import view_engine_library as lib

    for op in ops:
        root = parse_arch(working)
        norm = normalize("", fields, root=root)
        step_specs: list[ET.Element] = []
        kind = op.get("op")
        if kind == "move":
            node, el = _require_node(norm, op.get("node"), "item to move")
            target, tel = _require_node(norm, op.get("target"), "place to move to")
            pos = str(op.get("position") or "after")
            if pos not in {"before", "after", "inside"}:
                raise EngineError("Moves can go before, after or inside something.")
            if node["id"] == target["id"]:
                raise EngineError("Pick a different place to move it to.")
            if node["kind"] == "root":
                raise EngineError("The whole screen can't be moved.")
            parents = _parents(root)
            cur = tel
            while cur is not None:
                if cur is el:
                    raise EngineError(f"'{node['label']}' can't be moved inside itself.")
                cur = parents.get(cur)
            parent_tag = tel.tag if pos == "inside" else (parents.get(tel).tag if parents.get(tel) is not None else "")
            _check_parent(el.tag, parent_tag, node["label"])
            spec = _xpath_el(target["anchor"], pos)
            spec.append(_xpath_el(node["anchor"], "move"))
            step_specs.append(spec)
        elif kind == "insert_field":
            fname = str(op.get("field") or "")
            if not FIELD_NAME_RE.match(fname) or fname not in fields:
                raise EngineError(f"There is no field called '{fname}' on this record type.")
            if f"field:{fname}" in norm.by_id:
                raise EngineError(f"'{fields[fname].get('string') or fname}' is already on this screen.")
            target, tel = _require_node(norm, op.get("target"), "place to add it")
            pos = str(op.get("position") or "after")
            if pos not in {"before", "after", "inside"}:
                raise EngineError("New fields go before, after or inside something.")
            parents = _parents(root)
            parent_tag = tel.tag if pos == "inside" else (parents.get(tel).tag if parents.get(tel) is not None else "")
            _check_parent("field", parent_tag, str(fields[fname].get("string") or fname))
            spec = _xpath_el(target["anchor"], pos)
            new = ET.SubElement(spec, "field")
            new.set("name", fname)
            widget = str(op.get("widget") or "")
            if widget:
                lib.check_widget(widget, str(fields[fname].get("type") or ""), major or 17)
                new.set("widget", widget)
            for extra in ("string", "placeholder"):
                val = str(op.get(extra) or "").strip()
                if val:
                    if len(val) > 80:
                        raise EngineError("Labels and hints need 1 to 80 characters.")
                    new.set(extra, val)
            if op.get("optional") in {"show", "hide"} and root.tag in {"list", "tree"}:
                new.set("optional", str(op.get("optional")))
            step_specs.append(spec)
        elif kind == "hide":
            node, el = _require_node(norm, op.get("node"), "item to hide")
            if node["kind"] == "root":
                raise EngineError("The whole screen can't be hidden.")
            if el.tag == "field" and (fields.get(el.get("name") or "") or {}).get("required") is True:
                warnings.append(f"'{node['label']}' must be filled in. Hiding it can stop people saving records.")
            attr_name = "column_invisible" if root.tag in {"list", "tree"} and el.tag == "field" else "invisible"
            spec = _xpath_el(node["anchor"], "attributes")
            a = ET.SubElement(spec, "attribute")
            a.set("name", attr_name)
            a.text = "1"
            step_specs.append(spec)
        elif kind == "set_attr":
            node, el = _require_node(norm, op.get("node"), "item to change")
            attr = str(op.get("attr") or "")
            value = str(op.get("value") if op.get("value") is not None else "")
            if el is root:
                lib.check_root_attr(root.tag, attr, value, fields, major or 17)
                allowed = (attr,)
            else:
                allowed = SETTABLE_ATTRS.get(el.tag, ())
            if attr not in allowed:
                raise EngineError(f"'{attr}' can't be changed on this item here.")
            if attr in lib.LIST_FIELD_ATTRS:
                if root.tag not in {"list", "tree"}:
                    raise EngineError("Column settings only apply to lists.")
                lib.check_list_field_attr(attr, value)
                if attr in {"sum", "avg"} and value and (fields.get(el.get("name") or "") or {}).get("type") not in {"integer", "float", "monetary"}:
                    raise EngineError("Only number columns can show a total.")
            if attr == "options" and value:
                import ast as _ast

                try:
                    parsed = _ast.literal_eval(value)
                except (ValueError, SyntaxError) as exc:
                    raise EngineError("Those display options couldn't be read.") from exc
                if not isinstance(parsed, dict) or len(value) > 300:
                    raise EngineError("Those display options couldn't be read.")
            if attr == "style" and value and not re.fullmatch(r"(\s*(color|background-color)\s*:\s*#[0-9a-fA-F]{3,6}\s*;?)+\s*", value):
                raise EngineError("Only text and background colours can be set here.")
            if attr == "widget" and value and el.tag == "field":
                lib.check_widget(value, str((fields.get(el.get("name") or "") or {}).get("type") or ""), major or 17)
            if attr in BOOL_ATTRS and value not in BOOL_VALUES:
                raise EngineError("Choose yes or no for this setting.")
            if attr == "widget" and value and not WIDGET_RE.match(value):
                raise EngineError("That display style isn't valid.")
            if attr == "string" and (not value.strip() or len(value) > 80):
                raise EngineError("Labels need 1 to 80 characters.")
            if len(value) > 300:
                raise EngineError("That value is too long.")
            if el.get(attr) == value and not op.get("force"):
                dropped.append(f"{node['label']}: {attr} already set to that.")
                continue
            spec = _xpath_el(node["anchor"], "attributes")
            a = ET.SubElement(spec, "attribute")
            a.set("name", attr)
            a.text = value
            step_specs.append(spec)
        elif kind == "set_condition":
            from app import view_engine_logic as vl

            node, el = _require_node(norm, op.get("node"), "item to change")
            attr = str(op.get("attr") or "invisible")
            if attr not in vl.RULE_ATTRS:
                raise EngineError("Rules can show or hide an item, or make it required or read-only.")
            if attr in {"required", "readonly"} and el.tag != "field":
                raise EngineError("Only fields can be required or read-only.")
            if attr == "column_invisible" and root.tag not in {"list", "tree"}:
                raise EngineError("Whole columns can only be hidden on lists.")
            sense = "hide" if op.get("sense") == "hide" else "show"
            cond = op.get("condition")
            if op.get("copy_from"):
                # Copy rules: reuse the exact rule another item on this screen already has.
                _src, src_el = _require_node(norm, op.get("copy_from"), "item to copy from")
                value = src_el.get(attr) or ""
            elif cond is None:
                value = ""
            else:
                clean = vl.validate_condition(cond, fields, record_names=record_names)
                value = vl.rule_expression(attr, sense, vl.compile_condition(clean), el.get(attr), bool(op.get("keep_existing", True)))
            if len(value) > 600:
                raise EngineError("That rule is too long. Split it into fewer parts.")
            if (el.get(attr) or "") == value:
                dropped.append(f"{node['label']}: that rule is already in place.")
                continue
            spec = _xpath_el(node["anchor"], "attributes")
            a = ET.SubElement(spec, "attribute")
            a.set("name", attr)
            a.text = value
            step_specs.append(spec)
        elif kind == "set_access":
            from app import view_engine_logic as vl

            node, el = _require_node(norm, op.get("node"), "item to change")
            if node["kind"] == "root":
                raise EngineError("Use 'Access to this record type' for the whole screen.")
            edit, see = vl.access_level_groups(list(op.get("edit") or []), list(op.get("see") or []))
            if known_groups is not None:
                unknown = [g for g in [*edit, *see] if g not in known_groups]
                if unknown:
                    raise EngineError("A role you picked no longer exists in this database. Reload the roles.")
            if see and el.tag != "field":
                raise EngineError("Only fields can be read-only for some roles.")
            if see and any(child.tag in {"list", "tree", "form", "kanban"} for child in el):
                raise EngineError("Lines tables can't be read-only for some roles only yet. Choose Can edit or Hidden.")
            target_groups = ",".join(edit if edit else see)
            spec = _xpath_el(node["anchor"], "attributes")
            a = ET.SubElement(spec, "attribute")
            a.set("name", "groups")
            a.text = target_groups
            if see and not edit:
                ro = ET.SubElement(spec, "attribute")
                ro.set("name", "readonly")
                ro.text = "1"
            if (el.get("groups") or "") != target_groups or (see and not edit and el.get("readonly") != "1"):
                step_specs.append(spec)
            if see and edit:
                after = _xpath_el(node["anchor"], "after")
                copy_el = ET.SubElement(after, "field")
                for k, v in el.attrib.items():
                    if k not in {"groups", "readonly", "required"}:
                        copy_el.set(k, v)
                copy_el.set("groups", ",".join(see))
                copy_el.set("readonly", "1")
                step_specs.append(after)
            if not step_specs:
                dropped.append(f"{node['label']}: 'Who can see it' is already set that way.")
                continue
        elif kind == "insert_element":
            ekind = str(op.get("element") or "")
            target, tel = _require_node(norm, op.get("target"), "place to add it")
            pos = str(op.get("position") or "after")
            if pos not in {"before", "after", "inside"}:
                raise EngineError("New items go before, after or inside something.")
            parents = _parents(root)
            parent_tag = tel.tag if pos == "inside" else (parents.get(tel).tag if parents.get(tel) is not None else "")
            allowed_parents = lib.ELEMENT_PARENTS.get(ekind)
            if allowed_parents is None:
                raise EngineError(f"'{ekind}' isn't in the component library.")
            if ekind == "smart_button" and not (parent_tag == "div" and (tel if pos == "inside" else parents.get(tel)).get("name") == "button_box"):
                raise EngineError("Smart buttons go in the button box at the top of the form.")
            if parent_tag not in allowed_parents:
                raise EngineError(f"That can't go inside a {_plain_tag(parent_tag)} in Odoo.")
            wrap_seq += 1
            new_el = lib.build_element(ekind, op.get("props") or {}, root=root, fields=fields, major=major or 17,
                                       seq=wrap_seq, actions=actions, methods=methods)
            spec = _xpath_el(target["anchor"], pos)
            spec.append(new_el)
            step_specs.append(spec)
        elif kind == "set_decoration":
            from app import view_engine_logic as vl

            node, el = _require_node(norm, op.get("node"), "item to colour")
            style = str(op.get("style") or "")
            if style not in lib.DECORATIONS:
                raise EngineError("Pick a colour or style.")
            if root.tag not in {"list", "tree"} or not (el is root or el.tag == "field"):
                raise EngineError("Colour rules apply to list rows and columns.")
            cond = op.get("condition")
            value = "" if cond is None else vl.compile_condition(vl.validate_condition(cond, fields, record_names=record_names))
            attr = f"decoration-{style}"
            if (el.get(attr) or "") == value:
                dropped.append(f"{node['label']}: that colour rule is already in place.")
                continue
            spec = _xpath_el(node["anchor"], "attributes")
            a = ET.SubElement(spec, "attribute")
            a.set("name", attr)
            a.text = value
            step_specs.append(spec)
        elif kind == "kanban_add":
            if root.tag != "kanban":
                raise EngineError("Card items only go on card views.")
            akind = str(op.get("kind") or "field")
            if akind not in lib.KANBAN_ADD_KINDS:
                raise EngineError("Pick what to add to the card.")
            props = dict(op.get("props") or {})
            if akind == "colour":
                from app import view_engine_logic as vl

                props["expression"] = lib.compile_qweb_condition(
                    vl.validate_condition(op.get("condition"), fields, record_names=record_names), fields)
            anchor_expr, _place = lib.kanban_card_anchor(root)
            new_el = lib.build_kanban_element(akind, props, fields, major or 17)
            if akind != "colour" and new_el.tag == "field" and new_el.get("name") not in {e.get("name") for e in root.iter("field")}:
                pass
            spec = _xpath_el(anchor_expr, "inside")
            spec.append(new_el)
            step_specs.append(spec)
            expect.append(f'name="{props.get("field")}"' if akind != "colour" else "o_ingenium_card_flag")
        elif kind in {"search_add_filter", "search_add_groupby", "search_add_field"}:
            from app import view_engine_logic as vl

            if root.tag != "search":
                raise EngineError("Filters and group-bys go on the search screen.")
            label = str(op.get("label") or "").strip()
            if kind != "search_add_field" and (not label or len(label) > 80):
                raise EngineError("Give it a name of 1 to 80 characters.")
            wrap_seq += 1
            spec = _xpath_el("//search", "inside")
            if kind == "search_add_filter":
                cond = vl.validate_condition(op.get("condition"), fields, record_names=record_names)
                f = ET.SubElement(spec, "filter")
                f.set("name", f"{LAYER_PREFIX}_filter_{_slug(label)}_{wrap_seq}")
                f.set("string", label)
                f.set("domain", lib.compile_domain(cond))
                expect.append(f'name="{f.get("name")}"')
            elif kind == "search_add_groupby":
                fname = str(op.get("field") or "")
                meta = fields.get(fname) or {}
                if not meta or meta.get("type") not in lib.GROUPABLE or meta.get("store") is False:
                    raise EngineError(f"Records can't be grouped by '{meta.get('string') or fname}'.")
                f = ET.SubElement(spec, "filter")
                f.set("name", f"{LAYER_PREFIX}_groupby_{_slug(label)}_{wrap_seq}")
                f.set("string", label)
                f.set("context", f"{{'group_by': '{fname}'}}")
                expect.append(f'name="{f.get("name")}"')
            else:
                fname = str(op.get("field") or "")
                if not FIELD_NAME_RE.match(fname) or fname not in fields:
                    raise EngineError(f"There is no field called '{fname}' on this record type.")
                if fields[fname].get("store") is False and not fields[fname].get("related"):
                    raise EngineError("People can only search fields that are saved in the database.")
                f = ET.SubElement(spec, "field")
                f.set("name", fname)
                if label:
                    f.set("string", label[:80])
            step_specs.append(spec)
        elif kind == "insert_section":
            from app import view_engine_portable as vp

            target, tel = _require_node(norm, op.get("target"), "place to add it")
            pos = str(op.get("position") or "after")
            if pos not in {"before", "after", "inside"}:
                raise EngineError("Sections go before, after or inside something.")
            parents = _parents(root)
            parent_tag = tel.tag if pos == "inside" else (parents.get(tel).tag if parents.get(tel) is not None else "")
            wrap_seq += 1
            skip = {str(x) for x in (op.get("skip") or []) if isinstance(x, str)}
            left_out: list[dict[str, str]] = []
            sec = vp.validate_section_xml(str(op.get("xml") or ""), fields, root, wrap_seq, skip, left_out)
            if left_out:
                warnings.append("Left out of the section: " + ", ".join(f"{x['label']} ({x['reason']})" for x in left_out) + ".")
            _check_parent(sec.tag, parent_tag, sec.get("string") or "Section")
            spec = _xpath_el(target["anchor"], pos)
            spec.append(sec)
            step_specs.append(spec)
        elif kind == "wrap":
            ids = op.get("nodes") or []
            if not isinstance(ids, list) or not ids:
                raise EngineError("Pick at least one item to put into a new section.")
            wkind = str(op.get("kind") or "group")
            label = str(op.get("label") or "").strip()[:80]
            picked = [_require_node(norm, nid, "item") for nid in ids]
            parents = _parents(root)
            parent_els = {id(parents.get(el)) for _, el in picked}
            if len(parent_els) != 1:
                raise EngineError("Pick items that sit side by side in the same section.")
            parent = parents.get(picked[0][1])
            assert parent is not None
            wrap_seq += 1
            new_name = f"{LAYER_PREFIX}_{wkind}_{_slug(label) if label else 'new'}_{wrap_seq}"
            while _count(root, f"//{wkind}[@name='{new_name}']"):
                wrap_seq += 1
                new_name = f"{LAYER_PREFIX}_{wkind}_{_slug(label) if label else 'new'}_{wrap_seq}"
            first_node, first_el = picked[0]
            if wkind == "group":
                for n, el in picked:
                    _check_parent(el.tag, "group", n["label"])
                _check_parent("group", parent.tag, label or "New group")
                spec = _xpath_el(first_node["anchor"], "before")
                g = ET.SubElement(spec, "group")
                g.set("name", new_name)
                if label:
                    g.set("string", label)
                step_specs.append(spec)
                inner = _xpath_el(f"//group[@name='{new_name}']", "inside")
                for n, _el in picked:
                    inner.append(_xpath_el(n["anchor"], "move"))
                step_specs.append(inner)
            elif wkind == "page":
                if parent.tag != "page":
                    raise EngineError("A new tab can only be made from items that are already on a tab.")
                page_node = next((v for k, v in norm.by_id.items() if norm.el_by_id[k] is parent), None)
                if not page_node or not page_node.get("anchor"):
                    raise EngineError("That tab can't be targeted safely, so a new tab can't be added next to it.")
                spec = _xpath_el(page_node["anchor"], "after")
                p = ET.SubElement(spec, "page")
                p.set("name", new_name)
                p.set("string", label or "New tab")
                step_specs.append(spec)
                inner = _xpath_el(f"//page[@name='{new_name}']", "inside")
                for n, _el in picked:
                    inner.append(_xpath_el(n["anchor"], "move"))
                step_specs.append(inner)
            elif wkind == "notebook":
                for n, el in picked:
                    if el.tag not in {"group", "field", "div", "separator"}:
                        raise EngineError(f"'{n['label']}' can't go on a tab.")
                _check_parent("notebook", parent.tag, label or "New tabs")
                spec = _xpath_el(first_node["anchor"], "before")
                nb = ET.SubElement(spec, "notebook")
                nb.set("name", new_name)
                p = ET.SubElement(nb, "page")
                p.set("name", f"{new_name}_page")
                p.set("string", label or "New tab")
                step_specs.append(spec)
                inner = _xpath_el(f"//page[@name='{new_name}_page']", "inside")
                for n, _el in picked:
                    inner.append(_xpath_el(n["anchor"], "move"))
                step_specs.append(inner)
            else:
                raise EngineError("New sections can be a group, a tab or a set of tabs.")
        else:
            raise EngineError(f"Unknown change '{kind}'.")

        for spec in step_specs:
            expr = spec.get("expr") or ""
            if is_positional(expr) or (spec.get("position") == "replace"):
                raise EngineError("That change would need an unsafe locator, so it was refused.")
            for inner_spec in spec.iter("xpath"):
                if inner_spec.get("position") == "replace" or is_positional(inner_spec.get("expr") or ""):
                    raise EngineError("That change would need an unsafe locator, so it was refused.")
        if not step_specs:
            continue
        chunk = ET.Element("data")
        for spec in step_specs:
            chunk.append(spec)
        working = apply_inherit_local(working, ET.tostring(chunk, encoding="unicode"))
        for spec in step_specs:
            out.append(spec)
        steps.append({"op": kind, "xpath": [ET.tostring(s, encoding="unicode") for s in step_specs]})

    if not len(out):
        raise EngineError("These changes cancel each other out, so there is nothing to save.")
    arch = ET.tostring(out, encoding="unicode")
    return CompileResult(arch=arch, expected_arch=working, steps=steps, dropped=dropped, warnings=sorted(set(warnings)), expect=expect)


# ----------------------------------------------------------------------------
# Records (live sample, read-only, never stored)
# ----------------------------------------------------------------------------

READ_SKIP_TYPES = frozenset({"binary", "image", "properties", "properties_definition", "json"})
MAX_SAMPLE = 80


def record_fields(tree: dict[str, Any], fields: dict[str, Any]) -> list[str]:
    names: list[str] = []

    def walk(node: dict[str, Any]) -> None:
        if node.get("tag") == "field" and node.get("name") and str(node["id"]).startswith("field:"):
            meta = fields.get(node["name"]) or {}
            if meta and meta.get("type") not in READ_SKIP_TYPES and node["name"] not in names:
                names.append(node["name"])
        for child in node.get("children") or []:
            walk(child)

    walk(tree)
    return names[:120]


def display_value(value: Any, meta: dict[str, Any]) -> Any:
    ftype = meta.get("type")
    if value is False or value is None:
        return "" if ftype != "boolean" else False
    if ftype == "many2one" and isinstance(value, (list, tuple)) and len(value) == 2:
        return str(value[1])
    if ftype in {"one2many", "many2many"} and isinstance(value, list):
        return f"{len(value)} item{'s' if len(value) != 1 else ''}"
    if ftype == "selection":
        for key, label in meta.get("selection") or []:
            if key == value:
                return str(label)
        return str(value)
    if ftype == "html" and isinstance(value, str):
        text = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", text).strip()[:240]
    if isinstance(value, str):
        return value[:240]
    return value


def stress_picks(records: list[dict[str, Any]], names: list[str]) -> dict[str, int | None]:
    """Code picks the longest and emptiest record from the sample."""
    if not records:
        return {"longest": None, "emptiest": None}

    def length(rec: dict[str, Any]) -> int:
        return sum(len(str(rec.get(n) or "")) for n in names if not isinstance(rec.get(n), bool))

    def empties(rec: dict[str, Any]) -> int:
        return sum(1 for n in names if rec.get(n) in ("", None, False, "0 items"))

    longest = max(records, key=lambda r: (length(r), -int(r.get("id") or 0)))
    emptiest = max(records, key=lambda r: (empties(r), -length(r)))
    return {"longest": int(longest["id"]), "emptiest": int(emptiest["id"])}


def layer_name(model: str, view_type: str, base_view_id: int) -> str:
    return f"{LAYER_PREFIX} {model} {view_type} {base_view_id}"


def count_layer_steps(layer_arch: str | None) -> int:
    if not layer_arch:
        return 0
    try:
        root = parse_arch(layer_arch)
    except EngineError:
        return 0
    return len(list(root)) if root.tag == "data" else 1
