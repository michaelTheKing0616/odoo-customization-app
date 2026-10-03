"""Memory and Postgres idempotency claims for offline-queue work."""

from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)

from app.offline.idempotency import MemoryIdempotencyStore, claim_db  # noqa: E402

_INTEGRATION_URL = "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom"


def test_memory_claim_runs_compute_once() -> None:
    store = MemoryIdempotencyStore()
    calls = {"n": 0}

    def compute() -> dict:
        calls["n"] += 1
        return {"count": calls["n"]}

    first = store.claim("job-abc", compute)
    second = store.claim("job-abc", compute)
    assert calls["n"] == 1
    assert first == second == {"count": 1}


def test_empty_key_raises() -> None:
    store = MemoryIdempotencyStore()
    with pytest.raises(ValueError):
        store.claim("", lambda: {"ok": True})


def _postgres_integration_available() -> None:
    try:
        import psycopg
    except ImportError:
        pytest.skip("psycopg not installed")
    try:
        with psycopg.connect(
            "host=127.0.0.1 port=5433 dbname=odoo_custom user=odoo_custom password=odoo_custom"
        ) as conn:
            conn.execute("SELECT 1")
    except Exception:
        pytest.skip("Postgres idempotency integration DB not reachable")


def test_claim_db_runs_compute_once_on_postgres() -> None:
    _postgres_integration_available()
    os.environ["DATABASE_URL"] = _INTEGRATION_URL
    from sqlalchemy import inspect

    from app.db import SessionLocal, engine

    if "idempotency_keys" not in inspect(engine).get_table_names():
        pytest.skip("idempotency_keys table missing")

    db = SessionLocal()
    key = f"idem-{uuid.uuid4().hex[:12]}"
    calls = {"n": 0}
    try:

        def compute() -> dict:
            calls["n"] += 1
            return {"count": calls["n"]}

        first = claim_db(db, key, compute)
        second = claim_db(db, key, compute)
        assert calls["n"] == 1
        assert first == second == {"count": 1}
    finally:
        db.close()
