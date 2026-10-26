"""Version-aware access changes for Bots (BOT-V20-ACCESS).

Typed operations (``UserGroups``, ``GroupSpec``, ``AccessRow``, ``RecordRule``) become one
Odoo write or create on the right model and fields for the live version:

* 17/18: res.users.groups_id, res.groups.users, ir.model.access + ir.rule. Adding a group to
  a user (or an implied group to a group) WRITES the implied groups into members' groups_id.
* 19 (from source only, no live sandbox): group_ids / user_ids / all_group_ids, ir.model.access
  + ir.rule, implied groups are computed (not written into members).
* 20 (JSON-RPC/JSON2 only): ir.model.access and ir.rule are merged into ``ir.access``
  (operation = letters c/r/u/d, ``domain`` = record restriction, one ``group_id`` per row).

Reads are normalised to one shape on every version (``norm_*``) so the diff preview, the
before-image and undo compare like with like. Every operation is simulated with
``lockout.simulate`` (a refusal refuses), risk-floored by the existing classifier plus the
reviewed append-only ``rules.access_tier`` (core groups / global rows = L3, else >= L2), and
executed only through ``guard.WriteGate``: writes via ``WriteGate.run`` with
``before_image.RouteA`` hooks, creates/unlinks via ``WriteGate.call``. Undo is the same path
in reverse (re-simulated, re-gated). Reads go through ``diff.ReadOnly``. Anything unread,
unrecognised or ambiguous refuses (fail closed). The layer never writes reified
in_group_N / sel_groups_* fields, all_group_ids or res.users.role.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.bots import before_image as bi
from app.bots import diff as df
from app.bots import guard as gd
from app.bots import lockout as lk
from app.bots.risk import classifier as rc
from app.bots.risk import rules as rr
from app.bots.risk.rules import Refusal

RF, MISS = "RF-R8", "access-change"
PERMS = ("read", "write", "create", "unlink")
PERM_FIELD = {p: f"perm_{p}" for p in PERMS}  # 17-19 ir.model.access / ir.rule
OP_LETTER = {"create": "c", "read": "r", "write": "u", "unlink": "d"}  # 20 ir.access
LETTER_ORDER = "crud"  # 20 selection values list letters in this order
WORD = {"read": "open", "write": "edit", "create": "create", "unlink": "delete"}
CTX = {"context": {"active_test": False}}


@dataclass(frozen=True)
class VMap:
    key: str
    user_groups: str
    group_users: str
    acl_model: str
    rule_model: str
    merged: bool  # 20: one ir.access model for access rights and record rules
    writes_implied: bool  # 17/18: implied groups are written into members' groups


VMAPS = {
    "17-18": VMap("17-18", "groups_id", "users", "ir.model.access", "ir.rule", False, True),
    "19": VMap("19", "group_ids", "user_ids", "ir.model.access", "ir.rule", False, False),
    "20": VMap("20", "group_ids", "user_ids", "ir.access", "ir.access", True, False),
}
_P = {f"perm_{p}": "boolean" for p in PERMS}
_ACL = {"name": "char", "model_id": "many2one", "group_id": "many2one", "active": "boolean", **_P}
_RULE = {"name": "char", "model_id": "many2one", "groups": "many2many", "domain_force": "text"}
_RULE |= {"active": "boolean", **_P}
_GROUP = {"name": "char", "implied_ids": "many2many"}
META = ["type", "store", "readonly"]

# Every field this layer may write, per version and model, with its fields_get type
# (drift-tested live on 17 and 20; 19 from source only; also re-checked at runtime).
ALLOWED: dict[str, dict[str, dict[str, str]]] = {
    "17-18": {
        "res.users": {"groups_id": "many2many"},
        "res.groups": _GROUP,
        "ir.model.access": _ACL,
        "ir.rule": _RULE,
    },
    "19": {
        "res.users": {"group_ids": "many2many"},
        "res.groups": _GROUP,
        "ir.model.access": _ACL,
        "ir.rule": _RULE,
    },
    "20": {
        "res.users": {"group_ids": "many2many"},
        "res.groups": _GROUP,
        "ir.access": {
            "name": "char",
            "model_id": "many2one",
            "group_id": "many2one",
            "operation": "selection",
            "domain": "char",
            "active": "boolean",
        },
    },
}


# ---------------------------------------------------------------- operations
@dataclass(frozen=True)
class UserGroups:
    user_id: int
    add: tuple[int, ...] = ()
    remove: tuple[int, ...] = ()


@dataclass(frozen=True)
class GroupSpec:
    """group_id None = create (name required)."""

    group_id: int | None = None
    name: str | None = None
    implied_add: tuple[int, ...] = ()
    implied_remove: tuple[int, ...] = ()


@dataclass(frozen=True)
class AccessRow:
    """row_id None = create. group_id 0 = every user (global). None = unchanged."""

    row_id: int | None = None
    model: str | None = None
    group_id: int | None = None
    perms: tuple[str, ...] | None = None
    active: bool | None = None
    name: str | None = None


@dataclass(frozen=True)
class RecordRule:
    """row_id None = create. group_ids () = global rule. None = unchanged."""

    row_id: int | None = None
    model: str | None = None
    group_ids: tuple[int, ...] | None = None
    domain: str | None = None
    perms: tuple[str, ...] | None = None
    active: bool | None = None
    name: str | None = None


Op = UserGroups | GroupSpec | AccessRow | RecordRule


@dataclass
class Plan:
    op: Op
    vm: VMap
    model: str
    verb: str  # write | create
    ids: list[int]
    values: dict[str, Any]
    before: dict[str, Any] | None  # normalised; None for a create
    after: dict[str, Any]  # normalised preview
    task_id: str
    risk_class: str
    tier: int
    reasons: tuple[str, ...]
    lines: list[str]
    sim: lk.LockoutSim


@dataclass
class Result:
    status: str  # done | refused | partial | tripped | duplicate | mismatch
    plan: Plan
    record_id: int | None = None
    report: gd.RunReport | None = None
    image_ref: str | None = None
    refusal: Refusal | None = None
    after: dict[str, Any] | None = None


class Refused(Exception):
    def __init__(self, why: str) -> None:
        super().__init__(why)
        self.refusal = Refusal(RF, MISS, why)


def _no(why: str) -> Refused:
    return Refused(why)


def _ids(v: Any) -> list[int]:
    return sorted(int(x) for x in (v or []))


def _m2o(v: Any) -> int | None:
    return int(v[0]) if isinstance(v, list | tuple) and v else (int(v) if v else None)


def _perms(p: Sequence[str] | None) -> dict[str, bool]:
    bad = set(p or ()) - set(PERMS)
    if p is not None and (bad or not p):
        raise _no(f"permissions must be a non-empty subset of {PERMS}")
    return {k: k in (p or ()) for k in PERMS}


# ---------------------------------------------------------------- version detection
def detect(read: Any) -> VMap:
    """Version map from live metadata, then a runtime drift check of every allowed field."""
    um = read("res.users", "fields_get", [[]], {"attributes": META})
    have = {
        r["model"]
        for r in read(
            "ir.model",
            "search_read",
            [[("model", "in", ["ir.access", "ir.model.access", "ir.rule"])]],
            {"fields": ["model"]},
        )
    }
    legacy = {"ir.model.access", "ir.rule"}
    if have == {"ir.access"} and "group_ids" in um and "groups_id" not in um:
        vm = VMAPS["20"]
    elif have == legacy and "group_ids" in um and "groups_id" not in um:
        vm = VMAPS["19"]
    elif have == legacy and "groups_id" in um and "group_ids" not in um:
        vm = VMAPS["17-18"]
    else:
        raise _no(f"access model layout not recognised ({sorted(have)})")
    for model, want in ALLOWED[vm.key].items():
        got = um if model == "res.users" else read(model, "fields_get", [[]], {"attributes": META})
        for f, t in want.items():
            m = got.get(f) or {}
            if m.get("type") != t or m.get("store") is False or m.get("readonly") is True:
                raise _no(f"{model}.{f} is {m!r} here, expected stored writable {t}: not supported")
    return vm


# ---------------------------------------------------------------- normalised reads
def _read1(read: Any, model: str, rid: int, fields: list[str]) -> dict:
    rows = read(model, "read", [[rid]], {**CTX, "fields": fields})
    if len(rows) != 1:
        raise _no(f"{model} {rid} not found")
    return rows[0]


def norm_user(read: Any, vm: VMap, uid: int) -> dict[str, Any]:
    u = _read1(read, "res.users", uid, [vm.user_groups])
    return {"kind": "user", "id": uid, "groups": _ids(u[vm.user_groups])}


def norm_group(read: Any, vm: VMap, gid: int) -> dict[str, Any]:
    g = _read1(read, "res.groups", gid, ["name", "implied_ids"])
    return {"kind": "group", "id": gid, "name": g["name"], "implied": _ids(g["implied_ids"])}


def _model_name(read: Any, mid: int) -> str:
    return _read1(read, "ir.model", mid, ["model"])["model"]


def _model_id(read: Any, model: str) -> int:
    rows = read("ir.model", "search_read", [[("model", "=", model)]], {"fields": ["id"]})
    if len(rows) != 1:
        raise _no(f"model {model} not installed")
    return rows[0]["id"]


def norm_row(read: Any, vm: VMap, model: str, rid: int) -> dict[str, Any]:
    """One shape for 17-19 ir.model.access / ir.rule and 20 ir.access."""
    if vm.merged:
        r = _read1(
            read, model, rid, ["name", "model_id", "group_id", "operation", "domain", "active"]
        )
        op = r.get("operation") or ""
        if set(op) - set(LETTER_ORDER):
            raise _no(f"ir.access operation {op!r} not understood")
        dom = r.get("domain") or None
        g = _m2o(r.get("group_id"))
        perms = {p: OP_LETTER[p] in op for p in PERMS}
        kind, groups = ("rule" if dom else "access"), ([g] if g else [])
    elif model == vm.acl_model:
        r = _read1(
            read, model, rid, ["name", "model_id", "group_id", "active", *PERM_FIELD.values()]
        )
        g = _m2o(r.get("group_id"))
        kind, groups, dom = "access", ([g] if g else []), None
        perms = {p: bool(r[PERM_FIELD[p]]) for p in PERMS}
    else:
        r = _read1(
            read,
            model,
            rid,
            ["name", "model_id", "groups", "domain_force", "active"] + list(PERM_FIELD.values()),
        )
        kind, groups, dom = "rule", _ids(r.get("groups")), (r.get("domain_force") or None)
        perms = {p: bool(r[PERM_FIELD[p]]) for p in PERMS}
    return {
        "kind": kind,
        "id": rid,
        "name": r.get("name") or "",
        "model": _model_name(read, _m2o(r["model_id"]) or 0),
        "groups": groups,
        "perms": perms,
        "domain": dom,
        "active": bool(r.get("active")),
    }


def row_values(vm: VMap, after: dict, model_id: int, fields: set[str] | None = None) -> dict:
    """Normalised row -> write values for this version (``fields`` = normalised keys changed)."""
    keys = fields or {"name", "model", "groups", "perms", "domain", "active"}
    out: dict[str, Any] = {}
    if "name" in keys:
        out["name"] = after["name"]
    if "model" in keys:
        out["model_id"] = model_id
    if "active" in keys:
        out["active"] = after["active"]
    g = after["groups"]
    if vm.merged:
        if len(g) > 1:
            raise _no("Odoo 20 rows carry one group: split the rule into one row per group")
        if "groups" in keys:
            out["group_id"] = g[0] if g else False
        if "perms" in keys:
            out["operation"] = "".join(
                c for c in LETTER_ORDER for p in PERMS if after["perms"][p] and OP_LETTER[p] == c
            )
        if "domain" in keys:
            out["domain"] = after["domain"] or False
        return out
    if after["kind"] == "access":
        if len(g) > 1:
            raise _no("an access right carries one group")
        if "groups" in keys:
            out["group_id"] = g[0] if g else False
    else:
        if "groups" in keys:
            out["groups"] = [(6, 0, list(g))]
        if "domain" in keys:
            out["domain_force"] = after["domain"]
    if "perms" in keys:
        out |= {PERM_FIELD[p]: after["perms"][p] for p in PERMS}
    return out


# ---------------------------------------------------------------- the layer
class AccessLayer:
    def __init__(
        self,
        rpc: Any,
        gate: gd.WriteGate,
        store: bi.ImageStore,
        *,
        bot_uid: int,
        route: rr.Route = "A",
        policy: rr.Policy | None = None,
    ) -> None:
        self.rpc, self.read = rpc, df.ReadOnly(rpc)
        self.gate, self.store, self.bot_uid = gate, store, bot_uid
        self.route, self.policy = route, policy or rr.Policy()
        self._vm: VMap | None = None
        self._core: dict[int, str] | None = None

    # -- facts
    def vm(self) -> VMap:
        if self._vm is None:
            self._vm = detect(self.read)
        return self._vm

    def _forced(self, vm: VMap) -> set[int]:
        """Odoo 20 server-side: every new group implies base.group_user_regular."""
        if vm.key != "20":
            return set()
        rows = self.read(
            "ir.model.data",
            "search_read",
            [
                [
                    ("module", "=", "base"),
                    ("model", "=", "res.groups"),
                    ("name", "=", "group_user_regular"),
                ]
            ],
            {"fields": ["res_id"]},
        )
        return {r["res_id"] for r in rows}

    def core(self) -> dict[int, str]:
        if self._core is None:
            names = [x.split(".")[1] for x in rr.ACCESS_CORE_GROUPS]
            rows = self.read(
                "ir.model.data",
                "search_read",
                [[("module", "=", "base"), ("model", "=", "res.groups"), ("name", "in", names)]],
                {"fields": ["name", "res_id"]},
            )
            got = {r["res_id"]: f"base.{r['name']}" for r in rows}
            if not {"base.group_system", "base.group_user"} <= set(got.values()):
                raise _no("core groups unreadable")
            self._core = got
        return self._core

    def _graph(self) -> dict[int, dict]:
        rows = self.read("res.groups", "search_read", [[]], {**CTX, "fields": ["implied_ids"]})
        return {g["id"]: {"implied": set(g["implied_ids"] or [])} for g in rows}

    def _names(self, gids: Sequence[int]) -> dict[int, str]:
        if not gids:
            return {}
        rows = self.read(
            "res.groups", "read", [sorted(set(gids))], {**CTX, "fields": ["display_name"]}
        )
        if len(rows) != len(set(gids)):
            raise _no("a named group does not exist")
        return {r["id"]: r["display_name"] for r in rows}

    def current(self, plan: Plan, rid: int | None = None) -> dict[str, Any]:
        vm, rid = plan.vm, rid if rid is not None else (plan.ids[0] if plan.ids else None)
        if rid is None:
            raise _no("nothing to read")
        if plan.model == "res.users":
            return norm_user(self.read, vm, rid)
        if plan.model == "res.groups":
            return norm_group(self.read, vm, rid)
        return norm_row(self.read, vm, plan.model, rid)

    # -- planning
    def plan(self, op: Op) -> Plan | Refusal:
        try:
            return self._plan(op)
        except Refused as exc:
            return exc.refusal
        except (lk.Unsimulated, PermissionError, KeyError, TypeError, ValueError) as exc:
            return Refusal(RF, MISS, f"could not plan: {type(exc).__name__}: {exc}")

    def _plan(self, op: Op) -> Plan:
        vm = self.vm()
        if isinstance(op, UserGroups):
            return self._user(vm, op)
        if isinstance(op, GroupSpec):
            return self._group(vm, op)
        if isinstance(op, AccessRow | RecordRule):
            return self._row(vm, op)
        raise _no(f"unknown operation {type(op).__name__}")

    def _user(self, vm: VMap, op: UserGroups) -> Plan:
        add, rem = set(op.add), set(op.remove)
        if not (add or rem) or add & rem:
            raise _no("say which groups to add or remove, never both for one group")
        before = norm_user(self.read, vm, op.user_id)
        graph = self._graph()
        if (add | rem) - set(graph):
            raise _no("a named group does not exist")
        cur = set(before["groups"])
        want = (cur - rem) | add
        if vm.writes_implied:  # 17/18 store implied groups on the user: say so in the plan
            want |= lk.closure(graph, add)
        if still := lk.closure(graph, want) & rem:
            raise _no(f"groups {sorted(still)} stay implied by another group the user keeps")
        if want == cur:
            raise _no("no change")
        after = {**before, "groups": sorted(want)}
        names = self._names(sorted(cur | want))
        gain = [names[g] for g in sorted(want - cur)]
        lose = [names[g] for g in sorted(cur - want)]
        lines = [
            f"User #{op.user_id}: "
            + "; ".join(
                x
                for x in (
                    f"adds {', '.join(gain)}" if gain else "",
                    f"removes {', '.join(lose)}" if lose else "",
                )
                if x
            )
        ]
        if vm.writes_implied and rem:
            lines.append("On Odoo 17/18 groups the removed group implied stay on the user.")
        vals = {vm.user_groups: [(6, 0, sorted(want))]}
        return self._finish(
            op,
            vm,
            "res.users",
            "write",
            [op.user_id],
            vals,
            before,
            after,
            touched=add | rem | (want ^ cur),
            glob=False,
            lines=lines,
        )

    def _group(self, vm: VMap, op: GroupSpec) -> Plan:
        add, rem = set(op.implied_add), set(op.implied_remove)
        if add & rem:
            raise _no("a group cannot be both added and removed")
        graph = self._graph()
        if (add | rem) - set(graph):
            raise _no("a named group does not exist")
        forced = self._forced(vm)
        if rem & forced:
            raise _no("Odoo 20 makes every group imply 'Is regular user': it cannot be removed")
        if op.group_id is None:
            add |= forced  # the server adds it anyway; preview it so the after-state matches
            if not (op.name or "").strip() or rem:
                raise _no("a new group needs a name and nothing to remove")
            after = {"kind": "group", "id": None, "name": op.name.strip(), "implied": sorted(add)}
            # always explicit: Odoo 20 defaults implied_ids to base.group_user otherwise
            vals: dict[str, Any] = {"name": after["name"], "implied_ids": [(6, 0, sorted(add))]}
            names = self._names(sorted(add))
            lines = [
                f"New group '{after['name']}'"
                + (f" that includes {', '.join(names.values())}" if add else "")
            ]
            return self._finish(
                op,
                vm,
                "res.groups",
                "create",
                [],
                vals,
                None,
                after,
                touched=add,
                glob=False,
                lines=lines,
            )
        before = norm_group(self.read, vm, op.group_id)
        if op.group_id in lk.closure(graph, add):
            raise _no("that would make the group include itself")
        imp = (set(before["implied"]) - rem) | add
        after = {**before, "implied": sorted(imp), "name": (op.name or before["name"]).strip()}
        vals = {}
        if after["name"] != before["name"]:
            vals["name"] = after["name"]
        if imp != set(before["implied"]):
            vals["implied_ids"] = [(6, 0, sorted(imp))]
        if not vals:
            raise _no("no change")
        if vm.writes_implied and imp - set(before["implied"]):
            members = self.read("res.groups", "read", [[op.group_id]], {"fields": [vm.group_users]})
            if members and members[0][vm.group_users]:
                raise _no(
                    "on Odoo 17/18 adding an included group writes it into every member and "
                    "undo cannot take it back: add it to the members directly instead"
                )
        names = self._names(sorted(add | rem))
        lines = [
            f"Group '{before['name']}'"
            + (f" renamed to '{after['name']}'" if "name" in vals else "")
            + (f"; now includes {', '.join(names[g] for g in sorted(add))}" if add else "")
            + (f"; no longer includes {', '.join(names[g] for g in sorted(rem))}" if rem else "")
        ]
        return self._finish(
            op,
            vm,
            "res.groups",
            "write",
            [op.group_id],
            vals,
            before,
            after,
            touched={op.group_id} | add | rem,
            glob=False,
            lines=lines,
        )

    def _row(self, vm: VMap, op: AccessRow | RecordRule) -> Plan:
        kind = "access" if isinstance(op, AccessRow) else "rule"
        model = vm.acl_model if kind == "access" else vm.rule_model
        if isinstance(op, AccessRow):
            groups = None if op.group_id is None else ([op.group_id] if op.group_id else [])
            dom = None
        else:
            groups = None if op.group_ids is None else sorted(set(op.group_ids))
            dom = op.domain
            if dom is not None and not dom.strip():
                raise _no("a record rule needs a domain")
        if op.row_id is None:
            if not op.model or not (op.name or "").strip() or op.perms is None or groups is None:
                raise _no("a new row needs model, name, permissions and group(s)")
            if kind == "rule" and dom is None:
                raise _no("a record rule needs a domain")
            before, ids = None, []
            after = {
                "kind": kind,
                "id": None,
                "name": op.name.strip(),
                "model": op.model,
                "groups": groups,
                "perms": _perms(op.perms),
                "domain": dom,
                "active": True if op.active is None else op.active,
            }
            mid, verb, changed = _model_id(self.read, op.model), "create", None
        else:
            before = norm_row(self.read, vm, model, op.row_id)
            if before["kind"] != kind:
                raise _no(f"row {op.row_id} is a {before['kind']}, not a {kind}")
            if op.model and op.model != before["model"]:
                raise _no("moving a row to another model is a new row")
            after = dict(before)
            for k, v in (
                ("name", op.name),
                ("groups", groups),
                ("domain", dom),
                ("active", op.active),
            ):
                if v is not None:
                    after[k] = v.strip() if k == "name" else v
            if op.perms is not None:
                after["perms"] = _perms(op.perms)
            changed = {k for k in after if after[k] != before[k]}
            if not changed:
                raise _no("no change")
            mid, verb, ids = _model_id(self.read, before["model"]), "write", [op.row_id]
        if not any(after["perms"].values()):
            raise _no("a row must allow at least one operation")
        if after["groups"]:
            self._names(after["groups"])
        vals = row_values(vm, after, mid, changed)
        word = "Access right" if kind == "access" else "Record rule"
        who = (
            ", ".join(self._names(after["groups"]).values())
            if after["groups"]
            else "EVERY user (global)"
        )
        ops = ", ".join(WORD[p] for p in PERMS if after["perms"][p])
        lines = [
            f"{word} '{after['name']}' on {after['model']} for {who}: {ops}"
            + (f" where {after['domain']}" if after["domain"] else "")
            + ("" if after["active"] else " (inactive)")
        ]
        if vm.merged and kind == "rule" and after["groups"]:
            lines.append(
                f"WARNING (Odoo 20): this GIVES {who} {ops} access to records matching "
                f"{after['domain']}. On Odoo 20 a group row with a domain adds access; "
                "it does not restrict access the group already has."
            )
        touched = set(after["groups"]) | set((before or {}).get("groups") or [])
        glob = not after["groups"] or (before is not None and not before["groups"])
        sens = (rr.sensitivity_floor(after["model"], None) or ("", ""))[0] in ("R8", "R8C")
        return self._finish(
            op,
            vm,
            model,
            verb,
            ids,
            vals,
            before,
            after,
            touched=touched,
            glob=glob,
            lines=lines,
            security_model=sens,
        )

    def _finish(
        self,
        op,
        vm,
        model,
        verb,
        ids,
        vals,
        before,
        after,
        *,
        touched,
        glob,
        lines,
        security_model=False,
    ) -> Plan:
        allowed = ALLOWED[vm.key][model]
        if set(vals) - set(allowed):
            raise _no(f"fields {sorted(set(vals) - set(allowed))} not allowed on {model}")
        task = f"m:{model}:{'create' if verb == 'create' else 'write'}"
        sim = lk.simulate(
            self.read, [lk.Change(model, verb, tuple(ids), dict(vals))], bot_uid=self.bot_uid
        )
        if isinstance(sim, Refusal):
            raise Refused(sim.reason) from None
        fl = rc.task_floor(task, frozenset(vals))
        if fl is None:
            raise _no(f"{task} has no risk floor")
        cls, sub = fl
        base = rr.required_tier(cls, sub, self.route, self.policy)
        cg, graph = self.core(), self._graph()  # follow the implied chain to core groups
        core = {cg[c] for g in touched if g in graph for c in lk.closure(graph, {g}) if c in cg}
        core |= {cg[g] for g in touched if g in cg}
        tier, why = rr.access_tier(base, core=core, global_rule=glob, security_model=security_model)
        tier = max(tier, sim.tier)
        return Plan(
            op,
            vm,
            model,
            verb,
            list(ids),
            vals,
            before,
            after,
            task,
            cls,
            tier,
            tuple(why),
            lines + sim.card_lines(),
            sim,
        )

    # -- execution (WriteGate only)
    def apply(self, plan: Plan, spec: gd.RunSpec) -> Result:
        return self._exec(plan, spec, plan.values, plan.before, plan.after, plan.verb)

    def _exec(self, plan, spec, values, expect_now, want, verb, rid=None) -> Result:
        if spec.approval.level < plan.tier:
            return Result(
                "refused", plan, refusal=Refusal(RF, MISS, f"needs L{plan.tier} approval")
            )
        s = dataclasses.replace(spec, task_id=plan.task_id, risk_class=plan.risk_class)
        try:
            if verb != "create" and self.current(plan, rid) != expect_now:
                raise _no("changed since the preview: plan again")
        except Refused as exc:
            return Result("refused", plan, refusal=exc.refusal)
        if verb == "create":
            try:
                new = self.gate.call(s, plan.model, "create", [values])
            except PermissionError as exc:
                return Result("refused", plan, refusal=Refusal(RF, MISS, str(exc)))
            new = int(new[0] if isinstance(new, list) else new)
            ref = self.store.put({"created": plan.model, "id": new, "after": {**want, "id": new}})
            got = self.current(plan, new)
            ok = got == {**want, "id": new}
            return Result("done" if ok else "mismatch", plan, new, None, ref, after=got)
        ids = [rid] if rid is not None else plan.ids
        db = s.db_fingerprint
        ra = bi.RouteA(
            self.read,
            self.rpc,
            self.store,
            plan=gd.plan_hash(db, s.task_id, plan.model, values, ids),
            model=plan.model,
            ids=ids,
            values=values,
            switch_check=lambda: self.gate.switch.check(db),
            approval=spec.approval.level,
        )
        rep = self.gate.run(s, plan.model, ids, values, **ra.hooks())
        img = ra.last_image
        self.last_log = list(ra.log)
        res = Result(rep.status, plan, ids[0], rep, img.ref if img else None, rep.refusal)
        if rep.status == "done":
            res.after = self.current(plan, ids[0])
            if res.after != want:
                res.status = "mismatch"
        return res

    def undo(self, done: Result, spec: gd.RunSpec) -> Result | Refusal:
        """Reverse one applied op through the same simulate + risk + gate path."""
        p = done.plan
        if done.status != "done" or done.record_id is None:
            return Refusal(RF, MISS, "only a completed change can be undone")
        try:
            now = self.current(p, done.record_id)
            if now != (done.after or {}):
                raise _no("changed since it was applied: undo refused")
            if p.verb == "create":
                return self._undo_create(p, done.record_id, spec)
            before = p.before or {}
            if p.model == "res.users":
                vals = {p.vm.user_groups: [(6, 0, before["groups"])]}
            elif p.model == "res.groups":
                vals = {"name": before["name"], "implied_ids": [(6, 0, before["implied"])]}
                vals = {k: v for k, v in vals.items() if k in p.values}
            else:
                changed = {k for k in before if before[k] != now[k]}
                vals = row_values(p.vm, before, _model_id(self.read, before["model"]), changed)
            rp = self._finish(
                p.op,
                p.vm,
                p.model,
                "write",
                [done.record_id],
                vals,
                now,
                before,
                touched=set(),
                glob=False,
                lines=[],
            )
            rp.tier = max(rp.tier, p.tier)
        except Refused as exc:
            return exc.refusal
        except (lk.Unsimulated, PermissionError, KeyError, TypeError, ValueError) as exc:
            return Refusal(RF, MISS, f"undo could not plan: {type(exc).__name__}")
        return self._exec(rp, spec, vals, now, before, "write", done.record_id)

    def _group_refs(self, vm: VMap, gid: int) -> str:
        """Access rows, record rules, menus and actions that name the group (all must be 0)."""
        out = []
        models = [(vm.acl_model, ["group_id"]), (vm.rule_model, ["groups"])][
            : 1 if vm.merged else 2
        ]
        models += [(m, ["groups_id", "group_ids"]) for m in ("ir.ui.menu", "ir.actions.act_window")]
        for model, cands in models:
            meta = self.read(model, "fields_get", [[]], {"attributes": ["type"]})
            f = next((c for c in cands if c in meta), None)
            if f is None:
                raise _no(f"{model} group field unreadable: not deleted")
            ctx = {"context": {"active_test": False}}
            n = self.read(model, "search_count", [[(f, "in", [gid])]], ctx)
            out += [f"{n} {model}"] if n else []
        return ", ".join(out)

    def _undo_create(self, p: Plan, rid: int, spec: gd.RunSpec) -> Result | Refusal:
        if p.model == "res.groups":  # lockout refuses group deletes; ours must be unused
            users = _read1(self.read, "res.groups", rid, [p.vm.group_users])[p.vm.group_users]
            used = self.read("res.groups", "search_count", [[("implied_ids", "in", [rid])]], CTX)
            if users or used:
                raise _no("the new group is in use now: remove its members first")
            refs = self._group_refs(p.vm, rid)
            if refs:
                raise _no(f"the new group is still referenced ({refs}): not deleted")
        else:
            sim = lk.simulate(
                self.read, [lk.Change(model=p.model, op="unlink", ids=(rid,))], bot_uid=self.bot_uid
            )
            if isinstance(sim, Refusal):
                return sim
        if spec.approval.level < p.tier:
            return Refusal(RF, MISS, f"needs L{p.tier} approval")
        s = dataclasses.replace(spec, task_id=f"m:{p.model}:delete", risk_class=p.risk_class)
        try:
            self.gate.call(s, p.model, "unlink", [[rid]])
        except PermissionError as exc:
            return Refusal(RF, MISS, str(exc))
        gone = not self.read(p.model, "search", [[("id", "=", rid)]], CTX)
        return Result("done" if gone else "mismatch", p, rid)
