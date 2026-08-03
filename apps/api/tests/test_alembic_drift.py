"""Alembic head + model parity (PROD-2 / REM-9)."""

from __future__ import annotations

import os

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("DB_MIGRATIONS", "auto")

from app import account_models  # noqa: F401
from app import billing_models  # noqa: F401
from app import db_models  # noqa: F401
from app.db import Base, run_migrations
from app.settings import settings


def test_baseline_revision_exists() -> None:
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    rev = script.get_revision(heads[0])
    assert rev is not None
    assert rev.doc
    assert rev.module.upgrade is not None


def test_alembic_env_imports_models() -> None:
    assert Base.metadata.tables
    assert "odoo_connections" in Base.metadata.tables


@pytest.mark.integration
def test_autogenerate_produces_empty_diff_against_head() -> None:
    """Models must match applied migrations — no silent schema drift."""
    from alembic import command
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import ProgrammingError

    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not available for drift check: {exc}")

    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    head = script.get_heads()[0]

    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
        ctx = MigrationContext.configure(conn)
        current = ctx.get_current_revision()

    if current is None and "odoo_connections" in tables:
        command.stamp(cfg, head)
    elif current != head:
        try:
            command.upgrade(cfg, "head")
        except ProgrammingError as exc:
            if "already exists" in str(exc).lower():
                command.stamp(cfg, head)
                command.upgrade(cfg, "head")
            else:
                raise

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)

    ops = [d for d in diff if d[0] not in ("add_comment", "remove_comment")]
    assert not ops, f"Schema drift detected — add an Alembic revision: {ops}"
