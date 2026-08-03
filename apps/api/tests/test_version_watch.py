"""Unit tests for version watch (TIER-4)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection  # noqa: E402
from app.version_watch import observe_server_version, versions_differ  # noqa: E402


@pytest.fixture(autouse=True)
def _db_ready() -> None:
    init_db()


def test_versions_differ_ignores_empty() -> None:
    assert versions_differ(None, "19.0") is False
    assert versions_differ("19.0", None) is False
    assert versions_differ("19.0", "19.0") is False
    assert versions_differ("18.0", "19.0") is True


def test_first_observation_sets_last_seen_without_upgrade() -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="watch-first",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version=None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        result = observe_server_version(db, row, "19.0", auto_health_check=False)
        db.refresh(row)

        assert result.changed is False
        assert result.upgrade_detected is False
        assert row.last_seen_version == "19.0"
        assert row.upgrade_detected is False
    finally:
        db.close()


def test_version_change_flags_upgrade_and_queues_job() -> None:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="watch-upgrade",
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            server_version="18.0",
            last_seen_version="18.0",
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        with patch("app.health_check.queue_health_check_job", return_value="job-123") as queued:
            result = observe_server_version(db, row, "19.0", auto_health_check=True)
            db.refresh(row)

        assert result.changed is True
        assert result.upgrade_detected is True
        assert result.health_job_id == "job-123"
        assert row.upgrade_detected is True
        assert row.server_version == "19.0"
        queued.assert_called_once()
    finally:
        db.close()
