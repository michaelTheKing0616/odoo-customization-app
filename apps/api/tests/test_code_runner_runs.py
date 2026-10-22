import time

import pytest

from app.code_runner import runs as rr
from app.code_runner.child import ScriptError, check_source, plain_traceback


def test_dunder_access_refused():
    for src in ["x = odoo.__class__", "getattr(odoo, '__closure__')", "__import__('os')"]:
        with pytest.raises(ScriptError):
            check_source(src)
    check_source("odoo.execute_kw('res.partner', 'search', [[]])")


def ch(op, model="res.partner", i=1, before=None, after=None):
    return {"op": op, "model": model, "id": i, "before": before, "after": after}


def test_safety_meter_and_money():
    assert rr.safety([], [])["level"] == "none"
    low = rr.safety([ch("write", before={"name": "a"}, after={"name": "b"})], [])
    assert low["level"] == "low" and not low["needs_approval"] and low["undoable"]
    money = rr.safety([ch("write", "account.move")], [])
    assert money["needs_approval"] and money["money"] == ["account.move"]
    dele = rr.safety([ch("unlink")] + [ch("method")], [])
    assert dele["level"] == "high" and not dele["undoable"]


def receipt(**kw):
    base = {"mode": "dry", "connection_id": "c", "status": "done", "sample": False, "safety": {"needs_approval": False},
            "receipt": {"code_hash": rr.code_hash("x=1"), "expires_at": time.time() + 60}}
    base.update(kw)
    return base


def test_real_run_gates():
    rr.check_real_run(receipt(), connection_id="c", script="x=1", write_mode="standard")
    cases = [(None, "dry_run_receipt_required"), (receipt(connection_id="d"), "dry_run_receipt_required"),
             (receipt(status="failed"), "dry_run_failed"), (receipt(sample=True), "sample_only"),
             (receipt(receipt={"code_hash": "zz", "expires_at": time.time() + 60}), "code_changed"),
             (receipt(receipt={"code_hash": rr.code_hash("x=1"), "expires_at": time.time() - 1}), "receipt_expired"),
             (receipt(safety={"needs_approval": True}), "approval_required")]
    for r, code in cases:
        with pytest.raises(rr.Refused) as e:
            rr.check_real_run(r, connection_id="c", script="x=1", write_mode="standard")
        assert e.value.code == code
    with pytest.raises(rr.Refused) as e:
        rr.check_real_run(receipt(), connection_id="c", script="x=1", write_mode="observer")
    assert e.value.code == "observer_connection"


def test_approval_rules(tmp_path, monkeypatch):
    monkeypatch.setenv("INGENIUM_CODE_RUNNER_DIR", str(tmp_path))
    r = receipt(id="11111111-1111-1111-1111-111111111111", requested_by="u1")
    with pytest.raises(rr.Refused):
        rr.approve(r, approver="u2", role="developer", auth_on=True, requester_ok=False)
    with pytest.raises(rr.Refused):
        rr.approve(r, approver="u1", role="admin", auth_on=True, requester_ok=False)
    assert rr.approve(r, approver="u2", role="admin", auth_on=True, requester_ok=False)["approved"]
    rr.check_real_run({**r, "safety": {"needs_approval": True}}, connection_id="c", script="x=1", write_mode="standard")


def test_undo_script_reverses_newest_first():
    run = {"id": "abcdef12", "changes": [ch("create", i=5, after={"name": "n"}),
                                         ch("write", i=7, before={"name": "old", "user_id": [3, "Bob"]}, after={"name": "new"}),
                                         ch("unlink", i=9)]}
    lines = rr.undo_script(run).splitlines()
    assert "Not undone: unlink" in lines[1]
    assert lines[2] == "odoo.execute_kw('res.partner', 'write', [[7], {'name': 'old', 'user_id': 3}])"
    assert lines[3] == "odoo.execute_kw('res.partner', 'unlink', [[5]])"


def test_profile_fixes_and_estimate():
    calls = [{"model": "res.partner", "method": "write", "line": 4, "ms": 2.0} for _ in range(25)]
    p = rr.profile(calls, "a\nb\nc\nfor x in y: odoo.execute_kw('res.partner','write',[[x],{}])\n")
    assert p["lines"][0]["line"] == 4 and "write/unlink once" in p["fixes"][0]["fix"]
    est = rr.estimate({"sample_counts": [{"model": "res.partner", "count": 200}], "timing_ms": 1000,
                       "calls": [{"method": "search_read"}], "changes": [1] * 20})
    assert est["records"] == 200 and est["seconds"] == 10.0 and est["writes"] == 200


def test_plain_traceback_points_at_script_line():
    try:
        exec(compile("x = 1\ny = {}['missing']\n", "<script>", "exec"), {})
    except KeyError as exc:
        tb = plain_traceback(exc)
    assert tb["line"] == 2 and tb["kind"] == "KeyError" and tb["hint"]
