"""BOT-V20-ACCESS: version-aware access changes (fakes for 17/18, 19, 20)."""

from __future__ import annotations

import ast
import copy as cp
from pathlib import Path
from typing import Any

import pytest

from app.bots import access as ac
from app.bots import before_image as bi
from app.bots import guard as gd
from app.bots.audit import AuditLog
from app.bots.risk import rules as rr
from app.bots.risk.rules import Refusal
from tests.test_nf_bot_kill_audit import (  # noqa: F401
    ANCHOR,
    FP,
    OWNER,
    REH,
    _clean,
    engine,
    fake_owner,
)
from tests.test_nf_bot_lockout_sim import BOT, Fake

pytestmark = pytest.mark.no_app_db
SRC = Path(ac.__file__)
MODELS = {100: "sale.order", 101: "res.partner", 102: "res.users"}
VS = (17, 19, 20)


def lk_m2o(v):
    return v[0] if isinstance(v, (list, tuple)) else v


class AFake(Fake):
    """Stateful access model on top of the lockout fake: reads by id, and writes."""

    def __init__(self, v: int) -> None:
        super().__init__(v)
        self.writes: list[tuple] = []
        for r in self.acl:
            r["name"] = f"acl {r['id']}"
        self.rules[0]["domain_force"] = "[('company_id', 'in', company_ids)]"
        self.access = [
            {
                "id": r["id"],
                "name": r["name"],
                "model_id": r["model_id"],
                "group_id": r["group_id"],
                "active": True,
                "domain": False,
                "operation": "".join(
                    c
                    for p, c in (("create", "c"), ("read", "r"), ("write", "u"), ("unlink", "d"))
                    if r[f"perm_{p}"]
                ),
            }
            for r in self.acl
        ]
        self.wd = 0
        if v < 19:  # 17/18 store implied groups on the user
            for u in self.users.values():
                u["groups"] = set(self._closure(u["groups"]))

    @property
    def vk(self) -> str:
        return "20" if self.v >= 20 else ("19" if self.v == 19 else "17-18")

    def rows(self, model: str) -> list[dict]:
        return {"ir.access": self.access, "ir.model.access": self.acl, "ir.rule": self.rules}[model]

    def _meta(self, model: str) -> dict:
        allowed = ac.ALLOWED[self.vk].get(model)
        if model in ("ir.access", "ir.model.access", "ir.rule") and allowed:
            return {f: {"type": t, "store": True} for f, t in allowed.items()}
        return super()._meta(model)

    def _user(self, i: int, fields: list[str]) -> dict:
        u = self.users[i]
        full = {
            "id": i,
            "name": u["name"],
            "login": u["login"],
            "active": u.get("active", True),
            "share": u["share"],
            self.gf: sorted(u["groups"]),
            "company_ids": u["c"],
            "company_id": [u["cid"], "c"],
            "oauth_provider_id": False,
            "lang": "en_US",
            "write_date": self.wd,
        }
        return {k: full.get(k, False) for k in ["id", *fields]}

    def _group(self, g: int, fields: list[str]) -> dict:
        n, imp = self.groups[g]
        members = sorted(i for i, u in self.users.items() if g in u["groups"])
        full = {
            "id": g,
            "name": n,
            "full_name": n,
            "display_name": n,
            "implied_ids": sorted(imp),
            ("user_ids" if self.v >= 19 else "users"): members,
            "write_date": self.wd,
        }
        return {k: full.get(k, False) for k in ["id", *fields]}

    def __call__(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        kw = kw or {}
        if model == "ir.model.data" and ("name", "=", "group_user_regular") in args[0]:
            reg = getattr(self, "regular", None)  # Odoo 20 forced implication, opt-in
            return [{"res_id": reg}] if reg else []
        if model in ("ir.ui.menu", "ir.actions.act_window"):
            if method == "fields_get":
                return {("group_ids" if self.v >= 19 else "groups_id"): {"type": "many2many"}}
            return getattr(self, "refs", {}).get(model, 0)
        if method == "search_count" and args[0] and args[0][0][0] in ("group_id", "groups"):
            f, _, (gid,) = args[0][0]
            rows = (
                self.access if model == "ir.access" else self.acl if f == "group_id" else self.rules
            )
            hit = (lambda v: gid in (v or [])) if f == "groups" else (lambda v: gid == lk_m2o(v))
            return sum(hit(r.get(f)) for r in rows)
        if method in ("write", "create", "unlink"):
            self.writes.append((model, method, cp.deepcopy(args)))
            self.wd += 1
            return self._w(model, method, args)
        if method == "fields_get" or model in self.fail:
            return super().__call__(model, method, args, kw)
        fields = kw.get("fields") or (args[1] if len(args) > 1 else [])
        dom = args[0] if args else []
        if model == "ir.model":
            if method == "read":
                return [{"id": i, "model": MODELS[i]} for i in args[0] if i in MODELS]
            if dom and dom[0][1] == "=":
                return [{"id": i, "model": m} for i, m in MODELS.items() if m == dom[0][2]]
        if model == "res.users" and method == "read":
            return [self._user(i, fields) for i in args[0] if i in self.users]
        if model == "res.groups":
            if method == "read":
                return [self._group(g, fields) for g in args[0] if g in self.groups]
            if method == "search_count":
                return sum(1 for _n, imp in self.groups.values() if dom[0][2][0] in imp)
            if method == "search_read" and fields == ["implied_ids"]:
                return [{"id": g, "implied_ids": list(i)} for g, (_n, i) in self.groups.items()]
        if model in ("ir.access", "ir.model.access", "ir.rule") and (
            model != "ir.access" or self.v >= 20
        ):
            rows = self.rows(model)
            if method == "read":
                return [
                    {**cp.deepcopy(r), "write_date": self.wd} for r in rows if r["id"] in args[0]
                ]
            if method == "search":
                return [r["id"] for r in rows if r["id"] == dom[0][2]]
            return cp.deepcopy(rows)
        if method == "search":
            return []
        return super().__call__(model, method, args, kw)

    def _w(self, model: str, method: str, args: list) -> Any:
        if model == "res.users":
            ((uid,), vals) = args
            gs = set(vals[self.gf][0][2])
            self.users[uid]["groups"] = set(self._closure(gs)) if self.v < 19 else gs
            return True
        if model == "res.groups":
            if method == "create":
                g = max(self.groups) + 1
                imp = vals_imp(args[0])
                self.groups[g] = (args[0]["name"], imp)
                return g
            if method == "unlink":
                for g in args[0]:
                    del self.groups[g]
                return True
            ((g,), vals) = args
            n, imp = self.groups[g]
            new = vals_imp(vals) if "implied_ids" in vals else imp
            if self.v < 19:  # 17/18: newly implied groups are written into members
                for u in self.users.values():
                    if g in u["groups"]:
                        u["groups"] |= set(self._closure(set(new)))
            self.groups[g] = (vals.get("name", n), new)
            return True
        rows = self.rows(model)
        if method == "create":
            i = max(r["id"] for r in rows) + 1 if rows else 1
            rows.append({"id": i, **_m2o_fix(args[0])})
            return i
        if method == "unlink":
            rows[:] = [r for r in rows if r["id"] not in args[0]]
            return True
        ((rid,), vals) = args
        for r in rows:
            if r["id"] == rid:
                r.update(_m2o_fix(vals))
        return True


def vals_imp(vals: dict) -> list[int]:
    return list(vals["implied_ids"][0][2]) if vals.get("implied_ids") else []


def _m2o_fix(vals: dict) -> dict:
    out = dict(vals)
    for f in ("model_id", "group_id"):
        if f in out and isinstance(out[f], int) and out[f]:
            out[f] = [out[f], "x"]
    if "groups" in out:
        out["groups"] = list(out["groups"][0][2])
    return out


@pytest.fixture
def gate(engine, tmp_path):  # noqa: F811
    _clean(engine)

    def make(f: AFake) -> ac.AccessLayer:
        sw = gd.KillSwitch(engine, lambda s: OWNER, grant_source=fake_owner)
        g = gd.WriteGate(sw, AuditLog(engine, anchor=ANCHOR), f, REH)
        return ac.AccessLayer(f, g, bi.ImageStore(tmp_path / "bi"), bot_uid=BOT)

    return make


_N = iter(range(10**6))


def spec(level: int = 3) -> gd.RunSpec:
    return gd.RunSpec(
        FP,
        "x",
        "bot-1",
        "R8",
        "RF-R8",
        gd.Approval(level, "alice"),
        f"k{next(_N)}",
        rehearsal_id="rh-1",
    )


def ok(p: Any) -> ac.Plan:
    assert isinstance(p, ac.Plan), p
    return p


# ---------------------------------------------------------------- versions + shape
@pytest.mark.parametrize("v", VS)
def test_detect_picks_the_version_map(v) -> None:
    f = AFake(v)
    vm = ac.detect(f)
    assert vm is ac.VMAPS[f.vk]
    assert vm.merged == (v >= 20) and vm.writes_implied == (v < 19)


def test_detect_refuses_drifted_field_type() -> None:
    f = AFake(20)
    real = f._meta
    f._meta = lambda m: {**real(m), "operation": {"type": "char"}} if m == "ir.access" else real(m)
    with pytest.raises(ac.Refused, match="operation"):
        ac.detect(f)


def test_allowed_maps_never_write_reified_or_computed_fields() -> None:
    for vk, models in ac.ALLOWED.items():
        for m, fs in models.items():
            bad = [
                x
                for x in fs
                if x.startswith(("in_group_", "sel_groups_"))
                or x in ("all_group_ids", "role", "kind", "for_read", "global")
            ]
            assert not bad, (vk, m, bad)
    assert set(ac.ALLOWED["20"]) == {"res.users", "res.groups", "ir.access"}


@pytest.mark.parametrize("v", VS)
def test_normalised_row_shape_is_identical_across_versions(v) -> None:
    f = AFake(v)
    vm = ac.detect(f)
    row = ac.norm_row(f, vm, vm.acl_model, 1)
    assert row == {
        "kind": "access",
        "id": 1,
        "name": "acl 1",
        "model": "sale.order",
        "groups": [5],
        "perms": {"read": True, "write": True, "create": True, "unlink": False},
        "domain": None,
        "active": True,
    }


# ---------------------------------------------------------------- apply + undo per op
@pytest.mark.parametrize("v", VS)
def test_user_add_group_apply_and_undo(v, gate) -> None:
    f = AFake(v)
    L = gate(f)
    p = ok(L.plan(ac.UserGroups(14, add=(6,))))  # Dana: Sales/User -> + Sales/Manager
    assert p.tier == 3 and p.values == {f.gf: [(6, 0, [1, 5, 6] if v < 19 else [5, 6])]}
    assert any("Sales / Manager" in x for x in p.lines)
    before = cp.deepcopy(f.users[14]["groups"])
    r = L.apply(p, spec())
    assert r.status == "done", r
    assert 6 in f.users[14]["groups"]
    u = L.undo(r, spec())
    assert isinstance(u, ac.Result) and u.status == "done", u
    assert f.users[14]["groups"] == before


def test_odoo20_forced_regular_user_is_previewed_and_unremovable(gate) -> None:
    f = AFake(20)
    f.regular = 1
    L = gate(f)
    p = ok(L.plan(ac.GroupSpec(name="Probe")))
    assert p.after["implied"] == [1] and p.values["implied_ids"] == [(6, 0, [1])]
    assert "cannot be removed" in L.plan(ac.GroupSpec(5, implied_remove=(1,))).reason
    assert ok(gate(AFake(17)).plan(ac.GroupSpec(name="Probe"))).after["implied"] == []


@pytest.mark.parametrize("v", VS)
def test_group_create_implied_and_undo(v, gate) -> None:
    f = AFake(v)
    L = gate(f)
    p = ok(L.plan(ac.GroupSpec(name="Probe", implied_add=(5,))))
    r = L.apply(p, spec())
    assert r.status == "done" and f.groups[r.record_id] == ("Probe", [5])
    u = L.undo(r, spec())
    assert u.status == "done" and r.record_id not in f.groups


@pytest.mark.parametrize("v", VS)
def test_group_rename_and_implied_change_undo(v, gate) -> None:
    f = AFake(v)
    L = gate(f)
    f.groups[7] = ("Empty", [])
    p = ok(L.plan(ac.GroupSpec(7, name="Renamed", implied_add=(5,))))
    r = L.apply(p, spec())
    assert r.status == "done" and f.groups[7] == ("Renamed", [5])
    assert L.undo(r, spec()).status == "done" and f.groups[7] == ("Empty", [])


@pytest.mark.parametrize("v", VS)
def test_access_row_create_modify_undo(v, gate) -> None:
    f = AFake(v)
    L = gate(f)
    p = ok(L.plan(ac.AccessRow(model="res.partner", group_id=5, perms=("read",), name="probe")))
    vm = ac.VMAPS[f.vk]
    want = (
        {"operation": "r", "domain": False}
        if v >= 20
        else {"perm_read": True, "perm_write": False, "perm_create": False, "perm_unlink": False}
    )
    assert p.model == vm.acl_model and want.items() <= p.values.items()
    r = L.apply(p, spec())
    assert r.status == "done" and r.after["perms"]["read"] and r.after["kind"] == "access"
    m = ok(L.plan(ac.AccessRow(r.record_id, perms=("read", "write"))))
    r2 = L.apply(m, spec())
    assert r2.status == "done" and r2.after["perms"]["write"]
    assert L.undo(r2, spec()).status == "done"
    assert ac.norm_row(f, vm, vm.acl_model, r.record_id)["perms"]["write"] is False
    assert L.undo(r, spec()).status == "done"
    assert all(x["id"] != r.record_id for x in f.rows(vm.acl_model))


@pytest.mark.parametrize("v", VS)
def test_record_rule_create_modify_undo_and_global_refused(v, gate) -> None:
    f = AFake(v)
    L = gate(f)
    glob = ac.RecordRule(
        model="res.partner", group_ids=(), domain="[(1, '=', 1)]", perms=("read",), name="g"
    )
    r0 = L.plan(glob)  # a global row also binds the Bot: lockout refuses it
    assert isinstance(r0, Refusal) and "Bot" in r0.reason
    op = ac.RecordRule(
        model="res.partner", group_ids=(5,), domain="[(1, '=', 1)]", perms=("read",), name="r"
    )
    p = ok(L.plan(op))
    assert p.tier == 3
    r = L.apply(p, spec())
    assert r.status == "done" and r.after["kind"] == "rule" and r.after["groups"] == [5]
    m = L.apply(ok(L.plan(ac.RecordRule(r.record_id, domain="[(0, '=', 1)]"))), spec())
    assert m.status == "done" and m.after["domain"] == "[(0, '=', 1)]"
    assert L.undo(m, spec()).status == "done"
    assert L.undo(r, spec()).status == "done"


def test_odoo20_rule_with_two_groups_refused_and_warns_grant(gate) -> None:
    L = gate(AFake(20))
    two = ac.RecordRule(
        model="res.partner", group_ids=(5, 6), domain="[]x", perms=("read",), name="r"
    )
    assert "one group" in L.plan(two).reason
    one = ok(
        L.plan(
            ac.RecordRule(
                model="res.partner", group_ids=(5,), domain="[(1,'=',1)]", perms=("read",), name="r"
            )
        )
    )
    assert any("GIVES" in x for x in one.lines)


# ---------------------------------------------------------------- refusals (fail closed)
@pytest.mark.parametrize("v", VS)
def test_lockout_refusals(v, gate) -> None:
    f = AFake(v)
    L = gate(f)
    assert isinstance(L.plan(ac.UserGroups(2, remove=(2,))), Refusal)  # last human admin
    assert isinstance(L.plan(ac.UserGroups(BOT, remove=(2,))), Refusal)  # the Bot itself
    assert f.writes == []


@pytest.mark.parametrize("v", VS)
def test_remove_still_implied_and_noop_and_unknown_refused(v, gate) -> None:
    L = gate(AFake(v))
    assert "implied" in L.plan(ac.UserGroups(11, remove=(5,))).reason  # 6 implies 5
    if v < 19:
        L.read._rpc.users[14]["groups"] = {1, 5}
    assert "no change" in L.plan(ac.UserGroups(14, add=(5,))).reason
    assert isinstance(L.plan(ac.UserGroups(14, add=(99,))), Refusal)
    assert isinstance(L.plan(ac.UserGroups(14, add=(6,), remove=(6,))), Refusal)
    assert "itself" in L.plan(ac.GroupSpec(5, implied_add=(6,))).reason


def test_implied_add_on_group_with_members_refused_only_on_17(gate) -> None:
    r17 = gate(AFake(17)).plan(ac.GroupSpec(5, implied_add=(4,)))
    assert isinstance(r17, Refusal) and "undo cannot" in r17.reason
    p20 = ok(gate(AFake(20)).plan(ac.GroupSpec(5, implied_add=(3,))))
    assert p20.tier == 3 and any("base.group_erp_manager" in w for w in p20.reasons)


@pytest.mark.parametrize("v", VS)
def test_low_approval_stale_preview_and_kill_switch_refuse(v, gate) -> None:
    f = AFake(v)
    L = gate(f)
    p = ok(L.plan(ac.UserGroups(14, add=(6,))))
    assert L.apply(p, spec(level=2)).status == "refused" and f.writes == []
    f.users[14]["groups"].add(4)
    assert "changed since" in L.apply(p, spec()).refusal.reason and f.writes == []
    f.users[14]["groups"].discard(4)
    L.gate.switch.turn_on(FP, OWNER, "test")
    assert L.apply(p, spec()).status == "refused" and f.writes == []


@pytest.mark.parametrize("v", VS)
def test_undo_refused_when_changed_since(v, gate) -> None:
    f = AFake(v)
    L = gate(f)
    r = L.apply(ok(L.plan(ac.GroupSpec(name="P"))), spec())
    f.users[14]["groups"].add(r.record_id)
    u = L.undo(r, spec())
    assert isinstance(u, Refusal) and r.record_id in f.groups


def test_unreadable_refuses(gate) -> None:
    f = AFake(17)
    f.fail.add("ir.model.data")
    assert isinstance(gate(f).plan(ac.UserGroups(14, add=(6,))), Refusal)


# ---------------------------------------------------------------- risk rules + structure
def test_access_tier_rules_are_reviewed_and_cover_lockout_core_groups() -> None:
    from app.bots import lockout as lk

    assert {lk.ADMIN_X, lk.ACCESS_X, lk.USER_X, lk.PORTAL_X} <= set(rr.ACCESS_CORE_GROUPS)
    assert all(len(w) > 15 for w in rr.ACCESS_CORE_GROUPS.values())
    assert rr.access_tier(1, core=set(), global_rule=False, security_model=False)[0] == 2
    for kw in ({"core": {"base.group_user"}}, {"global_rule": True}, {"security_model": True}):
        args = {"core": set(), "global_rule": False, "security_model": False, **kw}
        assert rr.access_tier(1, **args)[0] == 3


def test_core_group_change_is_l3_with_reason(gate) -> None:
    p = ok(gate(AFake(20)).plan(ac.UserGroups(14, add=(3,))))
    assert p.tier == 3 and any("base.group_erp_manager" in w for w in p.reasons)


def test_no_raw_rpc_writes_only_gate_paths() -> None:
    from tests.test_nf_bot_kill_audit import rpc_write_calls

    src = SRC.read_text()
    assert rpc_write_calls(src) == [] and "execute_kw" not in src and "xmlrpc" not in src
    tree = ast.parse(src)
    gate_calls = sorted(
        ast.unparse(c.func)
        for c in ast.walk(tree)
        if isinstance(c, ast.Call)
        and isinstance(c.func, ast.Attribute)
        and c.func.attr in ("run", "call")
        and "gate" in ast.unparse(c.func)
    )
    assert gate_calls == ["self.gate.call", "self.gate.call", "self.gate.run"]
    assert "self.rpc, self.read = rpc, df.ReadOnly(rpc)" in src


@pytest.mark.parametrize("v", VS)
def test_review_fixes_self_widening_refs_core_chain_wording(v, gate) -> None:
    f = AFake(v)
    L = gate(f)
    # bot (admin, group 2) gains via the implied chain: refused by lockout
    r = L.plan(ac.GroupSpec(3, implied_add=(6,)))
    assert isinstance(r, Refusal) and ("Bot" in r.reason or v < 19)  # 17/18: refused earlier
    # group create undo refuses while anything still names the group
    g = L.apply(ok(L.plan(ac.GroupSpec(name="Probe"))), spec())
    acl = L.apply(
        ok(
            L.plan(
                ac.AccessRow(model="res.partner", group_id=g.record_id, perms=("read",), name="a")
            )
        ),
        spec(),
    )
    assert "still referenced" in L.undo(g, spec()).reason
    assert L.undo(acl, spec()).status == "done"
    f.refs = {"ir.ui.menu": 1}
    assert "1 ir.ui.menu" in L.undo(g, spec()).reason
    f.refs = {}
    assert L.undo(g, spec()).status == "done"
    # a non-core group that implies a core group is core (implied chain), L3 with the reason
    p = ok(L.plan(ac.AccessRow(model="res.partner", group_id=6, perms=("read",), name="b")))
    assert p.tier == 3 and any("base.group_user" in w for w in p.reasons)
    assert "base.group_no_one" in rr.ACCESS_CORE_GROUPS
    if v >= 20:
        q = ok(
            L.plan(
                ac.RecordRule(
                    model="res.partner",
                    group_ids=(5,),
                    domain="[(1, '=', 1)]",
                    perms=("read",),
                    name="c",
                )
            )
        )
        assert any(x.startswith("WARNING (Odoo 20): this GIVES") for x in q.lines)
