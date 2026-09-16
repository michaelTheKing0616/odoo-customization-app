"""View ↔ Python field consistency — OWL undefined-field guard."""

from __future__ import annotations

from app.ai_option_a_policy import policy_findings
from app.ai_option_a_view_fields import (
    align_xml_field_names_to_python,
    arch_fields_missing_from_registry,
    extract_python_fields_by_model,
    view_field_consistency_findings,
)
from app.ai_static_odoo import rewrite_draft_stock_xpaths
from app.ai_structural_zip_gate import structural_zip_gate


def _draft_bad_markup() -> dict:
    return {
        "custom_code_blocks": [
            {
                "source_file": "models/sale_markup.py",
                "kind": "python",
                "content": (
                    "from odoo import fields, models\n\n"
                    "class SaleOrder(models.Model):\n"
                    "    _inherit = 'sale.order'\n"
                    "    x_markup_percent = fields.Float(string='Markup %')\n"
                    "    x_withholding_tax_id = fields.Many2one('account.tax')\n"
                ),
            },
            {
                "source_file": "views/sale_markup_views.xml",
                "kind": "xml",
                "content": (
                    '<odoo>\n'
                    '  <record id="sale_order_form_markup" model="ir.ui.view">\n'
                    '    <field name="name">sale.order.form.markup</field>\n'
                    '    <field name="model">sale.order</field>\n'
                    '    <field name="inherit_id" ref="sale.view_order_form"/>\n'
                    '    <field name="arch" type="xml">\n'
                    '      <xpath expr="//field[@name=\'tax_totals\']" position="before">\n'
                    '        <field name="markup_percentage"/>\n'
                    '        <field name="withholding_tax_id"/>\n'
                    "      </xpath>\n"
                    "    </field>\n"
                    "  </record>\n"
                    "</odoo>\n"
                ),
            },
        ]
    }


def test_extract_python_fields_by_model() -> None:
    py = (
        "from odoo import fields, models\n\n"
        "class SaleOrder(models.Model):\n"
        "    _inherit = 'sale.order'\n"
        "    x_markup_percent = fields.Float()\n"
    )
    got = extract_python_fields_by_model(py)
    assert got["sale.order"] == {"x_markup_percent"}


def test_view_field_undefined_blocks_policy() -> None:
    draft = _draft_bad_markup()
    codes = {f["code"] for f in view_field_consistency_findings(draft)}
    assert "view_field_undefined" in codes
    codes2 = {f["code"] for f in policy_findings(draft)}
    assert "view_field_undefined" in codes2


def test_free_align_rewrites_markup_percentage() -> None:
    draft = _draft_bad_markup()
    n = rewrite_draft_stock_xpaths(draft)
    assert n >= 1
    xml = draft["custom_code_blocks"][1]["content"]
    assert "markup_percentage" not in xml
    assert 'name="x_markup_percent"' in xml
    assert 'name="x_withholding_tax_id"' in xml
    assert not view_field_consistency_findings(draft)


def test_align_xml_helper() -> None:
    xml = '<xpath expr="//field[@name=\'tax_totals\']" position="before">'
    xml += '<field name="markup_percentage"/></xpath>'
    out = align_xml_field_names_to_python(xml, {"x_markup_percent"})
    assert "x_markup_percent" in out
    assert "markup_percentage" not in out


def test_arch_fields_missing_from_registry() -> None:
    arch = (
        '<xpath expr="//field[@name=\'tax_totals\']" position="before">'
        '<field name="markup_percentage"/>'
        '<field name="tax_totals"/>'
        "</xpath>"
    )
    missing = arch_fields_missing_from_registry(
        arch, {"partner_id": {}, "tax_totals": {}}, model="sale.order"
    )
    assert missing == ["markup_percentage"]


def test_structural_zip_rejects_undefined_view_field() -> None:
    files = {
        "demo/__manifest__.py": "{'name': 'Demo', 'version': '1.0'}",
        "demo/models/sale_markup.py": (
            "from odoo import fields, models\n\n"
            "class SaleOrder(models.Model):\n"
            "    _inherit = 'sale.order'\n"
            "    x_markup_percent = fields.Float()\n"
        ),
        "demo/views/sale.xml": (
            '<odoo><record id="v" model="ir.ui.view">'
            '<field name="model">sale.order</field>'
            '<field name="arch" type="xml">'
            '<xpath expr="//field[@name=\'tax_totals\']" position="before">'
            '<field name="markup_percentage"/>'
            "</xpath></field></record></odoo>"
        ),
    }
    gate = structural_zip_gate(files=files)
    assert gate["ok"] is False
    assert any("view_field_undefined" in str(f) for f in gate["findings"])


def test_non_x_python_field_on_stock_inherit_fails() -> None:
    draft = {
        "custom_code_blocks": [
            {
                "source_file": "models/bad.py",
                "kind": "python",
                "content": (
                    "from odoo import fields, models\n\n"
                    "class SaleOrder(models.Model):\n"
                    "    _inherit = 'sale.order'\n"
                    "    markup_percentage = fields.Float()\n"
                ),
            }
        ]
    }
    codes = {f["code"] for f in view_field_consistency_findings(draft)}
    assert "custom_field_not_x_prefix" in codes


def test_security_implied_ids_not_flagged_as_view_field() -> None:
    """res.groups data XML must not trip the OWL view↔Python gate."""
    draft = {
        "custom_code_blocks": [
            {
                "source_file": "models/sale_markup.py",
                "kind": "python",
                "content": (
                    "from odoo import fields, models\n\n"
                    "class SaleOrder(models.Model):\n"
                    "    _inherit = 'sale.order'\n"
                    "    x_markup_percent = fields.Float()\n"
                ),
            },
            {
                "source_file": "security/groups.xml",
                "kind": "xml",
                "content": (
                    "<odoo>\n"
                    '  <record id="group_markup_user" model="res.groups">\n'
                    '    <field name="name">Markup User</field>\n'
                    '    <field name="implied_ids" eval="[(4, ref(\'base.group_user\'))]"/>\n'
                    "  </record>\n"
                    "</odoo>\n"
                ),
            },
            {
                "source_file": "views/sale_markup_views.xml",
                "kind": "xml",
                "content": (
                    "<odoo>\n"
                    '  <record id="sale_order_form_markup" model="ir.ui.view">\n'
                    '    <field name="name">sale.order.form.markup</field>\n'
                    '    <field name="model">sale.order</field>\n'
                    '    <field name="inherit_id" ref="sale.view_order_form"/>\n'
                    '    <field name="arch" type="xml">\n'
                    "      <xpath expr=\"//field[@name='tax_totals']\" position=\"before\">\n"
                    '        <field name="x_markup_percent"/>\n'
                    "      </xpath>\n"
                    "    </field>\n"
                    "  </record>\n"
                    "</odoo>\n"
                ),
            },
        ]
    }
    assert view_field_consistency_findings(draft) == []
    gate = structural_zip_gate(
        files={
            "m/__manifest__.py": "{'name': 'M'}",
            "m/models/sale_markup.py": draft["custom_code_blocks"][0]["content"],
            "m/security/groups.xml": draft["custom_code_blocks"][1]["content"],
            "m/views/sale_markup_views.xml": draft["custom_code_blocks"][2]["content"],
        }
    )
    assert gate["ok"] is True
    assert not any("implied_ids" in str(f) for f in gate["findings"])


def test_ensure_python_field_strings_preserves_many2one_comodel() -> None:
    from app.ai_option_a_acceptance import ensure_python_field_strings
    from app.ai_static_odoo import harden_authored_python
    from app.ai_option_a_view_fields import extract_python_fields_by_model

    src = (
        "from odoo import fields, models\n\n"
        "class SaleOrder(models.Model):\n"
        "    _inherit = 'sale.order'\n"
        "    x_withholding_tax_id = fields.Many2one('account.tax')\n"
    )
    out = ensure_python_field_strings(src)
    assert "Many2one('account.tax', string=" in out or 'Many2one("account.tax", string=' in out
    assert "string=" in out
    # keyword must not precede positional comodel
    assert "string=" in out.split("Many2one(")[1]
    assert not out.split("Many2one(")[1].strip().startswith("string=")
    hardened = harden_authored_python(src)
    got = extract_python_fields_by_model(hardened)
    assert "x_withholding_tax_id" in got.get("sale.order", set())
