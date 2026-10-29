"""BOT-R4-POSTING: guarded posting / validation over an in-memory Odoo (17/18/19/20 shapes)."""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.bots import posting as po
from app.bots.risk.rules import Refusal
from tests.test_nf_bot_kill_audit import engine  # noqa: F401
from tests.test_nf_bot_walker import F, Odoo, W, m2o, spec  # noqa: F401

pytestmark = pytest.mark.no_app_db
VS = (17, 18, 19, 20)
TODAY = date(2026, 10, 26)


class Books(Odoo):
    """Adds the posting models; buttons do what Odoo does to state."""

    def __init__(self, v: int) -> None:
        super().__init__(v)
        sel = lambda *k: F("selection", selection=[[x, x] for x in k], readonly=True)  # noqa: E731
        pst = (
            ("draft", "posted", "cancel") if v < 18 else ("draft", "in_process", "paid", "canceled")
        )
        self.meta["account.move"].update(
            journal_id=m2o("account.journal"),
            name=F("char"),
            payment_state=sel("not_paid", "paid", "partial"),
            reversed_entry_id=m2o("account.move"),
            restrict_mode_hash_table=F("boolean"),
        )
        self.meta["stock.picking"].update(
            company_id=m2o("res.company"), name=F("char"), picking_type_id=m2o("x")
        )
        self.meta["stock.picking"]["state"]["selection"] += [["confirmed", "confirmed"]]
        add = {
            "account.move.line": {
                "move_id": m2o("account.move"),
                "account_id": m2o("account.account"),
                "debit": F("float"),
                "credit": F("float"),
                "partner_id": m2o("res.partner"),
            },
            "account.payment": {
                "state": sel(*pst),
                "date": F("date"),
                "company_id": m2o("res.company"),
                "journal_id": m2o("account.journal"),
                "amount": F("monetary"),
                "payment_type": sel("inbound", "outbound"),
                "partner_id": m2o("res.partner"),
                "is_reconciled": F("boolean", readonly=True),
            },
            "stock.move": {
                "picking_id": m2o("stock.picking"),
                "product_id": m2o("product.product"),
                "product_uom_qty": F("float"),
                "quantity": F("float"),
                "location_id": m2o("stock.location"),
                "location_dest_id": m2o("stock.location"),
                "state": sel("assigned", "done", "cancel"),
            },
            "product.product": {"tracking": sel("none", "lot", "serial")},
            "stock.quant": {
                "company_id": m2o("res.company"),
                "product_id": m2o("product.product"),
                "location_id": m2o("stock.location"),
                "quantity": F("float"),
                "inventory_quantity": F("float"),
                "inventory_quantity_set": F("boolean"),
            },
            "account.move.reversal": {
                "move_ids": F("many2many", relation="account.move"),
                "date": F("date"),
                "reason": F("char"),
                "journal_id": m2o("account.journal"),
            },
            "stock.return.picking": {"picking_id": m2o("stock.picking")},
        }
        self.meta.update(add)
        for m in add:
            self.rows.setdefault(m, {})
        self.meta["ir.module.module"] = {"name": F("char"), "state": F("char")}
        self.rows["ir.module.module"] = {
            1: {"name": "account", "state": "installed"},
            2: {"name": "l10n_ar_edi", "state": "uninstalled"},
        }
        self.rows["ir.model"] = {i: {"model": m} for i, m in enumerate(self.meta, 500)}
        R = self.rows  # noqa: N806
        R["account.move"][8].update(journal_id=1, name="/")
        R["account.move.line"].update(
            {
                81: {"move_id": 8, "account_id": 1, "debit": 10.0, "credit": 0.0},
                82: {"move_id": 8, "account_id": 2, "debit": 0.0, "credit": 10.0},
            }
        )
        R["account.payment"][20] = {
            "state": "draft",
            "date": "2026-10-20",
            "company_id": 1,
            "journal_id": 1,
            "amount": 5.0,
            "payment_type": "inbound",
        }
        R["stock.picking"][12].update(company_id=1, name="WH/IN/1")
        R["stock.move"][30] = {
            "picking_id": 12,
            "product_id": 40,
            "product_uom_qty": 2.0,
            "quantity": 2.0,
            "location_id": 5,
            "location_dest_id": 8,
            "state": "assigned",
        }
        R["product.product"][40] = {"tracking": "none"}
        R["stock.quant"][50] = {
            "company_id": 1,
            "product_id": 40,
            "location_id": 8,
            "quantity": 3.0,
            "inventory_quantity": 5.0,
            "inventory_quantity_set": True,
        }
        for rs in R.values():
            for r in rs.values():
                r.setdefault("write_date", "2026-10-01 00:00:00")
                r.setdefault("create_uid", 2)
        self.v_ = v
        self.wizard_reply: Any = True

    def __call__(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        R = self.rows  # noqa: N806
        if model == "account.payment" and method == "action_post":
            for i in args[0]:
                R[model][i]["state"] = "posted" if self.v_ < 18 else "in_process"
            return True
        if model == "account.payment" and method in ("action_draft", "action_cancel"):
            for i in args[0]:
                R[model][i]["state"] = "draft" if method == "action_draft" else "cancel"
            return True
        if model == "stock.picking" and method == "button_validate":
            if self.wizard_reply is not True:
                return self.wizard_reply
            for i in args[0]:
                R[model][i]["state"] = "done"
                for m in R["stock.move"].values():
                    if m["picking_id"] == i:
                        m["state"] = "done"
                        q = R["stock.quant"].setdefault(
                            600 + m["location_dest_id"],
                            {
                                "product_id": m["product_id"],
                                "location_id": m["location_dest_id"],
                                "quantity": 0.0,
                                "company_id": 1,
                            },
                        )
                        q["quantity"] += m["quantity"]
            return True
        if model == "stock.quant" and method == "action_apply_inventory":
            for i in args[0]:
                R[model][i].update(
                    quantity=R[model][i]["inventory_quantity"], inventory_quantity_set=False
                )
            return True
        if model == "account.move.reversal" and method == "refund_moves":
            w = R[model][args[0][0]]
            for mid in w["move_ids"]:
                self._create(
                    "account.move", {"reversed_entry_id": mid, "company_id": 1, "date": w["date"]}
                )
            return {"type": "ir.actions.act_window"}
        if model == "stock.return.picking" and method in (
            "create_returns",
            "action_create_returns",
        ):
            assert method == ("create_returns" if self.v_ < 18 else "action_create_returns")
            src = R[model][args[0][0]]["picking_id"]
            rid = self._create("stock.picking", {"origin": "ret", "company_id": 1})
            R["stock.picking"][rid]["state"] = "assigned"
            for m in [m for m in R["stock.move"].values() if m["picking_id"] == src]:
                self._create(
                    "stock.move",
                    {
                        "picking_id": rid,
                        "product_id": m["product_id"],
                        "product_uom_qty": m["product_uom_qty"],
                        "location_id": m["location_dest_id"],
                        "location_dest_id": m["location_id"],
                    },
                )
            return {"res_id": rid}
        if model == "stock.quant" and method == "write" and "inventory_quantity" in args[1]:
            for i in args[0]:
                R[model][i].update(args[1], inventory_quantity_set=True)
            return True
        return super().__call__(model, method, args, kw)


@pytest.fixture
def P(W):  # noqa: N802, F811
    def make(v: int) -> tuple[po.Poster, Books]:
        w, o = W(v, o=Books(v))
        return po.Poster(w, today=TODAY), o

    return make


def plan_or_skip(p: po.Poster, op: str, ids: tuple, n: int | None = None) -> po.PostPlan:
    r = p.plan(op, ids, f"p-{op}", len(ids) if n is None else n)
    if isinstance(r, Refusal) and ("catalogue" in r.reason or "not verified" in r.reason):
        # fail closed: no catalogue row, or the v20 return route is not on this target
        pytest.skip(f"catalogue has no row for {op}: {r.reason}")
    assert isinstance(r, po.PostPlan), r
    return r


def refused(r: Any, part: str) -> None:
    assert isinstance(r, Refusal), r
    assert part in r.reason, r.reason


@pytest.mark.parametrize("v", VS)
def test_move_post_preview_l3_apply_and_credit_note_undo(v, P) -> None:
    p, o = P(v)
    pp = plan_or_skip(p, "move_post", (8,))
    assert pp.tier == 3 and pp.walk.tier == 3
    assert any("debit 10.0 = credit 10.0" in x for x in pp.preview)
    assert "credit note" in pp.counter
    assert p.apply(pp, spec(2)).status == "refused"  # L2 never posts
    d = p.apply(pp, spec(3))
    assert d.status == "done" and o.rows["account.move"][8]["state"] == "posted"
    u = p.undo(d, spec(3))
    assert u.status == "done", u.refusal
    rev = [r for r in o.rows["account.move"].values() if r.get("reversed_entry_id") == 8]
    assert len(rev) == 1 and rev[0]["state"] == "posted"
    assert 8 in o.rows["account.move"]  # never unlinked
    assert not any(c == ("account.move", "unlink") for c in o.calls)


@pytest.mark.parametrize("v", VS)
def test_payment_post_version_states_and_undo(v, P) -> None:
    p, o = P(v)
    d = p.apply(plan_or_skip(p, "payment_post", (20,)), spec(3))
    assert d.status == "done"
    assert o.rows["account.payment"][20]["state"] == ("posted" if v < 18 else "in_process")
    assert p.undo(d, spec(3)).status == "done"
    assert o.rows["account.payment"][20]["state"] == "cancel"


@pytest.mark.parametrize("v", VS)
def test_picking_validate_and_return(v, P) -> None:
    p, o = P(v)
    pp = plan_or_skip(p, "picking_validate", (12,))
    assert any("5 -> 8" in x for x in pp.preview)
    d = p.apply(pp, spec(3))
    assert d.status == "done"
    u = p.undo(d, spec(3))
    assert u.status == "done", u.refusal
    assert o.rows["stock.picking"][u.undo_ids[0]]["state"] == "done"


@pytest.mark.parametrize("v", VS)
def test_inventory_apply_and_counter_adjustment(v, P) -> None:
    p, o = P(v)
    r = p.plan("inventory_apply", (50,), "p", 1)
    if isinstance(r, Refusal):  # catalogue has no row for the button: fail closed
        assert "stock.quant:action_apply_inventory" in r.reason
        return
    assert any("3.0 -> 5.0 (+2.0)" in x for x in r.preview)
    d = p.apply(r, spec(3))
    assert d.status == "done" and o.rows["stock.quant"][50]["quantity"] == 5.0
    assert p.undo(d, spec(3)).status == "done" and o.rows["stock.quant"][50]["quantity"] == 3.0


# ---------------------------------------------------------------- probes: irrecoverable cases
@pytest.mark.parametrize("v", VS)
def test_count_must_match_approved_plan(v, P) -> None:
    p, _ = P(v)
    refused(p.plan("move_post", (8,), "p", 2), "approved plan")
    refused(p.plan("move_post", (8, 8), "p", 2), "distinct")
    refused(p.plan("frob", (8,), "p", 1), "unknown posting op")


@pytest.mark.parametrize("v", VS)
def test_locked_period_refuses_post_and_undo(v, P) -> None:
    p, o = P(v)
    f = "period_lock_date" if v < 18 else "hard_lock_date"
    o.rows["res.company"][1][f] = "2026-10-05"  # doc dated 2026-10-01
    refused(p.plan("move_post", (8,), "p", 1), "locked period")
    o.rows["res.company"][1][f] = "2026-10-31"  # today locked: undo impossible
    refused(p.plan("picking_validate", (12,), "p", 1), "locked period")


@pytest.mark.parametrize("v", VS)
def test_already_posted_sent_edi_unbalanced_refused(v, P) -> None:
    p, o = P(v)
    o.meta["account.move"]["edi_state"] = F("char")  # metadata is read once per walker
    refused(p.plan("move_post", (9,), "p", 1), "not ready")
    o.rows["account.move"][8]["is_move_sent"] = True
    refused(p.plan("move_post", (8,), "p", 1), "already sent")
    o.rows["account.move"][8]["is_move_sent"] = False
    o.rows["account.move.line"][82]["credit"] = 9.0
    refused(p.plan("move_post", (8,), "p", 1), "unbalanced")
    o.rows["account.move.line"][82]["credit"] = 10.0
    o.rows["account.move"][8]["edi_state"] = "sent"
    refused(p.plan("move_post", (8,), "p", 1), "e-invoice")


@pytest.mark.parametrize("v", VS)
def test_tracked_partial_and_wizard_reply(v, P) -> None:
    p, o = P(v)
    o.rows["product.product"][40]["tracking"] = "serial"
    refused(p.plan("picking_validate", (12,), "p", 1), "lot/serial")
    o.rows["product.product"][40]["tracking"] = "none"
    o.rows["stock.move"][30]["quantity"] = 1.0
    refused(p.plan("picking_validate", (12,), "p", 1), "backorder")
    o.rows["stock.move"][30]["quantity"] = 2.0
    pp = plan_or_skip(p, "picking_validate", (12,))
    o.wizard_reply = {"type": "ir.actions.act_window", "res_model": "stock.backorder.confirmation"}
    assert p.apply(pp, spec(3)).status == "mismatch"


@pytest.mark.parametrize("v", VS)
def test_changed_since_preview_and_reconciled_undo(v, P) -> None:
    p, o = P(v)
    pp = plan_or_skip(p, "move_post", (8,))
    o.rows["account.move.line"][81]["debit"] = 11.0
    o.rows["account.move.line"][82]["credit"] = 11.0
    refused(p.apply(pp, spec(3)).refusal, "changed since the preview")
    pp = plan_or_skip(p, "payment_post", (20,))
    d = p.apply(pp, spec(3))
    o.rows["account.payment"][20]["is_reconciled"] = True
    u = p.undo(d, spec(3))
    assert u.status == "refused" and "changed since" in u.refusal.reason
    pp2 = plan_or_skip(p, "picking_validate", (12,))
    d2 = p.apply(pp2, spec(3))
    for q in (50, 608):  # stock already shipped on
        o.rows["stock.quant"][q]["quantity"] = 0.0
    refused(p.undo(d2, spec(3)).refusal, "already left")


def test_writes_only_through_the_gate() -> None:
    from tests.test_nf_bot_kill_audit import READ_PASSTHROUGH, rpc_write_calls

    src = Path(po.__file__).read_text()
    pins = READ_PASSTHROUGH["posting.py"]
    assert rpc_write_calls(src, pins) == [] and "execute_kw" not in src and "xmlrpc" not in src
    tree = ast.parse(src)
    calls = {ast.unparse(c.func) for c in ast.walk(tree) if isinstance(c, ast.Call)}
    assert "self.w.gate.call" in calls and not any(
        c.endswith((".rpc", "w.rpc", "quiet")) for c in calls
    )
    assert "unlink" not in src.replace("never an unlink", "").replace("Never an unlink", "")


# ---------------------------------------------------------------- review round 2
def _model(o: Books, m: str, meta: dict, rows: dict) -> None:
    o.meta[m], o.rows[m] = meta, rows
    o.rows["ir.model"][900 + len(o.rows["ir.model"])] = {"model": m}


LIVE_PROVIDERS = {
    "move_post": ("account_edi_proxy_client.user", {"edi_mode": F("char")}, {"edi_mode": "prod"}),
    "payment_post": ("payment.provider", {"state": F("char")}, {"state": "enabled"}),
    "picking_validate": (
        "delivery.carrier",
        {"prod_environment": F("boolean")},
        {"prod_environment": True},
    ),
}


@pytest.mark.parametrize("v", VS)
@pytest.mark.parametrize("op", sorted(LIVE_PROVIDERS))
def test_live_provider_refuses_button_with_no_values(v, op, P) -> None:
    """Review probe (test_probe_post1) made permanent: a button carries no values, yet a live
    payment provider / production carrier / e-invoice connection must be seen and refused."""
    p, o = P(v)
    m, meta, row = LIVE_PROVIDERS[op]
    ids = {"move_post": (8,), "payment_post": (20,), "picking_validate": (12,)}[op]
    _model(o, m, meta, {1: dict(row)})
    r = p.plan(op, ids, "p", 1)
    if isinstance(r, Refusal) and "not verified" in r.reason:
        return  # v20 picking: refused earlier, still closed
    refused(r, "cannot be held or undone")
    o.rows[m][1] = {k: (False if k == "prod_environment" else "test") for k in row}
    r = p.plan(op, ids, "p", 1)
    assert isinstance(r, (po.PostPlan, Refusal)) and not (
        isinstance(r, Refusal) and "cannot be held" in r.reason
    )


@pytest.mark.parametrize("v", VS)
def test_payment_token_and_production_carrier_refused(v, P) -> None:
    p, o = P(v)
    o.meta["account.payment"]["payment_token_id"] = m2o("payment.token")
    o.meta["stock.picking"]["carrier_id"] = m2o("delivery.carrier")
    _model(
        o, "delivery.carrier", {"prod_environment": F("boolean")}, {3: {"prod_environment": True}}
    )
    o.rows["account.payment"][20]["payment_token_id"] = 77
    refused(p.plan("payment_post", (20,), "p", 1), "saved card")
    o.rows["stock.picking"][12]["carrier_id"] = 3
    r = p.plan("picking_validate", (12,), "p", 1)
    assert isinstance(r, Refusal) and ("production" in r.reason or "not verified" in r.reason)


@pytest.mark.parametrize("v", VS)
def test_deferral_and_chained_moves_refused(v, P) -> None:
    p, o = P(v)
    o.meta["account.move.line"]["deferred_start_date"] = F("date")
    o.meta["stock.move"]["move_dest_ids"] = F("many2many", relation="stock.move")
    o.rows["account.move.line"][81]["deferred_start_date"] = "2026-11-01"
    refused(p.plan("move_post", (8,), "p", 1), "deferral")
    o.rows["stock.move"][30]["move_dest_ids"] = [31]
    r = p.plan("picking_validate", (12,), "p", 1)
    assert isinstance(r, Refusal) and ("chained" in r.reason or "not verified" in r.reason)


@pytest.mark.parametrize("v", VS)
def test_unexpected_side_records_stop_and_expected_are_listed(v, P, engine) -> None:  # noqa: F811
    p, o = P(v)
    o.meta["account.move"]["origin_payment_id"] = m2o("account.payment")
    real = Books.__call__

    def side(self, model, method, args, kw=None):  # noqa: ANN001, ANN202
        out = real(self, model, method, args, kw)
        if (model, method) == ("account.payment", "action_post"):
            self._create("account.move", {"origin_payment_id": 20, "company_id": 1})
        if (model, method) == ("account.move", "action_post"):
            self._create("account.move", {"ref": "deferral", "company_id": 1})
        return out

    o.__class__ = type("SideBooks", (Books,), {"__call__": side})
    d = p.apply(plan_or_skip(p, "payment_post", (20,)), spec(3))
    assert d.status == "done" and list(d.extra) == ["expected account.move"]
    d = p.apply(plan_or_skip(p, "move_post", (8,)), spec(3))
    assert d.status == "needs-human" and d.extra.get("account.move"), d
    assert "kill switch on" in d.refusal.reason
    assert p.w.gate.switch.check(p.w.db) is not None  # writes now stopped for this DB


@pytest.mark.parametrize("v", VS)
def test_einvoice_routes_refuse_move_post(v, P) -> None:
    """Older account_edi framework (journal formats), Peppol registration and l10n e-invoice
    data each refuse posting; unreadable journal formats refuse too."""
    p, o = P(v)
    _model(o, "account.edi.format", {"name": F("char")}, {1: {"name": "ZATCA"}})
    refused(p.plan("move_post", (8,), "p", 1), "journal formats unreadable")
    _model(o, "account.journal", {"edi_format_ids": F("many2many")}, {1: {"edi_format_ids": [1]}})
    refused(p.plan("move_post", (8,), "p", 1), "active e-invoice formats")
    o.rows["account.journal"][1]["edi_format_ids"] = []
    assert isinstance(p.plan("move_post", (8,), "p", 1), po.PostPlan)
    p, o = P(v)
    o.meta["res.company"]["account_peppol_proxy_state"] = F("char")
    for cid in o.rows["res.company"]:
        o.rows["res.company"][cid]["account_peppol_proxy_state"] = "active"
    refused(p.plan("move_post", (8,), "p", 1), "Peppol")
    p, o = P(v)
    o.meta["account.move"]["l10n_sa_edi_chain_index"] = F("integer")
    o.rows["account.move"][8]["l10n_sa_edi_chain_index"] = 3
    refused(p.plan("move_post", (8,), "p", 1), "e-invoice data")
    o.rows["account.move"][8]["l10n_sa_edi_chain_index"] = 0
    assert isinstance(p.plan("move_post", (8,), "p", 1), po.PostPlan)


@pytest.mark.parametrize("v", VS)
def test_installed_l10n_edi_module_refuses_move_post(v, P) -> None:
    """l10n_ar_edi asks AFIP for the CAE inside action_post: empty move fields, still refused."""
    p, o = P(v)
    assert isinstance(p.plan("move_post", (8,), "p", 1), po.PostPlan)  # not installed: ok
    o.rows["ir.module.module"][2]["state"] = "installed"
    refused(p.plan("move_post", (8,), "p", 1), "l10n_ar_edi is installed")
    r = p.plan("picking_validate", (12,), "p", 1)  # stock ops never e-invoice
    assert not (isinstance(r, Refusal) and "l10n_ar_edi" in r.reason)
    for name in ("l10n_cl_edi", "l10n_tr_nilvera_einvoice", "l10n_eg_edi_eta", "l10n_in_edi"):
        o.rows["ir.module.module"][2]["name"] = name
        refused(p.plan("move_post", (8,), "p", 1), name)
    o.rows["ir.module.module"] = {}
    refused(p.plan("move_post", (8,), "p", 1), "modules unreadable")


@pytest.mark.parametrize("v", VS)
def test_idle_einvoice_defaults_do_not_refuse(v, P) -> None:
    p, o = P(v)
    o.meta["account.move"]["l10n_xx_edi_state"] = F("char")
    for idle in ("to_send", "", False):  # walker (shared) still refuses not_applicable/none
        o.rows["account.move"][8]["l10n_xx_edi_state"] = idle
        assert isinstance(p.plan("move_post", (8,), "p", 1), po.PostPlan), idle
    o.rows["account.move"][8]["l10n_xx_edi_state"] = "sent"
    refused(p.plan("move_post", (8,), "p", 1), "")


@pytest.mark.parametrize("v", VS)
def test_undo_reversal_checks_einvoice_before_posting(v, P) -> None:
    p, o = P(v)
    pp = plan_or_skip(p, "move_post", (8,))
    d = p.apply(pp, spec(3))
    assert d.status == "done"
    o.rows["ir.module.module"][2]["state"] = "installed"  # appears after apply
    u = p.undo(d, spec(3))
    assert u.status != "done" and "l10n_ar_edi" in str(u.refusal)
    rev = [r for r in o.rows["account.move"].values() if r.get("reversed_entry_id") == 8]
    assert all(r["state"] == "draft" for r in rev)  # credit note never posted


@pytest.mark.parametrize("v", VS)
@pytest.mark.parametrize("op,ids", [("move_post", (8,)), ("inventory_apply", (50,))])
def test_l3_floor_even_though_catalogue_row_says_l2(v, op, ids, P) -> None:
    import json
    import pathlib

    rows = json.loads(pathlib.Path("app/bots/risk/catalogue_rows.json").read_text())
    assert "human-approve-L2" in rows["controls"]["R4"]
    p, o = P(v)
    pp = plan_or_skip(p, op, ids)
    assert pp.tier == 3
    assert p.apply(pp, spec(2)).status == "refused"


@pytest.mark.parametrize("v", VS)
def test_payment_post_runs_einvoice_checks(v, P) -> None:
    """CFDI payment complement (l10n_mx_edi): a posted customer payment queues an e-invoice."""
    p, o = P(v)
    assert isinstance(p.plan("payment_post", (20,), "p", 1), (po.PostPlan, Refusal))
    ok = p.plan("payment_post", (20,), "p", 1)
    o.rows["ir.module.module"][2].update(name="l10n_mx_edi", state="installed")
    refused(p.plan("payment_post", (20,), "p", 1), "l10n_mx_edi is installed")
    r = p.plan("picking_validate", (12,), "p", 1)
    assert not (isinstance(r, Refusal) and "l10n_mx_edi" in r.reason)  # pickings unchanged
    o.rows["ir.module.module"][2]["state"] = "uninstalled"
    _model(o, "account.journal", {"edi_format_ids": F("many2many")}, {1: {"edi_format_ids": [4]}})
    o.rows["account.payment"][20]["journal_id"] = 1
    refused(p.plan("payment_post", (20,), "p", 1), "active e-invoice formats")
    o.rows["account.journal"][1]["edi_format_ids"] = []
    assert type(p.plan("payment_post", (20,), "p", 1)) is type(ok)
    if isinstance(ok, po.PostPlan):  # undo re-checks before cancelling
        d = p.apply(ok, spec(3))
        assert d.status == "done", d.refusal
        o.rows["ir.module.module"][2]["state"] = "installed"
        u = p.undo(d, spec(3))
        assert u.status != "done" and "l10n_mx_edi" in str(u.refusal)
        assert o.rows["account.payment"][20]["state"] != "cancel"


@pytest.mark.parametrize("v", VS)
def test_nemhandel_module_and_proxy_state_refuse(v, P) -> None:
    p, o = P(v)
    o.rows["ir.module.module"][2].update(name="l10n_dk_nemhandel", state="installed")
    refused(p.plan("move_post", (8,), "p", 1), "l10n_dk_nemhandel")
    p, o = P(v)
    o.meta["res.company"]["l10n_dk_nemhandel_proxy_state"] = F("char")
    for c in o.rows["res.company"].values():
        c["l10n_dk_nemhandel_proxy_state"] = "receiver"
    refused(p.plan("move_post", (8,), "p", 1), "nemhandel_proxy_state")
