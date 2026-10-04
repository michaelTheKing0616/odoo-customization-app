"""T8-S16. Redaction and privacy on the in-process path.

A log line, the audit chain, and a trace must not keep a secret.
``test_redaction`` in ``tests/test_audit_chain.py`` already redacts
sensitive chain keys through ``redact_payload``. ``test_scrub_removes_exact_secrets_and_key_shapes``
in ``tests/test_llm_gateway_phase1.py`` already removes exact secrets and
``sk-`` / Bearer shapes through ``scrub``. This module calls those functions.
It does not copy a second scrubber.

A log line, a chain payload, and a trace that contain the fake secret are
scrubbed with those same functions. The raw secret is absent from the stored
text. The store refuses text that still contains it.

This module does not probe Odoo and does not log a real secret.
"""

from __future__ import annotations

import importlib.util
import json
import socket
from pathlib import Path
from types import ModuleType

import pytest

from app.audit_chain import redact_payload
from app.llm_gateway.scrub import scrub

pytestmark = pytest.mark.no_app_db

_TESTS = Path(__file__).resolve().parents[1]
_AUDIT_CHAIN = _TESTS / "test_audit_chain.py"
_GATEWAY = _TESTS / "test_llm_gateway_phase1.py"

_REDACTION = "test_redaction"
_SCRUB_SHAPES = "test_scrub_removes_exact_secrets_and_key_shapes"

# Fake marker only. Not a credential.
_FAKE_SECRET = "sk-test-redaction-marker"


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("redaction suite opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


def _load_module(path: Path, module_name: str) -> ModuleType:
    """Load one existing test module from its file.

    Inputs: the file path and a unique module name.
    Outputs: the loaded module.
    Side effects: executes that module's imports. Does not call Odoo and
    does not log a secret.
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


def _store(kind: str, text: str, bucket: dict[str, str]) -> None:
    """Keep text only when the fake secret is already gone.

    Inputs: the store kind, the candidate text, and the in-memory bucket.
    Outputs: none. The bucket gains ``kind`` when the text is clean.
    Side effects: writes one string into ``bucket``. Does not log.
    Raises AssertionError when the fake secret is still present. That refusal
    is the fail-closed gate: raw secret text is not stored.
    """
    if _FAKE_SECRET in text:
        raise AssertionError(f"refusing to store a raw secret in {kind}")
    bucket[kind] = text


def test_existing_redaction_and_scrub() -> None:
    """Call the tests that already redact chain keys and scrub secret shapes.

    Inputs: none.
    Outputs: none.
    Side effects: loads ``test_audit_chain.py`` and ``test_llm_gateway_phase1.py``,
    then calls ``test_redaction`` and ``test_scrub_removes_exact_secrets_and_key_shapes``.
    Does not copy those checks, does not probe Odoo, and does not log a secret.
    """
    audit = _load_module(_AUDIT_CHAIN, "ingenium_existing_audit_chain_redaction")
    gateway = _load_module(_GATEWAY, "ingenium_existing_gateway_scrub")
    _call(audit, _REDACTION)
    _call(gateway, _SCRUB_SHAPES)


def test_fake_secret_is_absent_from_stored_log_chain_and_trace() -> None:
    """Scrub a log line, a chain payload, and a trace before they are stored.

    Inputs: one log line, one chain payload, and one trace. Each contains
    the fake marker ``sk-test-redaction-marker``. The chain payload also
    puts that marker under ``api_key``, which ``redact_payload`` redacts by
    key. The free-text fields still need ``scrub``.
    Outputs: none.
    Side effects: calls ``redact_payload`` and ``scrub``. Writes only the
    scrubbed strings into an in-memory bucket. Does not copy a scrubber,
    does not probe Odoo, and does not log the marker.
    """
    log_line = f"operator note {_FAKE_SECRET}"
    chain_payload = {
        "note": f"chain {_FAKE_SECRET}",
        "api_key": _FAKE_SECRET,
    }
    trace = f"phase_changed detail={_FAKE_SECRET}"

    assert _FAKE_SECRET in log_line
    assert _FAKE_SECRET in json.dumps(chain_payload)
    assert _FAKE_SECRET in trace

    redacted = redact_payload(chain_payload)
    assert redacted["api_key"] == "[redacted]"
    assert _FAKE_SECRET in str(redacted["note"])

    stored: dict[str, str] = {}
    _store("log", scrub(log_line, [_FAKE_SECRET]), stored)
    _store(
        "chain",
        scrub(json.dumps(redacted, sort_keys=True), [_FAKE_SECRET]),
        stored,
    )
    _store("trace", scrub(trace, [_FAKE_SECRET]), stored)

    stored_text = "\n".join(stored[kind] for kind in ("log", "chain", "trace"))
    assert _FAKE_SECRET not in stored_text
    assert "operator note" in stored["log"]
    assert "phase_changed" in stored["trace"]
    assert "[redacted]" in stored["log"]
    assert "[redacted]" in stored["chain"]
    assert "[redacted]" in stored["trace"]
    with pytest.raises(AssertionError, match="refusing to store a raw secret"):
        _store("log", log_line, stored)
