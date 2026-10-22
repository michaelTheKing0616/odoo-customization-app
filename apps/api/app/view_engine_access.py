"""Odoo-side lookups for "Who can see it" (Builders stage 2a).

Reads groups, users and access rights from the connected database with the
field names each Odoo major uses (17/18: groups_id, trans_implied_ids;
19/20: all_group_ids, all_implied_ids). Computes impact and the blocks that
stop admin lock-outs and hidden required fields. Writes nothing.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from app import view_engine_logic as vl

SYSTEM_GROUP = "base.group_system"
INTERNAL_GROUP = "base.group_user"
PROTECTED_MODELS_RE = re.compile(r"^(ir\.|res\.users|res\.groups|res\.company$|base\.|bus\.|auth_)")
PERMS = ("read", "write", "create", "unlink")
PERM_WORDS = {"read": "open", "write": "change", "create": "create", "unlink": "delete"}


@dataclass
class GroupCatalog:
    by_id: dict[int, dict[str, Any]] = field(default_factory=dict)
    xmlid_of: dict[int, str] = field(default_factory=dict)
    id_of: dict[str, int] = field(default_factory=dict)
    closure: dict[int, set[int]] = field(default_factory=dict)  # group -> itself + implied

    def name(self, xmlid: str) -> str:
        gid = self.id_of.get(xmlid)
        return str((self.by_id.get(gid or 0) or {}).get("name") or xmlid)

    def names(self) -> dict[str, str]:
        return {x: self.name(x) for x in self.id_of}

    def member_of_role(self, xmlid: str) -> set[str]:
        gid = self.id_of.get(xmlid)
        if gid is None:
            return set()
        return {self.xmlid_of[g] for g in self.closure.get(gid, {gid}) if g in self.xmlid_of}


def _has_field(client: Any, model: str, name: str) -> bool:
    try:
        return name in (client.execute_kw(model, "fields_get", [[name]], {"attributes": ["type"]}) or {})
    except Exception:  # noqa: BLE001
        return False


def group_catalog(client: Any) -> GroupCatalog:
    implied = "all_implied_ids" if _has_field(client, "res.groups", "all_implied_ids") else "trans_implied_ids"
    rows = client.execute_kw("res.groups", "search_read", [[]], {"fields": ["id", "display_name", implied]})
    cat = GroupCatalog()
    for r in rows or []:
        gid = int(r["id"])
        cat.by_id[gid] = {"id": gid, "name": str(r.get("display_name") or "")}
        cat.closure[gid] = {gid, *[int(x) for x in r.get(implied) or []]}
    data = client.execute_kw(
        "ir.model.data", "search_read", [[("model", "=", "res.groups")]], {"fields": ["module", "name", "res_id"]}
    )
    for d in data or []:
        gid = int(d["res_id"])
        if gid in cat.by_id and gid not in cat.xmlid_of:
            x = f"{d['module']}.{d['name']}"
            cat.xmlid_of[gid] = x
            cat.id_of[x] = gid
    return cat


def users_with_groups(client: Any, cat: GroupCatalog, user_ids: list[int] | None = None) -> list[dict[str, Any]]:
    gfield = "all_group_ids" if _has_field(client, "res.users", "all_group_ids") else "groups_id"
    domain: list[Any] = [("share", "=", False)]
    if user_ids:
        domain = [("id", "in", [int(u) for u in user_ids])]
    rows = client.execute_kw("res.users", "search_read", [domain], {"fields": ["id", "name", "login", gfield], "limit": 2000})
    out = []
    for r in rows or []:
        gids: set[int] = set()
        for g in r.get(gfield) or []:
            gids |= cat.closure.get(int(g), {int(g)})
        out.append({
            "id": int(r["id"]), "name": str(r.get("name") or ""), "login": str(r.get("login") or ""),
            "member_of": {cat.xmlid_of[g] for g in gids if g in cat.xmlid_of},
        })
    return out


def field_level_groups(client: Any, model: str, cat: GroupCatalog) -> dict[str, str]:
    rows = client.execute_kw(
        "ir.model.fields", "search_read", [[("model", "=", model), ("groups", "!=", False)]], {"fields": ["name", "groups"]}
    )
    out = {}
    for r in rows or []:
        xs = [cat.xmlid_of[int(g)] for g in r.get("groups") or [] if int(g) in cat.xmlid_of]
        if xs:
            out[str(r["name"])] = ",".join(xs)
    return out


# Odoo 20 replaced ir.model.access + ir.rule with one model, ir.access:
# "permission" rows grant operations (optionally limited by a domain) and
# "restriction" rows narrow them for everyone. Older versions keep the two models.
OP_LETTERS = (("create", "c"), ("read", "r"), ("write", "u"), ("unlink", "d"))


def access_model_name(client: Any) -> str:
    cached = getattr(client, "_ingenium_access_model", None)
    if cached:
        return str(cached)
    try:
        found = client.execute_kw("ir.model", "search_count", [[("model", "=", "ir.model.access")]])
        name = "ir.model.access" if found else "ir.access"
    except Exception:  # noqa: BLE001
        name = "ir.model.access"
    try:
        setattr(client, "_ingenium_access_model", name)
    except Exception:  # noqa: BLE001
        pass
    return name


def perms_to_operation(perms: dict[str, Any]) -> str | None:
    letters = "".join(letter for p, letter in OP_LETTERS if perms.get(p))
    return letters or None


def operation_to_perms(operation: str | None) -> dict[str, bool]:
    return {p: letter in (operation or "") for p, letter in OP_LETTERS}


def plain_perms(values: dict[str, Any]) -> dict[str, bool]:
    """Accept {read: ..} or {perm_read: ..} and return {read: ..}."""
    return {p: bool(values.get(p, values.get(f"perm_{p}", False))) for p in PERMS}


def row_values(backend: str, perms: dict[str, Any]) -> dict[str, Any]:
    """Odoo write values for a row's permissions on this backend."""
    clean = plain_perms(perms)
    if backend == "ir.access":
        op = perms_to_operation(clean)
        return {"operation": op, "active": True} if op else {"active": False}
    return {f"perm_{p}": clean[p] for p in PERMS}


def read_row_perms(client: Any, backend: str, row_id: int) -> dict[str, bool]:
    if backend == "ir.access":
        row = client.execute_kw("ir.access", "read", [[int(row_id)]], {"fields": ["operation", "active"]})[0]
        return operation_to_perms(row.get("operation") if row.get("active", True) else "")
    row = client.execute_kw("ir.model.access", "read", [[int(row_id)]], {"fields": [f"perm_{p}" for p in PERMS]})[0]
    return plain_perms(row)


def access_rows(client: Any, model: str, cat: GroupCatalog) -> list[dict[str, Any]]:
    backend = access_model_name(client)
    if backend == "ir.access":
        rows = client.execute_kw(
            "ir.access", "search_read", [[("model_id.model", "=", model), ("kind", "=", "permission")]],
            {"fields": ["id", "name", "group_id", "operation", "domain", "active"]},
        )
    else:
        rows = client.execute_kw(
            "ir.model.access", "search_read", [[("model_id.model", "=", model)]],
            {"fields": ["id", "name", "group_id", "perm_read", "perm_write", "perm_create", "perm_unlink", "active"]},
        )
    out = []
    for r in rows or []:
        gid = int(r["group_id"][0]) if r.get("group_id") else None
        perms = operation_to_perms(r.get("operation")) if backend == "ir.access" else plain_perms(r)
        out.append({
            "id": int(r["id"]), "name": str(r.get("name") or ""),
            "group": cat.xmlid_of.get(gid) if gid else None, "group_id": gid,
            "group_name": cat.by_id.get(gid, {}).get("name") if gid else "Everyone",
            **perms,
            "domain": str(r.get("domain") or "") if backend == "ir.access" else "",
            "ingenium": str(r.get("name") or "").startswith("ingenium_access"),
        })
    return out


def grant_domain(rows: list[dict[str, Any]], member_of: set[str]) -> tuple[str | None, bool]:
    """Odoo 20: the record limit a new permission row should carry so a grant
    doesn't widen which records the role reaches. (domain or None, ok)."""
    reach = [r for r in rows if r.get("read") and (r.get("group") is None and r.get("group_id") is None or r.get("group") in member_of)]
    if not reach:
        return None, True
    if any(not (r.get("domain") or "").strip() or (r.get("domain") or "").strip() == "[]" for r in reach):
        return None, True
    domains = {str(r.get("domain")).strip() for r in reach}
    if len(domains) == 1:
        return domains.pop(), True
    return None, False


def effective_perms(rows: list[dict[str, Any]], member_of: set[str]) -> dict[str, bool]:
    out = {p: False for p in PERMS}
    for r in rows:
        if r.get("group") is None and r.get("group_id") is None or (r.get("group") in member_of):
            for p in PERMS:
                out[p] = out[p] or bool(r.get(p))
    return out


def record_rules(client: Any, model: str, cat: GroupCatalog) -> list[dict[str, Any]]:
    if access_model_name(client) == "ir.access":
        rows = client.execute_kw(
            "ir.access", "search_read", [[("model_id.model", "=", model)]],
            {"fields": ["id", "name", "group_id", "operation", "domain", "kind"]},
        )
        out = []
        for r in rows or []:
            dom = str(r.get("domain") or "")
            if r.get("kind") == "permission" and not dom.strip():
                continue  # plain grants are shown in the access table
            gname = cat.by_id.get(int(r["group_id"][0]), {}).get("name") if r.get("group_id") else None
            out.append({
                "id": int(r["id"]), "name": str(r.get("name") or ""),
                "applies_to": gname or "Everyone",
                "domain": dom, "plain": explain_domain(dom),
                "perms": [p for p, v in operation_to_perms(r.get("operation")).items() if v],
                "kind": "limit" if r.get("kind") == "restriction" else "grant_with_limit",
            })
        return out
    rows = client.execute_kw(
        "ir.rule", "search_read", [[("model_id.model", "=", model)]],
        {"fields": ["id", "name", "groups", "domain_force", "perm_read", "perm_write", "perm_create", "perm_unlink", "global"]},
    )
    out = []
    for r in rows or []:
        groups = [cat.by_id.get(int(g), {}).get("name", str(g)) for g in r.get("groups") or []]
        out.append({
            "id": int(r["id"]), "name": str(r.get("name") or ""),
            "applies_to": "Everyone" if r.get("global") else ", ".join(groups),
            "domain": str(r.get("domain_force") or ""),
            "plain": explain_domain(str(r.get("domain_force") or "")),
            "perms": [p for p in PERMS if r.get(f"perm_{p}")],
            "kind": "limit",
        })
    return out


_DOMAIN_VALUE_WORDS = {
    "user.id": "the person themself", "user.company_id.id": "their company", "company_ids": "their companies",
    "user.partner_id.id": "the person themself",
}


def explain_domain(domain: str) -> str | None:
    """'[('user_id','=',user.id)]' -> 'user id is the person themself'. None when too complex."""
    raw = (domain or "").strip()
    if raw in {"", "[]", "[(1, '=', 1)]", "[(1,'=',1)]"}:
        return "All records"
    try:
        tree = ast.parse(raw, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(tree, ast.List):
        return None
    bits: list[str] = []
    joiner = " and "
    for el in tree.elts:
        if isinstance(el, ast.Constant) and el.value in {"|", "&"}:
            joiner = " or " if el.value == "|" else " and "
            continue
        if not (isinstance(el, (ast.Tuple, ast.List)) and len(el.elts) == 3):
            return None
        left, op, right = el.elts
        if not (isinstance(left, ast.Constant) and isinstance(op, ast.Constant)):
            return None
        field_words = str(left.value).replace(".", " ").replace("_id", "").replace("_ids", "").replace("_", " ")
        rsrc = ast.unparse(right)
        rwords = next((w for k, w in _DOMAIN_VALUE_WORDS.items() if k in rsrc), None) or (
            str(right.value) if isinstance(right, ast.Constant) else None)
        if rwords is None:
            return None
        opw = {"=": "is", "!=": "is not", "in": "is one of", "not in": "is not one of", "child_of": "is within"}.get(str(op.value))
        if not opw:
            return None
        if rwords == "False":
            bits.append(f"{field_words} is {'empty' if opw == 'is' else 'filled in'}")
        else:
            bits.append(f"{field_words} {opw} {rwords}")
    return joiner.join(bits) if bits else None


def _names(people: list[dict[str, Any]], limit: int = 3) -> str:
    names = [p["name"] for p in people[:limit]]
    rest = len(people) - len(names)
    if rest > 0:
        return ", ".join(names) + f" and {rest} more"
    if len(names) > 1:
        return ", ".join(names[:-1]) + " and " + names[-1]
    return names[0] if names else ""


def field_access_impact(
    *, label: str, users: list[dict[str, Any]], before_groups: str | None, edit: list[str], see: list[str],
    field_required: bool, has_default: bool, can_create_member: Any, connection_uid: int, cat: GroupCatalog,
) -> dict[str, Any]:
    """Plain impact + blocks for a field-level 'Who can see it' change."""
    after_groups = ",".join(edit if edit else see)
    before = {u["id"] for u in users if vl.groups_allow(before_groups, u["member_of"])}
    after = {u["id"] for u in users if vl.groups_allow(after_groups, u["member_of"])}
    by_id = {u["id"]: u for u in users}
    lose = sorted((by_id[i] for i in before - after), key=lambda u: u["name"])
    gain = sorted((by_id[i] for i in after - before), key=lambda u: u["name"])
    impact: list[str] = []
    blocks: list[str] = []
    warnings: list[str] = []
    if lose:
        impact.append(f"{len(lose)} {'person loses' if len(lose) == 1 else 'people lose'} sight of {label}: {_names(lose)}.")
    if gain:
        impact.append(f"{len(gain)} {'person starts' if len(gain) == 1 else 'people start'} seeing {label}: {_names(gain)}.")
    if see:
        read_only = [u for u in users if vl.groups_allow(",".join(see), u["member_of"])]
        if read_only:
            impact.append(f"{len(read_only)} can see {label} but not change it.")
        if edit:
            both = [u for u in users if vl.groups_allow(",".join(edit), u["member_of"]) and vl.groups_allow(",".join(see), u["member_of"])]
            if both:
                blocks.append(
                    f"{_names(both)} {'is' if len(both) == 1 else 'are'} in both a 'Can edit' and a 'Can only see' role, "
                    "so Odoo would show them the field twice. Change one of the roles."
                )
    if not impact:
        impact.append(f"Nobody's view of {label} changes.")
    admins_losing = [u for u in lose if SYSTEM_GROUP in u["member_of"]]
    if admins_losing:
        blocks.append(
            f"Administrators ({_names(admins_losing)}) would lose sight of {label}. "
            f"Add the role '{cat.name(SYSTEM_GROUP)}' or choose Everyone."
        )
    if any(u["id"] == connection_uid for u in lose):
        blocks.append(f"The Odoo login Ingenium uses would lose sight of {label}, so you couldn't edit it here any more.")
    if field_required:
        creators = [u for u in lose if can_create_member(u["member_of"])]
        if creators:
            msg = (f"{label} must be filled in, and {_names(creators)} can create records but wouldn't see it.")
            if has_default:
                warnings.append(msg + " Odoo fills in a default value, so saving still works.")
            else:
                blocks.append(msg + " Keep it visible for them or give it a default value in Odoo.")
    return {"impact": impact, "blocks": blocks, "warnings": warnings,
            "lose": [{"id": u["id"], "name": u["name"]} for u in lose[:50]],
            "gain": [{"id": u["id"], "name": u["name"]} for u in gain[:50]]}


def model_access_plan(rows: list[dict[str, Any]], changes: list[dict[str, Any]], cat: GroupCatalog) -> tuple[list[dict[str, Any]], list[str]]:
    """Turn desired per-role permissions into row actions. Grants add/extend an
    Ingenium row; revokes switch off the role's own rows (copying what stays).
    Returns (actions, blocks)."""
    actions: list[dict[str, Any]] = []
    blocks: list[str] = []
    for ch in changes:
        g = str(ch.get("group") or "")
        if g not in cat.id_of:
            blocks.append("A role you picked no longer exists in this database. Reload and try again.")
            continue
        own = [r for r in rows if r.get("group") == g and (r.get("active", True))]
        member = cat.member_of_role(g)
        current = effective_perms(rows, member)
        want = {p: bool(ch.get(p, current[p])) for p in PERMS}
        revoke = [p for p in PERMS if current[p] and not want[p]]
        grant = [p for p in PERMS if want[p] and not current[p]]
        for p in revoke:
            direct = any(r.get(p) for r in own)
            via = [r for r in rows if r.get(p) and r.get("group") != g and (r.get("group") is None or r.get("group") in member)]
            if via:
                src = via[0]
                who = src.get("group_name") or "Everyone"
                blocks.append(f"{cat.name(g)} can {PERM_WORDS[p]} these records through '{who}'. Change it there instead.")
            elif not direct:
                blocks.append(f"Couldn't find where {cat.name(g)} gets the right to {PERM_WORDS[p]}.")
        if blocks:
            continue
        if not revoke and not grant:
            continue
        stay = {p: want[p] for p in PERMS}
        ing = next((r for r in own if r.get("ingenium")), None)
        if revoke:
            for r in own:
                if not r.get("ingenium") and any(r.get(p) for p in revoke):
                    actions.append({"type": "deactivate", "id": r["id"], "group": g})
        if ing:
            actions.append({"type": "write", "id": ing["id"], "group": g, "perms": stay})
        elif any(stay.values()):
            actions.append({"type": "create", "group": g, "group_id": cat.id_of[g], "perms": stay})
    return actions, blocks


def apply_plan_to_rows(rows: list[dict[str, Any]], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [dict(r) for r in rows]
    for a in actions:
        if a["type"] == "deactivate":
            out = [r for r in out if r["id"] != a["id"]]
        elif a["type"] == "write":
            for r in out:
                if r["id"] == a["id"]:
                    r.update(a["perms"])
        elif a["type"] == "create":
            out.append({"id": -1, "group": a["group"], "group_id": a["group_id"], **a["perms"], "ingenium": True})
    return out


def model_access_impact(model_label: str, users: list[dict[str, Any]], rows_before: list[dict[str, Any]],
                        rows_after: list[dict[str, Any]], connection_uid: int) -> tuple[list[str], list[str]]:
    impact: list[str] = []
    blocks: list[str] = []
    for p in PERMS:
        lose = [u for u in users if effective_perms(rows_before, u["member_of"])[p] and not effective_perms(rows_after, u["member_of"])[p]]
        gain = [u for u in users if not effective_perms(rows_before, u["member_of"])[p] and effective_perms(rows_after, u["member_of"])[p]]
        if lose:
            impact.append(f"{len(lose)} {'person' if len(lose) == 1 else 'people'} can no longer {PERM_WORDS[p]} {model_label}: {_names(lose)}.")
            admins = [u for u in lose if SYSTEM_GROUP in u["member_of"]]
            if admins:
                blocks.append(f"Administrators ({_names(admins)}) would lose the right to {PERM_WORDS[p]} {model_label}. Nothing was changed.")
            if any(u["id"] == connection_uid for u in lose):
                blocks.append(f"The Odoo login Ingenium uses would lose the right to {PERM_WORDS[p]} {model_label}.")
        if gain:
            impact.append(f"{len(gain)} {'person' if len(gain) == 1 else 'people'} can now {PERM_WORDS[p]} {model_label}: {_names(gain)}.")
    if not impact:
        impact.append("Nobody's access changes.")
    return impact, blocks
