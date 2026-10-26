"""BOT-R6-DELETE-MERGE live: archive, safe delete, partner merge + undo on Odoo 17 and 20.

Needs ODOO_LIVE=1. Stacks: NF2_LIVE_URL_<v> (default http://127.0.0.1:182<v>, ports
18217-18220 only), DB ingenium_nf2_r6_<v> with ``contacts`` installed, admin/admin.
Fixtures are seeded by a test-side writer; the code under test writes only via the gate.
The snapshot proof is a stand-in Verified (the snapshot suite covers the real one).
"""

from __future__ import annotations

import dataclasses
import os
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.bots import before_image as bi
from app.bots import guard as gd
from app.bots import removal as rm
from app.bots import walker as wk
from app.bots.audit import AuditLog
from app.bots.risk.rules import Refusal
from tests.test_nf_bot_diff_blast_live import Json as _Json
from tests.test_nf_bot_kill_audit import (  # noqa: F401
    ANCHOR,
    FP,
    OWNER,
    REH,
    _clean,
    engine,
    fake_owner,
)
from tests.test_nf_bot_removal import snap

LIVE = os.environ.get("ODOO_LIVE") == "1"
pytestmark = [pytest.mark.no_app_db, pytest.mark.skipif(not LIVE, reason="live: ODOO_LIVE=1")]
EVIDENCE = Path.home() / ".ingenium_nf" / "nfwt" / "BOT-R6_live.txt"
RA = {"context": {"active_test": False}}


class Json(_Json):
    def __init__(self, v: int) -> None:  # same JSON-RPC client, this card's DB
        self.url = os.environ.get(f"NF2_LIVE_URL_{v}", f"http://127.0.0.1:182{v}")
        assert 18217 <= int(self.url.rsplit(":", 1)[1]) <= 18220, "nf2 live ports only"
        self.db = f"ingenium_nf2_r6_{v}"
        self.uid = self._call("common", "login", [self.db, "admin", "admin"])
        assert self.uid


def log(v: int, line: str) -> None:
    with EVIDENCE.open("a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} v{v} {line}\n")


@pytest.mark.parametrize("v", [17, 20])
def test_live_archive_delete_merge_undo(v, engine, tmp_path) -> None:  # noqa: F811
    _clean(engine)
    o = Json(v)
    sw = gd.KillSwitch(engine, lambda s: OWNER, grant_source=fake_owner)
    w = wk.Walker(
        o,
        sw,
        AuditLog(engine, anchor=ANCHOR),
        REH,
        bi.ImageStore(tmp_path / "bi"),
        wk.Ledger(tmp_path / "l.json"),
        db=FP,
        bot_uid=o.uid,
        version=v,
    )
    r = rm.Removal(w)
    tag = uuid.uuid4().hex[:6]
    mk = lambda **vals: o("res.partner", "create", [vals])  # noqa: E731 - test-side seeding
    z, t = mk(name=f"r6 archive {tag}"), mk(name=f"r6 delete {tag}")
    a, b = mk(name=f"r6 keep {tag}", is_company=True), mk(name=f"r6 dup {tag}", is_company=True)
    kid = mk(name=f"r6 kid {tag}", parent_id=b)
    o("res.partner", "message_post", [[b]], {"body": "r6 note"})
    n = iter(range(10**6))

    def spec(**kw: Any) -> gd.RunSpec:
        s = gd.RunSpec(
            FP,
            "x",
            "bot-1",
            "R6",
            "RF-R6",
            gd.Approval(3, "alice"),
            f"live{tag}{next(n)}",
            rehearsal_id="rh-1",
        )
        return dataclasses.replace(s, **kw)

    p = r.plan_remove("res.partner", [z], f"a{tag}")
    assert isinstance(p, rm.Plan) and p.kind == "archive", p
    res = r.apply(p, spec())
    act = o("res.partner", "read", [[z], ["active"]], RA)[0]["active"]
    log(v, f"archive #{z}: {res.status} active={act}")
    assert res.status == "done" and act is False, res.refusal

    p = r.plan_remove("res.partner", [t], f"d{tag}", allow_delete=True)
    assert isinstance(p, rm.Plan) and p.kind == "delete", p
    res = r.apply(p, spec(snapshot_id="snap:abc"), typed=str(p.count), snapshot=snap())
    left = o("res.partner", "search_count", [[("id", "=", t)]], RA)
    log(v, f"delete #{t}: count={p.count} {p.lines} -> {res.status} left={left}")
    assert res.status == "done" and left == 0, res.refusal

    if v == 17:  # multi-company: bot (admin here) not in a second company -> refused
        cos = o("res.company", "search", [[]], RA)
        extra = cos if len(cos) > 1 else cos + [o("res.company", "create", [{"name": "r6 co2"}])]
        o("res.users", "write", [[o.uid], {"company_ids": [(6, 0, [1])], "company_id": 1}])
        mc = r.plan_merge("res.partner", [a, b], a, f"mc{tag}")
        log(v, f"multi-company, bot not in all {sorted(extra)}: {mc}")
        o("res.users", "write", [[o.uid], {"company_ids": [(6, 0, sorted(extra))]}])
        assert isinstance(mc, Refusal) and "every company" in mc.reason, mc
    p = r.plan_merge("res.partner", [a, b], a, f"m{tag}")
    assert isinstance(p, rm.Plan), p
    res = r.apply(p, spec(snapshot_id="snap:abc"), typed=str(p.count), snapshot=snap())
    kp = o("res.partner", "read", [[kid], ["parent_id"]], RA)[0]["parent_id"]
    gone = not o("res.partner", "search_count", [[("id", "=", b)]], RA)
    log(
        v,
        f"merge #{b}->#{a}: count={p.count} {p.lines} -> {res.status} kid.parent={kp} gone={gone}",
    )
    assert res.status == "done" and gone and kp[0] == a, res.refusal

    u = r.undo_merge(res, spec(), f"u{tag}")
    new = o("res.partner", "search", [[("name", "=", f"r6 dup {tag}")]], RA)
    kp = o("res.partner", "read", [[kid], ["parent_id"]], RA)[0]["parent_id"]
    log(
        v,
        f"undo merge: {u.status} {u.refusal.reason if u.refusal else ''} new={new} kid.parent={kp}",
    )
    assert u.status in ("done", "partial") and len(new) == 1 and kp[0] == new[0], u.refusal
    log(v, f"kill switch after run: {sw.check(FP)}")
