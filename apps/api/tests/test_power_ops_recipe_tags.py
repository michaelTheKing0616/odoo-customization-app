"""Power Ops recipe metadata (tags / min_major) — no live Odoo."""

from __future__ import annotations

from app.power_ops_recipes import get_recipe, list_recipes


def test_list_recipes_exposes_tags_and_min_major() -> None:
    rows = list_recipes()
    assert len(rows) >= 8
    for row in rows:
        assert "tags" in row
        assert isinstance(row["tags"], list)
        assert isinstance(row["min_major"], int)
        assert row["min_major"] >= 16


def test_accounting_recipes_tagged() -> None:
    purge = get_recipe("purge_journal_entries")
    assert purge is not None
    assert "accounting" in purge.tags
    assert "account" in purge.requires_modules
    assert "destructive" in purge.tags


def test_generic_archive_tagged() -> None:
    archive = get_recipe("mass_archive")
    assert archive is not None
    assert "generic" in archive.tags
    assert "archive" in archive.tags
