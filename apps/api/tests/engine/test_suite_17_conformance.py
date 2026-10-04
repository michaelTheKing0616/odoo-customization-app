"""T8-S17. Provider conformance is C01 through C20.

``test_conformance_suite_passes_every_gate_case`` in
``tests/test_llm_gateway_phase1.py`` runs those cases on the scripted
adapter. This module calls that function. It does not copy the cases.

The existing suite passes on synthetic fixtures. The replay files under
``tests/fixtures/llm_gateway/`` are labeled synthetic replay and
``recorded_from_live_provider`` is false. That pass is not a live
operator recording.

Live operator recordings are still missing for C07, C08, C10, C11, C13,
C14, C16, C17, C18, C19, and OpenAI C20. GATE-P1-02 stays open. A missing
recording is not marked passed.

This module does not call a live model and does not invent a cassette,
a recording, or a fixture body.
"""

from __future__ import annotations

import importlib.util
import json
import socket
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = pytest.mark.no_app_db

_TESTS = Path(__file__).resolve().parents[1]
_GATE_CASES = _TESTS / "test_llm_gateway_phase1.py"
_FIXTURES = _TESTS / "fixtures" / "llm_gateway"
_GATE_FUNCTION = "test_conformance_suite_passes_every_gate_case"

PROVIDER_CONFORMANCE_IDS = tuple(f"C{index:02d}" for index in range(1, 21))
MISSING_LIVE_RECORDING_IDS = frozenset(
    {
        "C07",
        "C08",
        "C10",
        "C11",
        "C13",
        "C14",
        "C16",
        "C17",
        "C18",
        "C19",
    }
)
MISSING_OPENAI_LIVE_RECORDING_IDS = frozenset({"C20"})
GATE_P1_02 = "open"
_FAMILIES = ("anthropic", "gemini", "openai")


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("conformance suite opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


def _load_module(path: Path, module_name: str) -> ModuleType:
    """Load one existing test module from its file.

    Inputs: the file path and a unique module name.
    Outputs: the loaded module.
    Side effects: executes that module's imports. Does not call a live
    model and does not write a cassette.
    Raises FileNotFoundError when the file is missing, or ImportError when
    Python cannot load it.
    """
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(module: ModuleType, name: str) -> None:
    """Call one existing test function by name.

    Inputs: the loaded module and the function name.
    Outputs: none.
    Side effects: runs that function. Does not copy its body.
    Raises AssertionError when the name is missing or not callable.
    """
    function = getattr(module, name, None)
    assert callable(function), name
    function()


def _is_missing_live_recording(case_id: str, provider: str) -> bool:
    """Whether this provider still has no live operator recording for the case.

    Inputs: a conformance id and a provider family name.
    Outputs: True for C07, C08, C10, C11, C13, C14, C16, C17, C18, and C19
    on every family, and for OpenAI C20.
    Side effects: none.
    """
    if case_id in MISSING_LIVE_RECORDING_IDS:
        return True
    return provider == "openai" and case_id in MISSING_OPENAI_LIVE_RECORDING_IDS


def live_recording_status(case_id: str, *, provider: str) -> str:
    """Report the live-recording status this suite is allowed to store.

    Inputs: a conformance id and a provider family name.
    Outputs: ``"missing"`` when the live operator recording is locked open.
    Any other id returns ``"unrecorded"``. This function never returns
    ``"pass"``.
    Side effects: none. Does not read a fixture body and does not call a model.
    """
    if _is_missing_live_recording(case_id, provider):
        return "missing"
    return "unrecorded"


def reject_live_pass(case_id: str, *, provider: str, claimed: str) -> None:
    """Refuse to store a pass for a missing live recording.

    Inputs: a conformance id, the provider family, and the status a caller
    tried to store.
    Outputs: none.
    Side effects: none. Does not mark GATE-P1-02 closed and does not write
    a cassette.
    Raises AssertionError when ``claimed`` is a pass for a locked id.
    """
    if claimed == "pass" and _is_missing_live_recording(case_id, provider):
        raise AssertionError(
            f"missing live recording {provider} {case_id} is not a pass"
        )


def _synthetic_fixtures() -> dict[str, dict[str, Any]]:
    """Read the existing replay files and their case ids.

    Inputs: none. The directory is ``tests/fixtures/llm_gateway``.
    Outputs: payload by family name. Each payload is the JSON already on disk.
    Side effects: reads those files. Does not write a fixture and does not
    call a model.
    Raises FileNotFoundError when the directory has no JSON files.
    """
    paths = sorted(path for path in _FIXTURES.glob("*.json") if path.is_file())
    if not paths:
        raise FileNotFoundError(_FIXTURES)
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in paths
    }


def test_provider_conformance_is_c01_through_c20() -> None:
    """The provider set is C01–C20, and the locked ids sit inside it.

    Inputs: none.
    Outputs: none.
    Side effects: none. Does not copy a gate case and does not call a model.
    """
    assert PROVIDER_CONFORMANCE_IDS == tuple(f"C{index:02d}" for index in range(1, 21))
    assert len(PROVIDER_CONFORMANCE_IDS) == 20
    assert MISSING_LIVE_RECORDING_IDS <= set(PROVIDER_CONFORMANCE_IDS)
    assert MISSING_OPENAI_LIVE_RECORDING_IDS <= set(PROVIDER_CONFORMANCE_IDS)
    assert GATE_P1_02 == "open"


def test_existing_gate_cases_pass_on_synthetic_fixtures() -> None:
    """Call the suite that already runs C01–C20 on the scripted adapter.

    Inputs: none.
    Outputs: none.
    Side effects: loads ``tests/test_llm_gateway_phase1.py`` and calls
    ``test_conformance_suite_passes_every_gate_case``. Does not copy those
    cases, does not call a live model, and does not write a cassette.
    """
    module = _load_module(_GATE_CASES, "ingenium_existing_conformance_gate")
    _call(module, _GATE_FUNCTION)


def test_synthetic_fixtures_leave_the_locked_recordings_missing() -> None:
    """The replay files are synthetic, and the locked ids are not live passes.

    Inputs: the JSON files already under ``tests/fixtures/llm_gateway``.
    Outputs: none.
    Side effects: reads those files. Does not invent a body, does not mark
    a missing recording passed, and does not call a model.
    """
    payloads = _synthetic_fixtures()
    assert set(payloads) == set(_FAMILIES)
    assert GATE_P1_02 == "open"
    for family, payload in payloads.items():
        assert payload["label"] == "synthetic replay"
        assert payload["provenance"] == "synthetic_replay"
        assert payload["recorded_from_live_provider"] is False
        present = set(payload["cases"])
        assert present.isdisjoint(MISSING_LIVE_RECORDING_IDS)
        if family == "openai":
            assert "C20" not in present
        for case_id in present:
            assert live_recording_status(case_id, provider=family) != "pass"
    for case_id in MISSING_LIVE_RECORDING_IDS:
        for family in _FAMILIES:
            assert live_recording_status(case_id, provider=family) == "missing"
    assert live_recording_status("C20", provider="openai") == "missing"
    assert live_recording_status("C20", provider="anthropic") != "pass"
    assert live_recording_status("C20", provider="gemini") != "pass"


def test_a_claimed_pass_for_a_missing_recording_fails_closed() -> None:
    """A forged pass does not close GATE-P1-02.

    Inputs: a claimed ``"pass"`` for each locked id.
    Outputs: none.
    Side effects: none. The gate constant stays ``"open"``. Does not write
    a cassette and does not call a model.
    """
    assert GATE_P1_02 == "open"
    for case_id in sorted(MISSING_LIVE_RECORDING_IDS):
        for family in _FAMILIES:
            with pytest.raises(AssertionError, match="missing live recording"):
                reject_live_pass(case_id, provider=family, claimed="pass")
    with pytest.raises(AssertionError, match="missing live recording"):
        reject_live_pass("C20", provider="openai", claimed="pass")
    assert GATE_P1_02 == "open"
    assert live_recording_status("C07", provider="openai") == "missing"
    assert live_recording_status("C20", provider="openai") == "missing"
