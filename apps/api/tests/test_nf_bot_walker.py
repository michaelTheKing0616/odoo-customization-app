"""BOT-GENERIC-WALKER: generic record-change walker over an in-memory Odoo (17/18/19/20 shapes)."""

from __future__ import annotations

import ast
import copy as cp
from pathlib import Path
from typing import Any

import pytest

from app.bot_verify import targets as tg
from app.bots import access as ac
from app.bots import before_image as bi
from app.bots import guard as gd
from app.bots import walker as wk
from app.bots.audit import AuditLog
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
from tests.test_nf_bot_lockout_sim import BOT
from tests.test_nf_bot_lockout_sim import Fake as LkFake

pytestmark = pytest.mark.no_app_db
VS = (17, 18, 19, 20)
LKM = {"res.users", "res.groups", "ir.model.access", "ir.rule", "ir.access", "ir.model.data"}
LKM |= {"res.users.apikeys", "auth.oauth.provider", "res.users.deletion", "ir.ui.menu"}
S = wk.Step


def F(t: str, **kw: Any) -> dict:  # noqa: N802
    return {"type": t, "string": kw.pop("string", t), "store": True, "readonly": False, **kw}


def m2o(rel: str, **kw: Any) -> dict:
    return F("many2one", relation=rel, **kw)


def schema(v: int) -> dict[str, dict]:
    sel = lambda *k: [[x, x] for x in k]  # noqa: E731
    ptype = sel("consu", "service", "product") if v < 18 else sel("consu", "service", "combo")
    locks = (
        ["period_lock_date", "fiscalyear_lock_date"]
        if v < 18
        else ["sale_lock_date", "hard_lock_date", "fiscalyear_lock_date"]
    )
    s = {
        "res.partner": {
            "name": F("char"),
            "email": F("char"),
            "is_company": F("boolean"),
            "lang": F("selection", selection=sel("en_US", "fr_FR")),
            "category_id": F("many2many", relation="res.partner.category"),
            "comment": F("html"),
            "display_name": F("char", store=False, readonly=True),
            "write_date": F("datetime", readonly=True),
            "commercial_partner_id": m2o("res.partner", readonly=True, depends=["parent_id"]),
            "parent_id": m2o("res.partner"),
            "image_1920": F("binary"),
            "barcode": F("char", company_dependent=True),
            "company_id": m2o("res.company"),
            "country_code": F("char", related="country_id.code", readonly=True),
        },
        "res.partner.category": {"name": F("char", required=True, translate=True)},
        "res.company": {"name": F("char"), **{f: F("date") for f in locks}},
        "product.template": {
            "name": F("char", required=True, translate=True),
            "list_price": F("float"),
            "type": F("selection", selection=ptype, required=True, default="consu"),
        },
        "sale.order": {
            "name": F("char", default="New"),
            "partner_id": m2o("res.partner", required=True),
            "order_line": F("one2many", relation="sale.order.line", relation_field="order_id"),
            "state": F(
                "selection",
                selection=sel("draft", "sale", "cancel"),
                readonly=True,
                default="draft",
            ),
            "locked": F("boolean", readonly=True),
            "note": F("html"),
        },
        "sale.order.line": {
            "order_id": m2o("sale.order", required=True),
            "name": F("text"),
            "product_uom_qty": F("float"),
            "price_unit": F("float"),
        },
        "account.move": {
            "ref": F("char"),
            "partner_id": m2o("res.partner"),
            "date": F("date", required=True, default="2026-10-01"),
            "state": F(
                "selection",
                selection=sel("draft", "posted", "cancel"),
                readonly=True,
                default="draft",
            ),
            "company_id": m2o("res.company", required=True, default=1),
            "is_move_sent": F("boolean", readonly=True),
            "move_type": F("selection", selection=sel("entry", "out_invoice"), default="entry"),
        },
        "stock.picking": {
            "origin": F("char"),
            "partner_id": m2o("res.partner"),
            "state": F(
                "selection", selection=sel("draft", "assigned", "done", "cancel"), readonly=True
            ),
        },
        "hr.employee": {
            "name": F("char"),
            "work_email": F("char"),
            "job_title": F("char"),
            "pin": F("char"),
        },
        "crm.lead": {
            "name": F("char", required=True),
            "expected_revenue": F("monetary"),
            "priority": F("selection", selection=sel("0", "1", "2", "3")),
        },
        "project.task": {
            "name": F("char", required=True),
            "user_ids": F("many2many", relation="res.users"),
            "date_deadline": F("date" if v < 19 else "datetime"),
        },
        "x_probe": {"x_name": F("char", required=True)},
        "mail.mail": {"subject": F("char")},
        "ir.config_parameter": {"key": F("char"), "value": F("text")},
    }
    return s


class Odoo:
    """Generic in-memory Odoo: fields_get / search / read / create / write / unlink."""

    def __init__(self, v: int) -> None:
        self.v, self.meta, self.calls = v, schema(v), []
        self.rows: dict[str, dict[int, dict]] = {m: {} for m in self.meta}
        self.seq, self.onchange_value, self.fail = 100, {}, set()
        self.lk = LkFake(v)  # access models (users/groups/ACLs) for detect + lockout
        self.rows["res.company"].update(
            {1: {"name": "Co", "active": True}, 2: {"name": "Co2", "active": True}}
        )
        self.rows["res.partner"].update({3: {"name": "Azure", "email": "a@x"}, 4: {"name": "Deco"}})
        self.rows["res.partner.category"][5] = {"name": "VIP"}
        self.rows["sale.order"][7] = {"name": "S7", "partner_id": 3, "state": "draft"}
        self.rows["account.move"][8] = {
            "ref": "draft",
            "state": "draft",
            "date": "2026-10-01",
            "company_id": 1,
        }
        self.rows["account.move"][9] = {
            "ref": "posted",
            "state": "posted",
            "date": "2026-10-01",
            "company_id": 1,
        }
        self.rows["stock.picking"][11] = {"origin": "x", "state": "done"}
        self.rows["stock.picking"][12] = {"origin": "y", "state": "assigned"}
        self.rows["hr.employee"][13] = {"name": "Eve"}
        self.rows["crm.lead"][14] = {"name": "Lead", "priority": "0"}
        self.rows["project.task"][15] = {"name": "T"}
        self.rows["x_probe"][16] = {"x_name": "p"}
        self.rows["ir.model"] = {i: {"model": m} for i, m in enumerate(self.meta, 500)}
        for rs in self.rows.values():
            for r in rs.values():
                r.setdefault("write_date", "2026-10-01 00:00:00")
                r.setdefault("create_uid", 2)

    # ---- helpers
    def _val(self, model: str, f: str, r: dict) -> Any:
        m = self.meta.get(model, {}).get(f, {})
        v = r.get(f, [] if m.get("type") in wk.X2M else False)
        if m.get("type") == "many2one" and v:
            return [v, f"#{v}"]
        if m.get("type") == "one2many":
            return sorted(
                i
                for i, c in self.rows[m["relation"]].items()
                if c.get(m["relation_field"]) == r["id"]
            )
        return cp.deepcopy(v)

    def _match(self, model: str, r: dict, dom: list) -> bool:
        for leaf in dom:
            if not isinstance(leaf, (list, tuple)):
                continue
            f, op, want = leaf
            got = r.get(f)
            if op == "=":
                ok = got == want or (want is False and not got)
            elif op in ("!=", "in", "not in"):
                ok = {"!=": got != want, "in": got in want, "not in": got not in want}[op]
            elif op in (">", "<"):
                ok = got is not None and (got > want if op == ">" else got < want)
            else:
                ok = False
            if not ok:
                return False
        return True

    def _set(self, model: str, rid: int, vals: dict) -> None:
        r = self.rows[model][rid]
        for f, v in vals.items():
            m = self.meta[model][f]
            if m["type"] == "many2many":
                cur = set(r.get(f) or [])
                for c in v:
                    cur = set(c[2]) if c[0] == 6 else cur | {c[1]} if c[0] == 4 else cur - {c[1]}
                r[f] = sorted(cur)
            elif m["type"] == "one2many":
                for c in v:
                    self._create(m["relation"], {**c[2], m["relation_field"]: rid})
            else:
                r[f] = v
        r["write_date"] = f"2026-10-02 00:00:{self.seq % 60:02d}"

    def _create(self, model: str, vals: dict) -> int:
        self.seq += 1
        rid = self.seq  # nested line creates move seq on
        dflt = {f: m["default"] for f, m in self.meta[model].items() if "default" in m}
        self.rows[model][rid] = {**dflt, "create_uid": BOT}
        self._set(model, rid, vals)
        return rid

    # ---- RPC
    def __call__(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        kw = kw or {}
        self.calls.append((model, method))
        if model in self.fail:
            raise RuntimeError("unreadable")
        own = method in ("search", "search_count")  # ir.model existence: this fake
        if model in LKM and method == "fields_get":  # the shapes access.detect pins
            vm = ac.VMAPS["20" if self.v >= 20 else "19" if self.v == 19 else "17-18"]
            got = self.lk(model, method, args, kw)
            return {
                **got,
                **{f: F(t, relation="x") for f, t in ac.ALLOWED[vm.key].get(model, {}).items()},
            }
        if model in LKM or (model == "ir.model" and not own):
            if method in ("search", "search_count"):  # the lockout fake only answers reads
                got = self.lk(model, "search_read", args[:1], {})
                ids = [r["id"] for r in got if self._match(model, r, args[0])]
                return len(ids) if method == "search_count" else ids
            return self.lk(model, method, args, kw)
        rows = self.rows.get(model, {})
        if method == "fields_get":
            return cp.deepcopy(self.meta.get(model, {}))
        if method in ("search", "search_count", "search_read"):
            hit = sorted(i for i, r in rows.items() if self._match(model, {**r, "id": i}, args[0]))
            if kw.get("order") == "id desc":
                hit.reverse()
            hit = hit[: kw["limit"]] if kw.get("limit") else hit
            if method == "search":
                return hit
            if method == "search_count":
                return len(hit)
            fs = kw.get("fields") or list(self.meta.get(model, {}))
            return [
                {"id": i, **{f: self._val(model, f, {**rows[i], "id": i}) for f in fs}} for i in hit
            ]
        if method == "read":
            fs = kw.get("fields") or (args[1] if len(args) > 1 else list(self.meta.get(model, {})))
            return [
                {"id": i, **{f: self._val(model, f, {**rows[i], "id": i}) for f in fs}}
                for i in args[0]
                if i in rows
            ]
        if method == "default_get":
            return {
                f: self.meta[model][f]["default"]
                for f in args[0]
                if "default" in self.meta[model][f]
            }
        if method == "onchange":
            return {"value": dict(self.onchange_value.get(model, {}))}
        if method == "create":
            vs = args[0]
            return (
                [self._create(model, v) for v in vs]
                if isinstance(vs, list)
                else self._create(model, vs)
            )
        if method == "write":
            for i in args[0]:
                self._set(model, i, args[1])
            return True
        if method == "unlink":
            for i in args[0]:
                rows.pop(i)
                for m in self.meta[model].values():  # lines go with their parent (cascade)
                    if m["type"] == "one2many":
                        kids = self.rows[m["relation"]]
                        for k in [k for k, c in kids.items() if c.get(m["relation_field"]) == i]:
                            kids.pop(k)
            return True
        if method.startswith(("action_", "button_")):
            for i in args[0]:
                rows[i]["state"] = "posted"
            return True
        raise AssertionError(f"unexpected {model}.{method}")


class Store:
    def __init__(self) -> None:
        self.rows: list = []

    def record(self, *a: Any) -> None:
        self.rows.append(a)


@pytest.fixture
def W(engine, tmp_path, monkeypatch):  # noqa: F811, N802
    _clean(engine)
    monkeypatch.setattr(tg, "_STORE", Store())

    def make(v: int, reviewed: dict | None = None, o: Odoo | None = None) -> tuple[wk.Walker, Odoo]:
        o = o or Odoo(v)
        sw = gd.KillSwitch(engine, lambda s: OWNER, grant_source=fake_owner)
        w = wk.Walker(
            o,
            sw,
            AuditLog(engine, anchor=ANCHOR),
            REH,
            bi.ImageStore(tmp_path / "bi"),
            wk.Ledger(tmp_path / "ledger.json"),
            db=FP,
            bot_uid=BOT,
            version=v,
            reviewed=reviewed,
        )
        return w, o

    return make


_N = iter(range(10**6))


def spec(level: int = 3) -> gd.RunSpec:
    return gd.RunSpec(
        FP,
        "x",
        "bot-1",
        "R2",
        "RF-R2",
        gd.Approval(level, "alice"),
        f"k{next(_N)}",
        rehearsal_id="rh-1",
    )


def ok(r: Any) -> wk.Walk:
    assert isinstance(r, wk.Walk), r
    return r


def refused(r: Any, part: str) -> bool:
    assert isinstance(r, Refusal), r
    assert part in r.reason, r.reason
    return True


# ---------------------------------------------------------------- table: 12+ models
def CASES(v: int) -> list[tuple[str, list[wk.Step], str | None]]:  # noqa: N802
    ptype = "product" if v < 18 else "combo"
    dl = "2026-11-01" if v < 19 else "2026-11-01 09:00:00"
    return [
        (
            "partner write",
            [S("write", "res.partner", (3,), {"name": "Azure B", "category_id": [(6, 0, [5])]})],
            None,
        ),
        (
            "product create",
            [S("create", "product.template", values={"name": "Chair", "type": ptype})],
            "counter-document",
        ),
        (
            "sale line create",
            [S("create", "sale.order.line", values={"order_id": 7, "product_uom_qty": 2.0})],
            None,
        ),
        (
            "sale order with lines",
            [
                S(
                    "create",
                    "sale.order",
                    values={"partner_id": 3, "order_line": [(0, 0, {"name": "l"})]},
                )
            ],
            None,
        ),
        ("draft move write", [S("write", "account.move", (8,), {"ref": "INV/1"})], None),
        (
            "posted move refused",
            [S("write", "account.move", (9,), {"ref": "x"})],
            "only a reversal",
        ),
        (
            "done picking refused",
            [S("write", "stock.picking", (11,), {"origin": "z"})],
            "validated transfer",
        ),
        ("open picking write", [S("write", "stock.picking", (12,), {"origin": "z"})], None),
        ("employee write", [S("write", "hr.employee", (13,), {"job_title": "Lead"})], None),
        (
            "lead priority",
            [S("write", "crm.lead", (14,), {"priority": "2", "expected_revenue": 10})],
            None,
        ),
        ("task deadline", [S("write", "project.task", (15,), {"date_deadline": dl})], None),
        (
            "task assignees: R8, lockout cannot simulate",
            [S("write", "project.task", (15,), {"user_ids": [(6, 0, [BOT])]})],
            "not simulated",
        ),
        ("users refused", [S("write", "res.users", (BOT,), {"name": "x"})], "access layer"),
        (
            "config param refused",
            [S("create", "ir.config_parameter", values={"key": "a", "value": "b"})],
            "system parameters",
        ),
        ("mail refused", [S("create", "mail.mail", values={"subject": "hi"})], "outgoing email"),
        (
            "custom unreviewed refused",
            [S("write", "x_probe", (16,), {"x_name": "q"})],
            "nobody has reviewed",
        ),
    ]


@pytest.mark.parametrize("v", VS)
def test_table_twelve_models_plan_apply_undo(v, W) -> None:
    for name, steps, want in CASES(v):
        w, o = W(v)
        r = w.plan(steps, f"p-{name}")
        if want:
            assert refused(r, want), name
            continue
        walk = ok(r)
        before = cp.deepcopy(o.rows)
        done = w.apply(walk, spec())
        assert [d.status for d in done] == ["done"], (
            name,
            done[-1].refusal,
            getattr(w, "last_log", ""),
        )
        inv = w.undo_steps(done)
        assert isinstance(inv, list) and inv, (name, inv)
        back = w.apply(ok(w.plan(inv, f"u-{name}")), spec())
        assert all(d.status == "done" for d in back), (name, back[-1].refusal)

        def strip(rows: dict) -> dict:
            return {
                m: {
                    i: {
                        k: x
                        for k, x in r.items()
                        if k != "write_date" and x not in (False, [], None)
                    }
                    for i, r in rs.items()
                }
                for m, rs in rows.items()
            }

        assert strip(o.rows) == strip(before), name


@pytest.mark.parametrize("v", VS)
def test_field_validation_refusals(v, W) -> None:
    w, _ = W(v)
    P = lambda vals, m="res.partner", ids=(3,): w.plan([S("write", m, ids, vals)], "p")  # noqa: E731
    assert refused(P({"nope": 1}), "does not exist")
    assert refused(P({"display_name": "x"}), "computed and not stored")
    assert refused(P({"commercial_partner_id": 4}), "read-only")
    assert refused(P({"country_code": "BE"}), "related")
    assert refused(P({"write_date": "x"}), "managed by Odoo")
    assert refused(P({"lang": "de_DE"}), "does not fit a selection")
    assert refused(P({"parent_id": 999}), "do not exist")
    assert refused(P({"is_company": "yes"}), "boolean")
    assert refused(P({"image_1920": "%%%"}), "binary")
    assert refused(P({"category_id": [(2, 5)]}), "command 2 not allowed")
    assert refused(P({"category_id": [(6, 0, [77])]}), "do not exist")
    assert refused(P({"email": "b@x"}, ids=(999,)), "do not exist")
    assert refused(P({"pin": "1234"}, "hr.employee", (13,)), "credential")
    assert refused(P({"date_deadline": "11/01/2026"}, "project.task", (15,)), "does not fit")
    assert refused(
        w.plan([S("create", "crm.lead", values={"priority": "1"})], "p"),
        "required field(s) missing",
    )
    assert refused(P({"name": "Azure"}), "nothing would change")
    for blank in ("", "   ", False):
        c = w.plan([S("create", "res.partner.category", values={"name": blank})], "p")
        assert refused(c, "is required"), blank
    assert refused(P({"email": "b@x"}), "not simulated")  # R8 login email: lockout cannot simulate
    walk = ok(P({"barcode": "B1", "name": "Azure 2"}))
    assert any("company-dependent" in x for x in walk.steps[0].reasons)
    t = ok(w.plan([S("create", "res.partner.category", values={"name": "Desk"})], "p")).steps[0]
    assert any("translated" in x for x in t.reasons)


@pytest.mark.parametrize("v", VS)
def test_version_shapes_differ_and_mismatch_refuses(v, W) -> None:
    w, _ = W(v)
    bad = "combo" if v < 18 else "product"
    assert refused(
        w.plan([S("create", "product.template", values={"name": "x", "type": bad})], "p"),
        "does not fit",
    )
    wrong = 20 if v < 20 else 17
    w2, _ = W(wrong, o=Odoo(v))
    assert refused(w2.plan([S("write", "res.partner", (3,), {"name": "q"})], "p"), "plan says")


@pytest.mark.parametrize("v", VS)
def test_irrecoverable_states_and_locked_period(v, W) -> None:
    w, o = W(v)
    lock = "period_lock_date" if v < 18 else "hard_lock_date"
    o.rows["res.company"][1][lock] = "2026-12-31"
    assert refused(w.plan([S("write", "account.move", (8,), {"ref": "y"})], "p"), "locked period")
    assert refused(w.plan([S("unlink", "account.move", (9,))], "p"), "only a reversal")
    o.meta["account.move"]["edi_state"] = F(
        "selection", selection=[["sent", "sent"]], readonly=True
    )
    o.rows["account.move"][8]["edi_state"] = "sent"
    o.rows["res.company"][1][lock] = False
    w, _ = W(v, o=o)  # metadata is read once per walker
    assert refused(w.plan([S("write", "account.move", (8,), {"ref": "y"})], "p"), "e-invoice")


@pytest.mark.parametrize("v", VS)
def test_buttons_only_when_catalogue_marks_them(v, W) -> None:
    w, _ = W(v)
    walk = w.plan([S("call", "account.move", (8,), method="action_post")], "p")
    if isinstance(walk, Refusal):  # not every version's catalogue has the button
        assert "catalogue" in walk.reason
    else:
        assert walk.tier == 3 and any("irreversible" in x for x in walk.steps[0].reasons)
    assert refused(
        w.plan([S("call", "account.move", (8,), method="action_frobnicate")], "p"),
        "b:account.move:action_frobnicate",
    )
    assert refused(w.plan([S("call", "account.move", (8,), method="write")], "p"), "only button_")
    assert refused(
        w.plan([S("call", "account.move", (9,), method="button_draft")], "p"), "only a reversal"
    )


@pytest.mark.parametrize("v", VS)
def test_reviewed_custom_model_is_l3_and_undoable(v, W) -> None:
    with pytest.raises(wk.Refused):
        W(v, reviewed={"res.partner": "no"})
    w, o = W(v, reviewed={"x_probe": "owner reviewed 2026-10-26"})
    walk = ok(w.plan([S("write", "x_probe", (16,), {"x_name": "q"})], "p"))
    assert walk.tier == 3
    assert w.apply(walk, spec(2))[0].status == "refused"
    done = w.apply(walk, spec(3))
    assert done[0].status == "done" and o.rows["x_probe"][16]["x_name"] == "q"


@pytest.mark.parametrize("v", VS)
def test_side_effects_onchange_constraints_unreadable(v, W) -> None:
    w, o = W(v)
    o.onchange_value["res.partner"] = {"lang": "fr_FR"}
    st = ok(w.plan([S("write", "res.partner", (3,), {"name": "z"})], "p")).steps[0]
    assert any("the form would also set ['lang']" in x for x in st.reasons)
    assert any("constraint" in x for x in st.reasons)
    w, o = W(v)
    o.fail.add("ir.model.constraint")
    assert refused(w.plan([S("write", "res.partner", (3,), {"name": "z"})], "p"), "unreadable")


@pytest.mark.parametrize("v", VS)
def test_idempotent_rerun_and_crash_recovery(v, W, tmp_path) -> None:
    w, o = W(v)
    walk = ok(w.plan([S("create", "crm.lead", values={"name": "Once"})], "p"))
    first = w.apply(walk, spec())
    again = w.apply(walk, spec())
    assert (
        first[0].status == "done"
        and again[0].replayed
        and again[0].record_ids == first[0].record_ids
    )
    assert sum(r.get("name") == "Once" for r in o.rows["crm.lead"].values()) == 1
    # crash after the create, before the ledger said done: adopt, never create twice
    key = walk.steps[0].key
    w.ledger.put(key, {"status": "started", "top": first[0].record_ids[0] - 1, "ids": []})
    rec = w.apply(walk, spec())
    assert rec[0].status == "done" and rec[0].record_ids == first[0].record_ids
    assert sum(r.get("name") == "Once" for r in o.rows["crm.lead"].values()) == 1
    # crash mid-write: live state already equals the target -> done, no second write
    ww = ok(w.plan([S("write", "res.partner", (3,), {"name": "c"})], "p2"))
    o.rows["res.partner"][3]["name"] = "c"
    w.ledger.put(ww.steps[0].key, {"status": "started", "top": 0, "ids": [3]})
    n = len([c for c in o.calls if c[1] == "write"])
    assert w.apply(ww, spec())[0].status == "done"
    assert len([c for c in o.calls if c[1] == "write"]) == n
    # in between: needs a person
    w.ledger.put(ww.steps[0].key, {"status": "started", "top": 0, "ids": [3]})
    o.rows["res.partner"][3]["name"] = "other"
    assert w.apply(ww, spec())[0].status == "needs-human"


@pytest.mark.parametrize("v", VS)
def test_stale_preview_low_approval_and_kill_switch(v, W, engine) -> None:  # noqa: F811
    w, o = W(v)
    walk = ok(w.plan([S("write", "res.partner", (3,), {"name": "s"})], "p"))
    assert w.apply(walk, spec(0))[0].status == "refused"
    o.rows["res.partner"][3]["name"] = "moved"
    assert "changed since the preview" in w.apply(walk, spec())[0].refusal.reason
    walk = ok(w.plan([S("write", "res.partner", (3,), {"name": "s"})], "p3"))
    w.gate.switch.turn_on(FP, "owner", "stop")
    assert w.apply(walk, spec())[0].status != "done"
    assert o.rows["res.partner"][3]["name"] == "moved"


def test_undo_refused_when_changed_and_for_unlink(W) -> None:
    w, o = W(17)
    done = w.apply(ok(w.plan([S("write", "res.partner", (3,), {"name": "u"})], "p")), spec())
    o.rows["res.partner"][3]["name"] = "someone"
    assert refused(w.undo_steps(done), "changed since it was applied")
    d2 = w.apply(ok(w.plan([S("unlink", "res.partner", (4,))], "p2")), spec())
    assert d2[0].status == "done" and 4 not in o.rows["res.partner"]
    assert refused(w.undo_steps(d2), "no automatic undo")


def test_writes_only_through_the_gate() -> None:
    from tests.test_nf_bot_kill_audit import READ_PASSTHROUGH, rpc_write_calls

    src = Path(wk.__file__).read_text()
    pins = READ_PASSTHROUGH["walker.py"]
    assert rpc_write_calls(src, pins) == [] and "execute_kw" not in src and "xmlrpc" not in src
    tree = ast.parse(src)
    gates = sorted(
        ast.unparse(c.func)
        for c in ast.walk(tree)
        if isinstance(c, ast.Call)
        and isinstance(c.func, ast.Attribute)
        and c.func.attr in ("run", "call")
        and "gate" in ast.unparse(c.func)
    )
    assert gates == ["self.gate.call", "self.gate.call", "self.gate.run"]
    raw = [
        ast.unparse(c)
        for c in ast.walk(tree)
        if isinstance(c, ast.Call) and ast.unparse(c.func) == "self.rpc"
    ]
    assert raw == ["self.rpc(model, method, args, kw or {})"]  # _dry only, pinned to DRY_METHODS
    assert wk.DRY_METHODS == {"default_get", "onchange"}
    assert all(r for r in wk.REFUSED_MODELS.values()) and all(
        x[2] for x in wk.IRRECOVERABLE.values()
    )


def _nested_meta(w: wk.Walker, rel: str) -> None:
    real = w.meta

    def meta(m: str) -> dict:
        if m == "res.partner":
            d = dict(real(m))
            d["user_ids"] = {
                "type": "one2many",
                "relation": rel,
                "relation_field": "partner_id",
                "store": True,
            }
            return d
        if m == rel:
            return {"login": F("char"), "partner_id": m2o("res.partner")}
        return real(m)

    w.meta = meta


@pytest.mark.parametrize("rel", ["res.users", "x_unreviewed"])
def test_nested_create_into_refused_model_is_refused(rel, W) -> None:
    w, _ = W(VS[0])
    _nested_meta(w, rel)
    with pytest.raises(wk.Refused):
        w.check_values(
            "res.partner", {"name": "x", "user_ids": [(0, 0, {"login": "evil"})]}, "create"
        )


def test_reference_to_refused_model_and_menu_groups_are_refused(W) -> None:
    w, _ = W(VS[0])
    with pytest.raises(wk.Refused):
        w._value("res.partner", "r", {"type": "reference"}, "res.users,2", "write", 0)
    with pytest.raises(wk.Refused):
        w._model_ok("ir.cron")
    real = w.meta
    w.meta = lambda m: (
        {"groups_id": {"type": "many2many", "relation": "res.groups", "store": True}}
        if m == "ir.ui.menu"
        else real(m)
    )
    with pytest.raises(wk.Refused, match="grants access"):
        w.check_values("ir.ui.menu", {"groups_id": [(6, 0, [1])]}, "write")


class _Sink:
    def __init__(self, held: bool) -> None:
        self.held, self.opened, self.closed = held, 0, 0

    def scan(self, model, op, vals, ids):  # noqa: ANN001
        import app.bots.sinkhole as sh

        return sh.Scan(model, op)

    def open(self, scan, level):  # noqa: ANN001
        self.opened += 1

    def after_batch(self) -> bool:
        return self.held

    def close(self) -> None:
        self.closed += 1


@pytest.mark.parametrize("held", [True, False])
def test_button_runs_inside_a_proven_hold(held, W) -> None:
    w, _ = W(VS[0])
    real = w.sink
    fake = _Sink(held)
    w.sink = fake
    walk = w.plan([S("call", "account.move", (8,), method="action_post")], "p")
    if isinstance(walk, Refusal):
        pytest.skip("catalogue has no action_post here")
    assert walk.steps[0].tier == 3 and any("held" in x for x in walk.steps[0].lines)
    d = w.apply(walk, spec(3))[0]
    assert fake.opened == 1 and fake.closed == 1
    assert d.status == ("done" if held else "refused")
    w.sink = real
