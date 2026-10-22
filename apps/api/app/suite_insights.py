"""Configuration Suite ideas that only look (spec §16): data quality, archive check, role x-ray, access
hygiene, numbering, translations, automation catalogue, unused apps, custom field clean-up, storage forecast,
import aftercare, record time-travel, two-database compare, day-1 review and the hot-spot heatmap.

Every function reads; none writes. Numbers come from the database, never from an estimate. Text is plain words:
record types are shown by their Odoo name, technical names only under "code".
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE = re.compile(r"^[+()\d][\d\s().\-/]{5,}$")
SAMPLE = 2000


def _x(client: Any, model: str, method: str, args: list[Any] | None = None, kw: dict[str, Any] | None = None) -> Any:
    return client.execute_kw(model, method, args or [], kw or {})


def _try(fn: Any, default: Any) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001  app not installed or no rights: the panel says so instead of failing
        return default


def _has(client: Any, model: str) -> bool:
    return bool(_try(lambda: _x(client, "ir.model", "search_count", [[("model", "=", model)]]), 0))


def _label(client: Any, model: str) -> str:
    rows = _try(lambda: _x(client, "ir.model", "search_read", [[("model", "=", model)]], {"fields": ["name"], "limit": 1}), [])
    return rows[0]["name"] if rows else model


def _since(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


# 5 -------------------------------------------------------------------------------------------- data quality
def data_quality(client: Any, model: str = "res.partner") -> dict[str, Any]:
    meta = _x(client, model, "fields_get", [], {"attributes": ["string", "type", "store", "readonly", "relation"]})
    total = _x(client, model, "search_count", [[]])
    stored = {f: m for f, m in meta.items() if m.get("store", True) and not m.get("readonly")
              and m["type"] in {"char", "text", "many2one", "date", "datetime", "selection", "float", "integer", "monetary"}
              and not f.startswith(("message_", "activity_", "website_message"))}
    empty = []
    for f, m in stored.items():
        n = _try(lambda f=f: _x(client, model, "search_count", [[(f, "=", False)]]), None)
        if n is not None and total and n / total >= 0.8:
            empty.append({"field": m.get("string") or f, "code": f, "empty": n, "of": total})
    bad_email, bad_phone = [], []
    rows = _x(client, model, "search_read", [[]], {"fields": [f for f in ("name", "email", "phone") if f in meta], "limit": SAMPLE})
    for r in rows:
        if r.get("email") and not EMAIL.match(str(r["email"]).strip()):
            bad_email.append({"id": r["id"], "name": r.get("name"), "value": r["email"]})
        if r.get("phone") and not PHONE.match(str(r["phone"]).strip()):
            bad_phone.append({"id": r["id"], "name": r.get("name"), "value": r["phone"]})
    return {"record_type": _label(client, model), "code": model, "records": total, "checked": len(rows),
            "mostly_empty": sorted(empty, key=lambda e: -e["empty"])[:25],
            "bad_emails": bad_email[:50], "bad_phones": bad_phone[:50],
            "fix": "Fix values in Change records (Edit), or hide a never-filled field in View Designer."}


# 8 ------------------------------------------------------------------------------- archive dependency check
OPEN_USES = {
    "product.product": [("sale.order.line", "product_id", [("order_id.state", "in", ["draft", "sent"])], "open quotations"),
                        ("purchase.order.line", "product_id", [("order_id.state", "in", ["draft", "sent", "to approve"])], "open purchase orders"),
                        ("stock.move", "product_id", [("state", "not in", ["done", "cancel"])], "stock moves not done")],
    "res.partner": [("sale.order", "partner_id", [("state", "in", ["draft", "sent", "sale"])], "open sales orders"),
                    ("account.move", "partner_id", [("state", "=", "draft")], "draft invoices"),
                    ("crm.lead", "partner_id", [("active", "=", True), ("probability", "<", 100)], "open opportunities")],
}


def archive_check(client: Any, model: str, ids: list[int]) -> dict[str, Any]:
    if model == "product.template":
        pp = _x(client, "product.product", "search", [[("product_tmpl_id", "in", ids)]], {"context": {"active_test": False}})
        model, ids, back = "product.product", pp, "product_tmpl_id"
    else:
        back = None
    blocked: dict[int, list[str]] = {}
    for rel, field, dom, words in OPEN_USES.get(model, []):
        if not _has(client, rel):
            continue
        # search_read + count here: read_group changed shape in Odoo 19 (formatted_read_group).
        rows = _try(lambda: _x(client, rel, "search_read", [[(field, "in", ids), *dom]], {"fields": [field], "limit": 20000}), [])
        for rid, n in Counter(r[field][0] for r in rows if r.get(field)).items():
            blocked.setdefault(rid, []).append(f"{n} {words}")
    names = {r["id"]: r.get("display_name") or r.get("name") for r in
             _x(client, model, "read", [ids], {"fields": ["display_name", back] if back else ["display_name"]})} if ids else {}
    return {"safe": [{"id": i, "name": names.get(i)} for i in ids if i not in blocked],
            "blocked": [{"id": i, "name": names.get(i), "because": why} for i, why in blocked.items()],
            "next": "Archive the safe ones in Change records > Archive. Blocked ones need their open documents closed first."}


# 12 ------------------------------------------------------------------------------------------- role x-ray
def role_xray(client: Any, user_id: int) -> dict[str, Any]:
    u = _x(client, "res.users", "read", [[user_id]], {"fields": ["name", "login", _gfield(client), "share"]})
    if not u:
        return {"error": "No such user."}
    u = u[0]
    gids = u.get("groups_id") or u.get("group_ids") or []
    groups = _x(client, "res.groups", "read", [gids], {"fields": ["full_name", "name"]}) if gids else []
    am = "ir.access" if _v20(client) else "ir.model.access"
    acc = _try(lambda: _x(client, am, "search_read", [[("group_id", "in", gids + [False])]],
                          {"fields": ["model_id", "group_id"] + (["operation"] if am == "ir.access" else ["perm_read", "perm_write", "perm_create", "perm_unlink"])}), [])
    by_model: dict[str, dict[str, Any]] = {}
    for a in acc:
        name = a["model_id"][1] if a.get("model_id") else "?"
        why = a["group_id"][1] if a.get("group_id") else "everyone"
        m = by_model.setdefault(name, {"record_type": name, "read": [], "write": [], "create": [], "delete": []})
        if am == "ir.access":
            op = a.get("operation") or ""
            flags = {"read": "r" in op, "write": "u" in op, "create": "c" in op, "delete": "d" in op}
        else:
            flags = {"read": a["perm_read"], "write": a["perm_write"], "create": a["perm_create"], "delete": a["perm_unlink"]}
        for k, on in flags.items():
            if on and why not in m[k]:
                m[k].append(why)
    return {"user": u["name"], "login": u["login"], "portal": bool(u.get("share")),
            "roles": sorted(g.get("full_name") or g["name"] for g in groups),
            "can": sorted(by_model.values(), key=lambda m: m["record_type"])[:400],
            "note": "Each tick lists the role that grants it. Record rules can narrow this further."}


def _gfield(client: Any) -> str:
    """res.users groups field: groups_id up to 18, group_ids from 19."""
    meta = _try(lambda: _x(client, "res.users", "fields_get", [["group_ids", "groups_id"]], {"attributes": ["type"]}), {})
    return "group_ids" if "group_ids" in meta else "groups_id"


def _v20(client: Any) -> bool:
    return int(getattr(getattr(client, "capabilities", None), "major", 0) or 0) >= 20


# 13 ------------------------------------------------------------------------------------------ access hygiene
def access_hygiene(client: Any, days: int = 90) -> dict[str, Any]:
    gf = _gfield(client)
    users = _x(client, "res.users", "search_read", [[("active", "=", True)]], {"fields": ["name", "login", "login_date", "share", gf]})
    admin_gid = _try(lambda: _x(client, "ir.model.data", "check_object_reference", ["base", "group_system"])[1], None)
    cutoff = _since(days)
    out = {"admins_inactive": [], "no_role": [], "portal_inactive": []}
    for u in users:
        last = u.get("login_date") or ""
        idle = not last or last < cutoff
        row = {"id": u["id"], "name": u["name"], "login": u["login"], "last_sign_in": last or "never"}
        if admin_gid and admin_gid in (u.get(gf) or []) and idle and u["id"] != 1:
            out["admins_inactive"].append(row)
        if not u.get("share") and len(u.get(gf) or []) <= 2:
            out["no_role"].append(row)
        if u.get("share") and idle:
            out["portal_inactive"].append(row)
    return {**out, "days": days, "users": len(users), "next": "Remove access in Access, or use the leaver playbook to hand work over first."}


# 15 -------------------------------------------------------------------------------------------- numbering
def numbering_check(client: Any, model: str = "sale.order", field: str = "name") -> dict[str, Any]:
    if not _has(client, model):
        return {"record_type": model, "missing": True}
    names = [r[field] for r in _x(client, model, "search_read", [[]], {"fields": [field], "order": "id", "limit": 20000}) if r.get(field)]
    dupes = [n for n, c in Counter(names).items() if c > 1]
    gaps = []
    series: dict[str, list[int]] = {}
    for n in names:
        m = re.match(r"^(.*?)(\d+)$", str(n))
        if m:
            series.setdefault(m.group(1), []).append(int(m.group(2)))
    for prefix, nums in series.items():
        s = sorted(set(nums))
        for a, b in zip(s, s[1:], strict=False):
            if b - a > 1:
                gaps.append({"after": f"{prefix}{a}", "before": f"{prefix}{b}", "missing": b - a - 1})
    return {"record_type": _label(client, model), "documents": len(names), "duplicates": dupes[:50], "gaps": gaps[:50],
            "note": "Look only. Gaps usually come from deleted drafts or cancelled numbers; accounting numbering is fixed in Odoo's own screens."}


# 17 ---------------------------------------------------------------------------------- translation coverage
def translation_coverage(client: Any) -> dict[str, Any]:
    langs = _x(client, "res.lang", "search_read", [[("active", "=", True)]], {"fields": ["code", "name"]})
    fields = _x(client, "ir.model.fields", "search_read", [[("state", "=", "manual")]], {"fields": ["name", "model", "field_description"], "limit": 2000})
    out = []
    for lg in langs:
        if lg["code"] == "en_US":
            continue
        done = 0
        for f in fields:
            en = f["field_description"]
            tr = _try(lambda f=f: _x(client, "ir.model.fields", "read", [[f["id"]]], {"fields": ["field_description"], "context": {"lang": lg["code"]}})[0]["field_description"], en)
            if tr and tr != en:
                done += 1
        out.append({"language": lg["name"], "code": lg["code"], "custom_labels": len(fields), "translated": done,
                    "missing": len(fields) - done})
    return {"languages": out, "note": "Covers labels of fields made in this database. Translate them in View Designer > Translations."}


# 18 --------------------------------------------------------------------------------- automation catalogue
TRIGGER_WORDS = {"on_create": "when a record is created", "on_write": "when a record is changed", "on_create_or_write": "when a record is created or changed",
                 "on_unlink": "when a record is deleted", "on_change": "when a form field changes", "on_time": "on a timer",
                 "on_stage_set": "when the stage changes", "on_user_set": "when someone is assigned", "on_tag_set": "when a tag is added",
                 "on_state_set": "when the status changes", "on_priority_set": "when the priority changes", "on_archive": "when archived",
                 "on_unarchive": "when restored", "on_webhook": "when a webhook is called", "on_message_received": "when a message arrives",
                 "on_message_sent": "when a message is sent"}


def automation_catalogue(client: Any) -> dict[str, Any]:
    rules = _try(lambda: _x(client, "base.automation", "search_read", [[]], {"fields": ["name", "model_id", "trigger", "active", "last_run", "write_date"], "context": {"active_test": False}}), [])
    crons = _x(client, "ir.cron", "search_read", [[]], {"fields": ["name", "interval_number", "interval_type", "active", "lastcall", "nextcall"], "context": {"active_test": False}})
    return {"automations": [{"name": r["name"], "record_type": r["model_id"][1] if r.get("model_id") else "", "fires": TRIGGER_WORDS.get(r.get("trigger"), r.get("trigger")),
                             "on": r["active"], "last_fired": r.get("last_run") or "not recorded"} for r in rules],
            "schedules": [{"name": c["name"], "fires": f"every {c['interval_number']} {c['interval_type']}", "on": c["active"],
                           "last_fired": c.get("lastcall") or "never", "next": c.get("nextcall")} for c in crons],
            "installed": bool(rules) or _has(client, "base.automation")}


# 19 ---------------------------------------------------------------------------------------- unused apps
APP_MAIN = {"sale": "sale.order", "sale_management": "sale.order", "purchase": "purchase.order", "crm": "crm.lead", "stock": "stock.picking",
            "account": "account.move", "project": "project.task", "hr": "hr.employee", "mrp": "mrp.production", "website": "website.page",
            "helpdesk": "helpdesk.ticket", "event": "event.event", "pos_restaurant": "pos.order", "point_of_sale": "pos.order",
            "fleet": "fleet.vehicle", "maintenance": "maintenance.request", "survey": "survey.survey", "hr_expense": "hr.expense",
            "hr_holidays": "hr.leave", "mass_mailing": "mailing.mailing", "lunch": "lunch.order", "repair": "repair.order"}


def unused_apps(client: Any, days: int = 90) -> dict[str, Any]:
    installed = {r["name"]: r["shortdesc"] for r in _x(client, "ir.module.module", "search_read", [[("state", "=", "installed"), ("application", "=", True)]], {"fields": ["name", "shortdesc"]})}
    out = []
    for mod, label in installed.items():
        model = APP_MAIN.get(mod)
        if not model or not _has(client, model):
            continue
        recent = _try(lambda model=model: _x(client, model, "search_count", [[("create_date", ">=", _since(days))]]), None)
        total = _try(lambda model=model: _x(client, model, "search_count", [[]]), None)
        if recent == 0:
            out.append({"app": label, "code": mod, "records_ever": total, "new_in_period": 0,
                        "uninstall_removes": f"{total} {_label(client, model)} record(s) and the app's screens and settings" if total else "the app's screens and settings"})
    return {"days": days, "unused": out, "note": "Look only. Uninstalling is done in Odoo's Apps screen after a backup."}


# 20 ----------------------------------------------------------------------------------- custom field clean-up
def custom_fields(client: Any) -> dict[str, Any]:
    fields = _x(client, "ir.model.fields", "search_read", [[("state", "=", "manual"), ("store", "=", True)]], {"fields": ["name", "model", "field_description", "ttype"], "limit": 1000})
    views = _x(client, "ir.ui.view", "search_read", [[("arch_db", "ilike", "x_")]], {"fields": ["name", "arch_db", "model"], "limit": 2000})
    autos = _try(lambda: _x(client, "ir.actions.server", "search_read", [[("code", "ilike", "x_")]], {"fields": ["name", "code"]}), [])
    out = []
    for f in fields:
        total = _try(lambda f=f: _x(client, f["model"], "search_count", [[]]), 0)
        filled = _try(lambda f=f: _x(client, f["model"], "search_count", [[(f["name"], "!=", False)]]), None) if f["ttype"] not in {"boolean", "one2many", "many2many"} else None
        used_in = [v["name"] for v in views if f["name"] in (v.get("arch_db") or "")][:10]
        used_in += [f"server action {a['name']}" for a in autos if f["name"] in (a.get("code") or "")][:5]
        out.append({"label": f["field_description"], "code": f"{f['model']}.{f['name']}", "record_type": _label(client, f["model"]),
                    "filled": filled, "of": total, "never_filled": filled == 0 and total > 0, "used_in": used_in})
    return {"fields": sorted(out, key=lambda r: (not r["never_filled"], r["record_type"])),
            "note": "A never-filled field with nothing using it is the safest to remove (Builder > Fields)."}


# 21 ------------------------------------------------------------------------------------------ storage forecast
def storage_forecast(client: Any, limit_mb: float | None = None) -> dict[str, Any]:
    rows = _x(client, "ir.attachment", "search_read", [[("res_model", "!=", False)]], {"fields": ["create_date", "file_size"], "limit": 200000})
    by: dict[str, int] = {}
    for r in rows:
        k = str(r.get("create_date") or "")[:7]
        by[k] = by.get(k, 0) + int(r.get("file_size") or 0)
    months = [{"month": k, "mb": round(b / 1_048_576, 2)} for k, b in sorted(by.items()) if k]
    total = round(sum(m["mb"] for m in months), 2)
    pace = round(sum(m["mb"] for m in months[-6:]) / max(1, len(months[-6:])), 2) if months else 0.0
    reach = None
    if limit_mb and pace > 0 and limit_mb > total:
        reach = round((limit_mb - total) / pace, 1)
    return {"months": months[-24:], "total_mb": total, "pace_mb_per_month": pace, "limit_mb": limit_mb, "months_to_limit": reach,
            "note": "From the real upload dates of files attached to records."}


# 22 ------------------------------------------------------------------------------------------ import aftercare
def import_aftercare(client: Any, model: str = "res.partner", days: int = 14) -> dict[str, Any]:
    xid = _x(client, "ir.model.data", "search_read", [[("model", "=", model), ("module", "=", "__import__"), ("create_date", ">=", _since(days))]], {"fields": ["res_id"], "limit": SAMPLE})
    ids = [r["res_id"] for r in xid]
    if not ids:
        return {"record_type": _label(client, model), "imported": 0, "duplicates": [], "incomplete": []}
    meta = _x(client, model, "fields_get", [], {"attributes": ["required", "string"]})
    keys = [f for f in ("email", "default_code", "vat", "ref") if f in meta]
    rows = _x(client, model, "read", [ids], {"fields": ["display_name", *keys]})
    dup = []
    for k in keys:
        vals = [r[k] for r in rows if r.get(k)]
        for v, c in Counter(vals).items():
            if c > 1 or _x(client, model, "search_count", [[(k, "=", v), ("id", "not in", ids)]]):
                dup.append({"field": meta[k]["string"], "value": v})
    incomplete = [{"id": r["id"], "name": r["display_name"], "missing": [meta[k]["string"] for k in keys if not r.get(k)]} for r in rows if not all(r.get(k) for k in keys)]
    return {"record_type": _label(client, model), "imported": len(ids), "duplicates": dup[:50], "incomplete": incomplete[:50],
            "next": "Merge duplicates in Change records > Duplicates."}


# 24 --------------------------------------------------------------------------------------- record time-travel
def record_timeline(client: Any, model: str, rec_id: int) -> dict[str, Any]:
    msgs = _x(client, "mail.message", "search_read", [[("model", "=", model), ("res_id", "=", rec_id)]], {"fields": ["date", "author_id", "body", "message_type"], "order": "date asc", "limit": 500})
    # Tracking rows are read from their own side: mail.message lost tracking_value_ids in Odoo 20.
    trows = _try(lambda: _x(client, "mail.tracking.value", "search_read", [[("mail_message_id", "in", [m["id"] for m in msgs])]], {}), []) if msgs else []
    tv = {t["id"]: t for t in trows}
    for m in msgs:
        m["tracking_value_ids"] = [t["id"] for t in trows if (t.get("mail_message_id") or [0])[0] == m["id"]]

    def val(t: dict[str, Any], side: str) -> Any:
        for k in ("char", "integer", "float", "datetime", "text", "monetary"):
            v = t.get(f"{side}_value_{k}")
            if v not in (None, False, ""):
                return v
        return "(empty)"

    events = []
    for m in msgs:
        changes = []
        for t in (m.get("tracking_value_ids") or []):
            row = tv.get(t)
            if row:
                fld = row.get("field_desc") or (row.get("field_id") or [0, "?"])[1] or row.get("field")
                changes.append({"field": fld, "from": val(row, "old"), "to": val(row, "new")})
        text = re.sub(r"<[^>]+>", "", m.get("body") or "")
        if not changes and m.get("message_type") == "tracking":
            # Odoo 20 keeps tracking as text: "old → new (Field)" per line.
            for line in text.splitlines():
                hit = re.match(r"\s*(.*?)\s*→\s*(.*?)\s*\((.+)\)\s*$", line)
                if hit:
                    changes.append({"field": hit.group(3), "from": hit.group(1) or "(empty)", "to": hit.group(2) or "(empty)"})
        if changes or m.get("message_type") in {"notification", "tracking"}:
            events.append({"when": m["date"], "who": (m.get("author_id") or [0, "System"])[1], "changes": changes,
                           "note": re.sub(r"<[^>]+>", "", m.get("body") or "")[:200]})
    return {"record_type": _label(client, model), "id": rec_id, "events": events, "note": "Only fields Odoo tracks appear here."}


# 10 ------------------------------------------------------------------------------------- two-database compare
def setup_snapshot(client: Any) -> dict[str, Any]:
    mods = {r["name"] for r in _x(client, "ir.module.module", "search_read", [[("state", "=", "installed")]], {"fields": ["name"]})}
    fields = {f"{r['model']}.{r['name']}": r["field_description"] for r in _x(client, "ir.model.fields", "search_read", [[("state", "=", "manual")]], {"fields": ["model", "name", "field_description"]})}
    views = {r["name"] for r in _x(client, "ir.ui.view", "search_read", [[("inherit_id", "!=", False), ("model_data_id", "=", False)]], {"fields": ["name"]})}
    crons = {r["name"]: r["active"] for r in _x(client, "ir.cron", "search_read", [[]], {"fields": ["name", "active"], "context": {"active_test": False}})}
    return {"version": str(client.capabilities.major), "apps": mods, "fields": fields, "screens": views, "schedules": crons}


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    def diff(x: Any, y: Any) -> dict[str, list[str]]:
        return {"only_here": sorted(set(x) - set(y))[:200], "only_there": sorted(set(y) - set(x))[:200]}
    sched_flip = sorted(n for n in set(a["schedules"]) & set(b["schedules"]) if a["schedules"][n] != b["schedules"][n])
    out = {"versions": [a["version"], b["version"]], "apps": diff(a["apps"], b["apps"]), "fields": diff(a["fields"], b["fields"]),
           "screens": diff(a["screens"], b["screens"]), "schedules": {**diff(a["schedules"], b["schedules"]), "on_off_differs": sched_flip[:100]}}
    n = sum(len(v["only_here"]) + len(v["only_there"]) for k, v in out.items() if k != "versions") + len(sched_flip)
    out["summary"] = "The two databases are set up the same." if n == 0 else f"{n} difference(s) in apps, custom fields, screen changes and schedules."
    return out


# 29 ---------------------------------------------------------------------------------------------- day-1 review
def day1_review(client: Any) -> dict[str, Any]:
    co = _x(client, "res.company", "search_read", [[]], {"fields": ["name", "email", "phone", "street", "country_id", "vat", "logo"], "limit": 1})[0]
    l10n = _x(client, "ir.module.module", "search_count", [[("name", "=like", "l10n_%"), ("state", "=", "installed"), ("name", "not in", ["l10n_generic_coa"])]])
    users = _x(client, "res.users", "search_count", [[("share", "=", False), ("id", "!=", 1)]])
    mail = _try(lambda: _x(client, "ir.mail_server", "search_count", [[]]), 0)
    items = [
        {"item": "Company name, address and country", "ok": bool(co.get("street") and co.get("country_id")), "where": "Settings > Companies"},
        {"item": "Company email and phone", "ok": bool(co.get("email") and co.get("phone")), "where": "Settings > Companies"},
        {"item": "Tax ID", "ok": bool(co.get("vat")), "where": "Settings > Companies"},
        {"item": "Logo", "ok": bool(co.get("logo")), "where": "Settings > Companies"},
        {"item": "Country package (taxes and chart of accounts)", "ok": l10n > 0, "where": "Set up > Country package"},
        {"item": "At least one other user", "ok": users > 0, "where": "Settings > Users"},
        {"item": "Outgoing mail server", "ok": mail > 0, "where": "Settings > Technical > Outgoing mail servers (Odoo Online sends for you)"},
        {"item": "Backups", "ok": None, "where": "Your host's backup screen. Ingenium can't see backups over the API."},
    ]
    return {"company": co["name"], "items": items, "done": sum(1 for i in items if i["ok"]), "of": sum(1 for i in items if i["ok"] is not None)}


# 33 ------------------------------------------------------------------------------------------- hot-spot heatmap
def hotspots(runs: list[dict[str, Any]]) -> dict[str, Any]:
    c: Counter[str] = Counter()
    rows: Counter[str] = Counter()
    for r in runs:
        m = r.get("model") or r.get("record_type")
        if m:
            c[m] += 1
            rows[m] += int(r.get("count") or 0)
    top = [{"record_type": m, "runs": n, "records": rows[m]} for m, n in c.most_common(20)]
    return {"top": top, "hint": "Record types changed in bulk again and again are worth an automation." if top else "No bulk runs yet."}


# 16 ------------------------------------------------------------------------------- multi-company consistency
def multi_company(client: Any) -> dict[str, Any]:
    cos = _x(client, "res.company", "search_read", [[]], {"fields": ["name"]})
    if len(cos) < 2:
        return {"companies": len(cos), "findings": [], "note": "One company only, so nothing can be shared by mistake."}
    out = []
    for model, words in (("product.template", "products"), ("res.partner", "contacts"), ("account.journal", "journals"), ("stock.warehouse", "warehouses")):
        if not _has(client, model):
            continue
        n = _try(lambda model=model: _x(client, model, "search_count", [[("company_id", "=", False)]]), None)
        if n:
            out.append({"what": words, "shared_with_all": n, "check": f"{n} {words} are visible in every company. Usual for contacts; check it's meant for {words}."})
    return {"companies": len(cos), "findings": out, "fix": "Set the company on the records that belong to one company (Change records > Edit > Company)."}


# 38 ---------------------------------------------------------------------------------------------- setup score
def setup_score(client: Any) -> dict[str, Any]:
    d = day1_review(client)
    open_steps = [i for i in d["items"] if i["ok"] is False]
    return {"summary": f"{d['done']} of {d['of']} Day-1 steps done.", "done": d["done"], "of": d["of"], "open": open_steps}


# 48 ------------------------------------------------------------------------------------------- import health
def import_health(client: Any, days_min: int = 7, days_max: int = 120) -> dict[str, Any]:
    out = []
    for model, used_model, link, words in (("product.template", "sale.order.line", "product_id.product_tmpl_id", "products never sold"),
                                           ("res.partner", "account.move", "partner_id", "customers never invoiced")):
        xid = _x(client, "ir.model.data", "search_read", [[("model", "=", model), ("module", "=", "__import__"),
                                                           ("create_date", "<=", _since(days_min)), ("create_date", ">=", _since(days_max))]], {"fields": ["res_id"], "limit": SAMPLE})
        ids = [r["res_id"] for r in xid]
        if not ids or not _has(client, used_model):
            out.append({"what": words, "imported": len(ids), "never_used": 0, "examples": []})
            continue
        used = {r[link.split(".")[0]][0] for r in _try(lambda: _x(client, used_model, "search_read", [[(link, "in", ids)]], {"fields": [link.split(".")[0]], "limit": 20000}), []) if r.get(link.split(".")[0])}
        if model == "product.template":
            pp = {r["id"]: r["product_tmpl_id"][0] for r in _x(client, "product.product", "search_read", [[("id", "in", list(used))]], {"fields": ["product_tmpl_id"]})} if used else {}
            used = set(pp.values())
        idle = [i for i in ids if i not in used]
        names = _x(client, model, "read", [idle[:20]], {"fields": ["display_name"]}) if idle else []
        out.append({"what": words, "imported": len(ids), "never_used": len(idle), "examples": [n["display_name"] for n in names]})
    return {"checks": out, "note": f"Records imported {days_min} to {days_max} days ago that nothing has used yet. Review, don't delete in a hurry."}


# 46 ----------------------------------------------------------------------------------------- price-list diff
def price_list_diff(old: list[dict[str, str]], new: list[dict[str, str]], key: str) -> dict[str, Any]:
    o = {str(r.get(key, "")).strip(): r for r in old if str(r.get(key, "")).strip()}
    n = {str(r.get(key, "")).strip(): r for r in new if str(r.get(key, "")).strip()}
    changed = []
    for k in sorted(set(o) & set(n)):
        diffs = {c: {"old": o[k].get(c, ""), "new": n[k].get(c, "")} for c in n[k] if c != key and str(o[k].get(c, "")).strip() != str(n[k].get(c, "")).strip()}
        if diffs:
            changed.append({"row": k, "changes": diffs})
    return {"changed": changed, "added": sorted(set(n) - set(o)), "removed": sorted(set(o) - set(n)),
            "summary": f"{len(changed)} changed, {len(set(n) - set(o))} new, {len(set(o) - set(n))} gone. Only these go into the import plan."}


# 11 / 44 ------------------------------------------------------------------------------------- handover pack
def handover_html(client: Any, plans: list[dict[str, Any]], runs: list[dict[str, Any]]) -> str:
    import html as h
    e = h.escape
    d1, auto, cf = day1_review(client), automation_catalogue(client), custom_fields(client)
    apps = _x(client, "ir.module.module", "search_read", [[("state", "=", "installed"), ("application", "=", True)]], {"fields": ["shortdesc"]})
    users = _x(client, "res.users", "search_read", [[("share", "=", False)]], {"fields": ["name", "login", "login_date"]})
    rows = lambda items, cols: "".join("<tr>" + "".join(f"<td>{e(str(i.get(c) if i.get(c) not in (None, False) else '–'))}</td>" for c in cols) + "</tr>" for i in items)
    parts = [
        f"<h1>How {e(d1['company'])} is set up</h1><p>Odoo {e(str(client.capabilities.major))}. Made by Ingenium on {datetime.now(UTC):%d %b %Y}. Read from the database; nothing is assumed.</p>",
        "<h2>Day-1 checklist</h2><table><tr><th>Item</th><th>Done</th><th>Where</th></tr>" + "".join(f"<tr><td>{e(i['item'])}</td><td>{'Yes' if i['ok'] else 'No' if i['ok'] is False else 'Not visible'}</td><td>{e(i['where'])}</td></tr>" for i in d1["items"]) + "</table>",
        "<h2>Apps</h2><p>" + e(", ".join(sorted(a["shortdesc"] for a in apps))) + "</p>",
        "<h2>People</h2><table><tr><th>Name</th><th>Sign-in</th><th>Last signed in</th></tr>" + rows(users, ["name", "login", "login_date"]) + "</table>",
        "<h2>Automations</h2><table><tr><th>Name</th><th>Record type</th><th>Fires</th><th>On</th></tr>" + rows(auto["automations"], ["name", "record_type", "fires", "on"]) + "</table>",
        "<h2>Scheduled jobs</h2><table><tr><th>Name</th><th>Fires</th><th>On</th><th>Last</th></tr>" + rows(auto["schedules"], ["name", "fires", "on", "last_fired"]) + "</table>",
        "<h2>Fields made in this database</h2><table><tr><th>Field</th><th>Record type</th><th>Filled</th><th>Used in</th></tr>" + "".join(f"<tr><td>{e(f['label'])}</td><td>{e(f['record_type'])}</td><td>{e(str(f['filled']))} of {e(str(f['of']))}</td><td>{e(', '.join(f['used_in']) or '–')}</td></tr>" for f in cf["fields"]) + "</table>",
        "<h2>How this was set up (Ingenium plans and runs)</h2><table><tr><th>Plan</th><th>Steps</th><th>Run</th></tr>" + "".join(f"<tr><td>{e(p['name'])}</td><td>{p['steps']}</td><td>{e(p.get('run') or 'not run')}</td></tr>" for p in plans) + "</table>",
        "<h2>Bulk changes</h2><table><tr><th>Change</th><th>Record type</th><th>When</th><th>By</th></tr>" + rows(runs, ["name", "model", "started_at", "by"]) + "</table>",
    ]
    style = "body{font:15px/1.5 Inter,system-ui,sans-serif;max-width:900px;margin:40px auto;color:#1a1c21}table{border-collapse:collapse;width:100%;margin:8px 0 24px}td,th{border-bottom:1px solid #e5e7eb;padding:6px 8px;text-align:left;font-variant-numeric:tabular-nums}h1{letter-spacing:-.02em}@media print{body{margin:0}}"
    return f"<!doctype html><html lang=en><meta charset=utf-8><title>Handover pack</title><style>{style}</style><body>{''.join(parts)}</body></html>"
