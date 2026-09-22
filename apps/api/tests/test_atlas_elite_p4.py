"""P4 Config Atlas elite — class-wide gates (AI_INTENT_LLM=off)."""

from __future__ import annotations

import os

import pytest

os.environ["AI_INTENT_LLM"] = "off"

pytestmark = pytest.mark.no_app_db

from app.ai_atlas_elite import (
    atlas_zero_stub_intents,
    is_atlas_config_batch_brief,
    resolve_atlas_handoff,
)
from app.ai_build_spine import build_spine_payload, resolve_build_mode
from app.ai_class_stamp import resolve_class_stamp
from app.batch_os.atlas.loader import list_atlas, reload_atlas, search_atlas
from app.batch_os.recipes.registry import get_recipe, list_recipes
from app.batch_os.types import HONESTY_PREVIEW_NE_CONFIRMED, HONESTY_PREVIEW_NE_POSTED
from app.intent_router import route_intent
from app.intent_router.loader import reload_catalog


@pytest.fixture(autouse=True)
def _reload():
    reload_atlas()
    reload_catalog()
    yield
    reload_atlas()
    reload_catalog()


def test_zero_stub_atlas_intents_and_orders_recipe():
    assert atlas_zero_stub_intents() is True
    reload_atlas()
    classes = list_atlas()
    assert len(classes) == 8
    for c in classes:
        assert c["status"] == "complete"
        for intent in c["intents"]:
            assert intent["status"] != "stub", intent
    orders = next(
        i
        for c in classes
        if c["id"] == "document_batch"
        for i in c["intents"]
        if i["id"] == "docs.orders"
    )
    assert orders["status"] == "complete"
    assert orders["recipe"] == "document_batch.orders"
    assert get_recipe("document_batch.orders") is not None
    stubs = [c for c in list_recipes() if c.status == "stub"]
    assert stubs == []


def test_search_risk_craft_l3_lock_and_honesty():
    hits = search_atlas("lock")
    assert any(h["intent_id"] == "accounting.lock_dates" for h in hits)
    lock = next(h for h in hits if h["intent_id"] == "accounting.lock_dates")
    assert lock["risk"] == "L3"
    assert lock["status"] == "complete"
    assert HONESTY_PREVIEW_NE_POSTED
    assert HONESTY_PREVIEW_NE_CONFIRMED
    assert "not confirmed" in HONESTY_PREVIEW_NE_CONFIRMED.lower()


@pytest.mark.parametrize(
    "brief,recipe,atlas_class,risk",
    [
        ("lock accounting dates for period close", "accounting.lock_dates", "accounting", "L3"),
        ("apply NG tax pack via RPC", "accounting.tax_pack", "accounting", "L2"),
        ("partners CSV bulk create customers", "master_data.partners_batch", "master_data", "L1"),
        ("upload invoices document batch", "document_batch.invoices", "document_batch", "L1"),
        ("upload sales orders CSV batch", "document_batch.orders", "document_batch", "L1"),
        ("purchase order batch from spreadsheet", "document_batch.orders", "document_batch", "L1"),
        ("settings board payment terms pack", "settings.board_apply", "settings", "L2"),
    ],
)
def test_multi_brief_atlas_goldens(brief, recipe, atlas_class, risk):
    assert is_atlas_config_batch_brief(brief) is True
    handoff = resolve_atlas_handoff(brief)
    assert handoff is not None
    assert handoff["recipe_id"] == recipe
    assert handoff["atlas_class"] == atlas_class
    assert handoff["risk"] == risk
    assert handoff["delivery_lane"] == "online_metadata"
    assert handoff["artifact_kind"] == "stock_config"

    stamp = resolve_class_stamp(prompt=brief)
    assert stamp["artifact_kind"] == "stock_config"
    assert stamp["delivery_lane"] == "online_metadata"

    payload = build_spine_payload(prompt=brief, connection_id="c1")
    assert payload["artifact_kind"] == "stock_config"
    assert payload["build_mode"] == "stock_autopilot"
    assert payload["atlas_class"] == atlas_class
    assert payload["recipe_id"] == recipe
    assert payload["risk"] == risk
    assert payload["delivery_lane"] == "online_metadata"
    active = next(c for c in payload["chips"] if c["active"])
    assert "/connections/c1/" in active["href"]
    assert "studio" not in active["href"] or "config" in active["href"] or "journal" in active["href"]


def test_prefer_and_option_a_not_stolen_by_atlas():
    assert is_atlas_config_batch_brief(
        "Prefer for delivery checkbox and Delivery notes on Contacts under Delivery group"
    ) is False
    assert is_atlas_config_batch_brief(
        "add a field on Sales Orders for customer PO number"
    ) is False
    assert is_atlas_config_batch_brief(
        "add markup percent and withholding tax compute on Sales quotations"
    ) is False
    prefer = resolve_class_stamp(
        prompt="Prefer for delivery checkbox and Delivery notes on Contacts",
        grain="field_pack",
        inherit_only=True,
    )
    assert prefer["artifact_kind"] == "field_pack"
    markup = resolve_class_stamp(
        prompt="markup percent and withholding tax on sale.order",
        capability="option_a_authored",
        needs_module=True,
        module_delivery=True,
    )
    assert markup["artifact_kind"] == "option_a_module"


def test_intent_routes_order_batch_and_lock_dates():
    orders = route_intent("upload sales orders CSV batch", connection_id="c1")
    assert orders["matches"]
    top = orders["matches"][0]
    assert top["recipe"] == "document_batch.orders" or "order" in top["feature_id"]
    assert top["can_handle"] in {"true", "partial"}
    assert "orders" in top["route"] or top.get("atlas_class") == "document_batch"

    lock = route_intent("lock accounting dates", connection_id="c1")
    assert lock["matches"]
    ltop = lock["matches"][0]
    assert ltop["recipe"] == "accounting.lock_dates" or "lock" in ltop["feature_id"]
    assert ltop.get("risk") in {None, "L3"} or ltop["recipe"] == "accounting.lock_dates"


def test_resolve_build_mode_stock_config_chip():
    assert (
        resolve_build_mode(
            prompt="lock accounting dates",
            artifact_kind="stock_config",
            delivery_lane="online_metadata",
        )
        == "stock_autopilot"
    )
