"""GND-G-OPTA: Option A authoring sees the packet and refuses invented names.

Fake schema client + fake LLM only — no live Odoo and no live model.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.ai_generation_engine import classify_generation
from app.ai_option_a_author import author_option_a_module, seed_option_a_authored
from app.ai_option_a_gate import authoring_gate_passed, evaluate_authoring_gate
from app.ai_option_a_packet_ground import packet_ground_findings
from app.ai_schema_client import FakeSchemaClient
from app.live_schema_context import build_schema_packet, render_schema_packet
from odoo_client.read_plane import ReadPlane
from odoo_client.schema_graph import SchemaGraph

pytestmark = pytest.mark.no_app_db

MARKUP = (
    "The Client wants a Mark-up line added to every Sale. The Markup is calculated "
    "as a percentage of every sale made."
)

_FORM_ARCH = (
    "<form><sheet><group>"
    '<field name="partner_id"/>'
    '<field name="partner_invoice_id"/>'
    '<field name="date_order"/>'
    '<field name="tax_totals"/>'
    "</group></sheet></form>"
)
_LIST_ARCH = '<list><field name="name"/><field name="partner_id"/></list>'
_SEARCH_ARCH = '<search><field name="name"/><field name="partner_id"/></search>'


class _SaleViewTables:
    def __call__(self, model: str, method: str, args: list, kwargs: dict):
        if method != "get_view" or model != "sale.order":
            raise AssertionError((model, method))
        view_type = str(kwargs.get("view_type") or "form")
        arches = {"form": _FORM_ARCH, "list": _LIST_ARCH, "search": _SEARCH_ARCH}
        return {"arch": arches.get(view_type, "<form/>")}


def _sale_client() -> FakeSchemaClient:
    return FakeSchemaClient(
        models={"sale.order", "res.partner"},
        fields={
            "sale.order": {
                "partner_id": {
                    "type": "many2one",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "required": True,
                },
                "partner_invoice_id": {
                    "type": "many2one",
                    "ttype": "many2one",
                    "relation": "res.partner",
                },
                "date_order": {"type": "datetime", "ttype": "datetime"},
                "tax_totals": {"type": "binary", "ttype": "binary"},
                "name": {"type": "char", "ttype": "char"},
                "order_line": {
                    "type": "one2many",
                    "ttype": "one2many",
                    "relation": "sale.order.line",
                },
            },
            "res.partner": {
                "name": {"type": "char", "ttype": "char"},
            },
        },
    )


def _connection(*, major: int = 19) -> SimpleNamespace:
    return SimpleNamespace(
        id="fixture-sale",
        server_version=f"{major}.0",
        odoo_major=major,
        installed_modules=[{"name": "sale", "state": "installed"}],
    )


def _sale_packet():
    return build_schema_packet(
        _connection(),
        models=["sale.order"],
        schema_client=_sale_client(),
        schema_graph=SchemaGraph(ReadPlane(_SaleViewTables())),
    )


def _seed_draft():
    return seed_option_a_authored(MARKUP, classify_generation(MARKUP))


def test_author_prompt_contains_schema_packet_slice(monkeypatch: pytest.MonkeyPatch) -> None:
    packet = _sale_packet()
    prompts: list[str] = []

    class Dummy:
        name = "mock"

    def capture(_prov: object, prompt: str, **_k: object) -> str:
        prompts.append(prompt)
        return json.dumps(
            {
                "blocks": [
                    {
                        "source_file": "models/sale_markup.py",
                        "kind": "python",
                        "content": (
                            "from odoo import fields, models\n\n"
                            "class SaleOrder(models.Model):\n"
                            "    _inherit = 'sale.order'\n"
                            "    x_markup_percent = fields.Float(string='Markup %')\n"
                        ),
                    },
                    {
                        "source_file": "models/__init__.py",
                        "kind": "python",
                        "content": "from . import sale_markup\n",
                    },
                ]
            }
        )

    monkeypatch.setattr("app.llm_provider.get_llm_provider_for_tier", lambda *_a, **_k: Dummy())
    monkeypatch.setattr("app.llm_provider.generate_json_with_timeout_retry", capture)

    draft = _seed_draft()
    draft["_schema_packet"] = packet
    author_option_a_module(draft, prompt=MARKUP, schema_packet=packet)
    assert prompts, "expected LLM call"
    rendered = render_schema_packet(packet)
    assert "LIVE SCHEMA PACKET" in prompts[0]
    assert "MODEL sale.order" in prompts[0]
    assert "partner_id" in prompts[0]
    assert rendered.splitlines()[0] in prompts[0]


def test_invented_field_refused_before_sandbox() -> None:
    """Fake LLM invents a stock-looking field missing on the host — gate refuses it."""
    packet = _sale_packet()
    draft = _seed_draft()
    draft["_schema_packet"] = packet
    draft["custom_code_blocks"] = [
        {
            "source_file": "models/sale_markup.py",
            "kind": "python",
            "content": (
                "from odoo import api, fields, models\n\n"
                "class SaleOrder(models.Model):\n"
                "    _inherit = 'sale.order'\n"
                "    x_markup_percent = fields.Float(string='Markup %')\n\n"
                "    @api.depends('invented_stock_field')\n"
                "    def _compute_x_markup_percent(self):\n"
                "        for rec in self:\n"
                "            rec.x_markup_percent = 0.0\n"
            ),
        },
        {
            "source_file": "models/__init__.py",
            "kind": "python",
            "content": "from . import sale_markup\n",
        },
    ]
    findings = packet_ground_findings(draft, packet=packet)
    assert any(
        row.get("code") == "packet_field_missing" and "invented_stock_field" in str(row.get("message"))
        for row in findings
    ), findings
    payload = evaluate_authoring_gate(draft)
    assert payload["status"] == "fail"
    assert not authoring_gate_passed(draft)
    messages = " ".join(str(f.get("message") or "") for f in payload["findings"])
    assert "invented_stock_field" in messages


def test_invented_xpath_target_refused_before_sandbox() -> None:
    """Fake LLM invents an xpath anchor missing from combined_arch — gate refuses it."""
    packet = _sale_packet()
    draft = _seed_draft()
    draft["_schema_packet"] = packet
    draft["custom_code_blocks"] = [
        {
            "source_file": "models/sale_markup.py",
            "kind": "python",
            "content": (
                "from odoo import fields, models\n\n"
                "class SaleOrder(models.Model):\n"
                "    _inherit = 'sale.order'\n"
                "    x_markup_percent = fields.Float(string='Markup %')\n"
            ),
        },
        {
            "source_file": "models/__init__.py",
            "kind": "python",
            "content": "from . import sale_markup\n",
        },
        {
            "source_file": "views/sale_markup.xml",
            "kind": "xml",
            "content": (
                '<odoo>\n'
                '  <record id="view_order_form_markup" model="ir.ui.view">\n'
                '    <field name="name">sale.order.form.markup</field>\n'
                '    <field name="model">sale.order</field>\n'
                '    <field name="inherit_id" ref="sale.view_order_form"/>\n'
                '    <field name="arch" type="xml">\n'
                '      <xpath expr="//field[@name=\'totally_fake_anchor\']" position="after">\n'
                '        <field name="x_markup_percent"/>\n'
                "      </xpath>\n"
                "    </field>\n"
                "  </record>\n"
                "</odoo>\n"
            ),
        },
    ]
    findings = packet_ground_findings(draft, packet=packet)
    assert any(
        row.get("code") == "packet_xpath_missing" and "totally_fake_anchor" in str(row.get("message"))
        for row in findings
    ), findings
    payload = evaluate_authoring_gate(draft)
    assert payload["status"] == "fail"
    assert not authoring_gate_passed(draft)
    messages = " ".join(str(f.get("message") or "") for f in payload["findings"])
    assert "totally_fake_anchor" in messages


def test_valid_tax_totals_xpath_passes_packet_ground() -> None:
    packet = _sale_packet()
    draft = _seed_draft()
    draft["_schema_packet"] = packet
    draft["custom_code_blocks"] = [
        {
            "source_file": "models/sale_markup.py",
            "kind": "python",
            "content": (
                "from odoo import fields, models\n\n"
                "class SaleOrder(models.Model):\n"
                "    _inherit = 'sale.order'\n"
                "    x_markup_percent = fields.Float(string='Markup %')\n"
            ),
        },
        {
            "source_file": "models/__init__.py",
            "kind": "python",
            "content": "from . import sale_markup\n",
        },
        {
            "source_file": "views/sale_markup.xml",
            "kind": "xml",
            "content": (
                '<odoo>\n'
                '  <record id="view_order_form_markup" model="ir.ui.view">\n'
                '    <field name="name">sale.order.form.markup</field>\n'
                '    <field name="model">sale.order</field>\n'
                '    <field name="inherit_id" ref="sale.view_order_form"/>\n'
                '    <field name="arch" type="xml">\n'
                '      <xpath expr="//field[@name=\'tax_totals\']" position="before">\n'
                '        <field name="x_markup_percent"/>\n'
                "      </xpath>\n"
                "    </field>\n"
                "  </record>\n"
                "</odoo>\n"
            ),
        },
    ]
    findings = packet_ground_findings(draft, packet=packet)
    assert findings == [], findings


def test_repair_prompt_contains_schema_packet(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai_option_a_feedback import _default_repair_blocks

    packet = _sale_packet()
    prompts: list[str] = []

    class Dummy:
        name = "mock"

    def capture(_prov: object, prompt: str, **_k: object) -> str:
        prompts.append(prompt)
        return json.dumps({"blocks": []})

    monkeypatch.setattr("app.llm_provider.get_llm_provider_for_tier", lambda *_a, **_k: Dummy())
    monkeypatch.setattr("app.llm_provider.generate_json_with_timeout_retry", capture)

    draft = _seed_draft()
    draft["_schema_packet"] = packet
    draft["custom_code_blocks"] = [
        {
            "source_file": "models/sale_markup.py",
            "kind": "python",
            "content": (
                "from odoo import fields, models\n\n"
                "class SaleOrder(models.Model):\n"
                "    _inherit = 'sale.order'\n"
                "    x_markup_percent = fields.Float(string='Markup %')\n"
            ),
        }
    ]
    _default_repair_blocks("Fix the Fault on models/sale_markup.py", draft)
    assert prompts, "expected repair LLM call"
    assert "LIVE SCHEMA PACKET" in prompts[0]
    assert "MODEL sale.order" in prompts[0]
