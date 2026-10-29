"""B0-ISO: throwaway App DB before settings import; dev DATABASE_URL fails closed."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy

import tests.conftest as harness

pytestmark = pytest.mark.no_app_db

_DEV_URL = "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom"
_REFUSED = (
    _DEV_URL,
    "postgresql+psycopg://u:p@127.0.0.1:5433/other_db",
    "postgresql+psycopg://u:p@10.0.0.8:5432/ingenium_b0_iso",
    "postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_b0_iso?dbname=odoo_custom",
    "postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_b0_iso?host=10.0.0.8",
    "postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_b0_iso?hostaddr=10.0.0.8",
    "postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_b0_iso?host=127.0.0.1&hostaddr=10.0.0.8",
)
_NEXT_CONFIG = Path(__file__).resolve().parents[3] / "apps" / "web" / "next.config.ts"
_PLAN = """
version: 1
project: b0_iso
custom_fields:
  - model: res.partner
    name: x_b0_iso
    ttype: char
"""
_OTHER_PLAN = """
version: 1
project: b0_iso
custom_fields:
  - model: res.partner
    name: x_b0_iso_other
    ttype: char
"""


def _seal_socket(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace getaddrinfo and create_connection so a real socket call fails the test."""
    calls: list[str] = []

    def _getaddrinfo(*_a: object, **_k: object) -> None:
        calls.append("getaddrinfo")
        raise AssertionError("getaddrinfo")

    def _create_connection(*_a: object, **_k: object) -> None:
        calls.append("create_connection")
        raise AssertionError("create_connection")

    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", _create_connection)
    monkeypatch.setattr(harness, "_real_getaddrinfo", _getaddrinfo)
    monkeypatch.setattr(harness, "_real_create_connection", _create_connection)
    return calls


_DEV_COUNT_TABLES = (
    "odoo_connections",
    "plan_cards",
    "audit_logs",
    "audit_chain_entries",
    "journal_entry",
)
# Child only. It must not import conftest or app.settings. SELECT count(*) then rollback.
_DEV_COUNT_SCRIPT = """\
import json
import os
import sys

import psycopg
from psycopg import sql

_TABLES = (
    "odoo_connections",
    "plan_cards",
    "audit_logs",
    "audit_chain_entries",
    "journal_entry",
)
_CLEAR_ENV = (
    "DATABASE_URL",
    "PGHOST",
    "PGHOSTADDR",
    "PGPORT",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
    "PGSERVICE",
)


def _redact(text: str, secret: str) -> str:
    cleaned = text.replace(secret, "[url]") if secret else text
    if "://" not in secret or "@" not in secret.split("://", 1)[1]:
        return cleaned
    userinfo = secret.split("://", 1)[1].split("@", 1)[0]
    if ":" not in userinfo:
        return cleaned
    password = userinfo.split(":", 1)[1]
    if password:
        cleaned = cleaned.replace(password, "[redacted]")
    return cleaned


def main() -> None:
    secret = os.environ["B0_ISO_COUNT_URL"]
    for key in _CLEAR_ENV:
        os.environ.pop(key, None)
    url = secret
    prefix = "postgresql+psycopg://"
    if url.startswith(prefix):
        url = "postgresql://" + url[len(prefix) :]
    conn = psycopg.connect(url, autocommit=False, connect_timeout=5)
    try:
        counts = {}
        cursor = conn.cursor()
        try:
            for name in _TABLES:
                cursor.execute(
                    sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("count returned no row for " + name)
                counts[name] = int(row[0])
        finally:
            cursor.close()
        conn.rollback()
    finally:
        conn.close()
    json.dump(counts, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        secret = os.environ.get("B0_ISO_COUNT_URL", "")
        sys.stderr.write(_redact(f"{type(exc).__name__}: {exc}", secret))
        sys.exit(1)
"""


def _redact_dev_secret(text: str) -> str:
    """Remove the dev URL and its password from a snapshot error.

    Inputs: text that may contain the dev URL. Output: redacted text.
    Side effects: none.
    """
    cleaned = text.replace(_DEV_URL, "[url]")
    marker = "://"
    if marker not in _DEV_URL or "@" not in _DEV_URL.split(marker, 1)[1]:
        return cleaned
    userinfo = _DEV_URL.split(marker, 1)[1].split("@", 1)[0]
    if ":" not in userinfo:
        return cleaned
    password = userinfo.split(":", 1)[1]
    if password:
        cleaned = cleaned.replace(password, "[redacted]")
    return cleaned


def _dev_table_counts() -> dict[str, int]:
    """Read dev App DB row counts without importing the guard in the child.

    Inputs: none. Output: integer counts for the five dev tables.
    Side effects: a subprocess runs SELECT count(*) and rolls back. This
    process does not call psycopg.connect. No INSERT, UPDATE, DELETE, or DDL.
    """
    env = os.environ.copy()
    env["B0_ISO_COUNT_URL"] = _DEV_URL
    completed = subprocess.run(
        [sys.executable, "-c", _DEV_COUNT_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise AssertionError(_redact_dev_secret(detail or "dev count snapshot failed"))
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise AssertionError(_redact_dev_secret(completed.stdout)) from None
    if not isinstance(raw, dict) or set(raw) != set(_DEV_COUNT_TABLES):
        raise AssertionError("dev count snapshot returned unexpected tables")
    counts: dict[str, int] = {}
    for name in _DEV_COUNT_TABLES:
        value = raw[name]
        if type(value) is not int:
            raise AssertionError(f"dev count for {name} was not an integer")
        counts[name] = value
    return counts


def _dev_row_counts(url: str) -> dict[str, int]:
    """Snapshot helper. Must raise before any query against the dev App DB.

    Inputs: database URL. Output: not reached for a refused URL.
    Side effects: create_engine, which the guard refuses for odoo_custom.
    """
    sqlalchemy.create_engine(url)
    raise AssertionError("dev database accepted an engine")


def test_ac1_positive_throwaway_before_settings() -> None:
    """Session URL is ingenium_ on loopback, assigned before app.settings is imported."""
    source = Path(harness.__file__).read_text(encoding="utf-8")
    assign_at = source.find('os.environ["DATABASE_URL"] = _B0_ISO_DATABASE_URL')
    settings_at = source.find("from app.settings import settings")
    assert assign_at != -1
    assert settings_at != -1
    assert assign_at < settings_at

    from app.db import create_engine as app_create_engine
    from app.db import engine
    from app.settings import settings

    host, database = harness._db_endpoint(settings.database_url)
    env_host, env_database = harness._db_endpoint(os.environ["DATABASE_URL"])
    assert database.startswith("ingenium_")
    assert host in {"127.0.0.1", "::1", "localhost"}
    assert (host, database) == (env_host, env_database)
    assert database != "odoo_custom"
    assert engine.url.database == database
    assert engine.url.host == host
    assert app_create_engine is sqlalchemy.create_engine
    assert getattr(sqlalchemy.create_engine, "_b0_iso_guard", False) is True


@pytest.mark.parametrize("url", _REFUSED)
def test_ac1_negative_server_url_refused_before_socket(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _seal_socket(monkeypatch)
    with pytest.raises(ConnectionRefusedError):
        sqlalchemy.create_engine(url)
    assert calls == []


def test_ac2_positive_session_target_is_not_the_dev_db() -> None:
    host, database = harness._db_endpoint(os.environ["DATABASE_URL"])
    dev_host, dev_database = harness._db_endpoint(_DEV_URL)
    assert database.startswith("ingenium_")
    assert host in {"127.0.0.1", "::1", "localhost"}
    assert (host, database) != (dev_host, dev_database)


def test_ac2_negative_dev_counts_refused_before_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dev connects are refused before a socket call, and dev row counts stay equal.

    The counts are integers from a child that does not import conftest. This
    process does not query the dev database.
    """
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=1.0):
            pass
    except OSError:
        pytest.skip("dev App DB Postgres on 127.0.0.1:5433 is not running; AC2 needs its real row counts")
    before = _dev_table_counts()
    calls = _seal_socket(monkeypatch)
    with pytest.raises(ConnectionRefusedError, match="does not start with ingenium_"):
        _dev_row_counts(_DEV_URL)
    with pytest.raises(ConnectionRefusedError, match="does not start with ingenium_"):
        _dev_row_counts(
            "postgresql+psycopg://u:p@127.0.0.1:5433/ingenium_b0_iso?dbname=odoo_custom"
        )
    import psycopg

    with pytest.raises(ConnectionRefusedError, match="does not start with ingenium_"):
        psycopg.connect(_DEV_URL)
    with pytest.raises(ConnectionRefusedError, match="does not start with ingenium_"):
        psycopg.connect(host="127.0.0.1", port=5433, dbname="odoo_custom")
    with pytest.raises(ConnectionRefusedError, match="does not start with ingenium_"):
        psycopg.connect("postgresql://u@127.0.0.1:5433/ingenium_b0_iso?dbname=odoo_custom")
    with pytest.raises(ConnectionRefusedError, match="not loopback"):
        psycopg.connect("postgresql://u@127.0.0.1:5433/ingenium_b0_iso?host=10.0.0.8")
    with pytest.raises(ConnectionRefusedError, match="not loopback"):
        psycopg.connect(
            "postgresql://u@127.0.0.1:5433/ingenium_b0_iso?hostaddr=10.0.0.8"
        )
    assert calls == []
    after = _dev_table_counts()
    for name in _DEV_COUNT_TABLES:
        assert type(before[name]) is int
        assert type(after[name]) is int
        assert before[name] == after[name]


def test_ac3_positive_dist_dir_only_when_env_set() -> None:
    text = _NEXT_CONFIG.read_text(encoding="utf-8")
    assert 'process.env.PLAYWRIGHT_E2E_BUILD === "1"' in text
    assert "process.env.INGENIUM_DIST_DIR" in text
    assert (
        'const distDir = ingeniumDistDir || (isPlaywrightE2eBuild ? ".next-e2e" : undefined);'
        in text
    )
    assert "...(distDir ? { distDir } : {})" in text


def test_ac3_negative_no_hardcoded_dev_dist_dir() -> None:
    text = _NEXT_CONFIG.read_text(encoding="utf-8")
    assert 'distDir: ".next"' not in text
    assert "distDir: '.next'" not in text
    assert 'output: "standalone"' in text


def test_ac4_positive_live_ai_skipped_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INGENIUM_LIVE_AI", raising=False)

    class _Item:
        def __init__(self) -> None:
            self.path = type("Path", (), {"name": "test_b0_iso.py"})()
            self.keywords = {"live_ai": True}
            self.added: list[object] = []

        def add_marker(self, marker: object) -> None:
            self.added.append(marker)

    item = _Item()
    harness.pytest_collection_modifyitems(None, [item])
    assert len(item.added) == 1
    mark = getattr(item.added[0], "mark", None)
    reason = ""
    if mark is not None:
        reason = str(getattr(mark, "kwargs", {}).get("reason", ""))
    assert "INGENIUM_LIVE_AI" in reason


def test_ac4_negative_vertex_and_other_db_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INGENIUM_LIVE_AI", raising=False)
    monkeypatch.delenv("INGENIUM_LIVE_AI_ACTIVE", raising=False)
    with pytest.raises(ConnectionRefusedError, match="Vertex"):
        socket.getaddrinfo("aiplatform.googleapis.com", 443)
    calls = _seal_socket(monkeypatch)
    with pytest.raises(ConnectionRefusedError, match="does not start with ingenium_"):
        sqlalchemy.create_engine("postgresql+psycopg://u:p@127.0.0.1:5432/odoo_dev")
    assert calls == []


def test_ac4_order_session_url_a() -> None:
    _host, database = harness._db_endpoint(os.environ["DATABASE_URL"])
    assert database.startswith("ingenium_")


def test_ac4_order_session_url_b() -> None:
    from app.settings import settings

    _host, database = harness._db_endpoint(settings.database_url)
    assert database.startswith("ingenium_")


def test_ac5_positive_second_apply_writes_zero() -> None:
    from app.changeset.executor import reset_journal
    from app.config_as_code.apply import MemoryDb, apply_plan
    from app.config_as_code.loader import compile_plan, load_spec

    reset_journal()
    plan = compile_plan(load_spec(_PLAN))
    db = MemoryDb()
    assert apply_plan(db, plan) == 1
    written = db.writes
    reset_journal()
    assert apply_plan(db, plan) == 0
    assert db.writes == written


def test_ac5_negative_different_plan_writes_again() -> None:
    from app.changeset.executor import reset_journal
    from app.config_as_code.apply import MemoryDb, apply_plan
    from app.config_as_code.loader import compile_plan, load_spec

    reset_journal()
    db = MemoryDb()
    assert apply_plan(db, compile_plan(load_spec(_PLAN))) == 1
    reset_journal()
    assert apply_plan(db, compile_plan(load_spec(_OTHER_PLAN))) == 1
    assert db.writes == 2
