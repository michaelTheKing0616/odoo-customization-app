"""SQLAlchemy engine/session for the app metadata store."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import settings


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


def init_db() -> None:
    # Import models so metadata is registered.
    from app import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_schema_columns()


def _ensure_schema_columns() -> None:
    """Add columns create_all will not add on existing tables (dev-friendly)."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "promoted_modules" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("promoted_modules")}
        if "models_json" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE promoted_modules ADD COLUMN models_json TEXT"))

    if "odoo_connections" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("odoo_connections")}
        with engine.begin() as conn:
            if "protected_manifest_json" not in cols:
                conn.execute(
                    text("ALTER TABLE odoo_connections ADD COLUMN protected_manifest_json TEXT")
                )
            if "protected_manifest_version" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE odoo_connections ADD COLUMN protected_manifest_version VARCHAR(20)"
                    )
                )
            if "last_seen_version" not in cols:
                conn.execute(text("ALTER TABLE odoo_connections ADD COLUMN last_seen_version VARCHAR(50)"))
            if "upgrade_detected" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE odoo_connections ADD COLUMN upgrade_detected BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )
            if "upgrade_detected_at" not in cols:
                conn.execute(
                    text("ALTER TABLE odoo_connections ADD COLUMN upgrade_detected_at TIMESTAMPTZ")
                )
            if "preview_theme_json" not in cols:
                conn.execute(text("ALTER TABLE odoo_connections ADD COLUMN preview_theme_json TEXT"))
            if "preview_theme_json" not in cols:
                conn.execute(text("ALTER TABLE odoo_connections ADD COLUMN preview_theme_json TEXT"))

    _ensure_connection_fks(inspector)


def _ensure_connection_fks(inspector) -> None:
    """Add ON DELETE CASCADE FKs for connection-scoped tables when missing (Postgres)."""
    from sqlalchemy import text

    tables = {
        "metadata_snapshots": "fk_metadata_snapshots_connection_id",
        "sandbox_validations": "fk_sandbox_validations_connection_id",
        "promoted_modules": "fk_promoted_modules_connection_id",
        "background_jobs": "fk_background_jobs_connection_id",
        "customization_projects": "fk_customization_projects_connection_id",
        "health_check_runs": "fk_health_check_runs_connection_id",
        "approval_rules": "fk_approval_rules_connection_id",
        "approval_entries": "fk_approval_entries_connection_id",
    }
    existing = {t for t in tables if t in inspector.get_table_names()}
    if not existing:
        return

    dialect = engine.dialect.name
    if dialect != "postgresql":
        return

    with engine.begin() as conn:
        for table, constraint in tables.items():
            if table not in existing:
                continue
            # Drop orphan rows that would block FK creation
            conn.execute(
                text(
                    f"""
                    DELETE FROM {table}
                    WHERE connection_id IS NOT NULL
                      AND connection_id NOT IN (SELECT id FROM odoo_connections)
                    """
                )
            )
            has_fk = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE table_name = :table
                      AND constraint_type = 'FOREIGN KEY'
                      AND constraint_name = :name
                    """
                ),
                {"table": table, "name": constraint},
            ).scalar()
            if has_fk:
                continue
            # Drop any other FK on connection_id so we can recreate with CASCADE
            old = conn.execute(
                text(
                    """
                    SELECT constraint_name FROM information_schema.table_constraints
                    WHERE table_name = :table AND constraint_type = 'FOREIGN KEY'
                    """
                ),
                {"table": table},
            ).scalars().all()
            for name in old:
                conn.execute(text(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{name}"'))
            conn.execute(
                text(
                    f"""
                    ALTER TABLE {table}
                    ADD CONSTRAINT {constraint}
                    FOREIGN KEY (connection_id) REFERENCES odoo_connections(id)
                    ON DELETE CASCADE
                    """
                )
            )

