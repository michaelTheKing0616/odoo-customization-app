"""Ingenium change-set engine tests."""

from __future__ import annotations

from app.changeset.executor import apply, get_journal, reset_journal
from app.changeset.ops import get_op
from app.changeset.plan_card import render_plan_card
from app.changeset.policy import policy_decision, risk_of, self_approval_allowed
from app.changeset.validate import validate


def _field_create(model: str = "x_test.model", name: str = "x_flag") -> dict:
    return {"type": "field.create", "params": {"model": model, "name": name, "field_type": "char"}}


def test_unknown_op_rejected() -> None:
    report = validate([{"type": "rpc.read", "params": {}}], known_models=set())
    static = next(s for s in report["stages"] if s["name"] == "static")
    assert static["passed"] is False
    assert any("unknown" in e for e in static["errors"])


def test_51st_op_rejected() -> None:
    ops = [_field_create() for _ in range(51)]
    report = validate(ops, known_models={"x_test.model"})
    shape = next(s for s in report["stages"] if s["name"] == "shape")
    assert shape["passed"] is False


def test_missing_model_suggests_at_most_three() -> None:
    known = {f"res.partner.{i}" for i in range(20)}
    known.add("res.partner")
    report = validate(
        [_field_create(model="res.partnr", name="x_a")],
        known_models=known,
    )
    grounding = next(s for s in report["stages"] if s["name"] == "grounding")
    assert grounding["passed"] is False
    assert len(grounding["errors"]) == 1
    assert grounding["errors"][0].count("did_you_mean=") == 1
    hints = grounding["errors"][0].split("did_you_mean=")[1]
    assert hints.count(",") <= 2


def test_risk_never_decreases() -> None:
    op = {"type": "menu.create", "params": {"model": "ir.ui.menu"}}
    base = risk_of(op)
    elevated = risk_of(
        op,
        rows=2000,
        users=20,
        outbound=True,
        mode_c=True,
        protected=True,
    )
    order = ("R0", "R1", "R2", "R3", "R4")
    assert order.index(elevated) >= order.index(base)


def test_r3_production_needs_two_approvers() -> None:
    d = policy_decision("R3", "production")
    assert d["approvers"] == 2
    assert d["needs_simulation"] is True
    assert d["deny"] is False


def test_r4_denied() -> None:
    d = policy_decision("R4", "production")
    assert d["deny"] is True
    assert d["allow"] is False
    d2 = policy_decision("R4", "staging")
    assert d2["deny"] is True


def test_self_approval_false_for_r3() -> None:
    assert self_approval_allowed("R3") is False
    assert self_approval_allowed("R4") is False
    assert self_approval_allowed("R2") is True


def test_plan_hash_changes_when_assumptions_change() -> None:
    cs = [_field_create()]
    a = render_plan_card(cs, goal="g", assumptions=["a"], environment="staging")
    b = render_plan_card(cs, goal="g", assumptions=["b"], environment="staging")
    assert a["plan_hash"] != b["plan_hash"]


def test_mode_t_failure_rolls_back_fully() -> None:
    reset_journal()
    cs = [_field_create(), _field_create(name="x_two")]
    result = apply(cs, mode="T", fail_at=1)
    assert result["status"] == "ROLLED_BACK"
    assert result["applied_count"] == 0
    assert not any(e.get("kind") == "RESULT" for e in get_journal())


def test_mode_c_compensates_in_reverse() -> None:
    reset_journal()
    cs = [
        _field_create(name="x_one"),
        _field_create(name="x_two"),
        _field_create(name="x_three"),
    ]
    result = apply(cs, mode="C", fail_at=2)
    assert result["status"] == "ROLLED_BACK"
    assert result["risk_bump"] == 1
    compensations = [e for e in get_journal() if e.get("kind") == "COMPENSATE"]
    results = [e for e in get_journal() if e.get("kind") == "RESULT"]
    assert [e["index"] for e in compensations] == [1, 0]
    assert {e["index"] for e in compensations} == {e["index"] for e in results}


def test_second_apply_is_idempotent() -> None:
    reset_journal()
    cs = [_field_create()]
    first = apply(cs, mode="T")
    journal_len = len(get_journal())
    second = apply(cs, mode="T")
    assert first == second
    assert len(get_journal()) == journal_len


def test_module_uninstall_and_data_delete_are_r4() -> None:
    assert get_op("module.uninstall").risk_base == "R4"
    assert get_op("data.delete").risk_base == "R4"


def test_field_create_lint_requires_x_prefix() -> None:
    report = validate(
        [{"type": "field.create", "params": {"model": "x_m", "name": "bad"}}],
        known_models={"x_m"},
    )
    lints = next(s for s in report["stages"] if s["name"] == "lints")
    assert lints["passed"] is False


def test_rpc_write_forbidden() -> None:
    report = validate([{"type": "rpc.write", "params": {"model": "x"}}], known_models={"x"})
    static = next(s for s in report["stages"] if s["name"] == "static")
    assert static["passed"] is False


def test_catalog_is_the_closed_list() -> None:
    from app.changeset.ops import OP_CATALOG

    assert len(OP_CATALOG) >= 55
    assert "rpc.write" not in OP_CATALOG
    assert OP_CATALOG["module.uninstall"].risk_base == "R4"
    assert OP_CATALOG["field.create"].ddl is True
