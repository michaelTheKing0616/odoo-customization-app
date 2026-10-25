"""BV-STORE: verify-run store tests (own throwaway ingenium_wt_* DB, alembic-built)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

from app.bot_verify import contract as t
from app.bot_verify.readback import mask
from app.changeset.verify import CHECKS
from app.main import app
from app.routers import bot_verify as r
from app.safety_dependency import enforce_safety_gate
from app.scans.contract import ScanScope
from app.workspace_auth import require_app_auth

API = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1:54329"
ADMIN = f"postgresql://ingenium:ingenium@{HOST}/ingenium_wt_admin"
DB = f"ingenium_wt_bvstore_{uuid.uuid4().hex[:12]}"
URL = f"postgresql+psycopg://ingenium:ingenium@{HOST}/{DB}"
REV, DOWN = "4b7e9c1d2a3f", "b0a1c2d3e4f5"
WS_A, WS_B = "ws-a", "ws-b"
CONN_A, CONN_B, CONN_C = "conn-a", "conn-b", "conn-c"  # C: same workspace as A
OWNER = {CONN_A: WS_A, CONN_B: WS_B, CONN_C: WS_A}
PNG = b"\x89PNG\r\n\x1a\nstore"
SECRET, EMAIL = "sk-live-SEEDEDSECRET123", "jane.doe@example.com"


def _single_head_with(rev: str) -> str:
    """The one alembic head; ``rev`` must be it or one of its ancestors (future-proof)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    sd = ScriptDirectory.from_config(Config(str(API / "alembic.ini")))
    heads = sd.get_heads()
    assert len(heads) == 1, heads
    assert rev in {s.revision for s in sd.walk_revisions("base", heads[0])}
    return heads[0]


HEAD = _single_head_with("c7d8e9f0a1b2")  # BV-AUDIT is in the chain


def _alembic(*args: str) -> str:
    assert DB.startswith("ingenium_wt_") and HOST in URL
    env = {**os.environ, "DATABASE_URL": URL}
    out = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout + out.stderr


@pytest.fixture(scope="module")
def db_engine():
    with psycopg.connect(ADMIN, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{DB}"')
    _alembic("upgrade", "head")
    eng = create_engine(URL, poolclass=NullPool)
    with eng.begin() as c:
        for ws in (WS_A, WS_B):
            c.execute(
                text("INSERT INTO workspaces (id, name, slug) VALUES (:i, :i, :i)"), {"i": ws}
            )
        for cid, ws in OWNER.items():
            c.execute(
                text(
                    "INSERT INTO odoo_connections (id, workspace_id, name, url, db_name,"
                    " username, secret_encrypted, upgrade_detected) VALUES"
                    " (:i, :w, :i, 'http://x', 'd', 'u', 'enc', false)"
                ),
                {"i": cid, "w": ws},
            )
    yield eng
    eng.dispose()
    with psycopg.connect(ADMIN, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')


@pytest.fixture(autouse=True)
def _isolate(request, tmp_path, monkeypatch):
    from app import odoo_service, safety_dependency

    def _no_odoo(*_a, **_k):
        raise AssertionError("BV-STORE must not build an Odoo client")

    monkeypatch.setattr(safety_dependency, "_REGISTRY", None)
    monkeypatch.setattr(odoo_service, "client_from_connection", _no_odoo)
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
    if "db_engine" in request.fixturenames:
        with request.getfixturevalue("db_engine").begin() as c:
            c.execute(text("DELETE FROM verify_artifacts"))
            c.execute(text("DELETE FROM verify_runs"))


@pytest.fixture
def root(tmp_path):
    p = tmp_path / "data"
    p.mkdir()
    return p


@pytest.fixture
def store(db_engine, root):
    from app.bot_verify.store import VerifyStore

    return VerifyStore(db_engine, root)


def _scope(cid=CONN_A):
    return ScanScope(workspace_id=OWNER[cid], connection_id=cid)


def _run(run_id=None, evidence=None, status="passed"):
    check = t.CheckResult(check=CHECKS[0], op_index=0, passed=True, evidence=evidence or {"k": "v"})
    layer = t.LayerResult(layer="live", status="passed", reason=None, checks=[check], steps=[])
    return t.VerifyRun(
        run_id=run_id or str(uuid.uuid4()),
        changeset_id="cs-1",
        status=status,
        layers=[layer],
        started_at=datetime(2026, 10, 23, 9, tzinfo=UTC),
        finished_at=datetime(2026, 10, 23, 9, 5, tzinfo=UTC),
    )


def _fake_scope(connection_id: str, x_ws: str = Header(WS_A)):
    if OWNER.get(connection_id) != x_ws:
        raise HTTPException(status_code=404, detail="Connection not found")
    return ScanScope(workspace_id=x_ws, connection_id=connection_id)


@pytest.fixture
def client(store):
    from app.bot_verify.store import artifact_engine_from_store, get_engine_from_store

    o = app.dependency_overrides
    o[require_app_auth] = lambda: None
    o[enforce_safety_gate] = lambda: None
    o[r.bv_scope] = _fake_scope
    o[r.get_engine] = lambda: get_engine_from_store(store)
    o[r.artifact_engine] = lambda: artifact_engine_from_store(store)
    return TestClient(app)


def _same(a, b):
    assert a.status_code == b.status_code == 404
    assert a.content == b.content

    def h(x):
        return {k: v for k, v in x.headers.items() if k != "x-request-id"}

    assert h(a) == h(b)  # x-request-id is per request by design
    assert a.json()["error"]["code"] == "NOT_FOUND"


# AC1 ------------------------------------------------------------------------
def test_ac1_single_head_and_down_revision():
    out = _alembic("heads")
    assert [ln for ln in out.splitlines() if ln.strip()] == [f"{HEAD} (head)"]
    src = next((API / "alembic" / "versions").glob(f"{REV}_nf_verify_runs.py")).read_text()
    assert re.search(rf"^down_revision: .* = \"{DOWN}\"$", src, re.M)


def test_ac1_tables_columns_fks(db_engine):
    ins = inspect(db_engine)
    runs = {c["name"] for c in ins.get_columns("verify_runs")}
    arts = {c["name"] for c in ins.get_columns("verify_artifacts")}
    assert runs == {
        "run_id",
        "connection_id",
        "workspace_id",
        "changeset_id",
        "status",
        "layers",
        "started_at",
        "finished_at",
    }
    assert arts == {
        "artifact_id",
        "run_id",
        "connection_id",
        "blob_path",
        "content_type",
        "created_at",
    }
    fk_r = ins.get_foreign_keys("verify_runs")
    assert [(f["referred_table"], f["options"].get("ondelete")) for f in fk_r] == [
        ("odoo_connections", "CASCADE")
    ]
    fk_a = ins.get_foreign_keys("verify_artifacts")
    assert [(f["referred_table"], f["options"].get("ondelete")) for f in fk_a] == [
        ("verify_runs", "CASCADE")
    ]


def test_ac1_up_down_up_clean(db_engine):
    _alembic("downgrade", DOWN)
    names = set(inspect(create_engine(URL, poolclass=NullPool)).get_table_names())
    assert not {"verify_runs", "verify_artifacts"} & names
    assert "odoo_connections" in names
    _alembic("upgrade", "head")
    names = set(inspect(create_engine(URL, poolclass=NullPool)).get_table_names())
    assert {"verify_runs", "verify_artifacts"} <= names


# AC2 ------------------------------------------------------------------------
def test_ac2_round_trip(store):
    run = _run()
    store.save_run(_scope(), run)
    assert store.get_run(_scope(), run.run_id) == run


def test_ac2_engine_factories_match_contract(store):
    from app.bot_verify.store import artifact_engine_from_store, get_engine_from_store

    run = _run()
    store.save_run(_scope(), run)
    aid = store.put_artifact(_scope(), run.run_id, PNG, "image/png")
    assert get_engine_from_store(store)(_scope(), run.run_id) == run
    assert artifact_engine_from_store(store)(_scope(), run.run_id, aid) == PNG


def test_ac2_route_serves_stored_run_and_artifact(client, store):
    run = _run()
    store.save_run(_scope(), run)
    aid = store.put_artifact(_scope(), run.run_id, PNG, "image/png")
    base = f"/api/connections/{CONN_A}/verify-runs/{run.run_id}"
    res = client.get(base)
    assert res.status_code == 200 and res.json()["run_id"] == run.run_id
    res = client.get(f"{base}/artifacts/{aid}")
    assert res.status_code == 200 and res.content == PNG


def test_ac2_router_file_unchanged_default_engines():
    with pytest.raises(t.BVError):
        r.get_engine()(_scope(), "x")


# AC3 ------------------------------------------------------------------------
def test_ac3_foreign_run_identical_to_random(client, store):
    run_b = _run()
    store.save_run(_scope(CONN_B), run_b)
    run_c = _run()
    store.save_run(_scope(CONN_C), run_c)
    rnd = client.get(f"/api/connections/{CONN_A}/verify-runs/{uuid.uuid4()}")
    _same(client.get(f"/api/connections/{CONN_A}/verify-runs/{run_b.run_id}"), rnd)
    _same(client.get(f"/api/connections/{CONN_A}/verify-runs/{run_c.run_id}"), rnd)


def test_ac3_foreign_artifacts_identical_to_random(client, store):
    a1, a2, b = _run(), _run(), _run()
    store.save_run(_scope(), a1)
    store.save_run(_scope(), a2)
    store.save_run(_scope(CONN_B), b)
    art_a2 = store.put_artifact(_scope(), a2.run_id, PNG, "image/png")
    art_b = store.put_artifact(_scope(CONN_B), b.run_id, PNG, "image/png")
    u = f"/api/connections/{CONN_A}/verify-runs/{{}}/artifacts/{{}}"
    rnd = client.get(u.format(a1.run_id, uuid.uuid4()))
    _same(client.get(u.format(a1.run_id, art_a2)), rnd)  # other run, same connection
    _same(client.get(u.format(b.run_id, art_b)), rnd)  # foreign run + artifact
    _same(client.get(u.format(a1.run_id, art_b)), rnd)  # foreign artifact
    _same(client.get(u.format(uuid.uuid4(), uuid.uuid4())), rnd)


def test_ac3_other_workspace_same_connection_id(store):
    run = _run()
    store.save_run(_scope(), run)
    bad = ScanScope(workspace_id=WS_B, connection_id=CONN_A)
    with pytest.raises(t.BVError) as e1:
        store.get_run(bad, run.run_id)
    with pytest.raises(t.BVError) as e2:
        store.get_run(_scope(), str(uuid.uuid4()))
    assert e1.value.body() == e2.value.body() and e1.value.code == "NOT_FOUND"


def test_ac3_save_cannot_hijack_foreign_run(store):
    run = _run()
    store.save_run(_scope(CONN_B), run)
    with pytest.raises(t.BVError):
        store.save_run(_scope(), run)
    assert store.get_run(_scope(CONN_B), run.run_id) == run


def test_ac3_put_artifact_on_foreign_run_refused(store, root):
    run = _run()
    store.save_run(_scope(CONN_B), run)
    with pytest.raises(t.BVError):
        store.put_artifact(_scope(), run.run_id, PNG, "image/png")
    assert not any(p.is_file() for p in root.rglob("*"))


# AC4 ------------------------------------------------------------------------
def test_ac4_bytes_on_disk_relative_path(store, root, db_engine):
    run = _run()
    store.save_run(_scope(), run)
    aid = store.put_artifact(_scope(), run.run_id, PNG, "image/png")
    f = root / WS_A / "verify" / run.run_id / f"{aid}.png"
    assert f.read_bytes() == PNG
    with db_engine.connect() as c:
        row = c.execute(
            text("SELECT blob_path FROM verify_artifacts WHERE artifact_id=:a"), {"a": aid}
        ).one()
    assert row.blob_path == f"{WS_A}/verify/{run.run_id}/{aid}.png"
    assert not Path(row.blob_path).is_absolute()
    cols = inspect(db_engine).get_columns("verify_artifacts")
    assert not any(
        "BYTEA" in str(c["type"]).upper() or "BLOB" in str(c["type"]).upper() for c in cols
    )


@pytest.mark.parametrize(
    "bad", ["../escape.png", "/etc/passwd", "~/x.png", "a/\x00b.png", "ws-a/../../x.png", ""]
)
def test_ac4_path_traversal_refused(store, root, bad):
    from app.bot_verify.store import safe_blob_path

    with pytest.raises(ValueError):
        safe_blob_path(root, bad)


def test_ac4_symlink_escape_refused(store, root, tmp_path, db_engine):
    from app.bot_verify.store import safe_blob_path

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.png").write_bytes(b"secret")
    (root / "ws-a").mkdir()
    (root / "ws-a" / "link").symlink_to(outside)
    with pytest.raises(ValueError):
        safe_blob_path(root, "ws-a/link/x.png")
    run = _run()
    store.save_run(_scope(), run)
    aid = str(uuid.uuid4())
    with db_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO verify_artifacts (artifact_id, run_id, connection_id, blob_path,"
                " content_type, created_at) VALUES (:a, :r, :c, 'ws-a/link/x.png',"
                " 'image/png', now())"
            ),
            {"a": aid, "r": run.run_id, "c": CONN_A},
        )
    with pytest.raises(t.BVError) as e:
        store.get_artifact(_scope(), run.run_id, aid)
    assert e.value.code == "NOT_FOUND"


@pytest.mark.parametrize("bad_id", ["../x", "a/b", "x\x00", ".."])
def test_ac4_unsafe_ids_write_nothing(store, root, bad_id):
    with pytest.raises((t.BVError, ValueError)):
        store.save_run(_scope(), _run(run_id=bad_id))
    assert not any(root.rglob("*"))


def test_ac4_type_and_size_limits(store, root):
    run = _run()
    store.save_run(_scope(), run)
    with pytest.raises(t.BVError) as e:
        store.put_artifact(_scope(), run.run_id, PNG, "text/html")
    assert e.value.code == "VALIDATION"
    with pytest.raises(t.BVError):
        store.put_artifact(_scope(), run.run_id, b"x" * (5 * 1024 * 1024 + 1), "image/png")
    assert not any(p.is_file() for p in root.rglob("*"))


def test_ac4_no_orphan_blob_on_db_failure(store, root, monkeypatch):
    run = _run()
    store.save_run(_scope(), run)

    def boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(store, "_insert_artifact", boom)
    with pytest.raises(RuntimeError):
        store.put_artifact(_scope(), run.run_id, PNG, "image/png")
    assert not any(p.is_file() for p in root.rglob("*"))


# AC5 ------------------------------------------------------------------------
def test_ac5_no_secret_or_pii_in_rows(store, db_engine):
    # BV-02 masks PII; it does not mask secrets, so the store refuses raw ones.
    raw = {"partner_id": [7, EMAIL], "email": EMAIL}
    evidence = {k: str(v) for k, v in mask(raw).items()}
    for leak in ({"token": SECRET}, {"note": f"key {SECRET}"}):
        with pytest.raises(t.BVError):
            store.save_run(_scope(), _run(evidence=leak))
    run = _run(evidence=evidence)
    store.save_run(_scope(), run)
    store.put_artifact(_scope(), run.run_id, PNG, "image/png")
    with db_engine.connect() as c:
        dump = " ".join(
            str(tuple(row))
            for tbl in ("verify_runs", "verify_artifacts")
            for row in c.execute(text(f"SELECT * FROM {tbl}"))
        )
    assert SECRET not in dump and EMAIL not in dump


def test_ac5_store_refuses_unmasked_values(store):
    with pytest.raises(t.BVError) as e:
        store.save_run(_scope(), _run(evidence={"note": f"mail {EMAIL} key {SECRET}"}))
    assert e.value.code == "VALIDATION"


# Cascade ----------------------------------------------------------------------
def test_cascade_connection_delete_removes_rows(store, db_engine):
    with db_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO odoo_connections (id, workspace_id, name, url, db_name, username,"
                " secret_encrypted, upgrade_detected) VALUES ('conn-x', 'ws-a', 'x',"
                " 'http://x', 'd', 'u', 'enc', false)"
            )
        )
    s = ScanScope(workspace_id=WS_A, connection_id="conn-x")
    run = _run()
    store.save_run(s, run)
    store.put_artifact(s, run.run_id, PNG, "image/png")
    with db_engine.begin() as c:
        c.execute(text("DELETE FROM odoo_connections WHERE id='conn-x'"))
        n = c.execute(
            text(
                "SELECT (SELECT count(*) FROM verify_runs WHERE connection_id='conn-x')"
                " + (SELECT count(*) FROM verify_artifacts WHERE connection_id='conn-x')"
            )
        ).scalar()
    assert n == 0


# Drift parity ------------------------------------------------------------------
def test_drift_fresh_db_at_head_matches_orm():
    """Real autogenerate compare on a fresh alembic-built DB; no create_all, no stamp."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app import account_models, billing_models, db_models  # noqa: F401
    from app.db import Base

    name = f"ingenium_wt_bvdrift_{uuid.uuid4().hex[:12]}"
    url = f"postgresql+psycopg://ingenium:ingenium@{HOST}/{name}"
    with psycopg.connect(ADMIN, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    try:
        env = {**os.environ, "DATABASE_URL": url}
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=API,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        eng = create_engine(url, poolclass=NullPool)
        with eng.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={"compare_type": True})
            assert ctx.get_current_revision() == HEAD
            diff = compare_metadata(ctx, Base.metadata)
        eng.dispose()
        ops = [d for d in diff if not (isinstance(d, tuple) and d[0].endswith("_comment"))]

        # bot_* tables/indexes (BOT-KILL-AUDIT) are raw-SQL, owned by migrations, not the ORM
        def _bot(d: object) -> bool:
            if not isinstance(d, tuple) or d[0] not in ("remove_table", "remove_index"):
                return False
            tbl = d[1] if d[0] == "remove_table" else d[1].table
            return tbl.name.startswith("bot_")

        ops = [d for d in ops if not _bot(d)]
        assert not ops, ops
        assert {"verify_runs", "verify_artifacts"} <= set(Base.metadata.tables)
    finally:
        with psycopg.connect(ADMIN, autocommit=True) as c:
            c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
