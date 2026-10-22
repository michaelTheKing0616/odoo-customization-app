"""Suite steps map to validator-accepted change-set ops and pass the shared gates."""
from app import suite_changeset as sc
from app import suite_setup as ss
from app.changeset.validate import validate

ALL = [{"type": "install", "inputs": {"modules": ["sale", "stock"]}},
       {"type": "country_package", "inputs": {"country_code": "NG"}},
       {"type": "create", "inputs": {"model": "account.journal", "values": {"name": "B", "code": "B", "type": "bank"}}},
       {"type": "setting", "inputs": {"values": {"group_uom": True}}},
       {"type": "update", "inputs": {"model": "res.partner", "id": 3, "values": {"name": "a"}}, "depends_on": ["s3"]},
       {"type": "import", "inputs": {"model": "res.partner", "rows": [["a"]] * 2000}},
       {"type": "units", "inputs": {"name": "Box", "reference": "Units", "factor": 12}}]


def _steps(raw=ALL, kind="setup"):
    out, errs = ss.normalise_steps(raw, kind=kind)
    assert not errs
    return out


def test_every_step_type_maps_to_a_valid_changeset():
    steps = _steps()
    [cs] = sc.steps_to_changesets(steps)
    assert [o["type"] for o in cs] == ["module.install", "module.install", "module.install", "data.create_batch",
                                       "setting.set", "data.update_batch", "data.import_upsert", "data.import_upsert",
                                       "data.create_batch"]
    assert cs[2]["params"]["module"] == "l10n_ng"
    assert cs[5]["depends_on"] == [3]
    assert [o["params"]["row_count"] for o in cs[6:8]] == [1000, 1000]  # split to the shared row cap
    rep = validate(cs, known_models={"account.journal", "res.partner", "uom.uom"})
    assert rep["valid"], [st["errors"] for st in rep["stages"]]
    g = sc.gate(steps)
    assert g["ok"] and not g["blocked"]


def test_undo_remove_maps_to_unlink():
    steps = _steps([{"type": "remove", "inputs": {"model": "res.partner", "id": 9}}], kind="undo")
    [cs] = sc.steps_to_changesets(steps)
    assert cs[0]["type"] == "data.unlink" and cs[0]["params"]["ids"] == [9]
    assert sc.gate(steps)["ok"]


def test_large_plans_split_under_max_ops():
    steps = _steps([{"type": "create", "inputs": {"model": "res.partner", "values": {"name": f"p{i}"}}} for i in range(120)])
    css = sc.steps_to_changesets(steps)
    assert len(css) == 3 and all(len(c) <= 50 for c in css)
    assert sc.gate(steps)["ok"]


def test_gate_blocks_what_the_validator_refuses(monkeypatch):
    steps = _steps([{"type": "create", "inputs": {"model": "res.partner", "values": {"name": "x"}}}])
    monkeypatch.setattr(sc, "step_ops", lambda s: [{"type": "nope.op", "params": {"suite_step_id": s["id"]}}])
    g = sc.gate(steps)
    assert not g["ok"] and "s1" in g["blocked"]


def test_gate_blocks_policy_denials(monkeypatch):
    steps = _steps([{"type": "create", "inputs": {"model": "res.partner", "values": {"name": "x"}}}])
    monkeypatch.setattr(sc.cs_policy, "policy_for_op", lambda op, env: {"deny": True, "allow": False, "approvers": 0})
    assert sc.gate(steps)["blocked"] == {"s1": "The shared change policy refuses this step."}
