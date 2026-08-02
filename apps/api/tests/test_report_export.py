"""Unit tests for report → ModuleSpec export helpers."""

from __future__ import annotations

import zipfile
from io import BytesIO

from module_generator import ModuleSpec, ReportSpec, build_module_zip, render_module_files

from app.report_export import (
    qweb_arch_to_body_html,
    report_row_to_spec,
    should_export_report,
    template_xml_id_from_key,
)


def test_should_export_report_filters() -> None:
    assert should_export_report(model="x_lib_loan", report_name="sale.report_saleorder")
    assert should_export_report(model="res.partner", report_name="custom.partner_pdf")
    assert not should_export_report(model="res.partner", report_name="base.report_irmodulereference")


def test_qweb_arch_to_body_html_strips_shell() -> None:
    arch = (
        '<t t-name="custom.smoke">'
        '<t t-call="web.html_container">'
        '<t t-foreach="docs" t-as="doc">'
        '<div class="page"><h2 t-field="doc.display_name"/></div>'
        "</t></t></t>"
    )
    body = qweb_arch_to_body_html(arch)
    assert "doc." not in body
    assert 't-field="o.display_name"' in body
    assert "html_container" not in body


def test_report_row_to_spec_and_zip() -> None:
    row = {
        "id": 42,
        "name": "Partner PDF",
        "model": "res.partner",
        "report_name": "custom.partner_pdf",
        "print_report_name": False,
    }
    arch = (
        '<t t-name="custom.partner_pdf">'
        '<t t-call="web.html_container">'
        '<t t-foreach="docs" t-as="doc">'
        '<div class="page"><p>Hi <span t-field="doc.name"/></p></div>'
        "</t></t></t>"
    )
    spec_row = report_row_to_spec(row, arch=arch)
    assert spec_row.template_xml_id == "partner_pdf"
    assert "o.name" in spec_row.body_html

    module = ModuleSpec(
        technical_name="export_rpt",
        display_name="Export Rpt",
        reports=[spec_row],
    )
    files = render_module_files(module)
    assert "export_rpt/report/reports.xml" in files
    xml = files["export_rpt/report/reports.xml"]
    assert "partner_pdf" in xml
    assert "ir.actions.report" in xml
    assert "export_rpt.partner_pdf" in xml

    raw = build_module_zip(module)
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        assert any(n.endswith("report/reports.xml") for n in zf.namelist())


def test_template_xml_id_from_key() -> None:
    assert template_xml_id_from_key("custom.smoke_report_abc", report_id=1) == (
        "smoke_report_abc"
    )
