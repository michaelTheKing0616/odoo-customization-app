"""Expert vertical playbook catalog, ingest, and retrieval."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("AI_RAG", "off")

from app import ai_rag  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import ExpertChunk  # noqa: E402
from app.expert.chunker import DocChunk  # noqa: E402
from app.expert.ingest import ingest_vertical_docs  # noqa: E402
from app.expert.retrieval import retrieve_expert_chunks  # noqa: E402
from app.expert.store import upsert_chunks  # noqa: E402
from app.expert.vertical_catalog import expand_expert_query, match_verticals  # noqa: E402
from app.expert.vertical_playbooks import (  # noqa: E402
    all_vertical_playbook_chunks,
    render_catalog_playbook,
    vertical_doc_paths,
)
from app.settings import settings  # noqa: E402


@pytest.fixture()
def db_session():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_vertical_catalog_matches_school_question() -> None:
    q = "build an Odoo DB for a school — modules and apps?"
    hits = match_verticals(q)
    assert hits
    assert hits[0].id == "school_education"
    expanded = expand_expert_query(q)
    assert "school" in expanded.lower()
    assert "website_slides" in expanded.lower()


def test_vertical_catalog_matches_library_question() -> None:
    q = "What do I need to setup a library management Odoo DB?"
    hits = match_verticals(q)
    assert hits
    assert hits[0].id == "library_management"
    expanded = expand_expert_query(q)
    assert "isbn" in expanded.lower()
    assert "library management" in expanded.lower()


def test_library_playbook_file_exists() -> None:
    paths = vertical_doc_paths()
    assert any(p.name == "library-management.md" for p in paths)
    hits = match_verticals("library books loans isbn overdue")
    assert hits and hits[0].id == "library_management"
    md = render_catalog_playbook(hits[0])
    assert "library_management" in md


def test_vertical_playbook_files_exist() -> None:
    paths = vertical_doc_paths()
    assert any(p.name == "school-education.md" for p in paths)
    assert len(all_vertical_playbook_chunks()) >= 10


def test_render_catalog_playbook_includes_stock_modules() -> None:
    hits = match_verticals("hotel room booking PMS")
    assert hits and hits[0].id == "hotel"
    md = render_catalog_playbook(hits[0])
    assert "`sale`" in md or "sale" in md
    assert "hotel" in md.lower()


def test_retrieve_vertical_source_boost(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    token = "zz_vertical_boost_test_token"
    upsert_chunks(
        db_session,
        source="odoo_docs",
        version="19.0",
        chunks=[
            DocChunk(
                breadcrumb=f"Docs {token}",
                text=f"{token} school education student enrollment modules contacts website crm",
            )
        ],
        embed=False,
    )
    upsert_chunks(
        db_session,
        source="vertical",
        version="all",
        chunks=[
            DocChunk(
                breadcrumb=f"Vertical playbook: School / Education {token}",
                text=f"{token} school education student enrollment modules contacts website crm sale account",
            )
        ],
        embed=False,
    )
    monkeypatch.setattr(ai_rag, "embed_texts", lambda texts: None)
    settings.ai_rag = "off"
    hits = retrieve_expert_chunks(
        db_session,
        f"Odoo DB for a school modules apps {token}",
        version="19.0",
        min_score=0.01,
        top_k=2,
    )
    assert hits
    assert hits[0].source == "vertical"
    assert token in hits[0].breadcrumb


def test_ingest_vertical_docs_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock upsert — does not write fake embeddings to the dev knowledge base."""
    from app.expert.ingest import UpsertStats

    captured: dict[str, object] = {}

    def fake_upsert(_db, *, source, version, chunks, embed=True):
        captured["source"] = source
        captured["version"] = version
        captured["count"] = len(chunks)
        return UpsertStats(inserted=len(chunks))

    monkeypatch.setattr("app.expert.ingest.upsert_chunks", fake_upsert)
    stats = ingest_vertical_docs(embed=False)
    assert stats.inserted > 10
    assert captured["source"] == "vertical"
    assert captured["version"] == "all"
