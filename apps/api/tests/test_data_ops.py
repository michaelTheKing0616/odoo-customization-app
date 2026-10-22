"""T8-OP-DATA risk rules. Fakes only. No live Odoo and no writes."""

from __future__ import annotations

from datetime import datetime, timezone

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
from app.changeset.policy import (
    HEAVY_GATE_BACKUP,
    HEAVY_GATE_DISTINCT,
    HEAVY_GATE_SIMULATION,
    HEAVY_GATE_WINDOW,
    risk_of,
)

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
    assert handler_for("data.delete").refuse_reason({"model": "res.partner"}) == DELETE_DENIED
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
    assert delete_port_reason(one) == HEAVY_GATE_DISTINCT
    requester_is_approver = {
        **bare,
        "allow_list": ["res.partner"],
        "approvers": ["ada", "cam"],
        "requester": "cam",
    }
    assert delete_port_reason(requester_is_approver) == HEAVY_GATE_DISTINCT
    duplicate = {
        **bare,
        "allow_list": ["res.partner"],
        "approvers": ["ada", "ada"],
        "requester": "cam",
    }
    assert delete_port_reason(duplicate) == HEAVY_GATE_DISTINCT
    unnamed_requester = {
        **bare,
        "allow_list": ["res.partner"],
        "approvers": ["ada", "ben"],
    }
    assert delete_port_reason(unnamed_requester) == HEAVY_GATE_DISTINCT
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
    # String-only approvers are not a passed heavy gate (no user_id / sim / backup / window).
    assert delete_port_reason(satisfied) == HEAVY_GATE_DISTINCT

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
        with pytest.raises(PermissionError):
            apply_memory(store, op)
    with pytest.raises(DispatchError, match=HEAVY_GATE_DISTINCT):
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


# --- T8-OP-DATA apply through the existing executor -----------------------

from app.changeset.data_ops import (  # noqa: E402
    DATA_APPLY_OPS,
    DATA_OP_TYPES,
    MERGE_PARTNER_ONLY,
    PARTNER_MERGE_WIZARD,
    UPSERT_KEY_REQUIRED,
)
from app.changeset.executor import apply, reset_journal  # noqa: E402
from app.changeset.ops import op_base_risk  # noqa: E402

_RANK = ("R0", "R1", "R2", "R3", "R4")


class _CallPort(_Port):
    """In-memory port with ``execute_kw``. ``search`` answers from ``matches``."""

    def __init__(self, matches: dict | None = None) -> None:
        super().__init__()
        self._matches = dict(matches or {})

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None):
        self.calls.append(("execute_kw", model, method, args, kwargs))
        if method == "search":
            key = repr(args[0])
            if key in self._matches:
                return list(self._matches[key])
            return list(self._matches.get(model, []))
        return True


@pytest.fixture()
def _clean_journal():
    reset_journal()
    yield
    reset_journal()


def _apply_cases() -> dict[str, dict]:
    return {
        "data.create_batch": {"model": "res.partner", "rows": [{"name": "Ada"}, {"name": "Ben"}]},
        "data.update_batch": {
            "model": "res.partner",
            "domain": [["id", "in", [3, 4]]],
            "ids": [3, 4],
            "values": {"comment": "VIP"},
        },
        "data.archive_batch": {"model": "res.partner", "ids": [5, 6]},
        "data.import_upsert": {
            "model": "res.partner",
            "key": "ref",
            "rows": [{"ref": "C-1", "name": "Ada"}, {"ref": "C-2", "name": "Ben"}, {"id": 9, "name": "Cy"}],
        },
        "data.merge": {"model": "res.partner", "ids": [11, 12], "dst_id": 11},
        "translation.upsert": {
            "model": "product.template",
            "ids": [21],
            "field": "name",
            "value": "Chaise",
            "lang": "fr_FR",
        },
    }


def test_every_data_op_is_listed_once() -> None:
    assert set(DATA_OP_TYPES) == {
        "data.create_batch",
        "data.update_batch",
        "data.archive_batch",
        "data.import_upsert",
        "data.merge",
        "data.delete",
        "translation.upsert",
    }
    assert all(op_type in OP_CATALOG for op_type in DATA_OP_TYPES)
    assert DATA_APPLY_OPS == set(DATA_OP_TYPES)
    assert set(_apply_cases()) == DATA_APPLY_OPS - {"data.delete"}


def test_create_batch_applies_through_the_executor(_clean_journal) -> None:
    port = _CallPort()
    op = {"type": "data.create_batch", "params": _apply_cases()["data.create_batch"]}
    result = apply([op], mode="T", port=port)
    assert result["status"] == "VERIFIED"
    assert port.calls == [("create", "res.partner", {"name": "Ada"}), ("create", "res.partner", {"name": "Ben"})]


def test_update_batch_applies_through_the_executor(_clean_journal) -> None:
    port = _CallPort()
    op = {"type": "data.update_batch", "params": _apply_cases()["data.update_batch"]}
    result = apply([op], mode="T", port=port)
    assert result["status"] == "VERIFIED"
    assert port.calls == [("write", "res.partner", [3, 4], {"comment": "VIP"})]


def test_update_batch_resolves_a_domain_with_search_then_writes(_clean_journal) -> None:
    params = {"model": "res.partner", "domain": [["customer_rank", ">", 0]], "values": {"comment": "VIP"}}
    port = _CallPort({"res.partner": [7, 8]})
    result = apply([{"type": "data.update_batch", "params": params}], mode="T", port=port)
    assert result["status"] == "VERIFIED"
    assert port.calls[0] == (
        "execute_kw",
        "res.partner",
        "search",
        [[["customer_rank", ">", 0]]],
        {"limit": ROW_CAP + 1},
    )
    assert port.calls[1:] == [("write", "res.partner", [7, 8], {"comment": "VIP"})]


def test_archive_batch_applies_through_the_executor(_clean_journal) -> None:
    port = _CallPort()
    op = {"type": "data.archive_batch", "params": _apply_cases()["data.archive_batch"]}
    result = apply([op], mode="T", port=port)
    assert result["status"] == "VERIFIED"
    assert port.calls == [("write", "res.partner", [5, 6], {"active": False})]


def test_import_upsert_applies_through_the_executor(_clean_journal) -> None:
    matches = {repr([["ref", "=", "C-1"]]): [41], repr([["ref", "=", "C-2"]]): []}
    port = _CallPort(matches)
    op = {"type": "data.import_upsert", "params": _apply_cases()["data.import_upsert"]}
    result = apply([op], mode="T", port=port)
    assert result["status"] == "VERIFIED"
    searches = [call for call in port.calls if call[0] == "execute_kw"]
    assert [call[2] for call in searches] == ["search", "search"]
    assert all(call[4] == {"limit": 2} for call in searches)
    first_write = next(i for i, call in enumerate(port.calls) if call[0] in {"create", "write"})
    assert all(call[0] == "execute_kw" for call in port.calls[:first_write])
    assert [call for call in port.calls if call[0] in {"create", "write"}] == [
        ("write", "res.partner", [41], {"ref": "C-1", "name": "Ada"}),
        ("create", "res.partner", {"ref": "C-2", "name": "Ben"}),
        ("write", "res.partner", [9], {"name": "Cy"}),
    ]


def test_import_upsert_refuses_an_ambiguous_key_before_any_write(_clean_journal) -> None:
    params = {"model": "res.partner", "key": "ref", "rows": [{"ref": "C-1", "name": "Ada"}]}
    port = _CallPort({repr([["ref", "=", "C-1"]]): [41, 42]})
    with pytest.raises(DispatchError, match="more than one record"):
        apply([{"type": "data.import_upsert", "params": params}], mode="T", port=port)
    assert not any(call[0] in {"create", "write"} for call in port.calls)
    bad = {"model": "res.partner", "rows": [{"name": "Ada"}]}
    with pytest.raises(DispatchError, match=UPSERT_KEY_REQUIRED):
        dispatch_op(_CallPort(), {"type": "data.import_upsert", "params": bad})


def test_merge_applies_through_the_executor_only_at_r3(_clean_journal) -> None:
    op = {"type": "data.merge", "params": _apply_cases()["data.merge"]}
    port = _CallPort()
    with pytest.raises(Exception):
        apply([op], mode="T", port=port, max_risk="R2")
    assert port.calls == []
    reset_journal()
    with pytest.raises(Exception, match="mode_c_irreversible"):
        apply([op], mode="C", port=port, max_risk="R3")
    assert port.calls == []
    reset_journal()
    result = apply([op], mode="T", port=port, max_risk="R3")
    assert result["status"] == "VERIFIED"
    assert port.calls == [
        ("create", PARTNER_MERGE_WIZARD, {"partner_ids": [[6, 0, [11, 12]]], "dst_partner_id": 11}),
        ("execute_kw", PARTNER_MERGE_WIZARD, "action_merge", [[1]], None),
    ]


def test_merge_refuses_other_models_and_a_port_without_methods() -> None:
    port = _CallPort()
    with pytest.raises(DispatchError, match=MERGE_PARTNER_ONLY):
        dispatch_op(port, {"type": "data.merge", "params": {"model": "crm.lead", "ids": [1, 2], "dst_id": 1}})
    with pytest.raises(DispatchError, match="at least two"):
        dispatch_op(port, {"type": "data.merge", "params": {"model": "res.partner", "ids": [1], "dst_id": 1}})
    with pytest.raises(DispatchError, match="dst_id"):
        dispatch_op(port, {"type": "data.merge", "params": {"model": "res.partner", "ids": [1, 2], "dst_id": 3}})
    assert port.calls == []
    plain = _Port()
    with pytest.raises(DispatchError, match="call model methods"):
        dispatch_op(plain, {"type": "data.merge", "params": _apply_cases()["data.merge"]})
    assert plain.calls == []


def test_translation_upsert_applies_through_the_executor(_clean_journal) -> None:
    port = _CallPort()
    op = {"type": "translation.upsert", "params": _apply_cases()["translation.upsert"]}
    result = apply([op], mode="T", port=port)
    assert result["status"] == "VERIFIED"
    assert port.calls == [
        ("execute_kw", "product.template", "write", [[21], {"name": "Chaise"}], {"context": {"lang": "fr_FR"}}),
    ]
    plain = _Port()
    with pytest.raises(DispatchError, match="call model methods"):
        dispatch_op(plain, op)
    no_lang = {**_apply_cases()["translation.upsert"], "lang": ""}
    with pytest.raises(DispatchError, match="needs lang"):
        dispatch_op(_CallPort(), {"type": "translation.upsert", "params": no_lang})
    assert plain.calls == []


def test_delete_never_applies_through_the_executor_even_when_the_gate_is_satisfied(_clean_journal) -> None:
    """String-only approvers are not a passed heavy gate; delete stays refused."""
    satisfied = {
        "type": "data.delete",
        "params": {"model": "res.partner", "ids": [1]},
        "allow_list": ["res.partner"],
        "approvers": ["ada", "ben"],
        "requester": "cam",
    }
    bare = {"type": "data.delete", "params": {"model": "res.partner", "ids": [1]}}
    assert delete_port_reason(bare) == DELETE_DENIED
    assert delete_port_reason(satisfied) == HEAVY_GATE_DISTINCT
    assert op_base_risk("data.delete", satisfied["params"]) == "R4"
    for op in (bare, satisfied):
        for max_risk, escalated in (("R3", False), ("R4", False), ("R4", True)):
            port = _CallPort()
            with pytest.raises(Exception):
                apply([op], mode="T", port=port, max_risk=max_risk, escalated=escalated)
            assert port.calls == []
            reset_journal()


def test_write_batches_are_200() -> None:
    ids = list(range(1, 451))
    port = _CallPort()
    params = {"model": "res.partner", "domain": [["id", "in", ids]], "ids": ids, "values": {"comment": "x"}}
    dispatch_op(port, {"type": "data.update_batch", "params": params})
    assert [len(call[2]) for call in port.calls] == [200, 200, 50]
    assert port.calls[0][2] == ids[:200]
    archive = _CallPort()
    dispatch_op(archive, {"type": "data.archive_batch", "params": {"model": "res.partner", "ids": ids}})
    assert [len(call[2]) for call in archive.calls] == [200, 200, 50]
    translate = _CallPort()
    tr = {"model": "res.partner", "ids": ids, "field": "comment", "value": "x", "lang": "fr_FR"}
    dispatch_op(translate, {"type": "translation.upsert", "params": tr})
    assert [len(call[3][0]) for call in translate.calls] == [200, 200, 50]


def test_cap_1000_is_enforced_on_the_live_search_before_any_write() -> None:
    params = {"model": "res.partner", "domain": [["active", "=", True]], "values": {"comment": "x"}}
    port = _CallPort({"res.partner": list(range(1, ROW_CAP + 2))})
    with pytest.raises(DispatchError, match="row cap is 1000"):
        dispatch_op(port, {"type": "data.update_batch", "params": params})
    assert [call[2] for call in port.calls] == ["search"]
    over_rows = {"model": "res.partner", "rows": [{"name": str(i)} for i in range(ROW_CAP + 1)]}
    with pytest.raises(DispatchError, match="row cap is 1000"):
        dispatch_op(port, {"type": "data.create_batch", "params": over_rows})
    unbounded = {"model": "res.partner", "domain": []}
    with pytest.raises(DispatchError, match="unbounded domain"):
        dispatch_op(port, {"type": "data.archive_batch", "params": unbounded})
    assert [call[2] for call in port.calls] == ["search"]


def test_sample_over_20_never_applies_through_the_executor(_clean_journal) -> None:
    for op_type, params in _apply_cases().items():
        port = _CallPort()
        over = {**params, "sample": [{}] * (SAMPLE_LIMIT + 1)}
        with pytest.raises(DispatchError, match="sample is at most 20"):
            apply([{"type": op_type, "params": over}], mode="T", port=port)
        assert port.calls == []
        reset_journal()


def test_stock_quant_never_applies_through_the_executor(_clean_journal) -> None:
    for op_type, params in _apply_cases().items():
        port = _CallPort()
        quant = {**params, "model": "stock.quant"}
        with pytest.raises(Exception):
            apply([{"type": op_type, "params": quant}], mode="T", port=port, max_risk="R3")
        assert port.calls == []
        with pytest.raises(DispatchError):
            dispatch_op(port, {"type": op_type, "params": quant})
        assert port.calls == []
        reset_journal()


@pytest.mark.parametrize("op_type", DATA_OP_TYPES)
def test_caller_risk_never_lowers_catalog_risk_for_data_ops(op_type: str) -> None:
    params = _apply_cases().get(op_type, {"model": "res.partner", "ids": [1]})
    base = op_base_risk(op_type, params)
    assert _RANK.index(base) >= _RANK.index(OP_CATALOG[op_type].risk_base)
    for caller in _RANK:
        got = risk_of({"type": op_type, "params": params, "risk": caller})
        assert _RANK.index(got) >= _RANK.index(base), (op_type, caller, got)
    assert risk_of({"type": "data.merge", "params": _apply_cases()["data.merge"], "risk": "R0"}) == "R3"
    assert risk_of({"type": "data.delete", "params": {"model": "res.partner"}, "risk": "R0"}) == "R4"

# --- T8-HEAVY-R4 -----------------------------------------------------------

_HEAVY_NOW = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)
_HEAVY_WINDOW = {
    "start": "2026-10-05T14:00:00+00:00",
    "end": "2026-10-05T16:00:00+00:00",
}


def _heavy_person(user_id: str, **extra: object) -> dict:
    record = {"approver_id": user_id, "user_id": user_id, "decision": "approve"}
    record.update(extra)
    return record


def _full_heavy_gate(**overrides: object) -> dict:
    gate = {
        "environment": "production",
        "requester_id": "cam",
        "approvals": [_heavy_person("ada"), _heavy_person("ben")],
        "simulation_passed": True,
        "backup_id": "backup-1",
        "allowed_window": _HEAVY_WINDOW,
        "now": _HEAVY_NOW.isoformat(),
    }
    gate.update(overrides)
    return gate


def _delete_op(**gate_overrides: object) -> dict:
    return {
        "type": "data.delete",
        "params": {"model": "res.partner", "ids": [3, 4]},
        "allow_list": ["res.partner"],
        **_full_heavy_gate(**gate_overrides),
    }


def test_heavy_data_delete_refused_with_only_one_approver() -> None:
    port = _Port()
    op = _delete_op(approvals=[_heavy_person("ada")])
    assert delete_port_reason(op) == HEAVY_GATE_DISTINCT
    with pytest.raises(DispatchError, match=HEAVY_GATE_DISTINCT):
        dispatch_op(port, op)
    assert port.calls == []


def test_heavy_data_delete_refused_when_same_person_or_requester_is_both() -> None:
    port = _Port()
    same = _delete_op(
        approvals=[
            _heavy_person("ada", provider="google"),
            _heavy_person("ada", provider="microsoft"),
        ]
    )
    assert delete_port_reason(same) == HEAVY_GATE_DISTINCT
    with pytest.raises(DispatchError, match=HEAVY_GATE_DISTINCT):
        dispatch_op(port, same)
    both = _delete_op(
        approvals=[
            _heavy_person("cam", provider="google"),
            _heavy_person("cam", provider="microsoft"),
        ]
    )
    assert delete_port_reason(both) == HEAVY_GATE_DISTINCT
    with pytest.raises(DispatchError, match=HEAVY_GATE_DISTINCT):
        dispatch_op(port, both)
    assert port.calls == []


def test_heavy_data_delete_refused_without_simulation_backup_or_window() -> None:
    port = _Port()
    for key, value, reason in (
        ("simulation_passed", False, HEAVY_GATE_SIMULATION),
        ("backup_id", " ", HEAVY_GATE_BACKUP),
        (
            "allowed_window",
            {"start": "2026-10-05T10:00:00+00:00", "end": "2026-10-05T14:00:00+00:00"},
            HEAVY_GATE_WINDOW,
        ),
    ):
        op = _delete_op(**{key: value})
        assert delete_port_reason(op) == reason
        with pytest.raises(DispatchError, match=reason):
            dispatch_op(port, op)
    assert port.calls == []


@pytest.mark.xfail(
    strict=True,
    reason="ingenium_bridge PROHIBITED_OPS still refuses data.delete until the addon can verify the heavy-gate approval itself",
)
def test_heavy_data_delete_applies_with_full_heavy_gate(_clean_journal) -> None:
    port = _Port()
    op = _delete_op()
    assert delete_port_reason(op) is None
    assert handler_for("data.delete").refuse_reason(op["params"], document=[op]) is None
    result = apply([op], mode="T", port=port, max_risk="R4")
    assert result["status"] == "VERIFIED"
    assert port.calls == [("unlink", "res.partner", [3, 4])]


def test_heavy_data_delete_refused_when_model_not_on_allow_list_even_with_full_gate() -> None:
    port = _Port()
    op = {
        "type": "data.delete",
        "params": {"model": "res.partner", "ids": [1]},
        "allow_list": ["sale.order"],
        **_full_heavy_gate(),
    }
    assert delete_port_reason(op) == DELETE_DENIED
    with pytest.raises(DispatchError, match=DELETE_DENIED):
        dispatch_op(port, op)
    with pytest.raises(Exception):
        apply([op], mode="T", port=port, max_risk="R4")
    assert port.calls == []
    reset_journal()
