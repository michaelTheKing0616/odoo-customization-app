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


def test_render_skips_empty_field_names() -> None:
    arch = render_form_arch(
        FormViewSpec(
            string="Invoice",
            children=[
                GroupNode(
                    string="Extras",
                    children=[
                        FieldNode(name=""),
                        FieldNode(name="   "),
                        FieldNode(name="x_my_test"),
                        FieldNode(name="x_demo_note"),
                    ],
                ),
                NotebookNode(
                    pages=[
                        PageNode(
                            string="Invoice Lines",
                            children=[FieldNode(name="invoice_line_ids")],
                        )
                    ]
                ),
            ],
        )
    )
    assert 'name=""' not in arch
    assert 'name="x_my_test"' in arch
    assert 'name="x_demo_note"' in arch
    assert 'name="invoice_line_ids"' in arch


def test_additive_form_inherit_skips_stock_chrome() -> None:
    from odoo_client.view_arch import (
        ButtonNode,
        build_additive_form_inherit_arch,
        inherit_arch_looks_like_full_form_replace,
        render_form_arch,
        render_inherit_replace_arch,
    )

    spec = FormViewSpec(
        string="Bills",
        header_buttons=[
            ButtonNode(string="Send", name="action_invoice_sent", type="object"),
            ButtonNode(string="Print", name="action_print", type="object"),
            ButtonNode(string="Pay", name="action_register_payment", type="object"),
        ],
        button_box=[ButtonNode(string="Payments", name="1", type="action")],
        children=[
            GroupNode(string="Main", children=[FieldNode(name="partner_id")]),
            GroupNode(
                string="TEST GROUP",
                children=[
                    FieldNode(name="x_my_test"),
                    FieldNode(name="x_demo_note"),
                ],
            ),
            NotebookNode(
                pages=[
                    PageNode(string="Invoice Lines", children=[FieldNode(name="invoice_line_ids")]),
                    PageNode(string="Other Info", children=[FieldNode(name="narration")]),
                    PageNode(string="Other Info", children=[FieldNode(name="narration")]),
                ]
            ),
        ],
    )
    arch = build_additive_form_inherit_arch(
        spec,
        existing_field_names={"partner_id", "invoice_line_ids", "narration"},
    )
    assert 'position="inside"' in arch
    assert "//sheet" in arch
    assert "TEST GROUP" in arch
    assert 'name="x_my_test"' in arch
    assert 'name="x_demo_note"' in arch
    # Must NOT re-emit stock chrome (would duplicate under module inherits)
    assert "<header" not in arch
    assert "action_invoice_sent" not in arch
    assert "button_box" not in arch
    assert "<notebook" not in arch
    assert 'name="partner_id"' not in arch
    assert 'name="narration"' not in arch

    bad = render_inherit_replace_arch("form", render_form_arch(spec))
    assert inherit_arch_looks_like_full_form_replace(bad)
    assert not inherit_arch_looks_like_full_form_replace(arch)

    from odoo_client.view_arch import (
        extract_replaced_form_arch,
        form_spec_for_additive_repair,
    )

    inner = extract_replaced_form_arch(bad)
    assert inner is not None
    assert inner.lstrip().startswith("<form")
    repaired_spec = form_spec_for_additive_repair(bad)
    repaired = build_additive_form_inherit_arch(
        repaired_spec,
        existing_field_names={"partner_id", "invoice_line_ids", "narration"},
    )
    assert "TEST GROUP" in repaired
    assert 'name="x_demo_note"' in repaired
    assert "<header" not in repaired
    assert "<notebook" not in repaired


def test_additive_emits_x_fields_even_if_already_on_combined() -> None:
    """Designer Save must rewrite x_* groups; pass stock-only names as existing."""
    from odoo_client.view_arch import build_additive_form_inherit_arch

    spec = FormViewSpec(
        string="Bills",
        children=[
            GroupNode(string="Main", children=[FieldNode(name="partner_id")]),
            GroupNode(
                string="My Group",
                children=[FieldNode(name="x_demo_note"), FieldNode(name="x_test_field")],
            ),
        ],
    )
    # If x_* were wrongly treated as existing (old combined-arch bug), Save would refuse.
    try:
        build_additive_form_inherit_arch(
            spec,
            existing_field_names={"partner_id", "x_demo_note", "x_test_field"},
        )
        assert False, "x_* listed in existing_field_names must be skipped"
    except ValueError:
        pass

    arch = build_additive_form_inherit_arch(
        spec,
        existing_field_names={"partner_id"},
    )
    assert "My Group" in arch
    assert 'name="x_demo_note"' in arch
    assert 'name="x_test_field"' in arch
    assert 'name="partner_id"' not in arch


def test_additive_walks_nested_groups() -> None:
    from odoo_client.view_arch import build_additive_form_inherit_arch

    spec = FormViewSpec(
        string="Bills",
        children=[
            GroupNode(
                string="Outer",
                children=[
                    GroupNode(
                        string="Inner custom",
                        children=[FieldNode(name="x_nested")],
                    )
                ],
            )
        ],
    )
    arch = build_additive_form_inherit_arch(spec, existing_field_names=set())
    assert "Inner custom" in arch
    assert 'name="x_nested"' in arch


def test_additive_refuses_stock_only_canvas() -> None:
    from odoo_client.view_arch import build_additive_form_inherit_arch

    spec = FormViewSpec(
        string="Bills",
        children=[
            GroupNode(string="Main", children=[FieldNode(name="partner_id")]),
        ],
    )
    try:
        build_additive_form_inherit_arch(spec, existing_field_names={"partner_id"})
        assert False, "expected ValueError"
    except ValueError as exc:
        msg = str(exc)
        assert "x_*" in msg
        assert "Send/Print/Pay" in msg or "stock" in msg.lower()


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
    assert 'expr="//group"' in grouped
    assert "group[1]" not in grouped
    assert 'name="x_status"' in grouped
    named = render_inherit_field_arch(
        "x_status",
        "form",
        parent_arch='<form><sheet><group string="Main"><field name="x_name"/></group></sheet></form>',
    )
    assert "expr=\"//group[@string='Main']\"" in named


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


def test_field_chrome_attrs_round_trip() -> None:
    from odoo_client.view_arch import parse_form_arch, parse_list_arch

    spec = FormViewSpec(
        string="Partner",
        children=[
            GroupNode(
                children=[
                    FieldNode(
                        name="email",
                        string="Email",
                        help="Shown on hover",
                        placeholder="name@company.com",
                        class_name="oe_inline",
                        groups="base.group_user,!base.group_portal",
                        widget="email",
                        invisible=True,
                    )
                ]
            )
        ],
    )
    arch = render_form_arch(spec)
    assert 'help="Shown on hover"' in arch
    assert 'placeholder="name@company.com"' in arch
    assert 'class="oe_inline"' in arch
    assert 'groups="base.group_user,!base.group_portal"' in arch
    assert 'invisible="1"' in arch
    parsed = parse_form_arch(arch)
    field = parsed.children[0].children[0]
    assert isinstance(field, FieldNode)
    assert field.help == "Shown on hover"
    assert field.placeholder == "name@company.com"
    assert field.class_name == "oe_inline"
    assert field.groups == "base.group_user,!base.group_portal"
    assert field.widget == "email"
    assert field.invisible is True
    again = render_form_arch(parsed)
    assert 'placeholder="name@company.com"' in again
    assert 'class="oe_inline"' in again

    list_arch = render_list_arch(
        ListViewSpec(
            string="Partners",
            columns=[
                FieldNode(
                    name="email",
                    string="Email",
                    help="List hint",
                    class_name="oe_highlight",
                    groups="base.group_system",
                )
            ],
        )
    )
    list_spec = parse_list_arch(list_arch)
    col = list_spec.columns[0]
    assert col.help == "List hint"
    assert col.class_name == "oe_highlight"
    assert col.groups == "base.group_system"
