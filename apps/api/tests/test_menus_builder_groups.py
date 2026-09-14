"""Unit tests for menu visibility-group helpers (Odoo 17/18 groups_id vs 19 group_ids)."""

from __future__ import annotations

import pytest

from app.menu_groups import m2m_ids, menu_group_m2m_field

pytestmark = pytest.mark.no_app_db


class _FakeClient:
    def __init__(self, fields: set[str]) -> None:
        self.fields = fields

    def field_exists(self, model: str, name: str) -> bool:
        return model == "ir.ui.menu" and name in self.fields


def test_menu_group_field_prefers_odoo19_group_ids() -> None:
    assert menu_group_m2m_field(_FakeClient({"group_ids"})) == "group_ids"
    assert menu_group_m2m_field(_FakeClient({"groups_id"})) == "groups_id"
    assert menu_group_m2m_field(_FakeClient({"group_ids", "groups_id"})) == "group_ids"
    assert menu_group_m2m_field(_FakeClient(set())) is None


def test_m2m_ids_accepts_int_list_and_command_tuples() -> None:
    assert m2m_ids([4, 7]) == [4, 7]
    assert m2m_ids([(4, "Internal User"), (7, "Settings")]) == [4, 7]
    assert m2m_ids(False) == []
    assert m2m_ids(None) == []
    assert m2m_ids([True, 3]) == [3]
