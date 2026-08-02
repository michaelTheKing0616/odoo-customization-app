"""Unit tests for Studio feature recipe honesty catalog (M2-P0c)."""

from __future__ import annotations

from app.studio_feature_recipes import FEATURE_RECIPES, list_feature_recipes


def test_fourteen_studio_features_catalogued() -> None:
    rows = list_feature_recipes()
    assert len(rows) == 14
    ids = {r["id"] for r in rows}
    assert "contact_details" in ids
    assert "monetary_graph_pivot" in ids
    assert "date_range_gantt" in ids


def test_statuses_are_honest_literals() -> None:
    allowed = {"supported", "partial", "option_a", "module_gated", "unavailable"}
    for r in FEATURE_RECIPES:
        assert r["status"] in allowed
        assert r["how"]
        assert r["app_surfaces"]
