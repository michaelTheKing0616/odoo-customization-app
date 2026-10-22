"""Configuration Suite stage 2: the five Change records tools on one Check -> Run -> Review contract.

Tools: transitions (Odoo's own buttons), edit (one field on many records, old
values kept), duplicates (multi-field match, value picking, archive by default),
activities (assignee and due-date rules), portal (grant / revoke with email
readiness). Every verdict, count and reason is computed here from the live
database; the AI never decides. Each record gets a verdict at Check; Run writes
only records that were ready, re-checks each one right before writing, and keeps
what it needs for Undo.
"""

from __future__ import annotations

import difflib
import hashlib
import html
import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.suite_setup import GUARDED_MODELS, fault_line

TOOLS = ("transitions", "edit", "duplicates", "activities", "portal", "security", "message", "recompute")
MESSAGE_PACE_MS = 200
TRACK_OFF = {"tracking_disable": True, "mail_create_nosubscribe": True, "mail_notrack": True}
PROTECTED_USERS = {"base.user_root", "base.user_admin"}
SECURITY_ROUTE = "Give accounting rights in Odoo: Settings > Users & Companies > Users."
DEFAULT_CAP, MONEY_CAP, PORTAL_CAP = 500, 50, 50
DEFAULT_BATCH = 50
PORTAL_PACE_MS = 1000
MAX_SCAN = 5000

# Odoo buttons code knows: label, method, allowed states, known side effects, Odoo's own refusal text.
BUTTONS: dict[str, dict[str, dict[str, Any]]] = {
    "sale.order": {
        "confirm": {"label": "Confirm", "method": "action_confirm", "states": ["draft", "sent"],
                    "state_msg": "Some orders are not in a state requiring confirmation.",
                    "effects": ["Turns the quotation into a sales order.", "Creates delivery orders when Inventory is installed.", "Sends no email."],
                    "undo": None},
        "cancel": {"label": "Cancel", "method": "action_cancel", "states": ["draft", "sent", "sale"],
                   "state_msg": "This order can't be cancelled from its current status.",
                   "effects": ["Cancels the order and its open deliveries."], "undo": "action_draft"},
    },
    "purchase.order": {
        "confirm": {"label": "Confirm order", "method": "button_confirm", "states": ["draft", "sent"],
                    "state_msg": "This purchase is not in a state requiring confirmation.",
                    "effects": ["Turns the request for quotation into a purchase order.", "Creates receipts when Inventory is installed."], "undo": None},
    },
    "crm.lead": {
        "won": {"label": "Mark as won", "method": "action_set_won", "states": None, "state_msg": "",
                "effects": ["Moves the lead to the won stage."], "undo": None},
    },
    "account.move": {
        "post": {"label": "Post", "method": "action_post", "states": ["draft"], "money": True,
                 "state_msg": "Only draft entries can be posted.", "effects": ["Posts the entry. Posted entries can't be edited."], "undo": "button_draft"},
        "reset": {"label": "Reset to draft", "method": "button_draft", "states": ["posted", "cancel"], "money": True,
                  "state_msg": "Only posted or cancelled entries can be reset to draft.", "effects": ["Puts the entry back to draft."], "undo": None},
        "cancel": {"label": "Cancel entry", "method": "button_cancel", "states": ["draft"], "money": True,
                   "state_msg": "Only draft entries can be cancelled.", "effects": ["Cancels the draft entry."], "undo": "button_draft"},
    },
}
MONEY_ROUTE = {
    "account.move": "Edit invoices and entries in Odoo: Accounting > Customers > Invoices (or Vendors > Bills).",
    "account.tax": "Change taxes in Odoo: Accounting > Configuration > Taxes.",
    "account.account": "Change accounts in Odoo: Accounting > Configuration > Chart of Accounts.",
    "account.journal": "Change journals in Odoo: Accounting > Configuration > Journals.",
    "account.payment": "Change payments in Odoo: Accounting > Customers > Payments.",
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NEVER_EDIT = {"id", "create_uid", "create_date", "write_uid", "write_date", "__last_update", "display_name"}


def _x(client: Any, model: str, method: str, args: list[Any] | None = None, kw: dict[str, Any] | None = None) -> Any:
    return client.execute_kw(model, method, args or [], kw or {})


def _norm(v: Any) -> Any:
    if isinstance(v, list | tuple) and len(v) == 2 and isinstance(v[0], int):
        return v[0]
    return False if v is None else v


def money_route(model: str) -> str:
    return MONEY_ROUTE.get(model, "This is accounting data. Change it on Odoo's own Accounting screens.")


SEND_LATER_MAX_DAYS = 30
REPEAT_EVERY = ("daily", "weekly", "monthly")
REPEAT_MAX_DAYS = 366


def next_send(when: datetime, every: str) -> datetime:
    """The next time in a repeating send. Monthly keeps the day, or the month's last day."""
    import calendar

    if every == "daily":
        return when + timedelta(days=1)
    if every == "weekly":
        return when + timedelta(days=7)
    y, m = (when.year + (when.month // 12), when.month % 12 + 1)
    return when.replace(year=y, month=m, day=min(when.day, calendar.monthrange(y, m)[1]))


def send_at(change: dict[str, Any]) -> datetime | None:
    """When a message batch should go out (UTC), or None for now / unreadable."""
    raw = str((change or {}).get("send_at") or "").strip()
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def batch_hash(batch: dict[str, Any]) -> str:
    keep = {k: batch.get(k) for k in ("tool", "model", "domain", "ids", "change")}
    return hashlib.sha256(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:24]


def limits_for(batch: dict[str, Any]) -> dict[str, int]:
    tool, change = batch["tool"], batch.get("change") or {}
    money = tool == "transitions" and BUTTONS.get(batch["model"], {}).get(str(change.get("button")), {}).get("money")
    cap = MONEY_CAP if money else PORTAL_CAP if tool in {"portal", "security"} else DEFAULT_CAP
    lim = dict(batch.get("limits") or {})
    floor = PORTAL_PACE_MS if tool == "portal" else MESSAGE_PACE_MS if tool == "message" else 0
    return {"cap": min(int(lim.get("cap") or cap), cap), "batch": max(1, min(int(lim.get("batch") or DEFAULT_BATCH), 200)),
            "pace_ms": max(int(lim.get("pace_ms") or floor), floor)}


def pick_ids(client: Any, batch: dict[str, Any]) -> list[int]:
    if batch.get("ids"):
        return [int(i) for i in batch["ids"]][:MAX_SCAN]
    return list(_x(client, batch["model"], "search", [batch.get("domain") or []], {"limit": MAX_SCAN, "order": "id"}))


# ---------------------------------------------------------------- refusals before any record is read
def refuse(batch: dict[str, Any], fmeta: dict[str, Any] | None) -> str | None:
    tool, model, change = batch["tool"], batch["model"], batch.get("change") or {}
    if tool not in TOOLS:
        return "Unknown tool."
    if change.get("send_at") and tool != "message":
        return "Only messages can be sent later."
    if fmeta is None:
        return "This record type is not on this database."
    if tool == "transitions":
        b = BUTTONS.get(model, {}).get(str(change.get("button")))
        if not b:
            return "That button is not one this suite runs in bulk for this record type."
        if b.get("money") and not str(change.get("reason") or "").strip():
            return "Accounting buttons need a reason (decision D2)."
        return None
    if model in GUARDED_MODELS or model.startswith("account."):
        return f"Refused by the money guard. {money_route(model)}"
    if tool == "edit":
        f = str(change.get("field") or "")
        m = fmeta.get(f)
        if not m:
            return f"'{f}' is not a field on this record type."
        if f in NEVER_EDIT or m.get("readonly") or not m.get("store", True) or m.get("type") in {"one2many", "many2many", "binary"}:
            return f"'{m.get('string') or f}' can't be edited in bulk (Odoo computes it or it holds lists or files)."
        if "value" not in change:
            return "Say the new value."
    if tool == "activities" and "activity_ids" not in fmeta:
        return "This record type doesn't take activities."
    if tool == "activities" and not change.get("user_ids"):
        return "Choose who the activities go to."
    if tool == "portal" and model != "res.partner":
        return "Portal access is given to contacts."
    if tool == "portal" and change.get("action") not in {"grant", "revoke"}:
        return "Choose grant or revoke."
    if tool == "security":
        if model != "res.users":
            return "Security groups are changed on users."
        if not (change.get("add") or change.get("remove")):
            return "Choose groups to add or remove."
        if set(map(str, change.get("add") or [])) & set(map(str, change.get("remove") or [])):
            return "A group can't be added and removed at once."
    if tool == "message":
        if "message_ids" not in fmeta:
            return "This record type has no chatter to post in."
        if not str(change.get("body") or "").strip():
            return "Write the message."
        if change.get("kind", "note") not in {"note", "comment"}:
            return "Choose an internal note or a message to followers."
        rep = change.get("repeat")
        if rep:
            if not change.get("send_at"):
                return "Pick the first send time for a repeating send."
            if not isinstance(rep, dict) or rep.get("every") not in REPEAT_EVERY:
                return "Choose daily, weekly or monthly."
            until = send_at({"send_at": rep.get("until")})
            first = send_at(change)
            if until is None or first is None or until <= first:
                return "Pick an end date after the first send."
            if (until - datetime.now(UTC)).days > REPEAT_MAX_DAYS:
                return f"A repeating send can run for up to {REPEAT_MAX_DAYS} days."
        if change.get("send_at"):
            when = send_at(change)
            if when is None:
                return "Pick a valid date and time to send."
            now = datetime.now(UTC)
            if when <= now:
                return "Pick a time in the future, or send now."
            if (when - now).days >= SEND_LATER_MAX_DAYS:
                return f"Send later can wait up to {SEND_LATER_MAX_DAYS} days."
    if tool == "recompute":
        f = str(change.get("field") or "")
        if f not in fmeta:
            return f"'{f}' is not a field on this record type."
        if not fmeta[f].get("store", True) or not fmeta[f].get("readonly"):
            return f"'{fmeta[f].get('string') or f}' is not a stored computed field."
    if tool == "duplicates" and not change.get("groups"):
        return "Pick the groups to merge first."
    return None


# ---------------------------------------------------------------- per-record verdicts (read only)
def _resolve_value(client: Any, fmeta: dict[str, Any], field: str, value: Any) -> tuple[Any, str | None]:
    m = fmeta[field]
    if m.get("type") == "many2one" and isinstance(value, dict):
        rel = m.get("relation")
        ids = _x(client, rel, "search", [[("name", "=", str(value.get("ref")))]], {"limit": 2}) if value.get("ref") else []
        if len(ids) != 1:
            return None, f"No single {m.get('string') or field} is called '{value.get('ref')}'."
        return ids[0], None
    if m.get("type") == "selection" and value not in [k for k, _ in (m.get("selection") or [])] and value is not False:
        return None, f"'{value}' is not one of the choices for {m.get('string') or field}."
    return value, None


def _due_dates(n: int, due: dict[str, Any], today: date) -> list[date]:
    mode = due.get("mode", "in_days")
    days = max(0, int(due.get("days") or 0))
    if mode == "spread":
        span = max(1, days)
        out, d, slots = [], today, []
        while len(slots) < span:
            d += timedelta(days=1)
            if d.weekday() < 5:
                slots.append(d)
        for i in range(n):
            out.append(slots[i * span // max(n, 1)])
        return out
    return [today + timedelta(days=days)] * n


def due_words(due: dict[str, Any]) -> str:
    days = int(due.get("days") or 0)
    if due.get("mode") == "spread":
        return f"Due dates spread evenly over the next {days} working days."
    return "Due today." if days == 0 else f"Due in {days} day{'s' if days != 1 else ''}."


def check_records(client: Any, batch: dict[str, Any], fmeta: dict[str, Any], ids: list[int], *, today: date | None = None) -> list[dict[str, Any]]:
    tool, model, change = batch["tool"], batch["model"], batch.get("change") or {}
    out: list[dict[str, Any]] = []
    name_f = "display_name"
    if tool == "transitions":
        b = BUTTONS[model][change["button"]]
        fields = [name_f] + (["state"] if "state" in fmeta else []) + (["active"] if "active" in fmeta else [])
        rows = {r["id"]: r for r in _x(client, model, "read", [ids, fields])}
        bad_lines: set[int] = set()
        if model == "sale.order":
            lines = _x(client, "sale.order.line", "search_read", [[("order_id", "in", ids), ("product_id", "=", False), ("display_type", "=", False)]], {"fields": ["order_id"]})
            bad_lines = {_norm(r["order_id"]) for r in lines}
        for i in ids:
            r = rows.get(i)
            if not r:
                out.append({"id": i, "name": f"#{i}", "verdict": "blocked", "reason": "Gone from Odoo."})
            elif b["states"] and r.get("state") not in b["states"]:
                out.append({"id": i, "name": r[name_f], "verdict": "blocked", "reason": b["state_msg"], "now": r.get("state")})
            elif i in bad_lines:
                out.append({"id": i, "name": r[name_f], "verdict": "blocked", "reason": "A line on these orders missing a product, you cannot confirm it.", "now": r.get("state")})
            elif model == "crm.lead" and r.get("active") is False:
                out.append({"id": i, "name": r[name_f], "verdict": "blocked", "reason": "Lost leads can't be marked as won.", "now": "lost"})
            else:
                out.append({"id": i, "name": r[name_f], "verdict": "ready", "now": r.get("state"), "after": b["label"]})
        return out
    if tool == "edit":
        f = change["field"]
        val, err = _resolve_value(client, fmeta, f, change.get("value"))
        rows = _x(client, model, "read", [ids, [name_f, f]])
        for r in rows:
            cur = _norm(r.get(f))
            if err:
                out.append({"id": r["id"], "name": r[name_f], "verdict": "blocked", "reason": err})
            elif cur == val:
                out.append({"id": r["id"], "name": r[name_f], "verdict": "no_change", "now": cur})
            else:
                out.append({"id": r["id"], "name": r[name_f], "verdict": "ready", "now": cur, "after": val,
                            "now_label": r.get(f)[1] if isinstance(r.get(f), list) else None})
        return out
    if tool == "activities":
        users = [int(u) for u in change["user_ids"]]
        live_users = {u["id"] for u in _x(client, "res.users", "search_read", [[("id", "in", users), ("share", "=", False)]], {"fields": ["id"]})}
        rows = _x(client, model, "read", [ids, [name_f]])
        dues = _due_dates(len(rows), change.get("due") or {}, today or date.today())
        missing = [u for u in users if u not in live_users]
        for k, r in enumerate(rows):
            if missing:
                out.append({"id": r["id"], "name": r[name_f], "verdict": "blocked", "reason": "One of the chosen people is not an active internal user."})
                continue
            out.append({"id": r["id"], "name": r[name_f], "verdict": "ready", "user_id": users[k % len(users)], "due": dues[k].isoformat()})
        return out
    if tool == "portal":
        rows = _x(client, "res.partner", "read", [ids, [name_f, "email", "user_ids"]])
        portal_gid = _portal_group(client)
        for r in rows:
            email = str(r.get("email") or "").strip()
            users = _x(client, "res.users", "search_read", [[("partner_id", "=", r["id"])]], {"fields": ["share", "group_ids" if _has_field(client, "res.users", "group_ids") else "groups_id", "active"], "context": {"active_test": False}}) if r.get("user_ids") or True else []
            portal_user = next((u for u in users if u.get("share") and u.get("active") and portal_gid in (u.get("groups_id") or u.get("group_ids") or [])), None)
            internal = next((u for u in users if not u.get("share") and u.get("active")), None)
            if change["action"] == "grant":
                if internal:
                    out.append({"id": r["id"], "name": r[name_f], "verdict": "blocked", "reason": "This contact is an internal user already."})
                elif portal_user:
                    out.append({"id": r["id"], "name": r[name_f], "verdict": "no_change", "reason": "Already has portal access."})
                elif not EMAIL_RE.match(email):
                    out.append({"id": r["id"], "name": r[name_f], "verdict": "blocked", "reason": "No usable email address.", "fix": "Add an email address to this contact, then check again."})
                elif _x(client, "res.users", "search_count", [[("login", "=ilike", email), ("partner_id", "!=", r["id"])]], {"context": {"active_test": False}}):
                    out.append({"id": r["id"], "name": r[name_f], "verdict": "blocked", "reason": "Another user already signs in with this email.", "fix": "Give this contact a different email."})
                else:
                    out.append({"id": r["id"], "name": r[name_f], "verdict": "ready", "email": email})
            else:
                if not portal_user:
                    out.append({"id": r["id"], "name": r[name_f], "verdict": "no_change", "reason": "Has no portal access."})
                else:
                    out.append({"id": r["id"], "name": r[name_f], "verdict": "ready"})
        return out
    if tool == "security":
        return _check_security(client, fmeta, ids, change)
    if tool == "message":
        rows = _x(client, model, "read", [ids, [name_f]])
        return [{"id": r["id"], "name": r[name_f], "verdict": "ready", "after": "internal note" if change.get("kind", "note") == "note" else "message to followers"} for r in rows]
    if tool == "recompute":
        f = change["field"]
        dep, why = recompute_dep(client, model, f)
        rows = _x(client, model, "read", [ids, [name_f, f]])
        return [{"id": r["id"], "name": r[name_f], "verdict": "blocked", "reason": why} if not dep else
                {"id": r["id"], "name": r[name_f], "verdict": "ready", "now": _norm(r.get(f)), "dep": dep} for r in rows]
    if tool == "duplicates":
        for g in change["groups"]:
            keep, merge = int(g["keep"]), [int(i) for i in g["merge"] if int(i) != int(g["keep"])]
            allids = [keep, *merge]
            live = {r["id"]: r for r in _x(client, model, "read", [allids, [name_f] + (["active"] if "active" in fmeta else [])])}
            gid = f"g{keep}"
            if len(live) != len(allids):
                out.append({"id": keep, "group": gid, "name": live.get(keep, {}).get(name_f, f"#{keep}"), "verdict": "blocked", "reason": "A record in this group is gone."})
                continue
            if not merge:
                out.append({"id": keep, "group": gid, "name": live[keep][name_f], "verdict": "no_change", "reason": "Nothing to merge."})
                continue
            money = _money_refs(client, model, merge)
            if money:
                out.append({"id": keep, "group": gid, "name": live[keep][name_f], "verdict": "blocked",
                            "reason": f"Refused by the money guard: {money}. {money_route('account.move')} Odoo's own Merge keeps accounting history right."})
                continue
            values = dict(g.get("values") or {})
            unknown = [f for f in values if f not in fmeta or fmeta[f].get("readonly")]
            if unknown:
                out.append({"id": keep, "group": gid, "name": live[keep][name_f], "verdict": "blocked", "reason": "These values can't be set: " + ", ".join(unknown)})
                continue
            out.append({"id": keep, "group": gid, "name": live[keep][name_f], "verdict": "ready", "merge": merge, "values": values,
                        "after": f"Keep #{keep}, archive {len(merge)}"})
        return out
    return out


def _portal_group(client: Any) -> int:
    rows = _x(client, "ir.model.data", "search_read", [[("module", "=", "base"), ("name", "=", "group_portal")]], {"fields": ["res_id"]})
    return int(rows[0]["res_id"]) if rows else 0


_FIELD_CACHE: dict[tuple[int, str, str], bool] = {}


def _has_field(client: Any, model: str, field: str) -> bool:
    key = (id(client), model, field)
    if key not in _FIELD_CACHE:
        _FIELD_CACHE[key] = field in _x(client, model, "fields_get", [[field]], {"attributes": ["type"]})
    return _FIELD_CACHE[key]


def _money_refs(client: Any, model: str, ids: list[int]) -> str | None:
    """Accounting documents pointing at these records (they block a merge)."""
    if model != "res.partner":
        return None
    for m, label in (("account.move", "invoices or entries"), ("account.move.line", "journal items"), ("account.payment", "payments")):
        try:
            n = _x(client, m, "search_count", [[("partner_id", "in", ids)]])
        except Exception:  # noqa: BLE001  Accounting not installed
            n = 0
        if n:
            return f"{n} {label} point at the contact to archive"
    return None


# ---------------------------------------------------------------- duplicates scan (read only)
def _clean_phone(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))[-9:]


def _name_key(v: Any) -> str:
    return " ".join(sorted(re.sub(r"[^a-z0-9 ]", " ", str(v or "").lower()).split()))


def scan_duplicates(client: Any, model: str, domain: list[Any], fields: list[str]) -> list[dict[str, Any]]:
    """Groups with Strong / Possible match and the reasons. No scores."""
    meta = _x(client, model, "fields_get", [fields + ["name"]], {"attributes": ["type", "string"]})
    use = [f for f in fields if f in meta] or ["name"]
    rows = _x(client, model, "search_read", [domain], {"fields": sorted(set(use + ["name"])), "limit": MAX_SCAN, "order": "id"})
    parent = {r["id"]: r["id"] for r in rows}
    reasons: dict[tuple[int, int], list[str]] = {}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def link(a: int, b: int, why: str) -> None:
        reasons.setdefault((min(a, b), max(a, b)), []).append(why)
        parent[find(a)] = find(b)

    for f in use:
        if f == "name":
            continue
        bucket: dict[str, list[int]] = {}
        for r in rows:
            v = r.get(f)
            key = _clean_phone(v) if f in {"phone", "mobile"} else str(v or "").strip().lower()
            if key and len(key) >= 5:
                bucket.setdefault(key, []).append(r["id"])
        for ids in bucket.values():
            for b in ids[1:]:
                link(ids[0], b, f"same {meta[f].get('string', f).lower()}")
    if "name" in use or True:
        keys = [(r["id"], _name_key(r.get("name"))) for r in rows]
        by_first: dict[str, list[tuple[int, str]]] = {}
        for i, k in keys:
            if k:
                by_first.setdefault(k[:3], []).append((i, k))
        for grp in by_first.values():
            for x in range(len(grp)):
                for y in range(x + 1, len(grp)):
                    if difflib.SequenceMatcher(None, grp[x][1], grp[y][1]).ratio() >= 0.85:
                        link(grp[x][0], grp[y][0], "similar name")
    groups: dict[int, list[int]] = {}
    for r in rows:
        groups.setdefault(find(r["id"]), []).append(r["id"])
    by_id = {r["id"]: r for r in rows}
    out = []
    for ids in groups.values():
        if len(ids) < 2:
            continue
        why = sorted({w for (a, b), ws in reasons.items() if a in ids and b in ids for w in ws})
        strong = any(w.startswith("same") for w in why) and "similar name" in why
        out.append({"ids": sorted(ids), "strength": "Strong" if strong else "Possible", "reasons": why,
                    "records": [{k: by_id[i].get(k) for k in ["id", *use]} for i in sorted(ids)], "keep": min(ids)})
    return sorted(out, key=lambda g: (g["strength"] != "Strong", g["ids"][0]))


# ---------------------------------------------------------------- run one record (or group), with Undo data
class RecordChanged(Exception):
    """The record changed after Check; it is skipped, not written."""


def run_record(client: Any, batch: dict[str, Any], fmeta: dict[str, Any], rec: dict[str, Any]) -> dict[str, Any]:
    tool, model, change = batch["tool"], batch["model"], batch.get("change") or {}
    rid = int(rec["id"])
    if tool == "transitions":
        b = BUTTONS[model][change["button"]]
        if b["states"]:
            cur = _x(client, model, "read", [[rid], ["state"]])
            if not cur or cur[0]["state"] not in b["states"]:
                raise RecordChanged(b["state_msg"])
        _x(client, model, b["method"], [[rid]])
        after = _x(client, model, "read", [[rid], ["state"]])[0].get("state") if "state" in fmeta else None
        return {"state": "done", "after": after, "undo": {"method": b["undo"]} if b.get("undo") else None}
    if tool == "edit":
        f = change["field"]
        val, err = _resolve_value(client, fmeta, f, change.get("value"))
        if err:
            raise RecordChanged(err)
        cur = _norm(_x(client, model, "read", [[rid], [f]])[0].get(f))
        if cur == val:
            return {"state": "no_change", "undo": None}
        if cur != rec.get("now"):
            raise RecordChanged("It changed in Odoo after the check.")
        _x(client, model, "write", [[rid], {f: val}])
        return {"state": "done", "after": val, "undo": {"field": f, "old": cur, "new": val}}
    if tool == "activities":
        model_id = _x(client, "ir.model", "search", [[("model", "=", model)]])[0]
        vals = {"res_model_id": model_id, "res_id": rid, "user_id": int(rec["user_id"]), "date_deadline": rec["due"],
                "summary": str(change.get("summary") or "")[:200]}
        atype = change.get("activity_type")
        if atype:
            ids = [int(atype)] if str(atype).isdigit() else _x(client, "mail.activity.type", "search", [[("name", "=", str(atype))]], {"limit": 1})
            if ids:
                vals["activity_type_id"] = ids[0]
        aid = _x(client, "mail.activity", "create", [vals])
        return {"state": "done", "after": f"activity #{aid}", "undo": {"activity_id": int(aid)}}
    if tool == "portal":
        grant = change["action"] == "grant"
        wiz = _x(client, "portal.wizard", "create", [{"partner_ids": [(6, 0, [rid])]}])
        users = _x(client, "portal.wizard.user", "search", [[("wizard_id", "=", wiz), ("partner_id", "=", rid)]])
        if not users:
            raise RecordChanged("Odoo's portal screen had no line for this contact.")
        _x(client, "portal.wizard.user", "action_grant_access" if grant else "action_revoke_access", [users])
        return {"state": "done", "after": "portal access" if grant else "no portal access", "undo": {"portal": "revoke" if grant else "grant"}}
    if tool == "security":
        gf = group_field(client)
        cur = sorted(_x(client, "res.users", "read", [[rid], [gf]])[0].get(gf) or [])
        if cur != rec.get("now"):
            raise RecordChanged("Their groups changed in Odoo after the check.")
        _x(client, "res.users", "write", [[rid], {gf: [(6, 0, rec["after"])]}])
        got = sorted(_x(client, "res.users", "read", [[rid], [gf]])[0].get(gf) or [])
        kept = sorted(set(got) - set(rec["after"]))
        return {"state": "done", "after": got, "undo": {"old": cur, "new": got},
                "notes": [f"Odoo kept {len(kept)} group(s) that other groups of this user include."] if kept else []}
    if tool == "message":
        name = _x(client, model, "read", [[rid], ["display_name"]])[0]["display_name"]
        body = html.escape(str(change["body"])).replace("{name}", html.escape(str(name))).replace("\n", "<br/>")
        sub = "mail.mt_note" if change.get("kind", "note") == "note" else "mail.mt_comment"
        mid = _x(client, model, "message_post", [[rid]], {"body": body, "message_type": "comment", "subtype_xmlid": sub})
        mid = mid[0] if isinstance(mid, list) else mid
        return {"state": "done", "after": f"message #{mid}", "undo": {"message_id": int(mid), "kind": change.get("kind", "note")}}
    if tool == "recompute":
        f, dep = change["field"], rec["dep"]
        val = _norm(_x(client, model, "read", [[rid], [dep]])[0].get(dep))
        _x(client, model, "write", [[rid], {dep: val}], {"context": TRACK_OFF})
        after = _norm(_x(client, model, "read", [[rid], [f]])[0].get(f))
        same = after == rec.get("now")
        return {"state": "no_change" if same else "done", "after": after, "undo": None,
                "notes": ["Odoo recomputed it and the value was already right."] if same else []}
    if tool == "duplicates":
        return merge_group(client, model, fmeta, rid, [int(i) for i in rec["merge"]], dict(rec.get("values") or {}))
    raise RecordChanged("Unknown tool.")


# ---------------------------------------------------------------- security, message, recompute (restored from bulk-suite)
def group_field(client: Any) -> str:
    return "group_ids" if _has_field(client, "res.users", "group_ids") else "groups_id"


def _xmlids(client: Any, model: str, ids: list[int]) -> dict[int, str]:
    rows = _x(client, "ir.model.data", "search_read", [[("model", "=", model), ("res_id", "in", ids)]], {"fields": ["module", "name", "res_id"]})
    return {r["res_id"]: f"{r['module']}.{r['name']}" for r in rows}


def resolve_groups(client: Any, refs: list[Any]) -> tuple[list[int], str | None]:
    out: list[int] = []
    for ref in refs:
        if isinstance(ref, int) or str(ref).isdigit():
            out.append(int(ref))
            continue
        mod, _, name = str(ref).partition(".")
        rows = _x(client, "ir.model.data", "search_read", [[("model", "=", "res.groups"), ("module", "=", mod), ("name", "=", name)]], {"fields": ["res_id"]})
        if not rows:
            return [], f"No group called '{ref}'."
        out.append(int(rows[0]["res_id"]))
    return out, None


def is_money_group(xmlid: str) -> bool:
    mod = xmlid.split(".")[0]
    return mod in {"account", "account_accountant", "accountant"} or mod.startswith("account_")


def security_money(client: Any, gids: list[int]) -> str | None:
    """Accounting rights stay on Odoo's own Users screen (money guard)."""
    money = [x for x in _xmlids(client, "res.groups", gids).values() if is_money_group(x)] if gids else []
    return f"Refused by the money guard: {', '.join(sorted(money))}. {SECURITY_ROUTE}" if money else None


def _check_security(client: Any, fmeta: dict[str, Any], ids: list[int], change: dict[str, Any]) -> list[dict[str, Any]]:
    add, e1 = resolve_groups(client, list(change.get("add") or []))
    rem, e2 = resolve_groups(client, list(change.get("remove") or []))
    err = e1 or e2 or security_money(client, add + rem)
    gf = group_field(client)
    rows = _x(client, "res.users", "read", [ids, ["display_name", "share", gf]])
    protected = {i for i, x in _xmlids(client, "res.users", ids).items() if x in PROTECTED_USERS}
    out = []
    for r in rows:
        cur = sorted(r.get(gf) or [])
        new = sorted((set(cur) | set(add)) - set(rem))
        base = {"id": r["id"], "name": r["display_name"]}
        if err:
            out.append({**base, "verdict": "blocked", "reason": err})
        elif r["id"] in protected:
            out.append({**base, "verdict": "blocked", "reason": "The administrator's rights are changed in Odoo itself, one at a time."})
        elif r.get("share") and add:
            out.append({**base, "verdict": "blocked", "reason": "Portal users can't be given internal groups."})
        elif new == cur:
            out.append({**base, "verdict": "no_change", "now": cur})
        else:
            out.append({**base, "verdict": "ready", "now": cur, "after": new})
    return out


def recompute_dep(client: Any, model: str, field: str) -> tuple[str | None, str]:
    """A plain stored field the computation depends on; writing it back unchanged makes Odoo recompute."""
    m = (_x(client, model, "fields_get", [[field]], {"attributes": ["depends", "store", "readonly", "type"]}) or {}).get(field) or {}
    deps = list(dict.fromkeys(str(d).split(".")[0] for d in (m.get("depends") or [])))
    if not deps:
        return None, "Odoo doesn't say what this field is computed from, so it can't be refreshed from outside."
    meta = _x(client, model, "fields_get", [deps], {"attributes": ["store", "readonly", "type"]})
    for d in deps:
        dm = meta.get(d) or {}
        if dm.get("store", True) and not dm.get("readonly") and dm.get("type") not in {"one2many", "many2many", "binary"} and d not in NEVER_EDIT:
            return d, ""
    return None, "None of the fields it's computed from can be touched safely, so Odoo won't refresh it from outside."


def _ref_fields(client: Any, model: str) -> list[tuple[str, str]]:
    rows = _x(client, "ir.model.fields", "search_read",
              [[("ttype", "=", "many2one"), ("relation", "=", model), ("store", "=", True), ("readonly", "=", False)]],
              {"fields": ["model", "name"]})
    out = []
    for r in rows:
        m = r["model"]
        if m.startswith("account.") or m in GUARDED_MODELS or m.startswith("ir.") or m.startswith("bus.") or m == "mail.followers":
            continue
        out.append((m, r["name"]))
    return out


def merge_group(client: Any, model: str, fmeta: dict[str, Any], keep: int, merge: list[int], values: dict[str, Any]) -> dict[str, Any]:
    """Move links to the kept record, set chosen values, archive the others. Records every move for Undo."""
    if _money_refs(client, model, merge):
        raise RecordChanged("Accounting documents now point at a contact to archive.")
    old_vals = {f: _norm(v) for f, v in _x(client, model, "read", [[keep], list(values)])[0].items() if f != "id"} if values else {}
    moved: list[dict[str, Any]] = []
    for m, f in _ref_fields(client, model):
        try:
            ids = _x(client, m, "search", [[(f, "in", merge)]], {"context": {"active_test": False}})
        except Exception:  # noqa: BLE001  model not searchable by this user
            continue
        if not ids:
            continue
        rows = _x(client, m, "read", [ids, [f]], {"context": {"active_test": False}})
        by_old: dict[int, list[int]] = {}
        for r in rows:
            if r["id"] in merge and m == model:
                continue
            by_old.setdefault(_norm(r[f]), []).append(r["id"])
        for old, rids in by_old.items():
            try:
                _x(client, m, "write", [rids, {f: keep}])
                moved.append({"model": m, "field": f, "ids": rids, "old": old})
            except Exception as exc:  # noqa: BLE001  Odoo refused this link: keep going, report it
                moved.append({"model": m, "field": f, "ids": rids, "old": old, "failed": fault_line(exc)})
    msgs = []
    for res_model in ("mail.message", "mail.activity"):
        key = "model" if res_model == "mail.message" else "res_model"
        for old in merge:
            ids = _x(client, res_model, "search", [[(key, "=", model), ("res_id", "=", old)]])
            if ids:
                _x(client, res_model, "write", [ids, {"res_id": keep}])
                msgs.append({"model": res_model, "ids": ids, "old": old})
    if values:
        _x(client, model, "write", [[keep], values])
    archived = []
    if "active" in fmeta:
        _x(client, model, "write", [merge, {"active": False}])
        archived = merge
    failed = [m for m in moved if m.get("failed")]
    return {"state": "done", "after": f"kept #{keep}, archived {len(archived)}",
            "undo": {"keep": keep, "old_values": old_vals, "moved": [m for m in moved if not m.get("failed")], "messages": msgs, "archived": archived},
            "notes": [f"{m['model']} link not moved: {m['failed']}" for m in failed]}


def undo_record(client: Any, batch: dict[str, Any], res: dict[str, Any]) -> dict[str, Any]:
    """Put one record back. Returns {'state', 'message'}."""
    tool, model = batch["tool"], batch["model"]
    u = res.get("undo") or {}
    rid = int(res["id"])
    if tool == "edit":
        cur = _norm(_x(client, model, "read", [[rid], [u["field"]]])[0].get(u["field"]))
        if cur != u["new"]:
            return {"state": "skipped", "message": "Changed again in Odoo since the run, so it was left alone."}
        _x(client, model, "write", [[rid], {u["field"]: u["old"]}])
        return {"state": "done", "message": "Old value back."}
    if tool == "activities":
        if not _x(client, "mail.activity", "search", [[("id", "=", u["activity_id"])]]):
            return {"state": "skipped", "message": "The activity was done or removed already."}
        _x(client, "mail.activity", "unlink", [[u["activity_id"]]])
        return {"state": "done", "message": "Open activity removed."}
    if tool == "portal":
        r = run_record(client, {**batch, "change": {"action": u["portal"]}}, {}, {"id": rid})
        return {"state": "done", "message": r["after"]}
    if tool == "transitions":
        if not u.get("method"):
            return {"state": "skipped", "message": "Odoo has no button to undo this."}
        _x(client, model, u["method"], [[rid]])
        return {"state": "done", "message": "Undone with Odoo's own button."}
    if tool == "security":
        gf = group_field(client)
        cur = sorted(_x(client, "res.users", "read", [[rid], [gf]])[0].get(gf) or [])
        if cur != u["new"]:
            return {"state": "skipped", "message": "Their groups changed again in Odoo since the run, so they were left alone."}
        _x(client, "res.users", "write", [[rid], {gf: [(6, 0, u["old"])]}])
        return {"state": "done", "message": "Old groups back."}
    if tool == "message":
        if not _x(client, "mail.message", "search", [[("id", "=", u["message_id"])]]):
            return {"state": "skipped", "message": "The message was removed already."}
        _x(client, "mail.message", "unlink", [[u["message_id"]]])
        return {"state": "done", "message": "Removed from the chatter." + (" Emails already sent can't be recalled." if u.get("kind") == "comment" else "")}
    if tool == "recompute":
        return {"state": "skipped", "message": "Odoo computes this value from the record's data, so there's nothing to put back."}
    if tool == "duplicates":
        if u.get("archived"):
            _x(client, model, "write", [u["archived"], {"active": True}])
        for mv in u.get("moved", []):
            try:
                _x(client, mv["model"], "write", [mv["ids"], {mv["field"]: mv["old"]}])
            except Exception:  # noqa: BLE001
                pass
        for mv in u.get("messages", []):
            _x(client, mv["model"], "write", [mv["ids"], {"res_id": mv["old"]}])
        if u.get("old_values"):
            _x(client, model, "write", [[u["keep"]], u["old_values"]])
        return {"state": "done", "message": f"Unarchived {len(u.get('archived', []))}, links moved back."}
    return {"state": "skipped", "message": "Nothing to undo."}


def explain(batch: dict[str, Any], installed: set[str]) -> list[str]:
    """'What Odoo will also do', only from facts code can see."""
    tool, model, change = batch["tool"], batch["model"], batch.get("change") or {}
    if tool == "transitions":
        b = BUTTONS.get(model, {}).get(str(change.get("button")), {})
        eff = list(b.get("effects", []))
        if "stock" not in installed:
            eff = [e for e in eff if "Inventory" not in e]
        return eff or ["Odoo may also send emails or create documents. Check a few records first."]
    if tool == "edit":
        return ["Changes the field only. Odoo records the change in each record's history when the field is tracked."]
    if tool == "activities":
        return [due_words(change.get("due") or {}), "Each person gets the activity in their to-do list; Odoo may email them depending on their settings."]
    if tool == "portal":
        return ["Odoo emails each contact an invitation to set a password." if change.get("action") == "grant" else "The contact can no longer sign in to the portal."]
    if tool == "security":
        return ["Changes which groups each user is in. Odoo also adds groups implied by the ones added.", "Accounting rights stay on Odoo's Users screen (money guard)."]
    if tool == "message":
        return ["Posts an internal note; nobody is emailed." if change.get("kind", "note") == "note" else "Odoo emails the followers of each record. Undo removes it from the chatter but can't recall emails."]
    if tool == "recompute":
        return ["Odoo recomputes the stored value from the record's data. Nothing else changes; history tracking is off for the touch."]
    if tool == "duplicates":
        return ["Links, messages and activities move to the kept record.", "The others are archived, not deleted, so Undo can bring them back."]
    return []
