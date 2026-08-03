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
