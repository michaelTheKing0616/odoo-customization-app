"""Unit tests for production snapshot gate (no database)."""

from __future__ import annotations

import pytest

from app.snapshot_gate import SnapshotRequired, require_production_snapshot


def test_production_destructive_no_id_raises() -> None:
    with pytest.raises(SnapshotRequired):
        require_production_snapshot(
            write_mode="production",
            risk="destructive",
            snapshot_id=None,
            snapshot_exists=False,
        )


def test_production_destructive_id_not_exists_raises() -> None:
    with pytest.raises(SnapshotRequired):
        require_production_snapshot(
            write_mode="production",
            risk="destructive",
            snapshot_id="snap-1",
            snapshot_exists=False,
        )


def test_production_destructive_id_exists_returns() -> None:
    require_production_snapshot(
        write_mode="production",
        risk="destructive",
        snapshot_id="snap-1",
        snapshot_exists=True,
    )


def test_standard_destructive_no_id_returns() -> None:
    require_production_snapshot(
        write_mode="standard",
        risk="destructive",
        snapshot_id=None,
        snapshot_exists=False,
    )


def test_production_reversible_no_id_returns() -> None:
    require_production_snapshot(
        write_mode="production",
        risk="reversible",
        snapshot_id=None,
        snapshot_exists=False,
    )
