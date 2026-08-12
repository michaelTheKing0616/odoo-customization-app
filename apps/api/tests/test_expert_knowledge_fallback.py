"""Tests for Expert knowledge fallbacks and retrieval thresholds."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

import pytest  # noqa: E402

from app.expert.grounding import GroundingBundle  # noqa: E402
from app.expert.knowledge_fallback import (  # noqa: E402
    try_rule_based_bulk_routing,
    try_rule_based_field_type_guidance,
    try_rule_based_protected_guidance,
)
from app.expert.retrieval import retrieve_expert_chunks  # noqa: E402


@pytest.fixture
def db_session():
    from app.db import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _bundle(**kwargs) -> GroundingBundle:
    bundle = GroundingBundle(retrieval_version="19.0")
    for key, val in kwargs.items():
        setattr(bundle, key, val)
    return bundle


def test_field_type_many2one_vs_many2many() -> None:
    payload = try_rule_based_field_type_guidance(
        "When should I use many2one versus many2many?",
        _bundle(instance_summary={"server_version": "19.0"}),
    )
    assert payload is not None
    assert "Many2one" in payload["answer_markdown"]
    assert "Many2many" in payload["answer_markdown"]


def test_bulk_routing_fallback() -> None:
    payload = try_rule_based_bulk_routing(
        "How do I mass edit x_name for many records?",
        _bundle(
            suggested_tools=[
                {
                    "id": "mass_edit",
                    "label": "Mass edit",
                    "deep_link": "/connections/c1/bulk-suite",
                    "hint": "Update a field across a domain.",
                }
            ]
        ),
        connection_id="c1",
    )
    assert payload is not None
    assert "Mass edit" in payload["answer_markdown"]
    assert "/connections/c1/bulk-suite" in payload["answer_markdown"]


def test_protected_guidance_fallback() -> None:
    payload = try_rule_based_protected_guidance(
        "How should I relate x_matter to invoices safely?",
        _bundle(
            protected_flags=[
                {
                    "model": "account.move",
                    "tier": "tier_1",
                    "safe_alternative": "Use many2one link-only from x_matter.",
                }
            ]
        ),
        connection_id="c1",
    )
    assert payload is not None
    assert "account.move" in payload["answer_markdown"]
    assert "link-only" in payload["answer_markdown"].lower()


def test_jaccard_retrieval_uses_lower_threshold(db_session) -> None:
    """Chunks below embedding threshold but above jaccard threshold should match."""
    from app.db_models import ExpertChunk
    from sqlalchemy import delete

    chunk_id = "test-chunk-jaccard-threshold"
    db_session.execute(delete(ExpertChunk).where(ExpertChunk.id == chunk_id))
    db_session.add(
        ExpertChunk(
            id=chunk_id,
            source="project",
            version="all",
            breadcrumb="Developer / Fields / Relations",
            text="Many2one links one record; many2many links multiple via relation table.",
            content_hash="test-jaccard-hash-threshold-001",
            embedding_json=None,
        )
    )
    db_session.commit()

    hits = retrieve_expert_chunks(
        db_session,
        "many2one versus many2many field types",
        version="19.0",
        min_score=0.35,
    )
    assert hits, "expected jaccard fallback to return matches with lower threshold"
    db_session.execute(delete(ExpertChunk).where(ExpertChunk.id == chunk_id))
    db_session.commit()
