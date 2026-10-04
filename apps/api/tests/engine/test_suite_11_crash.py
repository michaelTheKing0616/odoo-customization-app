"""T8-S11. Crash injection at the journal boundaries the executor already has.

``apply(..., fail_at=index)`` aborts after that op's INTENT row and BEFORE
row, and before its write. Earlier indexes already have a RESULT. A partial
apply is not reported as VERIFIED. Mode T drops every RESULT row for the
run. Mode C appends COMPENSATE rows from the last applied index backward,
and only for ops the executor already accepted. An irreversible Mode C op
raises before any journal row.

The journal is still the in-process list (``_JOURNAL``). This module does
not recover a process kill from Postgres and does not invent a durable
write. GATE-P3-03 stays open. The crash matrix stays in
``tests/test_plan_card_recovery.py``. This file calls that function. It
does not keep a second copy of its journal.
"""

from __future__ import annotations

import importlib.util
import socket
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from app.changeset.executor import _protocol, apply, get_journal, reset_journal
from app.changeset.ops import get_op

pytestmark = pytest.mark.no_app_db

_CRASH_MATRIX = Path(__file__).resolve().parents[1] / "test_plan_card_recovery.py"
_CRASH_MATRIX_FUNCTION = "test_crash_matrix_never_reports_a_partial_apply_as_verified"
_PLAN_NAMES = ("x_one", "x_two", "x_three")


class FakePort:
    """In-memory create and write log. It has no rollback and no inverse."""

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


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("crash suite opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


@pytest.fixture(autouse=True)
def _clean_journal() -> None:
    reset_journal()
    yield
    reset_journal()


def _load_crash_matrix() -> ModuleType:
    """Load the existing crash-matrix module from its file.

    Inputs: none. The path is ``tests/test_plan_card_recovery.py``.
    Outputs: the loaded module.
    Side effects: executes that module's imports. Does not call Odoo.
    Raises FileNotFoundError when the file is missing, or ImportError when
    Python cannot load it.
    """
    if not _CRASH_MATRIX.is_file():
        raise FileNotFoundError(_CRASH_MATRIX)
    spec = importlib.util.spec_from_file_location(
        "ingenium_existing_crash_matrix",
        _CRASH_MATRIX,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_CRASH_MATRIX}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _field(name: str) -> dict[str, Any]:
    """One custom field create.

    Inputs: field name. It must already start with ``x_``.
    Outputs: a ``field.create`` op on ``x_test.model``.
    Side effects: none.
    """
    return {
        "type": "field.create",
        "params": {"model": "x_test.model", "name": name, "field_type": "char"},
    }


def _plan() -> list[dict[str, Any]]:
    """Three reversible field creates, in apply order.

    Inputs: none.
    Outputs: ``x_one``, ``x_two``, ``x_three``.
    Side effects: none.
    """
    return [_field(name) for name in _PLAN_NAMES]


def _kinds(journal: list[dict[str, Any]], kind: str, index: int | None = None) -> list[dict[str, Any]]:
    """Journal rows of one kind, in stored order.

    Inputs: journal rows, a kind name, and an optional op index.
    Outputs: the matching rows. A run INTENT has no index, so an index
    filter skips it.
    Side effects: none.
    """
    rows = [entry for entry in journal if entry.get("kind") == kind]
    if index is None:
        return rows
    return [entry for entry in rows if entry.get("index") == index]


def _position(journal: list[dict[str, Any]], kind: str, index: int) -> int:
    """Index of one journal row in the stored list.

    Inputs: journal rows, a kind name, and an op index.
    Outputs: the first matching position.
    Side effects: none.
    Raises AssertionError when that row is missing.
    """
    for position, entry in enumerate(journal):
        if entry.get("kind") == kind and entry.get("index") == index:
            return position
    raise AssertionError(f"missing {kind} at {index}")


def _created_names(port: FakePort) -> list[str]:
    """Field names stored on the fake, in create order.

    Inputs: the fake port.
    Outputs: ``name`` from each stored create.
    Side effects: none.
    """
    return [str(values.get("name")) for _model, values in port.created]


def _crash(mode: str, fail_at: int) -> tuple[dict[str, Any], list[dict[str, Any]], FakePort]:
    """Apply the three-field plan and stop at one existing executor boundary.

    Inputs: mode ``T`` or ``C``, and the op index passed to ``fail_at``.
    Outputs: the apply result, the in-process journal, and the fake port.
    Side effects: clears the process journal, then ``apply`` appends rows
    to that same list. Does not call Odoo and does not write Postgres.
    """
    reset_journal()
    port = FakePort()
    result = apply(_plan(), mode=mode, fail_at=fail_at, port=port)
    return result, get_journal(), port


def test_existing_crash_matrix_never_reports_a_partial_apply_as_verified() -> None:
    """Run the crash matrix that already lives in the plan-card tests.

    Inputs: none.
    Outputs: none.
    Side effects: loads ``test_plan_card_recovery.py`` and calls
    ``test_crash_matrix_never_reports_a_partial_apply_as_verified``.
    Does not copy its journal builder and does not call Odoo.
    """
    module = _load_crash_matrix()
    crash_matrix = getattr(module, _CRASH_MATRIX_FUNCTION, None)
    assert callable(crash_matrix)
    crash_matrix()


def test_crash_before_write_after_intent_and_before_is_not_verified() -> None:
    """``fail_at=0`` stops after INTENT and BEFORE, before any write.

    Both modes leave the killed index as INTENT then BEFORE. The port
    has no create. The run is not verified. Mode T has no RESULT row.
    Mode C has nothing applied, so it appends no COMPENSATE row.
    """
    for mode in ("T", "C"):
        result, journal, port = _crash(mode, 0)
        killed = [entry.get("kind") for entry in journal if entry.get("index") == 0]
        assert killed == ["INTENT", "BEFORE"]
        assert _kinds(journal, "RESULT") == []
        assert _kinds(journal, "RESULT", 0) == []
        assert _kinds(journal, "VERIFIED") == []
        assert _kinds(journal, "COMPENSATE") == []
        assert result["status"] == "ROLLED_BACK"
        assert result["status"] != "VERIFIED"
        assert result["status"] != "APPLIED"
        assert result["applied_count"] == 0
        assert result["report"]["missing"] == [0, 1, 2]
        assert _created_names(port) == []
        assert port.writes == []
        if mode == "T":
            assert result["risk_bump"] == 0
        else:
            assert result["risk_bump"] == 1


def test_crash_after_a_partial_result_is_not_verified() -> None:
    """A crash after one or two RESULT rows is not reported as verified.

    ``fail_at`` is the first index that has INTENT and BEFORE and no write.
    Earlier indexes were written. Mode T then clears every RESULT row.
    Mode C keeps those RESULT rows and compensates them in reverse.
    The killed index and anything after it stay off the port.
    """
    for mode in ("T", "C"):
        for fail_at in (1, 2):
            result, journal, port = _crash(mode, fail_at)
            killed = [entry.get("kind") for entry in journal if entry.get("index") == fail_at]
            assert killed == ["INTENT", "BEFORE"]
            assert _kinds(journal, "RESULT", fail_at) == []
            assert _kinds(journal, "VERIFIED") == []
            assert result["status"] == "ROLLED_BACK"
            assert result["status"] != "VERIFIED"
            assert result["applied_count"] == 0
            assert _created_names(port) == list(_PLAN_NAMES[:fail_at])
            assert _PLAN_NAMES[fail_at] not in _created_names(port)
            assert port.writes == []
            if mode == "T":
                assert _kinds(journal, "RESULT") == []
                assert _kinds(journal, "COMPENSATE") == []
                assert result["risk_bump"] == 0
                assert result["report"]["results"] == []
                assert result["report"]["compensates"] == []
            else:
                applied = list(range(fail_at))
                results = _kinds(journal, "RESULT")
                compensations = _kinds(journal, "COMPENSATE")
                assert [entry["index"] for entry in results] == applied
                assert [entry["index"] for entry in compensations] == list(reversed(applied))
                assert result["risk_bump"] == 1
                assert result["report"]["compensates"] == list(reversed(applied))
                result_at = _position(journal, "RESULT", fail_at - 1)
                intent_at = _position(journal, "INTENT", fail_at)
                before_at = _position(journal, "BEFORE", fail_at)
                assert result_at < intent_at < before_at


def test_mode_c_compensates_backward_only_for_reversible_ops() -> None:
    """Mode C compensates the applied prefix from the last index backward.

    Each compensated op is a catalog op the executor already allowed
    through. ``field.create`` is reversible ``E``. The index that crashed
    before its write is not compensated. An op with reversible ``N`` is
    not in the compensate list.
    """
    result, journal, port = _crash("C", 2)
    compensations = _kinds(journal, "COMPENSATE")
    results = _kinds(journal, "RESULT")
    assert result["status"] == "ROLLED_BACK"
    assert result["status"] != "VERIFIED"
    assert [entry["index"] for entry in compensations] == [1, 0]
    assert [entry["index"] for entry in compensations] == list(
        reversed([entry["index"] for entry in results])
    )
    assert [entry.get("type") for entry in compensations] == ["field.create", "field.create"]
    for entry in results:
        recorded = entry.get("reversible")
        catalog = get_op(str(entry.get("type")))
        assert catalog is not None
        assert recorded == catalog.reversible
        assert recorded != "N"
    for entry in compensations:
        catalog = get_op(str(entry.get("type")))
        assert catalog is not None
        assert catalog.reversible != "N"
    assert _kinds(journal, "COMPENSATE", 2) == []
    assert _created_names(port) == ["x_one", "x_two"]
    assert "x_three" not in _created_names(port)


def test_mode_c_irreversible_failure_stays_closed() -> None:
    """Mode C refuses an irreversible op before a journal row or a port call.

    A plan that starts with a reversible field create and then a
    ``data.merge`` is refused the same way. The field create is not written.
    """
    error = _protocol().BridgeError
    irreversible = {"type": "data.merge", "params": {"model": "res.partner"}}
    catalog = get_op("data.merge")
    assert catalog is not None
    assert catalog.reversible == "N"

    port = FakePort()
    with pytest.raises(error) as alone:
        apply([irreversible], mode="C", port=port)
    assert alone.value.code == "mode_c_irreversible"
    assert port.created == []
    assert port.writes == []
    assert get_journal() == []

    reset_journal()
    mixed = FakePort()
    with pytest.raises(error) as prefixed:
        apply([_field("x_one"), irreversible], mode="C", fail_at=1, port=mixed)
    assert prefixed.value.code == "mode_c_irreversible"
    assert mixed.created == []
    assert mixed.writes == []
    assert get_journal() == []


def test_a_finished_plan_is_verified_and_a_crash_of_that_plan_is_not() -> None:
    """The same plan is verified only when every op finishes.

    Inputs: the three-field plan, once with no ``fail_at`` and once stopped
    after the first RESULT.
    Outputs: none.
    Side effects: two in-memory applies. Does not call Odoo.
    """
    reset_journal()
    port = FakePort()
    finished = apply(_plan(), mode="T", port=port)
    assert finished["status"] == "VERIFIED"
    assert finished["applied_count"] == 3
    assert _kinds(get_journal(), "VERIFIED")
    assert _created_names(port) == list(_PLAN_NAMES)

    crashed, journal, crashed_port = _crash("T", 1)
    assert crashed["status"] != "VERIFIED"
    assert _kinds(journal, "VERIFIED") == []
    assert _created_names(crashed_port) == ["x_one"]


def test_journal_is_the_in_process_list_and_gate_p3_03_stays_open() -> None:
    """The crash record is the process list. Reset drops it.

    Appending VERIFIED onto the copy from ``get_journal`` does not verify
    the run. This is not recovery after a process kill, and it does not
    write a durable journal row. GATE-P3-03 stays open.
    """
    result, journal, _port = _crash("C", 1)
    assert result["status"] != "VERIFIED"
    assert isinstance(journal, list)
    assert journal
    assert "journal_entry_id" not in result
    forged = list(journal)
    forged.append({"kind": "VERIFIED", "run_id": "forged"})
    assert _kinds(get_journal(), "VERIFIED") == []
    assert get_journal() == journal
    reset_journal()
    assert get_journal() == []
    assert journal
