"""T8-OP-SCHEMA risk rules and the twelve-part schema contract. Fakes only."""

from __future__ import annotations

import pytest

from app.changeset.dispatch import DispatchError, dispatch_op
from app.changeset.handlers import apply_memory, handler_for
from app.changeset.ops import OP_CATALOG
from app.changeset.policy import risk_of
from app.changeset.schema_ops import (
    CONSTRAINT_X_MODELS_ONLY,
    SCHEMA_OP_TYPES,
    TWELVE_PARTS,
    TYPE_CHANGE_UNSUPPORTED,
    adjusted_schema_risk,
    schema_contracts,
)

pytestmark = pytest.mark.no_app_db


class _Port:
    """In-memory port. A schema refusal must not call it."""

    def __init__(self) -> None:
        self.created: list[tuple[str, dict]] = []

    def create(self, model: str, values: dict) -> int:
        self.created.append((model, values))
        return len(self.created)

    def write(self, model: str, ids: list[int], values: dict) -> None:
        raise AssertionError("write")


def test_schema_ops_have_twelve_parts() -> None:
    contracts = schema_contracts()
    assert tuple(contract.type for contract in contracts) == SCHEMA_OP_TYPES
    assert len(contracts) == 8
    for contract in contracts:
        parts = contract.as_parts()
        assert tuple(parts) == TWELVE_PARTS
        assert len(parts) == 12
        for name, value in parts.items():
            assert value is not None, name
        entry = OP_CATALOG[contract.type]
        assert contract.risk_base == entry.risk_base
        assert contract.reversible == entry.reversible
        assert contract.ddl is entry.ddl
        assert contract.simulate_in_place is (not entry.ddl)
        assert contract.params_schema["type"] == "object"
        assert contract.params_schema["required"]
        assert contract.postconditions
        params = {"model": "x_ticket", "name": "x_note"}
        assert isinstance(contract.plan(params), str)
        assert contract.type in contract.plan(params)
        assert contract.risk_adjust(params) == entry.risk_base
    by_type = {contract.type: contract for contract in contracts}
    created = by_type["field.create"]
    assert any(
        "cascade" in issue
        for issue in created.preconditions(
            {
                "model": "sale.order",
                "name": "x_a",
                "ttype": "many2one",
                "relation": "res.partner",
                "on_delete": "cascade",
            }
        )
    )
    assert created.inverse({"model": "sale.order", "name": "x_note", "ttype": "char"})["type"] == "field.deprecate"
    assert by_type["field.delete"].inverse({"model": "x_ticket", "name": "x_note"}) is None


def test_compute_field_is_r3() -> None:
    computed = {
        "type": "field.create",
        "params": {"model": "sale.order", "name": "x_total", "compute": "_compute_x_total"},
    }
    plain = {"type": "field.create", "params": {"model": "sale.order", "name": "x_note", "ttype": "char"}}
    updated = {
        "type": "field.update",
        "params": {"model": "x_ticket", "name": "x_total", "compute": "_compute_x_total"},
    }
    labeled = {"type": "field.update", "params": {"model": "x_ticket", "name": "x_note", "string": "Note"}}
    assert risk_of(computed) == "R3"
    assert risk_of(plain) == "R2"
    assert risk_of(updated) == "R3"
    assert risk_of(labeled) == "R1"
    assert adjusted_schema_risk("field.create", computed["params"]) == "R3"


def test_field_type_change_is_unsupported() -> None:
    handler = handler_for("field.update")
    change = {"model": "sale.order", "name": "x_note", "ttype": "float"}
    same = {"model": "sale.order", "name": "x_note", "ttype": "char", "current_type": "char"}
    label = {"model": "sale.order", "name": "x_note", "string": "Note"}
    assert TYPE_CHANGE_UNSUPPORTED in handler.issues(change)
    assert handler.refuse_reason(change) == TYPE_CHANGE_UNSUPPORTED
    assert handler.issues(same) == []
    assert handler.refuse_reason(same) is None
    assert handler.issues(label) == []
    port = _Port()
    with pytest.raises(DispatchError, match="type change"):
        dispatch_op(port, {"type": "field.update", "params": change})
    assert port.created == []
    with pytest.raises(PermissionError, match="type change"):
        apply_memory({}, {"type": "field.update", "params": change})
    store: dict = {}
    apply_memory(store, {"type": "field.update", "params": label})
    assert store


def test_field_delete_nonempty_financial_hr_or_stock_is_r4() -> None:
    fake_counts = {
        "hr.employee": 4,
        "stock.picking": 1,
        "account.journal": 2,
        "account.tax": 0,
        "sale.order": 500,
    }
    assert adjusted_schema_risk(
        "field.delete",
        {"model": "hr.employee", "name": "x_note"},
        counts=fake_counts,
    ) == "R4"
    assert adjusted_schema_risk(
        "field.delete",
        {"model": "stock.picking", "name": "x_note"},
        counts=fake_counts,
    ) == "R4"
    assert adjusted_schema_risk(
        "field.delete",
        {"model": "account.journal", "name": "x_note"},
        counts=fake_counts,
    ) == "R4"
    assert adjusted_schema_risk(
        "field.delete",
        {"model": "account.tax", "name": "x_note"},
        counts=fake_counts,
    ) == "R3"
    assert adjusted_schema_risk(
        "field.delete",
        {"model": "sale.order", "name": "x_note"},
        counts=fake_counts,
    ) == "R3"
    assert risk_of(
        {"type": "field.delete", "params": {"model": "hr.employee", "name": "x_note", "record_count": 4}}
    ) == "R4"
    assert risk_of(
        {"type": "field.delete", "params": {"model": "stock.picking", "name": "x_note", "record_count": 0}}
    ) == "R3"
    assert risk_of({"type": "field.delete", "params": {"model": "hr.employee", "name": "x_note"}}) == "R3"


def test_constraint_sql_is_allowed_on_x_models_only() -> None:
    handler = handler_for("constraint.sql")
    allowed = {"model": "x_ticket", "name": "x_ticket_uniq", "definition": "unique(x_name)"}
    assert handler.issues(allowed) == []
    assert handler.refuse_reason(allowed) is None
    store: dict = {}
    apply_memory(store, {"type": "constraint.sql", "params": allowed})
    assert store
    port = _Port()
    for model in ("sale.order", "account.move", "hr.employee", "stock.picking"):
        params = {"model": model, "name": "uniq", "definition": "unique(name)"}
        assert handler.issues(params) == [CONSTRAINT_X_MODELS_ONLY]
        assert handler.refuse_reason(params) == CONSTRAINT_X_MODELS_ONLY
        with pytest.raises(PermissionError, match="x_ models only"):
            apply_memory({}, {"type": "constraint.sql", "params": params})
        with pytest.raises(DispatchError, match="x_ models only"):
            dispatch_op(port, {"type": "constraint.sql", "params": params})
    assert port.created == []
