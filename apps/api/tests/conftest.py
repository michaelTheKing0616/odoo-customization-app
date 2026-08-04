"""Reset workspace kill-switch state before TRUST API tests."""

from __future__ import annotations

import os

# TRUST-1 defaults new connections to observer; mutating API tests expect standard unless
# they explicitly set write_mode (see test_trust1_write_mode.py).
os.environ.setdefault("TEST_DEFAULT_WRITE_MODE", "standard")

import pytest


@pytest.fixture(autouse=True)
def _unpause_workspace_writes() -> None:
    from app.account_models import Workspace
    from app.db import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        for ws in db.query(Workspace).all():
            if ws.writes_paused:
                ws.writes_paused = False
                db.add(ws)
        db.commit()
    finally:
        db.close()
