"""Sale fiscal/compute CLASS — markup % + WHT on markup only (P1 Job 2).

Class-wide Option A on sale.order (stock sale host): percentage markup drives
amounts; withholding/tax base = markup only; never purchase.order; never Prefer
/ Studio % field alone as “enough” for automated math on Online.

Completeness ≠ Cert ≠ Autopilot. Promote stays human.
"""

from __future__ import annotations

import re
from typing import Any

CLASS_INTENT_ID = "sale_order_markup_wht"
CLASS_MARKER = "ingenium:markup_wht_class"
HOST_MODEL = "sale.order"

_MARKUP_RE = re.compile(r"(?i)\bmark-?up\b|\bmark\s*up\b")
_WHT_RE = re.compile(r"(?i)\bwithh?olding\s+tax\b|\bwht\b")
_SALE_HOST_RE = re.compile(
    r"(?i)\b("
    r"sale\.order|sales?\s+order|quotation|every\s+sale|each\s+sale|"
    r"for\s+sales|on\s+sales|sale\s+they|selling\s+price"
    r")\b"
)
_PURCHASE_ONLY_RE = re.compile(
    r"(?i)\b(purchase\.order|purchase\s+orders?|vendor\s+bill|rfq)\b"
)
_SALES_NEGATION_RE = re.compile(
    r"(?i)\b(not\s+purchases?|never\s+purchases?|sales?\s+only|only\s+for\s+sales)\b"
)
_TAX_CREATE_RE = re.compile(
    r"""(?:env\s*\[\s*['\"]account\.tax['\"]\s*\]|\baccount\.tax\b)\s*\.\s*create\s*\(""",
    re.I,
)
_PURCHASE_INHERIT_RE = re.compile(
    r"""_inherit\s*=\s*['\"]purchase\.order['\"]""",
    re.I,
)


def is_markup_wht_class_brief(prompt: str) -> bool:
    """True for sale markup (+ optional WHT) fiscal/compute CLASS."""
    text = prompt or ""
    if not _MARKUP_RE.search(text):
        return False
    # Explicit "not sales" / purchase-only → out of class.
    if re.search(r"(?i)\bnot\s+sales?\b", text) and _PURCHASE_ONLY_RE.search(text):
        return False
    if _PURCHASE_ONLY_RE.search(text) and not (
        _SALE_HOST_RE.search(text) or _SALES_NEGATION_RE.search(text)
    ):
        return False
    return True


def markup_wht_host_from_prompt(prompt: str) -> str:
    """Always sale.order for this class — never purchase.order."""
    _ = prompt
    return HOST_MODEL


def class_mutant_briefs() -> list[dict[str, str]]:
    """Parameterized brief mutants — not one client SOW string."""
    return [
        {
            "id": "markup_wht_classic",
            "prompt": (
                "Add a markup percentage on every Sale. Selling price = cost + markup. "
                "Withholding tax on the markup amount only, sales only — not purchases."
            ),
        },
        {
            "id": "markup_wht_range",
            "prompt": (
                "On sale.order, operator chooses markup % between 10 and 25 at entry. "
                "WHT applies only to the markup portion. Never create account.tax."
            ),
        },
        {
            "id": "markup_only_no_wht_cue",
            "prompt": (
                "Mark-up line on Sales quotations: percentage drives line selling price "
                "from product cost. Sales only."
            ),
        },
        {
            "id": "markup_wht_compute",
            "prompt": (
                "Custom python compute on sale.order for markup percent, markup amount, "
                "and withholding on markup; do not touch purchase orders."
            ),
        },
    ]


def online_metadata_incomplete_interim(
    *,
    prompt: str = "",
    host_model: str = HOST_MODEL,
) -> dict[str, Any]:
    """Prefer / Studio % field alone on Online is incomplete interim — not Autopilot done."""
    from app.ai_class_stamp import LANE_COPY, apply_class_stamp, resolve_class_stamp

    ir: dict[str, Any] = {
        "intent_id": "sale_markup_online_incomplete_interim",
        "host_model": host_model or HOST_MODEL,
        "path": "prefer_or_studio_metadata",
        "complete": False,
        "interim": True,
        "checks": [
            {"id": "markup_percent_field", "required": True, "status": "interim"},
            {"id": "automated_price_effect", "required": True, "status": "blocked_online"},
            {"id": "wht_base_markup", "required": False, "status": "blocked_online"},
            {"id": "module_lane_required", "required": True, "status": "pending"},
        ],
        "operator_copy": (
            "Online lane can add a Markup % metadata field (Prefer / Studio), but "
            "automated selling-price math and WHT-on-markup require an Option A "
            "Python module on Odoo.sh / self-host. Completeness ≠ Cert ≠ Autopilot. "
            "Promote stays human — Online Python promote is blocked."
        ),
    }
    apply_class_stamp(
        ir,
        resolve_class_stamp(
            prompt=prompt,
            capability="option_a_authored",
            grain="full_app",
            needs_module=True,
            module_delivery=True,
        ),
    )
    # Honest Online interim: metadata lane for the % field, module lane still required.
    ir["delivery_lane"] = "online_metadata"
    ir["delivery_lane_copy"] = LANE_COPY["online_metadata"]
    ir["artifact_kind"] = "option_a_module"
    ir["prove_status"] = "pending"
    ir["module_lane_required"] = True
    ir["module_lane_copy"] = LANE_COPY["module_sh_or_self"]
    return ir


def _scaffold_python() -> str:
    return f'''# -*- coding: utf-8 -*-
"""{CLASS_MARKER} — sale.order markup % + WHT on markup only.

CE-safe: x_* computes / onchange only. Never redefine stock _compute_amount.
Never create account.tax records via ORM. Never inherit purchase.order.
"""
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_markup_percent = fields.Float(
        string="Markup %",
        help="Percent 10-25 for this sale. WHT applies to the markup amount only.",
    )
    x_markup_amount = fields.Monetary(
        string="Markup Amount",
        compute="_compute_markup_amounts",
        store=True,
        currency_field="currency_id",
    )
    x_wht_on_markup = fields.Monetary(
        string="WHT on Markup",
        compute="_compute_markup_amounts",
        store=True,
        currency_field="currency_id",
        help="Withholding tax base = markup amount only (not the full selling price).",
    )
    x_wht_rate = fields.Float(
        string="WHT Rate %",
        default=0.0,
        help="Optional rate on markup amount only — reuse an existing tax xmlid; do not invent taxes.",
    )

    @api.depends(
        "order_line.price_unit",
        "order_line.product_uom_qty",
        "order_line.product_id.standard_price",
        "x_markup_percent",
        "x_wht_rate",
    )
    def _compute_markup_amounts(self):
        for order in self:
            pct = float(order.x_markup_percent or 0)
            markup = 0.0
            for line in order.order_line:
                cost = float(line.product_id.standard_price or 0)
                qty = float(line.product_uom_qty or 0)
                markup += cost * (pct / 100.0) * qty
            order.x_markup_amount = markup
            rate = float(order.x_wht_rate or 0)
            order.x_wht_on_markup = markup * (rate / 100.0)

    @api.onchange("x_markup_percent")
    def _onchange_markup_percent(self):
        for order in self:
            pct = float(order.x_markup_percent or 0)
            for line in order.order_line:
                cost = float(line.product_id.standard_price or 0)
                line.price_unit = cost * (1.0 + pct / 100.0)
'''


def _scaffold_xml() -> str:
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!-- {CLASS_MARKER} -->
<odoo>
  <record id="view_order_form_markup_wht" model="ir.ui.view">
    <field name="name">sale.order.form.markup.wht</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">
      <xpath expr="//field[@name='tax_totals']" position="before">
        <field name="x_markup_percent"/>
        <field name="x_markup_amount"/>
        <field name="x_wht_rate"/>
        <field name="x_wht_on_markup"/>
      </xpath>
    </field>
  </record>
</odoo>
'''


def scaffold_markup_wht_blocks(
    draft: dict[str, Any],
    *,
    prompt: str = "",
) -> list[dict[str, Any]]:
    """Attach CE-safe Option A blocks for the markup+WHT class."""
    text = prompt or str(draft.get("_user_prompt") or "")
    if not is_markup_wht_class_brief(text):
        return []
    host = markup_wht_host_from_prompt(text)
    blocks = [
        {
            "source_file": "models/sale_order_markup_wht.py",
            "path": "models/sale_order_markup_wht.py",
            "kind": "python",
            "filename": "sale_order_markup_wht.py",
            "model": host,
            "reason": (
                "Markup % + WHT-on-markup CLASS — sale.order only "
                "(module → sandbox → human Promote)"
            ),
            "source": "markup_wht_class_scaffold",
            "option_a": True,
            "content": _scaffold_python(),
        },
        {
            "source_file": "models/__init__.py",
            "path": "models/__init__.py",
            "kind": "python",
            "filename": "__init__.py",
            "reason": "Import sale_order_markup_wht",
            "source": "markup_wht_class_scaffold",
            "option_a": True,
            "content": "from . import sale_order_markup_wht\n",
        },
        {
            "source_file": "views/sale_order_markup_wht.xml",
            "path": "views/sale_order_markup_wht.xml",
            "kind": "xml",
            "filename": "sale_order_markup_wht.xml",
            "model": host,
            "reason": "sale.view_order_form inherit — tax_totals xpath",
            "source": "markup_wht_class_scaffold",
            "option_a": True,
            "content": _scaffold_xml(),
        },
    ]
    draft["models"] = [{"model": host, "mode": "inherit", "fields": [
        {
            "name": "x_markup_percent",
            "ttype": "float",
            "string": "Markup %",
        },
        {"name": "x_markup_amount", "ttype": "monetary", "string": "Markup Amount"},
        {"name": "x_wht_on_markup", "ttype": "monetary", "string": "WHT on Markup"},
        {"name": "x_wht_rate", "ttype": "float", "string": "WHT Rate %"},
    ]}]
    deps = list(draft.get("depends") or ["base"])
    if "sale" not in deps:
        deps.append("sale")
    draft["depends"] = deps
    draft["display_name"] = draft.get("display_name") or "Sales markup"
    draft["grain"] = "full_app"
    draft["_capability_primary_option_a"] = True
    draft["_delivery_preference"] = "module_zip"
    return blocks


def static_markup_wht_findings(
    draft: dict[str, Any],
    *,
    prompt: str = "",
) -> dict[str, Any]:
    """Static prove helpers for class acceptance checks."""
    text = prompt or str(draft.get("_user_prompt") or "")
    blocks = [b for b in (draft.get("custom_code_blocks") or []) if isinstance(b, dict)]
    blob = "\n".join(str(b.get("content") or "") for b in blocks)
    hosts = []
    for m in draft.get("models") or []:
        if isinstance(m, dict) and str(m.get("mode") or "") == "inherit":
            mid = str(m.get("model") or "")
            if mid:
                hosts.append(mid)

    markup_present = bool(
        re.search(r"\bx_markup_percent\b", blob)
        or any(
            isinstance(f, dict) and str(f.get("name")) == "x_markup_percent"
            for m in draft.get("models") or []
            if isinstance(m, dict)
            for f in (m.get("fields") or [])
        )
    )
    # WHT base = markup: x_wht_* depends on / multiplies markup amount, not full untaxed.
    wht_base = bool(
        re.search(r"\bx_wht_on_markup\b", blob)
        and (
            re.search(r"x_markup_amount", blob)
            or re.search(r"markup\s*\*\s*\(?\s*rate|markup\s*\*\s*\(rate", blob, re.I)
            or CLASS_MARKER in blob
        )
    )
    # Briefs that only ask markup (no WHT) — WHT check optional / auto-pass with note.
    wants_wht = bool(_WHT_RE.search(text))
    if not wants_wht:
        wht_base = True

    purchase_untouched = not (
        "purchase.order" in hosts or _PURCHASE_INHERIT_RE.search(blob)
    )
    no_tax_create = not bool(_TAX_CREATE_RE.search(blob))
    sale_host = HOST_MODEL in hosts or (
        not hosts and is_markup_wht_class_brief(text)
    )
    onchange_or_compute = bool(
        re.search(r"onchange\(['\"]x_markup_percent", blob)
        or re.search(r"def\s+_compute_markup", blob)
        or re.search(r"def\s+_onchange_markup", blob)
    )
    tax_totals_xpath = bool(
        re.search(r"""@name=['\"]tax_totals['\"]""", blob)
        or re.search(r"""name=['\"]tax_totals['\"]""", blob)
    )

    return {
        "host_model": HOST_MODEL if sale_host else (hosts[0] if hosts else ""),
        "markup_present": markup_present,
        "wht_base_is_markup": wht_base,
        "purchase_untouched": purchase_untouched,
        "no_tax_create": no_tax_create,
        "sale_host_only": sale_host and purchase_untouched,
        "price_effect_authored": onchange_or_compute,
        "tax_totals_xpath": tax_totals_xpath,
        "wants_wht": wants_wht,
        "class_marker": CLASS_MARKER in blob,
        "block_count": len(blocks),
    }


__all__ = [
    "CLASS_INTENT_ID",
    "CLASS_MARKER",
    "HOST_MODEL",
    "class_mutant_briefs",
    "is_markup_wht_class_brief",
    "markup_wht_host_from_prompt",
    "online_metadata_incomplete_interim",
    "scaffold_markup_wht_blocks",
    "static_markup_wht_findings",
]
