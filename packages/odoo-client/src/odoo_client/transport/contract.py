"""Transport contract enforced on a caller-supplied send function.

The send function is a fake in tests and, later, an HTTP or XML-RPC adapter.
This module does not open a socket. Local sandbox clients stay on plain HTTP
until a card wires this gate in front of them.

Limits, copied from the engine contract:
- at most two calls in flight for one database
- 30s on an idempotent read, 120s on anything else
- TLS required; ``verify`` must be ``True``
- a write does not follow a redirect
- an idempotent read may retry a transport failure at most twice
- a write retries only when ``retry_safe`` is set and the error is a deadlock
  or a concurrency failure, and then at most twice
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from odoo_client.read_plane import READ_PLANE_METHODS
from odoo_client.rpc_transport_errors import (
    ApiUnavailable,
    ConcurrencyError,
    DeadlockDetected,
    OdooRpcError,
    ServerError,
    Timeout,
    map_transport_error,
)

READ_TIMEOUT_SECONDS = 30.0
WRITE_TIMEOUT_SECONDS = 120.0
MAX_IN_FLIGHT_PER_DATABASE = 2
MAX_WRITE_RETRIES = 2

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_READ_RETRYABLE = (Timeout, ApiUnavailable, ServerError, DeadlockDetected, ConcurrencyError)
_WRITE_RETRYABLE = (DeadlockDetected, ConcurrencyError)


class TransportPolicyError(Exception):
    """The call was refused before a retry or a second hop."""


class WritePlaneRedirectError(TransportPolicyError):
    """A write observed a redirect and did not follow it."""

    def __init__(self, status: int, location: str) -> None:
        self.status = status
        self.location = location
        super().__init__(f"write-plane redirect refused ({status})")


@dataclass(frozen=True)
class PreparedCall:
    """One attempt handed to ``send``. ``attempt`` starts at 1."""

    database: str
    model: str
    method: str
    url: str
    timeout: float
    allow_redirects: bool
    verify: bool
    attempt: int


@dataclass(frozen=True)
class RedirectHop:
    """A redirect the send function observed and did not follow itself."""

    status: int
    location: str


def timeout_for(method: str) -> float:
    """Idempotent reads use the short timeout. Every other method uses the write timeout."""
    if method in READ_PLANE_METHODS:
        return READ_TIMEOUT_SECONDS
    return WRITE_TIMEOUT_SECONDS


def assert_tls(url: str, verify: object = True) -> None:
    """Refuse a non-HTTPS URL and any ``verify`` value other than ``True``.

    ``verify=False`` and the string ``"false"`` both fail this check.
    """
    if verify is not True:
        raise TransportPolicyError("verify=false is refused")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise TransportPolicyError("TLS required")


class TransportContract:
    """Serialize calls per database and apply timeout, TLS, redirect, and retry rules."""

    def __init__(self, send: Callable[[PreparedCall], Any]) -> None:
        self._send = send
        self._guard = threading.Lock()
        self._slots: dict[str, threading.BoundedSemaphore] = {}

    def call(
        self,
        *,
        database: str,
        model: str,
        method: str,
        url: str,
        verify: object = True,
        retry_safe: bool = False,
    ) -> Any:
        """Send one RPC under the contract. Side effect: invokes ``send`` one or more times."""
        assert_tls(url, verify)
        key = _database_key(database)
        if not isinstance(method, str) or not method:
            raise TransportPolicyError("method is required")
        timeout = timeout_for(method)
        allow_redirects = method in READ_PLANE_METHODS
        slot = self._slot(key)
        slot.acquire()
        try:
            return self._attempt(
                database=key,
                model=model,
                method=method,
                url=url,
                timeout=timeout,
                allow_redirects=allow_redirects,
                retry_safe=retry_safe,
            )
        finally:
            slot.release()

    def _slot(self, database: str) -> threading.BoundedSemaphore:
        with self._guard:
            slot = self._slots.get(database)
            if slot is None:
                slot = threading.BoundedSemaphore(MAX_IN_FLIGHT_PER_DATABASE)
                self._slots[database] = slot
            return slot

    def _attempt(
        self,
        *,
        database: str,
        model: str,
        method: str,
        url: str,
        timeout: float,
        allow_redirects: bool,
        retry_safe: bool,
    ) -> Any:
        attempt = 0
        while True:
            attempt += 1
            prepared = PreparedCall(
                database=database,
                model=model,
                method=method,
                url=url,
                timeout=timeout,
                allow_redirects=allow_redirects,
                verify=True,
                attempt=attempt,
            )
            try:
                result = self._send(prepared)
            except TransportPolicyError:
                raise
            except Exception as exc:
                mapped = map_transport_error(exc)
                if _may_retry(method, retry_safe, mapped, attempt):
                    continue
                if mapped is exc:
                    raise
                raise mapped from exc
            hop = _redirect_hop(result)
            if hop is not None and not allow_redirects:
                raise WritePlaneRedirectError(hop.status, hop.location)
            return result


def _database_key(database: str) -> str:
    if not isinstance(database, str):
        raise TransportPolicyError("database is required")
    key = database.strip()
    if not key:
        raise TransportPolicyError("database is required")
    return key


def _may_retry(method: str, retry_safe: bool, error: OdooRpcError, attempt: int) -> bool:
    """``attempt`` is the try that just failed. Two retries means three tries total."""
    if attempt > MAX_WRITE_RETRIES:
        return False
    if method in READ_PLANE_METHODS:
        return isinstance(error, _READ_RETRYABLE)
    if retry_safe and isinstance(error, _WRITE_RETRYABLE):
        return True
    return False


def _redirect_hop(result: Any) -> RedirectHop | None:
    if isinstance(result, RedirectHop) and result.status in _REDIRECT_STATUSES:
        return result
    return None
