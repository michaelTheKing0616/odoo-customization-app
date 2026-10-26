"""BOT-R6-DELETE-MERGE: archive / delete / partner merge via the walker + gate (fake Odoo)."""

from __future__ import annotations

import copy as cp
from typing import Any

import pytest

from app.bots import removal as rm
from app.bots import snapshot as sn
from app.bots import walker as wk
from app.bots.risk.rules import Refusal
from tests.test_nf_bot_kill_audit import FP, engine, rpc_write_calls  # noqa: F401
from tests.test_nf_bot_walker import F, W, m2o, spec  # noqa: F401
from tests.test_nf_bot_walker import Odoo as WOdoo

pytestmark = [pytest.mark.no_app_db]
VS = (17, 18, 19, 20)
API = rm.__file__.rsplit("/app/", 1)[0]


class Odoo(WOdoo):
    def __init__(self, v: int) -> None:
        super().__init__(v)
        self.meta["res.partner"]["active"] = F("boolean")
        self.meta["sale.order"]["partner_id"]["on_delete"] = "restrict"
        self.meta["account.move"]["partner_id"]["on_delete"] = "restrict"
        self.meta["account.move.line"] = {
            "move_id": m2o("account.move", on_delete="cascade"),
            "partner_id": m2o("res.partner", on_delete="set null"),
            "reconciled": F("boolean"),
        }
        self.meta["mail.message"] = {"res_model": F("char"), "res_id": F("integer")}
        self.meta[rm.WIZ] = {
            "partner_ids": F("many2many", relation="res.partner"),
            "dst_partner_id": m2o("res.partner"),
        }
        for m in ("account.move.line", "mail.message", rm.WIZ):
            self.rows[m] = {}
        self.rows["ir.model"] = {i: {"model": m} for i, m in enumerate(self.meta, 500)}
        for r in self.rows["res.partner"].values():
            r["active"] = True
        self.rows["res.partner"][20] = {"name": "Azure dup", "active": True}
        self.rows["res.partner"][21] = {"name": "Lonely", "active": True}
        self.rows["sale.order"][22] = {"name": "S22", "partner_id": 20, "state": "draft"}
        self.rows["mail.message"][23] = {"res_model": "res.partner", "res_id": 20}
        self.rows["account.move.line"][24] = {"move_id": 8, "reconciled": False}
        for rs in self.rows.values():
            for r in rs.values():
                r.setdefault("write_date", "2026-10-01 00:00:00")
                r.setdefault("create_uid", 2)
        self.meta["res.company"]["partner_id"] = m2o("res.partner")
        self.user_partners: set[int] = set()
        self.xmlids: set[int] = set()
        self.drop_relink = False
        self.bot_cos, self.hidden_cos, self.multi_grp = {1, 2}, set(), False

    def _fields(self, dom: list) -> list[dict]:
        d = {f: v for f, _, v in dom}
        out = []
        for model, fs in self.meta.items():
            for name, m in fs.items():
                if "relation" in d and m.get("relation") != d["relation"]:
                    continue
                if "ttype" in d and m["type"] not in d["ttype"]:
                    continue
                if "name" in d and name != d["name"]:
                    continue
                if not m.get("store", True):
                    continue
                od = m.get("on_delete", "set null")
                out.append(
                    {
                        "model": model,
                        "name": name,
                        "ttype": m["type"],
                        "on_delete": od,
                        "store": True,
                    }
                )
        return out

    def __call__(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        keys = {x[0] for x in (args[0] if args else []) if isinstance(x, (list, tuple))}
        if model == "ir.model.fields" and method == "search_read" and keys & {"relation", "name"}:
            return self._fields(args[0])
        if model == "ir.rule" and method == "search_count":
            return 0
        if model == "res.users" and method == "search" and args[0][0][0] == "partner_id":
            return sorted(set(args[0][0][2]) & self.user_partners)
        if model in self.fail:
            raise RuntimeError("unreadable")
        if model == "res.users" and method == "read" and args[1] == ["company_ids"]:
            return [{"id": i, "company_ids": sorted(self.bot_cos)} for i in args[0]]
        if model == "res.users" and method == "search_count" and keys & {"groups_id", "group_ids"}:
            return int(self.multi_grp)
        if model == "ir.model.data" and method == "search_read" and "module" in keys:
            return [{"id": 9, "res_id": 5}]
        if model == "res.company" and method == "search_read":
            got = super().__call__(model, method, args, kw)
            return [r for r in got if r["id"] not in self.hidden_cos]
        if model == "res.company" and method == "read" and len(args[0]) == 1:
            i = args[0][0]
            if i in self.hidden_cos:
                raise RuntimeError("odoo.exceptions.AccessError")
            if i not in self.rows["res.company"]:
                raise RuntimeError("odoo.exceptions.MissingError")
        if model == "ir.model.data" and method == "search" and keys == {"model", "res_id"}:
            return sorted(set(args[0][1][2]) & self.xmlids)
        if model == rm.WIZ and method == "action_merge":
            self.calls.append((model, method))
            self._merge(self.rows[rm.WIZ][args[0][0]])
            return True
        return super().__call__(model, method, args, kw)

    def _merge(self, wz: dict) -> None:
        dst = wz["dst_partner_id"]
        src = [i for i in wz["partner_ids"] if i != dst]
        for model, fs in self.meta.items():
            for f, m in fs.items():
                if m.get("relation") != "res.partner" or self.drop_relink:
                    continue
                for r in self.rows[model].values():
                    if m["type"] == "many2one" and r.get(f) in src:
                        r[f] = dst
                    if m["type"] == "many2many" and set(r.get(f) or []) & set(src):
                        r[f] = sorted((set(r[f]) - set(src)) | {dst})
        for r in self.rows["mail.message"].values():
            if r["res_model"] == "res.partner" and r["res_id"] in src:
                r["res_id"] = dst
        for i in src:
            self.rows["res.partner"].pop(i)


def snap(sid: str = "snap:abc", fp: str = FP, ok: bool = True) -> sn.Verified:
    v = sn.Verified.__new__(sn.Verified)
    v.snap = type("S", (), {"id": sid, "fingerprint": fp})()
    v.refusal = None if ok else Refusal("RF-R3", "snapshot-proof", "x")
    return v


@pytest.fixture
def R(W):  # noqa: N802, F811
    def make(v: int = 17):
        w, o = W(v, o=Odoo(v))
        return rm.Removal(w), o

    return make


def ok(p: Any) -> rm.Plan:
    assert isinstance(p, rm.Plan), p
    return p


def no(p: Any, part: str) -> None:
    assert isinstance(p, Refusal), p
    assert part in p.reason, p.reason


def writes(o: Odoo) -> list:
    return [c for c in o.calls if c[1] in ("write", "create", "unlink", "action_merge")]


@pytest.mark.parametrize("v", VS)
def test_archive_preferred_and_undoable(R, v) -> None:
    r, o = R(v)
    p = ok(r.plan_remove("res.partner", [21], "a1"))
    assert p.kind == "archive" and p.walk.steps[0].step.values == {"active": False}
    res = r.apply(p, spec())
    assert res.status == "done", res.refusal
    assert o.rows["res.partner"][21]["active"] is False


def test_delete_needs_explicit_ask(R) -> None:
    r, o = R()
    no(r.plan_remove("res.partner.category", [5], "d0"), "asked for explicitly")
    assert writes(o) == []


@pytest.mark.parametrize("v", VS)
def test_delete_l3_typed_count_and_snapshot(R, v) -> None:
    r, o = R(v)
    p = ok(r.plan_remove("res.partner", [21], "d1", allow_delete=True))
    assert p.kind == "delete" and p.tier == 3 and p.count >= 1
    s = spec(level=3)
    for typed, sv, part in (
        (None, snap(), "typed"),
        (str(p.count + 1), snap(), "typed"),
        (str(p.count), None, "snapshot"),
        (str(p.count), snap(fp="other"), "another database"),
        (str(p.count), snap(ok=False), "not verified"),
    ):
        res = r.apply(p, s, typed=typed, snapshot=sv)
        assert res.status == "refused" and part in res.refusal.reason, (part, res.refusal)
    res = r.apply(p, s, typed=str(p.count), snapshot=snap())
    assert res.status == "refused" and "snapshot" in res.refusal.reason  # spec not bound
    assert writes(o) == []
    s = spec(level=3)
    s = type(s)(**{**s.__dict__, "snapshot_id": "snap:abc"})
    res = r.apply(p, s, typed=str(p.count), snapshot=snap())
    assert res.status == "done", res.refusal
    assert 21 not in o.rows["res.partner"]


def test_delete_refused_on_restrict_and_final_rows(R) -> None:
    r, o = R()
    no(r.plan_remove("res.partner", [20], "d2", allow_delete=True), "restrict")
    o.rows["account.move.line"][24]["reconciled"] = True
    no(r.plan_remove("account.move", [8], "d3", allow_delete=True), "reconciled")
    no(r.plan_remove("account.move", [9], "d4", allow_delete=True), "posted")
    assert writes(o) == []


def test_delete_stale_count_refused_at_job_open(R) -> None:
    r, o = R()
    p = ok(r.plan_remove("res.partner", [21], "d5", allow_delete=True))
    o.rows["account.move.line"][30] = {
        "partner_id": 21,
        "reconciled": False,
        "write_date": "x",
        "create_uid": 2,
    }
    s = spec(level=3)
    s = type(s)(**{**s.__dict__, "snapshot_id": "snap:abc"})
    res = r.apply(p, s, typed=str(p.count), snapshot=snap())
    assert res.status != "done" and 21 in o.rows["res.partner"]
    assert "changed since approval" in res.refusal.reason, res.refusal


@pytest.mark.parametrize("v", VS)
def test_merge_full_image_apply_and_undo(R, v) -> None:
    r, o = R(v)
    p = ok(r.plan_merge("res.partner", [3, 20], 3, "m1"))
    rel = {(e["model"], e["field"]): e["ids"] for e in p.image["relinked"]}
    assert rel[("sale.order", "partner_id")] == [22]
    assert rel[("mail.message", "res_id")] == [23]
    assert [x["id"] for x in p.image["partners"]] == [3, 20] and p.count == 3
    assert r.w.store.get(p.image_ref)["src"] == [20]
    s = spec(level=3)
    s = type(s)(**{**s.__dict__, "snapshot_id": "snap:abc"})
    no_typed = r.apply(p, s, typed="2", snapshot=snap())
    assert no_typed.status == "refused" and writes(o) == []
    res = r.apply(p, s, typed="3", snapshot=snap())
    assert res.status == "done", res.refusal
    assert 20 not in o.rows["res.partner"] and o.rows["sale.order"][22]["partner_id"] == 3
    u = r.undo_merge(res, spec(level=3), "m1u")
    # message history cannot be rewritten by the walker: reported, left on the kept partner
    assert u.status == "partial" and "mail.message [23]" in u.refusal.reason, u.refusal
    assert o.rows["mail.message"][23]["res_id"] == 3
    new = max(o.rows["res.partner"])
    assert o.rows["res.partner"][new]["name"] == "Azure dup"
    assert o.rows["sale.order"][22]["partner_id"] == new


def test_merge_refusals(R) -> None:
    r, o = R()
    no(r.plan_merge("product.template", [1, 2], 1, "x"), "no stock Odoo merge wizard")
    no(r.plan_merge("res.partner", [3], 3, "x"), "2-3")
    no(r.plan_merge("res.partner", [3, 4, 20, 21], 3, "x"), "2-3")
    no(r.plan_merge("res.partner", [3, 20], 4, "x"), "including")
    no(r.plan_merge("res.partner", [3, 99], 3, "x"), "do not exist")
    o.user_partners = {20}
    no(r.plan_merge("res.partner", [3, 20], 3, "x"), "user")
    o.user_partners = set()
    o.rows["account.move"][9]["partner_id"] = 20
    no(r.plan_merge("res.partner", [3, 20], 3, "x"), "posted")
    del o.meta[rm.WIZ]
    o.rows["ir.model"] = {i: {"model": m} for i, m in enumerate(o.meta, 500)}
    no(r.plan_merge("res.partner", [3, 21], 3, "x"), "not installed")
    assert writes(o) == []


def test_merge_readback_mismatch_trips(R) -> None:
    r, o = R()
    o.drop_relink = True
    p = ok(r.plan_merge("res.partner", [3, 20], 3, "m2"))
    s = spec(level=3)
    s = type(s)(**{**s.__dict__, "snapshot_id": "snap:abc"})
    res = r.apply(p, s, typed=str(p.count), snapshot=snap())
    assert res.status == "mismatch" and r.w.gate.switch.check(FP) is not None


def test_merge_kill_switch_blocks(R) -> None:
    r, o = R()
    p = ok(r.plan_merge("res.partner", [3, 20], 3, "m3"))
    r.w.gate.switch.turn_on(FP, "owner-1", "stop")
    s = spec(level=3)
    s = type(s)(**{**s.__dict__, "snapshot_id": "snap:abc"})
    res = r.apply(p, s, typed=str(p.count), snapshot=snap())
    assert res.status == "refused" and 20 in o.rows["res.partner"]
    assert "kill" in res.refusal.reason.lower(), res.refusal
    assert not [c for c in o.calls if c == (rm.WIZ, "action_merge")]


def test_no_raw_rpc_writes_in_removal() -> None:
    src = open(f"{API}/app/bots/removal.py").read()
    assert rpc_write_calls(src) == [] and "execute_kw" not in src


def test_relink_steps_shape() -> None:
    img = {
        "relinked": [
            {
                "model": "sale.order",
                "field": "partner_id",
                "ttype": "many2one",
                "ids": [1, 2],
                "values": {"1": 20, "2": 20},
            },
            {
                "model": "res.partner",
                "field": "category_id",
                "ttype": "many2many",
                "ids": [5],
                "values": {"5": [20, 7]},
            },
        ]
    }
    st = rm._relink_steps(cp.deepcopy(img), {20: 40})
    assert st[0] == wk.Step("write", "sale.order", (1, 2), {"partner_id": 40})
    assert st[1].values == {"category_id": [(6, 0, [40, 7])]}


def test_merge_refuses_company_contact_xmlid_and_archived_dst(R) -> None:
    r, o = R()
    o.rows["res.company"][2]["partner_id"] = 20
    no(r.plan_merge("res.partner", [3, 20], 3, "x"), "company's own contact")
    o.rows["res.company"][2]["partner_id"] = False
    o.xmlids = {20}
    no(r.plan_merge("res.partner", [3, 20], 3, "x"), "xmlid")
    o.xmlids = set()
    o.rows["res.partner"][3]["active"] = False
    no(r.plan_merge("res.partner", [3, 20], 3, "x"), "archived")
    o.rows["res.partner"][3]["active"] = True
    o.fail.add("ir.model.data")
    no(r.plan_merge("res.partner", [3, 20], 3, "x"), "unreadable")
    assert writes(o) == []


def test_merge_refuses_multi_company_unless_bot_in_all(R) -> None:
    r, o = R()
    o.bot_cos = {1}  # 2 companies, bot only in 1
    no(r.plan_merge("res.partner", [3, 20], 3, "x"), "belong to every company")
    o.bot_cos = {1, 2}
    o.rows["res.company"][3] = {"name": "Branch", "active": True, "partner_id": 20}
    o.hidden_cos = {3}  # rule hides it; its contact 20 must not be merged away
    no(r.plan_merge("res.partner", [3, 20], 3, "x"), "hidden from the bot")
    o.hidden_cos = set()
    o.rows["res.company"].pop(3)
    o.rows["res.company"].pop(2)
    o.bot_cos, o.multi_grp = {1}, True  # one visible company but multi-company group in use
    o.rows["res.company"][4] = {"name": "Far", "active": True}
    o.hidden_cos = {4}
    no(r.plan_merge("res.partner", [3, 20], 3, "x"), "hidden")
    assert writes(o) == []


def test_merge_readback_unreadable_trips(R) -> None:
    r, o = R()
    p = ok(r.plan_merge("res.partner", [3, 20], 3, "m"))
    real = o._merge

    def merge_then_break(wz: dict) -> None:
        real(wz)
        o.fail.add("res.partner")  # e.g. server committed, then reads fail

    o._merge = merge_then_break
    s = spec(level=3)
    s = type(s)(**{**s.__dict__, "snapshot_id": "snap:abc"})
    res = r.apply(p, s, typed=str(p.count), snapshot=snap())
    assert res.status == "mismatch" and r.w.gate.switch.check(FP) is not None


def test_delete_readback_count_mismatch_trips(R) -> None:
    r, o = R()
    o.rows["mail.message"][41] = {"res_model": "res.partner", "res_id": 21}
    p = ok(r.plan_remove("res.partner", [21], "d", allow_delete=True))
    # the fake leaves the message behind on unlink: fewer rows gone than typed
    s = spec(level=3)
    s = type(s)(**{**s.__dict__, "snapshot_id": "snap:abc"})
    res = r.apply(p, s, typed=str(p.count), snapshot=snap())
    assert res.status == "mismatch" and "typed" in res.refusal.reason
    assert r.w.gate.switch.check(FP) is not None


def test_delete_plan_puts_low_count_flag_first(R) -> None:
    r, _ = R()
    p = ok(r.plan_remove("res.partner", [21], "p0", allow_delete=True))
    assert p.lines[0].startswith("COUNT MAY BE LOW") and "type this" in p.lines[0]


def test_delete_counts_pointer_rows(R) -> None:
    r, o = R()
    base = ok(r.plan_remove("res.partner", [21], "p0", allow_delete=True)).count
    o.rows["mail.message"][40] = {
        "res_model": "res.partner",
        "res_id": 21,
        "write_date": "x",
        "create_uid": 2,
    }
    p = ok(r.plan_remove("res.partner", [21], "p1", allow_delete=True))
    assert p.count == base + 1 and p.preview.blast["pointers"] == {"mail.message<-res.partner": 1}
    assert any("orphaned" in x for x in p.lines)
    o.fail.add("mail.message")
    no(r.plan_remove("res.partner", [21], "p2", allow_delete=True), "uncountable")


def test_generic_runner_refuses_merge_button(R) -> None:
    from app.bots.risk import classifier as cl

    r, o = R()
    try:
        got = r.w.plan([wk.Step("call", rm.WIZ, (1,), method="action_merge")], "g1")
    except cl.RiskAuditUnavailable:
        got = Refusal("RF-ANY", "catalogue", "refused (audit unavailable)")
    assert isinstance(got, Refusal), got
    assert writes(o) == []
