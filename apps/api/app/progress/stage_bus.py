"""Stage events for long runs. The UI can subscribe. A spinner is not a stage."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from app.progress.stage_registry import KNOWN_STAGES


class StageBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[[dict], None]]] = defaultdict(list)
        self.events: list[dict] = []

    def emit(self, run_id: str, stage: str, *, detail: str = "") -> None:
        if not stage or stage == "spinner":
            raise ValueError("stage must name the work")
        if stage not in KNOWN_STAGES:
            raise ValueError(f"unknown stage: {stage}")
        event = {"run_id": run_id, "stage": stage, "detail": detail}
        self.events.append(event)
        for listener in self._listeners[run_id]:
            listener(event)

    def subscribe(self, run_id: str, listener: Callable[[dict], None]) -> None:
        self._listeners[run_id].append(listener)
