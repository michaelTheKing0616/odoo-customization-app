"""Config Atlas + recipe registry (no live Odoo / no app DB)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.no_app_db

from app.batch_os.atlas.loader import list_atlas, reload_atlas, search_atlas
from app.batch_os.recipes.registry import get_recipe, list_recipes
from app.batch_os.types import HONESTY_PREVIEW_NE_POSTED


def test_atlas_seed_has_eight_classes_and_accounting_complete():
    reload_atlas()
    classes = list_atlas()
    ids = {c["id"] for c in classes}
    assert len(classes) == 8
    assert ids == {
        "accounting",
        "master_data",
        "document_batch",
        "settings",
        "access_company",
        "automation",
        "ui_studio",
        "housekeeping",
    }
    accounting = next(c for c in classes if c["id"] == "accounting")
    assert accounting["status"] == "complete"
    intent_ids = {i["id"] for i in accounting["intents"]}
    assert "accounting.journal_batch" in intent_ids
    assert "accounting.lock_dates" in intent_ids
    assert "accounting.opening_balances" in intent_ids
    lock = next(i for i in accounting["intents"] if i["id"] == "accounting.lock_dates")
    assert lock["risk"] == "L3"
    assert lock["recipe"] == "accounting.lock_dates"


def test_atlas_search_lock_dates():
    hits = search_atlas("lock")
    assert any(h["intent_id"] == "accounting.lock_dates" for h in hits)
    assert all(h["risk"] == "L3" for h in hits if h["intent_id"] == "accounting.lock_dates")


def test_recipe_registry_p0():
    cards = {c.id: c for c in list_recipes()}
    assert "accounting.journal_batch" in cards
    assert cards["accounting.journal_batch"].status == "complete"
    assert cards["accounting.lock_dates"].risk == "L3"
    assert get_recipe("accounting.opening_balances") is not None
    stubs = [c for c in list_recipes() if c.status == "stub"]
    assert len(stubs) == 0  # Batch OS series complete — zero stub recipes
    assert HONESTY_PREVIEW_NE_POSTED


def test_document_and_tax_recipes_registered():
    cards = {c.id: c for c in list_recipes()}
    assert cards["document_batch.invoices"].status == "complete"
    assert cards["document_batch.payments"].risk == "L2"
    assert cards["accounting.tax_pack"].status == "complete"
    assert get_recipe("accounting.fiscal_year") is not None


def test_all_atlas_classes_complete_and_intents_wired():
    reload_atlas()
    classes = list_atlas()
    assert len(classes) == 8
    for c in classes:
        assert c["status"] == "complete", c
        for intent in c["intents"]:
            assert intent.get("models"), intent
            assert intent.get("risk"), intent
            assert intent.get("status") in {"complete", "stub"}, intent
            # every intent either has a recipe id or is an explicit catalog pointer (recipe null)
            assert "recipe" in intent
