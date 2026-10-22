"""Suite stage 4: "Before you upgrade" forecast and "Check on every version"."""
from __future__ import annotations

from types import SimpleNamespace

from app.routers import suite as rs
from app.routers import suite_upkeep as rsu


class C:
    def __init__(self, major, apps=("uom", "hr_contract")):
        self.capabilities = SimpleNamespace(major=major); self.apps = apps

    def execute_kw(self, model, method, args, kw=None):
        if model == "ir.ui.view":
            return [{"id": 1, "name": "ingenium x", "model": "res.partner", "type": "tree", "arch_db": "<xpath expr=\"//tree\" position=\"inside\"/>", "inherit_id": [2, "p"]}]
        if model == "ir.module.module":
            return [{"name": a} for a in self.apps]
        return []


def test_forecast_lists_every_newer_version_with_screens_and_data_moves(monkeypatch):
    monkeypatch.setattr(rsu, "_client", lambda cid, db: C(17))
    out = rsu.upgrade_forecast("c1", None)
    assert [s["version"] for s in out["steps"]] == [18, 19, 20]
    assert out["steps"][0]["screens_to_fix"] == 1 and out["steps"][0]["auto_fixable"] == 1
    assert any("hr.version" in m for m in out["steps"][1]["data_moves"]) and any("ir.access" in m for m in out["steps"][2]["data_moves"])
    assert "Rehearse on a copy" in out["summary"]


def test_forecast_on_newest_version():
    import pytest  # noqa: F401
    rsu_client = C(20)
    rsu._client_orig = rsu._client
    try:
        rsu._client = lambda cid, db: rsu_client
        assert rsu.upgrade_forecast("c1", None)["summary"] == "You're on the newest version."
    finally:
        rsu._client = rsu._client_orig


def test_check_every_version_reports_each_database(monkeypatch):
    monkeypatch.setattr(rs, "_get", lambda db, cid, pid, kind: object())
    monkeypatch.setattr(rs.vs, "item_out", lambda row: {"payload": {"steps": []}})
    monkeypatch.setattr(rs, "_client", lambda cid, db: C({"a": 17, "b": 20}[cid]))
    monkeypatch.setattr(rs.ss, "check_plan", lambda client, steps, **k: {"counts": {"ready": 1}, "can_apply": True,
                                                                         "steps": {"s1": {"verdict": "ready", "message": ""}}})
    out = rs.suite_plan_check_every_version("a", "p", rs.EveryVersionBody(targets=["b", "a"]), None)
    assert [r["version"] for r in out["results"]] == ["17", "20"] and out["same_everywhere"]
