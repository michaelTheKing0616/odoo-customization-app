"""CMP-4: visual report designer QWeb compiler."""

from __future__ import annotations

import pytest

from app.module_spec_codec import draft_dict_to_module_spec
from app.report_design import (
    BLOCK_PALETTE,
    compile_report_design,
    design_to_module_report,
    emit_block,
    parse_qweb_anchors,
)
from module_generator import render_module_files


def test_block_palette_complete() -> None:
    types = {p["type"] for p in BLOCK_PALETTE}
    assert "heading" in types
    assert "o2m_table" in types
    assert "page_break" in types


def test_compile_primary_external_layout_golden() -> None:
    spec = {
        "report_key": "custom.report_rental",
        "use_external_layout": True,
        "blocks": [
            {"type": "heading", "text": "Rental Agreement", "level": 1},
            {"type": "label_field", "label": "Customer", "field": "partner_id"},
            {"type": "field", "field": "amount_total"},
        ],
    }
    out = compile_report_design(spec)
    arch = out["arch"]
    assert 't-name="custom.report_rental"' in arch
    assert 't-call="web.external_layout"' in arch
    assert 't-foreach="docs" t-as="doc"' in arch
    assert 't-field="doc.partner_id"' in arch
    assert "Rental Agreement" in arch
    assert "company_ids" not in arch


def test_compile_inherit_mode() -> None:
    spec = {
        "report_key": "custom.report_invoice_extra",
        "mode": "inherit",
        "inherit": {
            "base_report_key": "account.report_invoice",
            "xpath": "//div[@class='page']",
            "position": "inside",
        },
        "blocks": [{"type": "text", "text": "Thank you for your business."}],
    }
    arch = compile_report_design(spec)["arch"]
    assert 't-inherit="account.report_invoice"' in arch
    assert 'position="inside"' in arch
    assert "Thank you" in arch


def test_t_lang_wrapper() -> None:
    spec = {
        "report_key": "custom.report_lang",
        "use_external_layout": False,
        "t_lang": "doc.partner_id.lang",
        "blocks": [{"type": "field", "field": "name"}],
    }
    arch = compile_report_design(spec)["arch"]
    assert 't-lang="doc.partner_id.lang"' in arch


def test_design_to_module_spec_round_trip() -> None:
    fragment = design_to_module_report(
        {
            "name": "Rental PDF",
            "model": "x_rent_contract",
            "report_key": "custom.report_x_rent_contract",
            "blocks": [{"type": "heading", "text": "Contract", "level": 2}],
        }
    )
    draft = {
        "technical_name": "rent_mod",
        "display_name": "Rent",
        "reports": fragment["reports"],
    }
    spec = draft_dict_to_module_spec(draft)
    files = render_module_files(spec)
    assert "rent_mod/report/reports.xml" in files
    assert "Contract" in files["rent_mod/report/reports.xml"]


def test_o2m_table_emits_foreach() -> None:
    html = emit_block(
        {
            "type": "o2m_table",
            "o2m_field": "line_ids",
            "columns": [{"field": "product_id", "label": "Product"}],
        }
    )
    assert 't-foreach="doc.line_ids"' in html
    assert "Product" in html


def test_parse_qweb_anchors_finds_page() -> None:
    arch = """<t t-name="x"><div class="page"><h2>Title</h2></div></t>"""
    anchors = parse_qweb_anchors(arch)
    assert anchors
    assert any("page" in a["xpath"] for a in anchors)


def test_inherit_requires_base_key() -> None:
    with pytest.raises(ValueError, match="base_report_key"):
        compile_report_design({"mode": "inherit", "blocks": []})

def test_compile_inherit_slot_emits_one_anchor() -> None:
    """PDF-03: slot picker maps to one xpath/position; page body stay sibling-only."""
    from app.report_design import INHERIT_SLOT_MAP, resolve_inherit_anchor

    assert set(INHERIT_SLOT_MAP) == {"header", "before_body", "after_body", "footer"}
    xpath, position = resolve_inherit_anchor({"slot": "after_body"})
    assert xpath == "//div[@class='page']"
    assert position == "after"

    arch = compile_report_design(
        {
            "report_key": "custom.report_invoice_extra",
            "mode": "inherit",
            "inherit": {
                "base_report_key": "account.report_invoice",
                "slot": "footer",
            },
            "blocks": [{"type": "text", "text": "Footer note"}],
        }
    )["arch"]
    assert 't-inherit="account.report_invoice"' in arch
    assert 'expr="//div[@class=\'footer\']"' in arch
    assert 'position="inside"' in arch
    assert arch.count("<xpath ") == 1
    assert "Footer note" in arch


def test_compile_inherit_refuses_root_replace() -> None:
    with pytest.raises(ValueError, match="root or a large subtree"):
        compile_report_design(
            {
                "mode": "inherit",
                "inherit": {
                    "base_report_key": "account.report_invoice",
                    "xpath": "/",
                    "position": "replace",
                },
                "blocks": [],
            }
        )
    with pytest.raises(ValueError, match="root or a large subtree"):
        compile_report_design(
            {
                "mode": "inherit",
                "inherit": {
                    "base_report_key": "account.report_invoice",
                    "xpath": "//div[@class='page']",
                    "position": "replace",
                },
                "blocks": [],
            }
        )


def test_compile_inherit_refuses_missing_base_key_when_known() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        compile_report_design(
            {
                "mode": "inherit",
                "available_report_keys": ["account.report_invoice"],
                "inherit": {
                    "base_report_key": "missing.report",
                    "slot": "header",
                },
                "blocks": [],
            }
        )



# --- PDF-04: create from scratch, grounded ---


def test_use_external_layout_defaults_on() -> None:
    arch = compile_report_design(
        {
            "report_key": "custom.report_grounded",
            "blocks": [{"type": "field", "field": "display_name"}],
        }
    )["arch"]
    assert 't-call="web.external_layout"' in arch
    assert "html_container" not in arch


def test_refuse_empty_design() -> None:
    from app.report_design import refuse_empty_design

    with pytest.raises(ValueError, match="empty design"):
        refuse_empty_design({"blocks": []})
    with pytest.raises(ValueError, match="empty design"):
        refuse_empty_design({})
    refuse_empty_design({"blocks": [{"type": "text", "text": "x"}]})


def test_compile_refuses_unknown_field_via_grounding() -> None:
    from app.report_design import ground_design_against_schema

    spec = {
        "model": "sale.order",
        "report_key": "custom.report_x",
        "blocks": [{"type": "field", "field": "not_a_real_field"}],
    }
    with pytest.raises(ValueError, match="unknown field"):
        ground_design_against_schema(
            spec,
            parent_field_names={"display_name", "partner_id"},
            require_blocks=True,
        )
    # Must not reach compile with unknown token written into arch
    grounded = {
        "model": "sale.order",
        "report_key": "custom.report_x",
        "use_external_layout": True,
        "blocks": [{"type": "field", "field": "partner_id"}],
    }
    ground_design_against_schema(
        grounded,
        parent_field_names={"display_name", "partner_id"},
        require_blocks=True,
    )
    arch = compile_report_design(grounded)["arch"]
    assert 't-field="doc.partner_id"' in arch
    assert "not_a_real_field" not in arch


def test_o2m_columns_grounded_on_related_model_only() -> None:
    from app.report_design import (
        collect_field_tokens,
        ground_design_against_schema,
        relational_line_fields,
    )

    parent_meta = [
        {"name": "line_ids", "ttype": "one2many", "relation": "sale.order.line"},
        {"name": "partner_id", "ttype": "many2one", "relation": "res.partner"},
        {"name": "display_name", "ttype": "char", "relation": False},
    ]
    line_map = relational_line_fields(parent_meta)
    assert line_map == {"line_ids": "sale.order.line"}

    spec = {
        "model": "sale.order",
        "blocks": [
            {
                "type": "o2m_table",
                "o2m_field": "line_ids",
                "columns": [
                    {"field": "product_id", "label": "Product"},
                    {"field": "bogus_col", "label": "Nope"},
                ],
            }
        ],
    }
    tokens = collect_field_tokens(spec["blocks"])
    assert any(t["scope"] == "column" and t["field"] == "bogus_col" for t in tokens)
    with pytest.raises(ValueError, match="unknown field on related model"):
        ground_design_against_schema(
            spec,
            parent_field_names={"line_ids", "partner_id", "display_name"},
            related_field_names={"line_ids": {"product_id", "name", "display_name"}},
            require_blocks=True,
        )


def test_report_action_create_params_shape() -> None:
    """report.action.create values match ir.actions.report create vals (R2)."""
    from app.changeset.ui_ops import ui_target_model, ui_values

    assert ui_target_model("report.action.create") == "ir.actions.report"
    vals = ui_values(
        "report.action.create",
        {"name": "Partner PDF", "model": "res.partner", "report_name": "custom.report_partner"},
    )
    assert vals.get("model") == "res.partner"
    assert vals.get("name") == "Partner PDF"


# --------------------------------------------------------------------------
# PDF-07 — grounded Table Inspector (align / width / totals row)
# --------------------------------------------------------------------------


def _inspector_table_block(**overrides):
    block = {
        "type": "o2m_table",
        "o2m_field": "order_line",
        "columns": [
            {"field": "name", "label": "Description", "width": "2fr"},
            {"field": "product_uom_qty", "label": "Qty", "ttype": "float", "width": 15},
            {
                "field": "price_subtotal",
                "label": "Subtotal",
                "ttype": "monetary",
                "width": "20%",
                "sum": True,
            },
        ],
        "totals_row": True,
    }
    block.update(overrides)
    return block


def test_o2m_table_legacy_columns_emit_unchanged_shape() -> None:
    """Old specs ({field,label} only) keep plain <th>/<td> with no style/class."""
    html = emit_block(
        {
            "type": "o2m_table",
            "o2m_field": "line_ids",
            "columns": [{"field": "product_id", "label": "Product"}],
        }
    )
    assert html == (
        '<table class="table table-sm o_report_table"><thead><tr><th>Product</th></tr>'
        '</thead><tbody><tr t-foreach="doc.line_ids" t-as="line"><td>'
        '<span t-field="line.product_id"/></td></tr></tbody></table>'
    )
    assert "tfoot" not in html


def test_o2m_table_column_align_emits_bootstrap_class_and_inline_style() -> None:
    html = emit_block(
        {
            "type": "o2m_table",
            "o2m_field": "line_ids",
            "columns": [
                {"field": "name", "label": "A", "align": "left"},
                {"field": "qty", "label": "B", "align": "center"},
                {"field": "price", "label": "C", "align": "right"},
            ],
        }
    )
    assert "<th>A</th>" in html  # left is the default — no noise
    assert '<th class="text-center" style="text-align: center;">B</th>' in html
    assert '<th class="text-end" style="text-align: right;">C</th>' in html
    assert '<td class="text-end" style="text-align: right;"><span t-field="line.price"/></td>' in html


def test_o2m_table_column_align_defaults_right_for_numeric_ttype() -> None:
    html = emit_block(
        {
            "type": "o2m_table",
            "o2m_field": "line_ids",
            "columns": [
                {"field": "name", "label": "Name", "ttype": "char"},
                {"field": "price_unit", "label": "Price", "ttype": "float"},
                {"field": "amount", "label": "Amount", "ttype": "monetary"},
                {"field": "qty", "label": "Qty", "ttype": "integer"},
                {"field": "price_unit", "label": "Forced", "ttype": "float", "align": "left"},
            ],
        }
    )
    assert "<th>Name</th>" in html
    assert '<th class="text-end" style="text-align: right;">Price</th>' in html
    assert '<th class="text-end" style="text-align: right;">Amount</th>' in html
    assert '<th class="text-end" style="text-align: right;">Qty</th>' in html
    assert "<th>Forced</th>" in html


def test_o2m_table_bogus_align_falls_back_to_default() -> None:
    html = emit_block(
        {
            "type": "o2m_table",
            "o2m_field": "line_ids",
            "columns": [{"field": "name", "label": "N", "align": 'right" onload="x'}],
        }
    )
    assert "onload" not in html
    assert "<th>N</th>" in html


def test_o2m_table_column_width_percent_and_fr_resolve() -> None:
    from app.report_design import resolve_column_widths

    cols = _inspector_table_block()["columns"]
    assert resolve_column_widths(cols) == [65.0, 15.0, 20.0]
    html = emit_block(_inspector_table_block())
    assert '<th style="width: 65%;">Description</th>' in html
    assert '<th class="text-end" style="text-align: right; width: 15%;">Qty</th>' in html
    assert '<td style="width: 65%;"><span t-field="line.name"/></td>' in html


def test_o2m_table_column_width_fr_split_and_auto() -> None:
    from app.report_design import format_width_pct, resolve_column_widths

    cols = [
        {"field": "a", "width": "1fr"},
        {"field": "b", "width": "2fr"},
        {"field": "c"},
        {"field": "d", "width": "40"},
    ]
    widths = resolve_column_widths(cols)
    assert widths == [20.0, 40.0, None, 40.0]
    assert resolve_column_widths([{"field": "a", "width": "1fr"}, {"field": "b", "width": 100}]) == [
        None,
        100.0,
    ]
    assert format_width_pct(33.33) == "33.33%"
    assert format_width_pct(25.0) == "25%"


@pytest.mark.parametrize(
    "raw",
    [
        "10px; color:red",
        "expression(alert(1))",
        "50%; background:url(x)",
        "0",
        -5,
        101,
        "1e3",
        True,
        "",
        None,
        "calc(10% + 2px)",
        float("nan"),
        float("inf"),
    ],
)
def test_o2m_table_column_width_rejects_css_injection(raw) -> None:
    from app.report_design import parse_column_width

    assert parse_column_width(raw) is None
    html = emit_block(
        {
            "type": "o2m_table",
            "o2m_field": "line_ids",
            "columns": [{"field": "name", "label": "N", "width": raw}],
        }
    )
    assert "style=" not in html
    for bad in ("px", "color", "url(", "expression", "calc"):
        assert bad not in html


def test_o2m_table_totals_row_emits_pure_qweb_sum() -> None:
    html = emit_block(_inspector_table_block())
    assert "<tfoot>" in html
    assert '<tr class="o_report_table_total">' in html
    assert "<td><strong>Total</strong></td>" in html
    assert (
        '<strong t-esc="sum(doc.order_line.mapped(\'price_subtotal\'))" '
        't-options=\'{"widget": "float", "precision": 2}\'/>'
    ) in html
    # Non-summed numeric column stays an empty, aligned cell
    assert '<td class="text-end" style="text-align: right;"/>' in html
    # no Python aggregates outside QWeb; nothing unsafe
    for bad in ("t-raw", "t-out", "<script", "t-call"):
        assert bad not in html


def test_o2m_table_totals_integer_sum_has_no_float_widget() -> None:
    html = emit_block(
        {
            "type": "o2m_table",
            "o2m_field": "line_ids",
            "totals_row": True,
            "columns": [
                {"field": "name", "label": "N"},
                {"field": "qty", "label": "Qty", "ttype": "integer", "sum": True},
            ],
        }
    )
    assert '<strong t-esc="sum(doc.line_ids.mapped(\'qty\'))"/>' in html


def test_o2m_table_totals_off_or_without_sum_columns_emits_no_footer() -> None:
    off = emit_block(_inspector_table_block(totals_row=False))
    assert "tfoot" not in off
    no_sum = _inspector_table_block()
    no_sum["columns"] = [dict(c, sum=False) for c in no_sum["columns"]]
    assert "tfoot" not in emit_block(no_sum)
    # sum must be literally True — truthy strings do not enable totals
    truthy = _inspector_table_block()
    truthy["columns"] = [dict(c, sum="yes") for c in truthy["columns"]]
    assert "tfoot" not in emit_block(truthy)


def test_o2m_table_totals_label_escaped_and_custom() -> None:
    html = emit_block(_inspector_table_block(totals_label="Grand <b>total</b>"))
    assert "<strong>Grand &lt;b&gt;total&lt;/b&gt;</strong>" in html


def test_o2m_table_totals_label_qweb_refused_on_compile() -> None:
    spec = {
        "report_key": "custom.report_lines",
        "blocks": [_inspector_table_block(totals_label='<t t-esc="1"/>')],
    }
    with pytest.raises(ValueError, match="totals_label"):
        compile_report_design(spec)


def test_o2m_table_unsafe_column_field_refused() -> None:
    for bad in ('name"/><script>x</script><span t-field="x', "name; drop", "1abc", "a..b"):
        with pytest.raises(ValueError, match="invalid column field"):
            emit_block(
                {
                    "type": "o2m_table",
                    "o2m_field": "line_ids",
                    "columns": [{"field": bad, "label": "X"}],
                }
            )
    with pytest.raises(ValueError, match="invalid lines field"):
        emit_block({"type": "o2m_table", "o2m_field": "line_ids')", "columns": []})
    with pytest.raises(ValueError, match="invalid line variable"):
        emit_block({"type": "o2m_table", "o2m_field": "line_ids", "line_var": "x y"})


def test_o2m_table_inspector_compile_is_well_formed_and_gate_clean() -> None:
    import xml.etree.ElementTree as etree

    spec = {
        "report_key": "custom.report_lines",
        "model": "sale.order",
        "blocks": [{"type": "heading", "text": "Order", "level": 1}, _inspector_table_block()],
    }
    out = compile_report_design(spec)
    root = etree.fromstring(out["arch"].encode())
    tfoot = root.find(".//tfoot")
    assert tfoot is not None
    strong = tfoot.find(".//strong[@t-esc]")
    assert strong.get("t-esc") == "sum(doc.order_line.mapped('price_subtotal'))"
    assert strong.get("t-options") == '{"widget": "float", "precision": 2}'
    ths = root.findall(".//thead/tr/th")
    assert [th.get("style") for th in ths] == [
        "width: 65%;",
        "text-align: right; width: 15%;",
        "text-align: right; width: 20%;",
    ]
    # module export keeps the totals (doc. → o.)
    assert "sum(o.order_line.mapped('price_subtotal'))" in out["body_html"]


def test_o2m_table_inspector_module_export_renders_valid_xml() -> None:
    import xml.etree.ElementTree as etree

    fragment = design_to_module_report(
        {
            "name": "Order lines",
            "model": "sale.order",
            "report_key": "custom.report_order_lines",
            "blocks": [_inspector_table_block()],
        }
    )
    draft = {
        "technical_name": "order_lines_mod",
        "display_name": "Order lines",
        "reports": fragment["reports"],
    }
    files = render_module_files(draft_dict_to_module_spec(draft))
    xml = files["order_lines_mod/report/reports.xml"]
    etree.fromstring(xml.encode())
    assert "o_report_table_total" in xml
    assert "mapped(" in xml


def test_o2m_table_totals_grounding_refuses_non_numeric_column() -> None:
    from app.report_design import ground_design_against_schema

    spec = {
        "model": "sale.order",
        "blocks": [
            {
                "type": "o2m_table",
                "o2m_field": "order_line",
                "totals_row": True,
                "columns": [{"field": "name", "label": "Desc", "sum": True}],
            }
        ],
    }
    with pytest.raises(ValueError, match="only sum numeric fields"):
        ground_design_against_schema(
            spec,
            parent_field_names={"order_line"},
            related_field_names={"order_line": {"name", "price_subtotal"}},
            related_field_types={"order_line": {"name": "char", "price_subtotal": "monetary"}},
        )
    spec["blocks"][0]["columns"] = [
        {"field": "price_subtotal", "label": "Subtotal", "sum": True, "align": "center", "width": 30}
    ]
    ground_design_against_schema(
        spec,
        parent_field_names={"order_line"},
        related_field_names={"order_line": {"name", "price_subtotal"}},
        related_field_types={"order_line": {"name": "char", "price_subtotal": "monetary"}},
    )


def test_o2m_table_align_width_never_add_ground_tokens() -> None:
    from app.report_design import collect_field_tokens

    tokens = collect_field_tokens([_inspector_table_block(totals_label="Sum")])
    assert tokens == [
        {"scope": "parent", "field": "order_line"},
        {"scope": "column", "field": "name", "o2m_field": "order_line"},
        {"scope": "column", "field": "product_uom_qty", "o2m_field": "order_line"},
        {"scope": "column", "field": "price_subtotal", "o2m_field": "order_line"},
    ]


def test_o2m_table_annotate_column_types_overrides_client_hint() -> None:
    from app.report_design import annotate_column_types

    spec = {
        "blocks": [
            {
                "type": "o2m_table",
                "o2m_field": "order_line",
                "columns": [
                    {"field": "price_subtotal", "ttype": "char"},
                    {"field": "unknown_col"},
                ],
            },
            {"type": "text", "text": "hi"},
        ]
    }
    original_cols = spec["blocks"][0]["columns"]
    out = annotate_column_types(spec, {"order_line": {"price_subtotal": "monetary"}})
    assert out["blocks"][0]["columns"][0]["ttype"] == "monetary"
    assert "ttype" not in out["blocks"][0]["columns"][1]
    assert out["blocks"][1] == {"type": "text", "text": "hi"}
    # original column dicts are not mutated
    assert original_cols[0]["ttype"] == "char"
