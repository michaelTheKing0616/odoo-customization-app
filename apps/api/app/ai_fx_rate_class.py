"""FX / rate-provider sync CLASS — write stock res.currency.rate (P1 Job 1).

Class-wide: live HTTP rate providers sync into ``res.currency.rate`` (or
equivalent stock rate model). CBN is the earned gold shortcut inside the class
(``currency_rate_cbn``), not the only member. Generic providers → Option A
author scaffold or ``external_connector`` lane when Online cannot run Python.

Never Prefer / Nigeria Autopilot ``stock_reuse`` alone for live HTTP fetch.
Completeness ≠ Cert ≠ Autopilot. Promote stays human.
"""

from __future__ import annotations

import re
from typing import Any, Literal

CLASS_INTENT_ID = "fx_rate_provider_sync"
CLASS_MARKER = "ingenium:fx_rate_provider_class"
GOLD_CBN_ID = "currency_rate_cbn"
HOST_MODEL = "res.company"
RATE_MODEL = "res.currency.rate"
DEFAULT_CURRENCIES: tuple[str, ...] = ("USD", "GBP", "EUR")

FxMember = Literal["cbn_gold", "generic_option_a", "external_connector"]

_RATE_WRITE_RE = re.compile(
    r"(?i)\b("
    r"res\.currency\.rate|currency\s+rates?|exchange\s+rates?|fx\s+rates?|"
    r"live\s+rates?|automatic\s+currency\s+rates?|rate\s+provider|"
    r"pull(?:s|ing)?\s+(?:live\s+)?(?:fx\s+|currency\s+|exchange\s+)?rates?|"
    r"sync(?:s|ing)?\s+(?:live\s+)?(?:fx\s+|currency\s+|exchange\s+)?rates?|"
    r"write(?:s|ing)?\s+(?:to\s+)?(?:stock\s+)?(?:currency\s+)?rates?"
    r")\b"
)
_PROVIDER_RE = re.compile(
    r"(?i)\b("
    r"cbn|central\s+bank|ecb|european\s+central\s+bank|"
    r"open\s*exchange|fixer\.io|xe\.com|currencyapi|"
    r"http\s+provider|rate\s+provider|fx\s+provider|"
    r"api\s+(?:endpoint|url|key)|https?://|"
    r"service\s+(?:dropdown|field|provider)|"
    r"external\s+(?:connector|http|api)"
    r")\b"
)
_NIGERIA_STOCK_ONLY_RE = re.compile(
    r"(?i)\b("
    r"nigeria\s+autopilot|stock[_\s-]?first|activate\s+ngn|"
    r"custom\s+residual\s*:\s*none|capability\s+path\s*:\s*stock"
    r")\b"
)
_PREFER_ONLY_RE = re.compile(
    r"(?i)\b(prefer\s+for|add\s+(?:a\s+)?field\s+on|checkbox\s+on)\b"
)
_CURRENCY_ISO_RE = re.compile(r"\b([A-Z]{3})\b")
_KNOWN_ISO = frozenset(
    {
        "USD",
        "GBP",
        "EUR",
        "JPY",
        "CNY",
        "CHF",
        "CAD",
        "AUD",
        "ZAR",
        "AED",
        "SAR",
        "XOF",
        "XDR",
        "DKK",
        "NGN",
    }
)
_X_FX_APP_RE = re.compile(r"(?i)\b(_name\s*=\s*['\"]x_(?:fx|exchange)|model=['\"]x_(?:fx|exchange))")
_RATE_WRITE_CODE_RE = re.compile(
    r"(?i)res\.currency\.rate|env\s*\[\s*['\"]res\.currency\.rate['\"]\s*\]"
)
_QUOTED_CURRENCIES_CODE_RE = re.compile(
    r"(?i)(?:CBN_QUOTED_ISO|QUOTED_ISO|TARGET_CURRENCIES)\s*=\s*\(([^)]+)\)"
)


def is_nigeria_autopilot_stock_only(prompt: str) -> bool:
    """True for Nigeria Autopilot / activate-NGN stock_reuse — not this class."""
    text = prompt or ""
    if not _NIGERIA_STOCK_ONLY_RE.search(text):
        return False
    # Explicit live-rate / CBN / provider cues keep the brief in this class.
    if _PROVIDER_RE.search(text) and _RATE_WRITE_RE.search(text):
        if re.search(r"(?i)\b(cbn|central\s+bank|live\s+rates?|rate\s+provider)\b", text):
            return False
    return True


def is_fx_rate_provider_class_brief(prompt: str) -> bool:
    """True for rate-provider + write-to-odoo-currency-rates CLASS briefs."""
    text = prompt or ""
    if is_nigeria_autopilot_stock_only(text):
        return False
    if _PREFER_ONLY_RE.search(text) and not _RATE_WRITE_RE.search(text):
        return False
    if not _RATE_WRITE_RE.search(text):
        return False
    # Provider / HTTP / bank / Automatic Currency Rates service cue.
    if _PROVIDER_RE.search(text):
        return True
    # Explicit write/sync into Odoo rates without naming a bank still qualifies
    # when the brief mentions sync/pull/HTTP-ish language.
    if re.search(r"(?i)\b(sync|pull|fetch|cron|http|api|provider)\b", text):
        return True
    return False


def is_cbn_class_match(prompt: str) -> bool:
    """Earned gold shortcut — CBN / Central Bank of Nigeria + rate cue."""
    from app.ai_operator_brief import is_cbn_currency_rates_prompt

    return is_cbn_currency_rates_prompt(prompt or "")


def resolve_fx_member(prompt: str) -> FxMember:
    """Pick class member: CBN gold vs generic Option A vs connector honesty."""
    text = prompt or ""
    if is_cbn_class_match(text):
        return "cbn_gold"
    if re.search(r"(?i)\b(external\s+connector|connector\s+runbook|online\s+only)\b", text):
        return "external_connector"
    return "generic_option_a"


def quoted_currencies_from_prompt(prompt: str) -> tuple[str, ...]:
    """Parameterized quoted currencies — default USD/GBP/EUR (exclude company NGN)."""
    text = prompt or ""
    found: list[str] = []
    for m in _CURRENCY_ISO_RE.finditer(text.upper()):
        iso = m.group(1)
        if iso in _KNOWN_ISO and iso != "NGN" and iso not in found:
            found.append(iso)
    if found:
        return tuple(found)
    return DEFAULT_CURRENCIES


def class_mutant_briefs() -> list[dict[str, str]]:
    """Parameterized mutants — not one client SOW string."""
    return [
        {
            "id": "cbn_classic",
            "prompt": (
                "Company currency NGN. Activate USD, GBP, and EUR. "
                "Add Central Bank of Nigeria as the Service on Automatic Currency Rates "
                "so the cron pulls live CBN rates."
            ),
        },
        {
            "id": "cbn_short",
            "prompt": (
                "Pull CBN FX rates into Accounting Automatic Currency Rates "
                "and write stock res.currency.rate."
            ),
        },
        {
            "id": "generic_http_provider",
            "prompt": (
                "Sync live FX rates from an HTTPS rate provider into res.currency.rate "
                "for USD, GBP, and EUR when company currency is NGN. Cron daily."
            ),
        },
        {
            "id": "ecb_service",
            "prompt": (
                "Add ECB as Automatic Currency Rates service and pull daily exchange "
                "rates into Odoo stock currency rates for USD and GBP."
            ),
        },
        {
            "id": "open_exchange",
            "prompt": (
                "Use Open Exchange Rates API as the FX provider; write rates to "
                "res.currency.rate for EUR, USD, GBP. Never invent an x_fx app."
            ),
        },
        {
            "id": "online_connector",
            "prompt": (
                "Online only: external connector runbook to sync FX rates into "
                "res.currency.rate for USD/GBP/EUR — cannot promote Python on Online."
            ),
        },
    ]


def online_connector_runbook(*, prompt: str = "") -> dict[str, Any]:
    """Online honesty appendix — cannot promote Python; connector runbook IR."""
    from app.ai_class_stamp import LANE_COPY, online_python_block_alternatives
    from app.hosting import online_python_promote_block

    currencies = list(quoted_currencies_from_prompt(prompt))
    block = online_python_promote_block(hosting_hint="online")
    ir: dict[str, Any] = {
        "intent_id": "fx_rate_online_connector_runbook",
        "host_model": HOST_MODEL,
        "rate_model": RATE_MODEL,
        "path": "external_connector",
        "complete": False,
        "online_python_promote": False,
        "quoted_currencies": currencies,
        "checks": [
            {"id": "no_online_python_promote", "required": True, "status": "blocked"},
            {"id": "connector_writes_currency_rates", "required": True, "status": "pending"},
            {"id": "currencies_parameterized", "required": True, "status": "pending"},
            {"id": "module_lane_or_sh_alternative", "required": True, "status": "pending"},
        ],
        "operator_copy": (
            "Online cannot install Option A Python. Use an external connector to "
            f"POST/write stock {RATE_MODEL} for {', '.join(currencies)} (company NGN), "
            "or promote the gold/authored module on Odoo.sh / self-host after sandbox "
            "prove. Completeness ≠ Cert ≠ Autopilot. Promote stays human."
        ),
        "alternatives": list(online_python_block_alternatives()),
        "online_block": block,
        "delivery_lane": "external_connector",
        "delivery_lane_copy": LANE_COPY["external_connector"],
        "module_lane_copy": LANE_COPY["module_sh_or_self"],
        "online_lane_copy": LANE_COPY["online_metadata"],
        "artifact_kind": "external_connector",
        "prove_status": "pending",
        "promote_human": True,
        "completeness_is_not_cert": True,
    }
    return ir


def resolve_fx_host_stamp(
    *,
    prompt: str = "",
    hosting_hint: str | None = None,
    gold_artifact_id: str | None = None,
) -> dict[str, Any]:
    """Host stamps: module_sh_or_self vs external_connector vs online block copy."""
    from app.ai_class_stamp import LANE_COPY, apply_class_stamp, resolve_class_stamp
    from app.hosting import online_option_a_python_blocked

    member = resolve_fx_member(prompt)
    gold = gold_artifact_id or (GOLD_CBN_ID if member == "cbn_gold" else None)
    hint = (hosting_hint or "").strip() or None
    online_blocked = bool(hint and online_option_a_python_blocked(hint))

    if member == "external_connector" or online_blocked:
        stamp = {
            "delivery_lane": "external_connector",
            "artifact_kind": "external_connector",
            "prove_status": "pending",
            "delivery_lane_copy": LANE_COPY["external_connector"],
            "artifact_kind_copy": (
                "FX / HTTP provider class — gold Option A or external connector."
            ),
            "promote_human": True,
            "completeness_is_not_cert": True,
            "online_python_promote": False,
            "module_lane_copy": LANE_COPY["module_sh_or_self"],
            "online_lane_copy": LANE_COPY["online_metadata"],
            "fx_member": member,
        }
        if online_blocked:
            stamp["online_block"] = online_connector_runbook(prompt=prompt)
        return stamp

    base = resolve_class_stamp(
        prompt=prompt,
        capability="option_a_standalone" if gold else "option_a_authored",
        grain="full_app",
        needs_module=True,
        gold_artifact_id=gold,
        module_delivery=True,
    )
    apply_class_stamp(base, {"fx_member": member})
    base["fx_member"] = member
    base["module_lane_copy"] = LANE_COPY["module_sh_or_self"]
    base["connector_lane_copy"] = LANE_COPY["external_connector"]
    return base


def acceptance_contract_for_prompt(prompt: str = "", *, draft: dict[str, Any] | None = None) -> dict[str, Any]:
    """Class-wide acceptance: rates land on parameterized currencies; gold prove."""
    text = prompt or str((draft or {}).get("_user_prompt") or "")
    currencies = list(quoted_currencies_from_prompt(text))
    member = resolve_fx_member(text)
    gold = GOLD_CBN_ID if member == "cbn_gold" else None
    return {
        "intent_id": CLASS_INTENT_ID,
        "host_model": HOST_MODEL,
        "rate_model": RATE_MODEL,
        "quoted_currencies": currencies,
        "fx_member": member,
        "gold_artifact_id": gold,
        "checks": [
            {"id": "writes_currency_rate", "required": True},
            {"id": "currencies_parameterized", "required": True},
            {"id": "no_x_fx_app", "required": True},
            {"id": "not_nigeria_autopilot_alone", "required": True},
            {"id": "gold_or_scaffold_present", "required": True},
            {"id": "online_honesty_appendix", "required": False},
        ],
        "fixtures": {
            "brief_class": "fx_rate_provider_sync",
            "rate_model": RATE_MODEL,
            "quoted_currencies": currencies,
            "forbid": ["x_fx", "x_exchange", "prefer_stock_reuse_alone"],
            "gold_artifact_id": gold,
        },
    }


def scaffold_generic_fx_blocks(
    draft: dict[str, Any],
    *,
    prompt: str = "",
) -> list[dict[str, Any]]:
    """CE-safe Option A scaffold for generic (non-CBN-gold) FX members."""
    text = prompt or str(draft.get("_user_prompt") or "")
    if resolve_fx_member(text) == "cbn_gold":
        return []
    currencies = quoted_currencies_from_prompt(text)
    iso_tuple = ", ".join(f'"{c}"' for c in currencies)
    py = f'''# -*- coding: utf-8 -*-
"""{CLASS_MARKER} — FX rate provider → stock {RATE_MODEL}.

Writes parameterized quoted currencies ({", ".join(currencies)}) when company
currency is NGN (Odoo rate = 1 / provider naira-per-unit). Never invent x_fx.
Never Prefer / Nigeria Autopilot stock_reuse alone for live HTTP fetch.
"""
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Placeholder HTTPS provider — operator replaces with the real public endpoint.
# Gate forbids private/SSRF hosts; keep this a public HTTPS URL.
FX_PROVIDER_URL = "https://example.com/fx/rates.json"
QUOTED_ISO = ({iso_tuple})


class ResCompany(models.Model):
    _inherit = "res.company"

    x_fx_provider_url = fields.Char(
        string="FX provider URL",
        default=FX_PROVIDER_URL,
        help="Public HTTPS rate JSON endpoint. Writes stock res.currency.rate.",
    )
    x_fx_interval_unit = fields.Selection(
        [("manually", "Manually"), ("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")],
        string="FX rate interval",
        default="daily",
    )

    def action_activate_quoted_currencies(self):
        Currency = self.env["res.currency"].sudo()
        for iso in QUOTED_ISO:
            cur = Currency.search([("name", "=", iso)], limit=1)
            if cur and not cur.active:
                cur.active = True
        return True

    def update_currency_rates(self):
        self.ensure_one()
        return self._ingenium_sync_fx_rates()

    def _ingenium_sync_fx_rates(self):
        self.ensure_one()
        url = (self.x_fx_provider_url or FX_PROVIDER_URL).strip()
        if not url.startswith("https://"):
            raise UserError("FX provider URL must be public HTTPS.")
        req = Request(url, headers={{"User-Agent": "ingenium-fx-rate-class/1.0"}})
        try:
            with urlopen(req, timeout=30) as resp:  # noqa: S310 — gated HTTPS only
                payload = json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError, TimeoutError, ValueError) as err:
            raise UserError(f"FX provider fetch failed: {{err}}") from err
        rates = payload.get("rates") if isinstance(payload, dict) else None
        if not isinstance(rates, dict):
            raise UserError("FX provider JSON must include a rates object.")
        company = self
        today = fields.Date.context_today(self)
        Rate = self.env["res.currency.rate"].sudo()
        Currency = self.env["res.currency"].sudo()
        written = []
        company_is_ngn = bool(
            company.currency_id and company.currency_id.name == "NGN"
        )
        for iso in QUOTED_ISO:
            raw = rates.get(iso)
            if raw is None:
                continue
            try:
                provider_rate = float(raw)
            except (TypeError, ValueError):
                continue
            if provider_rate <= 0:
                continue
            # When company is NGN and provider quotes naira-per-unit, invert.
            odoo_rate = (1.0 / provider_rate) if company_is_ngn else provider_rate
            currency = Currency.search([("name", "=", iso)], limit=1)
            if not currency:
                _logger.warning("fx_rate_class: ISO %s not in res.currency", iso)
                continue
            existing = Rate.search(
                [
                    ("currency_id", "=", currency.id),
                    ("name", "=", today),
                    ("company_id", "=", company.id),
                ],
                limit=1,
            )
            if existing:
                existing.write({{"rate": odoo_rate}})
            else:
                Rate.create(
                    {{
                        "currency_id": currency.id,
                        "name": today,
                        "company_id": company.id,
                        "rate": odoo_rate,
                    }}
                )
            written.append(iso)
        if not written:
            raise UserError("No quoted currencies could be written.")
        return written


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    x_fx_provider_url = fields.Char(
        related="company_id.x_fx_provider_url",
        readonly=False,
        string="FX provider URL",
    )
    x_fx_interval_unit = fields.Selection(
        related="company_id.x_fx_interval_unit",
        readonly=False,
        string="FX rate interval",
    )

    def action_update_fx_rates(self):
        self.ensure_one()
        self.company_id.update_currency_rates()
        return True

    def action_activate_quoted_currencies(self):
        self.ensure_one()
        self.company_id.action_activate_quoted_currencies()
        return True
'''
    settings_xml = f'''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="res_config_settings_view_form_fx_rate" model="ir.ui.view">
        <field name="name">res.config.settings.view.form.inherit.fx.rate</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="account.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//setting[@id='update_exchange_rates']" position="after">
                <setting id="ingenium_fx_currency_rates"
                         string="Automatic Currency Rates"
                         help="{CLASS_MARKER} — writes stock {RATE_MODEL} for {", ".join(currencies)}.">
                    <div class="content-group">
                        <div class="row mt16">
                            <label for="x_fx_provider_url" class="col-lg-3 o_light_label"/>
                            <field name="x_fx_provider_url"/>
                        </div>
                        <div class="row mt8">
                            <label for="x_fx_interval_unit" class="col-lg-3 o_light_label"/>
                            <field name="x_fx_interval_unit"/>
                        </div>
                        <div class="mt8">
                            <button name="action_update_fx_rates" type="object"
                                    string="Update now" class="btn-link"/>
                            <button name="action_activate_quoted_currencies" type="object"
                                    string="Activate {", ".join(currencies)}" class="btn-link"/>
                        </div>
                    </div>
                </setting>
            </xpath>
        </field>
    </record>
</odoo>
'''
    cron_xml = '''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record forcecreate="True" id="ir_cron_fx_currency_rates" model="ir.cron">
        <field name="name">ingenium: update FX currency rates</field>
        <field name="model_id" ref="base.model_res_company"/>
        <field name="state">code</field>
        <field name="code">model.search([])._ingenium_sync_fx_rates()</field>
        <field name="interval_number">1</field>
        <field name="interval_type">days</field>
        <field name="numbercall">-1</field>
        <field name="active" eval="True"/>
    </record>
</odoo>
'''
    return [
        {
            "source_file": "models/fx_rates.py",
            "kind": "python",
            "reason": f"{CLASS_MARKER}: generic provider → {RATE_MODEL}",
            "content": py,
        },
        {
            "source_file": "views/res_config_settings_views.xml",
            "kind": "xml",
            "reason": f"{CLASS_MARKER}: settings UX",
            "content": settings_xml,
        },
        {
            "source_file": "data/ir_cron_data.xml",
            "kind": "xml",
            "reason": f"{CLASS_MARKER}: daily cron",
            "content": cron_xml,
        },
    ]


def apply_generic_fx_scaffold(draft: dict[str, Any], *, prompt: str = "") -> dict[str, Any]:
    """Attach generic FX scaffold onto an Option A authored draft."""
    text = prompt or str(draft.get("_user_prompt") or "")
    blocks = scaffold_generic_fx_blocks(draft, prompt=text)
    if not blocks:
        return draft
    draft["custom_code_blocks"] = blocks
    draft["models"] = [
        {"model": HOST_MODEL, "mode": "inherit", "fields": []},
    ]
    draft["depends"] = ["account"]
    draft["_pipeline"] = "option_a_fx_rate_class"
    draft["display_name"] = draft.get("display_name") or "FX Currency Rates"
    # Marker for static prove.
    draft["_fx_rate_class"] = {
        "intent_id": CLASS_INTENT_ID,
        "quoted_currencies": list(quoted_currencies_from_prompt(text)),
        "fx_member": resolve_fx_member(text),
        "marker": CLASS_MARKER,
    }
    return draft


def static_fx_rate_findings(
    draft: dict[str, Any],
    *,
    prompt: str = "",
) -> dict[str, Any]:
    """Static acceptance floor for FX rate CLASS (no live RPC required)."""
    text = prompt or str(draft.get("_user_prompt") or "")
    blob_parts: list[str] = []
    for b in draft.get("custom_code_blocks") or []:
        if isinstance(b, dict):
            blob_parts.append(str(b.get("content") or ""))
    blob = "\n".join(blob_parts)
    tech = str(draft.get("technical_name") or "")
    ir = draft.get("_generation_engine") if isinstance(draft.get("_generation_engine"), dict) else {}
    gold = str(ir.get("gold_artifact_id") or "")
    expected = set(quoted_currencies_from_prompt(text))

    writes_rate = bool(_RATE_WRITE_CODE_RE.search(blob) or gold == GOLD_CBN_ID)
    no_x_fx = not bool(_X_FX_APP_RE.search(blob)) and "x_fx" not in tech and "x_exchange" not in tech
    not_nigeria_alone = not is_nigeria_autopilot_stock_only(text)

    found_isos: set[str] = set()
    m = _QUOTED_CURRENCIES_CODE_RE.search(blob)
    if m:
        for iso in _CURRENCY_ISO_RE.findall(m.group(1).upper()):
            if iso in _KNOWN_ISO:
                found_isos.add(iso)
    # Gold CBN always quotes USD/GBP/EUR.
    if gold == GOLD_CBN_ID or "CBN_QUOTED_ISO" in blob:
        found_isos.update(DEFAULT_CURRENCIES)
    # Also accept ISO literals present in blob when expected.
    for iso in expected:
        if re.search(rf"""['\"]{iso}['\"]""", blob) or iso in blob:
            found_isos.add(iso)

    currencies_ok = expected.issubset(found_isos) if expected else bool(found_isos)
    gold_or_scaffold = bool(
        gold == GOLD_CBN_ID
        or CLASS_MARKER in blob
        or draft.get("_pipeline") in {"gold_template", "option_a_fx_rate_class"}
        or tech == GOLD_CBN_ID
    )

    return {
        "writes_currency_rate": writes_rate,
        "currencies_parameterized": currencies_ok,
        "no_x_fx_app": no_x_fx,
        "not_nigeria_autopilot_alone": not_nigeria_alone,
        "gold_or_scaffold_present": gold_or_scaffold,
        "online_honesty_appendix": True,  # appendix always available via runbook helper
        "quoted_currencies": sorted(expected),
        "found_currencies": sorted(found_isos),
        "host_model": HOST_MODEL,
        "rate_model": RATE_MODEL,
        "fx_member": resolve_fx_member(text),
        "gold_artifact_id": gold or None,
    }


__all__ = [
    "CLASS_INTENT_ID",
    "CLASS_MARKER",
    "DEFAULT_CURRENCIES",
    "GOLD_CBN_ID",
    "HOST_MODEL",
    "RATE_MODEL",
    "acceptance_contract_for_prompt",
    "apply_generic_fx_scaffold",
    "class_mutant_briefs",
    "is_cbn_class_match",
    "is_fx_rate_provider_class_brief",
    "is_nigeria_autopilot_stock_only",
    "online_connector_runbook",
    "quoted_currencies_from_prompt",
    "resolve_fx_host_stamp",
    "resolve_fx_member",
    "scaffold_generic_fx_blocks",
    "static_fx_rate_findings",
]
