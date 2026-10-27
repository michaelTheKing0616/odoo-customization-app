"""BOT-GENERIC-WALKER live: Odoo 17/19/20 (1811<v>) over JSON-RPC, ODOO_LIVE=1.

ODOO_LIVE_VERSIONS (default "17,20") picks the stacks that are up.

One walk over three models (create res.partner.category, write res.partner incl. a many2many,
write res.partner.industry) through WriteGate; a re-run replays from the ledger; the undo walk
restores the start state. Refusals checked live: res.users, an unknown field, an unknown button.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest

from app.bot_verify import targets as tg
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
from tests.test_nf_bot_sinkhole_live import LIVE, Json
from tests.test_nf_bot_walker import Store, ok, spec

pytestmark = [pytest.mark.no_app_db, pytest.mark.skipif(not LIVE, reason="set ODOO_LIVE=1")]
EVIDENCE = Path.home() / ".ingenium_nf" / "nfwt" / "BOT-GENERIC-WALKER_live.txt"
S = wk.Step


VERSIONS = [int(x) for x in os.environ.get("ODOO_LIVE_VERSIONS", "17,20").split(",")]


@pytest.mark.parametrize("v", VERSIONS)
def test_live_walk_change_replay_undo(v, engine, tmp_path, monkeypatch) -> None:  # noqa: F811
    o = Json(v)
    t0, tag = time.time(), uuid.uuid4().hex[:6]
    monkeypatch.setattr(tg, "_STORE", Store())
    uf = "groups_id" if v < 19 else "group_ids"
    sysg = o(
        "ir.model.data",
        "search_read",
        [[("module", "=", "base"), ("name", "=", "group_system")]],
        {"fields": ["res_id"]},
    )[0]["res_id"]
    bot = o(  # setup: a dedicated Bot user; admin (uid 2) stays the human admin
        "res.users",
        "create",
        [{"name": f"walker bot {tag}", "login": f"walkbot{tag}", uf: [(6, 0, [sysg])]}],
    )
    partner = o("res.partner", "create", [{"name": f"walk p {tag}"}])  # setup
    tag0 = o("res.partner.category", "create", [{"name": f"walk t0 {tag}"}])  # setup
    ind = o("res.partner.industry", "create", [{"name": f"walk ind {tag}"}])  # setup
    snap = lambda: (  # noqa: E731
        o("res.partner", "read", [[partner]], {"fields": ["name", "comment", "category_id"]}),
        o("res.partner.industry", "read", [[ind]], {"fields": ["name", "full_name"]}),
        o("res.partner.category", "search_count", [[("name", "like", f"walk new {tag}")]], {}),
    )
    start = snap()
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
    steps = [
        S("create", "res.partner.category", values={"name": f"walk new {tag}"}),
        S(
            "write",
            "res.partner",
            (partner,),
            {"name": f"walk p2 {tag}", "comment": "<p>x</p>", "category_id": [(6, 0, [tag0])]},
        ),
        S(
            "write",
            "res.partner.industry",
            (ind,),
            {"name": f"walk ind2 {tag}", "full_name": "walk full"},
        ),
    ]
    walk = ok(w.plan(steps, f"live-{tag}"))
    done = w.apply(walk, spec())
    assert [d.status for d in done] == ["done"] * 3, done[-1].refusal
    mid = snap()
    assert (
        mid[0][0]["category_id"] == [tag0] and mid[1][0]["full_name"] == "walk full" and mid[2] == 1
    )
    again = w.apply(walk, spec())  # same plan: replayed from the ledger, nothing written twice
    assert all(d.replayed for d in again) and snap() == mid
    inv = w.undo_steps(done)
    assert isinstance(inv, list) and len(inv) == 3, inv
    back = w.apply(ok(w.plan(inv, f"undo-{tag}")), spec())
    assert all(d.status == "done" for d in back), back[-1].refusal
    end = snap()
    assert end == start, (start, end)
    refusals = [
        w.plan([S("write", "res.users", (bot,), {"name": "x"})], "r1"),
        w.plan([S("write", "res.partner", (partner,), {"nope_x": 1})], "r2"),
        w.plan([S("call", "res.partner", (partner,), method="action_unknown_x")], "r3"),
        w.plan(  # nested create of a refused model through a relation
            [
                S(
                    "write",
                    "res.partner",
                    (partner,),
                    {"user_ids": [(0, 0, {"name": "x", "login": f"x{tag}"})]},
                )
            ],
            "r4",
        ),
        w.plan([S("write", "res.partner.category", (tag0,), {"name": " "})], "r5"),  # required
        w.plan([S("write", "x_unreviewed_model", (1,), {"x_name": "x"})], "r6"),
    ]
    assert all(isinstance(r, Refusal) for r in refusals), refusals
    for m, i in (
        ("res.partner.industry", ind),
        ("res.partner", partner),
        ("res.partner.category", tag0),
    ):
        o(m, "unlink", [[i]])  # teardown of setup records
    o("res.users", "write", [[bot], {"active": False}])  # teardown
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("a") as fh:
        fh.write(
            f"{time.strftime('%F %T')} v{v} walk create+write+write done, replay ok, undo "
            f"restored start; refusals: {[r.reason[:60] for r in refusals]} "
            f"({time.time() - t0:.1f}s)\n"
        )
