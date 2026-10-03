"""Risk escalations only raise, and they stop at R4."""

from __future__ import annotations

from itertools import product

from app.changeset.policy import policy_for_op, risk_of

_ORDER = ("R0", "R1", "R2", "R3", "R4")

# Catalog bases: R1, R2, R3, and R4. Models here are not protected:elevate.
_OPS = (
    {"type": "menu.create", "params": {"model": "ir.ui.menu"}},
    {"type": "translation.upsert", "params": {"lang": "en_US", "value": "Note"}},
    {"type": "field.create", "params": {"model": "sale.order", "name": "x_note", "field_type": "char"}},
    {"type": "report.inherit", "params": {"model": "sale.order"}},
    {"type": "access.create", "params": {"model": "sale.order", "group": "sales"}},
    {"type": "cron.create", "params": {"model": "sale.order", "name": "Sweep"}},
    {"type": "module.uninstall", "params": {"module": "sale"}},
    {"type": "data.delete", "params": {"model": "res.partner"}},
)


def _rank(risk: str) -> int:
    return _ORDER.index(risk)


def _menu() -> dict:
    return {"type": "menu.create", "params": {"model": "ir.ui.menu"}}


def _assert_one_step(op: dict, **flags: object) -> None:
    base = risk_of(op)
    raised = risk_of(op, **flags)
    assert raised in _ORDER
    assert _rank(raised) == min(_rank(base) + 1, len(_ORDER) - 1)


def test_rows_over_1000_or_users_over_10_raises_risk() -> None:
    op = _menu()
    base = risk_of(op)
    _assert_one_step(op, rows=1001)
    _assert_one_step(op, users=11)
    assert risk_of(op, rows=1000) == base
    assert risk_of(op, users=10) == base
    assert risk_of(op, rows=0, users=0) == base
    both = risk_of(op, rows=1001, users=11)
    assert _rank(both) == _rank(base) + 2
    assert both in _ORDER


def test_outbound_raises_risk() -> None:
    op = _menu()
    assert risk_of(op, outbound=False) == risk_of(op)
    _assert_one_step(op, outbound=True)


def test_no_simulation_on_production_raises_risk() -> None:
    op = _menu()
    assert risk_of(op, no_simulation_on_production=False) == risk_of(op)
    _assert_one_step(op, no_simulation_on_production=True)
    high = {"type": "access.create", "params": {"model": "sale.order", "group": "sales"}}
    assert risk_of(high) == "R3"
    assert risk_of(high, no_simulation_on_production=True) == "R4"
    assert policy_for_op(high, "production")["deny"] is False
    denied = policy_for_op(high, "production", no_simulation_on_production=True)
    assert denied["deny"] is True
    assert denied["allow"] is False


def test_mode_c_raises_risk() -> None:
    op = _menu()
    assert risk_of(op, mode_c=False) == risk_of(op)
    _assert_one_step(op, mode_c=True)


def test_final_risk_is_at_least_base_for_ops_and_combinations() -> None:
    row_counts = (0, 1000, 1001)
    user_counts = (0, 10, 11)
    flags = (False, True)
    for op in _OPS:
        base = risk_of(op)
        assert base in _ORDER
        for rows, users, outbound, mode_c, protected, no_simulation in product(
            row_counts, user_counts, flags, flags, flags, flags
        ):
            final = risk_of(
                op,
                rows=rows,
                users=users,
                outbound=outbound,
                mode_c=mode_c,
                protected=protected,
                no_simulation_on_production=no_simulation,
            )
            assert final in _ORDER
            assert _rank(final) >= _rank(base)
            for claimed in ("R0", "R1", "R4"):
                claimed_op = {**op, "risk": claimed}
                assert risk_of(
                    claimed_op,
                    rows=rows,
                    users=users,
                    outbound=outbound,
                    mode_c=mode_c,
                    protected=protected,
                    no_simulation_on_production=no_simulation,
                ) == final
    stacked = risk_of(
        {"type": "access.create", "params": {"model": "sale.order", "group": "sales"}},
        rows=1001,
        users=11,
        outbound=True,
        mode_c=True,
        protected=True,
        no_simulation_on_production=True,
    )
    assert stacked == "R4"
