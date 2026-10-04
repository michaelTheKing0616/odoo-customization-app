"""T8-S12. An unknown write outcome is NEEDS_HUMAN and is not verified.

``dispatch_op`` raises ``UnknownOutcome`` from ``app.changeset.executor``.
The executor appends one UNKNOWN row on the in-process journal (``_JOURNAL``)
and does not append RESULT or VERIFIED. A second ``apply`` of the same plan
returns the cached decision and does not call the port again.

``test_unknown_outcome_does_not_retry_the_write`` already covers that path,
including the stale-recovery journal. This file calls that function. It does
not keep a second copy of that journal and it does not add another journal.

There is no live read-back. A caller observation is not a read of Odoo, and
this suite does not invent one. GATE-P3-07 stays open for a live read-back.
"""

from __future__ import annotations

import importlib.util
import socket
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from app.changeset.executor import UnknownOutcome, apply, get_journal, reset_journal

pytestmark = pytest.mark.no_app_db

_UNKNOWN_TEST = Path(__file__).resolve().parents[1] / "test_executor_wal.py"
_UNKNOWN_TEST_FUNCTION = "test_unknown_outcome_does_not_retry_the_write"


class UncertainPort:
    """Port whose first create has an unknown outcome.

    A later create would succeed. A read, search, or search_read fails the
    test. This object does not read Odoo.
    """

    def __init__(self) -> None:
        self.creates = 0
        self.writes = 0
        self.reads = 0

    def create(self, model: str, values: dict[str, Any]) -> int:
        """Record one create. The first call raises ``UnknownOutcome``.

        Inputs: model name and values.
        Outputs: a local id, only when this is not the first create.
        Side effects: increments ``creates``. Does not open a socket.
        Raises UnknownOutcome on the first call.
        """
        self.creates += 1
        if self.creates == 1:
            raise UnknownOutcome()
        return self.creates

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> None:
        """Record one write and leave its outcome unknown.

        Inputs: model name, ids, and values.
        Outputs: none.
        Side effects: increments ``writes``. Does not open a socket.
        Raises UnknownOutcome.
        """
        self.writes += 1
        raise UnknownOutcome()

    def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict[str, Any]]:
        """Refuse a read-back.

        Inputs: model name, ids, and optional fields.
        Outputs: none.
        Side effects: increments ``reads``. Does not open a socket.
        Raises AssertionError. A live read-back is not part of this suite.
        """
        self.reads += 1
        raise AssertionError("unknown suite read back from a port")

    def search(self, model: str, domain: list[Any]) -> list[int]:
        """Refuse a search used as a read-back.

        Inputs: model name and domain.
        Outputs: none.
        Side effects: increments ``reads``. Does not open a socket.
        Raises AssertionError. A live read-back is not part of this suite.
        """
        self.reads += 1
        raise AssertionError("unknown suite read back from a port")

    def search_read(self, model: str, domain: list[Any], fields: list[str] | None = None) -> list[dict[str, Any]]:
        """Refuse a search_read used as a read-back.

        Inputs: model name, domain, and optional fields.
        Outputs: none.
        Side effects: increments ``reads``. Does not open a socket.
        Raises AssertionError. A live read-back is not part of this suite.
        """
        self.reads += 1
        raise AssertionError("unknown suite read back from a port")


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unknown suite opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


@pytest.fixture(autouse=True)
def _clean_journal() -> None:
    reset_journal()
    yield
    reset_journal()


def _load_unknown_outcome_test() -> ModuleType:
    """Load the existing unknown-outcome test from its file.

    Inputs: none. The path is ``tests/test_executor_wal.py``.
    Outputs: the loaded module.
    Side effects: executes that module's imports. Does not call Odoo.
    Raises FileNotFoundError when the file is missing, or ImportError when
    Python cannot load it.
    """
    if not _UNKNOWN_TEST.is_file():
        raise FileNotFoundError(_UNKNOWN_TEST)
    spec = importlib.util.spec_from_file_location(
        "ingenium_existing_unknown_outcome",
        _UNKNOWN_TEST,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_UNKNOWN_TEST}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _field() -> dict[str, Any]:
    """The field create the existing unknown-outcome test already applies.

    Inputs: none.
    Outputs: one ``field.create`` for ``x_flag`` on ``x_test.model``.
    Side effects: none.
    """
    return {
        "type": "field.create",
        "params": {"model": "x_test.model", "name": "x_flag", "field_type": "char"},
    }


def _claiming_observation() -> dict[str, Any]:
    """An observation that claims the write is verified.

    Inputs: none.
    Outputs: a dict with ``verified`` true. It is not a live read.
    Side effects: none.
    """
    return {
        "status": "VERIFIED",
        "verified": True,
        "postconditions": {"0": {"the field exists on the model": True}},
    }


def _kinds(journal: list[dict[str, Any]]) -> list[str]:
    """Kind of each journal row, in stored order.

    Inputs: journal rows from ``get_journal``.
    Outputs: the ``kind`` values.
    Side effects: none.
    """
    return [str(entry.get("kind")) for entry in journal]


def test_existing_unknown_outcome_does_not_retry_the_write() -> None:
    """Run the unknown-outcome test that already lives on the executor journal.

    Inputs: none.
    Outputs: none.
    Side effects: loads ``test_executor_wal.py`` and calls
    ``test_unknown_outcome_does_not_retry_the_write``. Does not copy its
    recovery journal and does not call Odoo.
    """
    module = _load_unknown_outcome_test()
    unknown_outcome = getattr(module, _UNKNOWN_TEST_FUNCTION, None)
    assert callable(unknown_outcome)
    unknown_outcome()


@pytest.mark.parametrize("mode", ["T", "C"])
def test_unknown_write_is_needs_human_and_not_verified(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``UnknownOutcome`` stays NEEDS_HUMAN. A success claim does not verify it.

    The port's first create raises ``UnknownOutcome``. Read methods fail if
    called. ``verify`` fails if called. The journal is the process list:
    UNKNOWN, and no RESULT, VERIFIED, or COMPENSATE row.
    """

    def _refuse_verify(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("unknown outcome called verify")

    monkeypatch.setattr("app.changeset.executor.verify", _refuse_verify)
    port = UncertainPort()
    result = apply(
        [_field()],
        mode=mode,
        port=port,
        observation=_claiming_observation(),
        model_success=True,
    )
    journal = get_journal()
    assert result["status"] == "NEEDS_HUMAN"
    assert result["status"] != "VERIFIED"
    assert result["applied_count"] == 0
    assert result["risk_bump"] == 1
    assert "verification" not in result
    assert result["report"]["results"] == []
    assert result["report"]["compensates"] == []
    assert result["report"]["missing"] == [0]
    assert _kinds(journal) == ["INTENT", "INTENT", "BEFORE", "UNKNOWN"]
    assert journal[0]["status"] == "NEEDS_HUMAN"
    assert journal[-1]["kind"] == "UNKNOWN"
    assert journal[-1]["index"] == 0
    assert journal[-1]["type"] == "field.create"
    assert not any(entry.get("kind") == "RESULT" for entry in journal)
    assert not any(entry.get("kind") == "VERIFIED" for entry in journal)
    assert not any(entry.get("kind") == "COMPENSATE" for entry in journal)
    assert port.creates == 1
    assert port.writes == 0
    assert port.reads == 0


@pytest.mark.parametrize("mode", ["T", "C"])
def test_second_apply_does_not_call_the_port(mode: str) -> None:
    """The second apply returns the same decision and does not touch the port.

    The port would accept a second create. That call does not happen. The
    process journal is unchanged. No read-back method runs.
    """
    port = UncertainPort()
    plan = [_field()]
    first = apply(plan, mode=mode, port=port)
    journal_after_first = get_journal()
    second = apply(plan, mode=mode, port=port)
    assert first["status"] == "NEEDS_HUMAN"
    assert second["status"] == "NEEDS_HUMAN"
    assert second["status"] != "VERIFIED"
    assert first["applied_count"] == 0
    assert second["applied_count"] == 0
    assert second["plan_hash"] == first["plan_hash"]
    assert "verification" not in first
    assert "verification" not in second
    assert port.creates == 1
    assert port.writes == 0
    assert port.reads == 0
    assert get_journal() == journal_after_first
    assert any(entry.get("kind") == "UNKNOWN" for entry in get_journal())
    assert not any(entry.get("kind") == "RESULT" for entry in get_journal())
    assert not any(entry.get("kind") == "VERIFIED" for entry in get_journal())


def test_forged_verified_row_does_not_verify_and_there_is_no_read_back() -> None:
    """A copied VERIFIED row does not verify the run. GATE-P3-07 stays open.

    The record is the process list from ``get_journal``. This test does not
    write another journal and does not read Odoo back.
    """
    port = UncertainPort()
    result = apply([_field()], mode="T", port=port)
    journal = get_journal()
    assert result["status"] == "NEEDS_HUMAN"
    assert result["status"] != "VERIFIED"
    assert isinstance(journal, list)
    assert journal
    assert "journal_entry_id" not in result
    forged = list(journal)
    forged.append({"kind": "VERIFIED", "run_id": "forged"})
    assert not any(entry.get("kind") == "VERIFIED" for entry in get_journal())
    assert get_journal() == journal
    assert port.reads == 0
    assert port.creates == 1
