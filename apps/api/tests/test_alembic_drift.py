"""Alembic head must exist and baseline revision is loadable (PROD-2 drift gate)."""

from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_baseline_revision_exists() -> None:
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    rev = script.get_revision(heads[0])
    assert rev is not None
    assert rev.doc
    # Upgrade/downgrade callables present
    assert rev.module.upgrade is not None


def test_alembic_env_imports_models() -> None:
    from app import db_models  # noqa: F401
    from app.db import Base

    assert Base.metadata.tables
    assert "odoo_connections" in Base.metadata.tables
