"""Unit tests for production snapshot gate (no database)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.snapshot_gate import SnapshotRequired, require_production_snapshot

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
FRESH = NOW - timedelta(minutes=2)


def _ok(**overrides: object) -> None:
    kwargs: dict = {
        "write_mode": "production",
        "risk": "destructive",
        "snapshot_id": "snap-1",
        "snapshot_exists": True,
        "snapshot_created_at": FRESH,
        "snapshot_connection_id": "conn-1",
        "connection_id": "conn-1",
        "now": NOW,
    }
    kwargs.update(overrides)
    require_production_snapshot(**kwargs)


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
    _ok()


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


def test_production_destructive_two_hour_old_snapshot_refused() -> None:
    with pytest.raises(SnapshotRequired, match="10-minute freshness window"):
        _ok(snapshot_created_at=NOW - timedelta(hours=2))


def test_production_snapshot_from_other_connection_refused() -> None:
    with pytest.raises(SnapshotRequired, match="different connection"):
        _ok(snapshot_connection_id="conn-other")


def test_production_billable_no_snapshot_refused() -> None:
    with pytest.raises(SnapshotRequired):
        require_production_snapshot(
            write_mode="production",
            risk="billable",
            snapshot_id=None,
            snapshot_exists=False,
        )


def test_production_billable_fresh_snapshot_returns() -> None:
    _ok(risk="BILLABLE")


def test_production_snapshot_older_than_last_write_refused() -> None:
    with pytest.raises(SnapshotRequired, match="last write audited"):
        _ok(
            snapshot_created_at=NOW - timedelta(minutes=5),
            last_write_audited_at=NOW - timedelta(minutes=2),
        )


def test_production_fresh_snapshot_newer_than_last_write_returns() -> None:
    _ok(
        snapshot_created_at=NOW - timedelta(minutes=1),
        last_write_audited_at=NOW - timedelta(minutes=5),
    )


def test_production_missing_created_at_refused() -> None:
    with pytest.raises(SnapshotRequired, match="created_at"):
        _ok(snapshot_created_at=None)


@pytest.mark.parametrize(
    "method",
    [
        "button_immediate_install",
        "button_install",
        "button_upgrade",
        "button_immediate_upgrade",
        "iap_charge",
        "sms_iap_send",
        "action_buy_credits",
    ],
)
def test_production_billable_method_requires_snapshot(method: str) -> None:
    with pytest.raises(SnapshotRequired):
        require_production_snapshot(
            write_mode="production",
            risk="reversible",
            method=method,
            snapshot_id=None,
            snapshot_exists=False,
        )


def test_odoo20_accepts_metadata_snapshot_without_web_database_backup() -> None:
    _ok(
        odoo_major=20,
        snapshot_kind="metadata",
        require_web_database_backup=True,
    )


def test_odoo20_metadata_snapshot_keeps_ten_minute_freshness_window() -> None:
    with pytest.raises(SnapshotRequired, match="10-minute freshness window"):
        _ok(
            odoo_major=20,
            snapshot_kind="metadata",
            require_web_database_backup=True,
            snapshot_created_at=NOW - timedelta(minutes=10, seconds=1),
        )


@pytest.mark.parametrize("major", [20, 21])
def test_major_20_and_above_skip_web_database_backup(major: int) -> None:
    _ok(
        odoo_major=major,
        snapshot_kind="metadata",
        require_web_database_backup=True,
    )


def test_odoo19_requires_web_database_backup_when_caller_asks() -> None:
    with pytest.raises(SnapshotRequired, match="/web/database"):
        _ok(
            odoo_major=19,
            snapshot_kind="metadata",
            require_web_database_backup=True,
        )


def test_odoo19_accepts_database_snapshot_when_caller_asks() -> None:
    _ok(
        odoo_major=19,
        snapshot_kind="database",
        require_web_database_backup=True,
    )


def test_missing_major_does_not_take_odoo_20_path() -> None:
    with pytest.raises(SnapshotRequired, match="/web/database"):
        _ok(
            odoo_major=None,
            snapshot_kind="metadata",
            require_web_database_backup=True,
        )


def test_major_above_20_stale_snapshot_still_refused() -> None:
    with pytest.raises(SnapshotRequired, match="10-minute freshness window"):
        _ok(
            odoo_major=21,
            snapshot_kind="metadata",
            require_web_database_backup=True,
            snapshot_created_at=NOW - timedelta(minutes=10, seconds=1),
        )


def test_billable_method_stays_gated_above_major_20() -> None:
    with pytest.raises(SnapshotRequired):
        require_production_snapshot(
            write_mode="production",
            risk="reversible",
            method="button_install",
            snapshot_id=None,
            snapshot_exists=False,
            odoo_major=21,
        )
