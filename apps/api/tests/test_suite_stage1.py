"""Configuration Suite stage 1: catalog, plan order, check receipt, waves, undo, money guard, workbook."""
from __future__ import annotations

import base64
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import dry_run_ledger as ledger
from app import suite_catalog as cat
from app import suite_setup as ss
from app import suite_workbook as swb
from app import view_engine_store as vs
from app.mutation_lock import connection_mutation_lock, reset_mutation_locks_for_tests
from app.routers import suite as rs


class MemStore:
    def __init__(self) -> None:
        self.seen: set[str] = set()

    def remember(self, digest: str, *, now: Any = None) -> None:
        self.seen.add(digest)

    def contains(self, digest: str, *, now: Any = None) -> bool:
        return digest in self.seen


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine("sqlite://")
    session = sessionmaker(bind=engine)()
    vs._ensure_tables(session)
    ledger.bind_store(MemStore())
    reset_mutation_locks_for_tests()
    monkeypatch.setattr(rs, "RUN_INLINE", True)
    monkeypatch.setattr(rs, "_row", lambda db, cid: type("Row", (), {"url": "http://x", "db_name": "d", "server_version": "19.0"})())
    yield session
    ledger.bind_store(None)
    session.close()


class Fake:
    """A tiny Odoo: enough models for setup steps. Records: {model: {id: vals}}."""

    def __init__(self, major: int = 19, posted: int = 0) -> None:
        self.major = major
        self.posted = posted
        self.settings = {"group_uom": False, "group_discount_per_so_line": False, "module_crm": False, "default_invoice_policy": "order"}
        self.recs: dict[str, dict[int, dict[str, Any]]] = {
            "uom.uom": {1: {"name": "Units", "relative_uom_id": False, "relative_factor": 1.0, "category_id": [1, "Unit"], "factor": 1.0, "uom_type": "reference", "active": True}},
            "product.category": {1: {"name": "All", "parent_id": False}},
            "product.template": {1: {"name": "Desk", "default_code": "D1", "categ_id": [1, "All"], "list_price": 100.0, "uom_id": [1, "Units"]}},
            "res.currency": {1: {"name": "USD", "active": True}, 2: {"name": "EUR", "active": False}},
            "ir.module.module": {1: {"name": "board", "state": "uninstalled"}, 2: {"name": "l10n_ng", "state": "uninstalled"}},
        }
        self.calls: list[tuple[str, str]] = []
        self.capabilities = type("C", (), {"major": major})()

    def server_version(self) -> dict[str, Any]:
        return {"server_version": f"{self.major}.0"}

    def _match(self, rec: dict[str, Any], dom: list[Any]) -> bool:
        for f, op, v in dom:
            cur = rec.get(f)
            cur = cur[0] if isinstance(cur, list) else cur
            if op == "=" and cur != v and not (f == "id" and rec.get("id") == v):
                return False
            if op == "=ilike" and str(cur).lower() != str(v).lower():
                return False
            if op == "in" and cur not in v:
                return False
            if op == "!=" and cur == v:
                return False
        return True

    def _search(self, model: str, dom: list[Any]) -> list[int]:
        dom = list(dom)
        return [i for i, r in self.recs.get(model, {}).items() if self._match({**r, "id": i}, dom)]

    def execute_kw(self, model: str, method: str, args: list, kw: dict | None = None) -> Any:
        kw = kw or {}
        self.calls.append((model, method))
        if model in {"account.move", "stock.move"} and method == "search_count":
            return self.posted if model == "account.move" else 0
        if model == "res.config.settings":
            if method == "fields_get":
                return {k: {"type": "selection" if k == "default_invoice_policy" else "boolean", "string": k,
                            "selection": [["order", "Ordered"], ["delivery", "Delivered"]]} for k in self.settings}
            if method == "default_get":
                return {k: self.settings[k] for k in args[0] if k in self.settings}
            if method == "create":
                self._pending = dict(args[0])
                return 9
            if method == "execute":
                self.settings.update(self._pending)
                return True
        if model == "uom.uom" and method == "fields_get":
            base = {"name": {"type": "char"}, "active": {"type": "boolean"}}
            if self.major >= 19:
                return {**base, "relative_uom_id": {"type": "many2one", "relation": "uom.uom"}, "relative_factor": {"type": "float"}}
            return {**base, "category_id": {"type": "many2one", "relation": "uom.category"}, "factor": {"type": "float"},
                    "factor_inv": {"type": "float"}, "uom_type": {"type": "selection"}}
        if method == "fields_get":
            if model not in self.recs:
                raise RuntimeError("no model")
            meta = {"name": {"type": "char", "string": "Name", "required": True}, "parent_id": {"type": "many2one", "relation": "product.category"},
                    "categ_id": {"type": "many2one", "relation": "product.category"}, "uom_id": {"type": "many2one", "relation": "uom.uom"},
                    "list_price": {"type": "float"}, "default_code": {"type": "char"}, "active": {"type": "boolean"}, "state": {"type": "char"}}
            return meta
        if method == "search":
            ids = self._search(model, args[0])
            return ids[: kw.get("limit") or None]
        if method == "search_count":
            return len(self._search(model, args[0]))
        if method == "search_read":
            return [{"id": i, **self.recs[model][i]} for i in self._search(model, args[0])]
        if method == "read":
            return [{"id": i, **{f: self.recs[model][i].get(f) for f in args[1]}} for i in args[0]]
        if method == "default_get":
            return {}
        if method == "create":
            nid = max(self.recs.setdefault(model, {}) or {0: None}) + 1
            vals = dict(args[0])
            if model == "uom.uom" and "relative_uom_id" in vals:
                vals["relative_uom_id"] = [vals["relative_uom_id"], self.recs["uom.uom"][vals["relative_uom_id"]]["name"]]
            self.recs[model][nid] = vals
            return nid
        if method == "write":
            for i in args[0]:
                self.recs[model][i].update(args[1])
            return True
        if method == "unlink":
            for i in args[0]:
                self.recs[model].pop(i)
            return True
        if method == "button_immediate_install":
            for i in args[0]:
                self.recs[model][i]["state"] = "installed"
            return True
        raise AssertionError(f"unexpected {model}.{method}")


# ---------------------------------------------------------------- catalog
def test_catalog_parses_every_section_and_resolves_versions() -> None:
    tasks = cat.load_catalog()
    assert len(tasks) > 200 and {t.section for t in tasks} >= {f"2.{i}" for i in range(1, 22)}
    units = cat.get_task("2.6#65")
    assert cat.resolve_for_version(units, 17)["models"] == ["uom.category", "uom.uom"]
    assert cat.resolve_for_version(units, 20)["models"] == ["uom.uom"]
    assert cat.get_task("2.1#1").rank == 0 and cat.get_task("2.1#5").rank == 2
    groups = next(t for t in tasks if any("account.group" in m.models for m in t.mechanisms))
    state, reason = cat.availability(groups, 20, models={"account.account"}, settings_fields=set(), edition="community")
    assert state == "not_here" and reason


def test_catalog_availability_follows_live_database() -> None:
    cur = cat.get_task("2.5#61")
    assert cat.availability(cur, 18, models={"res.currency"}, settings_fields=set(), edition="community")[0] == "available"
    assert cat.availability(cur, 18, models=set(), settings_fields=set(), edition="community")[0] == "not_here"
    ee = next(t for t in cat.load_catalog() if t.edition.upper().startswith("EE"))
    assert cat.availability(ee, 18, models=set(), settings_fields=set(), edition="community")[1] == "This needs Odoo Enterprise."


# ---------------------------------------------------------------- order and money guard
def test_waves_installs_first_then_rank_then_dependencies() -> None:
    steps, errs = ss.normalise_steps([
        {"id": "p", "type": "create", "inputs": {"model": "product.template", "values": {"name": "Chair", "categ_id": {"ref": "Office", "model": "product.category"}}}},
        {"id": "c", "type": "create", "inputs": {"model": "product.category", "values": {"name": "Office"}}},
        {"id": "s", "type": "setting", "inputs": {"values": {"group_uom": True}}},
        {"id": "i", "type": "install", "inputs": {"modules": ["board"]}},
        {"id": "u", "type": "units", "inputs": {"name": "Box", "reference": "Units", "factor": 6}},
    ])
    assert not errs
    waves, oerr = ss.order_waves(steps)
    assert not oerr and waves[0] == ["i"]
    flat = [s for w in waves for s in w]
    assert flat.index("c") < flat.index("p")
    wave_of = {s: n for n, w in enumerate(waves) for s in w}
    assert wave_of["p"] > wave_of["c"]


def test_cycles_and_unknown_dependencies_are_refused() -> None:
    steps, errs = ss.normalise_steps([{"id": "a", "type": "setting", "inputs": {"values": {"x": 1}}, "depends_on": ["zz"]}])
    assert errs and "zz" in errs[0]
    steps, _ = ss.normalise_steps([
        {"id": "a", "type": "setting", "inputs": {"values": {"x": 1}}, "depends_on": ["b"]},
        {"id": "b", "type": "setting", "inputs": {"values": {"y": 1}}, "depends_on": ["a"]},
    ])
    assert ss.order_waves(steps)[1]
    assert ss.normalise_steps([{"type": "remove", "inputs": {"model": "x.y", "id": 1}}])[1]


def test_money_guard_rules() -> None:
    g = ss.money_guard
    assert g({"type": "create", "inputs": {"model": "account.tax", "values": {}}}, posted_entries=0, done_moves=0)
    assert g({"type": "update", "inputs": {"model": "res.company", "values": {"currency_id": 2}}}, posted_entries=0, done_moves=0) is None
    assert g({"type": "update", "inputs": {"model": "res.company", "values": {"currency_id": 2}}}, posted_entries=3, done_moves=0)
    assert g({"type": "update", "inputs": {"model": "product.category", "values": {"property_cost_method": "fifo"}}}, posted_entries=0, done_moves=1)
    assert g({"type": "setting", "inputs": {"values": {"module_crm": True}}}, posted_entries=0, done_moves=0)
    assert g({"type": "setting", "inputs": {"values": {"chart_template": "ng"}}}, posted_entries=0, done_moves=0)
    assert g({"type": "install", "inputs": {"modules": ["board"]}}, posted_entries=1, done_moves=0)  # D4
    assert g({"type": "setting", "inputs": {"values": {"group_uom": True}}}, posted_entries=9, done_moves=9) is None


# ---------------------------------------------------------------- check, receipt, run, undo
def _plan(db, steps, name="p"):
    return rs.suite_plan_create("c1", rs.PlanBody(name=name, steps=steps), None, db)


def test_check_is_read_only_and_run_needs_its_receipt(db, monkeypatch) -> None:
    odoo = Fake(19)
    monkeypatch.setattr(rs, "_client", lambda cid, db: odoo)
    plan = _plan(db, [{"id": "s", "type": "setting", "inputs": {"values": {"group_uom": True}}},
                      {"id": "c", "type": "create", "inputs": {"model": "product.category", "values": {"name": "Office"}}}])
    with pytest.raises(HTTPException) as e:
        rs.suite_plan_run("c1", plan["id"], None, db)
    assert e.value.status_code == 428
    report = rs.suite_plan_check("c1", plan["id"], db)
    writes = [c for c in odoo.calls if c[1] in {"create", "write", "execute", "unlink", "button_immediate_install"}]
    assert writes == [] and report["receipt"] and report["counts"]["ready"] == 2
    # editing the plan voids the receipt
    rs.suite_plan_update("c1", plan["id"], rs.PlanBody(name="p", steps=[{"id": "s", "type": "setting", "inputs": {"values": {"group_uom": True}}}]), db)
    with pytest.raises(HTTPException) as e:
        rs.suite_plan_run("c1", plan["id"], None, db)
    assert e.value.status_code == 428
    rs.suite_plan_check("c1", plan["id"], db)
    run = rs.suite_plan_run("c1", plan["id"], None, db)
    assert run["payload"]["state"] == "done" and odoo.settings["group_uom"] is True


def test_run_waves_failure_pauses_and_dependents_wait_then_undo(db, monkeypatch) -> None:
    odoo = Fake(19)
    monkeypatch.setattr(rs, "_client", lambda cid, db: odoo)
    plan = _plan(db, [
        {"id": "u", "type": "units", "inputs": {"name": "Box of 6", "reference": "Units", "factor": 6}},
        {"id": "c", "type": "create", "inputs": {"model": "product.category", "values": {"name": "Office"}}},
        {"id": "p", "type": "create", "inputs": {"model": "product.template", "values": {"name": "Chair", "categ_id": {"ref": "Office", "model": "product.category"}}}},
        {"id": "s", "type": "setting", "inputs": {"values": {"group_discount_per_so_line": True}}},
    ])
    rep = rs.suite_plan_check("c1", plan["id"], db)
    assert rep["can_apply"], rep
    # someone changes Odoo after the check: the category appears, then is renamed away so 'p' can't find it
    real = odoo.execute_kw

    def flaky(model, method, args, kw=None):
        if model == "product.category" and method == "create":
            raise RuntimeError("ValidationError: not allowed today")
        return real(model, method, args, kw)

    odoo.execute_kw = flaky  # type: ignore[method-assign]
    run = rs.suite_plan_run("c1", plan["id"], None, db)["payload"]
    states = {s["id"]: s for w in run["waves"] for s in w["steps"]}
    assert run["state"] == "paused" and states["c"]["state"] == "failed" and states["p"]["state"] == "waiting"
    assert "needs c" in states["p"]["message"]
    odoo.execute_kw = real  # type: ignore[method-assign]
    run_id = next(r["id"] for r in rs.suite_runs("c1", db)["runs"])
    run = rs.suite_run_continue("c1", run_id, rs.ContinueBody(), db)["payload"]
    states = {s["id"]: s for w in run["waves"] for s in w["steps"]}
    assert run["state"] == "done" and states["p"]["state"] == "skipped" and states["s"]["state"] == "done"
    new_unit = next(i for i, r in odoo.recs["uom.uom"].items() if r["name"] == "Box of 6")
    assert odoo.recs["uom.uom"][new_unit]["relative_factor"] == 6
    undo = rs.suite_run_undo_plan("c1", run_id, None, db)
    kinds = [s["type"] for s in undo["payload"]["steps"]]
    assert undo["payload"]["kind"] == "undo" and kinds == ["setting", "remove"]  # reverse of run order (unit first, setting last)
    rs.suite_plan_check("c1", undo["id"], db)
    out = rs.suite_plan_run("c1", undo["id"], None, db)["payload"]
    assert out["state"] == "done" and odoo.settings["group_discount_per_so_line"] is False and new_unit not in odoo.recs["uom.uom"]


def test_units_use_the_17_18_category_mechanism() -> None:
    odoo = Fake(17)
    step = ss.normalise_steps([{"id": "u", "type": "units", "inputs": {"name": "Box", "reference": "Units", "factor": 6}}])[0][0]
    res = ss.apply_step(odoo, step, {}, {})
    rec = odoo.recs["uom.uom"][res["undo"]["id"]]
    assert rec["uom_type"] == "bigger" and rec["factor_inv"] == pytest.approx(6) and rec["category_id"] == 1


def _approve(db, pid: str) -> None:
    from app.routers import view_engine_2c as r2c

    req = rs.suite_plan_request_approval("c1", pid, None, db)
    r2c.approval_decide("c1", r2c.ApprovalDecideBody(item_id=req["item_id"], approve=True), None, db)


def test_guarded_steps_block_and_accounting_needs_approval(db, monkeypatch) -> None:
    odoo = Fake(19)
    monkeypatch.setattr(rs, "_client", lambda cid, db: odoo)
    plan = _plan(db, [{"id": "t", "type": "create", "inputs": {"model": "account.tax", "values": {"name": "VAT"}}}])
    rep = rs.suite_plan_check("c1", plan["id"], db)
    assert rep["steps"]["t"]["verdict"] == "blocked" and not rep["receipt"]
    plan = _plan(db, [{"id": "k", "type": "country_package", "inputs": {"country_code": "NG"}}])
    rep = rs.suite_plan_check("c1", plan["id"], db)
    assert rep["needs_approval"] and rep["receipt"]
    with pytest.raises(HTTPException) as e:
        rs.suite_plan_run("c1", plan["id"], None, db)
    assert e.value.status_code == 403
    _approve(db, plan["id"])
    run = rs.suite_plan_run("c1", plan["id"], None, db)["payload"]
    assert run["state"] == "done" and odoo.recs["ir.module.module"][2]["state"] == "installed"
    odoo2 = Fake(19, posted=4)
    monkeypatch.setattr(rs, "_client", lambda cid, db: odoo2)
    plan = _plan(db, [{"id": "i", "type": "install", "inputs": {"modules": ["board"]}}])
    assert rs.suite_plan_check("c1", plan["id"], db)["steps"]["i"]["verdict"] == "blocked"


def test_threshold_policy_and_mutation_lock(db, monkeypatch) -> None:
    odoo = Fake(19)
    monkeypatch.setattr(rs, "_client", lambda cid, db: odoo)
    rs.suite_policy_put("c1", rs.PolicyBody(approval_threshold=1, cloud_ai=True), None, db)
    assert rs.suite_policy_get("c1", db)["cloud_ai_consent_by"]
    plan = _plan(db, [{"id": "a", "type": "create", "inputs": {"model": "product.category", "values": {"name": "A"}}},
                      {"id": "b", "type": "create", "inputs": {"model": "product.category", "values": {"name": "B"}}}])
    assert rs.suite_plan_check("c1", plan["id"], db)["needs_approval"]
    _approve(db, plan["id"])
    with connection_mutation_lock("c1", "other job"):
        run = rs.suite_plan_run("c1", plan["id"], None, db)["payload"]
    assert run["state"] == "failed" and "Another change" in run["message"]


def test_unchanged_workbook_gives_zero_steps_and_edits_become_steps(db, monkeypatch) -> None:
    odoo = Fake(19)
    monkeypatch.setattr(rs, "_client", lambda cid, db: odoo)
    data = swb.build_workbook(odoo, connection_id="c1", server_version="19.0")
    out = rs.suite_workbook_upload("c1", rs.WorkbookBody(content_b64=base64.b64encode(data).decode()), None, db)
    assert out["steps"] == 0 and out["plan"] is None, out
    import io

    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data))
    wb["Products"].append(["Chair", "C1", "All", 50, "Units"])
    wb["Currencies"]["B3"] = "Yes"
    wb["Units"].append(["Box of 12", "Units", 12])
    for row in wb["Settings"].iter_rows(min_row=2):
        if row[0].value == "group_uom":
            row[2].value = "Yes"
    buf = io.BytesIO()
    wb.save(buf)
    out = rs.suite_workbook_upload("c1", rs.WorkbookBody(content_b64=base64.b64encode(buf.getvalue()).decode()), None, db)
    types = sorted(s["type"] for s in out["plan"]["payload"]["steps"])
    assert out["steps"] == 4 and types == ["create", "setting", "units", "update"]
    assert all(s["source"]["kind"] == "workbook" for s in out["plan"]["payload"]["steps"])
    assert "module_crm" not in [r["field"] for r in swb.setting_fields(odoo)]
