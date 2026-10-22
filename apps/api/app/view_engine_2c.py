"""Builders stage 2c: the 19 approved ideas (SPEC section 18).

Pure, deterministic helpers (no Odoo calls here). The router reads facts from
Odoo (counts and metadata only, never record contents unless the canvas already
shows them) and passes them in. AI only ever proposes; every proposal is
validated here against the live field list before anything is shown.
"""

from __future__ import annotations

import ast
import copy as copy_mod
import html as htmlmod
import math
import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app import view_engine_logic as vl
from app.view_engine import LAYER_PREFIX, EngineError

# ----------------------------------------------------------------------------
# Shared tree helpers
# ----------------------------------------------------------------------------

TRUE_WORDS = {"1", "True", "true"}


def walk(node: dict[str, Any], parent: dict[str, Any] | None = None, hidden: bool = False):
    attrs = node.get("attrs") or {}
    me_hidden = hidden or str(attrs.get("invisible") or "").strip() in TRUE_WORDS
    yield node, parent, me_hidden
    for c in node.get("children") or []:
        yield from walk(c, node, me_hidden)


def screen_field_nodes(tree: dict[str, Any]) -> list[tuple[dict[str, Any], bool]]:
    out = []
    for n, _p, hidden in walk(tree):
        if n.get("tag") == "field" and str(n.get("id", "")).startswith("field:") and not n.get("helper"):
            out.append((n, hidden))
    return out


def _label(fields: dict[str, Any], name: str) -> str:
    return str((fields.get(name) or {}).get("string") or name)


# ----------------------------------------------------------------------------
# 1. Field dependency map (what else uses this field before you hide/remove it)
# ----------------------------------------------------------------------------

def _word_re(name: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")


def uses_in_screen(tree: dict[str, Any], field: str) -> list[dict[str, str]]:
    """Other items on this screen whose rules read the field."""
    rx = _word_re(field)
    out = []
    for n, _p, _h in walk(tree):
        if n.get("tag") == "field" and n.get("name") == field:
            continue
        for attr in ("invisible", "required", "readonly", "column_invisible", "context", "domain"):
            expr = str((n.get("attrs") or {}).get(attr) or "")
            if expr and rx.search(expr):
                what = {"invisible": "show/hide rule", "column_invisible": "column rule", "required": "required rule",
                        "readonly": "read-only rule", "context": "default values", "domain": "choice filter"}[attr]
                out.append({"node": n["id"], "label": n.get("label") or n.get("tag") or "", "how": what})
    return out


def arch_mentions(arch: str, field: str, *, model_hint: str | None = None) -> bool:
    """A view/report/template arch reads the field (by name in a field tag, an
    expression, or object.field / doc.field / record.field)."""
    if not arch:
        return False
    if re.search(rf'<field[^>]*\bname="{re.escape(field)}"', arch):
        return True
    if re.search(rf"\b(?:o|doc|object|record|line|docs)\.{re.escape(field)}\b", arch):
        return True
    return bool(re.search(rf'(?:invisible|required|readonly|column_invisible)="[^"]*(?<![A-Za-z0-9_.]){re.escape(field)}(?![A-Za-z0-9_])', arch))


def domain_mentions(domain: str | None, field: str) -> bool:
    if not domain:
        return False
    return bool(re.search(rf"['\"]{re.escape(field)}(?:\.[a-z_]+)*['\"]", domain))


DEP_KINDS = {
    "screen_rule": ("This screen", "high"),
    "view": ("Other screens", "medium"),
    "report": ("Printed documents", "medium"),
    "email": ("Email templates", "medium"),
    "automation": ("Automations", "high"),
    "server_action": ("Server actions", "high"),
    "record_rule": ("Who can see which records", "high"),
    "filter": ("Saved filters", "low"),
    "default": ("Default values", "low"),
    "computed": ("Other fields calculated from it", "high"),
    "required": ("Saving", "high"),
}


def dependency_summary(items: list[dict[str, Any]], label: str, removing: bool) -> dict[str, Any]:
    """Group dependency hits; decide whether hiding/removing is safe in plain words."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        groups.setdefault(it["kind"], []).append(it)
    high = [k for k in groups if DEP_KINDS.get(k, ("", "low"))[1] == "high"]
    out_groups = [{"kind": k, "title": DEP_KINDS.get(k, (k, "low"))[0], "risk": DEP_KINDS.get(k, ("", "low"))[1],
                   "items": v[:25], "count": len(v)} for k, v in groups.items()]
    out_groups.sort(key=lambda g: ({"high": 0, "medium": 1, "low": 2}[g["risk"]], g["title"]))
    if not items:
        verdict = f"Nothing else uses {label}. {'Removing' if removing else 'Hiding'} it is safe."
        level = "safe"
    elif removing and high:
        verdict = f"{label} is used in {len(items)} place{'s' if len(items) != 1 else ''}, including {', '.join(DEP_KINDS[k][0].lower() for k in high)}. Removing it would break them; hide it instead."
        level = "blocked"
    elif high and not removing:
        verdict = (f"{label} is used in {len(items)} place{'s' if len(items) != 1 else ''}. Hiding only changes this screen: "
                   "the field keeps its value and everything below keeps working.")
        level = "caution"
    else:
        verdict = f"{label} is used in {len(items)} place{'s' if len(items) != 1 else ''}. Check them below before you go ahead."
        level = "caution"
    return {"verdict": verdict, "level": level, "groups": out_groups, "total": len(items)}


# ----------------------------------------------------------------------------
# 2. Conditional required in plain words: records affected right now
# ----------------------------------------------------------------------------

def condition_domain(cond: dict[str, Any]) -> list[Any]:
    """Validated condition tree (view_engine_logic.validate_condition) -> Odoo domain."""
    parts: list[list[Any]] = []
    for r in cond["rules"]:
        f, op, v = r["field"], r["op"], r.get("value")
        if op in {"is_true"}:
            parts.append([(f, "=", True)])
        elif op == "is_false":
            parts.append([(f, "!=", True)])
        elif op == "set":
            parts.append([(f, "!=", False)])
        elif op == "not_set":
            parts.append([(f, "=", False)])
        elif op == "is":
            parts.append([(f, "=", v)])
        elif op == "is_not":
            parts.append([(f, "!=", v)])
        elif op == "in":
            parts.append([(f, "in", list(v or []))])
        elif op == "not_in":
            parts.append([(f, "not in", list(v or []))])
        elif op == "contains":
            parts.append([(f, "ilike", v)])
        elif op in vl.NUM_OPS:
            parts.append([(f, vl.NUM_OPS[op].replace("==", "="), v)])
    if not parts:
        return []
    joiner = "|" if cond.get("match") == "any" else "&"
    out: list[Any] = [joiner] * (len(parts) - 1)
    for p in parts:
        out.extend(p)
    return out


def empty_domain(field: str, meta: dict[str, Any]) -> list[Any]:
    t = meta.get("type")
    if t == "boolean":
        return [(field, "=", False)]
    if t in {"integer", "float", "monetary"}:
        return [(field, "=", 0)]
    return [(field, "=", False)]


def required_impact_text(label: str, sentence: str, matching: int, missing: int) -> str:
    if not matching:
        return f"No records match \"{sentence}\" right now, so nobody is affected today."
    if not missing:
        return f"All {matching:,} records where {sentence} already have {label}. Nobody is blocked."
    return (f"{missing:,} of {matching:,} records where {sentence} have no {label} yet. "
            f"They'll need it the next time someone saves them.")


# ----------------------------------------------------------------------------
# 3. What blocks saving, per stage (tri-state evaluation of Odoo expressions)
# ----------------------------------------------------------------------------

class _Unknown:
    pass


UNKNOWN = _Unknown()


def eval_expr(expr: str | None, known: dict[str, Any]) -> bool | None:
    """True / False when the expression only depends on known values, None when it
    depends on something else on the record (Kleene logic)."""
    raw = (expr or "").strip()
    if not raw:
        return False
    if raw in TRUE_WORDS:
        return True
    if raw in {"0", "False", "false"}:
        return False
    try:
        tree = ast.parse(raw, mode="eval")
    except SyntaxError:
        return None

    def val(n: ast.AST) -> Any:
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, (ast.List, ast.Tuple)):
            items = [val(e) for e in n.elts]
            return UNKNOWN if any(i is UNKNOWN for i in items) else items
        if isinstance(n, ast.Name):
            return known.get(n.id, UNKNOWN)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            return known.get(f"{n.value.id}.{n.attr}", UNKNOWN)
        return UNKNOWN

    def truth(n: ast.AST) -> bool | None:
        if isinstance(n, ast.BoolOp):
            res = [truth(v) for v in n.values]
            if isinstance(n.op, ast.And):
                if any(r is False for r in res):
                    return False
                return True if all(r is True for r in res) else None
            if any(r is True for r in res):
                return True
            return False if all(r is False for r in res) else None
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            t = truth(n.operand)
            return None if t is None else not t
        if isinstance(n, ast.Compare) and len(n.ops) == 1:
            a, b = val(n.left), val(n.comparators[0])
            if a is UNKNOWN or b is UNKNOWN:
                return None
            op = n.ops[0]
            try:
                if isinstance(op, ast.Eq):
                    return a == b
                if isinstance(op, ast.NotEq):
                    return a != b
                if isinstance(op, ast.In):
                    return a in b
                if isinstance(op, ast.NotIn):
                    return a not in b
                if isinstance(op, ast.Gt):
                    return a > b
                if isinstance(op, ast.GtE):
                    return a >= b
                if isinstance(op, ast.Lt):
                    return a < b
                if isinstance(op, ast.LtE):
                    return a <= b
            except TypeError:
                return None
            return None
        v = val(n)
        if v is UNKNOWN:
            return None
        return bool(v)

    return truth(tree.body)


def stage_attr_names(tree: dict[str, Any], stage_field: str) -> set[str]:
    """Attributes of the stage record that rules read (stage_id.is_won -> is_won)."""
    out: set[str] = set()
    rx = re.compile(rf"\b{re.escape(stage_field)}\.([a-z_][a-z0-9_]*)")
    for n, _p, _h in walk(tree):
        for attr in ("invisible", "required", "readonly"):
            out.update(rx.findall(str((n.get("attrs") or {}).get(attr) or "")))
    return out


def save_blockers(tree: dict[str, Any], fields: dict[str, Any], stage_field: str,
                  stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For each stage: fields that must be filled in before a record can be saved
    there. Always-required (model) / required at this stage / depends on other values."""
    out = []
    nodes = screen_field_nodes(tree)
    for st in stages:
        known: dict[str, Any] = {stage_field: st["value"]}
        for k, v in (st.get("attrs") or {}).items():
            known[f"{stage_field}.{k}"] = v
        always, at_stage, depends = [], [], []
        seen: set[str] = set()
        for n, hidden in nodes:
            name = n.get("name") or ""
            if name in seen or name == stage_field:
                continue
            meta = fields.get(name) or {}
            attrs = n.get("attrs") or {}
            invisible = True if hidden else eval_expr(attrs.get("invisible"), known)
            readonly_model = bool(meta.get("readonly"))
            entry = {"field": name, "label": n.get("label") or _label(fields, name), "node": n["id"]}
            if meta.get("required") is True and not readonly_model:
                seen.add(name)
                always.append({**entry, "why": "Odoo always needs it." + (" It's hidden here, so saving can fail." if invisible is True else "")})
                continue
            req_expr = attrs.get("required")
            if not req_expr:
                continue
            req = eval_expr(req_expr, known)
            if req is False or invisible is True:
                continue
            seen.add(name)
            if req is True:
                at_stage.append({**entry, "why": "Required on this screen at this stage."})
            else:
                sentence = vl.explain_expression(req_expr, fields) or "some other values on the record"
                depends.append({**entry, "why": f"Required when {sentence}."})
        out.append({"value": st["value"], "label": st["label"], "always": always, "at_stage": at_stage, "depends": depends})
    return out


def stage_choices(fields: dict[str, Any]) -> tuple[str | None, str | None]:
    """Which field moves a record through its steps: ('stage_id','many2one') or ('state','selection')."""
    for name in ("stage_id", "state"):
        meta = fields.get(name) or {}
        if name == "stage_id" and meta.get("type") == "many2one":
            return name, "many2one"
        if name == "state" and meta.get("type") == "selection" and meta.get("selection"):
            return name, "selection"
    return None, None


# ----------------------------------------------------------------------------
# 4. Usage heatmap (counts only)
# ----------------------------------------------------------------------------

def heat_levels(counts: dict[str, int], total: int, changes: dict[str, int] | None, days: int) -> dict[str, dict[str, Any]]:
    """field -> {level 0-4, fill %, changes, label}. Level mixes how often a field
    is filled with how often people change it (tracked fields only)."""
    out: dict[str, dict[str, Any]] = {}
    changes = changes or {}
    top_change = max(changes.values(), default=0)
    for name, c in counts.items():
        rate = round(100 * c / total) if total else 0
        ch = changes.get(name, 0)
        score = rate / 100
        if top_change:
            score = 0.6 * score + 0.4 * (ch / top_change)
        level = 0 if score < 0.05 else 1 if score < 0.25 else 2 if score < 0.5 else 3 if score < 0.8 else 4
        bits = [f"Filled on {rate}% of {total:,}"]
        if name in changes:
            bits.append(f"changed {ch:,} time{'s' if ch != 1 else ''} in the last {days} days")
        out[name] = {"level": level, "rate": rate, "count": c, "changes": changes.get(name), "label": ", ".join(bits)}
    return out


# ----------------------------------------------------------------------------
# 5. Labelled sample data (never written to Odoo, never presented as real)
# ----------------------------------------------------------------------------

SAMPLE_NOTE = "Sample values, made up for the preview. Nothing here comes from your database."


def sample_value(name: str, meta: dict[str, Any], i: int) -> Any:
    t = meta.get("type")
    label = str(meta.get("string") or name)
    if t == "boolean":
        return i % 2 == 0
    if t in {"integer"}:
        return [3, 12, 0][i % 3]
    if t in {"float", "monetary"}:
        return [1250.0, 89.5, 0.0][i % 3]
    if t == "date":
        return (date(2026, 1, 15) + timedelta(days=30 * i)).isoformat()
    if t == "datetime":
        return (datetime(2026, 1, 15, 9, 30) + timedelta(days=30 * i)).strftime("%Y-%m-%d %H:%M")
    if t == "selection":
        sel = meta.get("selection") or []
        return sel[i % len(sel)][1] if sel else None
    if t == "many2one":
        return f"Sample {label.lower()} {i + 1}"
    if t in {"many2many", "one2many"}:
        return f"{i + 1} sample item{'s' if i else ''}"
    if t in {"binary", "html", "properties", "json"}:
        return None
    if t == "text":
        return f"Sample notes for {label.lower()}."
    if "email" in name:
        return f"sample{i + 1}@example.com"
    if "phone" in name or "mobile" in name:
        return f"+000 000 000 00{i + 1}"
    return f"Sample {label.lower()} {i + 1}"


def sample_records(names: list[str], fields: dict[str, Any], count: int = 3) -> list[dict[str, Any]]:
    out = []
    for i in range(max(1, min(count, 5))):
        rec: dict[str, Any] = {"id": -(i + 1), "display_name": f"Sample record {i + 1}", "__sample": True}
        for n in names:
            rec[n] = sample_value(n, fields.get(n) or {}, i)
        out.append(rec)
    return out


# ----------------------------------------------------------------------------
# 6. Accessibility simulator
# ----------------------------------------------------------------------------

def a11y_report(tree: dict[str, Any], fields: dict[str, Any], root_tag: str) -> dict[str, Any]:
    """What a screen reader announces, in order; keyboard (tab) order; issues with fixes."""
    order: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    labels_for: set[str] = set()
    for n, _p, _h in walk(tree):
        if n.get("tag") == "label" and (n.get("attrs") or {}).get("for"):
            labels_for.add(str(n["attrs"]["for"]))
    for n, parent, hidden in walk(tree):
        if hidden or n.get("helper"):
            continue
        attrs = n.get("attrs") or {}
        tag = n.get("tag")
        if tag == "page":
            order.append({"node": n["id"], "say": f"Tab, {attrs.get('string') or n.get('label') or 'untitled'}", "focus": True})
        elif tag == "group" and attrs.get("string"):
            order.append({"node": n["id"], "say": f"Section, {attrs['string']}", "focus": False})
        elif tag == "separator":
            order.append({"node": n["id"], "say": f"Heading, {attrs.get('string') or n.get('label') or ''}".strip(", "), "focus": False})
        elif tag == "button":
            text = (attrs.get("string") or "").strip()
            if not text:
                issues.append({"node": n["id"], "kind": "button_no_text",
                               "text": "A button shows only an icon. Unless it has hover text, a screen reader says only \"button\".",
                               "fix_label": "Give it a label", "fix": {"op": "set_attr", "node": n["id"], "attr": "string"}})
            order.append({"node": n["id"], "say": f"Button, {text or 'no name'}", "focus": True})
        elif tag == "field" and str(n.get("id", "")).startswith("field:"):
            name = n.get("name") or ""
            meta = fields.get(name) or {}
            nolabel = str(attrs.get("nolabel") or "") in TRUE_WORDS
            label = n.get("label") or _label(fields, name)
            in_group = bool(parent and parent.get("tag") == "group")
            has_label = (in_group and not nolabel) or name in labels_for
            req = str(attrs.get("required") or "") in TRUE_WORDS or meta.get("required") is True
            ro = str(attrs.get("readonly") or "") in TRUE_WORDS or bool(meta.get("readonly"))
            if not has_label and root_tag == "form":
                if attrs.get("placeholder"):
                    issues.append({"node": n["id"], "kind": "placeholder_label",
                                   "text": f"{label} uses its hint text as its only label. The hint disappears while typing.",
                                   "fix_label": "Show a label", "fix": {"op": "set_attr", "node": n["id"], "attr": "nolabel", "value": "0"}})
                elif root_tag == "form" and parent and parent.get("tag") != "div":
                    issues.append({"node": n["id"], "kind": "no_label", "text": f"{label} has no visible label, so it's announced without a name.",
                                   "fix_label": "Show a label", "fix": {"op": "set_attr", "node": n["id"], "attr": "nolabel", "value": "0"}})
            say = f"{label}, {_kind_word(meta.get('type'))}" + (", required" if req else "") + (", read only" if ro else "")
            order.append({"node": n["id"], "say": say, "focus": not ro})
    # Colour-only signals on lists
    root_attrs = tree.get("attrs") or {}
    if root_tag in {"list", "tree"}:
        decos = [k for k in root_attrs if k.startswith("decoration-")]
        if decos:
            issues.append({"node": tree["id"], "kind": "colour_only", "text": "Rows change colour to show meaning, with no words. People who can't tell colours apart miss it.",
                           "fix_label": None, "fix": None, "detail": "Add a status column so the meaning is also written."})
    if root_tag == "form":
        pages = [n for n, _p, h in walk(tree) if n.get("tag") == "page" and not h]
        if len(pages) > 7:
            issues.append({"node": tree["id"], "kind": "many_tabs", "text": f"{len(pages)} tabs. Keyboard users press Tab through every one.",
                           "fix_label": None, "fix": None})
    focus = [o for o in order if o["focus"]]
    return {"reading_order": order, "tab_order": [{"node": o["node"], "say": o["say"], "n": i + 1} for i, o in enumerate(focus)],
            "issues": issues, "summary": (f"{len(issues)} thing{'s' if len(issues) != 1 else ''} to fix for people using a screen reader or keyboard."
                                          if issues else "No problems found for screen readers or keyboard use.")}


def _kind_word(t: str | None) -> str:
    return {"char": "text box", "text": "text area", "html": "text editor", "integer": "number", "float": "number",
            "monetary": "amount", "boolean": "checkbox", "selection": "choice list", "many2one": "pick one",
            "many2many": "tags", "one2many": "table", "date": "date", "datetime": "date and time", "binary": "file"}.get(t or "", "field")


# ----------------------------------------------------------------------------
# 7. Industry starter screens (only fields this database really has)
# ----------------------------------------------------------------------------

STARTERS: dict[str, dict[str, Any]] = {
    "retail": {"label": "Retail shop", "models": {
        "product.template": [("Selling", ["name", "list_price", "taxes_id", "barcode", "default_code", "categ_id"]),
                             ("Stock", ["type", "is_storable", "qty_available", "uom_id"]),
                             ("Point of sale", ["available_in_pos", "pos_categ_ids", "to_weight"])],
        "res.partner": [("Customer", ["name", "phone", "mobile", "email", "barcode"]),
                        ("Loyalty", ["category_id", "property_product_pricelist"])]}},
    "distribution": {"label": "Wholesale and distribution", "models": {
        "product.template": [("Product", ["name", "default_code", "barcode", "categ_id", "uom_id", "uom_po_id"]),
                             ("Buying", ["seller_ids", "standard_price", "purchase_method"]),
                             ("Selling", ["list_price", "taxes_id", "invoice_policy"]),
                             ("Logistics", ["weight", "volume", "route_ids", "tracking"])],
        "res.partner": [("Company", ["name", "vat", "street", "city", "country_id"]),
                        ("Trading terms", ["property_payment_term_id", "property_supplier_payment_term_id", "credit_limit", "property_product_pricelist"]),
                        ("Contacts", ["phone", "email", "user_id"])],
        "sale.order": [("Order", ["partner_id", "date_order", "validity_date", "payment_term_id", "pricelist_id"]),
                       ("Delivery", ["warehouse_id", "picking_policy", "commitment_date"])]}},
    "services": {"label": "Services and consulting", "models": {
        "res.partner": [("Client", ["name", "email", "phone", "website", "industry_id"]),
                        ("Billing", ["vat", "property_payment_term_id", "lang"])],
        "crm.lead": [("Opportunity", ["name", "partner_id", "expected_revenue", "probability", "date_deadline"]),
                     ("Follow-up", ["user_id", "team_id", "tag_ids", "source_id"])],
        "product.template": [("Service", ["name", "type", "list_price", "uom_id", "service_policy", "service_tracking"])]}},
    "manufacturing": {"label": "Manufacturing", "models": {
        "product.template": [("Product", ["name", "default_code", "categ_id", "uom_id"]),
                             ("Making it", ["route_ids", "bom_ids", "produce_delay", "tracking"]),
                             ("Costs", ["standard_price", "list_price"])],
        "res.partner": [("Supplier", ["name", "vat", "phone", "email"]),
                        ("Terms", ["property_supplier_payment_term_id", "property_purchase_currency_id"])]}},
}


def starter_options(model: str, fields: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key, s in STARTERS.items():
        sections = s["models"].get(model)
        if not sections:
            continue
        have = [f for _t, fs in sections for f in fs if f in fields]
        missing = [f for _t, fs in sections for f in fs if f not in fields]
        out.append({"key": key, "label": s["label"], "fields_found": len(have), "fields_missing": len(missing),
                    "missing_labels": missing, "available": len(have) >= 3})
    return out


def starter_arch(key: str, model: str, fields: dict[str, Any], major: int, label: str) -> tuple[str, list[str], list[str]]:
    s = STARTERS.get(key)
    sections = (s or {}).get("models", {}).get(model)
    if not sections:
        raise EngineError("There's no starter screen for that industry on this record type.")
    esc = lambda t: (t or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")  # noqa: E731
    title = "name" if "name" in fields else next(iter(sorted(fields)), "id")
    used, missing = [], []
    pages = []
    for idx, (sec_title, names) in enumerate(sections):
        present = [n for n in names if n in fields and n != title and fields[n].get("type") not in {"properties"}]
        missing.extend(n for n in names if n not in fields)
        if not present:
            continue
        used.extend(present)
        inner = "".join(f'<field name="{n}"/>' for n in present)
        slug = re.sub(r"[^a-z0-9]+", "_", sec_title.lower()).strip("_")
        pages.append(f'<page name="ingenium_starter_{slug}_{idx}" string="{esc(sec_title)}"><group name="ingenium_starter_{slug}_{idx}_g">{inner}</group></page>')
    if not pages:
        raise EngineError("None of that starter's fields exist in this database.")
    chatter = ""
    if "message_ids" in fields:
        chatter = "<chatter/>" if major >= 18 else ('<div class="oe_chatter">' + "".join(
            f'<field name="{f}"/>' for f in ("message_follower_ids", "activity_ids", "message_ids") if f in fields) + "</div>")
    arch = (f'<form string="{esc(label)}"><sheet><div class="oe_title" name="ingenium_starter_title"><h1><field name="{title}"/></h1></div>'
            f'<notebook name="ingenium_starter_tabs">{"".join(pages)}</notebook></sheet>{chatter}</form>')
    return arch, used, missing


# ----------------------------------------------------------------------------
# 8. Explain this screen (code writes every sentence from the tree)
# ----------------------------------------------------------------------------

def explain_steps(tree: dict[str, Any], fields: dict[str, Any], model_label: str, group_names: dict[str, str]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    all_fields = [n for n, h in screen_field_nodes(tree) if not h]
    pages = [n for n, _p, h in walk(tree) if n.get("tag") == "page" and not h]
    buttons = [n for n, _p, h in walk(tree) if n.get("tag") == "button" and not h]
    status = next((n for n, _p, h in walk(tree) if n.get("tag") == "field" and (n.get("attrs") or {}).get("widget") == "statusbar"), None)
    intro = f"This is the {model_label} screen. It shows {len(all_fields)} field{'s' if len(all_fields) != 1 else ''}"
    intro += f" on {len(pages)} tab{'s' if len(pages) != 1 else ''}." if pages else "."
    steps.append({"node": tree["id"], "title": "Overview", "text": intro})
    if status:
        steps.append({"node": status["id"], "title": "Where the record is",
                      "text": f"The bar at the top shows the {status.get('label') or 'stage'}. Records move along it from left to right."})
    if buttons:
        names = [b.get("label") or (b.get("attrs") or {}).get("string") for b in buttons]
        names = [x for x in names if x][:6]
        if names:
            steps.append({"node": buttons[0]["id"], "title": "Actions",
                          "text": "Buttons you may see: " + ", ".join(names) + ". Some only appear at certain stages."})
    for n, _parent, hidden in walk(tree):
        if hidden or n.get("tag") not in {"group", "page"}:
            continue
        title = (n.get("attrs") or {}).get("string") or ""
        if n.get("tag") == "group" and not title:
            continue
        flds = [c for c, _pp, hh in walk(n) if c.get("tag") == "field" and str(c.get("id", "")).startswith("field:") and not hh and not c.get("helper")]
        if not flds:
            continue
        names = ", ".join((f.get("label") or f.get("name") or "") for f in flds[:6]) + ("…" if len(flds) > 6 else "")
        steps.append({"node": n["id"], "title": title or "Section", "text": f"{'Tab' if n.get('tag') == 'page' else 'Section'} with {len(flds)} field{'s' if len(flds) != 1 else ''}: {names}."})
    rules = []
    for n in all_fields:
        for attr, sentence in (n.get("rules") or {}).items():
            if attr in {"invisible", "required", "readonly"} and sentence and "too complex" not in sentence:
                rules.append((n, sentence))
    for n, sentence in rules[:8]:
        steps.append({"node": n["id"], "title": n.get("label") or "Rule", "text": f"{n.get('label')}: {sentence}"})
    limited = [n for n in all_fields if (n.get("attrs") or {}).get("groups")]
    if limited:
        who = sorted({group_names.get(g.strip().lstrip("!"), g.strip()) for n in limited for g in str(n["attrs"]["groups"]).split(",") if g.strip()})
        steps.append({"node": limited[0]["id"], "title": "Not everyone sees everything",
                      "text": f"{len(limited)} field{'s are' if len(limited) != 1 else ' is'} limited to some roles ({', '.join(who[:4])})."})
    req = [n for n in all_fields if str((n.get("attrs") or {}).get("required") or "") in TRUE_WORDS or (fields.get(n.get("name") or "") or {}).get("required") is True]
    if req:
        steps.append({"node": req[0]["id"], "title": "Must be filled in",
                      "text": "These fields must be filled in before saving: " + ", ".join(r.get("label") or "" for r in req[:8]) + "."})
    return steps


# ----------------------------------------------------------------------------
# 9 / 17. Role-scoped layers: step-by-step mode and layout comparison tests
# ----------------------------------------------------------------------------

STEPS_PREFIX = f"{LAYER_PREFIX}_steps"
TEST_PREFIX = f"{LAYER_PREFIX}_abtest"
SCOPED_PRIORITY = 995  # after the main Ingenium layer (990)


def scoped_layer_name(prefix: str, model: str, view_type: str, base_view_id: int, role: str) -> str:
    return f"{prefix}_{model.replace('.', '_')}_{view_type}_{base_view_id}_{role.replace('.', '_')}"


def step_candidates(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """Top-level sections of a form in reading order: groups under the sheet and
    tabs of the first notebook. Each can become one step. ``move`` lists what is
    moved into the step (a group itself, or the contents of a tab)."""
    sheet = next((n for n, _p, _h in walk(tree) if n.get("tag") == "sheet"), None)
    if not sheet:
        return []
    out = []
    for c in sheet.get("children") or []:
        attrs = c.get("attrs") or {}
        if str(attrs.get("invisible") or "") in TRUE_WORDS:
            continue
        if c.get("tag") == "group" and c.get("anchor"):
            flds = [x for x, _p, h in walk(c) if x.get("tag") == "field" and not h and not x.get("helper")]
            if flds:
                out.append({"node": c["id"], "kind": "group", "anchor": c["anchor"], "label": attrs.get("string") or _first_labels(flds),
                            "fields": len(flds), "move": [c["anchor"]], "field_names": [x.get("name") for x in flds if x.get("name")]})
        elif c.get("tag") == "notebook" and c.get("anchor"):
            for p in c.get("children") or []:
                if p.get("tag") != "page" or str((p.get("attrs") or {}).get("invisible") or "") in TRUE_WORDS or not p.get("anchor"):
                    continue
                kids = [k for k in p.get("children") or [] if k.get("anchor")]
                if len(kids) != len(p.get("children") or []) or not kids:
                    continue  # something inside can't be targeted safely
                flds = [x for x, _pp, h in walk(p) if x.get("tag") == "field" and not h and not x.get("helper")]
                out.append({"node": p["id"], "kind": "page", "anchor": p["anchor"], "label": (p.get("attrs") or {}).get("string") or p.get("label") or "Tab",
                            "fields": len(flds), "notebook_anchor": c["anchor"], "move": [k["anchor"] for k in kids],
                            "field_names": [x.get("name") for x in flds if x.get("name")]})
    return out


def _first_labels(flds: list[dict[str, Any]]) -> str:
    names = [f.get("label") or f.get("name") or "" for f in flds[:2]]
    return " and ".join(n for n in names if n) or "Details"


def steps_layer_arch(steps: list[dict[str, Any]]) -> str:
    """One notebook of 'Step n: ...' tabs placed where the first chosen section
    was; each section is moved (not copied), so nothing appears twice. Tabs
    emptied by the move are hidden."""
    if len(steps) < 2:
        raise EngineError("Pick at least two sections to make steps.")
    if len(steps) > 10:
        raise EngineError("Use at most 10 steps.")
    data = ET.Element("data")
    first = steps[0]
    pos_anchor = first.get("anchor") if first["kind"] == "group" else first.get("notebook_anchor")
    if not pos_anchor:
        raise EngineError("Those sections can't be targeted safely.")
    spec = ET.SubElement(data, "xpath", {"expr": pos_anchor, "position": "before"})
    nb = ET.SubElement(spec, "notebook", {"name": f"{STEPS_PREFIX}_notebook"})
    for i, st in enumerate(steps, start=1):
        label = re.sub(r"\s+", " ", str(st.get("label") or "Step")).strip()[:60]
        ET.SubElement(nb, "page", {"name": f"{STEPS_PREFIX}_{i}", "string": f"Step {i}: {label}"})
    for i, st in enumerate(steps, start=1):
        moves = st.get("move") or []
        if not moves:
            raise EngineError(f"'{st.get('label')}' can't be targeted safely.")
        inner = ET.SubElement(data, "xpath", {"expr": f"//page[@name='{STEPS_PREFIX}_{i}']", "position": "inside"})
        for a in moves:
            ET.SubElement(inner, "xpath", {"expr": a, "position": "move"})
    for st in steps:
        if st["kind"] == "page":
            h = ET.SubElement(data, "xpath", {"expr": st["anchor"], "position": "attributes"})
            ET.SubElement(h, "attribute", {"name": "invisible"}).text = "1"
    return ET.tostring(data, encoding="unicode")


def role_variant_arch(raw_a: str, raw_b: str, role: str) -> str:
    """Odoo 17+ refuses extension layers that carry groups on the record, so a
    role-only layout is written with groups *inside* the layer: each top-level
    part of the screen that differs gets ``groups="!role"`` on the normal
    version and a copy of the new version with ``groups="role"``. Odoo removes
    the part a person isn't allowed to see before the screen is sent, so each
    person gets exactly one version."""
    if not re.fullmatch(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+", role or ""):
        raise EngineError("Pick a role.")
    a, b = ET.fromstring(raw_a), ET.fromstring(raw_b)
    ka, kb = list(a), list(b)
    if a.tag != b.tag or [k.tag for k in ka] != [k.tag for k in kb]:
        raise EngineError("The new layout changes the outline of the screen, so it can't be limited to one role.")
    data = ET.Element("data")
    changed = 0
    for i in range(len(ka), 0, -1):  # from the end, so earlier positions don't shift
        ca, cb = ka[i - 1], kb[i - 1]
        if ET.tostring(ca) == ET.tostring(cb):
            continue
        if ca.get("groups") or cb.get("groups"):
            raise EngineError("That part of the screen is already limited to some roles, so a role-only version can't be added safely.")
        if [k.tag for k in ka].count(ca.tag) != 1:
            raise EngineError("That part of the screen can't be told apart from a similar one, so it can't be limited to one role.")
        expr = f"/{a.tag}/{ca.tag}"
        copy = copy_mod.deepcopy(cb)
        copy.set("groups", role)
        copy.tail = None
        hide = ET.SubElement(data, "xpath", {"expr": expr, "position": "attributes"})
        ET.SubElement(hide, "attribute", {"name": "groups"}).text = f"!{role}"
        after = ET.SubElement(data, "xpath", {"expr": expr, "position": "after"})  # first match = the normal version
        after.append(copy)
        changed += 1
    if not changed:
        raise EngineError("The new layout is the same as the current one.")
    return ET.tostring(data, encoding="unicode")


def role_differences(vis_a: dict[str, dict[str, Any]], vis_b: dict[str, dict[str, Any]], labels: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    only_a, only_b = [], []
    for nid in sorted(set(vis_a) | set(vis_b)):
        a = (vis_a.get(nid) or {}).get("visible", False)
        b = (vis_b.get(nid) or {}).get("visible", False)
        if a and not b:
            only_a.append({"node": nid, "label": labels.get(nid, nid), "why_not": str((vis_b.get(nid) or {}).get("reason") or "")})
        elif b and not a:
            only_b.append({"node": nid, "label": labels.get(nid, nid), "why_not": str((vis_a.get(nid) or {}).get("reason") or "")})
    return {"only_a": only_a, "only_b": only_b}


def proportion_test(x1: int, n1: int, x2: int, n2: int) -> dict[str, Any]:
    """Two-proportion z-test, explained in plain words."""
    if n1 < 30 or n2 < 30:
        return {"verdict": "too_few", "text": f"Too few new records to tell yet ({n1} and {n2}; at least 30 each needed).", "p": None}
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) if 0 < p < 1 else 0
    if not se:
        return {"verdict": "same", "text": "Both groups behave the same.", "p": 1.0}
    z = (p1 - p2) / se
    pval = math.erfc(abs(z) / math.sqrt(2))
    if pval < 0.05:
        better = "A" if p1 > p2 else "B"
        return {"verdict": better, "text": f"Layout {better} gets this field filled more often ({round(100 * p1)}% vs {round(100 * p2)}%), and the difference is unlikely to be chance.", "p": round(pval, 4)}
    return {"verdict": "unclear", "text": f"{round(100 * p1)}% vs {round(100 * p2)}%: no clear difference yet.", "p": round(pval, 4)}


# ----------------------------------------------------------------------------
# 10. Dashboard designer (graph / pivot screens)
# ----------------------------------------------------------------------------

GROUPABLE = {"many2one", "selection", "date", "datetime", "char", "boolean"}
MEASURABLE = {"integer", "float", "monetary"}
CHARTS = {"bar", "line", "pie"}
INTERVALS = {"day", "week", "month", "quarter", "year"}


def measure_options(fields: dict[str, Any]) -> list[dict[str, str]]:
    return sorted(({"name": n, "label": _label(fields, n), "type": str(m.get("type"))} for n, m in fields.items()
                   if m.get("type") in MEASURABLE and m.get("store") is not False and n not in {"id", "sequence"}),
                  key=lambda x: x["label"].lower())


def groupby_options(fields: dict[str, Any]) -> list[dict[str, str]]:
    return sorted(({"name": n, "label": _label(fields, n), "type": str(m.get("type"))} for n, m in fields.items()
                   if m.get("type") in GROUPABLE and m.get("store") is not False and not n.startswith("message_")
                   and n not in {"display_name", "__last_update"}), key=lambda x: x["label"].lower())


def validate_dashboard(spec: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    kind = spec.get("kind")
    if kind not in {"graph", "pivot"}:
        raise EngineError("Choose a chart or a pivot table.")
    meas = {m["name"] for m in measure_options(fields)}
    grp = {g["name"] for g in groupby_options(fields)}
    measures = [m for m in (spec.get("measures") or []) if m != "__count"]
    for m in measures:
        if m not in meas:
            raise EngineError(f"'{m}' can't be added up.")
    rows = list(spec.get("rows") or [])
    cols = list(spec.get("cols") or []) if kind == "pivot" else []
    for g in rows + cols:
        if g not in grp:
            raise EngineError(f"Records can't be grouped by '{g}'.")
    if not rows:
        raise EngineError("Pick what to group by.")
    if len(rows) > 3 or len(cols) > 2 or len(measures) > 4:
        raise EngineError("Use at most 3 row groups, 2 column groups and 4 numbers.")
    interval = spec.get("interval") or "month"
    if interval not in INTERVALS:
        raise EngineError("Pick day, week, month, quarter or year.")
    chart = spec.get("chart") or "bar"
    if kind == "graph" and chart not in CHARTS:
        raise EngineError("Pick a bar, line or pie chart.")
    return {"kind": kind, "measures": measures, "rows": rows, "cols": cols, "interval": interval, "chart": chart,
            "stacked": bool(spec.get("stacked"))}


def dashboard_arch(spec: dict[str, Any], fields: dict[str, Any], label: str) -> str:
    esc = lambda t: (t or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")  # noqa: E731
    parts = []

    def grp(name: str, typ: str) -> str:
        t = (fields.get(name) or {}).get("type")
        iv = f' interval="{spec["interval"]}"' if t in {"date", "datetime"} else ""
        return f'<field name="{name}" type="{typ}"{iv}/>'

    for r in spec["rows"]:
        parts.append(grp(r, "row"))
    for c in spec["cols"]:
        parts.append(grp(c, "col"))
    for m in spec["measures"]:
        parts.append(f'<field name="{m}" type="measure"/>')
    if spec["kind"] == "graph":
        stacked = ' stacked="1"' if spec["stacked"] and spec["chart"] == "bar" else ""
        return f'<graph string="{esc(label)}" type="{spec["chart"]}"{stacked} sample="1">{"".join(parts)}</graph>'
    return f'<pivot string="{esc(label)}" sample="1">{"".join(parts)}</pivot>'


# ----------------------------------------------------------------------------
# 12. Email client and dark-mode checks
# ----------------------------------------------------------------------------

GMAIL_CLIP_BYTES = 102 * 1024


def email_checks(html: str) -> dict[str, Any]:
    """Code checks against what common email apps are known to do. Each finding
    says which apps and what to do."""
    findings: list[dict[str, str]] = []
    raw = html or ""
    low = raw.lower()

    def add(sev: str, apps: str, text: str, fix: str) -> None:
        findings.append({"severity": sev, "apps": apps, "text": text, "fix": fix})

    size = len(raw.encode("utf-8"))
    if size > GMAIL_CLIP_BYTES:
        add("high", "Gmail", f"The email is {size // 1024} KB. Gmail cuts emails over 102 KB and hides the rest behind a link.",
            "Remove large blocks or long tables.")
    for m in re.finditer(r"<img\b[^>]*>", raw, re.I):
        tag = m.group(0)
        if not re.search(r"\balt\s*=", tag, re.I):
            add("medium", "All apps when pictures are blocked, screen readers", "A picture has no description, so people see nothing when pictures are blocked.",
                "Add a short description to the picture.")
            break
    widths = [int(w) for w in re.findall(r"width\s*[:=]\s*\"?(\d{3,4})(?:px)?", low)]
    if any(w > 640 for w in widths):
        add("medium", "Phones, Outlook", f"Something is {max(widths)} px wide. Most email layouts stay within 600 px.",
            "Use a 600 px wide content area.")
    if re.search(r"display\s*:\s*(flex|grid)", low):
        add("high", "Outlook on Windows", "The layout uses flexible boxes or grids, which Outlook on Windows ignores. Columns fall on top of each other.",
            "Use simple tables for columns.")
    if re.search(r"position\s*:\s*(absolute|fixed)", low):
        add("high", "Gmail, Outlook", "Some parts are placed with exact positions, which most email apps remove.", "Let content flow top to bottom.")
    if "background-image" in low or re.search(r"\bbackground\s*=", low):
        add("medium", "Outlook on Windows", "A background picture won't show in Outlook on Windows.", "Use a solid background colour behind the text too.")
    if re.search(r"<(script|form|iframe)\b", low):
        add("high", "All apps", "The email contains scripts, forms or embedded pages. Email apps remove them and may mark the email as spam.",
            "Use a link to a page instead.")
    if re.search(r"<link\b[^>]*stylesheet", low):
        add("medium", "Gmail, Outlook", "Styles are loaded from another file, which email apps don't load.", "Put styles directly on the elements.")
    if re.search(r'href\s*=\s*"http://', low):
        add("low", "All apps", "A link uses http:// instead of https://. Some apps warn people before opening it.", "Use https:// links.")
    if "border-radius" in low:
        add("low", "Outlook on Windows", "Rounded corners show as square corners in Outlook on Windows.", "No action needed; it still reads well.")
    # Dark mode: text colour set without a background (or the reverse) can become unreadable when the app inverts colours.
    dark_risk = 0
    for style in re.findall(r'style\s*=\s*"([^"]*)"', raw, re.I):
        s = style.lower()
        has_color = re.search(r"(?<!background-)color\s*:\s*(#[0-9a-f]{3,6}|rgb|black|white)", s)
        has_bg = re.search(r"background(-color)?\s*:\s*(#[0-9a-f]{3,6}|rgb|white|black)", s)
        if bool(has_color) != bool(has_bg):
            dark_risk += 1
    if dark_risk:
        add("medium", "Dark mode in Apple Mail, Outlook, Gmail apps",
            f"{dark_risk} place{'s set' if dark_risk != 1 else ' sets'} a text colour without a background colour (or the other way round). In dark mode the app may swap only one of them, making text hard to read.",
            "Set both a text colour and a background colour together.")
    if not re.search(r"color-scheme|prefers-color-scheme", low):
        add("low", "Apple Mail, Outlook for Mac", "The email doesn't say how it should look in dark mode, so each app decides on its own.",
            "No action needed for most emails; check the dark preview.")
    score = 100 - sum({"high": 20, "medium": 8, "low": 2}[f["severity"]] for f in findings)
    return {"findings": findings, "score": max(0, score), "size_kb": round(size / 1024, 1),
            "summary": "Looks fine in common email apps." if not findings else f"{len(findings)} thing{'s' if len(findings) != 1 else ''} to check before sending."}


# ----------------------------------------------------------------------------
# 13-16. Approvals, scheduled publish, post-publish watch, weekly digest
# ----------------------------------------------------------------------------

WATCH_SCHEDULE_MIN = [5, 60, 24 * 60]


def watch_due_times(start: datetime) -> list[str]:
    return [(start + timedelta(minutes=m)).isoformat() for m in WATCH_SCHEDULE_MIN]


def parse_when(text: str, now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EngineError("Pick a date and time.") from exc
    if when.tzinfo is None:
        raise EngineError("The time needs a time zone.")
    if when < now + timedelta(seconds=20):
        raise EngineError("Pick a time at least a minute from now.")
    if when > now + timedelta(days=60):
        raise EngineError("Schedule at most 60 days ahead.")
    return when.astimezone(UTC)


def digest_payload(versions: list[dict[str, Any]], approvals: list[dict[str, Any]], schedules: list[dict[str, Any]],
                   watch_alerts: list[dict[str, Any]], days: int, db_label: str) -> dict[str, Any]:
    by_screen: dict[str, dict[str, Any]] = {}
    for v in versions:
        key = f"{v.get('model')} · {v.get('view_type')}"
        s = by_screen.setdefault(key, {"screen": key, "publish": 0, "undo": 0, "other": 0, "last": None, "what": []})
        act = str(v.get("action") or "")
        if act in {"publish", "import", "fix", "restore"}:
            s["publish"] += 1
        elif act in {"undo", "remove"}:
            s["undo"] += 1
        else:
            s["other"] += 1
        s["last"] = max(filter(None, [s["last"], v.get("created_at")]), default=None)
        for w in (v.get("summary") or [])[:3]:
            if w not in s["what"] and len(s["what"]) < 6:
                s["what"].append(str(w))
    screens = sorted(by_screen.values(), key=lambda s: -(s["publish"] + s["undo"]))
    total_pub = sum(s["publish"] for s in screens)
    total_undo = sum(s["undo"] for s in screens)
    pending = [a for a in approvals if a.get("status") == "pending"]
    upcoming = [s for s in schedules if s.get("status") == "scheduled"]
    lines = [f"Screen changes in {db_label}, last {days} days"]
    if not screens:
        lines.append("No screens were changed.")
    else:
        lines.append(f"{total_pub} publish{'es' if total_pub != 1 else ''} and {total_undo} undo{'s' if total_undo != 1 else ''} on {len(screens)} screen{'s' if len(screens) != 1 else ''}.")
        for s in screens[:10]:
            lines.append(f"- {s['screen']}: {s['publish']} published, {s['undo']} undone" + (f" ({'; '.join(s['what'][:3])})" if s["what"] else ""))
    if pending:
        lines.append(f"{len(pending)} change{'s are' if len(pending) != 1 else ' is'} waiting for approval.")
    if upcoming:
        lines.append(f"{len(upcoming)} change{'s are' if len(upcoming) != 1 else ' is'} scheduled to publish.")
    if watch_alerts:
        lines.append(f"{len(watch_alerts)} screen{'s' if len(watch_alerts) != 1 else ''} had a problem after publishing:")
        for a in watch_alerts[:5]:
            lines.append(f"- {a.get('screen')}: {a.get('problem')}")
    return {"screens": screens, "published": total_pub, "undone": total_undo, "pending_approvals": len(pending),
            "scheduled": len(upcoming), "alerts": watch_alerts[:20], "text": "\n".join(lines)}


# ----------------------------------------------------------------------------
# 18. Report from a photo or PDF (AI proposes, code maps)
# ----------------------------------------------------------------------------

DOC_BLOCK_KINDS = {"heading", "field", "label_field", "text", "divider", "o2m_table"}


def pdf_text_lines(raw: bytes, max_lines: int = 200) -> list[str]:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    lines: list[str] = []
    for page in reader.pages[:3]:
        for ln in (page.extract_text() or "").splitlines():
            t = re.sub(r"\s+", " ", ln).strip()
            if t:
                lines.append(t[:160])
            if len(lines) >= max_lines:
                return lines
    return lines


def validate_doc_proposal(raw: Any, fields: dict[str, Any], line_fields: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep only blocks whose fields exist on the report's record type (and on its
    line type for tables). Everything else is listed as 'not in your database'."""
    blocks: list[dict[str, Any]] = []
    dropped: list[str] = []
    items = (raw or {}).get("blocks") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return [], ["The document could not be read."]
    for b in items[:40]:
        if not isinstance(b, dict):
            continue
        kind = str(b.get("kind") or "")
        if kind == "divider":
            blocks.append({"type": "divider"})
            continue
        if kind not in DOC_BLOCK_KINDS:
            continue
        label = re.sub(r"[<>{}]", "", str(b.get("label") or "")).strip()[:80]
        if kind in {"field", "label_field"}:
            f = str(b.get("field") or "")
            if f not in fields:
                dropped.append(f"{label or f}: no matching field")
                continue
            blocks.append({"type": kind, "field": f, **({"label": label or _label(fields, f)} if kind == "label_field" else {})})
        elif kind == "o2m_table":
            f = str(b.get("field") or "")
            meta = fields.get(f) or {}
            if meta.get("type") != "one2many":
                dropped.append(f"{label or 'Table'}: no matching list of lines")
                continue
            cols = [c for c in (b.get("columns") or []) if isinstance(c, str) and (line_fields is None or c in line_fields)]
            missing = [c for c in (b.get("columns") or []) if isinstance(c, str) and line_fields is not None and c not in line_fields]
            dropped.extend(f"Column {c}: no matching field" for c in missing)
            if not cols:
                dropped.append(f"{label or 'Table'}: none of its columns match")
                continue
            if label:
                blocks.append({"type": "heading", "text": label, "level": 4})
            blocks.append({"type": "line_table", "field": f, "columns": [{"field": c} for c in cols[:8]]})
        elif kind == "heading":
            if label:
                blocks.append({"type": "heading", "text": label, "level": 3})
        elif kind == "text":
            if label:
                blocks.append({"type": "text", "text": label})
        elif kind == "divider":
            blocks.append({"type": "divider"})
    return blocks, dropped


# ----------------------------------------------------------------------------
# 19. Live co-editing (in-memory rooms per API process)
# ----------------------------------------------------------------------------

COEDIT_TTL = 30.0
COEDIT_MAX_OPS = 400


def merge_coedit(room: dict[str, Any], editor: str, name: str, selected: str | None, since: int,
                 new_ops: list[dict[str, Any]], base_seq: int, now: float) -> dict[str, Any]:
    """Shared draft for one screen. Ops are appended with a sequence number; an op
    on an item another person changed after your base is refused (no silent
    overwrite) and returned so the UI can explain it."""
    editors = room.setdefault("editors", {})
    log: list[dict[str, Any]] = room.setdefault("log", [])
    for eid in [e for e, v in editors.items() if now - v["seen"] > COEDIT_TTL]:
        editors.pop(eid, None)
    editors[editor] = {"name": name, "selected": selected, "seen": now}
    refused = []
    for op in new_ops[:50]:
        node = str(op.get("node") or "")
        clash = next((e for e in log if e["seq"] > base_seq and e["editor"] != editor and node and str(e["op"].get("node") or "") == node), None)
        if clash:
            refused.append({"op": op, "by": clash["name"], "reason": f"{clash['name']} changed this item a moment ago."})
            continue
        room["seq"] = int(room.get("seq", 0)) + 1
        log.append({"seq": room["seq"], "editor": editor, "name": name, "op": op})
    if len(log) > COEDIT_MAX_OPS:
        del log[: len(log) - COEDIT_MAX_OPS]
    return {"seq": int(room.get("seq", 0)),
            "ops": [e for e in log if e["seq"] > since and e["editor"] != editor],
            "others": [{"editor_id": e, "name": v["name"], "selected": v["selected"]} for e, v in editors.items() if e != editor],
            "refused": refused}


def plain_html(text: str) -> str:
    return "<br/>".join(htmlmod.escape(x) for x in text.splitlines())


# SPEC 3.x style prompt for report-from-document (proposal only).
DOC_SYSTEM_PROMPT = (
    "You read the text of a printed business document (lines in reading order) and map it to an Odoo record's fields. "
    "You receive the lines, the record's field list with names, labels and types, and the fields of its line lists. "
    "Return only JSON matching the schema. Use only field names from the input. Never invent fields or values. "
    "For printed labels with a value next to them, use a label_field block. For a table of lines, use one o2m_table block "
    "with the matching line fields as columns. Fixed wording (titles, thank-you notes, terms) becomes heading or text "
    "blocks with the wording copied exactly. If a part matches no field, leave it out and list it in \"unclear\"."
)

DOC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "blocks": {"type": "array", "maxItems": 40, "items": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": sorted(DOC_BLOCK_KINDS)},
            "field": {"type": "string"}, "label": {"type": "string"},
            "columns": {"type": "array", "items": {"type": "string"}}}, "required": ["kind"]}},
        "unclear": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["blocks", "unclear"],
}
