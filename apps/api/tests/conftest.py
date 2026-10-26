"""Reset workspace kill-switch state before TRUST API tests."""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import uuid
from pathlib import Path


def _test_pg_port() -> int:
    """Loopback Postgres port. Default 54329. ``INGENIUM_TEST_PG_PORT`` overrides it.

    Inputs: none. Output: a TCP port. Empty env is the default.
    Side effects: none. A non-numeric value raises before any socket opens.
    """
    raw = os.environ.get("INGENIUM_TEST_PG_PORT", "").strip() or "54329"
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise RuntimeError("INGENIUM_TEST_PG_PORT must be a TCP port")
    return int(raw)


# B0-ISO: throwaway App DB before any import of app.settings.
# Loopback host, name starts with ingenium_. Assignment does not open a socket.
# A second exec of this module (pytest's assertion rewriter) must keep the name.
if "_B0_ISO_SESSION_READY" not in globals():
    _B0_ISO_PG_PORT = _test_pg_port()
    _B0_ISO_DB_NAME = f"ingenium_b0_iso_{uuid.uuid4().hex}"
    _B0_ISO_DATABASE_URL = (
        f"postgresql+psycopg://ingenium:ingenium@127.0.0.1:{_B0_ISO_PG_PORT}/{_B0_ISO_DB_NAME}"
    )
    os.environ["DATABASE_URL"] = _B0_ISO_DATABASE_URL
    # Unwrapped psycopg connect, saved when the guard installs, so session
    # cleanup can drop only the database this process created.
    _B0_ISO_DB_CREATED = False
    _B0_ISO_REAL_PG_CONNECT = None


def _session_maintenance_connect():
    """Open the loopback catalog so this process can create its own database.

    Inputs: none. Output: an autocommit connection.
    Side effects: one socket to 127.0.0.1 on the session port. Callers may run only
    CREATE DATABASE or DROP DATABASE for ``_B0_ISO_DB_NAME``. The session
    ``DATABASE_URL`` stays on that ingenium_ name.
    """
    from urllib.parse import urlparse

    import psycopg

    if not _B0_ISO_DB_NAME.startswith("ingenium_b0_iso_"):
        raise RuntimeError("session database name is not ingenium_b0_iso_")
    parsed = urlparse(
        _B0_ISO_DATABASE_URL.replace("postgresql+psycopg", "postgresql", 1)
    )
    if (parsed.hostname or "") not in {"127.0.0.1", "::1", "localhost"}:
        raise RuntimeError("session database host is not loopback")
    real = _B0_ISO_REAL_PG_CONNECT
    if real is None:
        real = getattr(psycopg.connect, "_b0_iso_real", None)
    if real is None:
        if getattr(psycopg.connect, "_b0_iso_guard", False):
            raise RuntimeError("session database maintenance connect is unavailable")
        real = psycopg.Connection.connect.__func__
    return real(
        psycopg.Connection,
        "",
        host=parsed.hostname,
        port=parsed.port or _B0_ISO_PG_PORT,
        user=parsed.username or "",
        password=parsed.password or "",
        dbname="postgres",
        autocommit=True,
    )


def _drop_session_database() -> None:
    """Drop the ingenium_ database this process created. No other name."""
    global _B0_ISO_DB_CREATED
    if not _B0_ISO_DB_CREATED:
        return
    if not _B0_ISO_DB_NAME.startswith("ingenium_b0_iso_"):
        return
    from psycopg import sql

    try:
        from app.db import engine

        engine.dispose()
    except Exception:  # noqa: BLE001 — exit cleanup must still attempt DROP
        pass
    conn = _session_maintenance_connect()
    try:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (_B0_ISO_DB_NAME,),
        )
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(_B0_ISO_DB_NAME)
            )
        )
    finally:
        conn.close()
    _B0_ISO_DB_CREATED = False


def _ensure_session_database() -> None:
    """Create this process's throwaway ingenium_ database before any test connects.

    Inputs: none. Output: none.
    Side effects: CREATE DATABASE for ``_B0_ISO_DB_NAME``, and an atexit DROP
    of that name only.
    """
    global _B0_ISO_DB_CREATED
    from psycopg import sql
    from psycopg.errors import DuplicateDatabase

    conn = _session_maintenance_connect()
    try:
        try:
            conn.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(_B0_ISO_DB_NAME))
            )
        except DuplicateDatabase:
            return
    finally:
        conn.close()
    _B0_ISO_DB_CREATED = True
    atexit.register(_drop_session_database)


if "_B0_ISO_SESSION_READY" not in globals():
    _ensure_session_database()
    _B0_ISO_SESSION_READY = True

# TRUST-1 defaults new connections to observer; mutating API tests expect standard unless
# they explicitly set write_mode (see test_trust1_write_mode.py).
os.environ.setdefault("TEST_DEFAULT_WRITE_MODE", "standard")
# The API rate limiter is per-process; a full-suite run trips 120/min and turns unrelated tests into 429s.
# Rate-limit tests pass an explicit limit, so switch the default off for the suite.
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")
# Before any test import opens the AI cache: never default to ~/.ingenium during collection.
_AI_CACHE_SESSION_DIR = tempfile.mkdtemp(prefix="ingenium_ai_cache_")
os.environ.setdefault(
    "INGENIUM_AI_CACHE_PATH",
    str(Path(_AI_CACHE_SESSION_DIR) / "session.sqlite"),
)
atexit.register(lambda: shutil.rmtree(_AI_CACHE_SESSION_DIR, ignore_errors=True))

import pytest


@pytest.fixture(autouse=True)
def _unpause_workspace_writes(request: pytest.FixtureRequest):
    """Put swap-module tests back on their SQLite engine, and everyone else on Postgres.

    Inputs: the current test node. Output: none.
    Side effects: rebinds ``app.db.engine`` for this test, then restores the
    session Postgres engine after the test. ``no_app_db`` tests skip the
    workspace query. Does not open a socket for a SQLite engine.
    """
    path = getattr(request.node, "path", None)
    name = path.name if path is not None else ""
    saved = _SWAP_ENGINES.get(name)
    if saved is not None:
        _apply_engine(saved[0], saved[1])
        yield
        _restore_session_engine()
        return
    _restore_session_engine()
    if "no_app_db" in request.keywords:
        yield
        _restore_session_engine()
        return
    from app.account_models import Workspace
    from app.db import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        # This test is a strict xfail while billing_plans has no "internal" row.
        # Earlier tests commit that row into the session database, so the suite
        # would pass and the strict mark would fail. Remove only that plan.
        if getattr(request.node, "name", "") == "test_admin_feature_flags_and_deactivate":
            _drop_seeded_internal_plan(db)
        for ws in db.query(Workspace).all():
            if ws.writes_paused:
                ws.writes_paused = False
                db.add(ws)
        db.commit()
    finally:
        db.close()
    yield
    _restore_session_engine()


@pytest.fixture(autouse=True)
def _isolate_ai_process_state():
    """Undo per-test leaks of process-global AI state (order-independent runs).

    Several tests assign ``settings.ai_intent_llm`` / ``settings.ai_llm_tier_fast``
    or ``os.environ`` directly; process caches (Flash enrich, app design) and the
    grounding contextvar also outlive a test. Snapshot before, restore after.
    """
    from app.settings import settings

    settings_snapshot = dict(vars(settings))
    env_snapshot = dict(os.environ)
    yield
    vars(settings).clear()
    vars(settings).update(settings_snapshot)
    for key in set(os.environ) - set(env_snapshot):
        del os.environ[key]
    for key, value in env_snapshot.items():
        if os.environ.get(key) != value:
            os.environ[key] = value
    try:
        from app.ai_conversation.grounding import set_grounding
        from app.ai_conversation.understand import clear_enrich_cache

        clear_enrich_cache()
        set_grounding(None)
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture(autouse=True)
def _no_real_infra_by_default(monkeypatch):
    """Tests use fakes for Docker/sandbox unless INGENIUM_LIVE_INFRA=1 (a test once wiped a dev stack).

    Any real `docker ...` subprocess raises, and the sandbox reports Docker as unavailable, so code
    paths degrade the way they do without Docker. Tests that need a sandbox inject a fake installer."""
    import os
    import subprocess

    if os.environ.get("INGENIUM_LIVE_INFRA") == "1":
        yield
        return
    real_run, real_popen = subprocess.run, subprocess.Popen

    def _is_docker(cmd) -> bool:
        first = cmd[0] if isinstance(cmd, (list, tuple)) and cmd else (cmd.split()[0] if isinstance(cmd, str) and cmd else "")
        return str(first).rsplit("/", 1)[-1] in {"docker", "docker-compose"}

    def run(cmd, *a, **k):
        if _is_docker(cmd):
            raise RuntimeError("real docker is blocked in tests (set INGENIUM_LIVE_INFRA=1)")
        return real_run(cmd, *a, **k)

    class Popen(real_popen):  # type: ignore[misc,valid-type]
        def __init__(self, cmd, *a, **k):
            if _is_docker(cmd):
                raise RuntimeError("real docker is blocked in tests (set INGENIUM_LIVE_INFRA=1)")
            super().__init__(cmd, *a, **k)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", Popen)
    try:
        import app.sandbox as _sb

        monkeypatch.setattr(_sb, "sandbox_docker_status", lambda: (False, "Docker is faked in tests"))
    except Exception:  # noqa: BLE001
        pass
    monkeypatch.setenv("INGENIUM_AGENT_SANDBOX", "off")
    yield


def _close_ai_cache() -> None:
    """Drop the process-global sqlite handle so the next test opens its own file."""
    from app.ai_client import ai_cache

    with ai_cache._lock:
        conn = ai_cache._conn
        ai_cache._conn = None
        ai_cache._conn_path = ""
        ai_cache._snap_seen.clear()
        if conn is not None:
            conn.close()


@pytest.fixture(autouse=True)
def _per_test_ai_cache_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """AI cache path set per test. Nothing in the suite reads ~/.ingenium/ai_cache.sqlite."""
    _close_ai_cache()
    monkeypatch.setenv("INGENIUM_AI_CACHE_PATH", str(tmp_path / "ai_cache.sqlite"))
    yield
    _close_ai_cache()


@pytest.fixture(autouse=True)
def _vertex_only_when_live_ai(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Real Vertex stays closed unless this test is marked live_ai and the opt-in env is set."""
    if os.environ.get("INGENIUM_LIVE_AI") == "1" and "live_ai" in request.keywords:
        monkeypatch.setenv("INGENIUM_LIVE_AI_ACTIVE", "1")
    yield


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live_ai: real Vertex calls; skipped unless INGENIUM_LIVE_AI=1",
    )


class _IngeniumURLModule(pytest.Module):
    """Restore the session ingenium_ URL before this test module is imported."""

    def _getobj(self):  # type: ignore[no-untyped-def]
        os.environ["DATABASE_URL"] = _B0_ISO_DATABASE_URL
        import sys

        if "app.settings" in sys.modules:
            from app.settings import settings

            settings.database_url = _B0_ISO_DATABASE_URL
        name = Path(self.path).name
        if name not in _ENGINE_SWAP_MODULES:
            _restore_session_engine()
        obj = super()._getobj()
        if name in _ENGINE_SWAP_MODULES:
            _SWAP_ENGINES[name] = (_session_db.engine, _session_db.SessionLocal)
            _restore_session_engine()
        return obj


def pytest_pycollect_makemodule(module_path: Path, parent: object):  # type: ignore[no-untyped-def]
    """One module's import-time DATABASE_URL must not leak into the next module."""
    return _IngeniumURLModule.from_parent(parent, path=module_path)


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    """Drop this process's ingenium_ database before the interpreter exits."""
    _drop_session_database()


@pytest.fixture(autouse=True)
def _install_api_host_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-pin this conftest's guard. Another suite file execs a second guard over socket.*."""
    monkeypatch.setattr(_socket, "getaddrinfo", _guarded_getaddrinfo)
    monkeypatch.setattr(_socket, "create_connection", _guarded_create_connection)


# --- DB target guard (B0-DBGUARD): fail before any socket call. ----------------------------
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _db_endpoint(url: str) -> tuple[str, str]:
    """Return (effective host, effective database). String parse only; no DNS and no socket.

    Effective host is query ``host`` or ``hostaddr`` when set, otherwise the
    authority host. When both are set, both must be loopback; a non-loopback
    value is the one returned. Effective database is query ``dbname`` when set,
    otherwise the path database. A query that only repeats a loopback host and
    an ``ingenium_`` name stays on that safe target.
    """
    from urllib.parse import parse_qsl, unquote, urlparse

    def norm_host(value: str) -> str:
        host = value.strip().rstrip(".").lower()
        if len(host) >= 2 and host.startswith("[") and host.endswith("]"):
            host = host[1:-1].strip().rstrip(".").lower()
        return host

    def values(name: str) -> list[str]:
        return [value for key, value in pairs if key.lower() == name]

    def picked(raw_values: list[str]) -> str | None:
        """One query host. A non-loopback value wins so the guard refuses it."""
        chosen: str | None = None
        for raw in raw_values:
            host = norm_host(raw)
            if not host:
                continue
            if host not in _LOOPBACK_HOSTS:
                return host
            chosen = host
        return chosen

    parsed = urlparse(url)
    authority = (parsed.hostname or "").rstrip(".").lower()
    path = unquote(parsed.path or "")
    database = path[1:] if path.startswith("/") else path
    pairs = parse_qsl(parsed.query, keep_blank_values=False, separator="&")
    query_host = picked(values("host"))
    query_addr = picked(values("hostaddr"))
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
    for name in values("dbname"):
        if name == "":
            continue
        database = name
        if not name.startswith("ingenium_"):
            break
    return host, database


def _db_target_refusal(host: str, database: str) -> str | None:
    """None when the name starts with ingenium_ and the host is loopback."""
    if not database.startswith("ingenium_"):
        return "database name does not start with ingenium_"
    if host not in _LOOPBACK_HOSTS:
        return "host is not loopback"
    return None


def guard_db_target(url: str) -> None:
    """Refuse a non-ingenium_ database or a non-loopback host before any socket call.

    Inputs: database URL. Userinfo is ignored and is not included in the error.
    Query ``host``, ``hostaddr``, and ``dbname`` override the authority host and
    the path database. When both ``host`` and ``hostaddr`` are set, both must
    be loopback.
    Output: None when the effective name starts with ``ingenium_`` and the
    effective host is ``127.0.0.1``, ``::1``, or ``localhost``.
    Side effects: raises ConnectionRefusedError on refusal. Does not resolve DNS
    and does not call socket.getaddrinfo or socket.create_connection.
    """
    host, database = _db_endpoint(url)
    reason = _db_target_refusal(host, database)
    if reason is None:
        return
    raise ConnectionRefusedError(
        f"test db guard: refusing host={host} database={database} ({reason})"
    )


_PSYCOPG_TARGET_KEYS = ("host", "hostaddr", "port", "dbname")


def _psycopg_guard_url(conninfo: object, kwargs: dict[str, object]) -> str:
    """Build a password-free URL so guard_db_target can see the psycopg target.

    Inputs: a psycopg conninfo string and the connect keyword arguments.
    Output: a postgresql URL whose host, hostaddr, and dbname follow libpq
    overrides. User and password are not copied into the URL.
    Side effects: none. Does not resolve DNS and does not open a socket.
    An unparsed target is refused before connect.
    """
    from urllib.parse import quote

    from psycopg.conninfo import conninfo_to_dict

    text = conninfo if isinstance(conninfo, str) else ""
    for prefix in ("postgresql+psycopg://", "postgres+psycopg://"):
        if text.startswith(prefix):
            text = "postgresql://" + text[len(prefix) :]
            break
    target = {
        key: kwargs[key]
        for key in _PSYCOPG_TARGET_KEYS
        if kwargs.get(key) is not None
    }
    try:
        info = conninfo_to_dict(text, **target)
    except Exception:
        raise ConnectionRefusedError(
            "test db guard: refusing unparsed psycopg target "
            "(database name does not start with ingenium_)"
        ) from None
    host = str(info.get("host") or "")
    hostaddr = str(info.get("hostaddr") or "")
    database = str(info.get("dbname") or "")
    port = str(info.get("port") or "")
    authority = host or hostaddr
    if ":" in authority and not (authority.startswith("[") and authority.endswith("]")):
        authority = f"[{authority}]"
    netloc = authority
    if port:
        netloc = f"{netloc}:{port}" if netloc else f":{port}"
    query: list[str] = []
    if host:
        query.append("host=" + quote(host, safe=""))
    if hostaddr:
        query.append("hostaddr=" + quote(hostaddr, safe=""))
    url = f"postgresql://{netloc}/{quote(database, safe='')}"
    if query:
        url = f"{url}?{'&'.join(query)}"
    return url


def _install_psycopg_connect_guard() -> None:
    """Send psycopg.connect through guard_db_target before any socket call.

    Inputs: none. Output: none.
    Side effects: replaces psycopg.connect and Connection.connect. A refused
    target raises ConnectionRefusedError and does not call the real connect,
    so the test process cannot read or write odoo_custom through psycopg.
    There is no skip flag and no read-only exception for odoo_custom.
    """
    import psycopg

    if getattr(psycopg.connect, "_b0_iso_guard", False):
        return
    real = psycopg.Connection.connect.__func__
    global _B0_ISO_REAL_PG_CONNECT
    if _B0_ISO_REAL_PG_CONNECT is None:
        _B0_ISO_REAL_PG_CONNECT = real

    def _connect_guarded(cls: type, conninfo: str, kwargs: dict[str, object]) -> object:
        guard_db_target(_psycopg_guard_url(conninfo, kwargs))
        return real(cls, conninfo, **kwargs)

    def _guarded_psycopg_connect(conninfo: str = "", **kwargs: object) -> object:
        return _connect_guarded(psycopg.Connection, conninfo, kwargs)

    def _guarded_connection_connect(
        cls: type, conninfo: str = "", **kwargs: object
    ) -> object:
        return _connect_guarded(cls, conninfo, kwargs)

    _guarded_psycopg_connect._b0_iso_guard = True  # type: ignore[attr-defined]
    _guarded_psycopg_connect._b0_iso_real = real  # type: ignore[attr-defined]
    psycopg.connect = _guarded_psycopg_connect  # type: ignore[assignment]
    psycopg.Connection.connect = classmethod(_guarded_connection_connect)  # type: ignore[method-assign]


def _database_url_text(url: object) -> str:
    """Return URL text for guard_db_target.

    Inputs: a string or a SQLAlchemy URL. Output: text with host and database.
    Side effects: none. Userinfo is not required and is not logged here.
    """
    if isinstance(url, str):
        return url
    render = getattr(url, "render_as_string", None)
    if callable(render):
        try:
            return str(render(hide_password=False))
        except TypeError:
            return str(url)
    return str(url)


def _install_db_engine_guard() -> None:
    """Send server create_engine calls through guard_db_target.

    Inputs: none. Output: none.
    Side effects: replaces sqlalchemy.create_engine. A non-sqlite URL that
    guard_db_target refuses raises ConnectionRefusedError and does not call
    the real create_engine, so no socket is opened. sqlite has no server and
    stays on the real create_engine.
    """
    import sqlalchemy
    from sqlalchemy.engine import create as sa_create

    real = sa_create.create_engine
    if getattr(real, "_b0_iso_guard", False):
        return

    def _guarded_create_engine(url: object, *args: object, **kwargs: object) -> object:
        text = _database_url_text(url)
        scheme = text.split(":", 1)[0].strip().lower()
        if not scheme.startswith("sqlite"):
            guard_db_target(text)
        return real(url, *args, **kwargs)

    _guarded_create_engine._b0_iso_guard = True  # type: ignore[attr-defined]
    sa_create.create_engine = _guarded_create_engine  # type: ignore[assignment]
    sqlalchemy.create_engine = _guarded_create_engine  # type: ignore[assignment]
    engine_mod = getattr(sqlalchemy, "engine", None)
    if engine_mod is not None:
        engine_mod.create_engine = _guarded_create_engine  # type: ignore[attr-defined]


_install_db_engine_guard()
_install_psycopg_connect_guard()

# Settings is constructed on this import. Test modules set AI_INTENT_LLM=off
# at import, which is too late once Settings already read the default "auto".
# Every suite file that sets the variable sets it to off. Env beats the env file.
os.environ.setdefault("AI_INTENT_LLM", "off")

# Snapshot before any test module replaces app.db.engine (test_reg_np_gnd, test_reg_np_t6).
import app.db as _session_db

_SESSION_ENGINE = _session_db.engine
_SESSION_FACTORY = _session_db.SessionLocal
_ENGINE_SWAP_MODULES = frozenset({"test_reg_np_gnd.py", "test_reg_np_t6.py"})
# Engine and SessionLocal each swap module installed at import, reapplied only for its tests.
_SWAP_ENGINES: dict[str, tuple[object, object]] = {}
# sessionmaker objects installed by app.db or a swap module. Modules that did
# ``from app.db import SessionLocal`` keep that object; rebinding updates them.
_KNOWN_SESSION_FACTORIES: set[object] = {_SESSION_FACTORY}


def _apply_engine(engine: object, factory: object) -> None:
    """Point app.db and every copied SessionLocal at one engine.

    Inputs: the engine and the sessionmaker bound to it. Output: none.
    Side effects: assigns ``app.db.engine`` and ``SessionLocal``, then assigns
    that same factory onto already-imported modules whose ``SessionLocal`` is
    one of the factories this process has used. Does not open a socket.
    """
    _KNOWN_SESSION_FACTORIES.add(_session_db.SessionLocal)
    _KNOWN_SESSION_FACTORIES.add(factory)
    _session_db.engine = engine
    _session_db.SessionLocal = factory
    import sys

    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        current = getattr(mod, "SessionLocal", None)
        if current in _KNOWN_SESSION_FACTORIES and current is not factory:
            try:
                setattr(mod, "SessionLocal", factory)
            except (AttributeError, TypeError):
                continue


def _drop_seeded_internal_plan(db: object) -> None:
    """Remove the seeded internal plan so one strict xfail still fails.

    Inputs: an open session. Output: none.
    Side effects: deletes plan_features, workspace_subscriptions, and
    billing_plans rows whose plan id is ``internal``, then commits.
    """
    from app.billing_models import BillingPlan, PlanFeature, WorkspaceSubscription

    db.query(PlanFeature).filter(PlanFeature.plan_id == "internal").delete(synchronize_session=False)  # type: ignore[attr-defined]
    db.query(WorkspaceSubscription).filter(  # type: ignore[attr-defined]
        WorkspaceSubscription.plan_id == "internal"
    ).delete(synchronize_session=False)
    db.query(BillingPlan).filter(BillingPlan.id == "internal").delete(synchronize_session=False)  # type: ignore[attr-defined]
    db.commit()  # type: ignore[attr-defined]


def _restore_session_engine() -> None:
    """Point app.db back at this process's ingenium_ engine.

    Inputs: none. Output: none.
    Side effects: rebinds ``app.db.engine`` and copied ``SessionLocal`` names
    to the snapshot taken before test modules imported. Does not open a new database.
    """
    _apply_engine(_SESSION_ENGINE, _SESSION_FACTORY)


# --- Host guard (Tope, Oct 20): tests never reach aonb or client Odoo hosts. ---------------
import socket as _socket

_LIVE_CLIENT_FILES = {"test_odoo20_version_table.py", "test_odoo20_drift_cells.py"}
_BLOCKED_SUFFIXES = (".odoo.com", ".odoo.sh")
_BLOCKED_EXTRA = {h.strip().lower() for h in os.environ.get("INGENIUM_BLOCKED_HOSTS", "").split(",") if h.strip()}


def _host_blocked(host: object) -> bool:
    h = str(host or "").strip().lower().rstrip(".")
    return "aonb" in h or h.endswith(_BLOCKED_SUFFIXES) or h in {"odoo.com", "odoo.sh"} or h in _BLOCKED_EXTRA


def _vertex_host(host: object) -> bool:
    h = str(host or "").strip().lower().rstrip(".")
    return (
        h == "aiplatform.googleapis.com"
        or h.endswith(".aiplatform.googleapis.com")
        or h.endswith("-aiplatform.googleapis.com")
    )


def _vertex_refused(host: object) -> bool:
    """Block Vertex unless this test opted in (live_ai + INGENIUM_LIVE_AI=1)."""
    if not _vertex_host(host):
        return False
    return (
        os.environ.get("INGENIUM_LIVE_AI") != "1"
        or os.environ.get("INGENIUM_LIVE_AI_ACTIVE") != "1"
    )


_real_getaddrinfo = _socket.getaddrinfo
_real_create_connection = _socket.create_connection


def _guarded_getaddrinfo(host, *a, **k):  # type: ignore[no-untyped-def]
    if _host_blocked(host):
        raise ConnectionRefusedError(f"test host guard: refusing {host} (aonb/client hosts are never reached from tests)")
    if _vertex_refused(host):
        raise ConnectionRefusedError(
            f"test host guard: refusing {host} (Vertex is live_ai only; set INGENIUM_LIVE_AI=1)"
        )
    return _real_getaddrinfo(host, *a, **k)


def _guarded_create_connection(address, *a, **k):  # type: ignore[no-untyped-def]
    host = address[0] if isinstance(address, tuple) else None
    if host is not None and _host_blocked(host):
        raise ConnectionRefusedError(f"test host guard: refusing {host}")
    if host is not None and _vertex_refused(host):
        raise ConnectionRefusedError(
            f"test host guard: refusing {host} (Vertex is live_ai only; set INGENIUM_LIVE_AI=1)"
        )
    return _real_create_connection(address, *a, **k)


_socket.getaddrinfo = _guarded_getaddrinfo
_socket.create_connection = _guarded_create_connection


def pytest_collection_modifyitems(config, items):  # type: ignore[no-untyped-def]
    skip_client = None
    if os.environ.get("INGENIUM_LIVE_CLIENT_TESTS") != "1":
        skip_client = pytest.mark.skip(
            reason=(
                "live client test: set INGENIUM_LIVE_CLIENT_TESTS=1 "
                "(still never reaches aonb/client hosts)"
            )
        )
    skip_ai = None
    if os.environ.get("INGENIUM_LIVE_AI") != "1":
        skip_ai = pytest.mark.skip(
            reason="live_ai: set INGENIUM_LIVE_AI=1 to call Vertex; skipped by default"
        )
    if skip_client is None and skip_ai is None:
        return
    for item in items:
        if skip_client is not None and item.path.name in _LIVE_CLIENT_FILES:
            item.add_marker(skip_client)
        # Fake nodes in the host-guard exec test have no keywords.
        if skip_ai is not None and "live_ai" in getattr(item, "keywords", {}):
            item.add_marker(skip_ai)
