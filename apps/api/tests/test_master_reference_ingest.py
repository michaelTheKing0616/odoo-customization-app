"""MASTER_REFERENCE.md ingest + retrieval (REM-9 / EXP-2)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import delete, func

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("AI_RAG", "off")

from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import ExpertChunk  # noqa: E402
from app.expert.ingest import ingest_project_docs  # noqa: E402
from app.expert.retrieval import retrieve_expert_chunks  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
MASTER = _REPO_ROOT / "docs" / "reference" / "MASTER_REFERENCE.md"


@pytest.fixture()
def db_session():
    if not MASTER.is_file():
        pytest.skip("MASTER_REFERENCE.md not present")
    init_db()
    db = SessionLocal()
    try:
        db.execute(delete(ExpertChunk))
        db.commit()
        yield db
    finally:
        db.close()


def test_master_reference_file_exists() -> None:
    assert MASTER.is_file(), "docs/reference/MASTER_REFERENCE.md required for REM-9"


def test_master_reference_ingest_chunk_count(db_session) -> None:
    stats = ingest_project_docs(embed=False)
    assert stats.inserted > 0 or stats.updated > 0

    count = (
        db_session.query(func.count(ExpertChunk.id))
        .filter(ExpertChunk.source == "project", ExpertChunk.version == "all")
        .scalar()
    )
    assert count and count > 10

    breadcrumbs = {
        row.breadcrumb
        for row in db_session.query(ExpertChunk.breadcrumb)
        .filter(ExpertChunk.source == "project")
        .limit(50)
    }
    assert any("Tier" in bc or "Document" in bc or "Reference" in bc for bc in breadcrumbs)


def test_master_reference_retrieves_protected_tiers(db_session) -> None:
    ingest_project_docs(embed=False)
    hits = retrieve_expert_chunks(
        db_session,
        "what are the protected module tiers",
        version="19.0",
        min_score=0.01,
        top_k=5,
    )
    assert hits
    joined = " ".join(h.text.lower() for h in hits)
    assert "tier" in joined
    assert hits[0].source == "project"
