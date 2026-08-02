"""Gold ModuleSpec shape for a comprehensive law-firm ops app (reference / tests).

Selections for taxonomy; substantive models for the operational loop. Not a domain pack —
documents what depth-first generation should aim for on world-class prompts.
"""

from __future__ import annotations

from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def law_firm_gold_spec() -> dict[str, Any]:
    practice = _sel(
        ("litigation", "Litigation"),
        ("corporate", "Corporate"),
        ("ip", "Intellectual Property"),
        ("employment", "Employment"),
        ("real_estate", "Real Estate"),
        ("family", "Family"),
        ("criminal", "Criminal"),
        ("tax", "Tax"),
        ("other", "Other"),
    )
    matter_status = _sel(
        ("intake", "Intake"),
        ("conflict_check", "Conflict check"),
        ("open", "Open"),
        ("discovery", "Discovery"),
        ("trial", "Trial / Hearing"),
        ("settlement", "Settlement"),
        ("closed", "Closed"),
        ("on_hold", "On hold"),
    )
    priority = _sel(("low", "Low"), ("normal", "Normal"), ("high", "High"), ("critical", "Critical"))
    party_role = _sel(
        ("client", "Client"),
        ("opposing", "Opposing party"),
        ("opposing_counsel", "Opposing counsel"),
        ("witness", "Witness"),
        ("expert", "Expert"),
        ("court", "Court / Tribunal"),
        ("other", "Other"),
    )
    time_status = _sel(
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("billed", "Billed"),
        ("written_off", "Written off"),
    )
    bill_status = _sel(
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("partial", "Partially paid"),
        ("paid", "Paid"),
        ("void", "Void"),
    )
    task_status = _sel(
        ("todo", "To do"),
        ("in_progress", "In progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    )
    hearing_status = _sel(
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("adjourned", "Adjourned"),
        ("cancelled", "Cancelled"),
    )
    trust_status = _sel(
        ("held", "Held"),
        ("applied", "Applied to fees"),
        ("refunded", "Refunded"),
    )

    return {
        "technical_name": "law_firm_management",
        "display_name": "Law Firm Management",
        "depends": ["base", "contacts", "mail"],
        "models": [
            {
                "model": "x_lf_attorney",
                "description": "Attorney / Fee Earner",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Contact",
                        "relation": "res.partner",
                    },
                    {
                        "name": "x_user_id",
                        "ttype": "many2one",
                        "string": "Login User",
                        "relation": "res.users",
                    },
                    {
                        "name": "x_practice_area",
                        "ttype": "selection",
                        "string": "Practice Area",
                        "selection": practice,
                    },
                    {"name": "x_bar_number", "ttype": "char", "string": "Bar / License No."},
                    {"name": "x_hourly_rate", "ttype": "float", "string": "Default Hourly Rate"},
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "string": "Currency",
                        "relation": "res.currency",
                    },
                    {"name": "x_active", "ttype": "boolean", "string": "Active"},
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "string": "Company",
                        "relation": "res.company",
                    },
                ],
            },
            {
                "model": "x_lf_matter",
                "description": "Matter / Case",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Matter Title", "required": True},
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "string": "Matter No.",
                        "help": "Matter reference — wire ir.sequence (e.g. MTR/00001)",
                    },
                    {
                        "name": "x_client_id",
                        "ttype": "many2one",
                        "string": "Primary Client",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {
                        "name": "x_responsible_id",
                        "ttype": "many2one",
                        "string": "Responsible Attorney",
                        "relation": "x_lf_attorney",
                        "required": True,
                    },
                    {
                        "name": "x_practice_area",
                        "ttype": "selection",
                        "string": "Practice Area",
                        "selection": practice,
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": matter_status,
                        "required": True,
                    },
                    {
                        "name": "x_priority",
                        "ttype": "selection",
                        "string": "Priority",
                        "selection": priority,
                    },
                    {"name": "x_open_date", "ttype": "date", "string": "Opened"},
                    {"name": "x_close_date", "ttype": "date", "string": "Closed"},
                    {"name": "x_limitation_date", "ttype": "date", "string": "Limitation / Deadline"},
                    {"name": "x_court", "ttype": "char", "string": "Court / Forum"},
                    {"name": "x_docket", "ttype": "char", "string": "Docket / File No."},
                    {"name": "x_description", "ttype": "text", "string": "Synopsis"},
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "string": "Company",
                        "relation": "res.company",
                    },
                ],
            },
            {
                "model": "x_lf_matter_party",
                "description": "Matter Party / Role",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Label", "required": True},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "string": "Matter",
                        "relation": "x_lf_matter",
                        "required": True,
                    },
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Party Contact",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {
                        "name": "x_role",
                        "ttype": "selection",
                        "string": "Role",
                        "selection": party_role,
                        "required": True,
                    },
                    {"name": "x_notes", "ttype": "char", "string": "Notes"},
                ],
            },
            {
                "model": "x_lf_time_entry",
                "description": "Time Entry (Billable)",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Narrative", "required": True},
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "string": "Reference",
                        "help": "Time entry ref — wire ir.sequence (e.g. TE/00001)",
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "string": "Matter",
                        "relation": "x_lf_matter",
                        "required": True,
                    },
                    {
                        "name": "x_attorney_id",
                        "ttype": "many2one",
                        "string": "Fee Earner",
                        "relation": "x_lf_attorney",
                        "required": True,
                    },
                    {"name": "x_date", "ttype": "date", "string": "Work Date", "required": True},
                    {"name": "x_hours", "ttype": "float", "string": "Hours", "required": True},
                    {"name": "x_rate", "ttype": "float", "string": "Rate"},
                    {"name": "x_amount", "ttype": "float", "string": "Amount"},
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "string": "Currency",
                        "relation": "res.currency",
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": time_status,
                        "required": True,
                    },
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "string": "Company",
                        "relation": "res.company",
                    },
                ],
            },
            {
                "model": "x_lf_expense",
                "description": "Matter Expense / Disbursement",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Description", "required": True},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "string": "Matter",
                        "relation": "x_lf_matter",
                        "required": True,
                    },
                    {"name": "x_date", "ttype": "date", "string": "Date"},
                    {"name": "x_amount", "ttype": "float", "string": "Amount", "required": True},
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "string": "Currency",
                        "relation": "res.currency",
                    },
                    {"name": "x_billable", "ttype": "boolean", "string": "Billable to Client"},
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "string": "Company",
                        "relation": "res.company",
                    },
                ],
            },
            {
                "model": "x_lf_task",
                "description": "Matter Task / Deadline",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Task", "required": True},
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "string": "Reference",
                        "help": "Task ref — wire ir.sequence (e.g. TSK/00001)",
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "string": "Matter",
                        "relation": "x_lf_matter",
                        "required": True,
                    },
                    {
                        "name": "x_assignee_id",
                        "ttype": "many2one",
                        "string": "Assignee",
                        "relation": "res.users",
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": task_status,
                        "required": True,
                    },
                    {"name": "x_due_date", "ttype": "date", "string": "Due Date"},
                    {
                        "name": "x_priority",
                        "ttype": "selection",
                        "string": "Priority",
                        "selection": priority,
                    },
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            },
            {
                "model": "x_lf_hearing",
                "description": "Hearing / Court Diary",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Hearing", "required": True},
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "string": "Reference",
                        "help": "Hearing ref — wire ir.sequence (e.g. HRG/00001)",
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "string": "Matter",
                        "relation": "x_lf_matter",
                        "required": True,
                    },
                    {
                        "name": "x_attorney_id",
                        "ttype": "many2one",
                        "string": "Appearing Counsel",
                        "relation": "x_lf_attorney",
                    },
                    {"name": "x_start", "ttype": "datetime", "string": "Start", "required": True},
                    {"name": "x_end", "ttype": "datetime", "string": "End"},
                    {"name": "x_location", "ttype": "char", "string": "Court / Location"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": hearing_status,
                        "required": True,
                    },
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            },
            {
                "model": "x_lf_document",
                "description": "Matter Document",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Title", "required": True},
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "string": "Matter",
                        "relation": "x_lf_matter",
                        "required": True,
                    },
                    {
                        "name": "x_doc_type",
                        "ttype": "selection",
                        "string": "Type",
                        "selection": _sel(
                            ("pleading", "Pleading"),
                            ("contract", "Contract"),
                            ("correspondence", "Correspondence"),
                            ("evidence", "Evidence"),
                            ("opinion", "Opinion"),
                            ("other", "Other"),
                        ),
                    },
                    {"name": "x_version", "ttype": "char", "string": "Version"},
                    {"name": "x_date", "ttype": "date", "string": "Document Date"},
                    {"name": "x_confidential", "ttype": "boolean", "string": "Confidential"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            },
            {
                "model": "x_lf_conflict",
                "description": "Conflict Check",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Subject", "required": True},
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "string": "Reference",
                        "help": "Conflict check ref — wire ir.sequence (e.g. CFC/00001)",
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "string": "Related Matter",
                        "relation": "x_lf_matter",
                    },
                    {
                        "name": "x_client_id",
                        "ttype": "many2one",
                        "string": "Prospective Client",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": _sel(
                            ("pending", "Pending"),
                            ("cleared", "Cleared"),
                            ("blocked", "Conflict — blocked"),
                        ),
                        "required": True,
                    },
                    {"name": "x_checked_at", "ttype": "datetime", "string": "Checked At"},
                    {"name": "x_notes", "ttype": "text", "string": "Findings"},
                ],
            },
            {
                "model": "x_lf_invoice",
                "description": "Fee Invoice / Bill",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Description", "required": True},
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "string": "Invoice No.",
                        "help": "Fee invoice ref — wire ir.sequence (e.g. INV/00001)",
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "string": "Matter",
                        "relation": "x_lf_matter",
                        "required": True,
                    },
                    {
                        "name": "x_client_id",
                        "ttype": "many2one",
                        "string": "Bill To",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {"name": "x_date", "ttype": "date", "string": "Invoice Date"},
                    {"name": "x_amount", "ttype": "float", "string": "Fees Total", "required": True},
                    {"name": "x_disbursements", "ttype": "float", "string": "Disbursements"},
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "string": "Currency",
                        "relation": "res.currency",
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": bill_status,
                        "required": True,
                    },
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "string": "Company",
                        "relation": "res.company",
                    },
                ],
            },
            {
                "model": "x_lf_payment",
                "description": "Client Payment",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Label", "required": True},
                    {
                        "name": "x_invoice_id",
                        "ttype": "many2one",
                        "string": "Invoice",
                        "relation": "x_lf_invoice",
                        "required": True,
                    },
                    {"name": "x_date", "ttype": "date", "string": "Payment Date"},
                    {"name": "x_amount", "ttype": "float", "string": "Amount", "required": True},
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "string": "Currency",
                        "relation": "res.currency",
                    },
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "string": "Company",
                        "relation": "res.company",
                    },
                ],
            },
            {
                "model": "x_lf_trust",
                "description": "Trust / Retainer Movement",
                "mode": "new",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Label", "required": True},
                    {
                        "name": "x_code",
                        "ttype": "char",
                        "string": "Reference",
                        "help": "Trust movement ref — wire ir.sequence (e.g. TRU/00001)",
                    },
                    {
                        "name": "x_matter_id",
                        "ttype": "many2one",
                        "string": "Matter",
                        "relation": "x_lf_matter",
                        "required": True,
                    },
                    {
                        "name": "x_client_id",
                        "ttype": "many2one",
                        "string": "Client",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {"name": "x_date", "ttype": "date", "string": "Date"},
                    {"name": "x_amount", "ttype": "float", "string": "Amount", "required": True},
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "string": "Currency",
                        "relation": "res.currency",
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": trust_status,
                        "required": True,
                    },
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "string": "Company",
                        "relation": "res.company",
                    },
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_lf_matter",
                "label": "Parties",
                "related_model": "x_lf_matter_party",
                "relation_field": "x_matter_id",
                "icon": "fa-users",
            },
            {
                "on_model": "x_lf_matter",
                "label": "Time",
                "related_model": "x_lf_time_entry",
                "relation_field": "x_matter_id",
                "icon": "fa-clock-o",
            },
            {
                "on_model": "x_lf_matter",
                "label": "Expenses",
                "related_model": "x_lf_expense",
                "relation_field": "x_matter_id",
                "icon": "fa-money",
            },
            {
                "on_model": "x_lf_matter",
                "label": "Tasks",
                "related_model": "x_lf_task",
                "relation_field": "x_matter_id",
                "icon": "fa-check-square-o",
            },
            {
                "on_model": "x_lf_matter",
                "label": "Hearings",
                "related_model": "x_lf_hearing",
                "relation_field": "x_matter_id",
                "icon": "fa-gavel",
            },
            {
                "on_model": "x_lf_matter",
                "label": "Documents",
                "related_model": "x_lf_document",
                "relation_field": "x_matter_id",
                "icon": "fa-file-text-o",
            },
            {
                "on_model": "x_lf_matter",
                "label": "Invoices",
                "related_model": "x_lf_invoice",
                "relation_field": "x_matter_id",
                "icon": "fa-file-text",
            },
            {
                "on_model": "x_lf_matter",
                "label": "Trust",
                "related_model": "x_lf_trust",
                "relation_field": "x_matter_id",
                "icon": "fa-university",
            },
            {
                "on_model": "x_lf_attorney",
                "label": "Matters",
                "related_model": "x_lf_matter",
                "relation_field": "x_responsible_id",
                "icon": "fa-briefcase",
            },
            {
                "on_model": "x_lf_invoice",
                "label": "Payments",
                "related_model": "x_lf_payment",
                "relation_field": "x_invoice_id",
                "icon": "fa-credit-card",
            },
            {
                "on_model": "res.partner",
                "label": "Matters (Client)",
                "related_model": "x_lf_matter",
                "relation_field": "x_client_id",
                "icon": "fa-briefcase",
                "requires_inherit_view": True,
            },
        ],
        "automations": [
            {
                "name": "Activity when matter opened",
                "model": "x_lf_matter",
                "trigger": "on_create",
                "description": "Kick off intake follow-up",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Complete matter intake checklist"}
                ],
            },
            {
                "name": "Activity before limitation date",
                "model": "x_lf_matter",
                "trigger": "on_time",
                "trg_date_field_name": "x_limitation_date",
                "description": "Remind counsel of approaching limitation",
                "filter_domain": "[('x_status', 'not in', ['closed'])]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Limitation date approaching"}
                ],
            },
            {
                "name": "Mark invoice paid when payment posted",
                "model": "x_lf_payment",
                "trigger": "on_create",
                "description": "Related write invoice → paid (simple stub)",
                "safe_actions": [
                    {
                        "kind": "related_write",
                        "relation_field": "x_invoice_id",
                        "field": "x_status",
                        "value": "paid",
                    }
                ],
            },
            {
                "name": "Task overdue activity",
                "model": "x_lf_task",
                "trigger": "on_time",
                "trg_date_field_name": "x_due_date",
                "filter_domain": "[('x_status', 'not in', ['done','cancelled'])]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Overdue matter task"}
                ],
            },
        ],
        "reuse_hints": [
            {
                "model": "res.partner",
                "reason": "Clients, opposing parties, courts, and counsel contacts",
            },
            {
                "model": "res.users",
                "reason": "Map attorneys to logins for assignment / activities",
            },
            {
                "model": "res.company",
                "reason": "Multi-office / multi-company firms",
            },
            {
                "model": "account.move",
                "reason": "Optional later: formal accounting invoices from fee bills",
                "optional": True,
            },
        ],
    }


__all__ = ["law_firm_gold_spec"]
