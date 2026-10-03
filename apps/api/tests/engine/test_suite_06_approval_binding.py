"""T8-S06. Apply is bound to the plan hash and the schema fingerprint.

A changed plan hash does not apply. A changed schema fingerprint does not
apply. A matching hash and a matching fingerprint may apply on the fake
port. A bound fingerprint with no live schema fails closed.

This module uses the in-process executor and a fake port. It does not call
Odoo, and it does not run a live approval.
``test_approval_mismatch_does_not_apply`` and
``test_rt17_modified_plan_is_not_the_approved_hash`` stay as written.
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
    """Port that fails if apply reaches a write. A refused apply never calls it."""

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Refuse a create that passed the approval binding.

        Inputs: model name and values.
        Outputs: none.
        Side effects: none. The call is not stored.
        Raises AssertionError. That means apply wrote after a closed binding.
        """
        raise AssertionError("approval binding wrote without a live schema")

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        """Refuse a write that passed the approval binding.

        Inputs: model name, ids, and values.
        Outputs: none.
        Side effects: none. The call is not stored.
        Raises AssertionError. That means apply wrote after a closed binding.
        """
        raise AssertionError("approval binding wrote without a live schema")


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("approval binding suite opened a socket")

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
    Side effects: none.
    """
    slice_data: dict[str, Any] = {"model": "x_ticket", "fields": list(fields)}
    slice_data.update(volatile)
    return slice_data


def _approved() -> tuple[list[dict[str, Any]], str, dict[str, Any], str]:
    """The plan, its hash, the schema slice, and that slice's fingerprint.

    Inputs: none.
    Outputs: the approved field create, the change-set fingerprint, the
    schema slice, and the schema fingerprint.
    Side effects: none.
    """
    plan = _plan()
    schema = _schema(["x_note"])
    return plan, changeset_fingerprint(plan), schema, schema_fingerprint(schema)


def test_changed_plan_hash_does_not_apply() -> None:
    """A modified plan does not apply under the original plan hash.

    The live schema still matches. The hash mismatch is enough to refuse.
    The fake port is not called and the journal stays empty.
    """
    plan, approved_hash, _schema_slice, fingerprint = _approved()
    modified = _plan("x_other")
    assert changeset_fingerprint(modified) != approved_hash
    port = FakePort()
    error = _protocol().BridgeError
    with pytest.raises(error) as caught:
        apply(
            modified,
            mode="T",
            port=port,
            approved_hash=approved_hash,
            schema_fingerprint=fingerprint,
            live_schema=_schema(["x_note"]),
        )
    assert caught.value.code == "approval_hash_mismatch"
    assert port.created == []
    assert port.writes == []
    assert get_journal() == []
    assert plan[0]["params"]["name"] == "x_note"


def test_changed_schema_fingerprint_does_not_apply() -> None:
    """A changed schema slice does not apply under the approved fingerprint.

    The plan hash still matches. The executor recomputes the live schema
    fingerprint. The fake port is not called and the journal stays empty.
    """
    plan, approved_hash, schema, fingerprint = _approved()
    changed = _schema(["x_note", "x_extra"], id=1, write_date="later")
    assert schema_fingerprint(changed) != fingerprint
    assert changeset_fingerprint(plan) == approved_hash
    port = FakePort()
    error = _protocol().BridgeError
    with pytest.raises(error) as caught:
        apply(
            plan,
            mode="T",
            port=port,
            approved_hash=approved_hash,
            schema_fingerprint=fingerprint,
            live_schema=changed,
        )
    assert caught.value.code == "schema_fingerprint_mismatch"
    assert port.created == []
    assert port.writes == []
    assert get_journal() == []
    assert schema["fields"] == ["x_note"]


def test_matching_hash_and_schema_fingerprint_may_apply() -> None:
    """A matching plan hash and schema fingerprint may apply on the fake port.

    Volatile ids on the live slice do not change the schema fingerprint.
    This apply is in memory. It is not a live approval.
    """
    plan, approved_hash, schema, fingerprint = _approved()
    live = _schema(["x_note"], id=9, write_date="later", create_date="c2")
    assert schema_fingerprint(live) == fingerprint
    assert schema_fingerprint(schema) == fingerprint
    port = FakePort()
    result = apply(
        plan,
        mode="T",
        port=port,
        approved_hash=approved_hash,
        schema_fingerprint=fingerprint,
        live_schema=live,
    )
    assert result["status"] == "VERIFIED"
    assert result["applied_count"] == 1
    assert result["plan_hash"] == approved_hash
    assert port.created == [
        (
            "ir.model.fields",
            {
                "name": "x_note",
                "model": "x_ticket",
                "field_description": "x_note",
                "ttype": "char",
            },
        )
    ]
    assert port.writes == []
    assert any(entry.get("kind") == "VERIFIED" for entry in get_journal())


def test_missing_live_schema_fails_closed() -> None:
    """A bound schema fingerprint with no live schema does not apply.

    The plan hash matches. The port raises if a write is reached, and that
    raise is not success. The journal stays empty.
    """
    plan, approved_hash, _schema_slice, fingerprint = _approved()
    port = ClosedPort()
    error = _protocol().BridgeError
    with pytest.raises(error) as caught:
        apply(
            plan,
            mode="T",
            port=port,
            approved_hash=approved_hash,
            schema_fingerprint=fingerprint,
        )
    assert caught.value.code == "schema_fingerprint_mismatch"
    assert port.created == []
    assert port.writes == []
    assert get_journal() == []
