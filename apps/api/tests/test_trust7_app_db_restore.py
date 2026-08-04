"""TRUST-7 app-DB restore drill — script + pg_dump smoke (non-destructive by default)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RESTORE_SCRIPT = REPO_ROOT / "scripts" / "restore_app_db.sh"


def _pg_count(pg_url: str, table: str) -> int:
    proc = subprocess.run(
        ["psql", pg_url, "-tAc", f"SELECT count(*) FROM {table};"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"psql count failed for {table}")
    return int(proc.stdout.strip())


def test_restore_script_exists_and_is_executable() -> None:
    assert RESTORE_SCRIPT.is_file()
    assert os.access(RESTORE_SCRIPT, os.X_OK)


def test_restore_script_usage_without_args() -> None:
    proc = subprocess.run(
        [str(RESTORE_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "Usage:" in proc.stderr


def test_pg_dump_smoke_to_temp(tmp_path: Path) -> None:
    if shutil.which("pg_dump") is None:
        pytest.skip("pg_dump not installed")
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
    )
    pg_url = db_url.replace("postgresql+psycopg", "postgresql")
    out = tmp_path / "app_db_smoke.dump"
    proc = subprocess.run(
        ["pg_dump", "-Fc", "-f", str(out), pg_url],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"pg_dump unavailable: {proc.stderr[:200]}")
    assert out.stat().st_size > 1024


@pytest.mark.integration
def test_restore_drill_on_copy_database(tmp_path: Path) -> None:
    """Destructive — only runs when TEST_APP_DB_RESTORE=1 and RESTORE_TEST_DATABASE_URL set."""
    if not os.environ.get("TEST_APP_DB_RESTORE"):
        pytest.skip("Set TEST_APP_DB_RESTORE=1 to run live restore drill on copy DB")
    restore_url = os.environ.get("RESTORE_TEST_DATABASE_URL")
    if not restore_url:
        pytest.skip("RESTORE_TEST_DATABASE_URL required for live restore drill")
    if shutil.which("pg_dump") is None or shutil.which("pg_restore") is None:
        pytest.skip("pg_dump/pg_restore not installed")
    if shutil.which("psql") is None:
        pytest.skip("psql not installed")

    source = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
    )
    dump_path = tmp_path / "trust7_drill.dump"
    pg_source = source.replace("postgresql+psycopg", "postgresql")
    pg_restore = restore_url.replace("postgresql+psycopg", "postgresql")

    dump = subprocess.run(
        ["pg_dump", "-Fc", "-f", str(dump_path), pg_source],
        capture_output=True,
        text=True,
        check=False,
    )
    assert dump.returncode == 0, dump.stderr

    baseline = subprocess.run(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            f"--dbname={pg_restore}",
            str(dump_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert baseline.returncode == 0, baseline.stderr

    before = _pg_count(pg_restore, "odoo_connections")
    if before < 1:
        pytest.skip("odoo_connections empty on copy DB — cannot row-count drill")

    delete = subprocess.run(
        [
            "psql",
            pg_restore,
            "-c",
            "DELETE FROM odoo_connections WHERE ctid IN (SELECT ctid FROM odoo_connections LIMIT 1);",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert delete.returncode == 0, delete.stderr
    after_delete = _pg_count(pg_restore, "odoo_connections")
    assert after_delete == before - 1

    env = os.environ.copy()
    env["DATABASE_URL"] = restore_url
    restore = subprocess.run(
        [str(RESTORE_SCRIPT), str(dump_path)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        input="",
    )
    assert restore.returncode == 0, restore.stderr or restore.stdout

    after_restore = _pg_count(pg_restore, "odoo_connections")
    assert after_restore == before
