"""A foreign connection id returns the same 404 bytes as a random id on that route."""

from __future__ import annotations

import atexit
import json
import re
import subprocess
import sys
import uuid
from collections.abc import Iterator
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app.account_service import SESSION_COOKIE, create_session, signup_user
from app.db import SessionLocal, init_db
from app.db_models import OdooConnection
from app.dry_run_ledger import bind_store
from app.dry_run_middleware import is_write_capable
from app.main import app
from app.safety_registry import build_route_registry, connection_id_from_path, is_exempt
from app.settings import settings

_BRACE = re.compile(r"\{([^}/:]+)(?::[^}]*)?\}")
_DB_NAME = re.compile(r"ingenium_[A-Za-z0-9_]+")
_FORBIDDEN_PORTS = frozenset(
    {3002, 5433, 5436, 8001, 8002, 8012, 8069, 8070, 8071, 8072, 8073, 11434}
)


def _ensure_throwaway_db() -> None:
    """Create the conftest ingenium_* database. The URL names it; the server does not."""
    parsed = urlparse(settings.database_url.replace("postgresql+psycopg", "postgresql", 1))
    name = (parsed.path or "").lstrip("/").split("?", 1)[0]
    host = (parsed.hostname or "").lower()
    port = parsed.port or 5432
    if _DB_NAME.fullmatch(name) is None or host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("refusing to create a database outside the throwaway ingenium_ URL")
    if port in _FORBIDDEN_PORTS:
        raise RuntimeError("refusing to create a database on a reserved port")
    script = (
        "import sys\n"
        "import psycopg\n"
        "from psycopg import sql\n"
        "name, host, port, user, password = sys.argv[1:6]\n"
        "admin = psycopg.connect(\n"
        "    host=host, port=int(port), dbname='postgres', user=user, password=password,\n"
        "    autocommit=True,\n"
        ")\n"
        "row = admin.execute(\n"
        "    'SELECT 1 FROM pg_database WHERE datname = %s', (name,)\n"
        ").fetchone()\n"
        "if row is None:\n"
        "    admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))\n"
    )
    subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            name,
            host,
            str(port),
            parsed.username or "ingenium",
            parsed.password or "",
        ],
        check=True,
    )

    def _drop() -> None:
        drop = (
            "import sys\n"
            "import psycopg\n"
            "from psycopg import sql\n"
            "name, host, port, user, password = sys.argv[1:6]\n"
            "admin = psycopg.connect(\n"
            "    host=host, port=int(port), dbname='postgres', user=user, password=password,\n"
            "    autocommit=True,\n"
            ")\n"
            "admin.execute(\n"
            "    sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(name))\n"
            ")\n"
        )
        subprocess.run(
            [
                sys.executable,
                "-c",
                drop,
                name,
                host,
                str(port),
                parsed.username or "ingenium",
                parsed.password or "",
            ],
            check=False,
        )

    atexit.register(_drop)


_ensure_throwaway_db()


def _carries_connection_id(path: str) -> bool:
    params = {name: "x" for name in _BRACE.findall(path)}
    return connection_id_from_path(path, params) is not None


def _connection_gated_routes() -> list[tuple[str, str, bool]]:
    registry = build_route_registry(app.openapi()["paths"])
    routes: list[tuple[str, str, bool]] = []
    for key, spec in registry.items():
        if is_exempt(key):
            continue
        method, path = key.split(":", 1)
        if not _carries_connection_id(path):
            continue
        routes.append((method, path, bool(spec.bypass_writes_paused)))
    routes.sort(key=lambda row: f"{row[0]}:{row[1]}")
    if not routes:
        raise RuntimeError("route registry has no gated connection id paths")
    return routes


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "gated_route" not in metafunc.fixturenames:
        return
    routes = _connection_gated_routes()
    metafunc.parametrize(
        "gated_route",
        routes,
        ids=[f"{method}:{path}" for method, path, _bypass in routes],
    )


def _fill(path: str, connection_id: str) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group(1) == "connection_id":
            return connection_id
        return "x"

    return _BRACE.sub(replace, path)


def _account(db, label: str) -> tuple[str, str]:
    email = f"{label}-{uuid.uuid4().hex[:8]}@example.com"
    user, workspace, _token = signup_user(
        db,
        email=email,
        password="gate-scope-pass-99",
        workspace_name=label,
    )
    user.email_verified = True
    workspace.plan = "internal"
    workspace.writes_paused = False
    db.add(user)
    db.add(workspace)
    db.commit()
    _session, raw = create_session(db, user=user, workspace_id=workspace.id)
    return workspace.id, raw


def _connection(db, workspace_id: str, *, paused: bool) -> OdooConnection:
    row = OdooConnection(
        id=str(uuid.uuid4()),
        name="Gate scope",
        url="http://127.0.0.1:9",
        db_name="ingenium_unused",
        username="admin",
        secret_encrypted="enc",
        write_mode="standard",
        writes_paused=paused,
        workspace_id=workspace_id,
    )
    db.add(row)
    return row


class _MemoryDryRun:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def remember(self, digest: str, *, now: object = None) -> None:
        del now
        self._seen.add(digest)

    def contains(self, digest: str, *, now: object = None) -> bool:
        del now
        return digest in self._seen


@pytest.fixture(scope="module", autouse=True)
def _dry_run_receipts() -> Iterator[None]:
    bind_store(_MemoryDryRun())
    yield
    bind_store(None)


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def world(client: TestClient) -> dict[str, str]:
    del client
    db = SessionLocal()
    try:
        workspace_a, cookie_a = _account(db, "gate-a")
        _workspace_b, cookie_b = _account(db, "gate-b")
        paused = _connection(db, workspace_a, paused=True)
        opened = _connection(db, workspace_a, paused=False)
        db.commit()
        return {
            "paused_id": paused.id,
            "open_id": opened.id,
            "missing_id": str(uuid.uuid4()),
            "cookie_a": cookie_a,
            "cookie_b": cookie_b,
        }
    finally:
        db.close()


def _ensure_paused(connection_id: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(OdooConnection, connection_id)
        if row is None:
            raise AssertionError("paused connection row disappeared")
        if not row.writes_paused:
            row.writes_paused = True
            db.commit()
    finally:
        db.close()


def _is_writes_paused(body: bytes) -> bool:
    payload = json.loads(body)
    detail = payload.get("detail")
    if isinstance(detail, dict) and detail.get("error") == "writes_paused":
        return True
    error = payload.get("error")
    if not isinstance(error, dict):
        return False
    nested = error.get("detail")
    return isinstance(nested, dict) and nested.get("error") == "writes_paused"


def _call(client: TestClient, method: str, path: str, cookie: str) -> tuple[int, bytes]:
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, cookie)
    if is_write_capable(method, path):
        preview = client.request(
            method,
            path,
            json={"dry_run": True},
            follow_redirects=False,
        )
        if preview.status_code != 200:
            return preview.status_code, preview.content
        response = client.request(
            method,
            path,
            json={"dry_run": False},
            follow_redirects=False,
        )
        return response.status_code, response.content
    response = client.request(method, path, follow_redirects=False)
    return response.status_code, response.content


def test_foreign_connection_matches_missing_id(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    world: dict[str, str],
    gated_route: tuple[str, str, bool],
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "accounts")
    method, path, bypass = gated_route
    label = f"{method} {path}"
    missing = _call(client, method, _fill(path, world["missing_id"]), world["cookie_b"])
    foreign_paused = _call(client, method, _fill(path, world["paused_id"]), world["cookie_b"])
    foreign_open = _call(client, method, _fill(path, world["open_id"]), world["cookie_b"])
    assert missing[0] == 404, (label, missing[1])
    # Same status and raw body as the random id. The body may be the raw
    # detail or the B5 NOT_FOUND envelope. A different body would leak existence.
    assert foreign_paused == missing, label
    assert foreign_open == missing, label
    if bypass:
        return
    _ensure_paused(world["paused_id"])
    owned = _call(client, method, _fill(path, world["paused_id"]), world["cookie_a"])
    assert owned[0] == 403, (label, owned[1])
    # Raw gate body, or the same refusal nested in a B5 envelope.
    assert _is_writes_paused(owned[1]), (label, owned[1])
