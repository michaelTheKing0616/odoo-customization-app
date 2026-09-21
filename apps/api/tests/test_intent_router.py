"""Intent → feature router — deterministic catalog (no live Odoo / no LLM)."""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.intent_router import route_intent
from app.intent_router.loader import load_features, reload_catalog


@pytest.fixture(autouse=True)
def _reload():
    reload_catalog()
    yield
    reload_catalog()


def test_catalog_merges_atlas_and_static():
    features = load_features()
    ids = {f.id for f in features}
    assert "journal.batch" in ids
    assert any(f.id.startswith("atlas.") for f in features)
    assert any(f.id.startswith("recipe.") for f in features)
    assert any(f.recipe == "accounting.lock_dates" for f in features)


def test_journal_prompt_routes_to_journal_batch():
    r = route_intent("upload 200 journal entries", connection_id="conn-1")
    assert r["can_handle"] == "true"
    assert r["llm_used"] is False
    top = r["matches"][0]
    assert top["route"] == "journal?tab=batch"
    assert top["deep_link"] == "/connections/conn-1/journal?tab=batch"
    assert top["recipe"] == "accounting.journal_batch"
    assert "journal" in top["why"].lower() or "Journal" in top["title"]


def test_partners_products_route_to_master_data():
    r = route_intent("bulk create customers", connection_id="c1")
    assert r["can_handle"] == "true"
    top = r["matches"][0]
    assert top["route"] == "journal?tab=master"
    assert "master" in top["deep_link"]


def test_invoices_route_to_document_batch():
    r = route_intent("upload customer invoices from csv", connection_id="c1")
    assert r["can_handle"] == "true"
    top = r["matches"][0]
    assert top["route"] == "journal?tab=invoices"
    assert top.get("recipe") in {None, "document_batch.invoices"} or "invoice" in top["title"].lower()


def test_lock_dates_route_to_atlas_recipe():
    r = route_intent("lock accounting dates", connection_id="c1")
    assert r["can_handle"] == "true"
    top = r["matches"][0]
    assert top["route"] == "config"
    assert top.get("recipe") == "accounting.lock_dates" or "lock" in top["title"].lower()


def test_sms_blast_unsupported_honest():
    r = route_intent("send SMS blast to all customers", connection_id="c1")
    assert r["can_handle"] == "false"
    assert r["matches"] == []
    assert "sms" in r["message"].lower() or "WhatsApp" in r["message"]
    assert "does not" in r["message"].lower() or "not" in r["message"].lower()


def test_ambiguous_returns_ranked_alternatives():
    r = route_intent("partners or invoices bulk upload", connection_id="c1")
    assert r["matches"], "expected at least one match"
    # Alternatives or ambiguous flag — ranked options for the operator
    assert r.get("alternatives") or r.get("ambiguous")
    if r.get("alternatives"):
        assert r["alternatives"][0]["confidence"] <= r["matches"][0]["confidence"] + 1e-9


def test_visitor_log_routes_to_studio():
    r = route_intent("build a visitor log app", connection_id="c1")
    assert r["can_handle"] == "true"
    assert r["matches"][0]["route"] == "studio"


def test_llm_not_required_when_off():
    assert os.environ.get("AI_INTENT_LLM", "off").lower() in {"off", "0", "false", "no", ""}
    r = route_intent("mass edit many records", connection_id="c1")
    assert r["llm_used"] is False
    assert r["source"] in {"deterministic", "unsupported_catalog"}
