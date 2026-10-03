"""T8-OP-DATA risk rules. Fakes only. No live Odoo and no writes."""

from __future__ import annotations

import pytest

from app.changeset.data_ops import (
    BATCH_NOT_200,
    BATCH_SIZE,
    DATA_DELETE_ALLOW_LIST,
    DELETE_DENIED,
    DELETE_NEEDS_TWO_APPROVERS,
    ROW_CAP,
    ROW_CAP_EXCEEDED,
    SAMPLE_LIMIT,
    SAMPLE_OVER_LIMIT,
    STOCK_QUANT_REFUSED,
    data_limit_issues,
    delete_port_reason,
    planned_batch_sizes,
)
from app.changeset.dispatch import DispatchError, dispatch_op
from app.changeset.handlers import apply_memory, handler_for
from app.changeset.ops import OP_CATALOG, get_op
from app.changeset.policy import risk_of

pytestmark = pytest.mark.no_app_db

_LIMITED = (
    "data.create_batch",
    "data.update_batch",
    "data.archive_batch",
    "data.import_upsert",
    "data.merge",
    "translation.upsert",
)
_PROTECTED_BATCH = (
    "data.create_batch",
    "data.update_batch",
    "data.archive_batch",
    "data.import_upsert",
    "data.merge",
)


class _Port:
    """In-memory port. A refused data op must not call it."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def create(self, model: str, values: dict) -> int:
        self.calls.append(("create", model, dict(values)))
        return len(self.calls)

    def write(self, model: str, ids: list[int], values: dict) -> None:
        self.calls.append(("write", model, list(ids), dict(values)))

    def unlink(self, model: str, ids: list[int]) -> None:
        self.calls.append(("unlink", model, list(ids)))


def _legal_update() -> dict:
    return {
        "model": "res.partner",
        "domain": [["id", "=", 1]],
        "values": {"name": "Ada"},
        "sample": [{}] * SAMPLE_LIMIT,
        "row_count": ROW_CAP,
        "batch_size": BATCH_SIZE,
    }


def test_sample_is_at_most_20_cap_is_1000_and_batches_are_200() -> None:
    assert SAMPLE_LIMIT == 20
    assert ROW_CAP == 1000
    assert BATCH_SIZE == 200
    handler = handler_for("data.update_batch")
    legal = _legal_update()
    assert handler.issues(legal) == []
    assert data_limit_issues(legal) == []
    assert planned_batch_sizes(legal) == [BATCH_SIZE] * 5
    assert planned_batch_sizes({"row_count": 201}) == [200, 1]
    assert planned_batch_sizes({"row_count": 200}) == [200]
    assert planned_batch_sizes({"model": "res.partner"}) == []
    assert max(planned_batch_sizes(legal) or [0]) == BATCH_SIZE

    over_sample = {**legal, "sample": [{}] * (SAMPLE_LIMIT + 1)}
    over_cap = {**legal, "row_count": ROW_CAP + 1}
    wrong_batch = {**legal, "batch_size": BATCH_SIZE - 1}
    claimed = {**legal, "sample_size": SAMPLE_LIMIT + 1, "sample": [{}] * SAMPLE_LIMIT}
    hidden_rows = {**legal, "ids": list(range(ROW_CAP + 1)), "row_count": 1}
    assert handler.issues(over_sample) == [SAMPLE_OVER_LIMIT]
    assert handler.issues(over_cap) == [ROW_CAP_EXCEEDED]
    assert handler.issues(wrong_batch) == [BATCH_NOT_200]
    assert SAMPLE_OVER_LIMIT in handler.issues(claimed)
    assert ROW_CAP_EXCEEDED in handler.issues(hidden_rows)
    assert planned_batch_sizes(over_cap) is None
    assert planned_batch_sizes({"row_count": 400}) == [200, 200]

    combined = {
        "model": "res.partner",
        "sample_size": 21,
        "rows": list(range(1001)),
        "batch_size": "200",
    }
    assert data_limit_issues(combined) == [SAMPLE_OVER_LIMIT, ROW_CAP_EXCEEDED, BATCH_NOT_200]

    unbounded = {"model": "res.partner", "domain": [], "values": {"name": "Ada"}}
    assert handler.issues(unbounded) == ["missing domain", "unbounded domain is forbidden"]
    missing = handler.issues({})
    assert missing[:3] == ["missing model", "missing domain", "missing values"]

    port = _Port()
    store: dict = {}
    for op_type in _LIMITED:
        params = {"model": "res.partner", "domain": [["id", "=", 1]], "values": {"name": "Ada"}, "sample_size": 21}
        assert SAMPLE_OVER_LIMIT in handler_for(op_type).issues(params)
        with pytest.raises(ValueError, match="sample is at most 20"):
            apply_memory(store, {"type": op_type, "params": params})
        with pytest.raises(DispatchError, match="sample is at most 20"):
            dispatch_op(port, {"type": op_type, "params": params})
        with pytest.raises(DispatchError, match="row cap is 1000"):
            dispatch_op(port, {"type": op_type, "params": {**params, "sample_size": 20, "row_count": 1001}})
        with pytest.raises(DispatchError, match="batches are 200"):
            dispatch_op(port, {"type": op_type, "params": {**params, "sample_size": 20, "batch_size": 500}})
    assert store == {}
    assert port.calls == []


def test_merge_is_r3_and_not_reversible() -> None:
    entry = OP_CATALOG["data.merge"]
    assert entry.risk_base == "R3"
    assert entry.reversible == "N"
    assert get_op("data.merge") == entry
    params = {"model": "res.partner", "ids": [1, 2]}
    op = {"type": "data.merge", "params": params}
    assert risk_of(op) == "R3"
    assert risk_of({**op, "risk": "R0"}) == "R3"
    handler = handler_for("data.merge")
    assert handler.inverse(params) is None
    assert handler.refuse_reason(params) is None


def test_delete_without_two_approvers_and_allow_list_does_not_reach_the_port() -> None:
    assert OP_CATALOG["data.delete"].risk_base == "R4"
    assert OP_CATALOG["data.delete"].reversible == "N"
    assert DATA_DELETE_ALLOW_LIST == frozenset()
    assert handler_for("data.delete").refuse_reason({"model": "res.partner"}) == "data.delete is prohibited"
    assert handler_for("data.delete").inverse({"model": "res.partner"}) is None

    port = _Port()
    store: dict = {}
    bare = {"type": "data.delete", "params": {"model": "res.partner"}}
    assert delete_port_reason(bare) == DELETE_DENIED
    one = {
        **bare,
        "allow_list": ["res.partner"],
        "approvers": ["ada"],
        "requester": "cam",
    }
    assert delete_port_reason(one) == DELETE_NEEDS_TWO_APPROVERS
    requester_is_approver = {
        **bare,
        "allow_list": ["res.partner"],
        "approvers": ["ada", "cam"],
        "requester": "cam",
    }
    assert delete_port_reason(requester_is_approver) == DELETE_NEEDS_TWO_APPROVERS
    duplicate = {
        **bare,
        "allow_list": ["res.partner"],
        "approvers": ["ada", "ada"],
        "requester": "cam",
    }
    assert delete_port_reason(duplicate) == DELETE_NEEDS_TWO_APPROVERS
    unnamed_requester = {
        **bare,
        "allow_list": ["res.partner"],
        "approvers": ["ada", "ben"],
    }
    assert delete_port_reason(unnamed_requester) == DELETE_NEEDS_TWO_APPROVERS
    wrong_model = {
        **bare,
        "allow_list": ["sale.order"],
        "approvers": ["ada", "ben"],
        "requester": "cam",
    }
    assert delete_port_reason(wrong_model) == DELETE_DENIED
    default_list = {**bare, "approvers": ["ada", "ben"], "requester": "cam"}
    assert delete_port_reason(default_list) == DELETE_DENIED
    in_params = {
        "type": "data.delete",
        "params": {
            "model": "res.partner",
            "allow_list": [],
            "approvers": ["ada", "ben"],
            "requester": "cam",
        },
    }
    assert delete_port_reason(in_params) == DELETE_DENIED

    satisfied = {
        **bare,
        "allow_list": ["res.partner"],
        "approvers": ["ada", "ben"],
        "requester": "cam",
    }
    assert delete_port_reason(satisfied) is None

    for op in (
        bare,
        one,
        requester_is_approver,
        duplicate,
        unnamed_requester,
        wrong_model,
        default_list,
        in_params,
        satisfied,
    ):
        with pytest.raises(DispatchError):
            dispatch_op(port, op)
        with pytest.raises(PermissionError, match="data.delete is prohibited"):
            apply_memory(store, op)
    with pytest.raises(DispatchError, match="data.delete is refused"):
        dispatch_op(port, satisfied)
    assert port.calls == []
    assert store == {}


def test_stock_quant_is_refused_before_the_port() -> None:
    port = _Port()
    quant = {"model": "stock.quant", "domain": [["id", "=", 1]], "values": {"name": "Q"}}
    for op_type in _PROTECTED_BATCH:
        assert handler_for(op_type).refuse_reason(quant) == "protected_deny"
        with pytest.raises(DispatchError, match="protected_deny"):
            dispatch_op(port, {"type": op_type, "params": quant})
    translation = handler_for("translation.upsert")
    assert translation.refuse_reason({"model": "stock.quant", "lang": "fr_FR", "value": "Quant"}) == STOCK_QUANT_REFUSED
    assert translation.refuse_reason({"res_model": "stock.quant", "value": "Quant"}) == STOCK_QUANT_REFUSED
    assert translation.refuse_reason({"model": "res.partner", "lang": "fr_FR", "value": "Partenaire"}) is None
    with pytest.raises(DispatchError, match="stock.quant is refused"):
        dispatch_op(port, {"type": "translation.upsert", "params": {"model": "stock.quant", "value": "Quant"}})
    delete = {
        "type": "data.delete",
        "params": {"model": "stock.quant"},
        "allow_list": ["stock.quant"],
        "approvers": ["ada", "ben"],
        "requester": "cam",
    }
    assert delete_port_reason(delete) == STOCK_QUANT_REFUSED
    with pytest.raises(DispatchError, match="stock.quant is refused"):
        dispatch_op(port, delete)
    assert port.calls == []
