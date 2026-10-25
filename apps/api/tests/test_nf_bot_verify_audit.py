"""BV-AUDIT: persisted walkthrough audit + stored approval, and BV-HARDEN/BV-UI-WIRE
reviewer follow-ups. Own throwaway ingenium_wt_* DB, alembic-built."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import psycopg
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

from app.bot_verify import flows as fl
from app.bot_verify import targets as tg
from app.bot_verify import walkthrough as wk

pytestmark = [pytest.mark.no_app_db]

API = Path(__file__).resolve().parents[1]
WEB = API.parent / "web"
PORT = os.environ.get("INGENIUM_TEST_PG_PORT", "54339")
HOST = f"127.0.0.1:{PORT}"
ADMIN = f"postgresql://ingenium:ingenium@{HOST}/ingenium_wt_admin"
DB = f"ingenium_wt_bvaudit_{uuid.uuid4().hex[:12]}"
URL = f"postgresql+psycopg://ingenium:ingenium@{HOST}/{DB}"
REV, DOWN = "c7d8e9f0a1b2", "4b7e9c1d2a3f"
CONN_A, CONN_B = "conn-audit-a", "conn-audit-b"
DISPOSABLE = dict(url="http://127.0.0.1:18117", db_name="ingenium_nf_bv_17", major=17)


def _alembic(*args: str) -> str:
    assert DB.startswith("ingenium_wt_") and PORT != "54329"
    out = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API,
        env={**os.environ, "DATABASE_URL": URL},
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout + out.stderr


@pytest.fixture(scope="module")
def engine():
    with psycopg.connect(ADMIN, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{DB}"')
    try:
        _alembic("upgrade", "head")
        eng = create_engine(URL, poolclass=NullPool)
        with eng.begin() as c:
            c.execute(
                text("INSERT INTO workspaces (id, name, slug) VALUES ('ws-au','ws-au','ws-au')")
            )
            for cid in (CONN_A, CONN_B):
                c.execute(
                    text(
                        "INSERT INTO odoo_connections (id, workspace_id, name, url, db_name,"
                        " username, secret_encrypted, upgrade_detected) VALUES"
                        " (:i, 'ws-au', :i, 'http://x', 'd', 'u', 'enc', false)"
                    ),
                    {"i": cid},
                )
        yield eng
        eng.dispose()
    finally:
        with psycopg.connect(ADMIN, autocommit=True) as c:
            c.execute(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')


@pytest.fixture()
def store(engine):
    prev = tg.audit_store()
    s = tg.AuditStore(engine)
    with engine.begin() as c:
        c.execute(text("DELETE FROM verify_audit"))
        c.execute(text("DELETE FROM verify_walk_approvals"))
    tg.configure_audit_store(s)
    yield s
    tg.configure_audit_store(prev)


def _rows(engine) -> list[dict[str, Any]]:
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text("SELECT * FROM verify_audit ORDER BY id"))]


# ------------------------------------------------------------------ AC1


def test_ac1_every_decision_is_a_row(store, engine) -> None:
    assert not hasattr(tg, "AUDIT_LOG")
    tg.resolve_target(**DISPOSABLE)
    with pytest.raises(tg.TargetNotAllowed):
        tg.resolve_target(**{**DISPOSABLE, "db_name": "aonb"}, connection_id=CONN_A)
    with pytest.raises(tg.TargetNotAllowed):
        tg.resolve_target(**{**DISPOSABLE, "url": "http://127.0.0.1:8069"})
    rows = _rows(engine)
    assert [(r["decision"], r["connection_id"]) for r in rows] == [
        ("allowed", None),
        ("refused", CONN_A),
        ("refused", None),
    ]
    assert rows[0]["reason"] == "disposable_clone" and rows[1]["db_name"] == "aonb"
    assert all(r["at"] is not None for r in rows)
    assert [r["decision"] for r in tg.audit_log(CONN_A)] == ["refused"]


def test_ac1_no_store_or_failed_write_refuses() -> None:
    prev = tg.audit_store()

    class Broken:
        def record(self, *a: Any) -> None:
            raise RuntimeError("db down")

        def approval(self, cid: Any) -> tg.WalkApproval:
            return tg.WalkApproval(False, None, None)

    try:
        tg.configure_audit_store(None)
        with pytest.raises(tg.TargetNotAllowed, match="not configured"):
            tg.resolve_target(**DISPOSABLE)
        with pytest.raises(tg.TargetNotAllowed, match="not configured"):
            tg.audit_log()
        tg.configure_audit_store(Broken())
        with pytest.raises(tg.TargetNotAllowed, match="audit write failed"):
            tg.resolve_target(**DISPOSABLE)
    finally:
        tg.configure_audit_store(prev)


# ------------------------------------------------------------------ AC2


def test_ac2_caller_flags_ignored_stored_approval_used(store) -> None:
    aonb = {**DISPOSABLE, "db_name": "aonb"}
    with pytest.raises(tg.TargetNotAllowed):
        tg.resolve_target(
            **aonb, connection_id=CONN_A, walkthrough_allowed=True, approved_by="u1", owner_id="u1"
        )
    store.set_approval(CONN_A, allowed=True, approved_by="u1", owner_id="u1")
    t = tg.resolve_target(**aonb, connection_id=CONN_A, walkthrough_allowed=False)
    assert t.kind == "approved_connection"
    for cid in (CONN_B, None):  # approval is keyed by connection
        with pytest.raises(tg.TargetNotAllowed):
            tg.resolve_target(**aonb, connection_id=cid, walkthrough_allowed=True)
    store.set_approval(CONN_B, allowed=True, approved_by="u2", owner_id="u1")
    with pytest.raises(tg.TargetNotAllowed):
        tg.resolve_target(**aonb, connection_id=CONN_B)
    store.set_approval(CONN_A, allowed=False, approved_by="u1", owner_id="u1")
    with pytest.raises(tg.TargetNotAllowed):
        tg.resolve_target(**aonb, connection_id=CONN_A)
    with pytest.raises(TypeError):
        tg.resolve_target(**aonb, connection_id=CONN_A, kind="approved_connection")


def test_ac2_approval_default_off_and_cascades(store, engine) -> None:
    assert store.approval(CONN_A).granted is False
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO odoo_connections (id, workspace_id, name, url, db_name,"
                " username, secret_encrypted, upgrade_detected) VALUES"
                " ('conn-gone','ws-au','g','http://x','d','u','enc',false)"
            )
        )
    store.set_approval("conn-gone", allowed=True, approved_by="u", owner_id="u")
    assert store.approval("conn-gone").granted
    with engine.begin() as c:
        c.execute(text("DELETE FROM odoo_connections WHERE id='conn-gone'"))
    assert store.approval("conn-gone").granted is False


# ------------------------------------------------------------------ AC3


def test_ac3_no_secrets_or_pii_in_rows(store, engine) -> None:
    secret, email = "sk-live-SEEDEDSECRET123", "jane.doe@example.com"
    with pytest.raises(tg.TargetNotAllowed):
        tg.resolve_target(
            url=f"http://{email}:{secret}@127.0.0.1:8069", db_name="ingenium_x", major=17
        )
    with pytest.raises(tg.TargetNotAllowed):
        tg.resolve_target(url="http://127.0.0.1:18117", db_name="x" * 300, major=17)
    blob = repr(_rows(engine))
    assert secret not in blob and email not in blob and "x" * 81 not in blob


def test_ac3_migration_round_trip(engine) -> None:
    assert re.search(rf"\b{REV}\b \(head\)", _alembic("heads"))
    _alembic("downgrade", DOWN)
    names = set(inspect(engine).get_table_names())
    assert {"verify_audit", "verify_walk_approvals"}.isdisjoint(names) and "verify_runs" in names
    _alembic("upgrade", "head")
    names = set(inspect(engine).get_table_names())
    assert {"verify_audit", "verify_walk_approvals"} <= names
    assert REV in _alembic("current")


# ------------------------------------------------------------------ AC4


class _Admin:
    def __init__(self, exc: Exception) -> None:
        self.exc, self.rows, self.writes = exc, {7: {"active": True, "groups_id": [1]}}, []

    def __call__(self, model: str, method: str, args: Any = (), kwargs: Any = None) -> Any:
        if method == "search":
            return list(self.rows)
        if method == "unlink":
            raise self.exc
        if method == "write":
            self.writes.append(args[1])
            for u in args[0]:
                self.rows[u] = {"active": False, "groups_id": []}
            return True
        if method == "read":
            return [self.rows[u] for u in args[0]]
        raise AssertionError(method)


class AccessError(Exception):
    pass


LOGIN = wk.WalkLogin("password", "ingenium_walk_z", "p" * 32)
_T = tg.WalkTarget(
    "http://127.0.0.1:18117", "127.0.0.1", 18117, "ingenium_nf_bv_17", 17, "disposable_clone"
)


@pytest.mark.parametrize(
    "exc",
    [
        PermissionError("no delete access to calendar.user"),
        AccessError("x"),
        RuntimeError("odoo.exceptions.AccessError: You are not allowed to delete 'User'"),
        type("Fault", (Exception,), {"faultCode": "odoo.exceptions.AccessError"})("x"),
    ],
)
def test_ac4_archive_only_on_access_refused(exc: Exception) -> None:
    adm = _Admin(exc)
    assert wk.delete_walk_user(_T, adm, LOGIN) is True and adm.writes


@pytest.mark.parametrize(
    "exc",
    [
        ConnectionError("reset"),
        TimeoutError("slow"),
        ValueError("bad domain"),
        RuntimeError("access denied by proxy"),
        RuntimeError("You are not allowed to delete this"),
    ],
)
def test_ac4_other_unlink_errors_reraise(exc: Exception) -> None:
    adm = _Admin(exc)
    with pytest.raises(type(exc)):
        wk.delete_walk_user(_T, adm, LOGIN)
    assert adm.writes == []


# ------------------------------------------------------------------ AC5


def test_ac5_walk_error_survives_cleanup_failure(monkeypatch) -> None:
    monkeypatch.setattr(wk, "create_walk_user", lambda *a, **k: LOGIN)

    def bad_delete(*a: Any, **k: Any) -> bool:
        raise ConnectionError("cleanup down")

    monkeypatch.setattr(wk, "delete_walk_user", bad_delete)
    with pytest.raises(RuntimeError, match="walk failed") as ei:
        with wk.walk_user(_T, lambda *a, **k: None, "r", None):
            raise RuntimeError("walk failed")
    notes = " ".join(getattr(ei.value, "__notes__", []))
    assert "cleanup" in notes and "ConnectionError" in notes
    with pytest.raises(ConnectionError):  # no walk error: cleanup failure still surfaces
        with wk.walk_user(_T, lambda *a, **k: None, "r", None):
            pass


# ------------------------------------------------------------------ AC6


@pytest.mark.parametrize(
    "access",
    [
        [],
        [{"type": "access.create", "params": {"model": "x_thing"}}],  # group-less
        [{"type": "access.create", "params": {"model": "x_other", "group": "base.group_user"}}],
        [
            {
                "type": "access.update",
                "params": {
                    "model": "x_thing",
                    "group": "base.group_user",
                    "perm_read": False,
                    "perm_write": False,
                    "perm_create": False,
                    "perm_unlink": False,
                },
            }
        ],
    ],
)
def test_ac6_acl_gap_broader(access: list[dict[str, Any]]) -> None:
    cs = [{"type": "model.scaffold", "params": {"model": " X_Thing "}}, *access]
    assert fl.acl_gaps(cs) == ["x_thing"]


def test_ac6_access_update_with_group_but_no_perm_keys_is_not_cover() -> None:
    cs = [
        {"type": "model.create", "params": {"model": "x_thing"}},
        {"type": "access.update", "params": {"model": "x_thing", "group": "base.group_user"}},
    ]
    assert fl.acl_gaps(cs) == ["x_thing"]


def test_ac6_access_create_without_perm_keys_covers_because_dispatch_defaults_perm_read() -> None:
    cs = [
        {"type": "model.create", "params": {"model": "x_thing"}},
        {"type": "access.create", "params": {"model": "x_thing", "group": "base.group_user"}},
    ]
    assert fl.acl_gaps(cs) == []


def test_ac6_acl_covered() -> None:
    cs = [
        {"type": "model.create", "params": {"model": "x_thing"}},
        {"type": "access.create", "params": {"model_id": "X_THING", "group": "base.group_user"}},
    ]
    assert fl.acl_gaps(cs) == []
    cs[1] = {
        "type": "access.create",
        "params": {"model": "x_thing", "group": "g", "operation": "read"},
    }  # Odoo 20 ir.access
    assert fl.acl_gaps(cs) == []


# ------------------------------------------------------------------ AC7


def test_ac7_copy_failed_reassures() -> None:
    src = (WEB / "src/components/bots/VerifyRunPanel.tsx").read_text()
    m = re.search(r'const COPY_FAILED = "([^"]*)"', src)
    assert m and m.group(1).endswith("Your Odoo data is unchanged.")
