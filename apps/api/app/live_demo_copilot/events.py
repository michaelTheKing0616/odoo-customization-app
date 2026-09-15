"""Process-local SSE fan-out for Live Demo Co-Pilot (not a durability boundary)."""

from __future__ import annotations

import threading
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: dict[str, list] = {}

    def publish(self, session_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            for q in list(self._subscribers.get(session_id, [])):
                try:
                    q.put(event)
                except Exception:  # noqa: BLE001
                    pass

    def subscribe(self, session_id: str):
        import queue

        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.setdefault(session_id, []).append(q)
        return q

    def unsubscribe(self, session_id: str, q) -> None:
        with self._lock:
            subs = self._subscribers.get(session_id, [])
            if q in subs:
                subs.remove(q)


EVENT_BUS = EventBus()
