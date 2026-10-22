#!/usr/bin/env python3
"""List test-fixture App DB connections, and delete them only with --apply --yes.

No flag prints the connection names and Odoo database names that would be
deleted, prints counts, and deletes 0 rows. It also prints the pg_dump -Fc
path it would use and does not create that file.

--apply without --yes deletes 0 rows and exits non-zero. --apply --yes writes
a pg_dump -Fc backup first, then deletes rows whose names match the fixture
patterns and that have no App Studio session and no live-demo session.

The script never drops a database. It connects only when the database name
starts with ingenium_ and the host is loopback. Port 5433 and the database
name odoo_custom are refused before any socket call.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlparse

FIXTURE_PATTERNS: tuple[str, ...] = (
    "Matrix conn",
    "Other client",
    "Granted client",
    "code-studio",
    "fake-m3",
    "Alice victim conn",
    "fake-ops",
    "role-matrix",
)

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
_FORBIDDEN_PORT = 5433
_FORBIDDEN_DATABASE = "odoo_custom"
_REQUIRED_TABLES = (
    "odoo_connections",
    "ai_sessions",
    "live_demo_copilot_sessions",
)
_EXIT_OK = 0
_EXIT_REFUSED = 2
_DUMP_STAMP = "%Y%m%dT%H%M%S%fZ"
# Same fallback as app.settings when DATABASE_URL is unset. The guard refuses it
# (port 5433, database odoo_custom) before any socket call.
_APP_DEFAULT_URL = "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom"


@dataclass(frozen=True)
class Target:
    """A database the guard has already allowed. Password is never printed."""

    host: str
    port: int
    database: str
    user: str
    password: str


@dataclass(frozen=True)
class Row:
    id: str
    name: str
    database: str


def name_matches(name: str) -> bool:
    """Return True when name is a fixture pattern or a spaced or hyphenated suffix of one.

    Inputs: a connection name. Output: True for an exact pattern, or the pattern
    followed by a space or hyphen. Side effects: none.
    """
    for pattern in FIXTURE_PATTERNS:
        if name == pattern or name.startswith(pattern + " ") or name.startswith(pattern + "-"):
            return True
    return False


def _normalise_url(url: str) -> str:
    """Return a postgresql:// URL. Inputs: a SQLAlchemy or libpq URL. Side effects: none."""
    for prefix in (
        "postgresql+psycopg://",
        "postgresql+asyncpg://",
        "postgres+psycopg://",
    ):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix) :]
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _norm_host(value: str) -> str:
    host = value.strip().rstrip(".").lower()
    if len(host) >= 2 and host.startswith("[") and host.endswith("]"):
        host = host[1:-1].strip().rstrip(".").lower()
    return host


def inspect_target(url: str) -> Target | str:
    """Return a Target, or a refusal reason. Does not open a socket and does not print the URL.

    Inputs: database URL. Query host, hostaddr, port, and dbname override the
    authority. A non-loopback host wins. Any port 5433 refuses. The database
    name odoo_custom refuses. Otherwise the name must start with ingenium_
    and the host must be loopback.
    Output: Target or a short reason string.
    Side effects: none.
    """
    if not url.strip():
        return "database name does not start with ingenium_"
    parsed = urlparse(_normalise_url(url))
    pairs = parse_qsl(parsed.query, keep_blank_values=False, separator="&")

    def values(name: str) -> list[str]:
        return [value for key, value in pairs if key.lower() == name]

    ports: list[int] = []
    if parsed.port is not None:
        ports.append(parsed.port)
    for raw in values("port"):
        text = raw.strip()
        if not text:
            continue
        try:
            ports.append(int(text))
        except ValueError:
            return "port is not a number"
    if _FORBIDDEN_PORT in ports:
        return "port 5433 is forbidden"
    port = ports[-1] if ports else 5432

    path = unquote(parsed.path or "")
    database = path[1:] if path.startswith("/") else path
    for name in values("dbname"):
        if name == "":
            continue
        database = name
        if name == _FORBIDDEN_DATABASE or not name.startswith("ingenium_"):
            break
    if database == _FORBIDDEN_DATABASE:
        return "database name odoo_custom is forbidden"
    if not database.startswith("ingenium_"):
        return "database name does not start with ingenium_"

    def picked(raw_values: list[str]) -> str | None:
        chosen: str | None = None
        for raw in raw_values:
            host = _norm_host(raw)
            if not host:
                continue
            if host not in _LOOPBACK_HOSTS:
                return host
            chosen = host
        return chosen

    query_host = picked(values("host"))
    query_addr = picked(values("hostaddr"))
    authority = _norm_host(parsed.hostname or "")
    if query_host is not None and query_addr is not None:
        if query_host not in _LOOPBACK_HOSTS:
            host = query_host
        elif query_addr not in _LOOPBACK_HOSTS:
            host = query_addr
        else:
            host = query_host
    elif query_host is not None:
        host = query_host
    elif query_addr is not None:
        host = query_addr
    else:
        host = authority
    if host not in _LOOPBACK_HOSTS:
        return "host is not loopback"

    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    return Target(host=host, port=port, database=database, user=user, password=password)


def _database_url_in_file(path: Path) -> str | None:
    """Return the DATABASE_URL value in one env file, or None when the key is absent.

    Inputs: path to an env file. Output: the value with matching quotes removed,
    or None when the file or the key is absent. Side effects: reads that file.
    Does not print the value and does not open a socket.
    """
    if not path.is_file():
        return None
    found: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if not line.startswith("DATABASE_URL="):
            continue
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        found = value.strip()
    if found == "":
        return None
    return found


def app_database_url() -> str:
    """Return the App DB URL the API would use. The caller must not print it.

    Inputs: DATABASE_URL in the process environment, otherwise the repo .env
    and the current directory .env, otherwise the API's built-in default.
    Output: a URL string. Side effects: may read an env file. Does not open a
    socket. When pydantic is installed, the API settings object is used instead
    of the file reader so both paths stay the same.
    """
    configured = os.environ.get("DATABASE_URL", "").strip()
    if configured:
        return configured
    try:
        import pydantic_settings  # noqa: F401

        api_root = Path(__file__).resolve().parents[1] / "apps" / "api"
        if str(api_root) not in sys.path:
            sys.path.insert(0, str(api_root))
        from app.settings import settings

        return settings.database_url
    except ModuleNotFoundError:
        root = Path(__file__).resolve().parents[1]
        found: str | None = None
        for path in (root / ".env", Path.cwd() / ".env"):
            value = _database_url_in_file(path)
            if value:
                found = value
        return found if found else _APP_DEFAULT_URL


def redact(text: str, url: str) -> str:
    """Remove userinfo from text. Inputs: a message and the URL. Side effects: none."""
    if not url:
        return text
    parsed = urlparse(_normalise_url(url))
    if parsed.username and parsed.password is not None:
        raw = f"{parsed.username}:{parsed.password}@"
        quoted = f"{quote(parsed.username, safe='')}:{quote(parsed.password, safe='')}@"
        text = text.replace(raw, "").replace(quoted, "")
    if parsed.password and parsed.password not in {
        parsed.username or "",
        unquote((parsed.path or "").lstrip("/")),
    }:
        text = text.replace(parsed.password, "***")
    return text


def dump_path(database: str) -> Path:
    """Return the pg_dump -Fc path for this run. Does not create the file or its directory.

    Inputs: an ingenium_ database name. B0_JUNK_DUMP_DIR overrides the directory.
    Output: an absolute path. Side effects: none.
    """
    override = os.environ.get("B0_JUNK_DUMP_DIR", "").strip()
    if override:
        directory = Path(override).expanduser().resolve()
    else:
        directory = Path(__file__).resolve().parents[1] / "backups" / "b0-junk"
    stamp = datetime.now(UTC).strftime(_DUMP_STAMP)
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", database)[:80] or "app"
    return directory / f"{safe}-{stamp}.dump"


def _print_plan(
    *,
    mode: str,
    deleted: int,
    rows: list[Row],
    remaining: str,
    dump: str,
    reason: str | None = None,
) -> None:
    if reason:
        print(f"refusing to connect: {reason}")
    print(f"mode: {mode}")
    print(f"deleted: {deleted}")
    print(f"connection_count: {len(rows)}")
    print(f"database_count: {len({row.database for row in rows})}")
    print(f"remaining_count: {remaining}")
    print(f"pg_dump -Fc: {dump}")
    print("databases_dropped: 0")
    for row in rows:
        print(f"connection: {row.name}")
        print(f"database: {row.database}")


def _refused(reason: str, *, mode: str) -> int:
    _print_plan(
        mode=mode,
        deleted=0,
        rows=[],
        remaining="not read",
        dump="not created",
        reason=reason,
    )
    return _EXIT_REFUSED


def _load(conn: object) -> tuple[list[Row], int]:
    """Return unused fixture rows and the connection total.

    Inputs: an open psycopg connection. Output: matching rows, then the count of
    every connection. Side effects: SELECT only. Raises PlanError when the
    session tables are missing, so a missing proof deletes nothing.
    """
    cursor = conn.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = ANY(%s)
            """,
            (list(_REQUIRED_TABLES),),
        )
        found = {str(row[0]) for row in cursor.fetchall()}
        missing = [name for name in _REQUIRED_TABLES if name not in found]
        if missing:
            raise PlanError("cannot prove which rows a real session has used")
        cursor.execute("SELECT COUNT(*) FROM odoo_connections")
        total = int(cursor.fetchone()[0])
        cursor.execute(
            """
            SELECT c.id, c.name, c.db_name
            FROM odoo_connections AS c
            WHERE NOT EXISTS (
                SELECT 1 FROM ai_sessions AS s WHERE s.connection_id = c.id
            )
            AND NOT EXISTS (
                SELECT 1
                FROM live_demo_copilot_sessions AS lived
                WHERE lived.connection_id = c.id
            )
            """
        )
        rows = [
            Row(id=str(row_id), name=str(name), database=str(database))
            for row_id, name, database in cursor.fetchall()
            if name_matches(str(name))
        ]
        rows.sort(key=lambda row: (row.name, row.database, row.id))
        return rows, total
    finally:
        cursor.close()


class PlanError(Exception):
    """The plan cannot be proven. Nothing is deleted."""


def _backup(target: Target, path: Path) -> None:
    """Write pg_dump -Fc to path. Inputs: an allowed target and a new file path.

    Output: none. Side effects: creates the parent directory and the dump file.
    Raises PlanError on failure and removes a partial file. Does not print the
    password. The password is passed only through the child environment.
    """
    pg_dump = _pg_dump_bin()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise PlanError("backup path already exists")
    env = os.environ.copy()
    env["PGHOST"] = target.host
    env["PGPORT"] = str(target.port)
    env["PGDATABASE"] = target.database
    env.pop("PGHOSTADDR", None)
    if target.user:
        env["PGUSER"] = target.user
    else:
        env.pop("PGUSER", None)
    if target.password:
        env["PGPASSWORD"] = target.password
    else:
        env.pop("PGPASSWORD", None)
    try:
        completed = subprocess.run(
            [pg_dump, "-Fc", "-f", str(path), "-w"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        path.unlink(missing_ok=True)
        raise PlanError("pg_dump failed") from exc
    if completed.returncode != 0 or not path.is_file() or path.stat().st_size == 0:
        path.unlink(missing_ok=True)
        raise PlanError("pg_dump failed")


def _pg_dump_bin() -> str:
    import shutil

    found = shutil.which("pg_dump")
    if not found:
        raise PlanError("pg_dump is not on PATH")
    return found


def _delete(conn: object, rows: list[Row]) -> int:
    """Delete the planned connection rows. Inputs: open connection and rows.

    Output: deleted row count. Side effects: DELETE on odoo_connections. Child
    rows follow the foreign keys already on the database. Does not drop a database.
    """
    if not rows:
        return 0
    cursor = conn.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute(
            "DELETE FROM odoo_connections WHERE id = ANY(%s) RETURNING id",
            ([row.id for row in rows],),
        )
        return len(cursor.fetchall())
    finally:
        cursor.close()


def _connect(target: Target) -> object:
    """Open the allowed database. Inputs: Target. Output: a psycopg connection.

    Side effects: one TCP connection to the loopback host. Raises PlanError
    when psycopg is missing, before any socket call.
    """
    try:
        import psycopg
    except ImportError as exc:
        raise PlanError("psycopg is not installed") from exc
    kwargs: dict[str, object] = {
        "host": target.host,
        "port": target.port,
        "dbname": target.database,
        "connect_timeout": 5,
    }
    if target.user:
        kwargs["user"] = target.user
    if target.password:
        kwargs["password"] = target.password
    return psycopg.connect(**kwargs)


def run(argv: list[str] | None = None) -> int:
    """Plan or delete fixture connections.

    Inputs: CLI args. --apply deletes only together with --yes.
    Output: process exit code. 0 when a dry-run read finishes. 2 when the
    target is refused, --yes is missing, or the backup or delete fails.
    Side effects: stdout report. A dump file and row deletes only for
    --apply --yes when at least one row matches. Never drops a database.
    """
    parser = argparse.ArgumentParser(
        description="List unused test-fixture connections. Delete them only with --apply --yes."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete matching rows. Does nothing unless --yes is also set.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Record a yes for this invocation. Required with --apply.",
    )
    args = parser.parse_args(argv)
    mode = "apply" if args.apply else "dry-run"
    try:
        url = app_database_url()
    except Exception as exc:
        print(f"refusing to connect: could not read the app database URL ({type(exc).__name__})")
        print(f"mode: {mode}")
        print("deleted: 0")
        print("connection_count: 0")
        print("database_count: 0")
        print("remaining_count: not read")
        print("pg_dump -Fc: not created")
        print("databases_dropped: 0")
        return _EXIT_REFUSED

    inspected = inspect_target(url)
    if isinstance(inspected, str):
        return _refused(inspected, mode=mode)

    path = dump_path(inspected.database)
    try:
        conn = _connect(inspected)
    except PlanError as exc:
        return _refused(str(exc), mode=mode)
    except Exception as exc:
        message = redact(str(exc), url).replace("\n", " ")
        return _refused(f"could not connect ({message})", mode=mode)

    try:
        with conn:
            try:
                rows, total = _load(conn)
            except PlanError as exc:
                _print_plan(
                    mode=mode,
                    deleted=0,
                    rows=[],
                    remaining="not read",
                    dump="not created",
                    reason=str(exc),
                )
                return _EXIT_REFUSED
            if not (args.apply and args.yes and rows):
                _print_plan(
                    mode="apply-refused" if args.apply and not args.yes else mode,
                    deleted=0,
                    rows=rows,
                    remaining=str(total - len(rows)),
                    dump=str(path),
                )
                if args.apply and not args.yes:
                    return _EXIT_REFUSED
                return _EXIT_OK
            try:
                _backup(inspected, path)
                deleted = _delete(conn, rows)
            except PlanError as exc:
                _print_plan(
                    mode=mode,
                    deleted=0,
                    rows=rows,
                    remaining=str(total),
                    dump="not created",
                    reason=str(exc),
                )
                return _EXIT_REFUSED
            if deleted != len(rows):
                conn.rollback()
                raise PlanError("deleted count did not match the plan")
            conn.commit()
            _print_plan(
                mode=mode,
                deleted=deleted,
                rows=rows,
                remaining=str(total - deleted),
                dump=str(path),
            )
            return _EXIT_OK
    except PlanError as exc:
        _print_plan(
            mode=mode,
            deleted=0,
            rows=[],
            remaining="not read",
            dump="not created",
            reason=str(exc),
        )
        return _EXIT_REFUSED
    except Exception as exc:
        message = redact(str(exc), url).replace("\n", " ")
        return _refused(f"stopped before delete ({message})", mode=mode)


def main(argv: list[str] | None = None) -> int:
    """CLI entry. Inputs: argv. Output: exit code. Side effects: see run()."""
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
