"""BOT-R4-POSTING live: Odoo 17 (18117) and 20 (18120) with account + stock, ODOO_LIVE=1.

Through Poster (Walker call step, WriteGate, proven sinkhole hold): post a balanced journal
entry and undo it with a posted reversal; post a payment and undo it (draft + cancel);
validate a receipt and undo it with a validated return (refused fail-closed on 20 when the
return route is not on the target). Probes: a posted
entry refuses, the approved count must match; inventory count applied and counter-counted.
"""

from __future__ import annotations

import time
import uuid
from datetime import date
from pathlib import Path

import pytest

from app.bot_verify import targets as tg
from app.bots import before_image as bi
from app.bots import guard as gd
from app.bots import posting as po
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
from tests.test_nf_bot_walker import Store, spec

pytestmark = [pytest.mark.no_app_db, pytest.mark.skipif(not LIVE, reason="set ODOO_LIVE=1")]
EVIDENCE = Path.home() / ".ingenium_nf" / "nfwt" / "BOT-R4-POSTING_live.txt"


class J(Json):
    """Buttons like account.payment.action_post return None: JSON-RPC then omits "result"."""

    def _call(self, service, method, args):  # noqa: ANN001, ANN202
        try:
            return super()._call(service, method, args)
        except KeyError:
            return None


def _xid(o: Json, mod: str, name: str) -> int:
    r = o(
        "ir.model.data",
        "search_read",
        [[("module", "=", mod), ("name", "=", name)]],
        {"fields": ["res_id"]},
    )
    return r[0]["res_id"]


@pytest.mark.parametrize("v", [17, 20])
def test_live_post_undo_and_probes(v, engine, tmp_path, monkeypatch) -> None:  # noqa: F811
    o = J(v)
    t0, tag, today = time.time(), uuid.uuid4().hex[:6], date.today().isoformat()
    monkeypatch.setattr(tg, "_STORE", Store())
    uf = "groups_id" if v < 19 else "group_ids"
    grp = [
        _xid(o, "base", "group_system"),
        _xid(o, "account", "group_account_manager"),
        _xid(o, "stock", "group_stock_manager"),
    ]
    bot = o(
        "res.users",
        "create",  # setup: dedicated Bot user
        [{"name": f"r4 bot {tag}", "login": f"r4bot{tag}", uf: [(6, 0, grp)]}],
    )
    acc = [
        o("account.account", "search", [[("account_type", "=", t)]], {"limit": 1})[0]
        for t in ("asset_current", "income")
    ]
    misc = o("account.journal", "search", [[("type", "=", "general"), ("code", "=", "MISC")]], {})[
        0
    ]
    bank = o("account.journal", "search", [[("type", "=", "bank")]], {"limit": 1})[0]
    partner = o("res.partner", "create", [{"name": f"r4 p {tag}"}])
    move = o(
        "account.move",
        "create",
        [
            {  # setup: draft balanced entry dated today
                "move_type": "entry",
                "journal_id": misc,
                "date": today,
                "line_ids": [
                    (0, 0, {"account_id": acc[0], "debit": 10.0, "name": "r4"}),
                    (0, 0, {"account_id": acc[1], "credit": 10.0, "name": "r4"}),
                ],
            }
        ],
    )
    pay = o(
        "account.payment",
        "create",
        [
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": partner,
                "amount": 5.0,
                "journal_id": bank,
            }
        ],
    )
    ptype = o(
        "stock.picking.type",
        "search_read",
        [[("code", "=", "incoming")]],
        {"fields": ["default_location_dest_id"], "limit": 1},
    )[0]
    vend = o("stock.location", "search", [[("usage", "=", "supplier")]], {"limit": 1})[0]
    dest = ptype["default_location_dest_id"][0]
    pv = {
        "name": f"r4 prod {tag}",
        **({"type": "product"} if v < 18 else {"type": "consu", "is_storable": True}),
    }
    prod = o("product.product", "create", [pv])
    pick = o(
        "stock.picking",
        "create",
        [
            {
                "picking_type_id": ptype["id"],
                "location_id": vend,
                "location_dest_id": dest,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            **({"name": "r4"} if v < 20 else {}),
                            "product_id": prod,
                            "product_uom_qty": 2.0,
                            "location_id": vend,
                            "location_dest_id": dest,
                        },
                    )
                ],
            }
        ],
    )
    o("stock.picking", "action_confirm", [[pick]], {})  # setup
    for m in o("stock.move", "search", [[("picking_id", "=", pick)]], {}):
        o("stock.move", "write", [[m], {"quantity": 2.0}], {})  # setup
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
    p = po.Poster(w)
    log = [f"v{v} {time.strftime('%H:%M')} tag={tag}"]

    def plan(op: str, ids: tuple, n: int | None = None):  # noqa: ANN202
        return p.plan(op, ids, f"{op}-{tag}", len(ids) if n is None else n)

    # probes first (nothing posted)
    assert "approved plan" in plan("move_post", (move,), 2).reason
    # lock-date probes stay unit-only: Odoo refuses to lock a period holding drafts
    log.append("probe: count ok")

    # journal entry: post + reversal
    pp = plan("move_post", (move,))
    assert isinstance(pp, po.PostPlan), pp
    d = p.apply(pp, spec(3))
    assert d.status == "done", d.refusal
    again = plan("move_post", (move,))
    assert isinstance(again, Refusal), again  # posted: refused
    u = p.undo(d, spec(3))
    assert u.status == "done", u.refusal
    rev = o("account.move", "read", [list(u.undo_ids), ["state", "reversed_entry_id"]], {})
    assert [r["state"] for r in rev] == ["posted"] and rev[0]["reversed_entry_id"][0] == move
    log.append(f"move {move} posted, reversal {u.undo_ids} posted")

    # payment: post + draft/cancel
    pp = plan("payment_post", (pay,))
    assert isinstance(pp, po.PostPlan), pp
    d = p.apply(pp, spec(3))
    assert d.status == "done", d.refusal
    u = p.undo(d, spec(3))
    assert u.status == "done", u.refusal
    st = o("account.payment", "read", [[pay], ["state"]], {})[0]["state"]
    assert st in ("cancel", "canceled"), st
    log.append(f"payment {pay} posted then {st}")

    # receipt: validate + return
    pp = plan("picking_validate", (pick,))
    if isinstance(pp, Refusal):
        assert v >= 20 and "not verified" in pp.reason, pp
        log.append(f"picking refused fail-closed: {pp.reason}")
    else:
        d = p.apply(pp, spec(3))
        assert d.status == "done", d.refusal
        u = p.undo(d, spec(3))
        assert u.status == "done", u.refusal
        log.append(f"picking {pick} done, return {u.undo_ids} done")

    # inventory count: apply + counter-count (own product; the quant has the WH company)
    prod2 = o("product.product", "create", [{**pv, "name": f"r4 count {tag}"}])
    inv = {"context": {"inventory_mode": True}}
    q = o(
        "stock.quant",
        "create",
        [{"product_id": prod2, "location_id": dest, "inventory_quantity": 4.0}],
        inv,
    )  # setup: a count
    q = q[0] if isinstance(q, list) else q
    pp = plan("inventory_apply", (q,))
    assert isinstance(pp, po.PostPlan), pp
    d = p.apply(pp, spec(3))
    assert d.status == "done", d.refusal
    assert o("stock.quant", "read", [[q], ["quantity"]], {})[0]["quantity"] == 4.0
    u = p.undo(d, spec(3))
    assert u.status == "done", u.refusal
    assert o("stock.quant", "read", [[q], ["quantity"]], {})[0]["quantity"] == 0.0
    log.append(f"quant {q} 0 -> 4 applied, counter-count back to 0 (side {d.extra})")
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("a") as fh:
        fh.write(" | ".join(log) + f" | {time.time() - t0:.0f}s\n")
