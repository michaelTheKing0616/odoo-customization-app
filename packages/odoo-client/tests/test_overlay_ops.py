"""Overlay xpath builders (UIX-6 / REM-6)."""

from __future__ import annotations

import pytest

from odoo_client.view_arch import (
    merge_inherit_data_arch,
    render_overlay_hide_arch,
    render_overlay_move_arch,
    render_overlay_operation_arch,
    validate_xpath_arch,
)


def test_overlay_hide_form() -> None:
    arch = render_overlay_hide_arch("//field[@name='email']", view_type="form")
    assert 'name="invisible"' in arch
    assert validate_xpath_arch(arch) == []


def test_overlay_hide_escapes_double_quotes_in_expr() -> None:
    arch = render_overlay_hide_arch('//field[@name="email"]', view_type="form")
    assert "&quot;" in arch
    assert validate_xpath_arch(arch) == []


def test_overlay_hide_list() -> None:
    arch = render_overlay_hide_arch("//field[@name='email']", view_type="list")
    assert 'name="column_invisible"' in arch


def test_overlay_move_nested() -> None:
    arch = render_overlay_move_arch(
        "//field[@name='phone']",
        "//field[@name='email']",
        position="after",
    )
    assert 'position="move"' in arch
    assert validate_xpath_arch(arch) == []


def test_merge_inherit_appends_xpath() -> None:
    first = render_overlay_hide_arch("//field[@name='a']", view_type="form")
    second = render_overlay_hide_arch("//field[@name='b']", view_type="form")
    merged = merge_inherit_data_arch(first, second)
    assert merged.count("<xpath") == 2


def test_render_overlay_operation_relabel_group() -> None:
    arch = render_overlay_operation_arch(
        "relabel",
        expr="//field[@name='name']",
        view_type="form",
        field_name="name",
        string="Contact name",
        label_target="group",
    )
    assert "//group[.//field[@name='name']]" in arch
    assert "Contact name" in arch


def test_render_overlay_add_field() -> None:
    arch = render_overlay_operation_arch(
        "add_field",
        expr="//field[@name='email']",
        view_type="form",
        add_field_name="x_note",
        add_position="after",
    )
    assert 'name="x_note"' in arch


def test_merge_rejects_non_data_root() -> None:
    with pytest.raises(ValueError, match="data"):
        merge_inherit_data_arch("<form/>", "<data/>")
