"""Process-wide stage bus for progress streaming."""

from __future__ import annotations

from app.progress.stage_bus import StageBus

_BUS = StageBus()


def get_stage_bus() -> StageBus:
    return _BUS
