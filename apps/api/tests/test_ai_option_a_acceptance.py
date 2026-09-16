"""Option A acceptance contracts + smoke self-heal."""

from __future__ import annotations

from typing import Any

from app.ai_failure_ir import failures_from_smoke
from app.ai_option_a_acceptance import (
    acceptance_for_draft,
    draft_xpath_anchor_ok,
    ensure_python_field_strings,
    python_fields_missing_labels,
    rewrite_note_xpath_to_tax_totals,
    run_acceptance_smoke,
    stamp_option_a_acceptance,
)
from app.ai_option_a_author import seed_option_a_authored
from app.ai_generation_engine import classify_generation
from app.ai_option_a_quality import rpc_option_a_smoke
from app.ai_static_odoo import harden_authored_python, rewrite_draft_stock_xpaths

MARKUP = (
    "The Client wants a Mark-up line added to every Sale. The Markup is calculated "
    "as a percentage of every sale made. A Withholding Tax, on the markup is to be "
    "calculated as well."
)


def _markup_draft(**overrides: Any) -> dict[str, Any]:
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    draft["custom_code_blocks"] = [
        {
            "source_file": "models/sale_markup.py",
            "kind": "python",
            "content": (
                "from odoo import api, fields, models\n\n"
                "class SaleOrder(models.Model):\n"
                "    _inherit = 'sale.order'\n"
                "    x_markup_percent = fields.Float()\n"
                "    x_markup_amount = fields.Monetary(string='Markup Amount')\n"
                "\n"
                "    @api.onchange('x_markup_percent')\n"
                "    def _onchange_markup(self):\n"
                "        for order in self:\n"
                "            pct = float(order.x_markup_percent or 0)\n"
                "            for line in order.order_line:\n"
                "                cost = line.product_id.standard_price or 0\n"
                "                line.price_unit = cost * (1 + pct / 100)\n"
            ),
        },
        {
            "source_file": "views/sale_markup.xml",
            "kind": "xml",
            "content": (
                "<odoo>\n"
                '  <record id="v" model="ir.ui.view">\n'
                '    <field name="model">sale.order</field>\n'
                '    <field name="inherit_id" ref="sale.view_order_form"/>\n'
                '    <field name="arch" type="xml">\n'
                "      <xpath expr=\"//field[@name='tax_totals']\" position=\"before\">\n"
                '        <field name="x_markup_percent"/>\n'
                '        <field name="x_markup_amount"/>\n'
                "      </xpath>\n"
                "    </field>\n"
                "  </record>\n"
                "</odoo>\n"
            ),
        },
    ]
    draft.update(overrides)
    stamp_option_a_acceptance(draft, prompt=MARKUP)
    return draft


def test_stamp_markup_acceptance_contract() -> None:
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    contract = draft["_option_a_acceptance"]
    assert contract["intent_id"] == "sale_order_markup_wht"
    ids = {c["id"] for c in contract["checks"]}
    assert "field_labeled" in ids
    assert "xpath_anchor" in ids
    assert "price_effect" in ids


def test_acceptance_for_generic_inherit() -> None:
    draft = {
        "_user_prompt": "Email me when stock hits minimum via cron",
        "models": [{"model": "stock.quant", "mode": "inherit", "fields": []}],
    }
    contract = acceptance_for_draft(draft)
    assert contract["intent_id"] == "option_a_generic"
    ids = {c["id"] for c in contract["checks"]}
    assert "price_effect" not in ids
    assert "field_labeled" in ids


def test_python_fields_missing_labels() -> None:
    draft = _markup_draft()
    missing = python_fields_missing_labels(draft)
    assert "x_markup_percent" in missing
    assert "x_markup_amount" not in missing


def test_ensure_python_field_strings_and_harden() -> None:
    py = (
        "from odoo import fields, models\n"
        "class SaleOrder(models.Model):\n"
        "    _inherit = 'sale.order'\n"
        "    x_markup_percent = fields.Float()\n"
    )
    out = ensure_python_field_strings(py)
    assert "string='Markup %'" in out or 'string="Markup %"' in out
    hardened = harden_authored_python(py)
    assert "string=" in hardened


def test_rewrite_note_xpath_to_tax_totals() -> None:
    xml = (
        "<odoo><record model='ir.ui.view'>"
        "<field name='model'>sale.order</field>"
        "<field name='arch' type='xml'>"
        "<xpath expr=\"//field[@name='note']\" position='before'>"
        "<field name='x_markup_percent'/>"
        "</xpath></field></record></odoo>"
    )
    out = rewrite_note_xpath_to_tax_totals(xml)
    assert "tax_totals" in out
    assert "@name='note'" not in out and '@name="note"' not in out


def test_draft_xpath_anchor_rejects_note() -> None:
    draft = _markup_draft()
    draft["custom_code_blocks"][1]["content"] = (
        "<odoo><record model='ir.ui.view'>"
        "<field name='model'>sale.order</field>"
        "<field name='arch' type='xml'>"
        "<xpath expr=\"//field[@name='note']\" position='before'>"
        "<field name='x_markup_percent'/>"
        "</xpath></field></record></odoo>"
    )
    assert draft_xpath_anchor_ok(draft)["ok"] is False
    rewrite_draft_stock_xpaths(draft)
    assert draft_xpath_anchor_ok(draft)["ok"] is True


def test_failures_from_smoke_per_check() -> None:
    smoke = {
        "ok": False,
        "message": "Acceptance smoke failed",
        "checks": [
            {
                "id": "field_labeled",
                "ok": False,
                "detail": "unlabeled: x_markup_percent",
                "repair_hint": "add string=",
            },
            {"id": "price_effect", "ok": True, "detail": "ok"},
        ],
    }
    fails = failures_from_smoke(smoke)
    assert len(fails) == 1
    assert fails[0]["category"] == "smoke"
    assert "field_labeled" in fails[0]["message"]
    assert fails[0].get("repair_hint") == "add string="
    assert fails[0].get("file") == "models/"


class _FakeKw:
    """Minimal execute_kw for acceptance smoke unit tests."""

    def __init__(self, *, labels: dict[str, str], price_after: float = 100.0) -> None:
        self.labels = labels
        self.price_after = price_after
        self._ids = 100

    def __call__(
        self, model: str, method: str, args: list, kwargs: dict | None = None
    ) -> Any:
        kwargs = kwargs or {}
        if method == "fields_get":
            out = {}
            for name, label in self.labels.items():
                out[name] = {
                    "string": label,
                    "type": "float" if "percent" in name else "monetary",
                }
            if "x_markup_percent" in out:
                out["x_markup_percent"]["type"] = "float"
            return out
        if method == "search_read" and model == "ir.ui.view":
            arch = (
                '<data><field name="tax_totals"/>'
                '<field name="x_markup_percent"/>'
                '<field name="x_markup_amount"/></data>'
            )
            return [{"id": 1, "name": "markup", "arch_db": arch}]
        if method == "search":
            return [1]
        if method == "create":
            self._ids += 1
            return self._ids
        if method == "write":
            return True
        if method == "onchange":
            return {}
        if method == "read":
            fields = args[1] if len(args) > 1 else []
            row = {f: 0 for f in fields}
            if "price_unit" in fields:
                row["price_unit"] = self.price_after
            if "x_markup_amount" in fields:
                row["x_markup_amount"] = 15.0 if self.price_after > 100 else 0.0
            return [row]
        if method == "get_views":
            return {"views": {}}
        return []


def test_run_acceptance_smoke_fails_unlabeled() -> None:
    draft = _markup_draft()
    # Harden would add string — leave unlabeled and mock registry with technical string.
    execute_kw = _FakeKw(labels={"x_markup_percent": "x_markup_percent", "x_markup_amount": "Markup Amount"})
    result = run_acceptance_smoke(draft, execute_kw=execute_kw)
    assert result["ok"] is False
    by_id = {c["id"]: c for c in result["checks"]}
    assert by_id["field_labeled"]["ok"] is False


def test_run_acceptance_smoke_fails_no_price_effect() -> None:
    draft = _markup_draft()
    rewrite_draft_stock_xpaths(draft)
    execute_kw = _FakeKw(
        labels={"x_markup_percent": "Markup %", "x_markup_amount": "Markup Amount"},
        price_after=100.0,
    )
    # Force amount field to stay 0 by making read return 0 for amount when price unchanged.
    result = run_acceptance_smoke(draft, execute_kw=execute_kw)
    by_id = {c["id"]: c for c in result["checks"]}
    # price stays 100 and FakeKw returns x_markup_amount=0 when price_after<=100
    assert by_id["price_effect"]["ok"] is False


def test_run_acceptance_smoke_passes_good_module() -> None:
    draft = _markup_draft()
    rewrite_draft_stock_xpaths(draft)
    execute_kw = _FakeKw(
        labels={"x_markup_percent": "Markup %", "x_markup_amount": "Markup Amount"},
        price_after=115.0,
    )
    result = run_acceptance_smoke(draft, execute_kw=execute_kw)
    assert result["ok"] is True
    assert all(c["ok"] for c in result["checks"])


def test_rpc_option_a_smoke_merges_acceptance() -> None:
    draft = _markup_draft()
    rewrite_draft_stock_xpaths(draft)
    execute_kw = _FakeKw(
        labels={"x_markup_percent": "Markup %", "x_markup_amount": "Markup Amount"},
        price_after=115.0,
    )
    smoke = rpc_option_a_smoke(draft, execute_kw=execute_kw)
    assert smoke["ok"] is True
    assert smoke.get("acceptance_ok") is True
    ids = {c["id"] for c in smoke["checks"] if isinstance(c, dict)}
    assert "field_labeled" in ids
    assert "price_effect" in ids
