"""Phone, blank keys, and fuzzy name match for imports."""

from __future__ import annotations

import pytest

from app.config_as_code.importers import dedupe_key, fuzzy_name_match, is_blank, normalize_ng_phone


def test_nigerian_phone_becomes_e164() -> None:
    assert normalize_ng_phone("08031234567") == "+2348031234567"
    assert normalize_ng_phone("+234 803 123 4567") == "+2348031234567"


def test_blank_cells_are_not_a_dedupe_key() -> None:
    assert is_blank(None) is True
    assert is_blank("  ") is True
    assert is_blank(float("nan")) is True
    assert dedupe_key({"email": "  ", "name": "Ada"}, ["email"]) is None
    assert dedupe_key({"email": "a@b.co"}, ["email"]) == "a@b.co"


def test_fuzzy_name_threshold() -> None:
    assert fuzzy_name_match("Example Foods", "Example Foods") is True
    assert fuzzy_name_match("Example Foods", "Example Food") is True
    assert fuzzy_name_match("Example Foods", "Other Shop") is False
    assert fuzzy_name_match("", "Example") is False


def test_short_phone_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_ng_phone("123")
