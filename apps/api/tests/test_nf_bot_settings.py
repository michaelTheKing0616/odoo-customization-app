"""BOT-T1-SETTINGS: settings changes via the write gate (real audit DB, fake Odoo)."""

from __future__ import annotations

from typing import Any

import pytest

from app.bots import guard as gd
from app.bots import settings as st
from app.bots.risk.rules import Refusal
from tests.test_nf_bot_kill_audit import (  # noqa: F401
    ANCHOR,
    API,
    FP,
    REH,
    engine,
    env,
    rpc_write_calls,
)

pytestmark = [pytest.mark.no_app_db]
VS = (17, 20)
FIELDS = {
    "group_discount_per_so_line": {"type": "boolean"},
    "group_stock_multi_locations": {"type": "boolean"},
    "module_stock_dropshipping": {"type": "boolean"},
    "default_invoice_policy": {
        "type": "selection",
        "selection": [["order", "Ordered"], ["delivery", "Delivered"]],
    },
    "company_id": {"type": "many2one", "readonly": False},
    "user_default_rights": {"type": "boolean", "readonly": True},
    "auth_signup_uninvited": {"type": "selection", "selection": [["b2b", "B"], ["b2c", "C"]]},
    "zz_custom_flag": {"type": "boolean"},
    "group_ids_like": {"type": "many2many"},
    "external_email_server_default": {"type": "boolean"},
}


class Odoo:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "group_discount_per_so_line": False,
            "group_stock_multi_locations": False,
            "module_stock_dropshipping": False,
            "default_invoice_policy": "order",
            "auth_signup_uninvited": "b2b",
            "zz_custom_flag": False,
            "external_email_server_default": False,
        }
        self.admins, self.pending, self.writes = 2, {}, []
        self.on_execute = None

    def read(self, model, method, args, kw=None) -> Any:
        if model == st.MODEL and method == "fields_get":
            return {f: FIELDS[f] for f in args[0] if f in FIELDS}
        if model == st.MODEL and method == "default_get":
            return {f: self.state[f] for f in args[0] if f in self.state}
        if model == "ir.model.data":
            return [{"res_id": 2}]
        if model == "res.users" and method == "fields_get":
            return {"group_ids": {}}
        if model == "res.users" and method == "search_count":
            return self.admins
        raise AssertionError((model, method))

    def rpc(self, model, method, args, kw=None) -> Any:
        self.writes.append((model, method))
        if method == "create":
            wid = 100 + len(self.writes)  # fresh wizard id, like Odoo
            self.pending[wid] = dict(args[0])
            return wid
        if method == "execute":
            self.state.update(self.pending.pop(args[0][0]))
            if self.on_execute:
                self.on_execute(self)
            return True
        raise AssertionError((model, method))


_N = iter(range(10**6))


def spec(level: int = 3, **kw: Any) -> gd.RunSpec:
    base = dict(rehearsal_id="rh-1")
    return gd.RunSpec(
        FP,
        "x",
        "bot-1",
        "R2",
        "RF-R2",
        gd.Approval(level, "alice"),
        f"k{next(_N)}",
        **{**base, **kw},
    )


@pytest.fixture
def mk(env):  # noqa: F811
    _, sw, audit = env

    def make(v: int = 17):
        o = Odoo()
        gate = gd.WriteGate(sw, audit, o.rpc, REH)
        return st.SettingsBot(o.read, gate, version=v, db=FP), o, sw, audit

    return make


def ok(p: Any) -> st.Plan:
    assert isinstance(p, st.Plan), p
    return p


def no(p: Any, part: str) -> None:
    assert isinstance(p, Refusal), p
    assert part in p.reason, p.reason


@pytest.mark.parametrize("v", VS)
def test_plan_apply_readback_and_noop(mk, v) -> None:
    b, o, _, _ = mk(v)
    p = ok(b.plan({"group_discount_per_so_line": True, "auth_signup_uninvited": "b2b"}))
    assert p.values == {"group_discount_per_so_line": True}
    assert p.before == {"group_discount_per_so_line": False}
    r = b.apply(p, spec())
    assert r.status == "done", r.refusal
    assert o.state["group_discount_per_so_line"] is True
    assert o.writes == [(st.MODEL, "create"), (st.MODEL, "execute")]
    again = b.apply(p, spec())  # re-run of a finished plan: state check, no write
    assert again.status == "done" and again.replayed and len(o.writes) == 2
    assert ok(b.plan({"group_discount_per_so_line": True})).noop
    assert b.apply(b.plan({"group_discount_per_so_line": True}), spec()).status == "noop"


def test_refusals_fail_closed(mk) -> None:
    b, o, _, _ = mk()
    no(b.plan({}), "no settings")
    no(b.plan({"nope_field": True}), "not on this database")
    no(b.plan({"user_default_rights": False}), "read-only")
    no(b.plan({"group_discount_per_so_line": "yes"}), "not a boolean")
    no(b.plan({"default_invoice_policy": "never"}), "not one of")
    no(b.plan({"default_invoice_policy": 1.5}), "not a selection")
    no(b.plan({"company_id": -1}), "bad record id")
    no(b.plan({"company_id": True}), "not a many2one")
    no(b.plan({"group_ids_like": [(6, 0, [1])]}), "not supported")
    no(b.plan({"module_stock_dropshipping": False}), "uninstalls")
    no(b.plan({"zz_custom_flag": True}), "zz_custom_flag")  # no catalogue row
    assert o.writes == []


def test_unreadable_form_refused(mk) -> None:
    b, _, _, _ = mk()
    b.read = lambda *a: (_ for _ in ()).throw(ConnectionError("x"))
    no(b.plan({"group_discount_per_so_line": True}), "unreadable")


def test_tiers_approval_and_snapshot(mk) -> None:
    b, o, _, _ = mk()
    p = ok(b.plan({"group_stock_multi_locations": True}))
    assert p.tier == 3 and p.cls == "R8"
    assert b.apply(p, spec(level=1)).status == "refused" and o.writes == []
    m = ok(b.plan({"module_stock_dropshipping": True}))
    assert m.needs_snapshot and m.tier == 3
    r = b.apply(m, spec())
    assert r.status == "refused" and "snapshot" in r.refusal.reason and o.writes == []
    assert b.apply(m, spec(snapshot_id="snap-1")).status == "done"
    no(b.undo(st.Result("done", m, {})), "no undo")


@pytest.mark.parametrize("v", VS)
def test_outgoing_mail_server_setting_needs_l2(mk, v) -> None:
    b, o, _, _ = mk(v)
    p = ok(b.plan({"external_email_server_default": True}))
    assert p.tier == 2 and not p.needs_snapshot
    assert any("outgoing email" in ln and "L2" in ln for ln in p.lines)
    r = b.apply(p, spec(level=1))
    assert r.status == "refused" and "L2" in r.refusal.reason and o.writes == []
    assert b.apply(p, spec(level=2)).status == "done"
    assert o.state["external_email_server_default"] is True
    # negative: an ordinary reviewed setting stays L1; a higher class is not lowered
    if v == 17:  # catalogue row checked on 17
        assert ok(b.plan({"default_invoice_policy": "delivery"})).tier == 1
    both = ok(b.plan({"external_email_server_default": False, "group_stock_multi_locations": True}))
    assert both.tier == 3 and both.cls == "R8"
    assert set(st.L2_SETTINGS) == {"external_email_server_default"}


def test_kill_switch_blocks_and_no_rehearsal_blocks(mk) -> None:
    b, o, sw, _ = mk()
    p = ok(b.plan({"group_discount_per_so_line": True}))
    r = b.apply(p, spec(rehearsal_id=None))
    assert r.status == "refused" and o.writes == []
    sw.turn_on(FP, "owner-1", "stop")
    assert b.apply(p, spec()).status == "refused" and o.writes == []


def test_changed_since_preview(mk) -> None:
    b, o, _, _ = mk()
    p = ok(b.plan({"default_invoice_policy": "delivery"}))
    o.state["default_invoice_policy"] = False
    r = b.apply(p, spec())
    assert r.status == "refused" and "changed since" in r.refusal.reason and o.writes == []


def test_readback_mismatch_trips_kill_switch(mk) -> None:
    b, o, sw, _ = mk()
    o.on_execute = lambda s: s.state.update(group_discount_per_so_line=False)
    r = b.apply(ok(b.plan({"group_discount_per_so_line": True})), spec())
    assert r.status == "mismatch" and sw.check(FP) is not None


def test_lost_admin_trips_kill_switch(mk) -> None:
    b, o, sw, _ = mk()
    o.on_execute = lambda s: setattr(s, "admins", 1)
    r = b.apply(ok(b.plan({"auth_signup_uninvited": "b2c"})), spec())
    assert r.status == "lockout" and sw.check(FP) is not None


def test_duplicate_key_needs_human(mk) -> None:
    b, o, _, _ = mk()
    p = ok(b.plan({"group_discount_per_so_line": True}))
    s = spec()
    assert b.apply(p, s).status == "done"
    o.state["group_discount_per_so_line"] = False  # someone reverted it; same key replayed
    r = b.apply(p, s)
    assert r.status == "needs-human" and len(o.writes) == 2


def test_undo_restores_through_gate(mk) -> None:
    b, o, _, audit = mk()
    d = b.apply(ok(b.plan({"default_invoice_policy": "delivery"})), spec())
    u = ok(b.undo(d))
    assert u.values == {"default_invoice_policy": "order"}
    r = b.apply(u, spec())
    assert r.status == "done", (r, o.writes, o.state)
    assert o.state["default_invoice_policy"] == "order"
    assert len(o.writes) == 4
    no(b.undo(st.Result("refused")), "completed")
    # the gate refuses the same change twice in one DB (same plan hash): fails closed
    assert b.apply(ok(b.plan({"default_invoice_policy": "delivery"})), spec()).status != "done"
    d2 = b.apply(ok(b.plan({"group_discount_per_so_line": True})), spec())
    o.state["group_discount_per_so_line"] = False
    no(b.undo(d2), "changed since")


def test_no_raw_rpc_writes_in_settings_module() -> None:
    src = (API / "app" / "bots" / "settings.py").read_text()
    assert rpc_write_calls(src) == [] and "execute_kw" not in src
