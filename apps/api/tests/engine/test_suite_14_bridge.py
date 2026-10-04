"""T8-S14. Bridge refusals on the in-process path.

Unknown ops, prohibited ops, and in-place DDL are already refused by
``test_apply_refuses_unknown_prohibited_and_inplace_ddl``. The kill switch
and the protocol gate are already refused by
``test_kill_switch_protocol_and_escalation_refuse_before_work``. Both
functions live in ``tests/test_bridge_protocol.py``. This module calls
them. The fail-closed case uses ``InMemoryBridge`` from
``app.bridge.memory``. This module does not define another bridge.

A non-DDL dry-run leaves the checksum of the in-memory records unchanged.
An in-place DDL apply does not write. A killed bridge does not write.

A live savepoint and a live kill switch have not run on Odoo. GATE-P2-08
and GATE-P2-09 stay open for those. This module does not probe Odoo.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import socket
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from app.bridge.memory import InMemoryBridge, load_protocol

pytestmark = pytest.mark.no_app_db

_PROTOCOL_TESTS = Path(__file__).resolve().parents[1] / "test_bridge_protocol.py"
_REFUSE_APPLY = "test_apply_refuses_unknown_prohibited_and_inplace_ddl"
_REFUSE_GATE = "test_kill_switch_protocol_and_escalation_refuse_before_work"

_NON_DDL = {
    "type": "view.inherit.create",
    "risk": "R1",
    "ddl": False,
    "params": {"anchor": "name"},
}
_DDL = {"type": "field.create", "risk": "R2", "ddl": True}


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("bridge suite opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


def _load_bridge_protocol_tests() -> ModuleType:
    """Load the existing bridge-protocol tests from their file.

    Inputs: none. The path is ``tests/test_bridge_protocol.py``.
    Outputs: the loaded module.
    Side effects: executes that module's imports. Does not call Odoo.
    Raises FileNotFoundError when the file is missing, or ImportError when
    Python cannot load it.
    """
    if not _PROTOCOL_TESTS.is_file():
        raise FileNotFoundError(_PROTOCOL_TESTS)
    spec = importlib.util.spec_from_file_location(
        "ingenium_existing_bridge_protocol",
        _PROTOCOL_TESTS,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_PROTOCOL_TESTS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _records_checksum(records: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON of the in-memory records.

    Inputs: the bridge ``records`` dict.
    Outputs: a hex digest. This is not an Odoo module hash.
    Side effects: none.
    """
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _seeded_bridge(**kwargs: object) -> InMemoryBridge:
    """An existing in-memory bridge with one stored row.

    Inputs: keyword arguments forwarded to ``InMemoryBridge``.
    Outputs: a bridge whose ``records`` are ``{"applied": ["existing"]}``.
    Side effects: none. Does not open a socket and does not call Odoo.
    """
    bridge = InMemoryBridge(**kwargs)
    bridge.records["applied"] = ["existing"]
    return bridge


def _assert_unwritten(bridge: InMemoryBridge, checksum: str) -> None:
    """The bridge still holds the seeded row and did not open a transaction.

    Inputs: the bridge and the checksum taken before the refused call.
    Outputs: none.
    Side effects: none.
    Raises AssertionError when the records changed, a transaction opened,
    or the outbound spy recorded a URL.
    """
    assert bridge.records == {"applied": ["existing"]}
    assert _records_checksum(bridge.records) == checksum
    assert bridge.transactions_opened == 0
    assert bridge.transactions_committed == 0
    assert bridge.outbound.urls == []
    assert bridge.savepoints_rolled_back == 0


def test_existing_bridge_protocol_refusals() -> None:
    """Call the protocol tests that already refuse a bad op and a closed gate.

    Inputs: none.
    Outputs: none.
    Side effects: loads ``test_bridge_protocol.py`` and calls
    ``test_apply_refuses_unknown_prohibited_and_inplace_ddl`` and
    ``test_kill_switch_protocol_and_escalation_refuse_before_work``.
    Does not copy those checks and does not call Odoo.
    """
    module = _load_bridge_protocol_tests()
    refuse_apply = getattr(module, _REFUSE_APPLY, None)
    refuse_gate = getattr(module, _REFUSE_GATE, None)
    assert callable(refuse_apply)
    assert callable(refuse_gate)
    refuse_apply()
    refuse_gate()


def test_inplace_ddl_apply_and_killed_bridge_do_not_write() -> None:
    """A dry-run checksum holds, in-place DDL does not write, and a kill does not write.

    The bridge is ``InMemoryBridge``. A non-DDL dry-run reports zero writes
    and leaves the record checksum unchanged. A DDL dry-run raises
    ``ddl_no_inplace``. An apply of that DDL op without a neutralized clone
    raises ``review_only``. A bridge whose ``ingenium.bridge.enabled`` param
    is ``0`` raises ``kill_switch``. Each refused call leaves the seeded row
    in place.

    This in-memory counter is not a live savepoint, and this param is not a
    live kill switch on Odoo. GATE-P2-08 and GATE-P2-09 stay open.
    """
    protocol = load_protocol()
    error = protocol.BridgeError

    dry = _seeded_bridge()
    before = _records_checksum(dry.records)
    result = dry.apply_changeset(
        [_NON_DDL],
        mode="dry_run",
        environment="production",
        neutralized_clone=False,
        max_risk="R2",
    )
    assert result["status"] == "dry_run"
    assert result["writes"] == 0
    assert result["rolled_back"] is True
    assert result["copied_database"] is False
    assert _records_checksum(dry.records) == before
    assert dry.records == {"applied": ["existing"]}
    assert dry.transactions_committed == 0
    assert dry.outbound.urls == []
    assert dry.savepoints_rolled_back == 0

    inplace_dry = _seeded_bridge()
    dry_checksum = _records_checksum(inplace_dry.records)
    with pytest.raises(error) as ddl_dry:
        inplace_dry.apply_changeset(
            [_DDL],
            mode="dry_run",
            environment="production",
            neutralized_clone=True,
            max_risk="R3",
        )
    assert ddl_dry.value.code == "ddl_no_inplace"
    _assert_unwritten(inplace_dry, dry_checksum)

    inplace_apply = _seeded_bridge()
    apply_checksum = _records_checksum(inplace_apply.records)
    with pytest.raises(error) as ddl_apply:
        inplace_apply.apply_changeset(
            [_DDL],
            mode="apply",
            environment="production",
            neutralized_clone=False,
            max_risk="R3",
        )
    assert ddl_apply.value.code == "review_only"
    _assert_unwritten(inplace_apply, apply_checksum)

    killed = _seeded_bridge(params={"ingenium.bridge.enabled": "0"})
    killed_checksum = _records_checksum(killed.records)
    with pytest.raises(error) as dead:
        killed.apply_changeset(
            [_NON_DDL],
            mode="apply",
            environment="production",
            neutralized_clone=True,
            max_risk="R2",
        )
    assert dead.value.code == "kill_switch"
    _assert_unwritten(killed, killed_checksum)
