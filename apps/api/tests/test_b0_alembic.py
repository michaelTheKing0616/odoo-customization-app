"""Oracle for B0-ALEMBIC. One positive and one negative case per acceptance criterion."""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.no_app_db

_API_ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN_PORTS = (
    ":3002",
    ":5433",
    ":5436",
    ":8001",
    ":8002",
    ":8012",
    ":8069",
    ":8070",
    ":8071",
    ":8072",
    ":8073",
    ":11434",
)
_FORBIDDEN_PORT_NUMBERS = frozenset(int(token.removeprefix(":")) for token in _FORBIDDEN_PORTS)
_SAFE_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DISPOSABLE_NAME = re.compile(r"ingenium_[a-z0-9_]+")
_STARTUP_TABLES = (
    "approval_entries",
    "approval_rules",
    "audit_logs",
    "background_jobs",
    "customization_projects",
    "health_check_runs",
    "integration_events",
    "live_demo_copilot_sessions",
    "metadata_snapshots",
    "odoo_connections",
    "promoted_modules",
    "sandbox_validations",
    "script_runs",
    "users",
    "workspaces",
)


def _alembic_config() -> Config:
    alembic_dir = str(_API_ROOT / "alembic")
    if alembic_dir not in sys.path:
        sys.path.insert(0, alembic_dir)
    return Config(str(_API_ROOT / "alembic.ini"))


def _script() -> ScriptDirectory:
    return ScriptDirectory.from_config(_alembic_config())


def _heads_report(heads: tuple[str, ...]) -> str:
    return "\n".join(heads)


def _single_head(heads: tuple[str, ...]) -> bool:
    lines = [line for line in _heads_report(heads).splitlines() if line.strip()]
    return len(lines) == 1


def _sql_text(statement: object) -> str:
    body = getattr(statement, "text", None)
    return body if isinstance(body, str) else str(statement)


def _startup_alters_disabled(statements: list[str]) -> bool:
    return not any("ALTER TABLE" in statement.upper() for statement in statements)


def _startup_sql(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """SQL that ``init_db(bootstrap=True)`` issues when guarded columns are missing.

    The engine is a fake. This must not open the dev App DB.
    """
    import app.db as db

    issued: list[str] = []

    class _Result:
        def scalar(self) -> None:
            return None

        def scalars(self) -> _Result:
            return self

        def all(self) -> list[str]:
            return []

    class _Conn:
        def execute(self, statement: object, *args: object, **kwargs: object) -> _Result:
            issued.append(_sql_text(statement))
            return _Result()

    class _Begin:
        def __enter__(self) -> _Conn:
            return _Conn()

        def __exit__(self, *args: object) -> bool:
            return False

    class _Engine:
        def __init__(self) -> None:
            self.dialect = type("Dialect", (), {"name": "postgresql"})()

        def begin(self) -> _Begin:
            return _Begin()

    class _Inspector:
        def get_table_names(self) -> list[str]:
            return list(_STARTUP_TABLES)

        def get_columns(self, table: str) -> list[dict[str, str]]:
            return []

    monkeypatch.setattr(db.settings, "db_migrations", "off")
    monkeypatch.setattr(db, "engine", _Engine())
    monkeypatch.setattr(db, "inspect", lambda engine: _Inspector())
    monkeypatch.setattr(db.Base.metadata, "create_all", lambda *args, **kwargs: None)

    def _refuse_shared_migrate() -> None:
        raise AssertionError("startup must not migrate a shared database")

    monkeypatch.setattr(db, "run_migrations", _refuse_shared_migrate)
    db.init_db(bootstrap=True)
    return issued


def _ac1_problems(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    problems: list[str] = []
    heads = tuple(_script().get_heads())
    if not _single_head(heads):
        problems.append(f"alembic heads printed {len(heads)} lines")
    alters = [sql for sql in _startup_sql(monkeypatch) if "ALTER TABLE" in sql.upper()]
    if not _startup_alters_disabled(alters):
        problems.append(f"startup issued {len(alters)} ALTER TABLE statements")
    return problems


def _bin(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise AssertionError(f"{name} is not on PATH")
    return found


def _free_port() -> int:
    for _ in range(20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        if port not in _FORBIDDEN_PORT_NUMBERS:
            return port
    raise AssertionError("no disposable port")


def _refuse_port(port: int) -> None:
    if port in _FORBIDDEN_PORT_NUMBERS:
        raise AssertionError(f"refusing forbidden port {port}")


def _refuse_disposable_url(url: str) -> None:
    for token in _FORBIDDEN_PORTS:
        if token in url:
            raise AssertionError(f"refusing forbidden port {token}")
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise AssertionError("disposable database must stay on localhost")
    if parsed.port in _FORBIDDEN_PORT_NUMBERS:
        raise AssertionError(f"refusing forbidden port {parsed.port}")
    name = parsed.path.lstrip("/")
    if _DISPOSABLE_NAME.fullmatch(name) is None:
        raise AssertionError("disposable database name must start with ingenium_")


def _tail(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout + "\n" + result.stderr)[-4000:]


def _nonempty_lines(payload: str) -> list[str]:
    return [line.strip() for line in payload.splitlines() if line.strip()]


def _uv(args: list[str], url: str) -> subprocess.CompletedProcess[str]:
    """Run a uv command aimed only at this disposable database."""
    _refuse_disposable_url(url)
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    env.pop("INGENIUM_LIVE_INFRA", None)
    env.pop("PYTEST_ADDOPTS", None)
    for key in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"):
        env.pop(key, None)
    for key in list(env):
        if key.startswith("PYTEST_"):
            env.pop(key, None)
    return subprocess.run(
        ["uv", "run", *args],
        cwd=_API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _child_database_name(url: str) -> str:
    """The child process must resolve this database before any upgrade runs."""
    result = _uv(
        [
            "python",
            "-c",
            "from app.settings import settings; print(settings.database_url.rsplit('/', 1)[-1])",
        ],
        url,
    )
    if result.returncode != 0:
        raise AssertionError(_tail(result))
    lines = _nonempty_lines(result.stdout)
    if not lines:
        raise AssertionError("child did not report its database name")
    return lines[-1]


def _connect(url: str):
    _refuse_disposable_url(url)
    return create_engine(url, poolclass=NullPool)


def _table_exists(url: str, table: str) -> bool:
    if _SAFE_IDENT.fullmatch(table) is None:
        raise AssertionError(table)
    engine = _connect(url)
    try:
        with engine.connect() as conn:
            found = conn.execute(
                text(
                    "SELECT 1 FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename = :name"
                ),
                {"name": table},
            ).scalar()
            return found is not None
    finally:
        engine.dispose()


def _record_count(url: str) -> int:
    engine = _connect(url)
    try:
        with engine.connect() as conn:
            names = [
                str(name)
                for name in conn.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'public' ORDER BY tablename"
                    )
                ).scalars()
            ]
            total = 0
            for name in names:
                if _SAFE_IDENT.fullmatch(name) is None:
                    raise AssertionError(f"unexpected table name {name}")
                counted = conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
                total += int(counted or 0)
            return total
    finally:
        engine.dispose()


_ADMIN_DB = "ingenium_b0_cluster_admin"


class _DisposableCluster:
    """A private Postgres cluster. App databases created here are ingenium_*."""

    def __init__(self, data: Path, port: int) -> None:
        self.data = data
        self.port = port
        self.created: list[str] = []
        self._initdb = _bin("initdb")
        self._pg_ctl = _bin("pg_ctl")

    def start(self) -> None:
        _refuse_port(self.port)
        init = subprocess.run(
            [
                self._initdb,
                "-D",
                str(self.data),
                "-U",
                "ingenium",
                "--auth=trust",
                "--encoding=UTF8",
                "--locale=C",
                "--no-sync",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if init.returncode != 0:
            raise AssertionError((init.stderr or init.stdout)[-2000:])
        start = subprocess.run(
            [
                self._pg_ctl,
                "-D",
                str(self.data),
                "-l",
                str(self.data / "server.log"),
                "-w",
                "-o",
                f"-p {self.port} -c listen_addresses=127.0.0.1",
                "start",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if start.returncode != 0:
            log = ""
            log_path = self.data / "server.log"
            if log_path.exists():
                log = log_path.read_text(errors="replace")[-2000:]
            raise AssertionError((start.stderr or start.stdout) + "\n" + log)
        # The test db guard refuses the maintenance database ``postgres``, so the
        # admin connection uses its own ingenium_ database made by createdb.
        made = subprocess.run(
            [_bin("createdb"), "-h", "127.0.0.1", "-p", str(self.port), "-U", "ingenium", _ADMIN_DB],
            capture_output=True,
            text=True,
            check=False,
        )
        if made.returncode != 0:
            raise AssertionError((made.stderr or made.stdout)[-2000:])

    def database_url(self, name: str) -> str:
        if _DISPOSABLE_NAME.fullmatch(name) is None:
            raise AssertionError(f"refusing database name {name}")
        _refuse_port(self.port)
        admin = create_engine(
            f"postgresql+psycopg://ingenium@127.0.0.1:{self.port}/{_ADMIN_DB}",
            isolation_level="AUTOCOMMIT",
            poolclass=NullPool,
        )
        try:
            with admin.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"),
                    {"name": name},
                ).scalar()
                if exists:
                    raise AssertionError(f"{name} already exists on the disposable cluster")
                conn.execute(text(f'CREATE DATABASE "{name}"'))
        finally:
            admin.dispose()
        self.created.append(name)
        url = f"postgresql+psycopg://ingenium@127.0.0.1:{self.port}/{name}"
        _refuse_disposable_url(url)
        return url

    def drop_created(self) -> None:
        if not self.created:
            return
        _refuse_port(self.port)
        admin = create_engine(
            f"postgresql+psycopg://ingenium@127.0.0.1:{self.port}/{_ADMIN_DB}",
            isolation_level="AUTOCOMMIT",
            poolclass=NullPool,
        )
        try:
            with admin.connect() as conn:
                for name in list(self.created):
                    if _DISPOSABLE_NAME.fullmatch(name) is None:
                        continue
                    conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        finally:
            admin.dispose()
            self.created.clear()

    def stop(self) -> None:
        try:
            self.drop_created()
        finally:
            subprocess.run(
                [self._pg_ctl, "-D", str(self.data), "-m", "immediate", "-w", "stop"],
                capture_output=True,
                text=True,
                check=False,
            )


@pytest.fixture(scope="module")
def disposable_cluster(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_DisposableCluster]:
    cluster = _DisposableCluster(tmp_path_factory.mktemp("ingenium_b0_pg") / "data", _free_port())
    try:
        cluster.start()
        yield cluster
    finally:
        cluster.stop()


def test_ac1_positive_upgrade_head_drift_on_fresh_db(
    disposable_cluster: _DisposableCluster,
) -> None:
    url = disposable_cluster.database_url("ingenium_b0_ac1")
    name = url.rsplit("/", 1)[-1]
    assert _child_database_name(url) == name
    upgrade = _uv(["alembic", "upgrade", "head"], url)
    assert upgrade.returncode == 0, _tail(upgrade)
    assert _table_exists(url, "odoo_connections") is True
    heads = _uv(["alembic", "heads"], url)
    assert heads.returncode == 0, _tail(heads)
    lines = _nonempty_lines(heads.stdout)
    assert len(lines) == 1, heads.stdout
    drift = _uv(["pytest", "-q", "tests/test_alembic_drift.py"], url)
    assert drift.returncode == 0, _tail(drift)
    assert " skipped" not in drift.stdout, drift.stdout


def test_ac1_negative_multiple_heads_or_startup_alter_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _single_head(("rev_a", "rev_b")) is False
    assert _startup_alters_disabled(
        ["ALTER TABLE users ADD COLUMN display_name VARCHAR(60)"]
    ) is False
    assert _ac1_problems(monkeypatch) == []


def _apply_docker_guard(monkeypatch: pytest.MonkeyPatch):
    """Run the suite's docker block. ``--noconftest`` does not install it for us."""
    monkeypatch.delenv("INGENIUM_LIVE_INFRA", raising=False)
    from tests.conftest import _no_real_infra_by_default

    guard = _no_real_infra_by_default.__wrapped__(monkeypatch)
    next(guard)
    return guard


def test_ac2_positive_isolated_sandbox_blocks_real_docker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.sandbox import DEV_PORTS, SANDBOX_PREFIX, sandbox_stack_for_major

    stack = sandbox_stack_for_major(19)
    assert stack.project == f"{SANDBOX_PREFIX}v19"
    assert stack.odoo_container.startswith(SANDBOX_PREFIX)
    assert stack.db_container.startswith(SANDBOX_PREFIX)
    assert stack.port not in DEV_PORTS
    guard = _apply_docker_guard(monkeypatch)
    try:
        with pytest.raises(RuntimeError, match="real docker is blocked in tests"):
            subprocess.run(["docker", "ps"], check=False)
    finally:
        guard.close()


def test_ac2_negative_shared_dev_stack_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.sandbox import SANDBOX_PREFIX, SandboxGuardError, SandboxStack, assert_isolated

    monkeypatch.setenv("INGENIUM_LIVE_INFRA", "1")
    dev_stack = SandboxStack(
        compose=Path("docker-compose.yml"),
        project="odoo-custom",
        url="http://127.0.0.1:8069",
        odoo_service="odoo",
        odoo_container="odoo20",
        db_container="odoo20-db",
        db_host="db",
        port=8069,
    )
    with pytest.raises(SandboxGuardError):
        assert_isolated(dev_stack)
    from app.sandbox import sandbox_stack_for_major

    assert sandbox_stack_for_major(19).project.startswith(SANDBOX_PREFIX)


def _refuse_forbidden_url(url: str) -> None:
    if not url.startswith("sqlite:///"):
        raise AssertionError("disposable plan DB must be a local sqlite file")
    for token in _FORBIDDEN_PORTS:
        if token in url:
            raise AssertionError(f"refusing forbidden port {token}")


def _zero_records(record_writes: int) -> bool:
    return record_writes == 0


def _plan_apply_rows(engine: object) -> int:
    from sqlalchemy.engine import Engine

    if not isinstance(engine, Engine):
        raise TypeError("expected an Engine")
    with engine.connect() as conn:
        counted = conn.execute(text("SELECT COUNT(*) FROM plan_apply")).scalar()
    return int(counted or 0)


def test_ac3_positive_second_upgrade_writes_zero_records(
    disposable_cluster: _DisposableCluster,
) -> None:
    url = disposable_cluster.database_url("ingenium_b0_ac3")
    name = url.rsplit("/", 1)[-1]
    assert _child_database_name(url) == name
    first = _uv(["alembic", "upgrade", "head"], url)
    assert first.returncode == 0, _tail(first)
    assert _table_exists(url, "odoo_connections") is True
    before = _record_count(url)
    assert before > 0
    second = _uv(["alembic", "upgrade", "head"], url)
    assert second.returncode == 0, _tail(second)
    second_writes = _record_count(url) - before
    assert second_writes == 0


def test_ac3_negative_second_insert_does_not_write_zero(tmp_path: Path) -> None:
    script = _script()
    head = script.get_heads()[0]
    first_plan = script._upgrade_revs(head, "base")
    assert _zero_records(len(first_plan)) is False

    url = f"sqlite:///{tmp_path / 'ingenium_b0_alembic_replay.db'}"
    _refuse_forbidden_url(url)
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE plan_apply (id INTEGER PRIMARY KEY, plan TEXT)"))
            conn.execute(text("INSERT INTO plan_apply (plan) VALUES ('head')"))
        before = _plan_apply_rows(engine)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO plan_apply (plan) VALUES ('head')"))
        second_writes = _plan_apply_rows(engine) - before
    finally:
        engine.dispose()
    assert second_writes == 1
    assert _zero_records(second_writes) is False
