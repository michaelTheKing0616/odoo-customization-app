"""Unit tests for view XML serialization (no live Odoo)."""

from odoo_client.view_arch import (
    FieldNode,
    FormViewSpec,
    GroupNode,
    ListViewSpec,
    NotebookNode,
    PageNode,
    SearchViewSpec,
    field_names_in_arch,
    inject_field_into_arch,
    render_form_arch,
    render_inherit_field_arch,
    render_list_arch,
    render_search_arch,
)


def test_render_form_with_group_and_notebook() -> None:
    arch = render_form_arch(
        FormViewSpec(
            string="Ticket",
            children=[
                GroupNode(
                    string="Main",
                    children=[
                        FieldNode(name="x_name", required=True),
                        FieldNode(name="x_priority"),
                    ],
                ),
                NotebookNode(
                    pages=[
                        PageNode(
                            string="Notes",
                            children=[FieldNode(name="x_notes")],
                        )
                    ]
                ),
            ],
        )
    )
    assert '<form string="Ticket">' in arch
    assert "<sheet>" in arch
    assert '<group string="Main">' in arch
    assert '<field name="x_name" required="1"/>' in arch or 'name="x_name"' in arch
    assert '<page string="Notes">' in arch
    assert 'name="x_notes"' in arch


def test_render_form_header_and_smart_buttons() -> None:
    from odoo_client.view_arch import ButtonNode, parse_form_arch

    arch = render_form_arch(
        FormViewSpec(
            string="Book",
            header_buttons=[
                ButtonNode(string="Mark Available", name="186", type="action", class_name="btn-primary"),
            ],
            statusbar_field="x_status",
            statusbar_visible="available,loaned",
            button_box=[
                ButtonNode(
                    string="Loans",
                    name="187",
                    type="action",
                    class_name="oe_stat_button",
                    icon="fa-book",
                    count_field="x_loan_count",
                ),
            ],
            children=[
                GroupNode(string="Main", children=[FieldNode(name="x_name")]),
            ],
        )
    )
    assert "<header>" in arch
    assert 'name="186"' in arch
    assert 'type="action"' in arch
    assert 'widget="statusbar"' in arch
    assert 'statusbar_visible="available,loaned"' in arch
    assert 'name="button_box"' in arch
    assert "oe_stat_button" in arch
    assert 'icon="fa-book"' in arch
    assert 'widget="statinfo"' in arch
    assert 'name="x_loan_count"' in arch

    parsed = parse_form_arch(arch)
    assert len(parsed.header_buttons) == 1
    assert parsed.header_buttons[0].name == "186"
    assert parsed.statusbar_field == "x_status"
    assert len(parsed.button_box) == 1
    assert parsed.button_box[0].string == "Loans"
    assert parsed.button_box[0].count_field == "x_loan_count"


def test_render_inherit_xpath_and_validate() -> None:
    from odoo_client.view_arch import render_inherit_xpath_arch, validate_xpath_arch

    arch = render_inherit_xpath_arch(
        expr="//sheet",
        position="inside",
        body_xml='<field name="x_notes"/>',
    )
    assert 'expr="//sheet"' in arch
    assert validate_xpath_arch(arch) == []
    bad = validate_xpath_arch("<notxml")
    assert bad and "Invalid XML" in bad[0]


def test_render_list_columns() -> None:
    arch = render_list_arch(
        ListViewSpec(
            string="Tickets",
            columns=[
                FieldNode(name="x_name"),
                FieldNode(name="x_priority"),
            ],
        )
    )
    assert arch.startswith("<list")
    assert 'name="x_name"' in arch
    assert 'name="x_priority"' in arch


def test_inject_and_parse_fields() -> None:
    form = '<form><sheet><group><field name="x_name"/></group></sheet></form>'
    injected = inject_field_into_arch(form, "x_status", view_type="form")
    assert 'name="x_status"' in injected
    assert field_names_in_arch(injected) == ["x_name", "x_status"]
    again = inject_field_into_arch(injected, "x_status", view_type="form")
    assert again == injected

    listing = '<list string="T"><field name="x_name"/></list>'
    listing2 = inject_field_into_arch(listing, "x_code", view_type="list")
    assert listing2.endswith("</list>") or "</list>" in listing2
    assert 'name="x_code"' in listing2


def test_render_search_arch() -> None:
    arch = render_search_arch(
        SearchViewSpec(
            string="Tickets",
            fields=[FieldNode(name="x_name"), FieldNode(name="x_priority")],
        )
    )
    assert arch.startswith("<search")
    assert 'string="Tickets"' in arch
    assert 'name="x_name"' in arch
    assert 'name="x_priority"' in arch


def test_inject_into_search_arch() -> None:
    search = '<search string="T"><field name="x_name"/></search>'
    injected = inject_field_into_arch(search, "x_status", view_type="search")
    assert 'name="x_status"' in injected
    assert injected.rstrip().endswith("</search>") or "</search>" in injected
    again = inject_field_into_arch(injected, "x_status", view_type="search")
    assert again == injected
    assert field_names_in_arch(injected) == ["x_name", "x_status"]


def test_render_arch_search_type() -> None:
    from odoo_client.view_arch import render_arch

    arch = render_arch("search", {"string": "S", "fields": [{"name": "x_name"}]})
    assert "<search" in arch
    assert 'name="x_name"' in arch


def test_render_inherit_field_arch_form() -> None:
    arch = render_inherit_field_arch("x_status", "form")
    assert "<data>" in arch
    # No parent arch → default sheet (group preferred when parent has <group>).
    assert 'expr="//sheet"' in arch
    assert 'position="inside"' in arch
    assert 'name="x_status"' in arch
    grouped = render_inherit_field_arch(
        "x_status",
        "form",
        parent_arch='<form><sheet><group><field name="x_name"/></group></sheet></form>',
    )
    assert 'expr="//group[1]"' in grouped
    assert 'name="x_status"' in grouped


def test_render_inherit_field_arch_list_and_tree() -> None:
    arch = render_inherit_field_arch(
        "x_code", "list", parent_arch="<list><field name='x_name'/></list>"
    )
    assert 'expr="//list"' in arch
    assert 'expr="//tree"' not in arch
    assert 'name="x_code"' in arch
    tree = render_inherit_field_arch(
        "x_code", "tree", parent_arch="<tree><field name='x_name'/></tree>"
    )
    assert 'expr="//tree"' in tree
    assert 'name="x_code"' in tree


def test_render_inherit_field_arch_search() -> None:
    arch = render_inherit_field_arch("x_priority", "search")
    assert 'expr="//search"' in arch
    assert 'name="x_priority"' in arch


def test_render_inherit_field_arch_rejects_unknown() -> None:
    import pytest

    with pytest.raises(ValueError, match="Unsupported inherit inject view_type"):
        render_inherit_field_arch("x_foo", "kanban")


def test_render_inherit_smart_buttons_into_existing_box() -> None:
    from odoo_client.view_arch import ButtonNode, render_inherit_smart_buttons_arch

    parent = """
    <form><sheet>
      <div name="button_box" class="oe_button_box"/>
      <group><field name="name"/><field name="phone"/></group>
    </sheet></form>
    """
    arch = render_inherit_smart_buttons_arch(
        [
            ButtonNode(
                string="Rentals",
                name="42",
                type="action",
                class_name="oe_stat_button",
                icon="fa-car",
                count_field="x_rent_contract_count",
            )
        ],
        parent_arch=parent,
    )
    assert 'expr="//div[@name=\'button_box\']"' in arch
    assert 'position="inside"' in arch
    assert 'name="42"' in arch
    assert 'name="x_rent_contract_count"' in arch
    assert "<form" not in arch.split("<xpath", 1)[0]


def test_render_inherit_smart_buttons_creates_box_when_missing() -> None:
    from odoo_client.view_arch import ButtonNode, render_inherit_smart_buttons_arch

    parent = '<form><sheet><group><field name="x_name"/></group></sheet></form>'
    arch = render_inherit_smart_buttons_arch(
        [
            ButtonNode(
                string="Loans",
                name="99",
                type="action",
                class_name="oe_stat_button",
                icon="fa-book",
            )
        ],
        parent_arch=parent,
    )
    assert 'expr="//sheet/*[1]"' in arch
    assert 'position="before"' in arch
    assert 'name="button_box"' in arch
    assert "oe_stat_button" in arch
    assert 'name="99"' in arch


def test_list_arch_sample_flag() -> None:
    arch = render_list_arch(
        ListViewSpec(string="Demo", columns=[FieldNode(name="x_name")], sample=True)
    )
    assert 'sample="1"' in arch


def test_field_image_options_emitted() -> None:
    arch = render_form_arch(
        FormViewSpec(
            string="Photo",
            children=[
                GroupNode(
                    children=[
                        FieldNode(
                            name="x_photo",
                            widget="image",
                            options='{"size": [128, 128]}',
                        )
                    ]
                )
            ],
        )
    )
    assert 'widget="image"' in arch
    assert "options=" in arch
    assert "128" in arch


def test_major16_form_field_attrs_roundtrip() -> None:
    from odoo_client.view_arch import parse_form_arch

    arch = render_form_arch(
        FormViewSpec(
            string="T",
            children=[
                GroupNode(
                    children=[
                        FieldNode(name="x_name", invisible="[('active', '=', False)]")
                    ]
                )
            ],
        ),
        major=16,
    )
    assert "attrs=" in arch
    spec = parse_form_arch(arch)
    field = spec.children[0].children[0]
    assert isinstance(field, FieldNode)
    assert field.invisible == "[('active', '=', False)]"
