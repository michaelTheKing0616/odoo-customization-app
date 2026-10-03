"""T8-S02. Apply, verify, inverse, then MetaSnapshot equality.

Round-trips only ops whose handler already returns a real inverse. The
path is in-memory: ``apply_memory``, ``verify`` on a fake observation,
``compensate_memory``, then ``MetaSnapshot`` equality. Ops with no inverse
are listed as not run. This module does not stub an inverse and does not
call Odoo.

A MetaSnapshot mismatch is not success, including when verify already passed.
This file does not claim the suite is green for the whole catalog.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

from app.changeset.handlers import apply_memory, compensate_memory, handler_for
from app.changeset.meta_snapshot import MetaSnapshot
from app.changeset.ops import OP_CATALOG
from app.changeset.protected_registry import reset_detections
from app.changeset.rollback import snapshots_match
from app.changeset.verify import REQUIRED_SMOKE, postconditions_for, verify

pytestmark = pytest.mark.no_app_db

_VIEW_INHERIT = frozenset({"view.inherit.create", "view.inherit.update"})
_BENIGN_PROBE: dict[str, Any] = {
    "model": "x_ticket",
    "name": "x_note",
    "ttype": "char",
    "group": "base.group_user",
    "module": "sale",
    "user": "demo",
    "domain_force": "[('id', '=', 1)]",
    "global": True,
}


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("round-trip opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


def _real_inverse(op_type: str, value: Any) -> bool:
    """Whether ``value`` is an inverse op, not an empty stub.

    Inputs: the forward op type and the handler return value.
    Outputs: True when the value names a catalog op, points ``inverse_of``
    at the forward type, and carries a params object.
    Side effects: none.
    """
    if not isinstance(value, dict) or not value:
        return False
    inverse_type = value.get("type")
    if not isinstance(inverse_type, str) or inverse_type not in OP_CATALOG:
        return False
    if value.get("inverse_of") != op_type:
        return False
    return isinstance(value.get("params"), dict)


def _round_trip_params(op_type: str) -> dict[str, Any]:
    """Params the in-memory applier accepts for one catalog op.

    Inputs: catalog op type.
    Outputs: model, field name, group, and an ingenium xmlid. View inherit
    ops also carry one field xpath so the anchor check passes.
    Side effects: none.
    """
    params = {
        "model": "x_ticket",
        "name": "x_note",
        "group": "base.group_user",
        "xmlid": "ingenium." + op_type.replace(".", "_"),
    }
    if op_type in _VIEW_INHERIT:
        params["xpath"] = "//field[@name='x_note']"
    return params


def _probes(op_type: str) -> tuple[dict[str, Any], ...]:
    """Param sets used to look for an inverse the handler already returns.

    Inputs: catalog op type.
    Outputs: the round-trip params, an empty dict, and one benign probe.
    Side effects: none.
    """
    return (_round_trip_params(op_type), {}, dict(_BENIGN_PROBE))


def _observed_inverse(op_type: str) -> dict[str, Any] | None:
    """Return the first real inverse from a non-refused probe, else None.

    Inputs: catalog op type.
    Outputs: the handler inverse, or None when every non-refused probe has
    none. Refused probes are skipped so a guard does not hide a real inverse.
    Side effects: clears protected-registry detections recorded while probing.
    Does not call Odoo.
    """
    handler = handler_for(op_type)
    try:
        for params in _probes(op_type):
            if handler.refuse_reason(params) is not None:
                continue
            value = handler.inverse(params)
            if _real_inverse(op_type, value):
                return value
        return None
    finally:
        reset_detections()


def _partition() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split the catalog into ops with a real inverse and ops without one.

    Inputs: none.
    Outputs: catalog-order tuples ``(with_inverse, without_inverse)``.
    Side effects: probes handler inverses. Does not call Odoo.
    """
    with_inverse: list[str] = []
    without_inverse: list[str] = []
    for op_type in OP_CATALOG:
        if _observed_inverse(op_type) is None:
            without_inverse.append(op_type)
        else:
            with_inverse.append(op_type)
    return tuple(with_inverse), tuple(without_inverse)


_WITH_INVERSE, _WITHOUT_INVERSE = _partition()


def _passing_observation(ops: list[dict[str, Any]]) -> dict[str, Any]:
    """Fake verification evidence that does not contact Odoo.

    Inputs: the ops just applied in memory.
    Outputs: an observation whose checks pass for those ops.
    Side effects: none.
    """
    posts: dict[str, dict[str, bool]] = {}
    for index, op in enumerate(ops):
        posts[str(index)] = {name: True for name in postconditions_for(op)}
    return {
        "postconditions": posts,
        "fingerprint": {
            "before": "fp-before",
            "after": "fp-after",
            "expected_after": "fp-after",
        },
        "views": {
            "requester": {"rendered": True, "error": None, "live": False},
            "low_privilege": {"rendered": True, "error": None, "live": False},
            "portal": {"rendered": True, "error": None, "live": False},
        },
        "smoke": [{"name": name, "passed": True} for name in REQUIRED_SMOKE],
        "access": {
            "before": {"sales": {"sale.order": ["read"]}},
            "after": {"sales": {"sale.order": ["read"]}},
        },
        "mail": {"before": 2, "after": 2},
        "data": {
            "counts": {"sale.order": {"expected": 4, "actual": 4}},
            "samples": {"sale.order": [{"id": "row-1"}]},
        },
    }


def _round_trip_succeeded(
    *,
    verified: bool,
    before: MetaSnapshot,
    after: MetaSnapshot,
) -> bool:
    """Whether verify passed and the inverse restored the snapshot.

    Inputs: the verify flag, the snapshot from before apply, and the snapshot
    from after the inverse.
    Outputs: True only when verify passed and the two snapshots match. A
    mismatch is not success.
    Side effects: none.
    """
    if verified is not True:
        return False
    if before != after:
        return False
    return snapshots_match(before.to_dict(), after.to_dict()) is True


def _coverage_report() -> str:
    """Name the ops this suite round-trips and the ops it leaves unrun.

    Inputs: none.
    Outputs: a two-line report. The second line is the not-run list.
    Side effects: none.
    """
    ran = ", ".join(_WITH_INVERSE) if _WITH_INVERSE else "(none)"
    skipped = ", ".join(_WITHOUT_INVERSE) if _WITHOUT_INVERSE else "(none)"
    return (
        f"round-tripped ({len(_WITH_INVERSE)}): {ran}\n"
        f"not run ({len(_WITHOUT_INVERSE)}): {skipped}"
    )


@pytest.mark.parametrize("op_type", _WITH_INVERSE)
def test_apply_verify_inverse_restores_meta_snapshot(op_type: str) -> None:
    """Apply, verify, inverse, then MetaSnapshot equality for one op.

    The handler must already return a real inverse for the params used here.
    """
    params = _round_trip_params(op_type)
    inverse = _observed_inverse(op_type)
    assert _real_inverse(op_type, inverse), op_type
    assert inverse is not None
    assert inverse["type"] in OP_CATALOG
    store: dict[str, dict[str, Any]] = {}
    before = MetaSnapshot.from_memory(store)
    op = {"type": op_type, "params": params}
    apply_memory(store, op)
    during = MetaSnapshot.from_memory(store)
    assert during != before, op_type
    report = verify([op], _passing_observation([op]), model_success=False)
    assert report["verified"] is True
    assert report["contacted_odoo"] is False
    compensate_memory(store, op)
    after = MetaSnapshot.from_memory(store)
    assert store == {}
    assert _round_trip_succeeded(verified=True, before=before, after=after) is True, op_type


def test_ops_without_an_inverse_are_not_run() -> None:
    """Ops whose handler returns no inverse stay listed and are not stubbed.

    The catalog is not fully round-tripped. An empty inverse dict does not
    move an op into the round-trip set.
    """
    assert _WITHOUT_INVERSE, _coverage_report()
    assert set(_WITH_INVERSE).isdisjoint(_WITHOUT_INVERSE)
    assert tuple(OP_CATALOG) == tuple(
        op_type for op_type in OP_CATALOG if op_type in set(_WITH_INVERSE) | set(_WITHOUT_INVERSE)
    )
    assert len(_WITH_INVERSE) + len(_WITHOUT_INVERSE) == len(OP_CATALOG)
    for op_type in _WITHOUT_INVERSE:
        assert _observed_inverse(op_type) is None, op_type
        handler = handler_for(op_type)
        for params in _probes(op_type):
            if handler.refuse_reason(params) is not None:
                continue
            assert handler.inverse(params) in (None, {}), op_type
        reset_detections()
    for op_type in _WITH_INVERSE:
        assert _observed_inverse(op_type) is not None, op_type
    assert len(_WITH_INVERSE) < len(OP_CATALOG), _coverage_report()


def test_meta_snapshot_mismatch_is_not_success() -> None:
    """A drifted MetaSnapshot is not a successful round trip.

    Verify may already have passed. The inverse may already have restored
    the store. A later snapshot that does not match the original is still
    not success.
    """
    op_type = "field.create"
    assert op_type in _WITH_INVERSE
    params = _round_trip_params(op_type)
    store: dict[str, dict[str, Any]] = {}
    before = MetaSnapshot.from_memory(store)
    op = {"type": op_type, "params": params}
    apply_memory(store, op)
    report = verify([op], _passing_observation([op]), model_success=False)
    assert report["verified"] is True
    compensate_memory(store, op)
    restored = MetaSnapshot.from_memory(store)
    assert _round_trip_succeeded(verified=True, before=before, after=restored) is True
    apply_memory(store, op)
    drifted = MetaSnapshot.from_memory(store)
    assert drifted != before
    assert snapshots_match(before.to_dict(), drifted.to_dict()) is False
    assert _round_trip_succeeded(verified=report["verified"], before=before, after=drifted) is False
