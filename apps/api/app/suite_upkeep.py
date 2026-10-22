"""Configuration Suite stage 2: Upkeep (scheduled actions, files) and After an upgrade.

Descriptions come from a known catalogue first; only when code has none may the
AI suggest one (prompt 9.4), and the validator throws away anything that looks
like a method or path. Storage figures are measured, never estimated: Odoo
stores identical files once (by checksum), so space comes back only when every
copy of a file goes.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

ACCOUNTING_FILE_MODELS = frozenset({"account.move", "account.move.line", "account.payment", "account.bank.statement",
                                    "account.bank.statement.line", "account.asset", "hr.expense", "hr.expense.sheet"})

# Known scheduled actions: phrase in the action's name -> plain sentence. Never method names.
KNOWN_CRONS: list[tuple[str, str]] = [
    ("email queue", "Sends the emails waiting in the outgoing queue."),
    ("auto-vacuum", "Cleans up Odoo's own temporary records so the database stays tidy."),
    ("autovacuum", "Cleans up Odoo's own temporary records so the database stays tidy."),
    ("post draft entries", "Posts draft entries whose date has come, for entries set to post automatically."),
    ("procurement", "Re-plans purchases, manufacturing and transfers from your stock rules."),
    ("scheduler", "Re-plans purchases, manufacturing and transfers from your stock rules."),
    ("event reminder", "Sends reminders for upcoming calendar events."),
    ("digest", "Sends the periodic KPI digest emails."),
    ("notification", "Deletes old notifications."),
    ("portal users deletion", "Removes portal users who asked for their account to be deleted."),
    ("web push", "Sends browser push notifications."),
    ("currency", "Updates currency exchange rates."),
    ("lead", "Updates or assigns leads."),
    ("snailmail", "Sends letters queued for postal mail."),
    ("partner autocomplete", "Syncs company details used to autocomplete contacts."),
    ("recurring", "Creates the next documents for recurring items."),
    ("activit", "Handles activity reminders and deadlines."),
    ("sms", "Sends text messages waiting in the queue."),
    ("fetchmail", "Collects incoming email from mail servers."),
    ("incoming", "Collects incoming email from mail servers."),
    ("payment", "Processes payment transactions with payment providers."),
    ("attachment", "Cleans up files."),
    ("gc ", "Cleans up Odoo's own temporary records."),
    ("garbage", "Cleans up Odoo's own temporary records."),
    ("calendar", "Keeps calendars in sync."),
    ("followup", "Sends payment follow-up reminders."),
    ("follow-up", "Sends payment follow-up reminders."),
]
_UNIT = {"minutes": "minute", "hours": "hour", "days": "day", "weeks": "week", "months": "month"}
CODE_LIKE = re.compile(r"(\w+\.\w+\s*\(|\w+\(|\b\w+_\w+\b|/\w+/|model\.)")


def how_often(number: int, kind: str) -> str:
    unit = _UNIT.get(kind, kind.rstrip("s"))
    return f"every {unit}" if int(number) == 1 else f"every {int(number)} {unit}s"


def known_description(name: str) -> str | None:
    low = name.lower()
    for key, text in KNOWN_CRONS:
        if key in low:
            return text
    return None


def fallback_sentence(often: str, record_type: str) -> str:
    return f"Runs {often} on {record_type}."


def validate_cron_sentence(text: Any, often: str, record_type: str) -> str:
    """9.4 output check: one plain sentence, no technical names; else the exact fallback."""
    s = str(text or "").strip()
    if not s or len(s) > 200 or CODE_LIKE.search(s) or "\n" in s:
        return fallback_sentence(often, record_type)
    return s


def plain_name(name: str) -> str:
    """Scheduled action names often start with 'Module: ...'; keep it, drop technical tails."""
    s = re.sub(r"\s*\(.*?\)\s*$", "", str(name or "")).strip()
    return s if not CODE_LIKE.search(s) else re.sub(r"[_.]", " ", s)


def timeline(nextcall: str | None, number: int, kind: str, *, now: datetime, hours: int = 24, cap: int = 48) -> list[str]:
    if not nextcall:
        return []
    t = datetime.fromisoformat(str(nextcall).replace(" ", "T")).replace(tzinfo=UTC)
    step = {"minutes": timedelta(minutes=number), "hours": timedelta(hours=number), "days": timedelta(days=number),
            "weeks": timedelta(weeks=number), "months": timedelta(days=30 * number)}.get(kind, timedelta(days=number))
    if step.total_seconds() <= 0:
        return []
    out = []
    end = now + timedelta(hours=hours)
    while t < now:
        t += step
    while t <= end and len(out) < cap:
        out.append(t.isoformat())
        t += step
    return out


# ---------------------------------------------------------------- files
def file_scan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Measured storage, breakdown, unattached files and repeated copies. Accounting files are excluded."""
    by_sum: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_sum.setdefault(str(r.get("checksum") or f"id{r['id']}"), []).append(r)
    stored = sum(int(v[0].get("file_size") or 0) for v in by_sum.values())
    logical = sum(int(r.get("file_size") or 0) for r in rows)
    breakdown: dict[str, dict[str, int]] = {}
    for r in rows:
        k = r.get("res_model") or ""
        b = breakdown.setdefault(k, {"files": 0, "bytes": 0})
        b["files"] += 1
        b["bytes"] += int(r.get("file_size") or 0)
    acc = [r for r in rows if r.get("res_model") in ACCOUNTING_FILE_MODELS]
    acc_sums = {str(r.get("checksum")) for r in acc}

    def is_unattached(r: dict[str, Any]) -> bool:
        name = str(r.get("name") or "")
        return (not r.get("res_model") and not r.get("res_id") and not r.get("res_field") and not r.get("url")
                and not r.get("public") and not name.startswith(("/web/", "web.assets", "/website/")) and r.get("type", "binary") == "binary")

    unattached = [r for r in rows if is_unattached(r)]
    repeats = []
    for s, group in by_sum.items():
        offer = [r for r in group if r.get("res_model") not in ACCOUNTING_FILE_MODELS and not r.get("res_field")]
        if len(group) > 1 and len(offer) > 1:
            keep = min(offer, key=lambda r: r["id"])
            repeats.append({"checksum": s, "size": int(group[0].get("file_size") or 0), "keep": keep["id"],
                            "copies": [r["id"] for r in offer if r["id"] != keep["id"]], "all": [r["id"] for r in group]})
    return {"files": len(rows), "stored_bytes": stored, "logical_bytes": logical,
            "breakdown": sorted(({"model": k, **v} for k, v in breakdown.items()), key=lambda x: -x["bytes"]),
            "accounting_excluded": len(acc), "unattached": [_short(r) for r in unattached if str(r.get("checksum")) not in acc_sums],
            "repeats": repeats}


def _short(r: dict[str, Any]) -> dict[str, Any]:
    return {"id": r["id"], "name": r.get("name"), "size": int(r.get("file_size") or 0), "checksum": r.get("checksum"), "created": r.get("create_date")}


def space_freed(rows: list[dict[str, Any]], remove_ids: set[int]) -> int:
    """Bytes that really come back: a file's space returns only when every copy of it is removed."""
    by_sum: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_sum.setdefault(str(r.get("checksum") or f"id{r['id']}"), []).append(r)
    return sum(int(g[0].get("file_size") or 0) for g in by_sum.values() if all(r["id"] in remove_ids for r in g))


def file_verdicts(rows: list[dict[str, Any]], ids: list[int]) -> list[dict[str, Any]]:
    scan = file_scan(rows)
    unatt = {u["id"] for u in scan["unattached"]}
    copies = {c for rp in scan["repeats"] for c in rp["copies"]}
    by_id = {r["id"]: r for r in rows}
    out = []
    for i in ids:
        r = by_id.get(i)
        if r is None:
            out.append({"id": i, "verdict": "blocked", "reason": "Gone from Odoo."})
        elif r.get("res_model") in ACCOUNTING_FILE_MODELS:
            out.append({"id": i, "name": r.get("name"), "verdict": "blocked", "reason": "Files on accounting documents are never cleaned."})
        elif r.get("res_field"):
            out.append({"id": i, "name": r.get("name"), "verdict": "blocked", "reason": "This file is part of a record's field (an image or document field)."})
        elif i in unatt or i in copies:
            out.append({"id": i, "name": r.get("name"), "verdict": "ready", "size": int(r.get("file_size") or 0),
                        "why": "Not attached to anything" if i in unatt else "Another copy of the same file is kept"})
        else:
            out.append({"id": i, "name": r.get("name"), "verdict": "blocked", "reason": "Attached to a record, and it is the only copy there."})
    return out


# ---------------------------------------------------------------- after an upgrade
UPGRADE_FACTS = [
    {"key": "list_tag", "since": 18, "test": re.compile(r"<tree\b|//tree\b|\btree\["), "text": "From Odoo 18, list views are written as 'list', not 'tree'.",
     "fix": "auto"},
    {"key": "attrs_states", "since": 17, "test": re.compile(r"\battrs=|\bstates="), "text": "From Odoo 17, show/hide rules are written directly on the field, not as 'attrs' or 'states'.",
     "fix": "manual"},
    {"key": "uom_category", "since": 19, "test": re.compile(r"uom\.category|\bcategory_id\b.*uom|uom_po_id"), "text": "From Odoo 19, units have no categories and no separate purchase unit.",
     "fix": "manual"},
    {"key": "hr_contract", "since": 19, "test": re.compile(r"hr\.contract\b"), "text": "From Odoo 19, contracts are employee versions.", "fix": "manual"},
    {"key": "ir_rule_access", "since": 20, "test": re.compile(r"ir\.rule\b|ir\.model\.access\b"), "text": "From Odoo 20, access lists and record rules are one thing (access).",
     "fix": "manual"},
]


# Odoo's own data model moves between versions that affect a database even without our screen changes.
DATA_MOVES: list[dict[str, Any]] = [
    {"since": 18, "app": None, "text": "List screens are called <list> instead of <tree>; custom screens that use <tree> need the new name."},
    {"since": 19, "app": "hr_contract", "text": "Employee contracts move into employee versions (hr.version); contract reports and automations need checking."},
    {"since": 19, "app": "uom", "text": "Units of measure lose categories: each unit points at a reference unit and a factor instead."},
    {"since": 20, "app": None, "text": "Access rights and record rules are merged into one access record type (ir.access); custom access rules need re-checking."},
]


def upgrade_matrix(changes: list[dict[str, Any]], target_major: int) -> list[dict[str, Any]]:
    rows = []
    for c in changes:
        arch = str(c.get("arch") or "")
        flags = [{"key": f["key"], "text": f["text"], "fix": f["fix"]} for f in UPGRADE_FACTS if target_major >= f["since"] and f["test"].search(arch)]
        rows.append({"id": c["id"], "name": c.get("name"), "model": c.get("model"), "type": c.get("type"), "flags": flags,
                     "status": "needs_fix" if flags else "ok", "fixed_arch": fix_arch(arch, flags)})
    return rows


def fix_arch(arch: str, flags: list[dict[str, Any]]) -> str | None:
    if not flags or any(f["fix"] != "auto" for f in flags):
        return None
    out = re.sub(r"<tree\b", "<list", arch)
    out = re.sub(r"</tree>", "</list>", out)
    out = re.sub(r"//tree\b", "//list", out)
    return re.sub(r"\btree\[", "list[", out)


def xpaths_resolve(fixed_arch: str, combined_arch: str) -> tuple[bool, list[str]]:
    """Check a fix without writing: every place the change attaches must exist in the target screen."""
    import xml.etree.ElementTree as ET  # noqa: N817

    target = ET.fromstring(f"<root>{combined_arch}</root>")
    change = ET.fromstring(fixed_arch)
    missing = []
    nodes = [change] if change.tag != "data" else list(change)
    for n in nodes:
        expr = n.get("expr") if n.tag == "xpath" else None
        if n.tag == "xpath" and expr:
            path = "." + expr if expr.startswith("//") else "./" + expr.lstrip("/")
            try:
                found = target.findall(path)
            except (SyntaxError, KeyError):
                found = []
            if not found:
                missing.append(expr)
        elif n.tag != "xpath" and n.get("name"):
            if not target.findall(f".//{n.tag}[@name='{n.get('name')}']"):
                missing.append(f"{n.tag} {n.get('name')}")
    return (not missing), missing
