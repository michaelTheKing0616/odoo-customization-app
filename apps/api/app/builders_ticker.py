"""Background ticker for the builders (stage 2c/2d): scheduled publishes, post-publish
watch checks and the weekly digest, once a minute.

Every API worker runs the loop, but only one does the work at a time: on
PostgreSQL a session advisory lock (works across workers and hosts sharing the
database); on SQLite an exclusive file lock next to the database (one host).
Off when INGENIUM_BUILDERS_TICKER=0 and under pytest.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import tempfile
from collections.abc import Iterator

logger = logging.getLogger(__name__)
INTERVAL_S = 60.0
LOCK_KEY = 0x1A6E_2C7B  # fixed advisory-lock key for the builders ticker


def enabled() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("INGENIUM_BUILDERS_TICKER", "1").strip() in {"0", "false", "off"}:
        return False
    return True


@contextlib.contextmanager
def single_runner(engine) -> Iterator[bool]:  # noqa: ANN001
    """Yield True when this process holds the run lock, False when another does."""
    engine = getattr(engine, "engine", engine)
    if engine.dialect.name == "postgresql":
        from sqlalchemy import text

        with engine.connect() as conn:
            got = bool(conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY}).scalar())
            try:
                yield got
            finally:
                if got:
                    conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
                    conn.commit()
        return
    import fcntl

    db_file = engine.url.database if engine.dialect.name == "sqlite" and engine.url.database not in (None, "", ":memory:") else None
    path = (db_file + ".builders.lock") if db_file else os.path.join(tempfile.gettempdir(), "ingenium_builders.lock")
    with open(path, "a+") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def run_once() -> dict[str, int]:
    from app.db import SessionLocal, engine
    from app.routers import view_engine_2c as r2c
    from app.routers import view_engine_2d as r2d

    out = {"schedules": 0, "watches": 0, "digests": 0, "abtests": 0, "skipped": 0}
    with single_runner(engine) as mine:
        if not mine:
            out["skipped"] = 1
            return out
        db = SessionLocal()
        try:
            out["schedules"] = len(r2c.run_due_schedules(db))
            out["watches"] = r2c.run_due_watches(db)
            out["digests"] = r2c.run_due_digests(db)
            out["abtests"] = r2d.run_due_abtests(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("builders ticker run failed: %s", exc)
            db.rollback()
        finally:
            db.close()
    return out


async def loop() -> None:
    while True:
        await asyncio.sleep(INTERVAL_S)
        try:
            await asyncio.to_thread(run_once)
        except Exception as exc:  # noqa: BLE001
            logger.warning("builders ticker failed: %s", exc)


def start() -> asyncio.Task[None] | None:
    if not enabled():
        return None
    return asyncio.get_event_loop().create_task(loop())
