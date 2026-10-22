"""Logic layer of the shared view engine (Builders stage 2a).

Pure, deterministic code:
- show/hide/required/read-only conditions: validate a condition tree, compile it
  to an Odoo 17+ inline expression, render the plain sentence back from the tree,
  and explain existing Odoo expressions in plain words;
- "Who can see it": evaluate ``groups`` for a role or a person, and the impact
  of an access change;
- history compare (tree diff with added / moved / hidden / changed markers);
- version checks against the stock catalogue captured from disposable DBs.

AI never reaches this module directly: AI output is passed through these
validators before anyone sees it.
"""

from __future__ import annotations

import ast
import gzip
import json
import re
from pathlib import Path
from typing import Any

from app.view_engine import EngineError

FIELD_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")
XMLID_RE = re.compile(r"^[a-z0-9_]+\.[a-zA-Z0-9_]+$")

# Operators the builder offers, per field type.
OPS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "boolean": ("is_true", "is_false"),
    "selection": ("is", "is_not", "in", "not_in", "set", "not_set"),
    "many2one": ("is", "is_not", "in", "not_in", "set", "not_set"),
    "many2many": ("set", "not_set"),
    "one2many": ("set", "not_set"),
    "char": ("is", "is_not", "contains", "set", "not_set"),
    "text": ("contains", "set", "not_set"),
    "html": ("set", "not_set"),
    "integer": ("eq", "ne", "gt", "ge", "lt", "le"),
    "float": ("eq", "ne", "gt", "ge", "lt", "le"),
    "monetary": ("eq", "ne", "gt", "ge", "lt", "le"),
    "date": ("set", "not_set"),
    "datetime": ("set", "not_set"),
}
OP_WORDS = {
    "is_true": "is ticked", "is_false": "is not ticked", "is": "is", "is_not": "is not",
    "in": "is one of", "not_in": "is none of", "set": "is filled in", "not_set": "is empty",
    "contains": "contains", "eq": "equals", "ne": "doesn't equal", "gt": "is more than",
    "ge": "is at least", "lt": "is less than", "le": "is at most",
}
NUM_OPS = {"eq": "==", "ne": "!=", "gt": ">", "ge": ">=", "lt": "<", "le": "<="}
RULE_ATTRS = ("invisible", "required", "readonly", "column_invisible")
MAX_RULES = 6


# ----------------------------------------------------------------------------
# Conditions: validate, compile, sentence
# ----------------------------------------------------------------------------

def _label(fields: dict[str, Any], name: str) -> str:
    return str((fields.get(name) or {}).get("string") or name)


def _sel_label(meta: dict[str, Any], key: Any) -> str:
    for k, lbl in meta.get("selection") or []:
        if k == key:
            return str(lbl)
    return str(key)


def validate_condition(cond: Any, fields: dict[str, Any], *, record_names: dict[str, dict[int, str]] | None = None) -> dict[str, Any]:
    """Check every field, operator and value. Returns a clean tree or raises EngineError.

    ``record_names`` maps many2one field -> {id: name} for ids that exist in Odoo
    (looked up by the router). Unknown ids are refused."""
    if not isinstance(cond, dict):
        raise EngineError("The rule could not be read.")
    rules = cond.get("rules")
    if not isinstance(rules, list) or not rules:
        raise EngineError("Add at least one part to the rule.")
    if len(rules) > MAX_RULES:
        raise EngineError(f"Rules can have up to {MAX_RULES} parts.")
    match = "any" if cond.get("match") == "any" else "all"
    clean: list[dict[str, Any]] = []
    for r in rules:
        if not isinstance(r, dict):
            raise EngineError("A part of the rule could not be read.")
        fname = str(r.get("field") or "")
        if not FIELD_RE.match(fname) or fname not in fields:
            raise EngineError(f"There is no field called '{fname}' on this record type.")
        meta = fields[fname] or {}
        ftype = str(meta.get("type") or "char")
        allowed = OPS_BY_TYPE.get(ftype)
        if not allowed:
            raise EngineError(f"Rules can't use '{_label(fields, fname)}' yet.")
        op = str(r.get("op") or "")
        if op not in allowed:
            raise EngineError(f"'{_label(fields, fname)}' can't be compared that way.")
        value = r.get("value")
        out: dict[str, Any] = {"field": fname, "op": op}
        if op in {"is", "is_not", "in", "not_in"}:
            values = value if isinstance(value, list) else [value]
            if op in {"is", "is_not"} and len(values) != 1:
                raise EngineError(f"Pick one value for '{_label(fields, fname)}'.")
            if not values or len(values) > 20:
                raise EngineError(f"Pick 1 to 20 values for '{_label(fields, fname)}'.")
            if ftype == "selection":
                keys = {k for k, _ in meta.get("selection") or []}
                for v in values:
                    if v not in keys:
                        raise EngineError(f"'{v}' isn't a choice of '{_label(fields, fname)}'.")
            elif ftype == "many2one":
                known = (record_names or {}).get(fname) or {}
                ids: list[int] = []
                for v in values:
                    if isinstance(v, bool) or not isinstance(v, int) or v not in known:
                        raise EngineError(f"That {_label(fields, fname)} wasn't found in your database.")
                    ids.append(int(v))
                values = ids
            elif ftype == "char":
                values = [str(v) for v in values]
                if any(len(v) > 120 or not v for v in values):
                    raise EngineError("Text values need 1 to 120 characters.")
            out["value"] = values if op in {"in", "not_in"} else values[0]
        elif op == "contains":
            text = str(value or "")
            if not text or len(text) > 120:
                raise EngineError("Text values need 1 to 120 characters.")
            out["value"] = text
        elif op in NUM_OPS:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                try:
                    value = float(str(value))
                except ValueError as exc:
                    raise EngineError(f"'{_label(fields, fname)}' needs a number.") from exc
            out["value"] = int(value) if ftype == "integer" or float(value).is_integer() else float(value)
        clean.append(out)
    return {"match": match, "rules": clean}


def _py(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_py(v) for v in value) + "]"
    return repr(value)


def compile_condition(cond: dict[str, Any]) -> str:
    """Validated tree -> Odoo 17+ inline expression (never ``attrs``)."""
    parts: list[str] = []
    for r in cond["rules"]:
        f, op, v = r["field"], r["op"], r.get("value")
        if op == "is_true" or op == "set":
            parts.append(f)
        elif op == "is_false" or op == "not_set":
            parts.append(f"not {f}")
        elif op == "is":
            parts.append(f"{f} == {_py(v)}")
        elif op == "is_not":
            parts.append(f"{f} != {_py(v)}")
        elif op == "in":
            parts.append(f"{f} in {_py(v)}")
        elif op == "not_in":
            parts.append(f"{f} not in {_py(v)}")
        elif op == "contains":
            parts.append(f"{_py(v)} in ({f} or '')")
        elif op in NUM_OPS:
            parts.append(f"{f} {NUM_OPS[op]} {_py(v)}")
    joiner = " or " if cond.get("match") == "any" else " and "
    if len(parts) == 1:
        return parts[0]
    return joiner.join(f"({p})" if (" or " in p or " and " in p) else p for p in parts)


def condition_sentence(cond: dict[str, Any], fields: dict[str, Any], record_names: dict[str, dict[int, str]] | None = None) -> str:
    """Plain sentence written by code from the tree (what the user approves)."""
    bits: list[str] = []
    for r in cond["rules"]:
        f, op, v = r["field"], r["op"], r.get("value")
        meta = fields.get(f) or {}
        lbl = _label(fields, f)

        def show(x: Any) -> str:
            if meta.get("type") == "selection":
                return _sel_label(meta, x)
            if meta.get("type") == "many2one":
                return str(((record_names or {}).get(f) or {}).get(int(x), f"record {x}"))
            if isinstance(x, float) and x.is_integer():
                return str(int(x))
            return str(x)

        if op in {"in", "not_in"}:
            vals = [show(x) for x in (v or [])]
            joined = ", ".join(vals[:-1]) + (" or " if len(vals) > 1 else "") + vals[-1] if vals else ""
            bits.append(f"{lbl} {'is' if op == 'in' else 'is not'} {joined}")
        elif op in {"is", "is_not", "contains"} or op in NUM_OPS:
            bits.append(f"{lbl} {OP_WORDS[op]} {show(v)}")
        else:
            bits.append(f"{lbl} {OP_WORDS[op]}")
    return (" or " if cond.get("match") == "any" else " and ").join(bits)


def rule_sentence(attr: str, sense: str, cond_text: str) -> str:
    if attr in {"invisible", "column_invisible"}:
        return f"Shown only when {cond_text}" if sense == "show" else f"Hidden when {cond_text}"
    if attr == "required":
        return f"Must be filled in when {cond_text}"
    return f"Read-only when {cond_text}"


def rule_expression(attr: str, sense: str, cond_expr: str, existing: str | None, keep_existing: bool) -> str:
    """Final attribute value. For show rules the user's condition is negated.
    Odoo's own rule is kept (or-ed) unless the user chose to replace it."""
    mine = f"not ({cond_expr})" if attr in {"invisible", "column_invisible"} and sense == "show" else cond_expr
    old = (existing or "").strip()
    if keep_existing and old and old not in {"0", "False", "false"}:
        if old in {"1", "True", "true"}:
            return old
        return f"({old}) or ({mine})"
    return mine


# ----------------------------------------------------------------------------
# Explain existing Odoo expressions in plain words
# ----------------------------------------------------------------------------

_CMP_WORDS = {ast.Eq: "is", ast.NotEq: "is not", ast.Gt: "is more than", ast.GtE: "is at least",
              ast.Lt: "is less than", ast.LtE: "is at most", ast.In: "is one of", ast.NotIn: "is none of"}


def expression_m2o_ids(expr: str, fields: dict[str, Any]) -> dict[str, set[int]]:
    """many2one field -> ids mentioned in an expression (so names can be looked up)."""
    out: dict[str, set[int]] = {}
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name):
            f = node.left.id
            if (fields.get(f) or {}).get("type") != "many2one":
                continue
            for comp in node.comparators:
                vals = comp.elts if isinstance(comp, (ast.List, ast.Tuple)) else [comp]
                for v in vals:
                    if isinstance(v, ast.Constant) and isinstance(v.value, int) and not isinstance(v.value, bool):
                        out.setdefault(f, set()).add(int(v.value))
    return out


def explain_expression(expr: str | None, fields: dict[str, Any], record_names: dict[str, dict[int, str]] | None = None) -> str | None:
    """'stage_id == 4 and not active' -> 'Stage is Won and Active is not ticked'.
    Returns None when the expression is beyond plain words (shown under Show code)."""
    raw = (expr or "").strip()
    if not raw:
        return None
    if raw in {"1", "True", "true"}:
        return "always"
    if raw in {"0", "False", "false"}:
        return "never"
    try:
        tree = ast.parse(raw, mode="eval")
    except SyntaxError:
        return None

    def name(n: ast.AST) -> str | None:
        if isinstance(n, ast.Name) and n.id in fields:
            return _label(fields, n.id)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "parent":
            return f"the parent's {n.attr}"
        return None

    def const(n: ast.AST, field_name: str | None) -> str | None:
        if isinstance(n, ast.Constant):
            v = n.value
            meta = fields.get(field_name or "") or {}
            if meta.get("type") == "selection":
                return _sel_label(meta, v)
            if meta.get("type") == "many2one" and isinstance(v, int):
                return str(((record_names or {}).get(field_name or "") or {}).get(v, f"record {v}"))
            if v is False or v is None:
                return "empty"
            if v is True:
                return "ticked"
            return str(v)
        if isinstance(n, (ast.List, ast.Tuple)):
            vals = [const(e, field_name) for e in n.elts]
            if any(v is None for v in vals):
                return None
            return ", ".join(v for v in vals if v)
        return None

    def walk(n: ast.AST) -> str | None:
        if isinstance(n, ast.BoolOp):
            parts = [walk(v) for v in n.values]
            if any(p is None for p in parts):
                return None
            return (" and " if isinstance(n.op, ast.And) else " or ").join(p for p in parts if p)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            inner = n.operand
            nm = name(inner)
            if nm:
                ftype = (fields.get(getattr(inner, "id", "")) or {}).get("type")
                return f"{nm} is not ticked" if ftype == "boolean" else f"{nm} is empty"
            sub = walk(inner)
            return f"not ({sub})" if sub else None
        nm = name(n)
        if nm:
            ftype = (fields.get(getattr(n, "id", "")) or {}).get("type")
            return f"{nm} is ticked" if ftype == "boolean" else f"{nm} is filled in"
        if isinstance(n, ast.Compare) and len(n.ops) == 1:
            left = n.left
            fname = left.id if isinstance(left, ast.Name) else None
            nm = name(left)
            word = _CMP_WORDS.get(type(n.ops[0]))
            right = const(n.comparators[0], fname)
            if nm and word and right is not None:
                if right == "empty" and word in {"is", "is not"}:
                    return f"{nm} {'is empty' if word == 'is' else 'is filled in'}"
                return f"{nm} {word} {right}"
            # 'x' in (name or '')
            if isinstance(left, ast.Constant) and isinstance(n.ops[0], ast.In):
                tgt = n.comparators[0]
                if isinstance(tgt, ast.BoolOp) and tgt.values and name(tgt.values[0]):
                    return f"{name(tgt.values[0])} contains {left.value}"
            return None
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get":
            base = n.func.value
            if isinstance(base, ast.Name) and base.id == "context" and n.args and isinstance(n.args[0], ast.Constant):
                return f"the screen was opened with '{n.args[0].value}'"
        return None

    return walk(tree.body)


def why_sentence(attr: str, expr: str | None, fields: dict[str, Any], record_names: dict[str, dict[int, str]] | None = None) -> str | None:
    text = explain_expression(expr, fields, record_names)
    if text is None:
        return None
    if attr in {"invisible", "column_invisible"}:
        return "Always hidden." if text == "always" else (None if text == "never" else f"Hidden when {text}.")
    if attr == "required":
        return "Always required." if text == "always" else (None if text == "never" else f"Must be filled in when {text}.")
    return "Always read-only." if text == "always" else (None if text == "never" else f"Read-only when {text}.")


# ----------------------------------------------------------------------------
# Groups ("Who can see it")
# ----------------------------------------------------------------------------

DEBUG_GROUP = "base.group_no_one"


def groups_allow(groups_attr: str | None, member_of: set[str], dev_kept: bool = True) -> bool:
    """Odoo's rule: comma list is OR; '!g' matches when the person is NOT in g.
    Odoo 19+ keeps 'Technical features' (base.group_no_one) items for everyone
    and the web client shows them in developer mode only, so with dev_kept that
    group counts as met; visibility_for adds the developer-mode note. Older
    versions (dev_kept=False) drop those items outside developer mode even for
    members (every internal user gets the group), so it counts as not met."""
    if DEBUG_GROUP in (groups_attr or ""):
        member_of = (member_of | {DEBUG_GROUP}) if dev_kept else (member_of - {DEBUG_GROUP})
    raw = (groups_attr or "").strip()
    if not raw:
        return True
    for token in (t.strip() for t in raw.split(",")):
        if not token:
            continue
        if token.startswith("!"):
            if token[1:] not in member_of:
                return True
        elif token in member_of:
            return True
    return False


def visibility_for(tree: dict[str, Any], member_of: set[str], field_groups: dict[str, str] | None = None,
                   group_names: dict[str, str] | None = None, dev_kept: bool = True) -> dict[str, dict[str, Any]]:
    """Per node: visible for this person/role, and why not. Conditions are listed
    but not evaluated (they depend on the record)."""
    out: dict[str, dict[str, Any]] = {}
    names = group_names or {}

    def who(attr: str) -> str:
        toks = [t.strip() for t in attr.split(",") if t.strip()]
        plain = [("not " if t.startswith("!") else "") + names.get(t.lstrip("!"), t.lstrip("!")) for t in toks]
        return ", ".join(plain)

    def walk(node: dict[str, Any], parent_hidden: str | None) -> None:
        attrs = node.get("attrs") or {}
        reason = parent_hidden
        if reason is None and not groups_allow(attrs.get("groups"), member_of, dev_kept):
            g = str(attrs.get("groups") or "")
            reason = ("Only shown in developer mode." if not dev_kept and DEBUG_GROUP in g
                      and groups_allow(g, member_of | {DEBUG_GROUP}, True)
                      else f"Only {who(g)} can see it.")
        if reason is None and node.get("tag") == "field" and field_groups and node.get("name") in field_groups:
            fg = field_groups[node["name"]]
            if not groups_allow(fg, member_of, dev_kept):
                reason = f"The field itself is limited to {who(fg)}."
        if reason is None and node.get("helper"):
            reason = "Always hidden. Odoo adds it so other parts of the screen work."
        elif reason is None and str(attrs.get("invisible") or "").strip() in {"1", "True", "true"}:
            reason = ("Only shown in developer mode." if DEBUG_GROUP in str(attrs.get("groups") or "")
                      else "Always hidden on this screen.")
        entry: dict[str, Any] = {"visible": reason is None, "reason": reason}
        if reason is None and dev_kept and DEBUG_GROUP in str(attrs.get("groups") or "") and not str(attrs.get("groups")).strip().startswith("!"):
            entry["note"] = "Only shown in developer mode."
        out[node["id"]] = entry
        hidden_for_kids = reason if reason is None else "The section it sits in is hidden."
        for child in node.get("children") or []:
            walk(child, hidden_for_kids if reason else None)

    walk(tree, None)
    return out


def prune_for(arch_root: Any, member_of: set[str], dev_kept: bool = True) -> None:
    """Remove nodes this person can't see and drop ``groups`` attributes, the way
    Odoo's get_views does for the logged-in user (used by the fidelity check)."""
    stack = [arch_root]
    while stack:
        el = stack.pop()
        for child in list(el):
            if not isinstance(child.tag, str):
                continue
            g = child.get("groups")
            if g is not None:
                if not groups_allow(g, member_of, dev_kept):
                    el.remove(child)
                    continue
                del child.attrib["groups"]
            stack.append(child)


def access_level_groups(edit: list[str], see: list[str]) -> tuple[list[str], list[str]]:
    for g in [*edit, *see]:
        if not XMLID_RE.match(g):
            raise EngineError("A role could not be recognised. Reload the roles and try again.")
    if set(edit) & set(see):
        raise EngineError("A role can't be both 'Can edit' and 'Can only see'.")
    return sorted(set(edit)), sorted(set(see))


# ----------------------------------------------------------------------------
# History compare
# ----------------------------------------------------------------------------

def _index(tree: dict[str, Any]) -> dict[str, tuple[str | None, dict[str, Any]]]:
    out: dict[str, tuple[str | None, dict[str, Any]]] = {}

    def walk(n: dict[str, Any], parent: str | None) -> None:
        out[n["id"]] = (parent, n)
        for c in n.get("children") or []:
            walk(c, n["id"])

    walk(tree, None)
    return out


def compare_trees(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Markers per node id: added, removed, moved, hidden, shown, changed (plain list too)."""
    a, b = _index(old), _index(new)
    markers: dict[str, str] = {}
    lines: list[str] = []
    for nid, (parent, node) in b.items():
        label = node.get("label") or node.get("tag")
        if nid not in a:
            markers[nid] = "added"
            lines.append(f"Added {label}")
            continue
        oparent, onode = a[nid]
        oinv = (onode.get("attrs") or {}).get("invisible") or (onode.get("attrs") or {}).get("column_invisible")
        ninv = (node.get("attrs") or {}).get("invisible") or (node.get("attrs") or {}).get("column_invisible")
        if parent != oparent:
            markers[nid] = "moved"
            lines.append(f"Moved {label}")
        elif oinv != ninv:
            markers[nid] = "hidden" if ninv in {"1", "True"} else ("shown" if not ninv else "changed")
            lines.append(f"{'Hid' if markers[nid] == 'hidden' else 'Changed when it shows:'} {label}")
        elif (onode.get("attrs") or {}) != (node.get("attrs") or {}) or onode.get("label") != node.get("label"):
            markers[nid] = "changed"
            lines.append(f"Changed {label}")
    for nid, (_p, node) in a.items():
        if nid not in b:
            markers[nid] = "removed"
            lines.append(f"Removed {node.get('label') or node.get('tag')}")
    # sibling order changes inside one parent count as moves
    for nid, (_p, node) in b.items():
        if nid in a and nid not in markers:
            ok = [c["id"] for c in a[nid][1].get("children") or [] if c["id"] in b]
            nk = [c["id"] for c in node.get("children") or [] if c["id"] in a]
            if ok != nk:
                common = [x for x in nk if x in ok]
                old_common = [x for x in ok if x in nk]
                for x, y in zip(common, old_common):
                    if x != y and x not in markers:
                        markers[x] = "moved"
                        lines.append(f"Moved {b[x][1].get('label') or b[x][1].get('tag')}")
    return {"markers": markers, "changes": lines[:200]}


# ----------------------------------------------------------------------------
# Version catalogue (stock screens captured from disposable Odoo 17-20 DBs)
# ----------------------------------------------------------------------------

CATALOG_DIR = Path(__file__).resolve().parent / "data" / "view_catalog"


def load_catalog(major: int) -> dict[str, Any] | None:
    path = CATALOG_DIR / f"v{int(major)}.json.gz"
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def catalog_versions() -> list[int]:
    if not CATALOG_DIR.exists():
        return []
    out = []
    for p in CATALOG_DIR.glob("v*.json.gz"):
        m = re.match(r"v(\d+)\.json\.gz$", p.name)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def ops_fields(ops: list[dict[str, Any]]) -> set[str]:
    """Field names an edit relies on (added fields and fields used in rules)."""
    out: set[str] = set()
    for op in ops:
        if op.get("op") == "insert_field" and op.get("field"):
            out.add(str(op["field"]))
        if op.get("op") == "set_condition" and isinstance(op.get("condition"), dict):
            for r in op["condition"].get("rules") or []:
                if isinstance(r, dict) and r.get("field"):
                    out.add(str(r["field"]))
        for key in ("node", "target"):
            nid = str(op.get(key) or "")
            if nid.startswith("field:"):
                out.add(nid.split(":", 1)[1])
    return out
