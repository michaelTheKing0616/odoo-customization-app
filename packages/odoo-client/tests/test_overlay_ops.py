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


PARTNER_FORM = """
<form>
  <sheet>
    <group id="header_left_group">
      <field name="email"/>
    </group>
    <notebook>
      <page string="Main">
        <field name="name"/>
      </page>
    </notebook>
  </sheet>
</form>
"""


def test_overlay_add_page_inside_named_notebook() -> None:
    arch = render_overlay_operation_arch(
        "add_page",
        expr="",
        view_type="form",
        string="Notes",
        parent_arch=PARTNER_FORM,
    )
    assert 'position="inside"' in arch
    assert 'name="x_page_notes"' in arch
    assert "Notes" in arch
    assert "//notebook" in arch
    inner = arch[arch.find("<xpath") : arch.find("</xpath>")]
    assert "<page" in inner
    assert "<notebook" not in inner
    assert validate_xpath_arch(arch, parent_arch=PARTNER_FORM) == []


def test_overlay_add_page_creates_notebook_when_missing() -> None:
    parent = '<form><sheet><group id="g"><field name="email"/></group></sheet></form>'
    arch = render_overlay_operation_arch(
        "add_page",
        expr="",
        view_type="form",
        string="Extra",
        parent_arch=parent,
    )
    assert "//sheet" in arch
    assert "<notebook>" in arch
    assert 'name="x_page_extra"' in arch
    assert validate_xpath_arch(arch, parent_arch=parent) == []


def test_overlay_add_group_semantic_inject() -> None:
    arch = render_overlay_operation_arch(
        "add_group",
        expr="//group[@id='header_left_group']",
        view_type="form",
        string="Flags",
        add_position="after",
        add_field_name="x_flag",
        parent_arch=PARTNER_FORM,
    )
    assert 'name="x_group_flags"' in arch
    assert 'name="x_flag"' in arch
    assert 'position="after"' in arch
    assert validate_xpath_arch(arch, parent_arch=PARTNER_FORM) == []


def test_overlay_move_inside_group() -> None:
    arch = render_overlay_operation_arch(
        "move",
        expr="//field[@name='email']",
        view_type="form",
        anchor_expr="//group[@id='header_left_group']",
        move_position="inside",
    )
    assert 'position="inside"' in arch
    assert 'position="move"' in arch
    assert validate_xpath_arch(arch) == []


def test_overlay_kanban_add_field_defaults_to_card() -> None:
    kanban = '<kanban><templates><t t-name="card"><field name="name"/></t></templates></kanban>'
    arch = render_overlay_operation_arch(
        "add_field",
        expr="",
        view_type="kanban",
        add_field_name="email",
        parent_arch=kanban,
    )
    assert "t-name=" in arch
    assert 'name="email"' in arch


def test_overlay_search_add_field_inside_search() -> None:
    arch = render_overlay_operation_arch(
        "add_field",
        expr="",
        view_type="search",
        add_field_name="email",
        parent_arch="<search><field name='name'/></search>",
    )
    assert "//search" in arch
    assert 'name="email"' in arch
    assert 'position="inside"' in arch
