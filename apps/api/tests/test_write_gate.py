"""A5 stage 1: the shared write gate (money guard, approval rule, undo point) and its undo."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import app.snapshots as snaps
from app import write_gate as wg


class FakeOdoo:
    def __init__(self, rows: dict[int, dict]):
        self.rows = rows
        self.writes: list[tuple] = []
        self.unlinked: list[int] = []

    def execute_kw(self, model, method, args, kwargs=None):
        if method == "read":
            return [{"id": i, **{f: self.rows[i].get(f) for f in kwargs["fields"]}} for i in args[0] if i in self.rows]
        if method == "search":
            want = args[0][0][2]
            return [i for i in want if i in self.rows]
        if method == "write":
            self.writes.append((args[0], args[1]))
            for i in args[0]:
                self.rows[i].update(args[1])
            return True
        if method == "unlink":
            self.unlinked += args[0]
            return True
        raise AssertionError(method)


@pytest.fixture
def saved(monkeypatch):
    out: list[dict] = []

    def fake_save(db, **kw):
        out.append(kw)
        return SimpleNamespace(id="s1", **kw)

    monkeypatch.setattr(snaps, "save_snapshot", fake_save)
    return out


def test_money_models_are_refused_before_anything_is_read(saved) -> None:
    odoo = FakeOdoo({1: {"name": "INV/1"}})
    with pytest.raises(wg.WriteRefused) as e:
        wg.guard_record_write(None, odoo, "c1", model="account.move", ids=[1], vals={"name": "x"}, source="Bulk", threshold=200)
    assert e.value.code == "money_guard"
    assert saved == [] and odoo.writes == []


def test_over_threshold_needs_approval_unless_approved(saved) -> None:
    odoo = FakeOdoo({i: {"name": f"n{i}"} for i in range(1, 6)})
    with pytest.raises(wg.WriteNeedsApproval):
        wg.guard_record_write(None, odoo, "c1", model="res.partner", ids=[1, 2, 3, 4, 5], vals={"name": "x"}, source="Bulk", threshold=3)
    wg.guard_record_write(None, odoo, "c1", model="res.partner", ids=[1, 2, 3, 4, 5], vals={"name": "x"}, source="Bulk", threshold=3, approved=True)
    assert len(saved) == 1


def test_undo_point_saves_current_values_and_undo_puts_them_back(saved) -> None:
    odoo = FakeOdoo({7: {"name": "Azure", "country_id": [1, "Nigeria"], "category_id": [3, 4]}, 8: {"name": "Gemini", "country_id": False, "category_id": []}})
    wg.guard_record_write(None, odoo, "c1", model="res.partner", ids=[7, 8], vals={"name": "X", "country_id": 2, "write_date": "z"}, source="Record editor", threshold=200)
    snap = saved[0]
    assert snap["resource_type"] == "record_values"
    assert snap["payload"]["fields"] == ["country_id", "name"]
    assert snap["payload"]["before"][0] == {"id": 7, "country_id": 1, "name": "Azure"}
    # the caller's own write
    odoo.execute_kw("res.partner", "write", [[7, 8], {"name": "X", "country_id": 2}])
    del odoo.rows[8]  # deleted meanwhile: skipped, not an error
    out = wg.undo_record_values(odoo, snap["payload"])
    assert out == {"restored": "record_values", "model": "res.partner", "records": 1, "skipped": 1}
    assert odoo.rows[7]["name"] == "Azure" and odoo.rows[7]["country_id"] == 1


def test_created_records_undo_removes_them_through_history_rollback(saved) -> None:
    odoo = FakeOdoo({11: {}, 12: {}})
    wg.record_created(None, "c1", model="x_visitor", ids=[11, 12, 13], source="Import")
    payload = saved[0]["payload"]
    row = SimpleNamespace(connection_id="c1", reversible="yes", resource_type="record_values", payload_json=json.dumps(payload))
    db = SimpleNamespace(get=lambda _m, _id: row)
    out = snaps.rollback_snapshot(db, odoo, "s1", connection_id="c1")
    assert odoo.unlinked == [11, 12] and out["skipped"] == 1


def test_x2many_values_are_saved_in_writable_form() -> None:
    assert wg._plain([3, 4]) == [(6, 0, [3, 4])]
    assert wg._plain([1, "Nigeria"]) == 1
    assert wg._plain("a") == "a"


def test_approval_status_uses_the_run_sheet_approvals_list(monkeypatch) -> None:
    from app.routers import suite as rs

    asked: list[tuple] = []
    state = {"found": None}
    monkeypatch.setattr(wg, "approval_threshold", lambda db, cid: 2)
    monkeypatch.setattr(rs, "find_approval", lambda db, cid, action, ref, h: state["found"])
    monkeypatch.setattr(rs, "ask_approval", lambda cid, db, req, action, ref, h, summary: asked.append((action, ref, h)) or {"ok": True})
    assert wg.approval_status(None, None, "c1", model="res.partner", ids=[1, 2], vals={"x": 1}, source="Bulk") is True
    with pytest.raises(wg.WriteNeedsApproval):
        wg.approval_status(None, None, "c1", model="res.partner", ids=[1, 2, 3], vals={"x": 1}, source="Bulk")
    assert asked and asked[0][0] == "shared_write"
    state["found"] = {"status": "pending"}
    with pytest.raises(wg.WriteNeedsApproval):
        wg.approval_status(None, None, "c1", model="res.partner", ids=[1, 2, 3], vals={"x": 1}, source="Bulk")
    assert len(asked) == 1  # not asked twice
    state["found"] = {"status": "approved"}
    assert wg.approval_status(None, None, "c1", model="res.partner", ids=[3, 2, 1], vals={"x": 1}, source="Bulk") is True


def test_import_guard_refuses_money_documents_but_not_accounting_setup() -> None:
    for m in ("account.move", "account.payment", "account.move.line"):
        with pytest.raises(wg.WriteRefused):
            wg.guard_record_create(None, "c1", model=m, source="Import")
    for m in ("account.account", "account.tax", "account.journal", "account.fiscal.position"):
        wg.guard_record_create(None, "c1", model=m, source="Import")
        assert wg.is_accounting_setup(m)


def test_accounting_setup_is_self_approved_and_recorded(monkeypatch, saved) -> None:
    from types import SimpleNamespace

    from app.routers import suite as rs

    monkeypatch.setattr(wg, "approval_threshold", lambda db, cid: 2)
    monkeypatch.setattr(rs, "find_approval", lambda *a: None)
    asked: list = []
    monkeypatch.setattr(rs, "ask_approval", lambda *a: asked.append(a) or {"ok": True})
    req = SimpleNamespace(state=SimpleNamespace(auth=SimpleNamespace(mode="accounts", user_id="u1", email="ada@firm.ng")))
    assert wg.approval_status(None, req, "c1", model="account.tax", ids=list(range(50)), vals={"x": 1}, source="Import", always=True) is True
    assert not asked  # no second person needed
    rec = saved[-1]
    assert rec["payload"]["approved_by"] == "ada@firm.ng" and rec["payload"]["approved_at"]
    with pytest.raises(wg.WriteNeedsApproval):  # other large changes keep someone-else-approves
        wg.approval_status(None, req, "c1", model="res.partner", ids=[1, 2, 3], vals={"x": 1}, source="Bulk")


def test_updated_rows_old_values_are_saved_and_undone(saved) -> None:
    odoo = FakeOdoo({5: {"name": "Old", "email": "a@x"}})
    got = wg.read_before(odoo, "res.partner", 5, {"name": "New", "email": "b@x"})
    odoo.execute_kw("res.partner", "write", [[5], {"name": "New", "email": "b@x"}])
    wg.save_before_values(None, "c1", model="res.partner", before=[got], source="Import")
    wg.undo_record_values(odoo, saved[0]["payload"])
    assert odoo.rows[5] == {"name": "Old", "email": "a@x"}
