"""Map missing inherit models to stock Community apps the operator can install.

Option A modules inherit ``sale.order`` / ``account.move`` — they do not create those
models. When the connected Odoo lacks the host app, offer to install the CE module.
That write is not Live Apply of the authored zip. Promote stays human.
"""

from __future__ import annotations

import re
from typing import Any

# model → (technical module, operator label). Line models share the parent app.
HOST_APPS: dict[str, tuple[str, str]] = {
    "sale.order": ("sale", "Sales"),
    "sale.order.line": ("sale", "Sales"),
    "account.move": ("account", "Invoicing"),
    "account.move.line": ("account", "Invoicing"),
    "purchase.order": ("purchase", "Purchase"),
    "purchase.order.line": ("purchase", "Purchase"),
    "stock.picking": ("stock", "Inventory"),
    "stock.move": ("stock", "Inventory"),
    "stock.quant": ("stock", "Inventory"),
    "stock.warehouse": ("stock", "Inventory"),
    "product.product": ("product", "Products"),
    "product.template": ("product", "Products"),
    "crm.lead": ("crm", "CRM"),
    "project.project": ("project", "Project"),
    "project.task": ("project", "Project"),
    "hr.employee": ("hr", "Employees"),
    "hr.expense": ("hr_expense", "Expenses"),
    "calendar.event": ("calendar", "Calendar"),
    "account.analytic.line": ("hr_timesheet", "Timesheets"),
    "mrp.production": ("mrp", "Manufacturing"),
    "mrp.bom": ("mrp", "Manufacturing"),
    "pos.order": ("point_of_sale", "Point of Sale"),
    "pos.config": ("point_of_sale", "Point of Sale"),
    "point_of_sale.order": ("point_of_sale", "Point of Sale"),
    "uom.uom": ("uom", "Units of Measure"),
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
        "ir.attachment",
        "ir.model",
        "mail.thread",
        "mail.activity.mixin",
    }
)

_INHERIT_MSG_RE = re.compile(r"Inherit model\s+(\S+)\s+is not", re.I)


def model_from_finding(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    raw = str(row.get("model") or "").strip()
    if raw:
        return raw
    match = _INHERIT_MSG_RE.search(str(row.get("message") or ""))
    return match.group(1).rstrip(".") if match else ""


def community_app_for_model(model: str | None) -> dict[str, str] | None:
    """Return ``{module, label}`` for a stock CE host, or None if we must not offer install."""
    mid = (model or "").strip()
    if not mid or mid.startswith("x_") or mid in _ALWAYS_PRESENT:
        return None
    hit = HOST_APPS.get(mid)
    if not hit:
        return None
    module, label = hit
    if module in {"base", "web", "mail"}:
        return None
    return {"module": module, "label": label}


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
