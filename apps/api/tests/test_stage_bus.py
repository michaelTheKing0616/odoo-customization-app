"""Live progress names the stage. A generic spinner is rejected."""

from __future__ import annotations

import pytest

from app.progress.stage_bus import StageBus


def test_events_are_stage_accurate() -> None:
    bus = StageBus()
    seen: list[str] = []
    bus.subscribe("run-1", lambda event: seen.append(event["stage"]))
    bus.emit("run-1", "expert_retrieve")
    bus.emit("run-1", "expert_answer", detail="3 ops")
    assert seen == ["expert_retrieve", "expert_answer"]


def test_spinner_is_not_a_stage() -> None:
    bus = StageBus()
    with pytest.raises(ValueError):
        bus.emit("run-1", "spinner")


def test_unknown_stage_is_rejected() -> None:
    bus = StageBus()
    with pytest.raises(ValueError, match="unknown stage"):
        bus.emit("run-1", "not_a_registered_stage")
