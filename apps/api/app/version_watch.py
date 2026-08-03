"""Odoo version change detection + cache invalidation (TIER-4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.bulk_suite.transitions import invalidate_discovery_cache
from app.db_models import OdooConnection
from app.tier_matrix import invalidate_matrix_cache


@dataclass
class VersionWatchResult:
    changed: bool
    previous: str | None
    observed: str
    upgrade_detected: bool
    health_job_id: str | None = None


def normalize_version(version: str | None) -> str:
    return (version or "").strip()


def versions_differ(previous: str | None, observed: str | None) -> bool:
    prev = normalize_version(previous)
    obs = normalize_version(observed)
    if not obs:
        return False
    if not prev:
        return False
    return prev != obs


def _invalidate_caches(connection_id: str) -> None:
    invalidate_matrix_cache(connection_id)
    invalidate_discovery_cache(connection_id=connection_id)


def observe_server_version(
    db: Session,
    row: OdooConnection,
    observed_version: str,
    *,
    auto_health_check: bool = True,
) -> VersionWatchResult:
    """Compare live Odoo version with last_seen_version; flag upgrades."""
    observed = normalize_version(observed_version)
    previous = normalize_version(row.last_seen_version)
    changed = versions_differ(row.last_seen_version, observed)

    row.server_version = observed or row.server_version

    if not row.last_seen_version:
        row.last_seen_version = observed or None
        db.add(row)
        db.commit()
        db.refresh(row)
        return VersionWatchResult(
            changed=False,
            previous=None,
            observed=observed,
            upgrade_detected=False,
        )

    if not changed:
        db.add(row)
        db.commit()
        db.refresh(row)
        return VersionWatchResult(
            changed=False,
            previous=previous or None,
            observed=observed,
            upgrade_detected=bool(row.upgrade_detected),
        )

    _invalidate_caches(row.id)
    row.upgrade_detected = True
    row.upgrade_detected_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)

    health_job_id: str | None = None
    if auto_health_check and observed:
        from app.health_check import queue_health_check_job

        health_job_id = queue_health_check_job(
            db,
            connection_id=row.id,
            trigger="auto",
            previous_version=previous or None,
            current_version=observed,
        )

    return VersionWatchResult(
        changed=True,
        previous=previous or None,
        observed=observed,
        upgrade_detected=True,
        health_job_id=health_job_id,
    )


def clear_upgrade_flag(db: Session, row: OdooConnection, *, observed_version: str | None = None) -> None:
    """After a successful health sweep, align last_seen_version and clear the flag."""
    version = normalize_version(observed_version or row.server_version)
    if version:
        row.last_seen_version = version
    row.upgrade_detected = False
    row.upgrade_detected_at = None
    db.add(row)
    db.commit()


__all__ = [
    "VersionWatchResult",
    "clear_upgrade_flag",
    "normalize_version",
    "observe_server_version",
    "versions_differ",
]
