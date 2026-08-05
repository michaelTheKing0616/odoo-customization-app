"""Idempotent Alembic helpers — safe when create_all() already applied schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def table_exists(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


def column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    return column in cols
