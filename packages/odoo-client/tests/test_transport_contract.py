"""Transport contract against a fake send function. No socket is opened."""

from __future__ import annotations

import threading

import pytest
import xmlrpc.client

from odoo_client.read_plane import ReadPlane, ReadPlaneError
from odoo_client.rpc_transport_errors import (
    AccessError,
    ApiUnavailable,
    AuthFailed,
    ConcurrencyError,
    DeadlockDetected,
    MissingError,
    RedirectWarning,
    ServerError,
    Timeout,
    Unknown,
    UserError,
    ValidationError,
    map_transport_error,
)
from odoo_client.transport.contract import (
    PreparedCall,
    RedirectHop,
    TransportContract,
    TransportPolicyError,
    WritePlaneRedirectError,
)


def _gate(send) -> TransportContract:
    return TransportContract(send)


def test_one_database_runs_at_most_two_calls_and_another_database_is_not_blocked() -> None:
    hold = threading.Event()
    entered = threading.Semaphore(0)
    lock = threading.Lock()
    inflight = {"alpha": 0, "beta": 0}
    peak = {"alpha": 0, "beta": 0}
    calls = {"alpha": 0, "beta": 0}

    def send(prepared: PreparedCall) -> dict:
        database = prepared.database
        with lock:
            inflight[database] += 1
            peak[database] = max(peak[database], inflight[database])
            calls[database] += 1
        entered.release()
        assert hold.wait(timeout=5)
        with lock:
            inflight[database] -= 1
        return {"ok": True}

    gate = _gate(send)

    def run(database: str) -> None:
        assert gate.call(
            database=database,
            model="sale.order",
            method="search_read",
            url="https://odoo.example",
        ) == {"ok": True}

    alpha = [threading.Thread(target=run, args=("alpha",)) for _ in range(3)]
    for thread in alpha:
        thread.start()
    assert entered.acquire(timeout=2)
    assert entered.acquire(timeout=2)
    assert entered.acquire(timeout=0.3) is False
    with lock:
        assert inflight["alpha"] == 2
        assert peak["alpha"] == 2

    beta = [threading.Thread(target=run, args=("beta",)) for _ in range(2)]
    for thread in beta:
        thread.start()
    assert entered.acquire(timeout=2)
    assert entered.acquire(timeout=2)
    with lock:
        assert inflight["beta"] == 2
        assert inflight["alpha"] == 2

    hold.set()
    for thread in alpha + beta:
        thread.join(timeout=2)
        assert not thread.is_alive()
    assert peak == {"alpha": 2, "beta": 2}
    assert calls == {"alpha": 3, "beta": 2}


def test_read_timeout_is_30s_and_write_timeout_is_120s() -> None:
    seen: list[PreparedCall] = []

    def send(prepared: PreparedCall) -> str:
        seen.append(prepared)
        return "ok"

    gate = _gate(send)
    assert gate.call(database="db", model="sale.order", method="search_read", url="https://odoo.example") == "ok"
    assert gate.call(database="db", model="sale.order", method="create", url="https://odoo.example") == "ok"
    assert [(row.method, row.timeout, row.allow_redirects) for row in seen] == [
        ("search_read", 30.0, True),
        ("create", 120.0, False),
    ]


def test_tls_is_required_and_verify_false_never_reaches_send() -> None:
    def send(prepared: PreparedCall) -> str:
        raise AssertionError(f"send was called for {prepared.url}")

    gate = _gate(send)
    with pytest.raises(TransportPolicyError, match="TLS required"):
        gate.call(database="db", model="sale.order", method="search_read", url="http://odoo.example")
    with pytest.raises(TransportPolicyError, match="verify=false is refused"):
        gate.call(
            database="db",
            model="sale.order",
            method="search_read",
            url="https://odoo.example",
            verify=False,
        )
    with pytest.raises(TransportPolicyError, match="verify=false is refused"):
        gate.call(
            database="db",
            model="sale.order",
            method="create",
            url="https://odoo.example",
            verify="false",
        )


def test_local_http_sandbox_sends_and_a_nonlocal_host_still_requires_tls() -> None:
    seen: list[PreparedCall] = []

    def send(prepared: PreparedCall) -> str:
        seen.append(prepared)
        return "ok"

    gate = _gate(send)
    local_urls = [
        "http://127.0.0.1:8069/xmlrpc/2/object",
        "http://localhost:8069/json/2/res.partner/search_read",
        "http://LOCALHOST/xmlrpc/2/common",
    ]
    for url in local_urls:
        assert gate.call(database="sandbox", model="sale.order", method="search_read", url=url) == "ok"
    assert [row.url for row in seen] == local_urls
    assert all(row.verify is True for row in seen)

    def refuse(prepared: PreparedCall) -> str:
        raise AssertionError(f"send was called for {prepared.url}")

    blocked = _gate(refuse)
    for url in ("http://odoo.example", "http://127.0.0.1.example", "http://localhost.evil"):
        with pytest.raises(TransportPolicyError, match="TLS required"):
            blocked.call(database="sandbox", model="sale.order", method="search_read", url=url)
    with pytest.raises(TransportPolicyError, match="verify=false is refused"):
        blocked.call(
            database="sandbox",
            model="sale.order",
            method="search_read",
            url="http://127.0.0.1:8069",
            verify=False,
        )

    def redirect(prepared: PreparedCall) -> RedirectHop:
        assert prepared.allow_redirects is False
        assert prepared.verify is True
        return RedirectHop(302, "http://127.0.0.1:9/evil")

    with pytest.raises(WritePlaneRedirectError) as caught:
        _gate(redirect).call(
            database="sandbox",
            model="sale.order",
            method="create",
            url="http://127.0.0.1:8069/xmlrpc/2/object",
        )
    assert caught.value.status == 302
    assert caught.value.location == "http://127.0.0.1:9/evil"


def test_write_redirect_is_not_followed() -> None:
    seen: list[str] = []

    def send(prepared: PreparedCall) -> RedirectHop:
        seen.append(prepared.url)
        assert prepared.allow_redirects is False
        return RedirectHop(302, "https://evil.example/xmlrpc/2/object")

    gate = _gate(send)
    with pytest.raises(WritePlaneRedirectError) as caught:
        gate.call(database="db", model="sale.order", method="create", url="https://odoo.example")
    assert caught.value.status == 302
    assert caught.value.location == "https://evil.example/xmlrpc/2/object"
    assert seen == ["https://odoo.example"]


def test_only_idempotent_reads_retry_and_a_safe_write_retries_deadlock_at_most_twice() -> None:
    def scripted(errors: list[BaseException]) -> tuple[TransportContract, list[int]]:
        pending = list(errors)
        attempts: list[int] = []

        def send(prepared: PreparedCall) -> str:
            attempts.append(prepared.attempt)
            if pending:
                raise pending.pop(0)
            return "ok"

        return _gate(send), attempts

    read_gate, read_attempts = scripted([TimeoutError("timed out"), TimeoutError("timed out")])
    assert read_gate.call(
        database="db",
        model="sale.order",
        method="search_read",
        url="https://odoo.example",
    ) == "ok"
    assert read_attempts == [1, 2, 3]

    user_gate, user_attempts = scripted([xmlrpc.client.Fault(1, "odoo.exceptions.UserError: stop")])
    with pytest.raises(UserError):
        user_gate.call(database="db", model="sale.order", method="read", url="https://odoo.example")
    assert user_attempts == [1]

    plain_gate, plain_attempts = scripted([RuntimeError("deadlock detected")])
    with pytest.raises(DeadlockDetected):
        plain_gate.call(database="db", model="sale.order", method="create", url="https://odoo.example")
    assert plain_attempts == [1]

    class _Server(Exception):
        status = 500

    safe_other, safe_other_attempts = scripted([_Server("boom")])
    with pytest.raises(ServerError):
        safe_other.call(
            database="db",
            model="sale.order",
            method="write",
            url="https://odoo.example",
            retry_safe=True,
        )
    assert safe_other_attempts == [1]

    deadlock = [RuntimeError("deadlock detected") for _ in range(4)]
    safe_gate, safe_attempts = scripted(deadlock)
    with pytest.raises(DeadlockDetected):
        safe_gate.call(
            database="db",
            model="sale.order",
            method="create",
            url="https://odoo.example",
            retry_safe=True,
        )
    assert safe_attempts == [1, 2, 3]

    raced = [RuntimeError("could not serialize access due to concurrent update") for _ in range(2)]
    race_gate, race_attempts = scripted(raced)
    assert race_gate.call(
        database="db",
        model="sale.order",
        method="write",
        url="https://odoo.example",
        retry_safe=True,
    ) == "ok"
    assert race_attempts == [1, 2, 3]


@pytest.mark.parametrize(
    ("error", "status", "body", "expected"),
    [
        ("odoo.exceptions.AccessError: not allowed", None, None, AccessError),
        ("odoo.exceptions.UserError: fix the form", None, None, UserError),
        ("odoo.exceptions.ValidationError: required", None, None, ValidationError),
        ("odoo.exceptions.MissingError: gone", None, None, MissingError),
        ("odoo.exceptions.RedirectWarning: confirm", None, None, RedirectWarning),
        ("could not serialize access due to concurrent update", None, None, ConcurrencyError),
        ("ERROR: deadlock detected", None, None, DeadlockDetected),
        (TimeoutError("timed out"), None, None, Timeout),
        ("authentication failed", None, None, AuthFailed),
        ("connection refused", None, None, ApiUnavailable),
        ("", 500, {"name": "werkzeug.exceptions.InternalServerError", "message": "boom"}, ServerError),
        ("not a known fault", None, None, Unknown),
        (xmlrpc.client.Fault(1, "odoo.exceptions.ValidationError: bad value"), None, None, ValidationError),
        ("", 401, {"message": "Invalid apikey"}, AuthFailed),
        ("", 403, {"name": "odoo.exceptions.AccessError", "message": "nope"}, AccessError),
        ("", 500, {"name": "psycopg2.errors.DeadlockDetected", "message": "deadlock detected"}, DeadlockDetected),
        ("", 503, {"message": "unavailable"}, ApiUnavailable),
        ("", 504, {"message": "gateway timed out"}, Timeout),
    ],
)
def test_transport_errors_map_onto_the_contract_names(error, status, body, expected) -> None:
    mapped = map_transport_error(error, status=status, body=body)
    assert isinstance(mapped, expected)


def test_method_allowlist_rejects_an_unknown_method_before_the_transport() -> None:
    seen: list[str] = []

    def transport(model: str, method: str, args: list, kwargs: dict) -> str:
        seen.append(method)
        return "ok"

    plane = ReadPlane(transport)
    with pytest.raises(ReadPlaneError, match="not_a_real_rpc_method"):
        plane.call("sale.order", "not_a_real_rpc_method")
    assert seen == []
