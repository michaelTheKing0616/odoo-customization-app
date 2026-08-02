"""Unit tests for kanban arch rendering (Phase P2) + adversarial parse round-trips."""

import pytest

from odoo_client.view_arch import (
    KanbanViewSpec,
    parse_arch,
    parse_kanban_arch,
    render_arch,
    render_kanban_arch,
)


def test_render_kanban_arch_with_group_by() -> None:
    arch = render_kanban_arch(
        string="Loans",
        records_fields=["x_name", "x_book_id", "x_returned"],
        default_group_by="x_returned",
    )
    assert '<kanban string="Loans"' in arch
    assert 'default_group_by="x_returned"' in arch
    assert 't-name="card"' in arch
    assert 'name="x_name"' in arch
    assert 'name="x_book_id"' in arch
    assert 'name="x_returned"' in arch


def test_render_kanban_arch_empty_card() -> None:
    arch = render_kanban_arch(string="Board", records_fields=[])
    assert "<kanban" in arch
    assert "default_group_by" not in arch
    assert "<div" in arch or "card" in arch


def test_render_arch_kanban_type() -> None:
    arch = render_arch(
        "kanban",
        {
            "string": "Loans",
            "records_fields": ["x_name", "x_member_id"],
            "default_group_by": "x_returned",
        },
    )
    assert 'default_group_by="x_returned"' in arch
    assert 'name="x_member_id"' in arch


def test_kanban_view_spec_validate() -> None:
    spec = KanbanViewSpec(
        string="Books",
        records_fields=["x_name", "x_status"],
        default_group_by="x_status",
    )
    arch = render_kanban_arch(
        string=spec.string,
        records_fields=spec.records_fields,
        default_group_by=spec.default_group_by,
    )
    assert 'default_group_by="x_status"' in arch


def test_kanban_parse_render_round_trip_preserves_order() -> None:
    """Designer load → edit order → save must keep card field order."""
    ordered = ["x_name", "x_member_id", "x_book_id", "x_returned"]
    arch = render_kanban_arch(
        string="Loans",
        records_fields=ordered,
        default_group_by="x_returned",
    )
    parsed = parse_kanban_arch(arch)
    assert parsed.records_fields == ordered
    assert parsed.default_group_by == "x_returned"
    assert parsed.string == "Loans"

    # Reorder in UI, then re-render (save path)
    reordered = ["x_returned", "x_name", "x_book_id", "x_member_id"]
    saved = render_arch(
        "kanban",
        {
            "string": parsed.string,
            "records_fields": reordered,
            "default_group_by": parsed.default_group_by,
        },
    )
    again = parse_arch("kanban", saved)
    assert again["records_fields"] == reordered
    assert again["default_group_by"] == "x_returned"


def test_parse_kanban_prefers_card_template_fields() -> None:
    arch = """
    <kanban string="Board" default_group_by="x_status">
      <field name="x_status"/>
      <templates>
        <t t-name="card">
          <field name="x_name"/>
          <field name="x_isbn"/>
        </t>
      </templates>
    </kanban>
    """
    spec = parse_kanban_arch(arch)
    assert spec.records_fields == ["x_name", "x_isbn"]
    assert spec.default_group_by == "x_status"


def test_parse_kanban_unwraps_inherit_replace() -> None:
    from odoo_client.view_arch import render_inherit_replace_arch

    inner = render_kanban_arch(
        string="Board",
        records_fields=["x_name", "x_stage"],
        default_group_by="x_stage",
    )
    wrapped = render_inherit_replace_arch("kanban", inner)
    assert wrapped.strip().startswith("<data>")
    spec = parse_kanban_arch(wrapped)
    assert spec.records_fields == ["x_name", "x_stage"]
    assert spec.default_group_by == "x_stage"


def test_parse_kanban_adversarial_empty_card_and_attrs() -> None:
    arch = """
    <kanban class="o_kanban_mobile" create="0" default_group_by="">
      <templates>
        <t t-name="kanban-box"><div/></t>
        <t t-name="card">
          <div class="oe_kanban_details"/>
        </t>
      </templates>
    </kanban>
    """
    spec = parse_kanban_arch(arch)
    assert spec.records_fields == []
    # empty attribute → falsy string; parser returns the attribute value as-is
    assert spec.default_group_by in (None, "")
    assert spec.string == "Kanban"


def test_parse_kanban_dedupes_duplicate_card_fields() -> None:
    arch = """
    <kanban string="Dupes">
      <templates>
        <t t-name="card">
          <field name="x_name"/>
          <field name="x_status"/>
          <field name="x_name"/>
        </t>
      </templates>
    </kanban>
    """
    spec = parse_kanban_arch(arch)
    assert spec.records_fields == ["x_name", "x_status"]


def test_parse_kanban_ignores_non_card_template_fields() -> None:
    arch = """
    <kanban string="Board" default_group_by="x_stage">
      <field name="x_noise"/>
      <templates>
        <t t-name="kanban-box">
          <field name="x_ignored"/>
        </t>
        <t t-name="card">
          <field name="x_title"/>
        </t>
      </templates>
    </kanban>
    """
    spec = parse_kanban_arch(arch)
    assert spec.records_fields == ["x_title"]
    assert "x_noise" not in spec.records_fields
    assert "x_ignored" not in spec.records_fields


def test_parse_kanban_rejects_non_kanban_root() -> None:
    with pytest.raises(ValueError, match="Expected <kanban>"):
        parse_kanban_arch('<form><field name="x_name"/></form>')


def test_parse_kanban_unwrap_data_without_replace_xpath_falls_through() -> None:
    """Adversarial inherit: <data> without replace xpath is not unwrapped as kanban."""
    arch = """
    <data>
      <xpath expr="//kanban" position="inside">
        <field name="x_extra"/>
      </xpath>
    </data>
    """
    with pytest.raises(ValueError, match="Expected <kanban>"):
        parse_kanban_arch(arch)


def test_parse_kanban_unwrap_nested_replace_round_trip() -> None:
    from odoo_client.view_arch import render_inherit_replace_arch

    ordered = ["x_a", "x_b", "x_c"]
    inner = render_kanban_arch(
        string="Adv",
        records_fields=ordered,
        default_group_by="x_b",
    )
    wrapped = render_inherit_replace_arch("kanban", inner)
    parsed = parse_kanban_arch(wrapped)
    assert parsed.records_fields == ordered
    re_rendered = render_kanban_arch(
        string=parsed.string,
        records_fields=parsed.records_fields,
        default_group_by=parsed.default_group_by,
    )
    again = parse_kanban_arch(re_rendered)
    assert again.records_fields == ordered
    assert again.default_group_by == "x_b"


def test_parse_kanban_malformed_xml_raises() -> None:
    with pytest.raises(Exception):
        parse_kanban_arch("<kanban><field name='x_name'></kanban>")


def test_kanban_parse_via_parse_arch_dispatch() -> None:
    arch = render_kanban_arch(
        string="Dispatch",
        records_fields=["x_name"],
        default_group_by="x_name",
    )
    data = parse_arch("kanban", arch)
    assert data["records_fields"] == ["x_name"]
    assert data["default_group_by"] == "x_name"
    assert data["string"] == "Dispatch"
