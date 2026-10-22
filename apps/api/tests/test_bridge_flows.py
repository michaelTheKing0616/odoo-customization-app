import pytest

from app.bridge import flows as fl
from app.code_runner import store


@pytest.fixture(autouse=True)
def _tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "root", lambda: tmp_path)


MONEY = {
    "odoo_model": "account.move",
    "mapping": [{"remote": "total", "odoo": "amount_total", "money": True}],
}


def test_versions_approval_rollout_rollback():
    with pytest.raises(ValueError):
        fl.propose("w", "f", MONEY, "ada", tests_ok=False)
    v1 = fl.propose("w", "f", MONEY, "ada", True)
    assert v1["money"]
    with pytest.raises(PermissionError):
        fl.approve("w", "f", 1, "ada", v1["hash"])
    with pytest.raises(ValueError):
        fl.approve("w", "f", 1, "bayo", "stale")
    fl.approve("w", "f", 1, "bayo", v1["hash"])
    assert fl.set_rollout("w", "f", 1, 100)["live"] == 1
    v2 = fl.propose("w", "f", {**MONEY, "x": 1}, "ada", True)
    fl.approve("w", "f", 2, "bayo", v2["hash"])
    fl.set_rollout("w", "f", 2, 25)
    got = {fl.version_for("w", "f", str(i)) for i in range(200)}
    assert got == {1, 2} and fl.version_for("w", "f", "7") == fl.version_for("w", "f", "7")
    assert fl.rollback("w", "f")["candidate"] is None and fl.version_for("w", "f", "7") == 1
    fl.set_rollout("w", "f", 2, 100)
    assert fl.rollback("w", "f")["live"] == 1


def test_backfill_reconcile_trace():
    assert fl.plan_backfill(1000, 200)["batches"] == 5
    with pytest.raises(ValueError):
        fl.plan_backfill(10**6)
    cur = {"batch": 2, "total": 3}
    cur = fl.backfill_step(cur, lambda o, n: [1, 2, 3][o : o + n], lambda r: r != 2)
    cur = fl.backfill_step(cur, lambda o, n: [1, 2, 3][o : o + n], lambda r: True)
    assert cur["done"] == 2 and cur["failed"] == 1 and cur["finished"] and cur["progress"] == 1.0
    r = fl.reconcile(
        [{"ref": "A", "amount": "10.00"}, {"ref": "B", "amount": 5}],
        [{"ref": "A", "amount": 10}, {"ref": "C", "amount": 1}],
    )
    assert not r["ok"] and r["missing_in_odoo"] == ["B"] and r["only_in_odoo"] == ["C"]
    assert fl.reconcile([{"ref": "A", "amount": "0.1"}], [{"ref": "A", "amount": 0.1}])["ok"]
    fl.trace("w", "f", "r1", "push", "ok")
    fl.trace("w", "f", "r2", "push", "failed", "HTTP 500")
    m = fl.monitor("w", "f")
    assert (
        m["counts"] == {"ok": 1, "failed": 1}
        and m["error_rate"] == 0.5
        and m["last_error"]["record"] == "r2"
    )
    assert [e["step"] for e in fl.get_trace("w", "f", "r1")] == ["push"]
