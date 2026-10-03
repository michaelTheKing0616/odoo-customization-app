"""T8-S07. An out-of-band schema change becomes STALE and refuses apply.

The fingerprint bound at approval is the hash of a fake schema slice. A
later slice with a different fingerprint is STALE. Apply does not run, and
the run is not verified. A missing live slice fails closed.

This module uses the in-process executor and a fake slice. It does not call
Odoo and it does not probe a database.
``test_stale_fingerprint_protected_target_and_unknown_outcome_do_not_claim_success``
stays as written.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest
from odoo_client.schema_fingerprint import schema_fingerprint

from app.changeset.executor import (
    _protocol,
    apply,
    changeset_fingerprint,
    get_journal,
    reset_journal,
    schema_drift_status,
)

pytestmark = pytest.mark.no_app_db


class FakePort:
    """In-memory create and write log. It does not open a socket."""

    def __init__(self) -> None:
        self.created: list[tuple[str, dict[str, Any]]] = []
        self.writes: list[tuple[str, list[int], dict[str, Any]]] = []

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Record one create.

        Inputs: model name and values.
        Outputs: a 1-based id local to this object.
        Side effects: appends a copy of ``values``. Does not open a socket.
        """
        self.created.append((model, dict(values)))
        return len(self.created)

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        """Record one write.

        Inputs: model name, ids, and values.
        Outputs: none.
        Side effects: appends copies. Does not open a socket.
        """
        self.writes.append((model, list(ids), dict(values)))


class ClosedPort(FakePort):
    """Port that fails if apply reaches a write. A stale plan never calls it."""

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Refuse a create that passed a stale or missing schema.

        Inputs: model name and values.
        Outputs: none.
        Side effects: none. The call is not stored.
        Raises AssertionError. That means apply wrote after drift refused.
        """
        raise AssertionError("drift suite wrote after a closed schema")

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        """Refuse a write that passed a stale or missing schema.

        Inputs: model name, ids, and values.
        Outputs: none.
        Side effects: none. The call is not stored.
        Raises AssertionError. That means apply wrote after drift refused.
        """
        raise AssertionError("drift suite wrote after a closed schema")


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("drift suite opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


@pytest.fixture(autouse=True)
def _clean_journal() -> None:
    reset_journal()
    yield
    reset_journal()


def _plan(name: str = "x_note") -> list[dict[str, Any]]:
    """One custom field create.

    Inputs: field name. It must already start with ``x_``.
    Outputs: a ``field.create`` op on ``x_ticket``.
    Side effects: none.
    """
    return [
        {
            "type": "field.create",
            "params": {"model": "x_ticket", "name": name, "ttype": "char"},
        }
    ]


def _schema(fields: list[str], **volatile: Any) -> dict[str, Any]:
    """Schema slice for ``x_ticket``.

    Inputs: field names, plus optional volatile keys such as ``id``.
    Outputs: a dict ``schema_fingerprint`` can hash.
    Side effects: none. This is not a live database read.
    """
    slice_data: dict[str, Any] = {"model": "x_ticket", "fields": list(fields)}
    slice_data.update(volatile)
    return slice_data


def _approved() -> tuple[list[dict[str, Any]], str, dict[str, Any], str]:
    """The plan, its hash, the schema slice, and that slice's fingerprint.

    Inputs: none.
    Outputs: the approved field create, the change-set fingerprint, the
    schema slice, and the schema fingerprint bound at approval.
    Side effects: none.
    """
    plan = _plan()
    schema = _schema(["x_note"])
    return plan, changeset_fingerprint(plan), schema, schema_fingerprint(schema)


def _run_is_verified(result: dict[str, Any] | None, journal: list[dict[str, Any]]) -> bool:
    """Whether this run claims a verified apply.

    Inputs: the apply result, or None when apply refused before a result,
    and the journal.
    Outputs: True only when the status is VERIFIED or a VERIFIED row exists.
    Side effects: none.
    """
    if result is not None and result.get("status") == "VERIFIED":
        return True
    return any(entry.get("kind") == "VERIFIED" for entry in journal)


def test_changed_schema_fingerprint_after_approval_is_stale_and_does_not_apply() -> None:
    """An out-of-band schema edit after approval is STALE and does not apply.

    The plan hash still matches. The live slice adds a field, so its
    fingerprint differs. Volatile ids on an otherwise equal slice stay
    CURRENT. The fake port is not called. The journal stays empty. The run
    is not verified.
    """
    plan, approved_hash, schema, fingerprint = _approved()
    volatile = _schema(["x_note"], id=4, write_date="later", create_date="c2")
    changed = _schema(["x_note", "x_shadow"])
    live_fingerprint = schema_fingerprint(changed)
    assert schema_fingerprint(volatile) == fingerprint
    assert schema_drift_status(fingerprint, volatile) == "CURRENT"
    assert live_fingerprint != fingerprint
    assert schema_drift_status(fingerprint, changed) == "STALE"
    assert changeset_fingerprint(plan) == approved_hash
    port = ClosedPort()
    error = _protocol().BridgeError
    result: dict[str, Any] | None = None
    with pytest.raises(error) as caught:
        result = apply(
            plan,
            mode="T",
            port=port,
            approved_hash=approved_hash,
            expected_fingerprint=fingerprint,
            live_fingerprint=live_fingerprint,
        )
    assert caught.value.code == "stale_fingerprint"
    assert result is None
    assert port.created == []
    assert port.writes == []
    assert get_journal() == []
    assert _run_is_verified(result, get_journal()) is False
    assert schema["fields"] == ["x_note"]


def test_missing_live_schema_fails_closed() -> None:
    """A bound fingerprint with no live slice does not apply and is not STALE.

    Absence is not a matching schema and it is not a verified run. The port
    raises if a write is reached. The journal stays empty.
    """
    plan, approved_hash, _schema_slice, fingerprint = _approved()
    port = ClosedPort()
    error = _protocol().BridgeError
    with pytest.raises(error) as closed:
        schema_drift_status(fingerprint, None)
    assert closed.value.code == "schema_fingerprint_mismatch"
    result: dict[str, Any] | None = None
    with pytest.raises(error) as refused:
        result = apply(
            plan,
            mode="T",
            port=port,
            approved_hash=approved_hash,
            expected_fingerprint=fingerprint,
        )
    assert refused.value.code == "stale_fingerprint"
    assert result is None
    assert port.created == []
    assert port.writes == []
    assert get_journal() == []
    assert _run_is_verified(result, get_journal()) is False
