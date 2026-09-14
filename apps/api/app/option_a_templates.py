"""Hand-written Option A gold artifacts — selected, not LLM-invented OWL."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.ai_generation_engine import GenerationPlan

GOLD_TEMPLATE_IDS = frozenset(
    {"pos_receipt_options", "invoice_qweb", "currency_rate_cbn"}
)


def apply_gold_template(
    prompt: str,
    template_id: str,
    *,
    plan: GenerationPlan | None = None,
) -> dict[str, Any]:
    if template_id == "pos_receipt_options":
        return _pos_receipt_options_draft(prompt, plan=plan)
    if template_id == "currency_rate_cbn":
        return _currency_rate_cbn_draft(prompt, plan=plan)
    if template_id == "invoice_qweb":
        from app.ai_capability_option_a_scaffold import scaffold_blocks_for_gaps
        from app.ai_generation_engine import attach_generation_engine, plan_to_ir
        from app.ai_llm_status import attach_llm_status
        from app.ai_operator_brief import attach_operator_brief

        draft: dict[str, Any] = {
            "technical_name": "invoice_document_extras",
            "display_name": "Invoice document extras",
            "depends": ["account"],
            "models": [
                {
                    "model": "account.move",
                    "description": "Invoice",
                    "mode": "inherit",
                    "fields": [
                        {
                            "name": "x_qr_payload",
                            "ttype": "char",
                            "string": "QR payload",
                            "help": "Raw payload for a report QR. PDF wiring is Option A.",
                        }
                    ],
                }
            ],
            "grain": "full_app",
            "_user_prompt": prompt,
            "_pipeline": "gold_template",
            "_capability_primary_option_a": True,
        }
        scaffolds = scaffold_blocks_for_gaps(draft, {"pdf_report", "qr_on_document", "click_to_pay"})
        if scaffolds:
            draft["custom_code_blocks"] = scaffolds
        attach_operator_brief(draft, user_prompt=prompt)
        attach_llm_status(draft, mode="pack_fallback", reason="gold_invoice_qweb")
        attach_generation_engine(draft, prompt, user_phase="review")
        ir = draft.get("_generation_engine")
        if isinstance(ir, dict):
            if plan is not None:
                for key, val in plan_to_ir(plan, user_phase="review").items():
                    ir[key] = val
            ir["gold_artifact_id"] = "invoice_qweb"
            ir["capability"] = "option_a_standalone"
            ir["module_delivery"] = True
        return draft
    raise ValueError(f"unknown gold template {template_id}")


def _pos_receipt_options_draft(
    prompt: str,
    *,
    plan: GenerationPlan | None = None,
) -> dict[str, Any]:
    from app.ai_generation_engine import (
        attach_generation_engine,
        option_a_settings_from_draft,
        plan_to_ir,
    )
    from app.ai_llm_status import attach_llm_status
    from app.ai_operator_brief import attach_operator_brief

    paper = "80"
    if re_search_58(prompt):
        paper = "58"
    models = [
        {
            "model": "pos.config",
            "description": "Point of Sale",
            "mode": "inherit",
            "fields": [
                {
                    "name": "x_receipt_header",
                    "ttype": "char",
                    "string": "Receipt header",
                    "help": "Printed above the stock OrderReceipt body.",
                },
                {
                    "name": "x_receipt_footer",
                    "ttype": "char",
                    "string": "Receipt footer",
                },
                {
                    "name": "x_receipt_paper_width",
                    "ttype": "selection",
                    "string": "Paper width",
                    "selection": "[('58','58 mm'),('80','80 mm')]",
                    "help": f"Default from prompt: {paper} mm. Not a live thermal WYSIWYG.",
                },
                {
                    "name": "x_receipt_show_logo",
                    "ttype": "boolean",
                    "string": "Show company logo",
                },
            ],
        }
    ]
    draft: dict[str, Any] = {
        "technical_name": "pos_receipt_options",
        "display_name": "POS Receipt Options",
        "depends": ["point_of_sale"],
        "models": models,
        "grain": "full_app",
        "_user_prompt": prompt,
        "_pipeline": "gold_template",
        "_capability_primary_option_a": True,
        "custom_code_blocks": _pos_receipt_blocks(),
    }
    attach_operator_brief(draft, user_prompt=prompt)
    attach_llm_status(draft, mode="pack_fallback", reason="gold_pos_receipt_options")
    attach_generation_engine(draft, prompt, user_phase="review")
    ir = draft.get("_generation_engine")
    if isinstance(ir, dict):
        if plan is not None:
            merged = plan_to_ir(plan, user_phase="review")
            for key, val in merged.items():
                ir[key] = val
        ir["gold_artifact_id"] = "pos_receipt_options"
        ir["capability"] = "option_a_standalone"
        ir["module_delivery"] = True
        ir["studio_parity_deferred"] = True
        settings = option_a_settings_from_draft(draft)
        if settings:
            ir["option_a_settings"] = settings
    return draft


def re_search_58(prompt: str) -> bool:
    import re

    return bool(re.search(r"(?i)\b58\s*mm\b", prompt or ""))


def _pos_receipt_blocks() -> list[dict[str, Any]]:
    py = '''# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    x_receipt_header = fields.Char(string="Receipt header")
    x_receipt_footer = fields.Char(string="Receipt footer")
    x_receipt_paper_width = fields.Selection(
        [("58", "58 mm"), ("80", "80 mm")],
        string="Paper width",
        default="80",
    )
    x_receipt_show_logo = fields.Boolean(string="Show company logo", default=True)
'''
    xml = """<?xml version="1.0" encoding="utf-8"?>
<templates xml:space="preserve">
    <t t-name="pos_receipt_options.OrderReceipt"
       t-inherit="point_of_sale.OrderReceipt" t-inherit-mode="extension">
        <xpath expr="//div[contains(@class, 'pos-receipt')]" position="before">
            <div t-if="env.services.pos.config.x_receipt_header"
                 class="pos-receipt-header text-center">
                <t t-esc="env.services.pos.config.x_receipt_header"/>
            </div>
        </xpath>
        <xpath expr="//div[contains(@class, 'pos-receipt')]" position="inside">
            <div t-if="env.services.pos.config.x_receipt_footer"
                 class="pos-receipt-footer text-center">
                <t t-esc="env.services.pos.config.x_receipt_footer"/>
            </div>
        </xpath>
    </t>
</templates>
"""
    test = '''# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPosReceiptOptions(TransactionCase):
    def test_pos_config_fields_registered(self):
        fields = self.env["pos.config"]._fields
        self.assertIn("x_receipt_header", fields)
        self.assertIn("x_receipt_footer", fields)
        self.assertIn("x_receipt_paper_width", fields)
        self.assertIn("x_receipt_show_logo", fields)

    def test_no_receipt_document_model(self):
        self.assertFalse(
            self.env["ir.model"].search([("model", "=", "x_receipt")], limit=1)
        )
'''
    init_tests = "# -*- coding: utf-8 -*-\nfrom . import test_pos_receipt_options\n"
    return [
        {
            "source_file": "models/pos_config.py",
            "kind": "python",
            "reason": "gold: pos.config receipt options",
            "content": py,
        },
        {
            "source_file": "static/src/xml/order_receipt.xml",
            "kind": "xml",
            "reason": "gold: OrderReceipt inherit (not a visual designer)",
            "content": xml,
        },
        {
            "source_file": "tests/__init__.py",
            "kind": "test",
            "reason": "gold: tests package",
            "content": init_tests,
        },
        {
            "source_file": "tests/test_pos_receipt_options.py",
            "kind": "test",
            "reason": "gold: inherit field tests",
            "content": test,
        },
    ]


def _currency_rate_cbn_draft(
    prompt: str,
    *,
    plan: GenerationPlan | None = None,
) -> dict[str, Any]:
    from app.ai_generation_engine import attach_generation_engine, plan_to_ir
    from app.ai_llm_status import attach_llm_status
    from app.ai_operator_brief import attach_operator_brief

    models = [
        {
            "model": "res.company",
            "description": "Company",
            "mode": "inherit",
            "fields": [],
        }
    ]
    draft: dict[str, Any] = {
        "technical_name": "currency_rate_cbn",
        "display_name": "CBN Currency Rates",
        "depends": ["account"],
        "models": models,
        "grain": "full_app",
        "_user_prompt": prompt,
        "_pipeline": "gold_template",
        "_capability_primary_option_a": True,
        "custom_code_blocks": _currency_rate_cbn_blocks(),
    }
    attach_operator_brief(draft, user_prompt=prompt)
    attach_llm_status(draft, mode="pack_fallback", reason="gold_currency_rate_cbn")
    attach_generation_engine(draft, prompt, user_phase="review")
    ir = draft.get("_generation_engine")
    if isinstance(ir, dict):
        if plan is not None:
            merged = plan_to_ir(plan, user_phase="review")
            for key, val in merged.items():
                ir[key] = val
        ir["gold_artifact_id"] = "currency_rate_cbn"
        ir["capability"] = "option_a_standalone"
        ir["module_delivery"] = True
        ir["option_a_settings"] = {
            "model": "res.company",
            "fields": [
                {
                    "name": "cbn_interval_unit",
                    "string": "CBN rate interval",
                    "help": (
                        "Community has no ECB Service. Interval for the CBN cron. "
                        "Does not change company currency."
                    ),
                },
                {
                    "name": "cbn_next_run",
                    "string": "CBN next run",
                    "help": "Informational. The ir.cron nextcall is authoritative.",
                },
            ],
        }
    return draft


def _currency_rate_cbn_blocks() -> list[dict[str, Any]]:
    py = r'''# -*- coding: utf-8 -*-
import json
import logging
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CBN_RATES_URL = "https://www.cbn.gov.ng/api/GetAllExchangeRatesGRAPH"
CBN_QUOTED_ISO = ("USD", "GBP", "EUR")
CBN_NAME_TO_ISO = {
    "US DOLLAR": "USD",
    "POUNDS STERLING": "GBP",
    "EURO": "EUR",
    "YEN": "JPY",
    "YUAN/RENMINBI": "CNY",
    "CFA": "XOF",
    "RIYAL": "SAR",
    "SOUTH AFRICAN RAND": "ZAR",
    "SWISS FRANC": "CHF",
    "UAE DIRHAM": "AED",
    "SDR": "XDR",
    "DANISH KRONA": "DKK",
}


class ResCompany(models.Model):
    _inherit = "res.company"

    cbn_interval_unit = fields.Selection(
        [
            ("manually", "Manually"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
        ],
        string="CBN rate interval",
        default="daily",
    )
    cbn_next_run = fields.Date(string="CBN next run")

    def write(self, vals):
        res = super().write(vals)
        if "cbn_interval_unit" in vals:
            self._cbn_sync_cron_active()
        return res

    def _cbn_sync_cron_active(self):
        cron = self.env.ref(
            "currency_rate_cbn.ir_cron_cbn_currency_rates",
            raise_if_not_found=False,
        )
        if not cron:
            return
        cron.active = any(c.cbn_interval_unit != "manually" for c in self.search([]))

    def _cbn_root_company(self):
        self.ensure_one()
        return self.root_id if "root_id" in self._fields else self

    def action_activate_quoted_currencies(self):
        Currency = self.env["res.currency"].with_context(active_test=False)
        activated = []
        for iso in CBN_QUOTED_ISO:
            cur = Currency.search([("name", "=", iso)], limit=1)
            if cur and not cur.active:
                cur.active = True
                activated.append(iso)
        return activated

    def update_currency_rates(self):
        companies = self or self.search([])
        errors = []
        for company in companies:
            try:
                company._update_currency_cbn()
            except UserError as exc:
                errors.append("%s: %s" % (company.display_name, exc))
        if errors:
            raise UserError("\n".join(errors))
        return True

    def _cron_update_cbn_rates(self):
        self.search([("cbn_interval_unit", "!=", "manually")]).update_currency_rates()

    def _cbn_fetch_payload(self):
        request = Request(
            CBN_RATES_URL,
            headers={"User-Agent": "OdooCurrencyRateCBN/1.0"},
        )
        try:
            with urlopen(request, timeout=20) as resp:
                raw = resp.read()
        except (URLError, HTTPError, TimeoutError, OSError) as exc:
            raise UserError(
                "CBN rate feed failed (%s). No res.currency.rate was written." % exc
            ) from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise UserError(
                "CBN rate feed was not JSON. No res.currency.rate was written."
            ) from exc
        if not isinstance(data, list):
            raise UserError("CBN rate feed shape is not a list. Nothing written.")
        return data

    def _cbn_latest_naira_per_iso(self, payload):
        latest = {}
        for row in payload:
            if not isinstance(row, dict):
                continue
            iso = CBN_NAME_TO_ISO.get(str(row.get("currency") or "").strip().upper())
            if not iso:
                continue
            try:
                naira = float(row.get("centralrate") or 0)
                ratedate = str(row.get("ratedate") or "")
            except (TypeError, ValueError):
                continue
            if naira <= 0 or not ratedate:
                continue
            prev = latest.get(iso)
            if not prev or ratedate > prev[0]:
                latest[iso] = (ratedate, naira)
        return {iso: pair[1] for iso, pair in latest.items()}

    def _cbn_odoo_rate(self, naira_per_foreign, naira_per_company):
        if naira_per_foreign <= 0 or naira_per_company <= 0:
            raise UserError("CBN returned a non-positive rate. Nothing written.")
        return naira_per_company / naira_per_foreign

    def _update_currency_cbn(self):
        self.ensure_one()
        company = self._cbn_root_company()
        payload = self._cbn_fetch_payload()
        naira_map = self._cbn_latest_naira_per_iso(payload)
        missing = [iso for iso in CBN_QUOTED_ISO if iso not in naira_map]
        if missing:
            raise UserError(
                "CBN feed is missing %s. No res.currency.rate was written."
                % ", ".join(missing)
            )
        company.action_activate_quoted_currencies()
        company_iso = (company.currency_id.name or "").upper()
        if company_iso == "NGN":
            naira_per_company = 1.0
        elif company_iso in naira_map:
            naira_per_company = naira_map[company_iso]
        else:
            raise UserError(
                "Company currency %s is not NGN and is not on the CBN table. "
                "Set company currency to NGN (or a CBN-quoted ISO) before Update."
                % (company_iso or "(empty)")
            )
        Currency = self.env["res.currency"].with_context(active_test=False)
        Rate = self.env["res.currency.rate"]
        today = fields.Date.context_today(self)
        written = []
        for iso in CBN_QUOTED_ISO:
            if iso == company_iso:
                continue
            currency = Currency.search([("name", "=", iso)], limit=1)
            if not currency:
                _logger.warning("currency_rate_cbn: ISO %s not in res.currency", iso)
                continue
            odoo_rate = self._cbn_odoo_rate(naira_map[iso], naira_per_company)
            domain = [
                ("currency_id", "=", currency.id),
                ("name", "=", today),
                ("company_id", "=", company.id),
            ]
            existing = Rate.search(domain, limit=1)
            if existing:
                existing.write({"rate": odoo_rate})
            else:
                Rate.create(
                    {
                        "currency_id": currency.id,
                        "name": today,
                        "company_id": company.id,
                        "rate": odoo_rate,
                    }
                )
            written.append(iso)
        if not written:
            raise UserError("No quoted currencies could be written.")
        company.cbn_next_run = today
        return written


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cbn_interval_unit = fields.Selection(
        related="company_id.cbn_interval_unit",
        readonly=False,
    )
    cbn_next_run = fields.Date(related="company_id.cbn_next_run", readonly=False)

    def action_update_cbn_rates(self):
        self.ensure_one()
        self.company_id.update_currency_rates()
        return True

    def action_activate_quoted_currencies(self):
        self.ensure_one()
        self.company_id.action_activate_quoted_currencies()
        return True
'''
    settings_xml = """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="res_config_settings_view_form_cbn" model="ir.ui.view">
        <field name="name">res.config.settings.view.form.inherit.cbn</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="account.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//setting[@id='update_exchange_rates']" position="attributes">
                <attribute name="invisible">1</attribute>
            </xpath>
            <xpath expr="//setting[@id='update_exchange_rates']" position="after">
                <setting id="cbn_currency_rates"
                         string="Automatic Currency Rates"
                         help="Community Service: Central Bank of Nigeria. Writes stock res.currency.rate.">
                    <div class="content-group">
                        <div class="row mt16">
                            <label for="cbn_interval_unit" class="col-lg-3 o_light_label" string="Service"/>
                            <span>Central Bank of Nigeria</span>
                        </div>
                        <div class="row mt8">
                            <label for="cbn_interval_unit" class="col-lg-3 o_light_label"/>
                            <field name="cbn_interval_unit"/>
                        </div>
                        <div class="row mt8">
                            <label for="cbn_next_run" class="col-lg-3 o_light_label"/>
                            <field name="cbn_next_run"/>
                        </div>
                        <div class="mt8">
                            <button name="action_update_cbn_rates" type="object"
                                    string="Update now" class="btn-link"/>
                            <button name="action_activate_quoted_currencies" type="object"
                                    string="Activate USD, GBP, EUR" class="btn-link"/>
                        </div>
                    </div>
                </setting>
            </xpath>
        </field>
    </record>
</odoo>
"""
    cron_xml = """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record forcecreate="True" id="ir_cron_cbn_currency_rates" model="ir.cron">
        <field name="name">CBN: update currency rates</field>
        <field name="model_id" ref="base.model_res_company"/>
        <field name="state">code</field>
        <field name="code">model._cron_update_cbn_rates()</field>
        <field name="user_id" ref="base.user_root"/>
        <field name="interval_number">1</field>
        <field name="interval_type">days</field>
    </record>
</odoo>
"""
    test = '''# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCurrencyRateCbn(TransactionCase):
    def test_company_fields_registered(self):
        fields = self.env["res.company"]._fields
        self.assertIn("cbn_interval_unit", fields)
        self.assertIn("cbn_next_run", fields)

    def test_no_custom_fx_model(self):
        Model = self.env["ir.model"]
        self.assertFalse(Model.search([("model", "=", "x_fx")], limit=1))
        self.assertFalse(Model.search([("model", "=", "x_exchange")], limit=1))
        self.assertFalse(Model.search([("model", "=", "x_currency_rate")], limit=1))

    def test_odoo_rate_inverts_naira_when_company_is_ngn(self):
        company = self.env.company
        rate = company._cbn_odoo_rate(1320.716, 1.0)
        self.assertAlmostEqual(rate, 1.0 / 1320.716, places=9)
'''
    init_models = "from . import cbn_rates\n"
    init_tests = "# -*- coding: utf-8 -*-\nfrom . import test_currency_rate_cbn\n"
    return [
        {
            "source_file": "models/cbn_rates.py",
            "kind": "python",
            "reason": "gold: CBN provider writes stock res.currency.rate",
            "content": py,
        },
        {
            "source_file": "models/__init__.py",
            "kind": "python",
            "reason": "gold: import CBN inherit",
            "content": init_models,
        },
        {
            "source_file": "views/res_config_settings_views.xml",
            "kind": "xml",
            "reason": "gold: Accounting Settings Service = CBN",
            "content": settings_xml,
        },
        {
            "source_file": "data/ir_cron.xml",
            "kind": "xml",
            "reason": "gold: daily CBN cron",
            "content": cron_xml,
        },
        {
            "source_file": "tests/__init__.py",
            "kind": "test",
            "reason": "gold: tests package",
            "content": init_tests,
        },
        {
            "source_file": "tests/test_currency_rate_cbn.py",
            "kind": "test",
            "reason": "gold: inherit field tests",
            "content": test,
        },
    ]
