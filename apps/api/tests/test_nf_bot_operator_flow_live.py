"""BOT-OPERATOR-FLOW live: Odoo 17 and 20 disposable sandboxes over JSON-RPC, ODOO_LIVE=1.

Ports / DBs from OPFLOW_PORT_<v> / OPFLOW_DB_<v> (default: the nf sandbox stacks). One plan:
create a tag, change a contact reference, and an uninstalled-module step. Nothing runs before the
store approval; approved steps run through the walker; configverify then says "matches"; a
re-run touches nothing; the undo walk restores the start state; the module step stays blocked
with "available in Odoo N via module M; needs install".
"""

from __future__ import annotations

import os
import uuid

import pytest

from app.bot_verify import targets as tg
from app.bots import before_image as bi
from app.bots import guard as gd
from app.bots import operator_flow as of
from app.bots import walker as wk
from app.bots.audit import AuditLog
from tests import test_nf_bot_sinkhole_live as sl
from tests.test_nf_bot_kill_audit import ANCHOR, FP, OWNER, REH, _clean, engine, fake_owner  # noqa: F401
from tests.test_nf_bot_walker import Store, ok, spec

pytestmark = [pytest.mark.no_app_db, pytest.mark.skipif(not sl.LIVE, reason="set ODOO_LIVE=1")]


class Live(sl.Json):
    def __init__(self, v: int) -> None:
        sl.PORTS[v] = int(os.environ.get(f"OPFLOW_PORT_{v}", sl.PORTS[v]))
        db = os.environ.get(f"OPFLOW_DB_{v}")
        if db:
            self.url, self.db = f"http://127.0.0.1:{sl.PORTS[v]}", db
            self.uid = self._call("common", "login", [db, "admin", "admin"])
            assert self.uid
        else:
            super().__init__(v)


@pytest.mark.parametrize("v", [17, 20])
def test_live_guided_plan(v, engine, tmp_path, monkeypatch) -> None:  # noqa: F811
    o, tag = Live(v), uuid.uuid4().hex[:6]
    monkeypatch.setattr(tg, "_STORE", Store())
    uf = "groups_id" if v < 19 else "group_ids"
    sysg = o(
        "ir.model.data",
        "search_read",
        [[("module", "=", "base"), ("name", "=", "group_system")]],
        {"fields": ["res_id"]},
    )
    bot = o(
        "res.users",
        "create",  # setup only: a dedicated bot user
        [{"name": f"flow bot {tag}", "login": f"flowbot{tag}", uf: [(6, 0, [sysg[0]["res_id"]])]}],
    )
    try:
        pname = f"flow p {tag}"
        pid = o("res.partner", "create", [{"name": pname, "ref": "old"}])  # setup
        inst = [
            m["name"]
            for m in o(
                "ir.module.module",
                "search_read",
                [[("state", "=", "installed")]],
                {"fields": ["name"]},
            )
        ]
        assert "mrp" not in inst, "sandbox must not have mrp installed"
        _clean(engine)
        sw = gd.KillSwitch(engine, lambda s: OWNER, grant_source=fake_owner)
        w = wk.Walker(
            o,
            sw,
            AuditLog(engine, anchor=ANCHOR),
            REH,
            bi.ImageStore(tmp_path / "bi"),
            wk.Ledger(tmp_path / "ledger.json"),
            db=FP,
            bot_uid=bot,
            version=v,
        )

        def it(kind, model, key, exp, **kw):
            ref = f"{model}:" + ",".join(f"{k}={x}" for k, x in sorted(key.items()))
            return {
                "kind": kind,
                "model": model,
                "key": key,
                "expected": exp,
                "relations": {},
                "module": "",
                "verdict": "stock",
                "risk": "R1",
                "reason": "",
                "ref": ref,
            } | kw

        items = [
            it("record", "res.partner.category", {"name": f"flow tag {tag}"}, {}),
            it("record", "res.partner", {"name": pname}, {"ref": f"new{tag}"}),
            it(
                "module",
                "mrp.production",
                {"name": "mrp"},
                {},
                module="mrp",
                verdict="stock-install",
            ),
        ]
        sp = {"spec_version": 1, "status": "designed", "odoo_major": v, "items": items}
        dec = of.Decisions(tmp_path / "dec.json")
        flow = of.OperatorFlow(
            sp,
            w,
            dec,
            tmp_path / "st.json",
            spec(),
            plan_id=f"live-{tag}",
            installed=inst,
            companies=o("res.company", "search", [[]]),
        )
        first = flow.run()
        assert [s["status"] for s in first["steps"]] == [of.PENDING, of.PENDING, of.BLOCKED], first
        assert f"available in Odoo {v} via module mrp; needs install" in first["steps"][2]["reason"]
        assert o("res.partner", "read", [[pid]], {"fields": ["ref"]})[0]["ref"] == "old"
        for c in flow.cards():
            dec.approve(f"live-{tag}", c, "alice", 3)
        rep = flow.run()
        st = rep["steps"]
        assert [s["status"] for s in st] == [of.EXECUTED, of.EXECUTED, of.BLOCKED], st
        assert st[0]["verified"] == st[1]["verified"] == "matches", st
        again = flow.run()
        assert all(s.get("resumed") for s in again["steps"][:2])
        inv = flow.undo_plan()
        assert isinstance(inv, list)
        back = w.apply(ok(w.plan(inv, f"undo-{tag}")), spec())
        assert all(d.status == "done" for d in back), back[-1].refusal
        assert o("res.partner", "read", [[pid]], {"fields": ["ref"]})[0]["ref"] == "old"
        assert not o("res.partner.category", "search_count", [[("name", "=", f"flow tag {tag}")]])
    finally:  # teardown: archive the bot user; the sandbox DB stays
        o("res.users", "write", [[bot], {"active": False}])
