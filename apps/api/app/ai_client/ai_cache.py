"""Shared AI response cache (exact + safe near-duplicate), per-DB sub-result cache, and savings stats.

SQLite file (default ~/.ingenium/ai_cache.sqlite, override INGENIUM_AI_CACHE_PATH).
Keys include model, provider, system, prompt, call options and the scope's Odoo version +
snapshot hash, so a snapshot change makes old entries unreachable; ``invalidate_db`` also
deletes them. Callers must not store text containing secrets/PII (shared client enforces).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

DEFAULT_TTL_S = 7 * 24 * 3600
VERSION_ONLY_TTL_S = 90 * 24 * 3600   # answers that do not read any database data
SEMANTIC_FLOOR = 0.92          # Jaccard on word 3-shingles; below this never reuse
SEMANTIC_MAX_CANDIDATES = 200

# USD per 1M tokens (input, output). Rough list prices; unknown models use the default row.
PRICES: dict[str, tuple[float, float]] = {
    "flash-lite": (0.10, 0.40), "flash": (0.30, 2.50), "pro": (1.25, 10.0),
    "gpt-4.1-mini": (0.40, 1.60), "gpt-4.1": (2.0, 8.0), "claude": (3.0, 15.0),
    "ollama": (0.0, 0.0), "mock": (0.0, 0.0), "default": (0.30, 2.50),
}

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None
_conn_path: str = ""


def _path() -> str:
    return os.environ.get("INGENIUM_AI_CACHE_PATH") or str(Path.home() / ".ingenium" / "ai_cache.sqlite")


def _db() -> sqlite3.Connection:
    global _conn, _conn_path
    p = _path()
    with _lock:
        if _conn is None or _conn_path != p:
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(p, check_same_thread=False, isolation_level=None)
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS resp(k TEXT PRIMARY KEY, scope TEXT, db TEXT, model TEXT,
                  norm TEXT, value TEXT, created REAL, expires REAL, in_tok INT, out_tok INT);
                CREATE INDEX IF NOT EXISTS resp_scope ON resp(scope);
                CREATE INDEX IF NOT EXISTS resp_db ON resp(db);
                CREATE TABLE IF NOT EXISTS sub(k TEXT PRIMARY KEY, db TEXT, value TEXT, created REAL, expires REAL);
                CREATE INDEX IF NOT EXISTS sub_db ON sub(db);
                CREATE TABLE IF NOT EXISTS stats(name TEXT PRIMARY KEY, n REAL);
                CREATE TABLE IF NOT EXISTS stamp(db TEXT, dep TEXT, n INTEGER, PRIMARY KEY(db, dep));
                """
            )
            cols = {r[1] for r in _conn.execute("PRAGMA table_info(resp)")}
            for col, typ in (("ttl", "REAL"), ("deps", "TEXT")):
                if col not in cols:
                    _conn.execute(f"ALTER TABLE resp ADD COLUMN {col} {typ}")
            _conn_path = p
        return _conn


def est_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def price_for(model: str) -> tuple[float, float]:
    m = (model or "").lower()
    for key in ("flash-lite", "gpt-4.1-mini", "gpt-4.1", "flash", "pro", "claude", "ollama", "mock"):
        if key in m:
            return PRICES[key]
    return PRICES["default"]


def usd_cost(model: str, in_tok: int, out_tok: int) -> float:
    pi, po = price_for(model)
    return (in_tok * pi + out_tok * po) / 1_000_000


def _h(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def make_key(*, provider: str, model: str, method: str, system: str, prompt: str,
             options: dict[str, Any], db: str, odoo_version: str, snapshot_hash: str) -> tuple[str, str]:
    """Return (exact_key, scope_key). scope_key groups entries eligible for near-duplicate reuse."""
    scope_key = _h(provider, model, method, system, options, db, odoo_version, snapshot_hash)
    return _h(scope_key, prompt), scope_key


_WS = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    return " ".join(_WS.split((text or "").lower())).strip()


def _shingles(norm: str) -> set[str]:
    w = norm.split()
    if len(w) < 3:
        return {" ".join(w)}
    return {" ".join(w[i:i + 3]) for i in range(len(w) - 2)}


def similarity(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def bump(name: str, by: float = 1.0) -> None:
    with _lock:
        _db().execute("INSERT INTO stats(name,n) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET n=n+excluded.n", (name, by))


ALL = "*"  # entries that did not declare what they read depend on the whole database


def _stamps(db: str, deps: list[str]) -> dict[str, int]:
    if not db or not deps:
        return {}
    c = _db()
    out = {}
    for d in deps:
        row = c.execute("SELECT n FROM stamp WHERE db=? AND dep=?", (db, d)).fetchone()
        out[d] = row[0] if row else 0
    return out


def mark_changed(db: str, models: list[str] | tuple[str, ...]) -> None:
    """Records/metadata of these models changed: entries that read them become stale.
    Pass ALL to stale every entry of the database."""
    if not db:
        return
    with _lock:
        c = _db()
        for m in set(models) | {ALL}:  # whole-DB entries go stale on any change
            c.execute("INSERT INTO stamp VALUES(?,?,1) ON CONFLICT(db, dep) DO UPDATE SET n=n+1", (db, m))
    bump("dep_changes")


def _fresh_row(db: str, deps_json: str | None) -> bool:
    if not db or not deps_json:
        return True
    want = json.loads(deps_json)
    if not want:
        return True
    have = _stamps(db, list(want))
    return all(have.get(d, 0) == n for d, n in want.items())


def _slide(key: str, ttl: float | None) -> None:
    _db().execute("UPDATE resp SET expires=? WHERE k=?", (time.time() + (ttl or DEFAULT_TTL_S), key))


def get_exact(key: str) -> str | None:
    with _lock:
        row = _db().execute("SELECT value, expires, db, deps, ttl FROM resp WHERE k=?", (key,)).fetchone()
        if not row or row[1] < time.time():
            return None
        if not _fresh_row(row[2], row[3]):
            _db().execute("DELETE FROM resp WHERE k=?", (key,))
            bump("dep_stale")
            return None
        _slide(key, row[4])  # sliding expiry: a hit keeps it alive
    return row[0]


def get_semantic(scope_key: str, prompt: str, floor: float = SEMANTIC_FLOOR) -> tuple[str, float] | None:
    norm = normalize(prompt)
    with _lock:
        rows = _db().execute(
            "SELECT norm, value, k, db, deps, ttl FROM resp WHERE scope=? AND expires>? ORDER BY created DESC LIMIT ?",
            (scope_key, time.time(), SEMANTIC_MAX_CANDIDATES),
        ).fetchall()
        best: tuple[str, float, str, float | None] | None = None
        for n, v, k, db, deps, ttl in rows:
            s = similarity(norm, n)
            if s >= floor and (best is None or s > best[1]) and _fresh_row(db, deps):
                best = (v, s, k, ttl)
        if best:
            _slide(best[2], best[3])
    return (best[0], best[1]) if best else None


def put(key: str, scope_key: str, *, db: str, model: str, prompt: str, value: str,
        ttl_s: int | None = None, in_tok: int = 0, out_tok: int = 0,
        reads: list[str] | tuple[str, ...] | None = None) -> None:
    """``reads``: models whose data the answer used. None with a db -> depends on the whole DB.
    No db -> version-only answer, kept 90 days."""
    now = time.time()
    ttl = ttl_s or (VERSION_ONLY_TTL_S if not db else DEFAULT_TTL_S)
    with _lock:
        deps = list(reads) if reads else ([ALL] if db else [])
        stamps = _stamps(db, deps)
        _db().execute(
            "INSERT OR REPLACE INTO resp(k,scope,db,model,norm,value,created,expires,in_tok,out_tok,ttl,deps)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, scope_key, db, model, normalize(prompt), value, now, now + ttl, in_tok, out_tok, ttl,
             json.dumps(stamps) if stamps else None),
        )


def invalidate_db(db: str) -> int:
    """Drop every cached answer and sub-result for one database (call on snapshot change)."""
    with _lock:
        c = _db()
        n = c.execute("DELETE FROM resp WHERE db=?", (db,)).rowcount
        n += c.execute("DELETE FROM sub WHERE db=?", (db,)).rowcount
    bump("invalidations")
    return n


def clear_all() -> None:
    with _lock:
        _db().executescript("DELETE FROM resp; DELETE FROM sub;")


def purge_expired() -> int:
    now = time.time()
    with _lock:
        c = _db()
        n = c.execute("DELETE FROM resp WHERE expires<?", (now,)).rowcount + c.execute(
            "DELETE FROM sub WHERE expires<?", (now,)).rowcount
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    bump("expired_purged", n)
    return n


_snap_seen: dict[str, str] = {}


def note_snapshot(db: str, snapshot_hash: str) -> bool:
    """Record the current snapshot hash for a DB; invalidates its cache when it changed."""
    if not db or not snapshot_hash:
        return False
    with _lock:
        prev = _snap_seen.get(db)
        if prev is None:
            row = _db().execute("SELECT value FROM sub WHERE k=?", ("__snap__" + db,)).fetchone()
            prev = row[0] if row else None
        if prev == snapshot_hash:
            _snap_seen[db] = snapshot_hash
            return False
        _snap_seen[db] = snapshot_hash
        _db().execute("INSERT OR REPLACE INTO sub VALUES(?,?,?,?,?)",
                      ("__snap__" + db, "", snapshot_hash, time.time(), 1e12))
    if prev is not None:
        mark_changed(db, [ALL])  # only entries without declared reads go stale
        return True
    return False


def subresult(db: str, kind: str, key: Any, compute: Callable[[], Any], *,
              snapshot_hash: str = "", ttl_s: int | None = None, fresh: bool = False) -> Any:
    """Per-DB cache for deterministic sub-results (schema summaries, mappings, explanations).

    ``compute`` must return JSON-serialisable data and must be deterministic for (db, snapshot).
    """
    k = _h("sub", db, kind, key, snapshot_hash)
    if not fresh:
        with _lock:
            row = _db().execute("SELECT value, expires FROM sub WHERE k=?", (k,)).fetchone()
        if row and row[1] >= time.time():
            bump("sub_hits")
            return json.loads(row[0])
    val = compute()
    bump("sub_misses")
    with _lock:
        _db().execute("INSERT OR REPLACE INTO sub VALUES(?,?,?,?,?)",
                      (k, db, json.dumps(val, default=str), time.time(), time.time() + (ttl_s or DEFAULT_TTL_S)))
    return val


def stats() -> dict[str, Any]:
    with _lock:
        c = _db()
        s = dict(c.execute("SELECT name, n FROM stats").fetchall())
        entries = c.execute("SELECT COUNT(*) FROM resp WHERE expires>?", (time.time(),)).fetchone()[0]
    calls = s.get("calls", 0)
    hits = s.get("hits_exact", 0) + s.get("hits_semantic", 0)
    return {
        "calls": int(calls),
        "hits_exact": int(s.get("hits_exact", 0)),
        "hits_semantic": int(s.get("hits_semantic", 0)),
        "misses": int(s.get("misses", 0)),
        "bypass_fresh": int(s.get("bypass_fresh", 0)),
        "not_cached_sensitive": int(s.get("skip_sensitive", 0)),
        "hit_rate": round(hits / calls, 4) if calls else 0.0,
        "tokens_saved": int(s.get("tokens_saved", 0)),
        "usd_saved": round(s.get("usd_saved", 0.0), 6),
        "usd_spent_est": round(s.get("usd_spent", 0.0), 6),
        "context_cache_hits": int(s.get("ctx_hits", 0)),
        "context_cache_created": int(s.get("ctx_created", 0)),
        "subresult_hits": int(s.get("sub_hits", 0)),
        "subresult_misses": int(s.get("sub_misses", 0)),
        "invalidations": int(s.get("invalidations", 0)),
        "dependency_changes": int(s.get("dep_changes", 0)),
        "stale_by_dependency": int(s.get("dep_stale", 0)),
        "model_fallbacks": int(s.get("model_fallbacks", 0)),
        "expired_purged": int(s.get("expired_purged", 0)),
        "guard_flags": {k[6:]: int(v) for k, v in s.items() if k.startswith("guard_")},
        "live_entries": int(entries),
    }


def start_daily_cleanup(interval_s: float = 24 * 3600) -> threading.Event:
    """Purge expired cache entries at boot and then once a day. Set the returned event to stop."""
    stop = threading.Event()

    def _loop() -> None:
        while True:
            try:
                purge_expired()
            except Exception:  # noqa: BLE001
                pass
            if stop.wait(interval_s):
                return

    threading.Thread(target=_loop, name="ai-cache-cleanup", daemon=True).start()
    return stop


# Q2 touch 111: did the last AI call in this request come from the cache? Read-only signal.
import contextvars as _cv

LAST_HIT: _cv.ContextVar[bool | None] = _cv.ContextVar("ingenium_ai_last_hit", default=None)


def note_hit(hit: bool) -> None:
    LAST_HIT.set(hit)
