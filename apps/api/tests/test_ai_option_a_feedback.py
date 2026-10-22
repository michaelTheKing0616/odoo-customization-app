"""Option A feedback repair (Repair with AI) on LLM-authored modules.

Rebuilt from the lost test file (intent recovered from its stale .pyc) and from
what ``app.ai_option_a_feedback`` does now. Fake LLM only: ``generate_blocks``
is injected, or the provider lookup is monkeypatched.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from app.ai_generation_engine import classify_generation
from app.ai_option_a_author import seed_option_a_authored
from app.ai_option_a_feedback import repair_option_a_from_feedback

MARKUP = (
    "The Client wants a Mark-up line added to every Sale. The Markup is calculated "
    "as a percentage of every sale made. A Withholding Tax, on the markup is to be "
    "calculated as well."
)

PYTHON_INHERIT = (
    "from odoo import api, fields, models\n\n"
    "class SaleOrder(models.Model):\n"
    "    _inherit = 'sale.order'\n"
    "    x_markup_percent = fields.Float(string='Markup %')\n"
    "    x_markup_amount = fields.Monetary(string='Markup Amount')\n"
    "    x_wht_on_markup = fields.Monetary(\n"
    "        string='WHT on Markup', compute='_compute_wht_on_markup')\n"
    "\n"
    "    @api.depends('x_markup_amount')\n"
    "    def _compute_wht_on_markup(self):\n"
    "        for order in self:\n"
    "            order.x_wht_on_markup = (order.x_markup_amount or 0) * 0.05\n"
    "\n"
    "    @api.onchange('x_markup_percent')\n"
    "    def _onchange_markup(self):\n"
    "        for order in self:\n"
    "            pct = float(order.x_markup_percent or 0)\n"
    "            for line in order.order_line:\n"
    "                cost = line.product_id.standard_price or 0\n"
    "                line.price_unit = cost * (1 + pct / 100)\n"
)

_VIEW = (
    "<odoo>\n"
    '  <record id="view_order_form_markup" model="ir.ui.view">\n'
    '    <field name="name">sale.order.form.markup</field>\n'
    '    <field name="model">sale.order</field>\n'
    '    <field name="inherit_id" ref="sale.view_order_form"/>\n'
    '    <field name="arch" type="xml">\n'
    '      <xpath expr="//field[@name=\'ANCHOR\']" position="before">\n'
    '        <field name="x_markup_percent"/>\n'
    '        <field name="x_markup_amount"/>\n'
    '        <field name="x_wht_on_markup"/>\n'
    "      </xpath>\n"
    "    </field>\n"
    "  </record>\n"
    "</odoo>\n"
)
TAX_TOTALS_XML = _VIEW.replace("ANCHOR", "tax_totals")
AMOUNT_TAX_XML = _VIEW.replace("ANCHOR", "amount_tax")

PARSE_AMOUNT_TAX = (
    "odoo.tools.convert.ParseError: while parsing views/sale_order_views.xml:3\n"
    "Element '<xpath expr=\"//field[@name='amount_tax']\">' cannot be located in parent view"
)
RUNTIME_FAULT = (
    'File "/mnt/extra-addons/x_markup/models/sale_markup.py", line 21, in _onchange_markup\n'
    "AttributeError: 'product.product' object has no attribute 'standard_cost'"
)


def _authored_draft(xml: str = TAX_TOTALS_XML, python: str = PYTHON_INHERIT) -> dict[str, Any]:
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    draft["custom_code_blocks"] = [
        {"source_file": "models/sale_markup.py", "kind": "python", "content": python},
        {
            "source_file": "models/__init__.py",
            "kind": "python",
            "content": "from . import sale_markup\n",
        },
        {"source_file": "views/sale_order_views.xml", "kind": "xml", "content": xml},
    ]
    draft["_option_a_authoring"] = {"status": "pass"}
    draft["_user_prompt"] = MARKUP
    return draft


def _content(draft: dict[str, Any], path: str) -> str:
    for block in draft.get("custom_code_blocks") or []:
        if block.get("source_file") == path:
            return str(block.get("content") or "")
    raise AssertionError(f"missing block {path}")


def _patch_markup(prompt: str, draft: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "source_file": "models/sale_markup.py",
            "content": PYTHON_INHERIT.replace("standard_price or 0", "standard_price or 0.0"),
        }
    ]


def test_xpath_rewrite_ignores_authoring_repair_budget() -> None:
    draft = _authored_draft(xml=AMOUNT_TAX_XML)
    draft["_repair_count"] = 99  # authoring budget long gone
    calls: list[str] = []

    res = repair_option_a_from_feedback(
        draft,
        error_text=PARSE_AMOUNT_TAX,
        generate_blocks=lambda p, d: calls.append(p) or [],
    )

    assert res["applied"] is True
    assert res["deterministic"] is True
    assert res["llm"] is False
    assert calls == []  # known CE fault + free fix: no LLM call
    xml = _content(draft, "views/sale_order_views.xml")
    assert "amount_tax" not in xml
    assert "tax_totals" in xml
    assert int(draft.get("_sandbox_repair_count") or 0) == 0
    assert "did not use Repair budget" in res["message"]


def test_sandbox_budget_is_independent_and_honest() -> None:
    draft = _authored_draft()
    draft["_repair_count"] = 99
    draft["_sandbox_repair_count"] = 3

    res = repair_option_a_from_feedback(
        draft, error_text=RUNTIME_FAULT, generate_blocks=_patch_markup
    )

    assert res["applied"] is False
    assert res["reason"] == "max_repair_exceeded"
    msg = str(res.get("message") or "")
    assert "budget" in msg.lower()
    assert "Download module zip" in msg, "Download module zip still works"
    assert "Do not click Install this app" in msg
    assert draft["_option_a_feedback_repair"] is res


def test_authoring_budget_does_not_block_sandbox_repair() -> None:
    draft = _authored_draft()
    draft["_repair_count"] = 99

    res = repair_option_a_from_feedback(
        draft, error_text=RUNTIME_FAULT, generate_blocks=_patch_markup
    )

    assert res["ok"] is True
    assert res["llm"] is True
    assert res["files"] == ["models/sale_markup.py"]
    assert res["gate_status"] == "pass"
    assert "standard_price or 0.0" in _content(draft, "models/sale_markup.py")
    assert draft["_sandbox_repair_count"] == 1
    assert "Publishing stays a step you confirm" in res["message"]


def test_patch_outside_implicated_files_is_ignored() -> None:
    draft = _authored_draft()
    before = copy.deepcopy(draft["custom_code_blocks"])

    res = repair_option_a_from_feedback(
        draft,
        error_text=RUNTIME_FAULT,
        generate_blocks=lambda p, d: [
            {"source_file": "models/__init__.py", "content": "import os\n"},
            {"source_file": "models/not_in_module.py", "content": "x = 1\n"},
        ],
    )

    assert res["applied"] is False
    assert res["reason"] == "no_patch"
    assert draft["custom_code_blocks"] == before
    assert "did not return a patch" in res["message"]


def test_llm_error_is_stamped_not_raised() -> None:
    draft = _authored_draft()

    def boom(prompt: str, d: dict[str, Any]) -> list[dict[str, Any]]:
        raise TimeoutError("fake provider timeout")

    res = repair_option_a_from_feedback(draft, error_text=RUNTIME_FAULT, generate_blocks=boom)

    assert res["applied"] is False
    assert "fake provider timeout" in draft["_option_a_feedback_repair_error"]


def test_repair_prompt_carries_fault_and_files() -> None:
    draft = _authored_draft()
    seen: list[str] = []
    repair_option_a_from_feedback(
        draft,
        error_text=RUNTIME_FAULT,
        operator_notes="Use standard_price, not standard_cost.",
        generate_blocks=lambda p, d: seen.append(p) or [],
    )
    assert seen, "fake LLM should be called once"
    assert "standard_cost" in seen[0]
    assert "models/sale_markup.py" in seen[0]
    assert "Use standard_price" in seen[0]


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda d: d.update({"_generation_engine": {"capability": "stock_reuse"}}), "not_authored"),
        (lambda d: None, "no_feedback"),
    ],
)
def test_refusals_are_honest(mutate: Any, reason: str) -> None:
    draft = _authored_draft()
    mutate(draft)
    res = repair_option_a_from_feedback(draft, error_text="", generate_blocks=_patch_markup)
    assert res["ok"] is False
    assert res["applied"] is False
    assert res["reason"] == reason


def test_gold_templates_are_never_llm_patched(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.ai_option_a_feedback as fb

    monkeypatch.setattr(fb, "is_gold_option_a_draft", lambda d: True)
    draft = _authored_draft()
    res = repair_option_a_from_feedback(
        draft, error_text=RUNTIME_FAULT, generate_blocks=_patch_markup
    )
    assert res["reason"] == "gold_locked"
    assert "Do not Install this app" in res["message"]


def test_default_repair_grounds_prompt_in_schema_packet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uncommitted GND-G-OPTA change: the repair prompt carries the host schema slice."""
    import app.ai_option_a_packet_ground as pg
    import app.llm_provider as lp
    from app.ai_option_a_feedback import _default_repair_blocks

    sent: list[str] = []
    monkeypatch.setattr(lp, "get_llm_provider_for_tier", lambda tier: object())
    monkeypatch.setattr(pg, "ensure_option_a_schema_packet", lambda draft, prompt="": None)
    monkeypatch.setattr(pg, "user_prompt_with_schema_packet", lambda p, d: p + "\n[SCHEMA PACKET]")

    def fake_generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        sent.extend(str(a) for a in args if isinstance(a, str))
        sent.extend(str(v) for v in kwargs.values() if isinstance(v, str))
        return {}

    monkeypatch.setattr(lp, "generate_json_with_timeout_retry", fake_generate)
    _default_repair_blocks("Fix the fault", _authored_draft())
    assert any("[SCHEMA PACKET]" in s for s in sent)


def test_default_repair_without_provider_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.llm_provider as lp
    from app.ai_option_a_feedback import _default_repair_blocks

    monkeypatch.setattr(lp, "get_llm_provider_for_tier", lambda tier: None)
    assert _default_repair_blocks("Fix the fault", _authored_draft()) == []
