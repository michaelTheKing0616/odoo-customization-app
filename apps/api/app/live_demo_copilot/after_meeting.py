"""Q7: after-meeting pack — summary, Q&A, a follow-up email draft (never sent) and a starter plan.

Built only from what the Co-Pilot already stored and checked (grounded answers with citations), so
it adds no new claims. Declined or unsure answers are listed as "to confirm", never as facts.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.ai_client.guards import Redactor

# Odoo app keywords -> app name, for the starter plan.
APPS = {
    "invoice": "Invoicing", "bill": "Invoicing", "payment": "Invoicing", "tax": "Invoicing", "vat": "Invoicing",
    "quote": "Sales", "quotation": "Sales", "sales order": "Sales", "deposit": "Sales", "price": "Sales",
    "stock": "Inventory", "inventory": "Inventory", "warehouse": "Inventory", "delivery": "Inventory",
    "purchase": "Purchase", "vendor": "Purchase", "supplier": "Purchase",
    "lead": "CRM", "pipeline": "CRM", "opportunit": "CRM",
    "employee": "Employees", "payroll": "Payroll", "leave": "Time Off", "timesheet": "Timesheets",
    "project": "Project", "task": "Project", "manufactur": "Manufacturing", "bom": "Manufacturing",
    "website": "Website", "shop": "eCommerce", "pos": "Point of Sale", "point of sale": "Point of Sale",
    "rental": "Rental", "helpdesk": "Helpdesk", "ticket": "Helpdesk", "subscription": "Subscriptions",
}


def _apps_for(text: str) -> list[str]:
    t = (text or "").lower()
    return sorted({app for k, app in APPS.items() if re.search(rf"\b{re.escape(k)}", t)})


def build_after_meeting(answers: list[dict[str, Any]], transcript_lines: int, *, presenter: str = "") -> dict[str, Any]:
    red = Redactor()
    answered = [a for a in answers if a.get("grounded") and not a.get("declined") and a.get("bullets")]
    to_confirm = [a for a in answers if a not in answered]
    qa = [
        {
            "question": red.redact(a.get("question") or ""),
            "asked_by": a.get("speaker_name"),
            "answer": [red.redact(str(b)) for b in a.get("bullets") or []],
            "sources": a.get("citations") or [],
            "confidence": a.get("confidence_flag"),
        }
        for a in reversed(answered)
    ]
    apps = Counter(app for a in answers for app in _apps_for(a.get("question") or ""))
    plan = [
        {"step": i + 1, "app": app, "why": f"Came up {n} time{'s' if n > 1 else ''} in the meeting."}
        for i, (app, n) in enumerate(apps.most_common(6))
    ]
    open_qs = [red.redact(a.get("question") or "") for a in reversed(to_confirm) if a.get("question")]
    summary = (
        f"{len(answers)} Odoo question{'s' if len(answers) != 1 else ''} came up over {transcript_lines} transcript lines; "
        f"{len(answered)} answered from checked sources, {len(open_qs)} to confirm."
    )
    lines = ["Hello,", "", "Thank you for your time today. Here is what we covered.", ""]
    for item in qa[:8]:
        lines.append(f"\u2022 {item['question']}")
        lines.extend(f"    {b}" for b in item["answer"][:3])
    if open_qs:
        lines += ["", "We will come back to you on:"] + [f"\u2022 {q}" for q in open_qs[:8]]
    if plan:
        lines += ["", "A suggested starting point: " + ", then ".join(p["app"] for p in plan) + "."]
    lines += ["", "Kind regards,", presenter or ""]
    return {
        "summary": summary,
        "qa": qa,
        "to_confirm": open_qs,
        "starter_plan": plan,
        "follow_up_email": {"subject": "Follow-up from today\u2019s Odoo demo", "body": "\n".join(lines).rstrip(), "sent": False},
        "note": "This is a draft. Ingenium never sends it for you.",
    }
