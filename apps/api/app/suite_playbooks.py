"""Suite playbooks (spec §16 ideas 6, 7, 9): they only DRAFT Change batches. Each batch still goes through
Check, approval and Run like any other, and each run has its own undo. Nothing here writes to Odoo."""

from __future__ import annotations

from typing import Any

# Record types a leaver usually owns, with the field that names the owner and what "still open" means.
OWNED = [
    ("crm.lead", "user_id", [("active", "=", True), ("probability", "<", 100)], "open leads and opportunities"),
    ("sale.order", "user_id", [("state", "in", ["draft", "sent", "sale"])], "open quotations and orders"),
    ("purchase.order", "user_id", [("state", "in", ["draft", "sent", "to approve", "purchase"])], "open purchase orders"),
    ("project.task", "user_ids", [("stage_id.fold", "=", False)], "open tasks"),
    ("helpdesk.ticket", "user_id", [("stage_id.fold", "=", False)], "open tickets"),
    ("res.partner", "user_id", [], "customers they look after"),
    ("mail.activity", "user_id", [], "planned activities"),
]


def _x(client: Any, model: str, method: str, args: list[Any] | None = None, kw: dict[str, Any] | None = None) -> Any:
    return client.execute_kw(model, method, args or [], kw or {})


def _has(client: Any, model: str) -> bool:
    try:
        return bool(_x(client, "ir.model", "search_count", [[("model", "=", model)]]))
    except Exception:  # noqa: BLE001
        return False


def _uname(client: Any, uid: int) -> str:
    r = _x(client, "res.users", "read", [[uid]], {"fields": ["name"]})
    if not r:
        raise ValueError(f"There is no user number {uid}.")
    return r[0]["name"]


def reassign(client: Any, model: str, field: str, from_user: int, to_users: list[int], domain: list[Any] | None = None) -> dict[str, Any]:
    """Idea 7: move records from one person to others, split fairly (round robin, oldest first)."""
    if not to_users:
        raise ValueError("Choose at least one person to move the records to.")
    ids = _x(client, model, "search", [[(field, "=", from_user), *(domain or [])]], {"order": "id", "limit": 5000})
    split: dict[int, list[int]] = {u: [] for u in to_users}
    for n, i in enumerate(ids):
        split[to_users[n % len(to_users)]].append(i)
    who = _uname(client, from_user)
    batches = [{"tool": "edit", "model": model, "ids": part, "change": {"field": field, "value": u},
                "name": f"Move {len(part)} from {who} to {_uname(client, u)}"} for u, part in split.items() if part]
    return {"records": len(ids), "batches": batches,
            "summary": f"{len(ids)} record(s) of {who} split over {len(to_users)} person(s)." if ids else f"{who} owns none of these."}


def leaver(client: Any, from_user: int, to_user: int) -> dict[str, Any]:
    """Idea 6: hand everything a leaver owns to a colleague, then remove their access (a separate step)."""
    who, to = _uname(client, from_user), _uname(client, to_user)
    batches, found = [], []
    for model, field, dom, words in OWNED:
        if not _has(client, model):
            continue
        meta = _x(client, model, "fields_get", [[field]], {"attributes": ["type"]})
        if field not in meta:
            continue
        if meta[field]["type"] == "many2many":
            found.append({"what": words, "count": _x(client, model, "search_count", [[(field, "in", [from_user]), *dom]]),
                          "how": "Shared with others, so it isn't moved in bulk. Open the list and add the colleague."})
            continue
        ids = _x(client, model, "search", [[(field, "=", from_user), *dom]], {"limit": 5000})
        found.append({"what": words, "count": len(ids), "how": f"Moved to {to}" if ids else "Nothing to move"})
        if ids:
            batches.append({"tool": "edit", "model": model, "ids": ids, "change": {"field": field, "value": to_user},
                            "name": f"Leaver {who}: {words} to {to}"})
    return {"leaver": who, "to": to, "found": found, "batches": batches,
            "then": f"After these runs, remove {who}'s access in Access (archive the user). Followers stay on records for history."}


TAG_MODELS = {"res.partner.category": "Contact tags", "crm.tag": "CRM tags", "project.tags": "Project tags", "product.tag": "Product tags"}


def tags(client: Any, model: str) -> dict[str, Any]:
    """Idea 9 (look part): every tag with how many records use it, near-duplicate names grouped."""
    if model not in TAG_MODELS or not _has(client, model):
        raise ValueError("Choose one of: " + ", ".join(TAG_MODELS.values()))
    rows = _x(client, model, "search_read", [[]], {"fields": ["name"], "limit": 2000})
    users = {"res.partner.category": ("res.partner", "category_id"), "crm.tag": ("crm.lead", "tag_ids"),
             "project.tags": ("project.task", "tag_ids"), "product.tag": ("product.template", "product_tag_ids")}[model]
    out, groups = [], {}
    for r in rows:
        n = _x(client, users[0], "search_count", [[(users[1], "in", [r["id"]])]]) if _has(client, users[0]) else 0
        out.append({"id": r["id"], "tag": r["name"], "used_by": n})
        groups.setdefault(" ".join(str(r["name"]).lower().replace("-", " ").split()), []).append(r["name"])
    return {"kind": TAG_MODELS[model], "tags": sorted(out, key=lambda t: t["used_by"]),
            "unused": [t["tag"] for t in out if t["used_by"] == 0],
            "look_alike": [g for g in groups.values() if len(g) > 1]}


def tag_rename(model: str, tag_id: int, new_name: str) -> dict[str, Any]:
    return {"batches": [{"tool": "edit", "model": model, "ids": [tag_id], "change": {"field": "name", "value": new_name},
                         "name": f"Rename tag to {new_name}"}]}
