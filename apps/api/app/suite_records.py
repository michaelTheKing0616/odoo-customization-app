"""Configuration Suite stage 2 (addition): record editor rules. Code decides what can be edited.

Every edit becomes an update step in a normal setup plan, so it gets the same Check with receipt,
approval threshold (D3), waves, run and reverse-plan undo. Accounting records are view only:
posted entries never change here, and drafts change only through Odoo's own buttons (Post,
Reset to draft) in Move records forward, which always asks for approval and a reason.
"""

from __future__ import annotations

import re
from typing import Any

from app.suite_setup import GUARDED_MODELS

NOT_EDITABLE_TYPES = {"one2many", "many2many", "binary", "properties", "json", "reference", "many2one_reference"}
SYSTEM_FIELDS = {"id", "create_uid", "create_date", "write_uid", "write_date", "__last_update", "display_name"}
OPS = {"=", "!=", ">", "<", ">=", "<=", "ilike", "not ilike", "in", "not in"}
MAX_PAGE = 500
MAX_EDITS = 5000


def view_only_reason(model: str) -> str | None:
    if model == "account.move" or model == "account.move.line":
        return ("Journal entries are view only here. Posted entries never change in the suite; a draft changes only through Odoo's own "
                "Post or Reset to draft buttons in Move records forward, which needs approval and a reason.")
    if model in GUARDED_MODELS or model.startswith("account."):
        return "Accounting records are view only here. Change them on Odoo's own Accounting screens."
    if model.startswith(("ir.", "res.users", "res.groups", "base.", "bus.", "mail.followers")):
        return "System records are view only here."
    return None


def field_rules(fmeta: dict[str, Any], model: str) -> list[dict[str, Any]]:
    locked = view_only_reason(model)
    out = []
    for f, m in fmeta.items():
        t = m.get("type")
        editable = (not locked and bool(m.get("store", True)) and not m.get("readonly") and t not in NOT_EDITABLE_TYPES and f not in SYSTEM_FIELDS)
        why = None if editable else (locked or ("Odoo works this out itself." if not m.get("store", True) or m.get("readonly") else
                                               "Lists and files are changed on the record's own screen." if t in NOT_EDITABLE_TYPES else "Odoo keeps this."))
        out.append({"name": f, "label": m.get("string") or f, "type": t, "relation": m.get("relation"), "required": bool(m.get("required")),
                    "stored": bool(m.get("store", True)), "editable": editable, "why_not": why, "sortable": bool(m.get("sortable", m.get("store", True))),
                    "groupable": bool(m.get("groupable", m.get("store", True))) and t not in NOT_EDITABLE_TYPES | {"text", "html"},
                    "choices": [{"value": k, "label": v} for k, v in (m.get("selection") or [])]})
    return sorted(out, key=lambda x: x["label"].lower())


def clean_filters(filters: list[Any], fmeta: dict[str, Any]) -> list[list[Any]]:
    out = []
    for flt in filters or []:
        if isinstance(flt, list | tuple) and len(flt) == 3 and str(flt[0]).split(".")[0] in fmeta | {"id": {}} and flt[1] in OPS:
            out.append([flt[0], flt[1], flt[2]])
    return out


def validate_edit(fmeta: dict[str, Any], model: str, field: str, value: Any) -> tuple[Any, str | None]:
    """Returns (value for the plan, problem). Many2one values may be an id or {'ref': name}."""
    locked = view_only_reason(model)
    if locked:
        return None, locked
    m = fmeta.get(field)
    if m is None:
        return None, f"'{field}' is not a field here."
    if not m.get("store", True) or m.get("readonly") or m.get("type") in NOT_EDITABLE_TYPES or field in SYSTEM_FIELDS:
        return None, f"'{m.get('string') or field}' can't be edited here (Odoo works it out, or it holds lists or files)."
    t = m.get("type")
    empty = value is None or value == "" or value is False
    if empty:
        if m.get("required"):
            return None, f"Odoo needs a value for '{m.get('string') or field}'."
        return (False if t != "boolean" else False), None
    if t == "boolean":
        if isinstance(value, str):
            v = value.strip().lower()
            if v not in {"yes", "no", "true", "false", "1", "0", "on", "off"}:
                return None, f"'{value}' is not yes or no."
            return v in {"yes", "true", "1", "on"}, None
        return bool(value), None
    if t in {"integer", "float", "monetary"}:
        try:
            n = float(str(value).replace(",", "")) if isinstance(value, str) else float(value)
        except ValueError:
            return None, f"'{value}' is not a number."
        return (int(n) if t == "integer" else n), None
    if t == "selection":
        keys = {k: k for k, _ in (m.get("selection") or [])} | {str(lbl).lower(): k for k, lbl in (m.get("selection") or [])}
        k = keys.get(value) or keys.get(str(value).lower())
        if not k:
            return None, f"'{value}' is not a choice for '{m.get('string') or field}'."
        return k, None
    if t == "many2one":
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            return int(value), None
        if isinstance(value, dict) and value.get("ref"):
            return {"ref": str(value["ref"])}, None
        return {"ref": str(value)}, None
    if t in {"date", "datetime"} and not re.fullmatch(r"\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?", str(value)):
        return None, f"'{value}' is not a date like 2026-10-16."
    return str(value), None


def replace_edits(rows: list[dict[str, Any]], field: str, find: str, replace: str, *, whole: bool = False, case: bool = False, html: bool = False) -> list[dict[str, Any]]:
    """For rich text (html) only the words between tags change, never the tags themselves."""
    flags = 0 if case else re.I
    pat = re.compile(rf"^{re.escape(find)}$" if whole else re.escape(find), flags)
    out = []
    for r in rows:
        old = r.get(field)
        if not isinstance(old, str) or not pat.search(old):
            continue
        if html:
            new = "".join(part if part.startswith("<") else pat.sub(lambda _m: replace, part) for part in re.split(r"(<[^>]*>)", old))
        else:
            new = pat.sub(lambda _m: replace, old)
        if new != old:
            out.append({"id": r["id"], "field": field, "value": new, "old": old})
    return out


def plan_steps(edits: list[dict[str, Any]], model: str, names: dict[int, str], labels: dict[str, str]) -> list[dict[str, Any]]:
    """One update step per record (its changed fields together), labelled in plain words."""
    by_rec: dict[int, dict[str, Any]] = {}
    for e in edits:
        by_rec.setdefault(int(e["id"]), {})[e["field"]] = e["value"]
    steps = []
    for rid, vals in by_rec.items():
        steps.append({"id": f"r{rid}", "type": "update", "inputs": {"model": model, "id": rid, "values": vals},
                      "label": f"Change {names.get(rid, f'#{rid}')}: " + ", ".join(labels.get(f, f) for f in vals),
                      "source": {"kind": "typed", "ref": "record editor"}})
    return steps
