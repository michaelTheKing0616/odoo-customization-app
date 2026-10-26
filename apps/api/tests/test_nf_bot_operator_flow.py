"""BOT-OPERATOR-FLOW: guided, approval-gated plan execution over the walker's in-memory Odoo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.bots import operator_flow as of
from app.bots import versioncaps as vc
from app.bots.operator_flow import flow as fl
from app.bots.risk.rules import Refusal
from tests.test_nf_bot_kill_audit import engine, fake_owner, rpc_write_calls  # noqa: F401
from tests.test_nf_bot_walker import VS, W, spec  # noqa: F401

pytestmark = pytest.mark.no_app_db


def ALL(v: int) -> list[str]:  # noqa: N802
    return sorted(vc.load(v).modules)


def item(model: str, key: dict, exp: dict, **kw: Any) -> dict:
    ref = f"{model}:" + ",".join(f"{k}={x}" for k, x in sorted(key.items()))
    return {
        "kind": "record",
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


def design(v: int, *items: dict) -> dict:
    return {"spec_version": 1, "status": "designed", "odoo_major": v, "items": list(items)}


@pytest.fixture
def F(W, tmp_path):  # noqa: F811, N802
    def make(v: int, sp: dict, installed: list[str] | None = None, o: Any = None):
        w, odoo = W(v, o=o)
        dec = of.Decisions(tmp_path / "dec.json")
        flow = of.OperatorFlow(
            sp,
            w,
            dec,
            tmp_path / "state.json",
            spec(),
            plan_id="plan-1",
            installed=ALL(v) if installed is None else installed,
        )
        return flow, dec, odoo

    return make


def by_ref(rep: dict) -> dict:
    return {s["ref"]: s for s in rep["steps"]}


LEAD = ("crm.lead", {"name": "Guided one"}, {})
PART = ("res.partner", {"id": 3}, {"name": "Renamed"})


@pytest.mark.parametrize("v", VS)
def test_cards_preview_without_writing(v, F) -> None:
    sp = design(v, item(*LEAD), item(*PART))
    flow, _, o = F(v, sp)
    n = len(o.calls)
    cards = flow.cards()
    assert [c.blocked for c in cards] == [None, None]
    assert cards[0].step.kind == "create" and cards[1].step.kind == "write"
    assert all(c.changes and c.tier and c.undo_how and "L" in c.risk for c in cards)
    assert cards[0].availability == "available on this database"
    assert not [c for c in o.calls[n:] if c[1] in ("create", "write", "unlink")]


def approve_all(flow, dec, level: int = 3, who: str = "alice") -> None:
    for c in flow.cards():
        dec.approve("plan-1", c, who, level)


@pytest.mark.parametrize("v", VS)
def test_nothing_written_without_store_approval_then_executes_once(v, F) -> None:
    sp = design(v, item(*LEAD))
    flow, dec, o = F(v, sp)
    rep = flow.run()
    assert rep["steps"][0]["status"] == of.PENDING and rep["status"] == "attention"
    assert not any(r.get("name") == "Guided one" for r in o.rows.get("crm.lead", {}).values())
    approve_all(flow, dec)
    rep = flow.run()
    s = rep["steps"][0]
    assert s["status"] == of.EXECUTED, s
    assert s["by"] == "alice" and s["record_ids"]
    assert s["verified"] == "matches" and rep["status"] == "complete", s
    again = flow.run()  # resume: executed step is not touched again
    assert again["steps"][0].get("resumed")
    assert sum(r.get("name") == "Guided one" for r in o.rows["crm.lead"].values()) == 1


@pytest.mark.parametrize("v", VS)
def test_skip_then_undo(v, F) -> None:
    sp = design(v, item(*LEAD), item(*PART))
    flow, dec, o = F(v, sp)
    c0, c1 = flow.cards()
    dec.approve("plan-1", c0, "alice", 3)
    dec.skip("plan-1", c1, "bob")
    st = flow.run()["steps"]
    assert st[1]["status"] == of.SKIPPED and o.rows["res.partner"][3]["name"] != "Renamed"
    assert st[0]["status"] == of.EXECUTED
    inv = flow.undo_plan()
    assert isinstance(inv, list) and inv[0].kind == "unlink"


def _tiered(v, F):
    for spec_item in (item(*LEAD), item(*PART), item("res.partner", {"id": 3}, {"lang": "fr_FR"})):
        flow, dec, o = F(v, design(v, spec_item))
        c = flow.cards()[0]
        if c.tier and c.tier >= 2:
            return flow, dec, o, c
    raise AssertionError("no step needing L2+ in the fixture")


@pytest.mark.parametrize("v", VS)
def test_l1_approval_on_higher_tier_step_is_blocked(v, F, monkeypatch) -> None:
    flow, dec, _, c = _tiered(v, F)
    dec.approve("plan-1", c, "alice", c.tier - 1)
    calls = []
    monkeypatch.setattr(flow.w, "apply", lambda *a, **k: calls.append(a) or [])
    s = flow.run()["steps"][0]
    assert s["status"] == of.BLOCKED, s
    assert s["reason"] == f"needs L{c.tier} approval, has L{c.tier - 1}" and not calls


@pytest.mark.parametrize(
    "change",
    [
        {"model": "res.partner.category"},
        {"key": {"id": 4}},
        {"expected": {"name": "EVIL"}},
        {"verdict": "stock-install"},
        {"module": "contacts"},
    ],
)
def test_approval_is_bound_to_the_card(change, F) -> None:
    sp = design(17, item("res.partner", {"id": 3}, {"name": "A"}))
    flow, dec, o = F(17, sp)
    approve_all(flow, dec)
    sp["items"][0].update(change)
    s = flow.run()["steps"][0]
    assert s["status"] == of.BLOCKED and s["reason"] == fl.CHANGED, s
    assert o.rows["res.partner"][3]["name"] not in ("A", "EVIL")
    for k in change:  # reverting does not revive the spent approval
        sp["items"][0][k] = item("res.partner", {"id": 3}, {"name": "A"})[k]
    assert flow.run()["steps"][0]["reason"] == fl.CHANGED


def test_tier_change_after_approval_blocks(F, monkeypatch) -> None:
    sp = design(17, item(*LEAD))
    flow, dec, _ = F(17, sp)
    approve_all(flow, dec)
    real = fl.StepCard.seal

    def bump(self):
        self.tier = (self.tier or 0) + 1
        real(self)

    monkeypatch.setattr(fl.StepCard, "seal", bump)
    assert flow.run()["steps"][0]["reason"] == fl.CHANGED


def test_unchanged_card_runs_and_noop_is_already_done(F) -> None:
    sp = design(17, item("res.partner", {"id": 3}, {"name": "A"}))
    flow, dec, o = F(17, sp)
    approve_all(flow, dec)
    assert (
        flow.run()["steps"][0]["status"] == of.EXECUTED and o.rows["res.partner"][3]["name"] == "A"
    )
    flow2, dec2, _ = F(17, design(17, item("res.partner", {"id": 3}, {"name": "A"})), o=o)
    flow2.plan_id = "plan-1"
    flow2.state = fl._Json(flow.state.path.with_name("st2.json"))
    approve_all(flow2, dec2)
    assert flow2.run()["steps"][0]["status"] == of.ALREADY


def test_duplicate_refs_block_whole_spec(F) -> None:
    a = item(*LEAD)
    b = item("crm.lead", {"name": "Other"}, {}) | {"ref": a["ref"]}
    flow, dec, o = F(17, design(17, a, b))
    approve_all(flow, dec)
    st = flow.run()["steps"]
    assert all(s["status"] == of.BLOCKED and "duplicate" in s["reason"] for s in st)
    assert not any(r.get("name") in ("Guided one", "Other") for r in o.rows["crm.lead"].values())


def test_dependent_step_waits_for_earlier_step(F) -> None:
    sp = design(17, item(*LEAD), item("crm.lead", {"name": "Second"}, {}))
    flow, dec, o = F(17, sp)
    c0, c1 = flow.cards()
    assert c1.deps == (1,)
    dec.skip("plan-1", c0, "bob")
    dec.approve("plan-1", c1, "alice", 3)
    s = flow.run()["steps"][1]
    assert s["status"] == of.BLOCKED and "waits on earlier step 1" in s["reason"]
    assert not any(r.get("name") == "Second" for r in o.rows["crm.lead"].values())


@pytest.mark.parametrize("v", VS)
def test_blocked_paths_fail_closed(v, F) -> None:
    items = [
        item("x_thing", {"name": "a"}, {}, verdict="needs-custom"),
        item("crm.lead", {"name": "b"}, {}, verdict="needs review", reason="unclear"),
        item("crm.lead", {"name": "c"}, {}, risk=None),
        item("res.config.settings", {}, {"group_x": True}, kind="setting"),
        item("crm.lead", {"name": "d"}, {}, relations={"partner_id": "res.partner:id=3"}),
        item("mrp.production", {"name": "e"}, {}),
    ]
    flow, dec, _ = F(v, design(v, *items), installed=["base"])
    approve_all(flow, dec)
    st = flow.run()["steps"]
    assert all(s["status"] == of.BLOCKED and s["reason"] for s in st)
    assert st[0]["reason"] == fl.NEEDS_BUILD
    assert "settings are not applied" in st[3]["reason"]
    assert "needs install" in st[5]["reason"] and "mrp" in st[5]["reason"]


@pytest.mark.parametrize("v", VS)
def test_version_mismatch_and_bad_spec_block_everything(v, F) -> None:
    other = 17 if v != 17 else 18
    flow, dec, _ = F(v, design(other, item(*LEAD)))
    approve_all(flow, dec)
    s = flow.run()["steps"][0]
    assert s["status"] == of.BLOCKED and f"Odoo {other}" in s["reason"]
    flow2, _, _ = F(v, {"spec_version": 1, "status": "not enough input", "items": []})
    assert flow2.run()["steps"][0]["status"] == of.BLOCKED


def test_module_step_wording_names_module(F) -> None:
    it = item("mrp.production", {"name": "mrp"}, {}, kind="module", module="mrp")
    flow, _, _ = F(17, design(17, it), installed=["base"])
    c = flow.cards()[0]
    assert c.blocked and "available in Odoo 17 via module mrp; needs install" in c.blocked


def test_concurrent_approvals_and_runs_lose_nothing(F, tmp_path) -> None:
    import threading

    its = [item("crm.lead", {"name": f"c{i}"}, {}) for i in range(12)]
    flow, dec, _ = F(17, design(17, *its))
    cards = flow.cards()
    ths = [threading.Thread(target=dec.approve, args=("plan-1", c, "alice", 3)) for c in cards]
    [t.start() for t in ths]
    [t.join() for t in ths]
    assert len(dec.load()["plan-1"]) == 12
    st = fl._Json(tmp_path / "race.json")
    ths = [
        threading.Thread(target=st.update, args=(lambda d, i=i: d.__setitem__(str(i), i),))
        for i in range(40)
    ]
    [t.start() for t in ths]
    [t.join() for t in ths]
    assert len(st.load()) == 40
    assert not list(tmp_path.glob("*.tmp"))


def test_decisions_store_rejects_anonymous_and_bad_level(tmp_path: Path) -> None:
    d = of.Decisions(tmp_path / "d.json")
    with pytest.raises(ValueError):
        d.approve("p", fl.StepCard(1, "r", "", "", "", digest="x"), "", 3)
    with pytest.raises(ValueError):
        d.approve("p", fl.StepCard(1, "r", "", "", "", digest="x"), "a", 4)
    with pytest.raises(ValueError):
        d.approve("p", fl.StepCard(1, "r", "", "", ""), "a", 3)
    assert d.get("p", fl.StepCard(1, "r", "", "", "")) is None
    (tmp_path / "d.json").write_text("[]")
    with pytest.raises(RuntimeError):
        d.load()


def test_no_raw_write_in_package() -> None:
    for p in Path(fl.__file__).parent.glob("*.py"):
        src = p.read_text()
        assert rpc_write_calls(src) == [] and "execute_kw" not in src, p
        assert "gate." not in src and ".rpc(" not in src, p
    assert isinstance(Refusal, type)


def test_failed_verification_flags_executed_step(F, monkeypatch) -> None:
    sp = design(17, item(*LEAD))
    flow, dec, _ = F(17, sp)
    approve_all(flow, dec)
    monkeypatch.setattr(fl.cv, "verify", lambda *a, **k: {"status": "attention", "items": []})
    rep = flow.run()
    assert rep["status"] == "attention" and rep["steps"][0]["needs_review"]
