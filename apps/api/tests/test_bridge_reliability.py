import json
from types import SimpleNamespace

import pytest

from app.bridge.reliability import contract_tests, detect_drift, replay

OF = {
    "name": {"type": "char", "required": True},
    "email": {"type": "char"},
    "list_price": {"type": "float"},
    "phone": {"type": "char"},
}
RF = {"full_name": "char", "email_address": "char"}
MAP = [
    {"remote": "full_name", "odoo": "name", "transform": "trim"},
    {"remote": "email_address", "odoo": "email", "transform": "none"},
]


def test_contract_tests():
    ok = contract_tests(MAP, RF, OF, [{"full_name": "Ada", "email_address": "a@x"}])
    assert ok["ok"]
    bad = contract_tests(MAP, RF, OF, [{"email_address": "a@x"}])
    assert not bad["ok"] and "name would be empty" in bad["cases"][0]["problems"]
    assert not contract_tests(MAP, RF, OF, [])["ok"]  # no samples, no pass


def test_drift():
    d = detect_drift(
        {"full_name": "char", "email_address": "char"},
        {"full_name": "dict", "telephone": "char"},
        MAP,
        OF,
    )
    kinds = {f["kind"] for f in d["proposed_fixes"]}
    assert (
        d["removed"] == ["email_address"]
        and d["type_changed"] == ["full_name"]
        and d["severity"] == "breaking"
    )
    assert {"unmap", "map_new"} <= kinds


def test_replay(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "app.bridge.reliability.enqueue",
        lambda db, c, k, p: seen.update(k=k, p=p) or SimpleNamespace(id="n"),
    )
    ev = SimpleNamespace(
        status="dead",
        payload_json=json.dumps({"a": 1}),
        idempotency_key="k1",
        attempts=8,
        connection_id="c",
    )
    replay(None, ev, {"a": 2})
    assert ev.status == "replayed" and seen["p"] == {"a": 2} and seen["k"].startswith("k1:replay:")
    with pytest.raises(ValueError):
        replay(None, ev)
    ev2 = SimpleNamespace(
        status="dead", payload_json="{}", idempotency_key="k2", attempts=1, connection_id="c"
    )
    with pytest.raises(ValueError):
        replay(None, ev2, {"api_key": "x"})
