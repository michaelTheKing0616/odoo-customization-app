"""WIP / projects persist across API key rotate (credential update only)."""

from __future__ import annotations

import inspect

import pytest

from app.db_models import AiDraftCache, CustomizationProject, OdooConnection
from app.routers import connections as connections_router

pytestmark = pytest.mark.no_app_db


def _fk_ondelete(table, column: str) -> str | None:
    col = table.c[column]
    fks = list(col.foreign_keys)
    assert fks, f"{table.name}.{column} missing FK"
    return fks[0].ondelete


def test_wip_tables_cascade_only_when_connection_deleted() -> None:
    assert _fk_ondelete(CustomizationProject.__table__, "connection_id") == "CASCADE"
    assert _fk_ondelete(AiDraftCache.__table__, "connection_id") == "CASCADE"
    # Secret lives on the connection row; rotating it is an UPDATE, not DELETE.
    assert "secret_encrypted" in OdooConnection.__table__.c


def test_update_connection_rotates_secret_without_deleting_wip() -> None:
    src = inspect.getsource(connections_router.update_connection)
    assert "secret_encrypted" in src
    assert "encrypt_secret" in src
    # Must not wipe connection-scoped drafts/projects on password/API key patch.
    assert "CustomizationProject" not in src
    assert "AiDraftCache" not in src
    assert "AiSession" not in src
    assert "db.delete" not in src
