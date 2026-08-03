"""Expert RAG ingest unit tests (chunker, store, retrieval — no live git/model)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import delete

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("AI_RAG", "off")
os.environ.setdefault("EXPERT_COMMUNITY_SOURCE", "off")

from app import ai_rag  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.db_models import ExpertChunk  # noqa: E402
from app.expert.chunker import (  # noqa: E402
    SPLIT_THRESHOLD,
    DocChunk,
    chunk_document,
    estimate_tokens,
)
from app.expert.retrieval import retrieve_expert_chunks  # noqa: E402
from app.expert.store import content_hash, upsert_chunks  # noqa: E402
from app.settings import settings  # noqa: E402

FIXTURE_RST = Path(__file__).parent / "fixtures" / "expert" / "sample_views.rst"


@pytest.fixture()
def db_session():
    init_db()
    db = SessionLocal()
    try:
        db.execute(delete(ExpertChunk))
        db.commit()
        yield db
    finally:
        db.close()


def test_cosine_similarity_exported() -> None:
    assert ai_rag.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert ai_rag.cosine_similarity([], [1.0]) == 0.0


def test_chunk_rst_breadcrumbs_and_integrity() -> None:
    text = FIXTURE_RST.read_text(encoding="utf-8")
    chunks = chunk_document(text, source_path="sample_views.rst", fmt="rst")
    assert chunks
    breadcrumbs = [c.breadcrumb for c in chunks]
    assert any("Developer Documentation" in bc for bc in breadcrumbs)
    assert any("Views" in bc for bc in breadcrumbs) or any("views" in c.text.lower() for c in chunks)
    assert any("inheritance" in c.text.lower() for c in chunks)
    for chunk in chunks:
        assert chunk.text.strip()
        assert "Developer Documentation" in chunk.breadcrumb or "Document" in chunk.breadcrumb


def test_chunk_no_mid_section_split_for_small_sections() -> None:
    text = """Title\n=====\n\nIntro body.\n\nSection A\n---------\n\nShort section stays whole.\n"""
    chunks = chunk_document(text, fmt="rst")
    assert len(chunks) == 1
    assert "Short section stays whole." in chunks[0].text


def test_chunk_oversized_section_gets_continuation_markers() -> None:
    paragraphs = ["Word " * 120 for _ in range(12)]
    body = "\n\n".join(paragraphs)
    assert estimate_tokens(body) > SPLIT_THRESHOLD
    text = f"Title\n=====\n\nBig Section\n------------\n\n{body}\n"
    chunks = chunk_document(text, fmt="rst")
    assert len(chunks) >= 2
    joined = "\n".join(c.text for c in chunks)
    assert "(continued from" in joined
    assert "(continued)" in joined


def test_chunk_respects_token_bounds_when_merging() -> None:
    text = FIXTURE_RST.read_text(encoding="utf-8")
    chunks = chunk_document(text, source_path="sample_views.rst", fmt="rst")
    for chunk in chunks:
        tokens = estimate_tokens(chunk.text)
        assert tokens <= SPLIT_THRESHOLD + 200


def test_chunk_markdown_headings() -> None:
    md = "## Child\n\nChild body about views and xpath inheritance in Odoo forms.\n"
    chunks = chunk_document(md, fmt="md")
    assert any("Child" in c.breadcrumb for c in chunks)
    assert any("xpath" in c.text for c in chunks)


def test_store_upsert_by_content_hash(db_session) -> None:
    chunk = DocChunk(breadcrumb="Test > Doc", text="Unique ingest body for hash test.")
    stats1 = upsert_chunks(
        db_session, source="project", version="all", chunks=[chunk], embed=False
    )
    assert stats1.inserted == 1
    stats2 = upsert_chunks(
        db_session, source="project", version="all", chunks=[chunk], embed=False
    )
    assert stats2.skipped == 1
    digest = content_hash("project", "all", chunk.breadcrumb, chunk.text)
    row = db_session.query(ExpertChunk).filter_by(content_hash=digest).one()
    assert row.source == "project"


def test_retrieve_version_filter(db_session) -> None:
    upsert_chunks(
        db_session,
        source="odoo_docs",
        version="19.0",
        chunks=[DocChunk(breadcrumb="Views", text="Odoo 19 view inheritance xpath guide.")],
        embed=False,
    )
    upsert_chunks(
        db_session,
        source="odoo_docs",
        version="18.0",
        chunks=[DocChunk(breadcrumb="Views", text="Odoo 18 legacy view inheritance guide.")],
        embed=False,
    )
    upsert_chunks(
        db_session,
        source="project",
        version="all",
        chunks=[DocChunk(breadcrumb="Matrix", text="Capability matrix for all versions.")],
        embed=False,
    )
    hits = retrieve_expert_chunks(db_session, "view inheritance xpath", version="19.0", min_score=0.01)
    versions = {h.version for h in hits}
    assert "18.0" not in versions
    assert "19.0" in versions or "all" in versions


def test_retrieve_project_source_boost(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    upsert_chunks(
        db_session,
        source="odoo_docs",
        version="19.0",
        chunks=[DocChunk(breadcrumb="Docs", text="view inheritance xpath documentation")],
        embed=False,
    )
    upsert_chunks(
        db_session,
        source="project",
        version="all",
        chunks=[DocChunk(breadcrumb="Project", text="view inheritance xpath documentation")],
        embed=False,
    )
    monkeypatch.setattr(ai_rag, "embed_texts", lambda texts: None)
    settings.ai_rag = "off"
    hits = retrieve_expert_chunks(
        db_session, "view inheritance xpath", version="19.0", min_score=0.01, top_k=2
    )
    assert hits
    assert hits[0].source == "project"
    assert hits[0].score > hits[1].score


def test_expert_lazy_exports_and_cache_paths() -> None:
    import app.expert as expert
    from app.expert.fetcher import cache_root, version_cache_dir

    assert expert.chunk_document is not None
    assert expert.retrieve_expert_chunks is not None
    root = cache_root()
    assert root.name == "expert"
    assert version_cache_dir("19.0").name == "odoo_docs_19_0"
