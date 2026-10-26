"""BOT-V20-ACCESS live: Odoo 17 (18117) and 20 (18120) sandboxes over JSON-RPC, ODOO_LIVE=1.

Drift: every allowed field vs live fields_get (19 is checked from source only: no sandbox).
Real change then undo through WriteGate: create group -> access row -> record rule -> add user
-> modify row; undo all in reverse; end state equals start. Lockout refusal on the Bot itself.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from app.bots import access as ac
from app.bots import before_image as bi
from app.bots import guard as gd
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
from tests.test_nf_bot_sinkhole_live import LIVE, Json

pytestmark = [pytest.mark.no_app_db, pytest.mark.skipif(not LIVE, reason="set ODOO_LIVE=1")]
EVIDENCE = Path.home() / ".ingenium_nf" / "nfwt" / "BOT-V20-ACCESS_live.txt"
_N = iter(range(10**6))


def spec() -> gd.RunSpec:
    return gd.RunSpec(
        FP,
        "x",
        "bot-1",
        "R8",
        "RF-R8",
        gd.Approval(3, "alice"),
        f"live{uuid.uuid4().hex}",
        rehearsal_id="rh-1",
    )


@pytest.mark.parametrize("v", [17, 20])
def test_live_drift_change_undo_and_lockout(v, engine, tmp_path) -> None:  # noqa: F811
    o = Json(v)
    t0, tag = time.time(), uuid.uuid4().hex[:6]
    vm = ac.detect(ac.df.ReadOnly(o))
    assert vm.key == ("20" if v >= 20 else "17-18")
    for model, want in ac.ALLOWED[vm.key].items():  # drift: allowed fields vs fields_get
        meta = o(model, "fields_get", [list(want)], {"attributes": ["type", "store", "readonly"]})
        for f, typ in want.items():
            m = meta[f]
            assert m["type"] == typ and m.get("store") and not m.get("readonly"), (model, f, m)
    uf = vm.user_groups
    user = o("res.users", "create", [{"name": f"v20acc {tag}", "login": f"v20acc{tag}"}])  # setup
    sysg = o(
        "ir.model.data",
        "search_read",
        [[("module", "=", "base"), ("name", "=", "group_system")]],
        {"fields": ["res_id"]},
    )[0]["res_id"]
    bot = o(  # setup: a dedicated Bot admin, so admin (uid 2) stays the human admin
        "res.users",
        "create",
        [{"name": f"v20acc bot {tag}", "login": f"v20bot{tag}", uf: [(6, 0, [sysg])]}],
    )
    start_groups = sorted(o("res.users", "read", [[user]], {"fields": [uf]})[0][uf])
    _clean(engine)
    sw = gd.KillSwitch(engine, lambda s: OWNER, grant_source=fake_owner)
    L = ac.AccessLayer(
        o,
        gd.WriteGate(sw, AuditLog(engine, anchor=ANCHOR), o, REH),
        bi.ImageStore(tmp_path / "bi"),
        bot_uid=bot,
    )

    def do(op):
        p = L.plan(op)
        assert isinstance(p, ac.Plan), p
        r = L.apply(p, spec())
        assert r.status == "done", (r.status, r.refusal, getattr(L, "last_log", None))
        return r

    done = [do(ac.GroupSpec(name=f"ingenium probe {tag}"))]
    g = done[0].record_id
    widen = L.plan(ac.GroupSpec(sysg, implied_add=(g,)))  # Bot gains via implied chain
    assert isinstance(widen, Refusal) and ("Bot" in widen.reason or v < 19), widen
    done.append(do(ac.AccessRow(model="res.partner", group_id=g, perms=("read",), name=f"p {tag}")))
    done.append(
        do(
            ac.RecordRule(
                model="res.partner",
                group_ids=(g,),
                domain="[(1, '=', 1)]",
                perms=("read",),
                name=f"r {tag}",
            )
        )
    )
    done.append(do(ac.UserGroups(user, add=(g,))))
    done.append(do(ac.AccessRow(done[1].record_id, perms=("read", "write"))))
    assert sorted(done[1].after) == sorted(done[2].after)  # one shape for access and rule
    for r in reversed(done):
        u = L.undo(r, spec())
        assert isinstance(u, ac.Result) and u.status == "done", (u, getattr(L, "last_log", None))
    assert sorted(o("res.users", "read", [[user]], {"fields": [uf]})[0][uf]) == start_groups
    assert not o("res.groups", "search", [[("id", "=", g)]], {})
    refused = L.plan(ac.UserGroups(bot, remove=(sysg,)))
    assert isinstance(refused, Refusal) and refused.rule == "RF-R8", refused
    o("res.users", "write", [[user, bot], {"active": False}])  # setup cleanup
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("a") as fh:
        fh.write(
            f"{time.strftime('%Y-%m-%d %H:%M')} odoo {v}: vm={vm.key} drift=ok "
            f"applied={len(done)} undone={len(done)} lockout_refused='{refused.reason}' "
            f"widen_refused='{widen.reason}' "
            f"{time.time() - t0:.1f}s\n"
        )
