"""Lockout simulation before any access/security change (BOT-LOCKOUT-SIM).

Reads the live access model (users, groups + implied closure, ir.model.access, ir.rule,
allowed companies, menu/action groups, auth paths) through ``diff.ReadOnly``, applies the
planned change in memory and compares before/after per user. Refuses (RF-R8
lockout-simulation) when no human admin with a working login path would remain, when the
Bot's own access shrinks, when a user/group would be deleted (archive instead), or when
anything needed is unreadable or not simulated. Every other access loss or gain escalates
to L3 with a plain-language impact list (who loses what) for the approval card. Writes are
never made here: execution goes through guard.WriteGate with a before-image.

Scope comes from the risk layer (``rules.sensitivity_floor`` == R8, plus R8 model floors)
and every in-scope model is assigned a handler or an explicit not-lockout reason
(``HANDLERS`` / ``NOT_LOCKOUT``; drift-tested against the catalogue-derived floors).
Plans are simulated step by step in the order given (the order the Bot applies them):
the admin, working-login and Bot-access invariants must hold after EVERY prefix, so a run
stopped between steps never leaves nobody with Settings. Any step that touches the Bot's own
user, groups, rows granting it access, companies, OAuth provider or API keys is refused.
Every written field must be simulated or on a reviewed allowlist (``FIELD_ALLOWLIST``,
each with a reason) and be a plain stored field in live fields_get; anything else refuses.
Odoo 17/18: res.users.groups_id, res.groups.users, reified in_group_N/sel_groups_A_B;
19/20: group_ids / user_ids / all_group_ids (cross-checked), res.groups.privilege.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.bots import before_image as bi
from app.bots import diff as df
from app.bots.risk import rules
from app.bots.risk.rules import Refusal

RF = "RF-R8"
MISS = "lockout-simulation"
ADMIN_X, ACCESS_X, USER_X, PORTAL_X = (
    "base.group_system",
    "base.group_erp_manager",
    "base.group_user",
    "base.group_portal",
)
PERMS = ("perm_read", "perm_write", "perm_create", "perm_unlink")
PERM_WORD = {
    "perm_read": "open",
    "perm_write": "edit",
    "perm_create": "create",
    "perm_unlink": "delete",
}
LOGIN_FIELDS = frozenset({"login", "password", "new_password", "totp_secret", "totp_enabled"})
CTX = {"context": {"active_test": False}}

# Every R8-floored model: how it is simulated, or why it is not a lockout change.
HANDLERS: dict[str, str] = {
    "res.users": "users",
    "res.groups": "groups",
    "ir.model.access": "acl",
    "ir.access": "acl",  # Odoo 20 name for access rights
    "ir.rule": "rule",
    "ir.ui.menu": "gated",
    "ir.actions.act_window": "gated",
    "ir.actions.actions": "gated",
    "ir.actions.server": "gated",
    "ir.actions.report": "gated",
    "ir.actions.client": "gated",
    "ir.actions.act_url": "gated",
    "res.company": "company",
    "ir.config_parameter": "blanket",
    "ir.mail_server": "blanket",
    "auth.oauth.provider": "oauth",
    "res.company.ldap": "blanket",
    "auth.passkey.key": "blanket",
    "res.users.apikeys": "apikey",
    "res.users.apikeys.description": "apikey",
    "res.users.deletion": "refuse",
    "res.groups.privilege": "display",
}
NOT_LOCKOUT: dict[str, str] = {
    "base.automation": "runs code/actions: R8 by code controls, no access-model change",
    "ir.cron": "scheduled code: R8 by code controls (its groups field is gated, see GATED_FIELDS)",
    "ir.actions.todo": "setup wizard queue: no access effect",
    "ir.actions.act_window.view": "view binding of an action: no access effect",
}
# Handled fields are simulated; allowlisted ones are reviewed as having no access effect
# (only if live fields_get shows them stored, not related, not relational to security).
HANDLED_FIELDS: dict[str, frozenset[str]] = {
    "res.users": frozenset({"groups_id", "group_ids", "active", "company_ids", "company_id"})
    | LOGIN_FIELDS,
    "res.groups": frozenset({"implied_ids", "users", "user_ids"}),
    "ir.model.access": frozenset({"active", "group_id", "model_id", *PERMS}),
    "ir.access": frozenset({"active", "group_id", "model_id", "operation", "domain"}),
    "ir.rule": frozenset({"active", "groups", "domain_force", "model_id", *PERMS}),
}
FIELD_ALLOWLIST: dict[str, dict[str, str]] = {
    "res.users": {
        "name": "display name only",
        "email": "contact address; the login is a separate field",
        "lang": "interface language",
        "tz": "timezone for dates",
        "phone": "contact detail",
        "mobile": "contact detail",
        "image_1920": "avatar picture",
        "notification_type": "inbox vs email delivery of notifications",
    },
    "res.groups": {
        "name": "label",
        "comment": "description",
        "sequence": "ordering",
        "color": "UI colour",
        "privilege_id": "19/20 display grouping (res.groups.privilege)",
        "category_id": "17/18 display grouping (ir.module.category)",
    },
    "ir.model.access": {"name": "label"},
    "ir.access": {"name": "label", "note": "description"},
    "ir.rule": {"name": "label"},
}
META_ATTRS = ["type", "relation", "store", "related", "readonly"]


def field_verdict(model: str, f: str, meta: dict) -> str | None:
    """None when writing ``f`` is simulated or reviewed harmless on this Odoo; else why not."""
    m = meta.get(f)
    if m is None:
        return f"{model}.{f} unknown on this Odoo"
    if f in HANDLED_FIELDS.get(model, ()):
        return None
    if model == "res.users" and f.startswith(("in_group_", "sel_groups_")):
        ok = all(x.isdigit() for x in f.split("_")[2:]) and len(f.split("_")) > 2
        return None if ok else f"{model}.{f} is not a reified group field"
    why = FIELD_ALLOWLIST.get(model, {}).get(f)
    if why is None:
        return f"{model}.{f} not on the reviewed allowlist (may change access)"
    rel = m.get("related")
    rel = ".".join(rel) if isinstance(rel, list | tuple) else str(rel or "")
    delegated = model == "res.users" and rel.startswith("partner_id.") and rel.count(".") == 1
    if m.get("readonly") or (rel and not delegated) or (m.get("store") is False and not delegated):
        return f"{model}.{f} is computed/related/readonly here: not simulated"
    # delegated = res.users field stored on its own partner (_inherits): contact data only
    if m.get("relation") in HANDLERS or str(m.get("relation") or "").startswith("auth."):
        return f"{model}.{f} links to a security model here"
    return None


class BotTouched(Exception):
    pass


GROUP_FIELD_NAMES = ("groups_id", "group_ids", "groups")  # gated objects' group field per major
AUTH_PARAMS = (
    "auth_signup.",
    "auth_oauth.",
    "auth_totp.",
    "auth_password_policy.",
    "web.base.url",
    "auth_ldap.",
)


def handler(model: str) -> str | None:
    return HANDLERS.get(model)


def needs_simulation(model: str, fields: Iterable[str] | None, verb: str | None = None) -> bool:
    """True when the risk layer floors this change at R8 and it is not a declared non-lockout."""
    if model in NOT_LOCKOUT and not (set(fields or ()) & set(GROUP_FIELD_NAMES)):
        return False
    f = rules.sensitivity_floor(model, None if fields is None else frozenset(fields), verb)
    return model in HANDLERS or (f is not None and f[0] == "R8")


def _r(reason: str) -> Refusal:
    return Refusal(RF, MISS, reason[:180])


class Unsimulated(Exception):
    pass


@dataclass(frozen=True)
class Change:
    model: str
    op: str  # write | create | unlink
    ids: tuple[int, ...] = ()
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Impact:
    user_id: int
    name: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class LockoutSim:
    tier: int
    admins_before: int
    admins_after: int
    removes_bot_access: bool
    impacts: tuple[Impact, ...]
    reasons: tuple[str, ...]
    revertible: bool

    @property
    def counts(self) -> dict[str, int]:
        return {
            "users_affected": len(self.impacts),
            "admins_after": self.admins_after,
            "lines": sum(len(i.lines) for i in self.impacts),
        }

    def card_lines(self) -> list[str]:
        out = [f"{self.admins_after} admin(s) keep Settings access and a working login."]
        out += [f"{i.name}: {'; '.join(i.lines)}" for i in self.impacts]
        if not self.impacts:
            out.append("No one loses or gains access.")
        return out + [f"Why L{self.tier}: {r}" for r in self.reasons]

    def gate_facts(self) -> dict[str, Any]:
        return {"admins_after": self.admins_after, "removes_bot_access": self.removes_bot_access}


# ---------------------------------------------------------------- state
@dataclass
class State:
    ver: dict[str, str]  # resolved field names
    users: dict[int, dict]
    groups: dict[int, dict]  # id -> {name, implied}
    xml: dict[str, int]
    acl: list[dict]
    rules_: list[dict]
    gated: dict[str, dict[int, set[int]]] = field(default_factory=dict)
    oauth_users: dict[int, int] = field(default_factory=dict)  # user -> provider
    providers_off: set[int] = field(default_factory=set)
    login_uncertain: set[int] = field(default_factory=set)
    companies_off: set[int] = field(default_factory=set)
    blanket: list[str] = field(default_factory=list)
    rule_touched: list[dict] = field(default_factory=list)
    gains_internal: set[int] = field(default_factory=set)
    next_id: int = -1
    dirty: set[int] = field(default_factory=set)
    regraph: bool = False
    relogin: bool = False
    acl_changed: bool = False

    def new_id(self) -> int:
        self.next_id -= 1
        return self.next_id + 1


def _m2o(v: Any) -> int | bool:
    return df.norm_read("many2one", v)


def _pick(meta: dict, *names: str) -> str:
    for n in names:
        if n in meta:
            return n
    raise Unsimulated(f"none of {names} on this Odoo")


def load(read: Any) -> State:
    um = read("res.users", "fields_get", [[]], {"attributes": ["type", "relation", "store"]})
    gm = read("res.groups", "fields_get", [[]], {"attributes": ["type", "relation", "store"]})
    ver = {
        "ugroups": "group_ids" if "group_ids" in um else _pick(um, "groups_id"),
        "gusers": _pick(gm, "user_ids", "users"),
        "all": "all_group_ids" if "all_group_ids" in um else "",
        "oauth": "oauth_provider_id" if "oauth_provider_id" in um else "",
    }
    uf = ["login", "active", "share", "name", ver["ugroups"], "company_ids", "company_id"]
    uf += [x for x in (ver["all"], ver["oauth"]) if x]
    users = {u["id"]: u for u in read("res.users", "search_read", [[]], {**CTX, "fields": uf})}
    groups = {
        g["id"]: {
            "name": g.get("full_name") or g.get("name") or f"group {g['id']}",
            "implied": set(g.get("implied_ids") or []),
        }
        for g in read(
            "res.groups",
            "search_read",
            [[]],
            {
                **CTX,
                "fields": ["name", "full_name" if "full_name" in gm else "name", "implied_ids"],
            },
        )
    }
    xd = read(
        "ir.model.data",
        "search_read",
        [
            [
                ("module", "=", "base"),
                ("model", "=", "res.groups"),
                ("name", "in", [x.split(".")[1] for x in (ADMIN_X, ACCESS_X, USER_X, PORTAL_X)]),
            ]
        ],
        {"fields": ["name", "res_id"]},
    )
    xml = {f"base.{r['name']}": r["res_id"] for r in xd}
    if ADMIN_X not in xml or USER_X not in xml:
        raise Unsimulated("admin/internal groups not resolvable")
    has = {
        m["model"]
        for m in read(
            "ir.model",
            "search_read",
            [[("model", "in", ["ir.model.access", "ir.access", "ir.rule"])]],
            {"fields": ["model"]},
        )
    }
    if "ir.model.access" in has:  # 17-19
        acl = read(
            "ir.model.access",
            "search_read",
            [[]],
            {**CTX, "fields": ["model_id", "group_id", "active", *PERMS]},
        )
    elif "ir.access" in has:  # 20: access rights + record rules merged, operation letters
        acl = [
            _acl_row(r)
            for r in read(
                "ir.access",
                "search_read",
                [[]],
                {**CTX, "fields": ["model_id", "group_id", "active", "operation", "domain"]},
            )
        ]
    else:
        raise Unsimulated("no access-rights model readable")
    rl = (
        read(
            "ir.rule",
            "search_read",
            [[]],
            {**CTX, "fields": ["name", "model_id", "groups", "active", *PERMS]},
        )
        if ("ir.rule" in has)
        else [
            dict(r, groups=[g] if (g := _m2o(r.get("group_id"))) else [])
            for r in acl
            if r.get("domain")
        ]
    )
    for u in users.values():
        u["groups"] = set(u.pop(ver["ugroups"]) or [])
        u["company_ids"] = set(u.get("company_ids") or [])
        u["company_id"] = _m2o(u.get("company_id"))
    st = State(ver, users, groups, xml, acl, rl)
    if ver["oauth"]:
        st.oauth_users = {
            i: _m2o(u.get(ver["oauth"])) for i, u in users.items() if _m2o(u.get(ver["oauth"]))
        }
    return st


OP_PERM = {
    "r": "perm_read",
    "u": "perm_write",
    "w": "perm_write",
    "c": "perm_create",
    "d": "perm_unlink",
}


def _acl_row(r: dict) -> dict:
    op = r.get("operation") or ""
    if set(op) - set(OP_PERM):
        raise Unsimulated(f"ir.access operation {op!r} not understood")
    return {**r, **{p: any(OP_PERM[c] == p for c in op) for p in PERMS}}


def closure(groups: dict[int, dict], base: Iterable[int]) -> set[int]:
    """Effective groups (implied, transitive); terminates on cycles."""
    seen: set[int] = set()
    stack = list(base)
    while stack:
        g = stack.pop()
        if g in seen:
            continue
        seen.add(g)
        if g not in groups:
            raise Unsimulated(f"group {g} unreadable")
        stack += list(groups[g]["implied"])
    return seen


def cycles(groups: dict[int, dict]) -> set[frozenset[int]]:
    """Every implied-group cycle over ALL groups, canonical as its member set (SCC)."""
    reach = {g: _reach(groups, d["implied"]) for g, d in groups.items()}
    return {
        frozenset({g} | {h for h in reach[g] if g in reach.get(h, ())})
        for g in groups
        if g in reach[g]
    }


def _reach(groups: dict[int, dict], start: Iterable[int]) -> set[int]:
    seen: set[int] = set()
    stack = list(start)
    while stack:
        g = stack.pop()
        if g in seen or g not in groups:
            continue
        seen.add(g)
        stack += list(groups[g]["implied"])
    return seen


# ---------------------------------------------------------------- applying the plan
def m2m(cur: set[int], v: Any) -> set[int]:
    out = set(cur)
    if not isinstance(v, list | tuple):
        raise Unsimulated("x2many value must be a command list")
    for c in v:
        if not isinstance(c, list | tuple) or not c or c[0] not in (3, 4, 5, 6):
            raise Unsimulated(f"x2many command {c!r} not simulated (create/update/delete)")
        if c[0] == 6:
            out = set(c[2])
        elif c[0] == 5:
            out = set()
        elif c[0] == 4:
            out.add(c[1])
        else:
            out.discard(c[1])
    return out


def _check_fields(model: str, vals: dict, meta: dict) -> None:
    for f in vals:
        if (why := field_verdict(model, f, meta)) is not None:
            raise Unsimulated(why)


def _user_fields(st: State, u: dict, vals: dict, meta: dict) -> None:
    _check_fields("res.users", vals, meta)
    for f, v in vals.items():
        if f == st.ver["ugroups"] or f in ("groups_id", "group_ids"):
            if f != st.ver["ugroups"]:
                raise Unsimulated(f"{f} is not this Odoo's user-groups field")
            u["groups"] = m2m(u["groups"], v)
        elif f.startswith("in_group_"):
            gid = int(f[9:])
            u["groups"] = (u["groups"] | {gid}) if v else (u["groups"] - {gid})
        elif f.startswith("sel_groups_"):
            ids = {int(x) for x in f[11:].split("_")}
            u["groups"] = (u["groups"] - ids) | ({v} if v else set())
        elif f == "active":
            u["active"] = bool(v)
        elif f in LOGIN_FIELDS:
            u.setdefault("login_changed", set()).add(f)
            if f == "login":
                u["login"] = v
        elif f == "company_ids":
            u["company_ids"] = m2m(u["company_ids"], v)
        elif f == "company_id":
            u["company_id"] = v
        # else: allowlisted preference field (field_verdict), no access effect


def apply(read: Any, st: State, ch: Change, meta: dict, bot: int, beff: set[int]) -> list[str]:
    """Mutates st for one step. Returns extra L3 reasons. Raises BotTouched / Unsimulated."""
    h, why = handler(ch.model), []
    vals = ch.values or {}
    if ch.model in HANDLED_FIELDS:
        _check_fields(ch.model, vals, meta.get(ch.model) or {})
    if h in (None, "refuse"):
        raise Unsimulated(f"{ch.model} {ch.op} not simulated")
    if h == "users":
        if ch.op == "unlink":
            raise Unsimulated("deleting users is refused: archive (active=False) instead")
        if ch.op == "create":
            nid = st.new_id()
            st.users[nid] = {
                "id": nid,
                "name": vals.get("name", "new user"),
                "login": vals.get("login"),
                "active": True,
                "share": False,
                "groups": set(),
                "company_ids": set(),
                "company_id": False,
            }
            targets = [nid]
        else:
            targets = list(ch.ids)
        for i in targets:
            if i == bot:
                raise BotTouched("plan changes the Bot's own user")
            if i not in st.users:
                raise Unsimulated(f"user {i} unreadable")
            _user_fields(st, st.users[i], vals, meta["res.users"])
            st.dirty.add(i)
    elif h == "groups":
        if ch.op == "unlink":
            raise Unsimulated("deleting groups is refused: remove members instead")
        targets = list(ch.ids)
        if ch.op == "create":
            nid = st.new_id()
            st.groups[nid] = {"name": vals.get("name", "new group"), "implied": set()}
            targets = [nid]
        for g in targets:
            if g not in st.groups:
                raise Unsimulated(f"group {g} unreadable")
            for f, v in vals.items():
                if f == "implied_ids":
                    new = m2m(st.groups[g]["implied"], v)
                    if g in beff and not st.groups[g]["implied"] <= new:
                        raise BotTouched("removes implied groups the Bot's own access relies on")
                    st.groups[g]["implied"] = new
                    st.regraph = True
                elif f == st.ver["gusers"]:
                    before = {u for u, d in st.users.items() if g in d["groups"]}
                    after = m2m(before, v)
                    if bot in before ^ after or any(
                        isinstance(c, list | tuple) and len(c) > 1 and c[1] == bot for c in v
                    ):
                        raise BotTouched("changes the Bot's own group membership")
                    st.dirty |= before | after
                    for u in before | after:
                        if u not in st.users:
                            raise Unsimulated(f"user {u} unreadable")
                        st.users[u]["groups"] = (st.users[u]["groups"] - {g}) | (
                            {g} if u in after else set()
                        )
                # else: allowlisted display field (field_verdict)
    elif h == "acl":
        ids = set(ch.ids)
        if ch.op == "create":
            row = {p: False for p in PERMS} | {"active": True, **vals, "id": st.new_id()}
            st.acl.append(_acl_row(row) if "operation" in vals else row)
            ids = {row["id"]}
        elif ids - {r["id"] for r in st.acl}:
            raise Unsimulated("access right unreadable")
        st.acl_changed = True
        for r in st.acl:
            if r["id"] in ids:
                gids = [_m2o(r.get("group_id"))]
                gids += [_m2o(vals.get("group_id"))] if "group_id" in vals else []
                for gid in gids:  # global rows (no group) apply to the Bot too
                    if gid is False or gid in beff:
                        raise BotTouched("changes access rows that apply to the Bot")
                if ch.op == "unlink":
                    r["active"] = False
                elif ch.op == "write":
                    r.update(_acl_row({**r, **vals}) if "operation" in vals else vals)
        if ch.model == "ir.access":  # 20: rows carry domains, i.e. they are record rules too
            st.rule_touched += [
                {"name": r.get("name"), "groups": {g} if (g := _m2o(r.get("group_id"))) else set()}
                for r in st.acl
                if r["id"] in ids
            ]
            why.append("Odoo 20 access rows carry record domains: domains are not evaluated")
    elif h == "rule":
        hit = [r for r in st.rules_ if r["id"] in ch.ids]
        if ch.op != "create" and len(hit) != len(ch.ids):
            raise Unsimulated("record rule unreadable")
        cand = [set(r.get("groups") or []) for r in hit]
        cand += [_cmd_ids(vals.get("groups"))] if ("groups" in vals or ch.op == "create") else []
        for gs in cand:  # global rules (no groups) apply to the Bot too
            if not gs or gs & beff:
                raise BotTouched("changes record rules that apply to the Bot")
        st.rule_touched += hit + (
            [{"name": vals.get("name", "new rule"), "groups": _cmd_ids(vals.get("groups"))}]
            if ch.op == "create"
            else []
        )
        if "groups" in vals:
            st.rule_touched += [
                {"name": r.get("name"), "groups": m2m(set(r.get("groups") or []), vals["groups"])}
                for r in hit
            ]
        why.append("record rules change which records users see: domains are not evaluated")
    elif h == "gated":
        gf = [f for f in vals if f in GROUP_FIELD_NAMES]
        other = sorted(set(vals) - set(gf))
        if ch.op == "unlink":
            raise Unsimulated(f"deleting {ch.model} not simulated: archive or regroup instead")
        rows = read(ch.model, "read", [list(ch.ids), gf or ["id"]], CTX) if ch.ids else []
        if len(rows) != len(ch.ids):
            raise Unsimulated(f"{ch.model} records unreadable")
        for r in rows:
            for f in gf:
                st.gated.setdefault(f"{ch.model}:{r['id']}", {})
                st.gated[f"{ch.model}:{r['id']}"] = {
                    "before": set(r.get(f) or []),
                    "after": m2m(set(r.get(f) or []), vals[f]),
                }
        if other:
            why.append(f"{ch.model} {other}: not an access change (other controls apply)")
    elif h == "company":
        if "active" in vals and not vals["active"]:
            if set(ch.ids) & st.users[bot]["company_ids"]:
                raise BotTouched("archives a company the Bot works in")
            st.companies_off |= set(ch.ids)
            st.relogin = True
        elif ch.op == "unlink":
            raise Unsimulated("deleting a company is refused")
    elif h == "oauth":
        if ch.op == "unlink" or vals.get("enabled") is False:
            if st.oauth_users.get(bot) in ch.ids:
                raise BotTouched("disables the Bot's login provider")
            st.providers_off |= set(ch.ids)
            st.relogin = True
        st.blanket.append("OAuth login provider changes: users signing in with it may lose login")
    elif h == "apikey":
        st.blanket.append("API keys change: integrations using them stop")
        rows = read(ch.model, "read", [list(ch.ids), ["user_id"]], CTX) if ch.ids else []
        if len(rows) != len(ch.ids):
            raise Unsimulated("API key owner unreadable")
        if any(_m2o(r.get("user_id")) == bot for r in rows) or (
            ch.op == "create" and _m2o(vals.get("user_id")) == bot
        ):
            raise BotTouched("changes the Bot's own API keys")
    elif h == "blanket":
        if ch.model == "ir.config_parameter":
            keys = (
                [vals.get("key", "")]
                if ch.op == "create"
                else [
                    r.get("key", "") for r in read(ch.model, "read", [list(ch.ids), ["key"]], CTX)
                ]
            )
            if not keys or any(not k for k in keys):
                raise Unsimulated("parameter key unreadable")
            if any(k.startswith(AUTH_PARAMS) for k in keys):
                st.blanket.append(f"login/signup/reset setting changes ({sorted(keys)})")
            else:
                why.append(f"parameters {sorted(keys)}: not login-related")
        elif ch.model == "ir.mail_server":
            st.blanket.append("outgoing mail server change: password-reset emails may stop")
        else:
            st.blanket.append(f"{ch.model} change: login path for its users may change")
    elif h == "display":
        why.append(f"{ch.model}: display grouping only, no access effect")
    return why


def _cmd_ids(v: Any) -> set[int]:
    return m2m(set(), v) if v else set()


# ---------------------------------------------------------------- evaluation
def _eff(st: State) -> dict[int, set[int]]:
    return {i: closure(st.groups, u["groups"]) for i, u in st.users.items()}


def _login_ok(st: State, i: int, u: dict) -> bool:
    return bool(
        u.get("active")
        and u.get("login")
        and not u.get("login_changed")
        and u["company_id"]
        and u["company_id"] in u["company_ids"]
        and not (u["company_ids"] <= st.companies_off)
        and u["company_id"] not in st.companies_off
        and st.oauth_users.get(i) not in st.providers_off
    )


def _is_admin(st: State, eff: dict[int, set[int]], i: int, bot: int) -> bool:
    u = st.users[i]
    return (
        i != bot
        and i > 0
        and st.xml[ADMIN_X] in eff[i]
        and not u.get("share")
        and _login_ok(st, i, u)
    )


def _admins(st: State, eff: dict[int, set[int]], bot: int) -> list[int]:
    return sorted(i for i in st.users if _is_admin(st, eff, i, bot))


def _acl_perms(st: State, eff: set[int]) -> set[tuple[Any, str]]:
    out = set()
    for r in st.acl:
        if not r.get("active", True):
            continue
        g = _m2o(r.get("group_id"))
        if g and g not in eff:
            continue
        m = _m2o(r.get("model_id"))
        out |= {(m, p) for p in PERMS if r.get(p)}
    return out


def simulate(rpc: Any, changes: Sequence[Change], *, bot_uid: int) -> LockoutSim | Refusal:
    read = rpc if isinstance(rpc, df.ReadOnly) else df.ReadOnly(rpc)
    if not changes:
        return _r("empty plan")
    if not isinstance(bot_uid, int) or isinstance(bot_uid, bool) or bot_uid < 1:
        return _r("bot user id unknown")
    try:
        before = load(read)
        if bot_uid not in before.users:
            return _r("bot user unreadable")
        eff0 = _eff(before)
        if before.ver["all"]:  # 19/20: Odoo's own effective groups must agree with ours
            for i, u in before.users.items():
                if u.get("active") and set(u.get(before.ver["all"]) or []) != eff0[i]:
                    return _r(f"effective groups disagree with Odoo for user {i}: not simulable")
        cyc0 = cycles(before.groups)
        a0 = _admins(before, eff0, bot_uid)
        if not a0:
            return _r("no human admin with a working login even now: fix that first")
        bot0 = (
            eff0[bot_uid],
            _acl_perms(before, eff0[bot_uid]),
            set(before.users[bot_uid]["company_ids"]),
            _login_ok(before, bot_uid, before.users[bot_uid]),
        )
        after = copy.deepcopy(before)
        eff, adm = {i: set(g) for i, g in eff0.items()}, set(a0)
        why: list[str] = []
        revertible = True
        meta = {
            m: read(m, "fields_get", [[]], {"attributes": META_ATTRS})
            for m in {c.model for c in changes}
            if m in HANDLED_FIELDS
        }
        meta.setdefault(
            "res.users", read("res.users", "fields_get", [[]], {"attributes": META_ATTRS})
        )
        ops_seen: set[tuple[str, tuple[str, ...]]] = set()
        for k, ch in enumerate(changes, 1):
            if ch.op not in ("write", "create", "unlink"):
                return _r(f"step {k}: op {ch.op!r} not simulated")
            try:
                why += apply(read, after, ch, meta, bot_uid, eff[bot_uid])
            except BotTouched as exc:
                return Refusal(RF, MISS, f"step {k}: {exc}")
            if after.regraph:  # implied graph changed: everyone, and cycles
                eff = _eff(after)
                new = cycles(after.groups) - cyc0
                if new:
                    return _r(
                        f"step {k}: plan creates a circular implied-group chain "
                        f"{sorted(sorted(c) for c in new)[:3]}"
                    )
                after.dirty |= set(after.users)
            for i in after.dirty:
                eff[i] = closure(after.groups, after.users[i]["groups"])
            for i in set(after.users) if after.relogin else after.dirty:
                (adm.add if _is_admin(after, eff, i, bot_uid) else adm.discard)(i)
            after.dirty.clear()
            after.regraph = after.relogin = False
            if not adm:
                return _r(
                    f"step {k}: would leave no working admin (Settings + login), "
                    "not counting the Bot"
                )
            ub = after.users[bot_uid]
            if (
                not bot0[0] <= eff[bot_uid]
                or not bot0[2] <= ub["company_ids"] - after.companies_off
                or (bot0[3] and not _login_ok(after, bot_uid, ub))
                or (after.acl_changed and bot0[1] - _acl_perms(after, eff[bot_uid]))
            ):
                return Refusal(RF, MISS, f"step {k}: removes the Bot's own access")
            after.acl_changed = False
            key = (ch.model, tuple(sorted(ch.values)))
            try:
                if ch.op == "write" and key not in ops_seen:
                    bi.field_ops(read, ch.model, list(key[1]))
                    ops_seen.add(key)
                elif ch.op == "unlink":
                    bi.reverse_op("unlink")
            except bi.Irreversible as exc:
                revertible = False
                why.append(f"not revertible via before-image: {exc}"[:160])
        eff1 = eff
        a1 = sorted(adm)
    except Unsimulated as exc:
        return _r(f"not simulated: {exc}")
    except Exception as exc:  # noqa: BLE001 - unreadable = refuse
        return _r(f"access model unreadable: {type(exc).__name__}")
    impacts = _impacts(before, after, eff0, eff1)
    blanket = sorted({b for b in after.blanket if not b.startswith("apikey-user:")})
    reasons = ["access/security change: R8 is always L3"]
    reasons += [f"{len(impacts)} user(s) lose or gain access"] if impacts else []
    reasons += blanket + sorted(set(why))
    if cyc0:
        reasons.append(f"{len(cyc0)} circular implied-group chain(s) already exist (unchanged)")
    return LockoutSim(3, len(a0), len(a1), False, tuple(impacts), tuple(reasons), revertible)


def _impacts(b: State, a: State, e0: dict, e1: dict) -> list[Impact]:
    gname = {
        **{g: d["name"] for g, d in b.groups.items()},
        **{g: d["name"] for g, d in a.groups.items()},
    }
    adm, intl = a.xml[ADMIN_X], a.xml[USER_X]
    out = []
    touched_rule_groups: set[int] = set()
    global_rule = False
    for r in a.rule_touched:
        gs = set(r.get("groups") or [])
        touched_rule_groups |= gs
        global_rule |= not gs
    for i, u1 in sorted(a.users.items()):
        u0 = b.users.get(i)
        lines: list[str] = []
        g0 = e0.get(i, set())
        g1 = e1[i]
        if u0 is not None and u1.get("login_changed"):
            lines.append(f"sign-in details change ({', '.join(sorted(u1['login_changed']))})")
        elif u0 is not None and _login_ok(b, i, u0) and not _login_ok(a, i, u1):
            lines.append("can no longer sign in")
        if adm in g0 and adm not in g1:
            lines.append("loses Settings (administrator) access")
        if intl not in g0 and intl in g1 and (u0 is None or u0.get("share") or i < 0):
            lines.append("becomes an internal user (back-office access, paid seat)")
        if intl in g0 and intl not in g1:
            lines.append("loses back-office (internal user) access")
        lost = sorted(gname.get(g, str(g)) for g in g0 - g1)
        gained = sorted(gname.get(g, str(g)) for g in g1 - g0)
        lines += [f"loses group {n}" for n in lost[:10]]
        lines += [f"...and {len(lost) - 10} more groups"] if len(lost) > 10 else []
        lines += [f"gains group {n}" for n in gained[:10]]
        p0, p1 = _acl_perms(b, g0), _acl_perms(a, g1)
        by_model: dict[Any, list[str]] = {}
        for m, p in sorted(p0 - p1, key=str):
            by_model.setdefault(m, []).append(PERM_WORD[p])
        lines += [f"can no longer {'/'.join(v)} model #{m}" for m, v in by_model.items()]
        gain: dict[Any, list[str]] = {}
        for m, p in sorted(p1 - p0, key=str):
            gain.setdefault(m, []).append(PERM_WORD[p])
        lines += [f"can now {'/'.join(v)} model #{m}" for m, v in gain.items()]
        for key, d in a.gated.items():
            seen0 = not d["before"] or bool(d["before"] & g0)
            seen1 = not d["after"] or bool(d["after"] & g1)
            if seen0 and not seen1:
                lines.append(f"loses menu/action {key}")
        if a.rule_touched and (global_rule or touched_rule_groups & (g0 | g1)):
            lines.append("may see different records (record rule changed)")
        if lines and (u1.get("active") or (u0 or {}).get("active")):
            out.append(Impact(i, str(u1.get("name") or u1.get("login") or i), tuple(lines)))
    return out
