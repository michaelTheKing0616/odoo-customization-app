"""B0-AICACHE-ISO: exact-response cache contract, and tests stay off home and Vertex.

Deleting these product lines fails the named test:
- ``ai_cache._path`` — cache file follows ``INGENIUM_AI_CACHE_PATH``
- ``ai_cache.make_key`` scope/prompt hash — model, prompt, inputs, snapshot
- ``ai_cache.put`` ttl ternary — 7 days with a db, 90 days without, else ``ttl_s``
- ``ai_cache.get_exact`` expiry check — a past ``expires`` is a miss
- ``ai_cache.invalidate_db`` delete — later ``get_exact`` for that db is ``None``
- ``ai_cache.note_snapshot`` ``mark_changed(db, [ALL])`` — whole-db rows go stale
- conftest per-test path, ``live_ai`` skip, Vertex host refusal
"""

from __future__ import annotations

import os
import socket
import time
from pathlib import Path

import pytest

from app import ai_draft_cache
from app.ai_client import ai_cache

pytestmark = pytest.mark.no_app_db

_HOME_CACHE = (Path.home() / ".ingenium").resolve()


def _key(**overrides: object) -> tuple[str, str]:
    args: dict[str, object] = {
        "provider": "mock",
        "model": "m",
        "method": "complete",
        "system": "",
        "prompt": "hello",
        "options": {"n": 1},
        "db": "ingenium_x",
        "odoo_version": "19",
        "snapshot_hash": "snap-a",
    }
    args.update(overrides)
    return ai_cache.make_key(**args)  # type: ignore[arg-type]


def _point_cache(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGENIUM_AI_CACHE_PATH", str(path))
    with ai_cache._lock:
        conn = ai_cache._conn
        ai_cache._conn = None
        ai_cache._conn_path = ""
        if conn is not None:
            conn.close()
    resolved = Path(ai_cache._path()).resolve()
    assert resolved == path.resolve()
    assert resolved != _HOME_CACHE and _HOME_CACHE not in resolved.parents


def test_ac1_exact_response_key_hit_invalidate_and_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "exact.sqlite"
    _point_cache(cache_path, monkeypatch)
    key, scope = _key()
    ai_cache.put(
        key, scope, db="ingenium_x", model="m", prompt="hello", value="ANSWER", ttl_s=60
    )
    stored = ai_cache._db().execute("SELECT ttl FROM resp WHERE k=?", (key,)).fetchone()
    assert stored is not None and stored[0] == 60
    assert ai_cache.get_exact(key) == "ANSWER"

    key_b, _scope_b = _key(snapshot_hash="snap-b")
    assert key_b != key
    assert ai_cache.get_exact(key_b) is None

    for field, value in (
        ("model", "other"),
        ("prompt", "other"),
        ("options", {"n": 2}),
        ("provider", "other"),
        ("system", "other"),
        ("method", "other"),
        ("db", "ingenium_other"),
        ("odoo_version", "18"),
    ):
        other, _scope = _key(**{field: value})
        assert other != key, field
        assert ai_cache.get_exact(other) is None, field

    kept, kept_scope = _key(db="ingenium_y", prompt="kept")
    ai_cache.put(
        kept, kept_scope, db="ingenium_y", model="m", prompt="kept", value="KEPT", ttl_s=60
    )
    assert ai_cache.invalidate_db("ingenium_x") >= 1
    assert ai_cache.get_exact(key) is None
    assert ai_cache.get_exact(kept) == "KEPT"

    expired, expired_scope = _key(prompt="past")
    ai_cache.put(
        expired, expired_scope, db="ingenium_x", model="m", prompt="past", value="OLD", ttl_s=60
    )
    with ai_cache._lock:
        ai_cache._db().execute(
            "UPDATE resp SET expires=? WHERE k=?", (time.time() - 5, expired)
        )
    assert ai_cache.get_exact(expired) is None


def test_ac1_default_ttl_is_seven_days_with_db_and_ninety_without(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _point_cache(tmp_path / "ttl.sqlite", monkeypatch)
    assert ai_cache.DEFAULT_TTL_S == 7 * 24 * 3600
    assert ai_cache.VERSION_ONLY_TTL_S == 90 * 24 * 3600

    now = time.time()
    key, scope = _key(prompt="with-db")
    ai_cache.put(key, scope, db="ingenium_x", model="m", prompt="with-db", value="A")
    row = ai_cache._db().execute("SELECT expires, ttl FROM resp WHERE k=?", (key,)).fetchone()
    assert row is not None
    assert row[1] == ai_cache.DEFAULT_TTL_S
    assert abs(row[0] - (now + ai_cache.DEFAULT_TTL_S)) < 5

    bare, bare_scope = _key(db="", prompt="version-only")
    ai_cache.put(bare, bare_scope, db="", model="m", prompt="version-only", value="B")
    row_b = ai_cache._db().execute(
        "SELECT expires, ttl FROM resp WHERE k=?", (bare,)
    ).fetchone()
    assert row_b is not None
    assert row_b[1] == ai_cache.VERSION_ONLY_TTL_S
    assert abs(row_b[0] - (now + ai_cache.VERSION_ONLY_TTL_S)) < 5
    assert ai_cache.get_exact(bare) == "B"


def test_ac1_note_snapshot_change_stales_whole_db_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _point_cache(tmp_path / "snap.sqlite", monkeypatch)
    ai_cache._snap_seen.clear()
    key, scope = _key(prompt="snap")
    ai_cache.put(key, scope, db="ingenium_x", model="m", prompt="snap", value="ANSWER", ttl_s=60)
    assert ai_cache.note_snapshot("ingenium_x", "snap-a") is False
    assert ai_cache.get_exact(key) == "ANSWER"
    ai_cache._snap_seen.clear()
    assert ai_cache.note_snapshot("ingenium_x", "snap-b") is True
    assert ai_cache.get_exact(key) is None


def test_exact_cache_does_not_use_draft_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("exact-response cache must not call save_draft_cache")

    monkeypatch.setattr(ai_draft_cache, "save_draft_cache", _boom)
    _point_cache(tmp_path / "draft.sqlite", monkeypatch)
    key, scope = _key(prompt="separate")
    ai_cache.put(
        key, scope, db="ingenium_x", model="m", prompt="separate", value="ANSWER", ttl_s=60
    )
    assert ai_cache.get_exact(key) == "ANSWER"


def test_each_test_cache_path_is_outside_home_ingenium(tmp_path: Path) -> None:
    path = Path(os.environ["INGENIUM_AI_CACHE_PATH"]).resolve()
    assert path == (tmp_path / "ai_cache.sqlite").resolve()
    assert path != _HOME_CACHE and _HOME_CACHE not in path.parents
    assert Path(ai_cache._path()).resolve() == path


def test_unmarked_test_refuses_vertex_hosts() -> None:
    hosts = ("aiplatform.googleapis.com", "us-central1-aiplatform.googleapis.com")
    for host in hosts:
        with pytest.raises(ConnectionRefusedError, match="Vertex"):
            socket.getaddrinfo(host, 443)
        with pytest.raises(ConnectionRefusedError, match="Vertex"):
            socket.create_connection((host, 443), timeout=1)


@pytest.mark.live_ai
def test_live_ai_runs_only_when_opted_in() -> None:
    assert os.environ.get("INGENIUM_LIVE_AI") == "1"
