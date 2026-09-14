"""Option A scaffolds — QWeb report inherit + payment/QR wiring.

Live Apply keeps honest Char stubs. The installable module (sandbox → promote)
ships the report inherit and a host ``_inherit`` that fills payment URL / QR
payload. Domain-agnostic: host-aware inherit targets, no vertical packs.
"""

from __future__ import annotations

import re
from typing import Any

# Stock QWeb document templates (Community public xmlids).
_HOST_REPORT_INHERIT: dict[str, str] = {
    "account.move": "account.report_invoice_document",
    "sale.order": "sale.report_saleorder_document",
    "purchase.order": "purchase.report_purchaseorder_document",
    "stock.picking": "stock.report_deliveryslip",
}

_HOST_MODULE: dict[str, str] = {
    "account.move": "account",
    "sale.order": "sale",
    "purchase.order": "purchase",
    "stock.picking": "stock",
}

_REPORTISH = frozenset({"pdf_report", "qr_on_document", "click_to_pay"})

# Pay/QR/PDF extras belong on a commercial *document*, never diary/HR/CRM chrome.
_COMMERCIAL_DOCUMENT_HOSTS: tuple[str, ...] = (
    "account.move",
    "sale.order",
    "purchase.order",
    "stock.picking",
)
_NEVER_PAY_QR_HOSTS = frozenset(
    {
        "calendar.event",
        "hr.employee",
        "crm.lead",
        "project.task",
        "project.project",
        "res.partner",
        "res.users",
        "mail.message",
        "mail.activity",
    }
)

_INVOICE_INTENT_RE = re.compile(
    r"\b(invoice|retainer|billing|invoicing|paystack|stripe|flutterwave|"
    r"card\s+checkout|customer\s+invoice|accounts?\s+receivable)\b",
    re.I,
)
_QUOTE_INTENT_RE = re.compile(
    r"\b(quotation|quote|sales?\s+order|sales?\s+quotation)\b",
    re.I,
)
_PO_INTENT_RE = re.compile(
    r"\b(purchase\s+order|vendor\s+bill|rfq)\b",
    re.I,
)
_PICKING_INTENT_RE = re.compile(
    r"\b(delivery\s+slip|picking|goods\s+receipt)\b",
    re.I,
)


def host_model_from_draft(draft: dict[str, Any], *, prompt: str = "") -> str:
    """Pick the stock document that should carry Pay/QR/PDF extras.

    Domain-agnostic: prefer invoice/quote/PO/picking already in the spec or
    named in the brief. Never land checkout chrome on calendar.event just
    because it is the first ``mode=inherit`` row in a pack.
    """
    text = (prompt or str(draft.get("_user_prompt") or "")).strip()
    inherit_ids: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if str(model.get("mode") or "new") == "inherit" and mid:
            inherit_ids.append(mid)
    depends = {str(d) for d in (draft.get("depends") or []) if d}
    scores: dict[str, int] = {}

    def bump(host: str, n: int) -> None:
        scores[host] = scores.get(host, 0) + n

    if _INVOICE_INTENT_RE.search(text):
        bump("account.move", 12)
    if _QUOTE_INTENT_RE.search(text):
        bump("sale.order", 8)
    if _PO_INTENT_RE.search(text):
        bump("purchase.order", 8)
    if _PICKING_INTENT_RE.search(text):
        bump("stock.picking", 8)

    for host in _COMMERCIAL_DOCUMENT_HOSTS:
        if host in inherit_ids:
            bump(host, 6)
        mod = _HOST_MODULE.get(host)
        if mod and mod in depends:
            bump(host, 2)

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], _COMMERCIAL_DOCUMENT_HOSTS.index(kv[0]) if kv[0] in _COMMERCIAL_DOCUMENT_HOSTS else 99))
    if ranked and ranked[0][1] > 0:
        return ranked[0][0]
    for host in _COMMERCIAL_DOCUMENT_HOSTS:
        if host in inherit_ids:
            return host
    for mid in inherit_ids:
        if mid not in _NEVER_PAY_QR_HOSTS:
            return mid
    return "account.move"


def _ensure_host_inherit_and_stubs(draft: dict[str, Any], host: str) -> None:
    """Guarantee the commercial host exists as inherit + Pay/QR Char stubs."""
    models = draft.setdefault("models", [])
    row = next(
        (
            m
            for m in models
            if isinstance(m, dict) and str(m.get("model") or "") == host
        ),
        None,
    )
    if row is None:
        row = {
            "model": host,
            "mode": "inherit",
            "inherit": host,
            "description": host,
            "fields": [],
        }
        models.append(row)
    else:
        row.setdefault("mode", "inherit")
        row.setdefault("fields", [])
    existing = {
        str(f.get("name"))
        for f in (row.get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }
    stubs = (
        {
            "name": "x_payment_url",
            "ttype": "char",
            "string": "Payment link",
            "help": "URL for click-to-pay on the PDF (Option A).",
            "widget": "url",
            "source": "capability_gap_stub",
        },
        {
            "name": "x_qr_payload",
            "ttype": "char",
            "string": "QR payload",
            "help": "Raw payload for a report QR. PDF wiring is Option A.",
            "source": "capability_gap_stub",
        },
    )
    for stub in stubs:
        if stub["name"] not in existing:
            row.setdefault("fields", []).append(dict(stub))
            existing.add(stub["name"])
    # Pay/QR stubs never belong on calendar/HR/CRM — strip leftovers.
    for model in models:
        if not isinstance(model, dict):
            continue
        if str(model.get("model") or "") == host:
            continue
        fields = model.get("fields")
        if not isinstance(fields, list):
            continue
        model["fields"] = [
            f
            for f in fields
            if not (
                isinstance(f, dict)
                and str(f.get("name") or "") in {"x_payment_url", "x_qr_payload"}
            )
        ]


def _slug_host(host: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (host or "host").lower()).strip("_") or "host"


def _class_name(host: str) -> str:
    parts = [p for p in host.replace(".", "_").split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts) + "DocumentExtras"


def report_inherit_xml(
    host: str,
    *,
    include_qr: bool,
    include_pay: bool,
) -> str:
    """QWeb inherit: pay CTA + QR on the stock document PDF."""
    inherit_id = _HOST_REPORT_INHERIT.get(host, "")
    slug = _slug_host(host)
    xml_id = f"report_{slug}_document_extras"

    pay_block = ""
    if include_pay:
        pay_block = """
                <div t-if="o.x_payment_url" class="mt-3 mb-2 text-center"
                     style="page-break-inside: avoid;">
                    <a t-att-href="o.x_payment_url"
                       style="display:inline-block;padding:10px 18px;background:#714B67;color:#fff;text-decoration:none;border-radius:4px;font-weight:600;">
                        Pay now
                    </a>
                    <div t-if="o.x_payment_url" class="text-muted mt-1" style="font-size:10px;">
                        <span t-esc="o.x_payment_url"/>
                    </div>
                </div>
"""

    qr_block = ""
    if include_qr:
        # Community /report/barcode supports QR without extra Python deps.
        qr_block = """
                <div t-if="o.x_qr_payload" class="mt-2 text-center"
                     style="page-break-inside: avoid;">
                    <img t-att-src="'/report/barcode/?barcode_type=%s&amp;value=%s&amp;width=%s&amp;height=%s' % ('QR', o.x_qr_payload, 128, 128)"
                         style="width:128px;height:128px;"
                         alt="QR"/>
                    <div class="text-muted" style="font-size:9px;">Scan to open payment link</div>
                </div>
"""

    body = f"{pay_block}{qr_block}".rstrip()
    if not body:
        body = """
                <div class="mt-2 text-muted" style="font-size:10px;">
                    Document extras placeholder — set x_payment_url / x_qr_payload on the record.
                </div>
"""

    if inherit_id:
        return f"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="{xml_id}" inherit_id="{inherit_id}">
        <xpath expr="//div[@id='total']" position="after">
{body}
        </xpath>
    </template>
</odoo>
"""

    return f"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="{xml_id}">
        <t t-call="web.html_container">
            <t t-foreach="docs" t-as="o">
                <div class="page">
                    <h2 t-esc="o.display_name"/>
{body}
                </div>
            </t>
        </t>
    </template>
    <record id="action_{xml_id}" model="ir.actions.report">
        <field name="name">Document extras</field>
        <field name="model">{host}</field>
        <field name="report_type">qweb-pdf</field>
        <field name="report_name">__MODULE__.{xml_id}</field>
        <field name="report_file">__MODULE__.{xml_id}</field>
        <field name="binding_model_id" search="[('model','=','{host}')]"/>
        <field name="binding_type">report</field>
    </record>
</odoo>
"""


def payment_link_python(host: str) -> str:
    """Host inherit: fill x_payment_url / x_qr_payload for the report."""
    cls = _class_name(host)
    if host == "account.move":
        url_inner = '''        if move.move_type not in ("out_invoice", "out_refund"):
            return False
        try:
            return move.get_portal_url()
        except Exception:
            base = base_url or move._pay_qr_base_url()
            return f"{base}/my/invoices/{move.id}" if move.id else False'''
    else:
        url_inner = '''        try:
            if hasattr(move, "get_portal_url"):
                return move.get_portal_url()
        except Exception:
            pass
        base = base_url or move._pay_qr_base_url()
        return f"{base}/web#id={move.id}&model={move._name}" if move.id else False'''

    return f'''# -*- coding: utf-8 -*-
"""Option A — payment link + QR payload for document PDF extras.

Fields x_payment_url / x_qr_payload are expected as Char (live stubs or this
module). Sync fills them from the portal/share URL when empty.
Sandbox-install before promote. Do not enable payment.provider secrets here.
"""
from odoo import api, fields, models


class {cls}(models.Model):
    _inherit = {host!r}

    x_payment_url = fields.Char(
        string="Payment link",
        help="URL for click-to-pay on the PDF (Option A).",
    )
    x_qr_payload = fields.Char(
        string="QR payload",
        help="Payload for report QR (usually the payment URL).",
    )

    def _pay_qr_base_url(self):
        # SUDO-JUSTIFIED: ir.config_parameter is admin-only; public web.base.url, no record ACL bypass.
        return self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""

    def _document_payment_url(self, base_url=""):
        self.ensure_one()
        move = self
{url_inner}

    def _sync_pay_qr_stubs(self):
        # Assign cache (not write-in-loop) — unique portal URLs per record.
        base = self._pay_qr_base_url() if self else ""
        for move in self:
            if "x_payment_url" not in move._fields and "x_qr_payload" not in move._fields:
                continue
            url = move._document_payment_url(base_url=base)
            if "x_payment_url" in move._fields and not move.x_payment_url and url:
                move.x_payment_url = url
            payload = url or (move.display_name if move else False)
            if "x_qr_payload" in move._fields and not move.x_qr_payload and payload:
                move.x_qr_payload = payload
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_pay_qr_stubs()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("skip_pay_qr_sync"):
            self._sync_pay_qr_stubs()
        return res

    def action_refresh_pay_qr_stubs(self):
        """Manual refresh for Print preview after portal is configured."""
        return self._sync_pay_qr_stubs()
'''


def website_controller_python() -> str:
    return '''# -*- coding: utf-8 -*-
"""Option A — website/portal controller skeleton (sandbox → promote)."""
from odoo import http
from odoo.http import request


class DocumentExtrasPortal(http.Controller):
    @http.route(
        ["/document-extras/<int:res_id>/pay"],
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def document_extras_pay(self, res_id, **kwargs):
        # Operator: bind to the correct model + access rules before go-live.
        return request.redirect("/my")
'''


def owl_widget_js() -> str:
    return '''/** @odoo-module **/
/** Option A — OWL field/widget skeleton (sandbox → promote). */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class DocumentExtrasWidget extends Component {
    static template = "document_extras.Widget";
    static props = { "*": true };
}

registry.category("fields").add("document_extras_widget", {
    component: DocumentExtrasWidget,
});
'''


def python_logic_skeleton(host: str) -> str:
    cls = _class_name(host).replace("DocumentExtras", "Logic")
    return f'''# -*- coding: utf-8 -*-
"""Option A — Python compute / constraint skeleton for {host}."""
from odoo import api, models


class {cls}(models.Model):
    _inherit = {host!r}

    # @api.depends("...")
    # def _compute_custom(self):
    #     for rec in self:
    #         rec.x_custom = False
'''


def scaffold_blocks_for_gaps(
    draft: dict[str, Any],
    gap_ids: set[str],
) -> list[dict[str, Any]]:
    """Build installable custom_code_blocks with real content."""
    host = host_model_from_draft(
        draft, prompt=str(draft.get("_user_prompt") or "")
    )
    slug = _slug_host(host)
    blocks: list[dict[str, Any]] = []
    if gap_ids & _REPORTISH or "payment_provider" in gap_ids:
        _ensure_host_inherit_and_stubs(draft, host)

    if gap_ids & _REPORTISH:
        report_path = f"report/{slug}_document_extras.xml"
        py_mod = f"{slug}_document_extras"
        py_path = f"models/{py_mod}.py"

        blocks.append(
            {
                "source_file": report_path,
                "path": report_path,
                "kind": "xml",
                "filename": report_path.split("/")[-1],
                "reason": (
                    "QWeb inherit: Pay now + QR on stock document PDF "
                    "(Option A: module → sandbox → promote)"
                ),
                "source": "capability_gap_scaffold",
                "option_a": True,
                "content": report_inherit_xml(
                    host, include_qr=True, include_pay=True
                ),
            }
        )
        blocks.append(
            {
                "source_file": py_path,
                "path": py_path,
                "kind": "python",
                "filename": py_path.split("/")[-1],
                "model": host,
                "reason": (
                    "Fill x_payment_url / x_qr_payload from portal URL for PDF extras"
                ),
                "source": "capability_gap_scaffold",
                "option_a": True,
                "content": payment_link_python(host),
            }
        )
        blocks.append(
            {
                "source_file": "models/__init__.py",
                "path": "models/__init__.py",
                "kind": "python",
                "filename": "__init__.py",
                "reason": f"Import {py_mod} for Option A document extras",
                "source": "capability_gap_scaffold",
                "option_a": True,
                "content": f"from . import {py_mod}\n",
            }
        )

        dep = _HOST_MODULE.get(host)
        if dep:
            deps = list(draft.get("depends") or ["base"])
            if dep not in deps:
                deps.append(dep)
            draft["depends"] = deps

    if "website_controller" in gap_ids:
        path = "controllers/document_extras_portal.py"
        blocks.append(
            {
                "source_file": path,
                "path": path,
                "kind": "python",
                "filename": "document_extras_portal.py",
                "reason": "Website/portal controller skeleton (Option A)",
                "source": "capability_gap_scaffold",
                "option_a": True,
                "content": website_controller_python(),
            }
        )
        deps = list(draft.get("depends") or ["base"])
        if "website" not in deps:
            deps.append("website")
        draft["depends"] = deps

    if "owl_widget" in gap_ids:
        path = "static/src/document_extras_widget.js"
        blocks.append(
            {
                "source_file": path,
                "path": path,
                "kind": "javascript",
                "filename": "document_extras_widget.js",
                "reason": "OWL widget skeleton (Option A assets)",
                "source": "capability_gap_scaffold",
                "option_a": True,
                "content": owl_widget_js(),
            }
        )

    if "python_logic" in gap_ids and not (gap_ids & _REPORTISH):
        path = f"models/{_slug_host(host)}_logic.py"
        blocks.append(
            {
                "source_file": path,
                "path": path,
                "kind": "python",
                "filename": path.split("/")[-1],
                "model": host,
                "reason": "Python compute/constraint skeleton (Option A)",
                "source": "capability_gap_scaffold",
                "option_a": True,
                "content": python_logic_skeleton(host),
            }
        )

    if "email_template_html" in gap_ids and not (gap_ids & _REPORTISH):
        path = f"data/mail_template_{_slug_host(host)}_extras.xml"
        blocks.append(
            {
                "source_file": path,
                "path": path,
                "kind": "xml",
                "filename": path.split("/")[-1],
                "reason": "Rich mail template skeleton with payment CTA (Option A)",
                "source": "capability_gap_scaffold",
                "option_a": True,
                "content": f"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="mail_template_{_slug_host(host)}_pay" model="mail.template">
        <field name="name">Document pay link</field>
        <field name="model">{host}</field>
        <field name="subject">Payment link for {{{{ object.display_name }}}}</field>
        <field name="body_html" type="html">
            <p>Pay online:</p>
            <p><a t-att-href="object.x_payment_url">Pay now</a></p>
        </field>
    </record>
</odoo>
""",
            }
        )

    if "payment_provider" in gap_ids:
        path = "data/payment_provider_stub.xml"
        blocks.append(
            {
                "source_file": path,
                "path": path,
                "kind": "xml",
                "filename": "payment_provider_stub.xml",
                "reason": (
                    "Payment provider stub (disabled, no secrets) — "
                    "wire keys via Autopilot connectors / human promote"
                ),
                "source": "capability_gap_scaffold",
                "option_a": True,
                "content": """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Domain-agnostic payment surface (Paystack / Stripe / Flutterwave / …).
         Autopilot connectors create a *disabled* payment.provider fixture.
         Never embed live API keys in this zip. Operator pastes keys in Odoo
         before go-live. Pair with reports/*_document_extras.xml for QR / Pay now. -->
    <data noupdate="1">
        <!-- Intentionally empty record set: connector / UI owns provider rows. -->
    </data>
</odoo>
""",
            }
        )
        deps = list(draft.get("depends") or ["base"])
        for dep in ("payment", "account"):
            if dep not in deps:
                deps.append(dep)
        draft["depends"] = deps

    if "webhook_inbound" in gap_ids:
        path = "controllers/webhook_inbound.py"
        blocks.append(
            {
                "source_file": path,
                "path": path,
                "kind": "python",
                "filename": "webhook_inbound.py",
                "reason": "Inbound webhook controller skeleton (Option A)",
                "source": "capability_gap_scaffold",
                "option_a": True,
                "content": '''# -*- coding: utf-8 -*-
"""Option A — inbound webhook skeleton (auth token required before go-live)."""
from odoo import http
from odoo.http import request


class DocumentExtrasWebhook(http.Controller):
    @http.route(
        ["/document-extras/webhook/<string:token>"],
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def document_extras_webhook(self, token, **payload):
        expected = (
            # SUDO-JUSTIFIED: webhook token lives on ir.config_parameter (admin-only ICP).
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("document_extras.webhook_token")
        )
        if not expected or token != expected:
            return {"ok": False, "error": "unauthorized"}
        # Operator: map payload onto stock sale.order / account.move.
        return {"ok": True}
''',
            }
        )

    if "report_paperformat" in gap_ids:
        path = f"report/paperformat_{_slug_host(host)}.xml"
        blocks.append(
            {
                "source_file": path,
                "path": path,
                "kind": "xml",
                "filename": path.split("/")[-1],
                "reason": "Custom paperformat for document PDF (Option A)",
                "source": "capability_gap_scaffold",
                "option_a": True,
                "content": f"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="paperformat_{_slug_host(host)}_extras" model="report.paperformat">
        <field name="name">Document extras paper</field>
        <field name="format">A4</field>
        <field name="orientation">Portrait</field>
        <field name="margin_top">40</field>
        <field name="margin_bottom">32</field>
        <field name="margin_left">7</field>
        <field name="margin_right">7</field>
    </record>
</odoo>
""",
            }
        )

    return blocks


__all__ = [
    "host_model_from_draft",
    "payment_link_python",
    "report_inherit_xml",
    "scaffold_blocks_for_gaps",
]
