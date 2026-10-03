"""Read plane. A method outside the allowlist never reaches the transport."""

from __future__ import annotations

import threading
from typing import Any, Callable

READ_PLANE_METHODS = frozenset(
    {
        "search_read",
        "read",
        "search",
        "search_count",
        "fields_get",
        "read_group",
        "formatted_read_group",
        "name_search",
        "default_get",
        "get_views",
        "get_view",
        "check_access_rights",
        "has_access",
        "context_get",
        "exists",
    }
)

MAX_IN_FLIGHT = 2


class ReadPlaneError(Exception):
    pass


class ReadPlane:
    def __init__(self, transport: Callable[..., Any], *, max_in_flight: int = MAX_IN_FLIGHT) -> None:
        self._transport = transport
        self._max_in_flight = max_in_flight
        self._in_flight = 0
        self._lock = threading.Lock()
        self.calls = 0

    def call(self, model: str, method: str, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> Any:
        if method not in READ_PLANE_METHODS or method.startswith("button_") or method.startswith("action_"):
            raise ReadPlaneError(method)
        with self._lock:
            if self._in_flight >= self._max_in_flight:
                raise ReadPlaneError("concurrency")
            self._in_flight += 1
            self.calls += 1
        try:
            return self._transport(model, method, args or [], kwargs or {})
        finally:
            with self._lock:
                self._in_flight -= 1
