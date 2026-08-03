"""Curated widget catalog validation."""

import pytest

from odoo_client.widget_catalog import validate_widget_for_ttype, widgets_for_ttype


def test_char_widgets_include_email() -> None:
    ids = {w.id for w in widgets_for_ttype("char")}
    assert "email" in ids
    assert "barcode" in ids


def test_validate_accepts_curated_widget() -> None:
    assert validate_widget_for_ttype("char", "phone") == "phone"


def test_validate_rejects_unknown_widget() -> None:
    with pytest.raises(ValueError, match="curated"):
        validate_widget_for_ttype("char", "not_a_real_widget")


def test_many2many_tags_allowed() -> None:
    assert validate_widget_for_ttype("many2many", "many2many_tags") == "many2many_tags"
