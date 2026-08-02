"""Round-trip and inherit tests for view_arch parse/render."""

from odoo_client.view_arch import (
    parse_arch,
    parse_form_arch,
    render_arch,
    render_form_arch,
    render_inherit_replace_arch,
    render_list_arch,
    render_search_arch,
)
from odoo_client.view_arch import (
    FieldNode,
    FormViewSpec,
    GroupNode,
    ListViewSpec,
    SearchFilterNode,
    SearchViewSpec,
)


def test_form_round_trip_preserves_groups() -> None:
    arch = render_form_arch(
        FormViewSpec(
            string="Book",
            children=[
                GroupNode(
                    string="Identity",
                    children=[
                        FieldNode(name="x_name", required=True),
                        FieldNode(name="x_author_id"),
                    ],
                ),
                GroupNode(
                    string="Catalog",
                    children=[FieldNode(name="x_isbn"), FieldNode(name="x_barcode", widget="barcode")],
                ),
            ],
        )
    )
    spec = parse_form_arch(arch)
    assert spec.string == "Book"
    assert len(spec.children) == 2
    assert spec.children[0].kind == "group"
    assert spec.children[0].string == "Identity"
    names = [c.name for c in spec.children[0].children if hasattr(c, "name")]
    assert names == ["x_name", "x_author_id"]
    again = render_form_arch(spec)
    assert "Identity" in again and "Catalog" in again
    assert 'widget="barcode"' in again


def test_list_and_search_parse() -> None:
    list_arch = render_list_arch(
        ListViewSpec(
            string="Loans",
            columns=[FieldNode(name="x_name"), FieldNode(name="x_returned")],
            decoration_danger="not x_returned",
        )
    )
    ls = parse_arch("list", list_arch)
    assert ls["decoration_danger"] == "not x_returned"
    assert len(ls["columns"]) == 2

    search_arch = render_search_arch(
        SearchViewSpec(
            string="S",
            fields=[FieldNode(name="x_name")],
            filters=[
                SearchFilterNode(
                    name="active",
                    string="Active",
                    domain="[('x_returned','=',False)]",
                )
            ],
        )
    )
    ss = parse_arch("search", search_arch)
    assert ss["filters"][0]["name"] == "active"
    assert "x_returned" in (ss["filters"][0]["domain"] or "")


def test_inherit_replace_wraps_form() -> None:
    inner = render_arch("form", {"string": "T", "children": [{"kind": "group", "children": [{"kind": "field", "name": "x_name"}]}]})
    wrapped = render_inherit_replace_arch("form", inner)
    assert 'position="replace"' in wrapped
    assert 'expr="//form"' in wrapped
    assert "x_name" in wrapped
