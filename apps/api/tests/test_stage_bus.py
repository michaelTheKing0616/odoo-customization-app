"""Live progress names the stage. A generic spinner is rejected."""

from __future__ import annotations

import pytest

from app.progress.stage_bus import StageBus


def test_events_are_stage_accurate() -> None:
    bus = StageBus()
    seen: list[str] = []
    bus.subscribe("run-1", lambda event: seen.append(event["stage"]))
    bus.emit("run-1", "validate")
    bus.emit("run-1", "simulate", detail="3 ops")
    assert seen == ["validate", "simulate"]


def test_spinner_is_not_a_stage() -> None:
    bus = StageBus()
    with pytest.raises(ValueError):
        bus.emit("run-1", "spinner")
