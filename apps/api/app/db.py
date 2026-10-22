"""SQLAlchemy engine/session for the app metadata store.

Migration policy (PROD-2):
- **Tests / empty local DB:** ``init_db()`` runs ``create_all`` (fast fixtures).
- **Deploy / shared hosts:** set ``DB_MIGRATIONS=auto`` so startup runs
  ``alembic upgrade head`` before serving.
- Startup does not issue ``ALTER TABLE``. New columns ship as Alembic revisions.
"""

from __future__ import annotations

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, inspect  # noqa: F401 — startup tests patch app.db.inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Apply Alembic head when DB_MIGRATIONS=auto."""
    from alembic import command
    from alembic.config import Config
    from pathlib import Path

    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    logger.info("Running alembic upgrade head")
    command.upgrade(cfg, "head")


def _is_postgres_url(url: str) -> bool:
    return url.startswith("postgresql") or "+psycopg" in url or "+asyncpg" in url


def _db_unreachable_message() -> str:
    from urllib.parse import urlparse

    raw = settings.database_url
    parsed = urlparse(raw.replace("postgresql+psycopg", "postgresql", 1))
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 5432
    return (
        f"App Postgres is not reachable at {host}:{port}. "
        "Start Docker Desktop, then run:\n"
        "  docker compose -p odoo-custom-dev -f docker/docker-compose.yml up -d app-db\n"
        "Wait until odoo-custom-app-db is healthy, then restart uvicorn."
    )


def init_db(*, bootstrap: bool = True) -> None:
    """Bootstrap schema — create_all for tests; optional Alembic when configured."""
    from app import db_models  # noqa: F401

    try:
        mode = settings.db_migrations.strip().lower()
        if mode == "auto":
            run_migrations()
            _ensure_schema_columns()
            return
        if bootstrap:
            from app import account_models  # noqa: F401
            from app import billing_models  # noqa: F401

            Base.metadata.create_all(bind=engine)
            _ensure_schema_columns()
    except OperationalError as exc:
        if _is_postgres_url(settings.database_url):
            raise RuntimeError(_db_unreachable_message()) from exc
        raise


def _ensure_schema_columns() -> None:
    """No-op. Alembic owns every column this used to ALTER."""
    return


def _ensure_connection_fks(inspector) -> None:
    """Connection ON DELETE FKs already come from Alembic revisions."""
    if inspector is None:
        return
