"""Map missing inherit models to stock Community apps the operator can install.

Option A modules inherit ``sale.order`` / ``account.move`` / ``stock.picking`` —
they do not create those models. When the connected Odoo lacks the host app, offer
to install the CE module. That write is not Live Apply of the authored zip.
Promote stays human.

Coverage: Odoo Community stock apps operators commonly inherit. Models not listed
fall back to the first dotted segment when it matches a known CE module label
(e.g. ``fleet.vehicle`` → Fleet). Always-present ``base`` / ``mail`` / ``res.*``
hosts never get an Install CTA.
"""

from __future__ import annotations

import re
from typing import Any

# Technical module → operator-facing Apps label (Community).
MODULE_LABELS: dict[str, str] = {
    "sale": "Sales",
    "sale_management": "Sales",
    "account": "Invoicing",
    "purchase": "Purchase",
    "stock": "Inventory",
    "product": "Products",
    "crm": "CRM",
    "project": "Project",
    "hr": "Employees",
    "hr_expense": "Expenses",
    "hr_attendance": "Attendances",
    "hr_holidays": "Time Off",
    "hr_recruitment": "Recruitment",
    "hr_timesheet": "Timesheets",
    "hr_contract": "Contracts",
    "calendar": "Calendar",
    "mrp": "Manufacturing",
    "point_of_sale": "Point of Sale",
    "pos_restaurant": "Restaurant",
    "uom": "Units of Measure",
    "contacts": "Contacts",
    "website": "Website",
    "website_sale": "eCommerce",
    "website_blog": "Blog",
    "website_slides": "eLearning",
    "website_event": "Events",
    "website_forum": "Forum",
    "mass_mailing": "Email Marketing",
    "mass_mailing_sms": "SMS Marketing",
    "survey": "Surveys",
    "fleet": "Fleet",
    "maintenance": "Maintenance",
    "repair": "Repairs",
    "quality_control": "Quality",
    "lunch": "Lunch",
    "im_livechat": "Live Chat",
    "board": "Dashboards",
    "gamification": "Gamification",
    "event": "Events",
    "event_sale": "Events",
    "planning": "Planning",
    "industry_fsm": "Field Service",
    "helpdesk": "Helpdesk",  # CE may omit; still useful if present on the instance
    "knowledge": "Knowledge",
    "approvals": "Approvals",
    "documents": "Documents",
    "barcodes": "Barcode",
    "stock_barcode": "Barcode",
    "delivery": "Delivery Methods",
    "stock_delivery": "Delivery Methods",
    "stock_account": "Inventory",
    "sale_stock": "Sales",
    "sale_purchase": "Sales",
    "purchase_stock": "Purchase",
    "account_payment": "Invoicing",
    "payment": "Payment Providers",
    "l10n_us": "US Localization",
    "l10n_uk": "UK Localization",
    "l10n_ng": "Nigeria Localization",
    "analytic": "Analytics",
    "base_automation": "Automation",
    "sms": "SMS",
    "voip": "VoIP",
    "whatsapp": "WhatsApp",
}

# Explicit model → (module, label). Line / child models share the parent app.
# Prefer this over the dotted-prefix fallback for ambiguous names (pos.* → point_of_sale).
HOST_APPS: dict[str, tuple[str, str]] = {
    # Sales
    "sale.order": ("sale", "Sales"),
    "sale.order.line": ("sale", "Sales"),
    "sale.report": ("sale", "Sales"),
    # Invoicing / Accounting CE
    "account.move": ("account", "Invoicing"),
    "account.move.line": ("account", "Invoicing"),
    "account.payment": ("account", "Invoicing"),
    "account.payment.method": ("account", "Invoicing"),
    "account.journal": ("account", "Invoicing"),
    "account.account": ("account", "Invoicing"),
    "account.tax": ("account", "Invoicing"),
    "account.fiscal.position": ("account", "Invoicing"),
    "account.partial.reconcile": ("account", "Invoicing"),
    "account.bank.statement": ("account", "Invoicing"),
    "account.bank.statement.line": ("account", "Invoicing"),
    "account.analytic.account": ("analytic", "Analytics"),
    "account.analytic.line": ("hr_timesheet", "Timesheets"),
    # Purchase
    "purchase.order": ("purchase", "Purchase"),
    "purchase.order.line": ("purchase", "Purchase"),
    "purchase.requisition": ("purchase", "Purchase"),
    # Inventory / Stock / Delivery
    "stock.picking": ("stock", "Inventory"),
    "stock.picking.type": ("stock", "Inventory"),
    "stock.move": ("stock", "Inventory"),
    "stock.move.line": ("stock", "Inventory"),
    "stock.quant": ("stock", "Inventory"),
    "stock.warehouse": ("stock", "Inventory"),
    "stock.location": ("stock", "Inventory"),
    "stock.lot": ("stock", "Inventory"),
    "stock.package": ("stock", "Inventory"),
    "stock.rule": ("stock", "Inventory"),
    "stock.route": ("stock", "Inventory"),
    "stock.scrap": ("stock", "Inventory"),
    "stock.valuation.layer": ("stock_account", "Inventory"),
    "delivery.carrier": ("delivery", "Delivery Methods"),
    # Products
    "product.product": ("product", "Products"),
    "product.template": ("product", "Products"),
    "product.category": ("product", "Products"),
    "product.pricelist": ("product", "Products"),
    "product.supplierinfo": ("product", "Products"),
    "product.attribute": ("product", "Products"),
    "product.packaging": ("product", "Products"),
    "uom.uom": ("uom", "Units of Measure"),
    "uom.category": ("uom", "Units of Measure"),
    # CRM
    "crm.lead": ("crm", "CRM"),
    "crm.team": ("crm", "CRM"),
    "crm.stage": ("crm", "CRM"),
    "crm.tag": ("crm", "CRM"),
    # Project
    "project.project": ("project", "Project"),
    "project.task": ("project", "Project"),
    "project.task.type": ("project", "Project"),
    # HR family
    "hr.employee": ("hr", "Employees"),
    "hr.department": ("hr", "Employees"),
    "hr.job": ("hr", "Employees"),
    "hr.expense": ("hr_expense", "Expenses"),
    "hr.expense.sheet": ("hr_expense", "Expenses"),
    "hr.attendance": ("hr_attendance", "Attendances"),
    "hr.leave": ("hr_holidays", "Time Off"),
    "hr.leave.type": ("hr_holidays", "Time Off"),
    "hr.applicant": ("hr_recruitment", "Recruitment"),
    "hr.contract": ("hr_contract", "Contracts"),
    # Calendar / Discuss extras (mail itself is always present)
    "calendar.event": ("calendar", "Calendar"),
    "calendar.alarm": ("calendar", "Calendar"),
    # Manufacturing / Repair / Maintenance / Quality
    "mrp.production": ("mrp", "Manufacturing"),
    "mrp.bom": ("mrp", "Manufacturing"),
    "mrp.bom.line": ("mrp", "Manufacturing"),
    "mrp.workorder": ("mrp", "Manufacturing"),
    "mrp.workcenter": ("mrp", "Manufacturing"),
    "repair.order": ("repair", "Repairs"),
    "maintenance.request": ("maintenance", "Maintenance"),
    "maintenance.equipment": ("maintenance", "Maintenance"),
    "quality.check": ("quality_control", "Quality"),
    "quality.point": ("quality_control", "Quality"),
    # Point of Sale (technical models use pos.*, module is point_of_sale)
    "pos.order": ("point_of_sale", "Point of Sale"),
    "pos.order.line": ("point_of_sale", "Point of Sale"),
    "pos.config": ("point_of_sale", "Point of Sale"),
    "pos.session": ("point_of_sale", "Point of Sale"),
    "pos.payment": ("point_of_sale", "Point of Sale"),
    "pos.payment.method": ("point_of_sale", "Point of Sale"),
    "pos.category": ("point_of_sale", "Point of Sale"),
    "restaurant.table": ("pos_restaurant", "Restaurant"),
    "restaurant.floor": ("pos_restaurant", "Restaurant"),
    # Website / eCommerce
    "website": ("website", "Website"),
    "website.page": ("website", "Website"),
    "website.menu": ("website", "Website"),
    "blog.post": ("website_blog", "Blog"),
    "blog.blog": ("website_blog", "Blog"),
    "slide.channel": ("website_slides", "eLearning"),
    "slide.slide": ("website_slides", "eLearning"),
    "forum.forum": ("website_forum", "Forum"),
    "forum.post": ("website_forum", "Forum"),
    # Marketing / Surveys / Events
    "mailing.mailing": ("mass_mailing", "Email Marketing"),
    "mailing.contact": ("mass_mailing", "Email Marketing"),
    "sms.sms": ("sms", "SMS"),
    "survey.survey": ("survey", "Surveys"),
    "survey.user_input": ("survey", "Surveys"),
    "event.event": ("event", "Events"),
    "event.registration": ("event", "Events"),
    # Fleet / Lunch / Live chat
    "fleet.vehicle": ("fleet", "Fleet"),
    "fleet.vehicle.log.services": ("fleet", "Fleet"),
    "lunch.product": ("lunch", "Lunch"),
    "lunch.order": ("lunch", "Lunch"),
    "im_livechat.channel": ("im_livechat", "Live Chat"),
    # Payments (acquirers — secrets stay operator-pasted)
    "payment.provider": ("payment", "Payment Providers"),
    "payment.transaction": ("payment", "Payment Providers"),
}

# Prefix overrides when the first dotted segment is not the installable module name.
_PREFIX_MODULE: dict[str, str] = {
    "pos": "point_of_sale",
    "restaurant": "pos_restaurant",
    "blog": "website_blog",
    "slide": "website_slides",
    "forum": "website_forum",
    "mailing": "mass_mailing",
    "event": "event",
    "fleet": "fleet",
    "lunch": "lunch",
    "survey": "survey",
    "repair": "repair",
    "maintenance": "maintenance",
    "quality": "quality_control",
    "delivery": "delivery",
    "payment": "payment",
    "website": "website",
    "project": "project",
    "crm": "crm",
    "sale": "sale",
    "purchase": "purchase",
    "stock": "stock",
    "product": "product",
    "account": "account",
    "mrp": "mrp",
    "hr": "hr",
    "calendar": "calendar",
    "uom": "uom",
    "analytic": "analytic",
}

_ALWAYS_PRESENT = frozenset(
    {
        "base",
        "web",
        "mail",
        "res.partner",
        "res.users",
        "res.company",
        "res.currency",
        "res.country",
        "res.country.state",
        "res.lang",
        "res.bank",
        "ir.attachment",
        "ir.model",
        "ir.model.fields",
        "ir.ui.view",
        "ir.ui.menu",
        "ir.actions.act_window",
        "ir.actions.report",
        "ir.sequence",
        "ir.cron",
        "ir.rule",
        "ir.config_parameter",
        "mail.thread",
        "mail.activity.mixin",
        "mail.message",
        "mail.activity",
        "mail.channel",
    }
)

_ALWAYS_PRESENT_PREFIXES = frozenset({"base", "web", "mail", "ir", "res"})

_INHERIT_MSG_RE = re.compile(r"Inherit model\s+(\S+)\s+is not", re.I)


def model_from_finding(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    raw = str(row.get("model") or "").strip()
    if raw:
        return raw
    match = _INHERIT_MSG_RE.search(str(row.get("message") or ""))
    return match.group(1).rstrip(".") if match else ""


def _label_for_module(module: str) -> str:
    return MODULE_LABELS.get(module) or module.replace("_", " ").title()


def community_app_for_model(model: str | None) -> dict[str, str] | None:
    """Return ``{module, label}`` for a stock CE host, or None if we must not offer install."""
    mid = (model or "").strip()
    if not mid or mid.startswith("x_") or mid in _ALWAYS_PRESENT:
        return None
    hit = HOST_APPS.get(mid)
    if hit:
        module, label = hit
        if module in {"base", "web", "mail"}:
            return None
        return {"module": module, "label": label}

    prefix = mid.split(".", 1)[0].strip().lower()
    if not prefix or prefix in _ALWAYS_PRESENT_PREFIXES:
        return None
    module = _PREFIX_MODULE.get(prefix, prefix)
    if module in {"base", "web", "mail"}:
        return None
    if module not in MODULE_LABELS and prefix not in _PREFIX_MODULE:
        # Unknown CE/enterprise tease — still offer when the prefix looks like a module
        # technical name (snake_case), so new hosts get an Install CTA without a code edit.
        if not re.fullmatch(r"[a-z][a-z0-9_]*", module):
            return None
    return {"module": module, "label": _label_for_module(module)}


def enrich_model_missing_finding(row: dict[str, Any], model: str) -> dict[str, Any]:
    out = dict(row)
    out["model"] = model
    app = community_app_for_model(model)
    if app:
        out["install_module"] = app["module"]
        out["install_label"] = app["label"]
    return out


def host_install_offers(findings: list[Any] | None) -> list[dict[str, Any]]:
    """Group ``model_missing`` findings into one install offer per Community app."""
    grouped: dict[str, dict[str, Any]] = {}
    for row in findings or []:
        if not isinstance(row, dict) or str(row.get("code") or "") != "model_missing":
            continue
        model = model_from_finding(row)
        app = community_app_for_model(model)
        if not app:
            continue
        key = app["module"]
        bucket = grouped.setdefault(
            key,
            {
                "module": app["module"],
                "label": app["label"],
                "models": [],
            },
        )
        if model not in bucket["models"]:
            bucket["models"].append(model)

    offers: list[dict[str, Any]] = []
    for bucket in grouped.values():
        models: list[str] = list(bucket["models"])
        label = str(bucket["label"])
        module = str(bucket["module"])
        listed = ", ".join(models)
        bucket["message"] = (
            f"This Option A module inherits {listed}. Those models come from the stock "
            f"{label} app ({module}). Install {label} on this connection so the authoring "
            "gate can verify the inherit. That does not install this custom zip — "
            "Promote stays human."
        )
        offers.append(bucket)
    return offers
