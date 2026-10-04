"""T8-S18. SSRF, the scrubber, cross-tenant scope, and IDOR.

``test_ssrf_blocks_https_link_local_public_http_and_cgnat`` in
``tests/test_llm_gateway_phase1.py`` already rejects those base URLs
through ``guard_base_url``. ``test_other_connection_is_not_found`` in
``tests/test_changeset_inbox.py`` already refuses another connection
through ``Inbox.decide``. This module calls those functions. It does
not copy a second checker.

One SSRF target is blocked before a request. Another connection's
record is not found. A fake secret passed to ``scrub`` does not remain
in the stored text.

GATE-P3-01 is not closed. Suites 1 through 18 existing as files is not
that gate.

This module does not open a socket and does not log a real secret.
"""

from __future__ import annotations

import importlib.util
import socket
from pathlib import Path
from types import ModuleType

import pytest

from app.changeset.inbox import Inbox, InboxError
from app.llm_gateway.scrub import scrub
from app.llm_gateway.ssrf import SsrfRejected, guard_base_url

pytestmark = pytest.mark.no_app_db

_TESTS = Path(__file__).resolve().parents[1]
_ENGINE = Path(__file__).resolve().parent
_GATEWAY = _TESTS / "test_llm_gateway_phase1.py"
_INBOX = _TESTS / "test_changeset_inbox.py"

_SSRF = "test_ssrf_blocks_https_link_local_public_http_and_cgnat"
_OTHER_CONNECTION = "test_other_connection_is_not_found"

# File presence is recorded here and is not a pass for the gate.
GATE_P3_01 = "open"
_SUITE_PREFIXES = tuple(f"test_suite_{index:02d}_" for index in range(1, 19))

# Fake marker only. Not a credential.
_FAKE_SECRET = "sk-test-boundary-marker"

# Link-local metadata address. Resolved only by the stub below.
_BLOCKED_URL = "https://169.254.169.254/latest"
_BLOCKED_ADDRESS = "169.254.169.254"


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("boundary suite opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


def _load_module(path: Path, module_name: str) -> ModuleType:
    """Load one existing test module from its file.

    Inputs: the file path and a unique module name.
    Outputs: the loaded module.
    Side effects: executes that module's imports. Does not call Odoo and
    does not open a socket.
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


def _field() -> dict:
    """One field op the existing inbox test already submits.

    Inputs: none.
    Outputs: a ``field.create`` payload for ``x_m``.
    Side effects: none.
    """
    return {"type": "field.create", "params": {"model": "x_m", "name": "x_note"}}


def test_existing_ssrf_and_other_connection() -> None:
    """Call the tests that already block SSRF targets and other connections.

    Inputs: none.
    Outputs: none.
    Side effects: loads ``test_llm_gateway_phase1.py`` and
    ``test_changeset_inbox.py``, then calls
    ``test_ssrf_blocks_https_link_local_public_http_and_cgnat`` and
    ``test_other_connection_is_not_found``. Does not copy those checks.
    Does not open a socket. GATE-P3-01 stays open.
    """
    gateway = _load_module(_GATEWAY, "ingenium_existing_ssrf_guard")
    inbox = _load_module(_INBOX, "ingenium_existing_inbox_scope")
    _call(gateway, _SSRF)
    _call(inbox, _OTHER_CONNECTION)
    assert GATE_P3_01 == "open"


def test_ssrf_target_is_blocked_before_a_request() -> None:
    """A link-local base URL never reaches the request function.

    Inputs: ``https://169.254.169.254/latest`` and a resolve stub that
    returns that address. The request function records a URL and is the
    only place a request would start.
    Outputs: none.
    Side effects: calls ``guard_base_url`` and ``scrub``. Writes the scrubbed
    attempt into an in-memory bucket. Does not copy the SSRF checker, does
    not open a socket, and does not log the fake secret.
    """
    requested: list[str] = []

    def send_request(url: str) -> None:
        requested.append(url)
        raise AssertionError("SSRF target reached a request")

    with pytest.raises(SsrfRejected, match="blocked") as blocked:
        host = guard_base_url(
            _BLOCKED_URL,
            resolve=lambda _host: [_BLOCKED_ADDRESS],
        )
        send_request(f"https://{host}/latest")
    assert requested == []
    assert _BLOCKED_ADDRESS in str(blocked.value)

    attempt = f"ssrf blocked {_FAKE_SECRET} {_BLOCKED_URL}"
    assert _FAKE_SECRET in attempt
    stored: dict[str, str] = {}
    _store("ssrf", scrub(attempt, [_FAKE_SECRET]), stored)
    assert _FAKE_SECRET not in stored["ssrf"]
    assert "[redacted]" in stored["ssrf"]
    assert _BLOCKED_URL in stored["ssrf"]
    with pytest.raises(AssertionError, match="refusing to store a raw secret"):
        _store("ssrf", attempt, stored)


def test_other_connection_record_is_not_found() -> None:
    """Another connection cannot load or approve this card.

    Inputs: one pending card on connection ``c1``, then a decide call from
    connection ``c2`` for that plan hash.
    Outputs: none.
    Side effects: calls ``Inbox.submit`` and ``Inbox.decide``. The card stays
    pending on ``c1``. The attempt text is scrubbed before it is stored.
    Does not copy the inbox checker, does not open a socket, and does not
    log the fake secret.
    """
    inbox = Inbox()
    result = inbox.submit(
        [_field()],
        goal="Add a note",
        assumptions=[],
        environment="staging",
        requester_id="u1",
        known_models={"x_m"},
        connection_id="c1",
    )
    assert result["ok"] is True
    plan_hash = result["card"]["plan_hash"]
    with pytest.raises(InboxError, match="not found"):
        inbox.decide(
            plan_hash,
            approver_id="u2",
            decision="approve",
            connection_id="c2",
        )
    owned = inbox.visible("c1")
    assert len(owned) == 1
    assert owned[0]["status"] == "pending"
    assert owned[0]["approvals"] == []
    assert owned[0]["connection_id"] == "c1"
    assert inbox.visible("c2") == []

    attempt = f"idor {_FAKE_SECRET} connection=c2 hash={plan_hash}"
    assert _FAKE_SECRET in attempt
    stored: dict[str, str] = {}
    _store("idor", scrub(attempt, [_FAKE_SECRET]), stored)
    assert _FAKE_SECRET not in stored["idor"]
    assert "[redacted]" in stored["idor"]
    assert plan_hash in stored["idor"]
    assert _FAKE_SECRET not in str(inbox.cards)
    with pytest.raises(AssertionError, match="refusing to store a raw secret"):
        _store("idor", attempt, stored)


def test_suite_files_do_not_close_gate_p3_01() -> None:
    """Eighteen suite files on disk leave GATE-P3-01 open.

    Inputs: the engine test directory.
    Outputs: none.
    Side effects: reads file names. Does not mark the gate closed and does
    not open a socket.
    """
    present = sorted(path.name for path in _ENGINE.glob("test_suite_*.py"))
    for prefix in _SUITE_PREFIXES:
        assert any(name.startswith(prefix) for name in present), prefix
    assert GATE_P3_01 == "open"
