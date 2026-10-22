"""Demo Co-Pilot honesty labels from real Odoo lookups on the connected demo database.

Code decides the label; the model only proposes which app answers the question.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

logger = logging.getLogger(__name__)

IN_DEMO = "In your demo"
NOT_SET_UP = "Standard Odoo, not set up yet"
CUSTOM = "Possible with customisation"
NOT_AVAILABLE = "Not available"

APP_MODULES: dict[str, str] = {
    "inventory": "stock", "sales": "sale_management", "sale": "sale_management", "crm": "crm",
    "accounting": "account", "invoicing": "account", "purchase": "purchase", "manufacturing": "mrp",
    "mrp": "mrp", "project": "project", "helpdesk": "helpdesk", "employees": "hr", "hr": "hr",
    "payroll": "hr_payroll", "point of sale": "point_of_sale", "pos": "point_of_sale", "website": "website",
    "ecommerce": "website_sale", "timesheets": "hr_timesheet", "fleet": "fleet", "maintenance": "maintenance",
    "contacts": "contacts", "expenses": "hr_expense", "recruitment": "hr_recruitment", "time off": "hr_holidays",
    "subscriptions": "sale_subscription", "rental": "sale_renting", "documents": "documents", "sign": "sign",
    "email marketing": "mass_mailing", "events": "event", "elearning": "website_slides",
    "quality": "quality_control", "plm": "mrp_plm", "field service": "industry_fsm", "knowledge": "knowledge",
    "appraisals": "hr_appraisal", "attendances": "hr_attendance", "lunch": "lunch", "surveys": "survey",
    "survey": "survey", "discuss": "mail", "calendar": "calendar", "repairs": "repair", "planning": "planning",
    "approvals": "approvals", "spreadsheet": "spreadsheet_dashboard", "marketing automation": "marketing_automation",
}


def module_for(app: str | None) -> str | None:
    if not app:
        return None
    a = app.strip().lower()
    if re.fullmatch(r"[a-z0-9_]+", a) and "_" in a:
        return a
    return APP_MODULES.get(a, a if re.fullmatch(r"[a-z0-9_]+", a) else None)


def installed_modules(db: Any, connection_id: str | None) -> set[str] | None:
    """Installed module names on the demo DB (cached 5 min per DB). None when unreachable."""
    if not connection_id or db is None:
        return None
    from app.ai_client.ai_cache import subresult
    from app.odoo_service import client_from_connection, get_connection_or_404

    def _read() -> list[str]:
        client = client_from_connection(get_connection_or_404(db, connection_id), db=db)
        rows = client.execute_kw("ir.module.module", "search_read",
                                 [[("state", "=", "installed")]], {"fields": ["name"]})
        return sorted(r["name"] for r in rows)

    try:
        return set(subresult(connection_id, "installed_modules", "v1", _read, ttl_s=300))
    except Exception as exc:  # noqa: BLE001
        logger.info("demo grounding lookup failed for %s: %s", connection_id, exc)
        return None


def demo_label(verdict: str, app: str | None, installed: set[str] | None) -> str | None:
    """Label from verdict + real install state. None when there is no database to check."""
    from app.live_demo_copilot.stage2_answer import (CUSTOMIZATION, NOT_SURE, STOCK_COMMUNITY,
                                                     STOCK_ENTERPRISE_ONLY, STOCK_ONCE_INSTALLED)
    if verdict == CUSTOMIZATION:
        return CUSTOM
    if verdict == NOT_SURE:
        return None
    if installed is None:
        return NOT_SET_UP if verdict in {STOCK_COMMUNITY, STOCK_ONCE_INSTALLED, STOCK_ENTERPRISE_ONLY} else None
    mod = module_for(app)
    if mod and mod in installed:
        return IN_DEMO
    if verdict == STOCK_ENTERPRISE_ONLY and "web_enterprise" not in installed:
        return NOT_AVAILABLE
    return NOT_SET_UP


def claim_verifier(installed: set[str] | None) -> Callable[[str], bool]:
    """For free-text answers: a sentence claiming something is in the demo must name an
    app/module that is actually installed."""
    def _check(sentence: str) -> bool:
        if not installed:
            return False
        low = sentence.lower()
        for name, mod in APP_MODULES.items():
            if re.search(rf"\b{re.escape(name)}\b", low) and mod in installed:
                return True
        return any(re.search(rf"\b{re.escape(m)}\b", low) for m in installed if "_" in m)
    return _check
