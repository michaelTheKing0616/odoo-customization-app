"""BOT-LOCKOUT-SIM live: Odoo 17 + 20 over JSON-RPC (ports 18217-18220, DB ingenium_nf2_lock_<v>).

Needs ODOO_LIVE=1. Fixtures are seeded by a test-side writer; the simulator only reads
(every simulator call is recorded and must be a read method).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.bots import diff as df
from app.bots import lockout as lk
from app.bots.risk.rules import Refusal
from tests.test_nf_bot_diff_blast_live import LIVE, Json

pytestmark = [pytest.mark.no_app_db, pytest.mark.skipif(not LIVE, reason="live: ODOO_LIVE=1")]
EVIDENCE = Path.home() / ".ingenium_nf" / "nfwt" / "BOT-LOCKOUT-SIM_live.txt"


class Lock(Json):
    def __init__(self, v: int) -> None:
        self.url = f"http://127.0.0.1:182{v}"
        self.db = f"ingenium_nf2_lock_{v}"
        self.uid = self._call("common", "login", [self.db, "admin", "admin"])


@pytest.fixture(scope="module", params=[17, 20])
def env(request):
    v, o = request.param, Lock(request.param)
    gf = "group_ids" if v >= 19 else "groups_id"
    x = {
        n: o("ir.model.data", "check_object_reference", ["base", n])[1]
        for n in ("group_system", "group_user", "group_portal")
    }
    tag = uuid.uuid4().hex[:6]

    def mk(name: str, groups: list[int]) -> int:
        return o(
            "res.users",
            "create",
            [{"name": f"nf2 {name} {tag}", "login": f"{name}{tag}", gf: [(6, 0, groups)]}],
        )

    ids = {
        "bot": mk("bot", [x["group_system"]]),
        "intl": mk("intl", [x["group_user"]]),
        "portal": mk("portal", [x["group_portal"]]),
    }
    # no other human admins: only uid 2 (admin) + the bot
    others = o(
        "res.users",
        "search",
        [[("id", "not in", [2, ids["bot"]]), (gf, "in", [x["group_system"]])]],
    )
    if others:
        o("res.users", "write", [others, {"active": False}])
    return v, o, gf, x, ids


class Spy:
    def __init__(self, o) -> None:
        self.o, self.methods = o, set()

    def __call__(self, model, method, args, kw=None):
        self.methods.add(method)
        return self.o(model, method, args, kw)


def _sim(o, bot, *chs):
    s = Spy(o)
    r = lk.simulate(s, list(chs), bot_uid=bot)
    assert s.methods <= df.READ_METHODS
    return r


def _log(v, name, r):
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("a") as fh:
        fh.write(f"{v}\t{name}\t{r if isinstance(r, Refusal) else r.card_lines()}\n")


def test_live_harmless_change_reads_cleanly(env):
    v, o, gf, x, ids = env
    r = _sim(o, ids["bot"], lk.Change("res.users", "write", (ids["intl"],), {"lang": "en_US"}))
    _log(v, "harmless", r)
    assert isinstance(r, lk.LockoutSim) and r.admins_before >= 1 and not r.impacts


def test_live_last_admin_refused(env):
    v, o, gf, x, ids = env
    r = _sim(o, ids["bot"], lk.Change("res.users", "write", (2,), {gf: [(3, x["group_system"])]}))
    _log(v, "last-admin", r)
    assert isinstance(r, Refusal) and "no working admin" in r.reason


def test_live_portal_to_internal(env):
    v, o, gf, x, ids = env
    r = _sim(
        o,
        ids["bot"],
        lk.Change("res.users", "write", (ids["portal"],), {gf: [(6, 0, [x["group_user"]])]}),
    )
    _log(v, "portal-to-internal", r)
    assert any("becomes an internal user" in ln for i in r.impacts for ln in i.lines)


def test_live_bot_demotion_and_cycle(env):
    v, o, gf, x, ids = env
    gu = "user_ids" if v >= 19 else "users"
    r = _sim(
        o,
        ids["bot"],
        lk.Change("res.groups", "write", (x["group_system"],), {gu: [(3, ids["bot"])]}),
    )
    _log(v, "bot-demoted", r)
    assert isinstance(r, Refusal) and "Bot's own" in r.reason
    r = _sim(
        o,
        ids["bot"],
        lk.Change(
            "res.groups", "write", (x["group_user"],), {"implied_ids": [(4, x["group_system"])]}
        ),
    )
    _log(v, "cycle", r)
    assert isinstance(r, Refusal) and "circular" in r.reason


def test_live_field_drift_and_role(env):
    v, o, gf, x, ids = env
    models = ["res.users", "res.groups", "ir.access" if v >= 20 else "ir.model.access"]
    models += [] if v >= 20 else ["ir.rule"]
    for m in models:
        meta = o(m, "fields_get", [[]], {"attributes": lk.META_ATTRS})
        for f, d in meta.items():
            if d.get("readonly") and f not in lk.HANDLED_FIELDS.get(m, ()):
                continue
            ok = lk.field_verdict(m, f, meta) is None
            known = f in lk.HANDLED_FIELDS.get(m, ()) or f in lk.FIELD_ALLOWLIST.get(m, {})
            reified = m == "res.users" and f.startswith(("in_group_", "sel_groups_"))
            assert ok <= (known or reified), f"{v} {m}.{f} passes without review"
    um = o("res.users", "fields_get", [["role"]], {"attributes": lk.META_ATTRS})
    if v >= 19:
        assert "role" in um and lk.field_verdict("res.users", "role", um) is not None
        r = _sim(o, ids["bot"], lk.Change("res.users", "write", (2,), {"role": "group_user"}))
        _log(v, "role", r)
        assert isinstance(r, Refusal)
    else:
        assert "role" not in um


def test_live_every_prefix_checked(env):
    v, o, gf, x, ids = env
    r = _sim(
        o,
        ids["bot"],
        lk.Change("res.users", "write", (2,), {gf: [(3, x["group_system"])]}),
        lk.Change("res.users", "write", (2,), {gf: [(4, x["group_system"])]}),
    )
    _log(v, "prefix", r)
    assert isinstance(r, Refusal) and r.reason.startswith("step 1:")
