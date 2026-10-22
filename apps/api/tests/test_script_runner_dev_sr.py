"""DEV-SR — confirm phrase, forbidden RPC, crash journal, and a second run row."""

from __future__ import annotations

import os
import socket
import textwrap
import threading
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.account_service import signup_user  # noqa: E402
from app.crypto import encrypt_secret  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import OdooConnection, ScriptRun  # noqa: E402
from app.entitlements import ensure_workspace_subscription  # noqa: E402
from app.main import app  # noqa: E402
from app.script_runner.child_main import (  # noqa: E402
    ScriptOdoo,
    _WriteCounter,
    _script_builtins,
)
from app.script_runner.executor import run_script_in_subprocess  # noqa: E402
from app.script_runner.service import script_hash  # noqa: E402
from odoo_client.client import OdooClient  # noqa: E402

WRITE_SCRIPT = textwrap.dedent(
    """
    odoo.execute_kw("res.partner", "write", [[1], {"comment": "script-runner"}])
    """
).strip()

CONFIRM = {
    "confirm_advanced": True,
    "confirm_phrase": "I understand the risks",
}


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _conn() -> OdooConnection:
    db = SessionLocal()
    try:
        _user, ws, _ = signup_user(
            db,
            email=f"sr-{uuid.uuid4().hex[:8]}@example.com",
            password="sr-pass-99-long",
        )
        conn = OdooConnection(
            name="script-runner",
            url="http://127.0.0.1:9",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
            workspace_id=ws.id,
        )
        db.add(conn)
        sub = ensure_workspace_subscription(db, ws.id)
        sub.plan_id = "internal"
        db.commit()
        db.refresh(conn)
        return conn
    finally:
        db.close()


def _runs(connection_id: str) -> list[dict[str, str | None]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(ScriptRun)
            .filter(ScriptRun.connection_id == connection_id)
            .order_by(ScriptRun.created_at.asc(), ScriptRun.id.asc())
            .all()
        )
        return [
            {
                "id": row.id,
                "status": row.status,
                "script_hash": row.script_hash,
                "connection_id": row.connection_id,
                "write_counts_json": row.write_counts_json,
                "snapshot_id": row.snapshot_id,
                "error": row.error,
            }
            for row in rows
        ]
    finally:
        db.close()


class _HitServer:
    def __init__(self) -> None:
        self.hits: list[int] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self._sock.settimeout(0.2)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    def _accept(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except (TimeoutError, OSError):
                continue
            self.hits.append(1)
            conn.close()

    def close(self) -> None:
        self._stop.set()
        self._sock.close()
        self._thread.join(timeout=2)


def test_write_without_confirm_phrase_does_not_call_odoo(client: TestClient) -> None:
    conn = _conn()
    with (
        patch("app.routers.script_runner.run_script_sync") as sync,
        patch("app.routers.script_runner.enqueue_script_run") as enqueue,
        patch("odoo_client.client.OdooClient") as odoo_client,
    ):
        res = client.post(
            f"/api/connections/{conn.id}/script-runner/run",
            json={"script": WRITE_SCRIPT, "async_job": False},
        )
    assert res.status_code == 403, res.text
    detail = res.json()["detail"]
    assert detail["requires_confirmation"] is True
    assert detail["confirm_phrase"] == "I understand the risks"
    sync.assert_not_called()
    enqueue.assert_not_called()
    odoo_client.assert_not_called()
    assert _runs(conn.id) == []


def test_forbidden_rpc_does_not_leave_the_process() -> None:
    server = _HitServer()
    try:
        config = {
            "url": f"http://127.0.0.1:{server.port}",
            "db": "odoo_dev",
            "username": "admin",
            "password": "admin",
            "write_mode": "standard",
        }
        unlink = run_script_in_subprocess(
            script='odoo.execute_kw("res.users", "unlink", [[1]])\n',
            connection_config=config,
            job_id="forbid-unlink",
            timeout_s=20,
        )
        protected = run_script_in_subprocess(
            script='odoo.execute_kw("ir.config_parameter", "set_param", ["database.secret", "x"])\n',
            connection_config=config,
            job_id="forbid-param",
            timeout_s=20,
        )
    finally:
        server.close()

    assert server.hits == []
    assert unlink["ok"] is False
    assert "never_allowed" in (unlink.get("stderr") or unlink.get("error") or "")
    assert protected["ok"] is False
    assert "protected_param" in (protected.get("stderr") or protected.get("error") or "")


def test_stored_client_dispatch_after_allowed_call_does_not_connect() -> None:
    """An allowed call must not leave a client that can skip the never-allowed check.

    connect() and execute_kw succeed without a socket. The listening port can
    only see a connection if the script reaches the real _dispatch_execute.
    """
    server = _HitServer()
    clients: list[OdooClient] = []

    def _connect_without_socket(self: OdooClient) -> int:
        self._uid = 1
        self._rpc_protocol = "xmlrpc"
        transport = getattr(self._object, "_ServerProxy__transport", None)
        if transport is not None:
            transport._call_timeout = 2.0
        clients.append(self)
        return 1

    def _execute_without_socket(
        self: OdooClient,
        model: str,
        method: str,
        args: list[object] | None = None,
        kwargs: dict[str, object] | None = None,
    ) -> list[object]:
        del self, model, method, args, kwargs
        return []

    script = textwrap.dedent(
        """
        marker.append(odoo.execute_kw("res.partner", "search", [[]]))
        try:
            odoo._client._dispatch_execute("res.users", "unlink", [[1]], {})
            marker.append("unlink-sent")
        except Exception:
            marker.append("unlink-blocked")
        try:
            gotten = object.__getattribute__(odoo, "_client")
            gotten._dispatch_execute("res.users", "unlink", [[1]], {})
            marker.append("getattr-sent")
        except Exception:
            marker.append("getattr-blocked")
        try:
            odoo._client._dispatch_execute(
                "ir.config_parameter", "set_param", ["database.secret", "x"], {}
            )
            marker.append("param-sent")
        except Exception:
            marker.append("param-blocked")
        """
    ).strip()
    marker: list[object] = []
    namespace = {
        "__builtins__": _script_builtins(),
        "odoo": ScriptOdoo(
            {
                "url": f"http://127.0.0.1:{server.port}",
                "db": "odoo_dev",
                "username": "admin",
                "password": "admin",
                "write_mode": "standard",
            },
            _WriteCounter(),
        ),
        "marker": marker,
    }
    try:
        with (
            patch.object(OdooClient, "connect", _connect_without_socket),
            patch.object(OdooClient, "execute_kw", _execute_without_socket),
        ):
            exec(compile(script, "<stored-client>", "exec"), namespace)  # noqa: S102
            assert len(clients) == 1
            assert clients[0]._dispatch_execute.__func__ is OdooClient._dispatch_execute
    finally:
        server.close()

    assert marker[0] == []
    assert "unlink-sent" not in marker
    assert "getattr-sent" not in marker
    assert "param-sent" not in marker
    assert "unlink-blocked" in marker
    assert "param-blocked" in marker
    assert server.hits == []


def test_execute_kw_globals_cannot_open_a_file_or_connect_a_socket(tmp_path) -> None:
    """The callable a script receives must not carry this module's globals.

    ``log`` and ``progress`` are already rebound. ``execute_kw`` used to be the
    real method, so ``__func__.__globals__`` was ``child_main`` and exposed
    ``os`` and the real ``builtins``.
    """
    import builtins

    import app.script_runner.child_main as script_child

    server = _HitServer()
    target = tmp_path / "execute-kw-globals.txt"
    script = textwrap.dedent(
        f"""
        file_created = False
        socket_created = False
        direct_open_blocked = False
        import_os_blocked = False
        try:
            os_mod = odoo.execute_kw.__func__.__globals__["os"]
            fd = os_mod.open({str(target)!r}, os_mod.O_WRONLY | os_mod.O_CREAT | os_mod.O_TRUNC, 0o644)
            os_mod.close(fd)
            file_created = True
        except Exception:
            file_created = False
        try:
            sock = odoo.execute_kw.__func__.__globals__["builtins"].__import__("socket").socket()
            socket_created = True
            sock.settimeout(1.0)
            sock.connect(("127.0.0.1", {server.port}))
            sock.close()
        except Exception:
            pass
        try:
            open({str(target)!r}, "w")
        except PermissionError:
            direct_open_blocked = True
        try:
            import os
        except ImportError:
            import_os_blocked = True
        """
    ).strip()
    namespace = {
        "__builtins__": _script_builtins(),
        "odoo": ScriptOdoo(
            {
                "url": "http://127.0.0.1:9",
                "db": "odoo_dev",
                "username": "admin",
                "password": "admin",
                "write_mode": "standard",
            },
            _WriteCounter(),
        ),
    }
    try:
        exec(compile(script, "<execute-kw-globals>", "exec"), namespace)  # noqa: S102
    finally:
        server.close()

    received = namespace["odoo"].execute_kw
    func = received.__func__
    globs = func.__globals__
    assert globs is not script_child.__dict__
    assert "os" not in globs
    assert "sys" not in globs
    assert "builtins" not in globs
    assert builtins not in globs.values()
    assert script_child.os not in globs.values()
    for value in globs.values():
        owner = getattr(value, "__globals__", None)
        assert owner is not script_child.__dict__

    assert namespace["file_created"] is False
    assert namespace["socket_created"] is False
    assert namespace["direct_open_blocked"] is True
    assert namespace["import_os_blocked"] is True
    assert not target.exists()
    assert server.hits == []


def test_crashed_run_is_visible_as_failed(client: TestClient) -> None:
    conn = _conn()
    res = client.post(
        f"/api/connections/{conn.id}/script-runner/run",
        json={
            "script": "raise RuntimeError('script crashed')\n",
            "async_job": False,
            **CONFIRM,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is False
    assert body["run"]["status"] == "failed"
    assert "script crashed" in (body["run"]["error"] or "")

    listed = client.get(f"/api/connections/{conn.id}/script-runner/runs")
    assert listed.status_code == 200
    rows = listed.json()
    assert rows[0]["status"] == "failed"
    assert rows[0]["script_hash"] == script_hash("raise RuntimeError('script crashed')\n")
    assert "script crashed" in (rows[0]["error"] or "")


def test_parent_crash_leaves_a_failed_row(client: TestClient) -> None:
    conn = _conn()
    with patch(
        "app.script_runner.service.run_script_in_subprocess",
        side_effect=RuntimeError("runner blew up"),
    ):
        res = client.post(
            f"/api/connections/{conn.id}/script-runner/run",
            json={"script": "log('x')\n", "async_job": False, **CONFIRM},
        )
    assert res.status_code == 200, res.text
    assert res.json()["run"]["status"] == "failed"
    assert "crashed" in (res.json()["run"]["error"] or "").lower()
    rows = _runs(conn.id)
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"


def test_second_run_of_the_same_script_is_a_new_row(client: TestClient) -> None:
    conn = _conn()
    result = {
        "ok": True,
        "stdout": "done\n",
        "stderr": "",
        "error": None,
        "write_counts": {"res.partner": {"create": 0, "write": 2, "unlink": 0}},
    }
    body = {"script": WRITE_SCRIPT, "async_job": False, **CONFIRM}
    with patch("app.script_runner.service.run_script_in_subprocess", return_value=result):
        first = client.post(f"/api/connections/{conn.id}/script-runner/run", json=body)
        second = client.post(f"/api/connections/{conn.id}/script-runner/run", json=body)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    rows = _runs(conn.id)
    assert len(rows) == 2
    assert rows[0]["id"] != rows[1]["id"]
    assert rows[0]["script_hash"] == rows[1]["script_hash"] == script_hash(WRITE_SCRIPT)
    assert rows[0]["connection_id"] == rows[1]["connection_id"] == conn.id
    assert rows[0]["status"] == "succeeded"
    assert rows[1]["status"] == "succeeded"
    assert '"write": 2' in (rows[0]["write_counts_json"] or "")
    assert rows[0]["snapshot_id"]
    assert rows[1]["snapshot_id"]
    assert rows[0]["snapshot_id"] != rows[1]["snapshot_id"]
