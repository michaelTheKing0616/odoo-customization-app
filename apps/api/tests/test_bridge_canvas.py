from app.bridge.canvas import agent_call, check_canvas, from_defn

DEFN = {
    "connector": "stripe",
    "odoo_model": "account.payment",
    "mapping": [{"remote": "amount", "odoo": "amount", "transform": "to_float", "money": True}],
    "remote_fields": {"amount": "float"},
    "trigger": {"kind": "webhook"},
}


def test_canvas():
    c = from_defn("f", DEFN)
    assert {"connector", "odoo", "map", "guard"} <= {
        n["kind"] for n in c["nodes"]
    } and check_canvas(c) == []
    assert check_canvas(
        {"nodes": [{"id": "a", "kind": "nope"}], "edges": [{"from": "a", "to": "b"}]}
    )


def test_agent_safety():
    flow = {"live": 1, "versions": [{"n": 1, "money": True, "defn": DEFN}]}
    r = agent_call(None, "f", {"amount": "10"}, dry_run=True, get_flow=lambda: flow, candidates=[])
    assert r["ok"] and r["sandbox"] and r["would"] == "create"
    assert agent_call(None, "f", {"amount": "10"}, dry_run=False, get_flow=lambda: flow)[
        "refused"
    ].startswith("Money")
    assert agent_call(None, "f", {}, get_flow=lambda: None)["refused"]
