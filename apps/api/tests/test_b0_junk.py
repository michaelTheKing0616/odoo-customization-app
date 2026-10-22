"""B0-JUNK: dry-run lists fixture rows; --apply deletes only with --yes on a disposable DB.

The disposable cluster is created and dropped in this test. --apply is not used
against any other database. The maintenance commands createdb and dropdb talk
to the postgres database of this private cluster only, and only for names this
test appended to its own list.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.no_app_db

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / "scripts" / "cleanup_test_connections.py"
_FORBIDDEN_PORTS = frozenset(
    {3002, 5433, 5436, 8001, 8002, 8012, 8069, 8070, 8071, 8072, 8073, 11434}
)
_DB_NAME = re.compile(r"ingenium_[a-z0-9_]+")
_SECRET = "red-herring"

_UNUSED = (
    ("Alice victim conn", "odoo_alice"),
    ("Granted client", "odoo_granted"),
    ("Matrix conn", "odoo_matrix"),
    ("Other client", "odoo_other"),
    ("Other client extra", "odoo_other_extra"),
    ("code-studio", "odoo_code_studio"),
    ("fake-m3", "odoo_fake_m3"),
    ("fake-ops", "odoo_fake_ops"),
    ("role-matrix", "odoo_role_matrix"),
)
_KEPT_NAMES = (
    ("Acme Books", "acme_books"),
    ("Matrix connection", "odoo_matrix_real"),
)
_USED_AI = ("Matrix conn", "odoo_matrix_used")
_USED_LIVE = ("role-matrix", "odoo_role_used")


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
        if port not in _FORBIDDEN_PORTS:
            return port
    raise AssertionError("no disposable port")


def _require_disposable(port: int, database: str) -> None:
    if port in _FORBIDDEN_PORTS:
        raise AssertionError(f"refusing port {port}")
    if _DB_NAME.fullmatch(database) is None or database == "odoo_custom":
        raise AssertionError(f"refusing database {database}")


class _Cluster:
    """Private Postgres. Databases this object drops are ones it created."""

    def __init__(self, data: Path, port: int) -> None:
        self.data = data
        self.port = port
        self.created: list[str] = []
        self.started = False
        self.initdb = _bin("initdb")
        self.pg_ctl = _bin("pg_ctl")
        self.createdb = _bin("createdb")
        self.dropdb = _bin("dropdb")

    def start(self) -> None:
        _require_disposable(self.port, "ingenium_b0_junk_cluster")
        init = subprocess.run(
            [
                self.initdb,
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
            timeout=60,
        )
        if init.returncode != 0:
            raise AssertionError((init.stderr or init.stdout)[-2000:])
        start = subprocess.run(
            [
                self.pg_ctl,
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
            timeout=60,
        )
        if start.returncode != 0:
            log = ""
            log_path = self.data / "server.log"
            if log_path.exists():
                log = log_path.read_text(errors="replace")[-2000:]
            raise AssertionError((start.stderr or start.stdout) + "\n" + log)
        self.started = True

    def create(self, name: str) -> None:
        _require_disposable(self.port, name)
        if name in self.created:
            raise AssertionError(f"{name} already created in this run")
        made = subprocess.run(
            [
                self.createdb,
                "-h",
                "127.0.0.1",
                "-p",
                str(self.port),
                "-U",
                "ingenium",
                name,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if made.returncode != 0:
            raise AssertionError((made.stderr or made.stdout)[-2000:])
        self.created.append(name)

    def drop_created(self) -> None:
        if not self.started:
            return
        for name in list(self.created):
            _require_disposable(self.port, name)
            if name in {"postgres", "template0", "template1"}:
                raise AssertionError(name)
            subprocess.run(
                [
                    self.dropdb,
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(self.port),
                    "-U",
                    "ingenium",
                    "--if-exists",
                    "--force",
                    name,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        self.created.clear()

    def stop(self) -> None:
        error: Exception | None = None
        try:
            self.drop_created()
        except Exception as exc:
            error = exc
        if self.started:
            subprocess.run(
                [self.pg_ctl, "-D", str(self.data), "-m", "immediate", "-w", "stop"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.started = False
        if error is not None:
            raise error


@pytest.fixture(scope="module")
def cluster(tmp_path_factory: pytest.TempPathFactory) -> object:
    item = _Cluster(tmp_path_factory.mktemp("ingenium_b0_junk_pg") / "data", _free_port())
    try:
        item.start()
        yield item
    finally:
        item.stop()


def _connect(port: int, database: str) -> psycopg.Connection:
    _require_disposable(port, database)
    conn = psycopg.connect(
        host="127.0.0.1",
        port=port,
        dbname=database,
        user="ingenium",
        password=_SECRET,
        connect_timeout=5,
    )
    conn.autocommit = True
    return conn


def _seed(port: int, database: str) -> None:
    _require_disposable(port, database)
    with _connect(port, database) as conn:
        conn.execute(
            """
            CREATE TABLE odoo_connections (
                id varchar(36) PRIMARY KEY,
                name varchar(200) NOT NULL,
                db_name varchar(200) NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE ai_sessions (
                id varchar(36) PRIMARY KEY,
                connection_id varchar(36) REFERENCES odoo_connections (id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE live_demo_copilot_sessions (
                id varchar(36) PRIMARY KEY,
                connection_id varchar(36) REFERENCES odoo_connections (id) ON DELETE SET NULL
            )
            """
        )
        rows = list(_UNUSED) + list(_KEPT_NAMES) + [_USED_AI, _USED_LIVE]
        ids: dict[tuple[str, str], str] = {}
        for name, db_name in rows:
            row_id = str(uuid.uuid4())
            ids[(name, db_name)] = row_id
            conn.execute(
                "INSERT INTO odoo_connections (id, name, db_name) VALUES (%s, %s, %s)",
                (row_id, name, db_name),
            )
        conn.execute(
            "INSERT INTO ai_sessions (id, connection_id) VALUES (%s, %s)",
            (str(uuid.uuid4()), ids[_USED_AI]),
        )
        conn.execute(
            "INSERT INTO live_demo_copilot_sessions (id, connection_id) VALUES (%s, %s)",
            (str(uuid.uuid4()), ids[_USED_LIVE]),
        )


def _new_database(cluster: _Cluster) -> str:
    name = f"ingenium_b0_junk_{uuid.uuid4().hex}"
    cluster.create(name)
    _seed(cluster.port, name)
    return name


def _run(database_url: str, dump_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["B0_JUNK_DUMP_DIR"] = str(dump_dir)
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        env=env,
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _url(port: int, database: str) -> str:
    _require_disposable(port, database)
    return f"postgresql://ingenium:{_SECRET}@127.0.0.1:{port}/{database}"


def _field(stdout: str, key: str) -> str:
    prefix = f"{key}: "
    found = [line[len(prefix) :] for line in stdout.splitlines() if line.startswith(prefix)]
    assert len(found) == 1, stdout
    return found[0]


def _pairs(stdout: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    pending: str | None = None
    for line in stdout.splitlines():
        if line.startswith("connection: "):
            assert pending is None
            pending = line[len("connection: ") :]
        elif line.startswith("database: "):
            assert pending is not None
            pairs.append((pending, line[len("database: ") :]))
            pending = None
    assert pending is None
    return pairs


def _no_secret(result: subprocess.CompletedProcess[str]) -> None:
    blob = result.stdout + "\n" + result.stderr
    assert _SECRET not in blob


def _connection_count(port: int, database: str) -> int:
    with _connect(port, database) as conn:
        row = conn.execute("SELECT COUNT(*) FROM odoo_connections").fetchone()
    assert row is not None
    return int(row[0])


def _table_rows(port: int, database: str) -> int:
    total = 0
    with _connect(port, database) as conn:
        names = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        ).fetchall()
        for (name,) in names:
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(name)) is None:
                raise AssertionError(name)
            counted = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()
            assert counted is not None
            total += int(counted[0])
    return total


def _names(port: int, database: str) -> list[tuple[str, str]]:
    with _connect(port, database) as conn:
        rows = conn.execute(
            "SELECT name, db_name FROM odoo_connections ORDER BY name, db_name"
        ).fetchall()
    return [(str(name), str(db_name)) for name, db_name in rows]


def test_ac1_positive_dry_run_lists_unused_fixture_rows_and_deletes_zero(
    cluster: _Cluster, tmp_path: Path
) -> None:
    database = _new_database(cluster)
    before = _table_rows(cluster.port, database)
    result = _run(_url(cluster.port, database), tmp_path)
    _no_secret(result)
    assert result.returncode == 0, result.stderr
    assert _field(result.stdout, "mode") == "dry-run"
    assert _field(result.stdout, "deleted") == "0"
    assert _field(result.stdout, "connection_count") == str(len(_UNUSED))
    assert _field(result.stdout, "database_count") == str(len(_UNUSED))
    assert _field(result.stdout, "remaining_count") == "4"
    assert _field(result.stdout, "databases_dropped") == "0"
    assert _pairs(result.stdout) == list(_UNUSED)
    dump = Path(_field(result.stdout, "pg_dump -Fc"))
    assert dump.is_absolute()
    assert not dump.exists()
    assert _table_rows(cluster.port, database) == before

    yes_only = _run(_url(cluster.port, database), tmp_path, "--yes")
    _no_secret(yes_only)
    assert yes_only.returncode == 0, yes_only.stderr
    assert _field(yes_only.stdout, "deleted") == "0"
    assert not Path(_field(yes_only.stdout, "pg_dump -Fc")).exists()
    assert _table_rows(cluster.port, database) == before


def test_ac1_negative_apply_without_yes_deletes_zero(cluster: _Cluster, tmp_path: Path) -> None:
    database = _new_database(cluster)
    before = _table_rows(cluster.port, database)
    result = _run(_url(cluster.port, database), tmp_path, "--apply")
    _no_secret(result)
    assert result.returncode != 0
    assert _field(result.stdout, "mode") == "apply-refused"
    assert _field(result.stdout, "deleted") == "0"
    assert _field(result.stdout, "databases_dropped") == "0"
    assert _pairs(result.stdout) == list(_UNUSED)
    assert not Path(_field(result.stdout, "pg_dump -Fc")).exists()
    assert _table_rows(cluster.port, database) == before


@pytest.mark.parametrize(
    ("url", "needle"),
    [
        ("postgresql://u:red-herring@127.0.0.1:5432/odoo_custom", "odoo_custom"),
        ("postgresql://u:red-herring@127.0.0.1:5433/ingenium_probe", "5433"),
        ("postgresql://u:red-herring@127.0.0.1:5433/odoo_custom", "5433"),
        ("postgresql://u:red-herring@10.0.0.8:5432/ingenium_probe", "not loopback"),
        (
            "postgresql://u:red-herring@127.0.0.1:5432/ingenium_probe?dbname=odoo_custom",
            "odoo_custom",
        ),
        (
            "postgresql://u:red-herring@127.0.0.1:5432/ingenium_probe?host=10.0.0.8",
            "not loopback",
        ),
        (
            "postgresql://u:red-herring@127.0.0.1:5432/ingenium_probe?port=5433",
            "5433",
        ),
    ],
)
def test_ac1_negative_refuses_forbidden_target_without_connecting(
    url: str, needle: str, tmp_path: Path
) -> None:
    result = _run(url, tmp_path)
    _no_secret(result)
    assert result.returncode != 0
    assert "refusing to connect:" in result.stdout
    assert needle in result.stdout
    assert _field(result.stdout, "deleted") == "0"
    assert _field(result.stdout, "connection_count") == "0"
    assert _field(result.stdout, "pg_dump -Fc") == "not created"
    assert _field(result.stdout, "databases_dropped") == "0"
    assert list(tmp_path.iterdir()) == []


def test_script_does_not_drop_databases() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "DROP DATABASE" not in source.upper()


def _cleanup_module() -> object:
    import importlib.util

    spec = importlib.util.spec_from_file_location("b0_junk_cleanup", _SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("cleanup script could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_env_file_url_is_refused_without_connecting(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'export DATABASE_URL="postgresql://u:red-herring@127.0.0.1:5433/ingenium_probe"\n',
        encoding="utf-8",
    )
    module = _cleanup_module()
    url = module._database_url_in_file(env_file)
    assert isinstance(url, str)
    reason = module.inspect_target(url)
    assert reason == "port 5433 is forbidden"


def test_ac2_positive_apply_leaves_the_real_rows(cluster: _Cluster, tmp_path: Path) -> None:
    database = _new_database(cluster)
    result = _run(_url(cluster.port, database), tmp_path, "--apply", "--yes")
    _no_secret(result)
    assert result.returncode == 0, result.stderr
    assert _field(result.stdout, "deleted") == str(len(_UNUSED))
    assert _field(result.stdout, "remaining_count") == "4"
    assert _field(result.stdout, "databases_dropped") == "0"
    dump = Path(_field(result.stdout, "pg_dump -Fc"))
    assert dump.is_file()
    assert dump.stat().st_size > 0
    assert _connection_count(cluster.port, database) == 4
    assert _names(cluster.port, database) == sorted(list(_KEPT_NAMES) + [_USED_AI, _USED_LIVE])


def test_ac2_negative_dry_run_leaves_every_row(cluster: _Cluster, tmp_path: Path) -> None:
    database = _new_database(cluster)
    result = _run(_url(cluster.port, database), tmp_path)
    _no_secret(result)
    assert result.returncode == 0, result.stderr
    assert _field(result.stdout, "deleted") == "0"
    assert _field(result.stdout, "remaining_count") == "4"
    assert _connection_count(cluster.port, database) == 13


def test_ac4_negative_first_apply_deletes_fixture_rows(cluster: _Cluster, tmp_path: Path) -> None:
    database = _new_database(cluster)
    before = _table_rows(cluster.port, database)
    result = _run(_url(cluster.port, database), tmp_path, "--apply", "--yes")
    _no_secret(result)
    assert result.returncode == 0, result.stderr
    deleted = int(_field(result.stdout, "deleted"))
    assert deleted == len(_UNUSED)
    assert deleted != 0
    assert _table_rows(cluster.port, database) == before - deleted


def test_ac4_positive_second_apply_writes_zero(cluster: _Cluster, tmp_path: Path) -> None:
    database = _new_database(cluster)
    first = _run(_url(cluster.port, database), tmp_path, "--apply", "--yes")
    _no_secret(first)
    assert first.returncode == 0, first.stderr
    assert int(_field(first.stdout, "deleted")) == len(_UNUSED)
    mid = _table_rows(cluster.port, database)
    second = _run(_url(cluster.port, database), tmp_path, "--apply", "--yes")
    _no_secret(second)
    assert second.returncode == 0, second.stderr
    assert _field(second.stdout, "deleted") == "0"
    assert _field(second.stdout, "connection_count") == "0"
    assert _field(second.stdout, "databases_dropped") == "0"
    assert not Path(_field(second.stdout, "pg_dump -Fc")).exists()
    assert _table_rows(cluster.port, database) == mid
    assert _connection_count(cluster.port, database) == 4
