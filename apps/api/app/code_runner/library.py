"""Script library (19), parameter forms (21), gallery (23), co-editing + comments (24), notebooks (26), tests (27)."""

from __future__ import annotations

import ast
import difflib
import time
import uuid
from typing import Any

from app.code_runner import store

MAX_VERSIONS = 200
MAX_REVS = 50
PRESENCE_TTL = 30.0


def _key(ws: str | None) -> str:
    return f"lib_{ws or 'local'}"


def _all(ws: str | None) -> dict[str, Any]:
    return store.load("library", _key(ws), {})


def _put(ws: str | None, data: dict[str, Any]) -> None:
    store.save("library", _key(ws), data)


def summary(s: dict[str, Any]) -> dict[str, Any]:
    return {k: s.get(k) for k in ("id", "name", "folder", "tags", "kind", "updated_at", "updated_by", "rev", "shared_connections")} | {
        "versions": len(s.get("versions") or []), "open_comments": sum(1 for c in s.get("comments") or [] if not c.get("resolved"))}


def search(ws: str | None, q: str = "", folder: str = "", tag: str = "") -> dict[str, Any]:
    items = list(_all(ws).values())
    ql = q.lower()
    out = [s for s in items
           if (not folder or s.get("folder") == folder) and (not tag or tag in (s.get("tags") or []))
           and (not ql or ql in s.get("name", "").lower() or ql in s.get("code", "").lower() or any(ql in t.lower() for t in s.get("tags") or []))]
    out.sort(key=lambda s: -(s.get("updated_at") or 0))
    return {"scripts": [summary(s) for s in out], "folders": sorted({s.get("folder") or "" for s in items} - {""}),
            "tags": sorted({t for s in items for t in s.get("tags") or []})}


def get(ws: str | None, sid: str) -> dict[str, Any] | None:
    return _all(ws).get(sid)


def create(ws: str | None, *, name: str, code: str, by: str | None, folder: str = "", tags: list[str] | None = None,
           kind: str = "script", cells: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    now = time.time()
    sid = str(uuid.uuid4())
    s = {"id": sid, "name": name[:120] or "Untitled", "folder": folder[:80], "tags": sorted(set(tags or []))[:20], "kind": kind,
         "code": code, "cells": cells or [], "rev": 1, "revs": [{"rev": 1, "code": code}], "updated_at": now, "updated_by": by,
         "versions": [{"n": 1, "code": code, "cells": cells or [], "at": now, "by": by, "note": "Created"}],
         "comments": [], "tests": [], "presence": {}, "shared_connections": []}
    with store.lock():
        data = _all(ws)
        data[sid] = s
        _put(ws, data)
    return s


def update_meta(ws: str | None, sid: str, **meta: Any) -> dict[str, Any]:
    with store.lock():
        data = _all(ws)
        s = data[sid]
        for k in ("name", "folder", "tags", "shared_connections", "tests"):
            if meta.get(k) is not None:
                s[k] = meta[k]
        _put(ws, data)
    return s


def delete(ws: str | None, sid: str) -> bool:
    with store.lock():
        data = _all(ws)
        hit = data.pop(sid, None) is not None
        _put(ws, data)
    return hit


# ---------------------------------------------------------------- versions + diff
def save_version(ws: str | None, sid: str, *, by: str | None, note: str = "") -> dict[str, Any]:
    with store.lock():
        data = _all(ws)
        s = data[sid]
        last = s["versions"][-1] if s["versions"] else None
        if last and last["code"] == s["code"] and last.get("cells") == s.get("cells"):
            return last
        v = {"n": (last["n"] + 1) if last else 1, "code": s["code"], "cells": s.get("cells") or [], "at": time.time(), "by": by, "note": note[:200]}
        s["versions"] = (s["versions"] + [v])[-MAX_VERSIONS:]
        _put(ws, data)
    return v


def diff(a: str, b: str, la: str = "a", lb: str = "b") -> str:
    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), la, lb))


# ---------------------------------------------------------------- live co-editing (rev + line merge)
def _changed_lines(base: list[str], new: list[str]) -> set[int]:
    out: set[int] = set()
    for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(None, base, new, autojunk=False).get_opcodes():
        if tag != "equal":
            out.update(range(i1, max(i2, i1 + 1)))
    return out


def merge3(base: str, mine: str, theirs: str) -> str | None:
    """Line merge: both edits apply when they touch different base lines; None on overlap."""
    b, m, t = base.splitlines(True), mine.splitlines(True), theirs.splitlines(True)
    if not (_changed_lines(b, m) & _changed_lines(b, t)):
        out = list(t)
        # replay my opcodes against theirs, from the bottom so offsets stay valid
        sm_t = difflib.SequenceMatcher(None, b, t, autojunk=False)
        def to_theirs(i: int) -> int:
            for tag, i1, i2, j1, j2 in sm_t.get_opcodes():
                if i1 <= i < i2 or (i == i1 == i2):
                    return j1 + (i - i1 if tag == "equal" else 0)
            return len(t)
        for tag, i1, i2, j1, j2 in reversed(difflib.SequenceMatcher(None, b, m, autojunk=False).get_opcodes()):
            if tag == "equal":
                continue
            s0 = to_theirs(i1)
            out[s0:s0 + (i2 - i1)] = m[j1:j2]
        return "".join(out)
    return None


def live_put(ws: str | None, sid: str, *, base_rev: int, code: str, by: str | None,
             cells: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    with store.lock():
        data = _all(ws)
        s = data[sid]
        if base_rev == s["rev"]:
            merged = code
        else:
            base = next((r["code"] for r in s.get("revs", []) if r["rev"] == base_rev), None)
            merged = merge3(base, code, s["code"]) if base is not None else None
            if merged is None:
                return {"ok": False, "conflict": True, "rev": s["rev"], "code": s["code"],
                        "message": "Someone changed the same lines. Their version is shown; re-apply your edit."}
        s["code"] = merged
        if cells is not None:
            s["cells"] = cells
        s["rev"] += 1
        s["revs"] = (s.get("revs", []) + [{"rev": s["rev"], "code": merged}])[-MAX_REVS:]
        s["updated_at"], s["updated_by"] = time.time(), by
        s.setdefault("presence", {})[by or "you"] = time.time()
        _put(ws, data)
    return {"ok": True, "rev": s["rev"], "code": merged, "merged": merged != code}


def live_get(ws: str | None, sid: str, *, by: str | None, cursor_line: int | None = None) -> dict[str, Any]:
    with store.lock():
        data = _all(ws)
        s = data[sid]
        pres = s.setdefault("presence", {})
        now = time.time()
        pres[by or "you"] = now
        if cursor_line:
            s.setdefault("cursors", {})[by or "you"] = cursor_line
        s["presence"] = {k: v for k, v in pres.items() if now - v < PRESENCE_TTL}
        _put(ws, data)
    return {"rev": s["rev"], "code": s["code"], "cells": s.get("cells") or [],
            "editors": [{"who": k, "line": (s.get("cursors") or {}).get(k)} for k in s["presence"]]}


# ---------------------------------------------------------------- line comments
def comment(ws: str | None, sid: str, *, line: int, text: str, by: str | None) -> dict[str, Any]:
    c = {"id": str(uuid.uuid4())[:8], "line": int(line), "text": text[:2000], "by": by, "at": time.time(), "resolved": False, "replies": []}
    with store.lock():
        data = _all(ws)
        data[sid]["comments"].append(c)
        _put(ws, data)
    return c


def resolve_comment(ws: str | None, sid: str, cid: str, *, reply: str = "", by: str | None = None, resolved: bool | None = None) -> dict[str, Any]:
    with store.lock():
        data = _all(ws)
        c = next(c for c in data[sid]["comments"] if c["id"] == cid)
        if reply:
            c["replies"].append({"text": reply[:2000], "by": by, "at": time.time()})
        if resolved is not None:
            c["resolved"] = resolved
        _put(ws, data)
    return c


# ---------------------------------------------------------------- parameter forms (item 21)
_TYPE_OF = {bool: "bool", int: "int", float: "float", str: "text"}


def detect_params(code: str) -> list[dict[str, Any]]:
    """params["x"] / params.get("x", default) → a form field; type from the default value or the name."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return []
    found: dict[str, dict[str, Any]] = {}
    for n in ast.walk(tree):
        name, default = None, None
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == "params" and isinstance(n.slice, ast.Constant):
            name = n.slice.value
        elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get"
              and isinstance(n.func.value, ast.Name) and n.func.value.id == "params" and n.args and isinstance(n.args[0], ast.Constant)):
            name = n.args[0].value
            if len(n.args) > 1:
                try:
                    default = ast.literal_eval(n.args[1])
                except ValueError:
                    default = None
        if not isinstance(name, str) or name in found:
            continue
        t = _TYPE_OF.get(type(default), "text")
        low = name.lower()
        if t == "text" and ("date" in low or low.endswith("_on") or low in {"since", "until", "before", "after"}):
            t = "date"
        if t == "text" and low.endswith("_ids"):
            t = "ids"
        elif t == "text" and (low.endswith("_id") or low in {"id", "record"}):
            t = "id"
        if t == "text" and low in {"model", "model_name"}:
            t = "model"
        found[name] = {"name": name, "label": name.replace("_", " ").capitalize(), "type": t, "default": default,
                       "required": default is None}
    return list(found.values())


def coerce_params(spec: list[dict[str, Any]], values: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    out, errors = {}, []
    for f in spec:
        v = values.get(f["name"], f.get("default"))
        if v in (None, "") and f.get("required"):
            errors.append(f"{f['label']} is needed.")
            continue
        try:
            if f["type"] == "int" or f["type"] == "id":
                v = int(v)
            elif f["type"] == "float":
                v = float(v)
            elif f["type"] == "bool":
                v = v in (True, "true", "1", 1, "on")
            elif f["type"] == "ids":
                v = [int(x) for x in (v if isinstance(v, list) else str(v).replace(" ", "").split(",")) if str(x)]
        except (TypeError, ValueError):
            errors.append(f"{f['label']} should be a {f['type']}.")
            continue
        out[f["name"]] = v
    return out, errors


# ---------------------------------------------------------------- starter gallery (item 23)
GALLERY: list[dict[str, Any]] = [
    {"id": "inactive_customers", "title": "Find customers with no orders this year", "category": "Customers", "risk": "reads",
     "code": 'since = params.get("since", "2026-01-01")\nparts = odoo.execute_kw("res.partner", "search_read", [[("customer_rank", ">", 0)]], {"fields": ["name", "email"], "limit": params.get("limit", 500)})\nrows = []\nfor p in parts:\n    n = odoo.execute_kw("sale.order", "search_count", [[("partner_id", "=", p["id"]), ("date_order", ">=", since)]])\n    if not n:\n        rows.append({"id": p["id"], "name": p["name"], "email": p["email"]})\nresult(rows)\nlog(f"{len(rows)} customers without orders since {since}")\n'},
    {"id": "fill_missing_country", "title": "Set a country on contacts that have none", "category": "Data clean-up", "risk": "writes",
     "code": 'country_id = params["country_id"]\nids = odoo.execute_kw("res.partner", "search", [[("country_id", "=", False)]], {"limit": params.get("limit", 200)})\nodoo.execute_kw("res.partner", "write", [ids, {"country_id": country_id}])\nlog(f"Updated {len(ids)} contacts")\n'},
    {"id": "archive_stale_leads", "title": "Archive leads untouched for N days", "category": "CRM", "risk": "writes",
     "code": 'days = params.get("days", 180)\nfrom datetime import datetime, timedelta\ncut = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")\nids = odoo.execute_kw("crm.lead", "search", [[("write_date", "<", cut), ("active", "=", True)]], {"limit": 500})\nodoo.execute_kw("crm.lead", "action_archive", [ids])\nlog(f"Archived {len(ids)} leads")\n'},
    {"id": "duplicate_emails", "title": "List contacts that share an email", "category": "Data clean-up", "risk": "reads",
     "code": 'rows = odoo.execute_kw("res.partner", "search_read", [[("email", "!=", False)]], {"fields": ["name", "email"]})\nseen = {}\nfor r in rows:\n    seen.setdefault(r["email"].strip().lower(), []).append(r)\ndupes = [{"email": e, "count": len(v), "names": ", ".join(x["name"] for x in v)} for e, v in seen.items() if len(v) > 1]\nresult(dupes)\n'},
    {"id": "count_by_state", "title": "Count records by status", "category": "Reports", "risk": "reads",
     "code": 'model = params.get("model", "sale.order")\nrows = odoo.execute_kw(model, "read_group", [[], ["state"], ["state"]], {"lazy": False})\nresult([{"state": r["state"], "count": r["__count"]} for r in rows])\n'},
    {"id": "tag_contacts", "title": "Add a tag to contacts from a list of ids", "category": "Customers", "risk": "writes",
     "code": 'ids = params["partner_ids"]\ntag_id = params["tag_id"]\nodoo.execute_kw("res.partner", "write", [ids, {"category_id": [(4, tag_id)]}])\nlog(f"Tagged {len(ids)} contacts")\n'},
]
