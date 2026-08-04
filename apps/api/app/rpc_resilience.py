"""TRUST-5 RPC fault tolerance — verify state before retrying unconfirmed writes."""

from __future__ import annotations

import xmlrpc.client
from dataclasses import dataclass, field
from typing import Any, Protocol


class RpcCaller(Protocol):
    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any: ...


DEFAULT_VERIFY_FIELDS = ("write_date", "display_name")


def is_transport_rpc_error(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, OSError, xmlrpc.client.ProtocolError)):
        return True
    if isinstance(exc, xmlrpc.client.Fault):
        return False
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "connection reset",
            "connection refused",
            "timed out",
            "timeout",
            "broken pipe",
            "connection dropped",
            "chaos:",
        )
    )


def record_fingerprint(row: dict[str, Any] | None) -> tuple[Any, ...] | None:
    if not row:
        return None
    return tuple(row.get(name) for name in DEFAULT_VERIFY_FIELDS)


def read_record_fingerprint(
    client: RpcCaller,
    model: str,
    record_id: int,
    *,
    fields: tuple[str, ...] = DEFAULT_VERIFY_FIELDS,
) -> tuple[Any, ...] | None:
    try:
        rows = client.execute_kw(
            model,
            "read",
            [[int(record_id)]],
            {"fields": list(fields)},
        )
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    return tuple(rows[0].get(name) for name in fields)


def execute_mutation_with_verify(
    client: RpcCaller,
    *,
    model: str,
    method: str,
    record_id: int,
    args_tail: list[Any] | None = None,
    max_attempts: int = 2,
) -> tuple[bool, str | None]:
    """Call ``execute_kw(model, method, [[record_id], *tail])`` with transport-safe retry.

    After a transport error, re-read the record fingerprint; if it changed, treat the
    mutation as having landed (no blind retry). Otherwise retry up to ``max_attempts``.
    """
    tail = list(args_tail or [])
    call_args = [[int(record_id)] + tail]
    pre = read_record_fingerprint(client, model, record_id)
    last_error: str | None = None
    attempts = max(1, int(max_attempts or 1))

    for attempt in range(attempts):
        try:
            client.execute_kw(model, method, call_args)
            return True, None
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc) or exc.__class__.__name__
            if not is_transport_rpc_error(exc):
                return False, last_error
            post = read_record_fingerprint(client, model, record_id)
            if pre is not None and post is not None and pre != post:
                return True, None
            if attempt + 1 >= attempts:
                return False, last_error
    return False, last_error or "unknown transport error"


@dataclass
class ChaosPolicy:
    """Test-only RPC fault injection policy."""

    fail_every: int = 0
    fail_on_call: int | None = None
    fail_methods: frozenset[str] = frozenset()
    _calls: int = field(default=0, init=False, repr=False)

    def should_fail(self, *, method: str) -> bool:
        self._calls += 1
        if self.fail_methods and method not in self.fail_methods:
            return False
        if self.fail_on_call is not None and self._calls == self.fail_on_call:
            return True
        if self.fail_every and self._calls % self.fail_every == 0:
            return True
        return False


class ChaosRpcWrapper:
    """Wrap an Odoo client ``execute_kw`` for chaos tests."""

    def __init__(self, inner: RpcCaller, policy: ChaosPolicy | None = None):
        self._inner = inner
        self._policy = policy or ChaosPolicy()

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        if self._policy.should_fail(method=method):
            raise ConnectionError(f"chaos: injected transport failure on {model}.{method}")
        return self._inner.execute_kw(model, method, args, kwargs)
