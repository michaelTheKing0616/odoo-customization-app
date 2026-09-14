"""Law-firm domain pack — stock-first matter workspace (senior Community shape).

Quotations, invoices, timesheets, CRM, calendar, and employees stay stock Odoo.
Custom residual is the legal matter plus parties, billable narrative, conflict
checks, and a document register. Stock hosts inherit ``x_matter_id`` so the
matter is the hub — do not clone Accounting / HR / Project / Calendar.
"""

from __future__ import annotations

import json
from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def _m2o(
    name: str,
    relation: str,
    string: str,
    *,
    required: bool = False,
    help: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "ttype": "many2one",
        "relation": relation,
        "string": string,
    }
    if required:
        row["required"] = True
    if help:
        row["help"] = help
    return row


def _inherit(model: str, description: str, fields: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": model,
        "mode": "inherit",
        "inherit": model,
        "description": description,
        "fields": fields,
    }


def law_firm_pack() -> dict[str, Any]:
    """Curated ModuleSpec: matter file on stock CRM / Sale / Account / HR / Timesheet."""
    practice = _sel(
        ("litigation", "Litigation"),
        ("corporate", "Corporate"),
        ("advisory", "Advisory"),
        ("other", "Other"),
    )
    matter_status = _sel(
        ("intake", "Intake"),
        ("open", "Open"),
        ("billed", "Billed"),
        ("on_hold", "On hold"),
        ("closed", "Closed"),
    )
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
        ("billed", "Billed"),
        ("written_off", "Written off"),
    )
    conflict_status = _sel(
        ("pending", "Pending"),
        ("cleared", "Cleared"),
        ("blocked", "Blocked"),
    )
    doc_type = _sel(
        ("pleading", "Pleading"),
        ("correspondence", "Correspondence"),
        ("advice", "Advice / Opinion"),
        ("contract", "Contract"),
        ("evidence", "Evidence"),
        ("other", "Other"),
    )
    models = [
        {
            "model": "x_matter",
            "description": "Legal matter / case file",
            "mode": "new",
            "is_workflow": True,
            "is_mail_thread": True,
            "is_mail_activity": True,
            "mixins": ["mail.thread", "mail.activity.mixin"],
            "fields": [
                {
                    "name": "x_name",
                    "ttype": "char",
                    "string": "Matter Title",
                    "required": True,
                },
                {
                    "name": "x_code",
                    "ttype": "char",
                    "string": "Matter No.",
                    "help": "Auto-numbered via ir.sequence (MATTER/00001)",
                },
                {
                    "name": "x_partner_id",
                    "ttype": "many2one",
                    "string": "Client",
                    "relation": "res.partner",
                    "required": True,
                },
                {
                    "name": "x_employee_id",
                    "ttype": "many2one",
                    "string": "Responsible Lawyer",
                    "relation": "hr.employee",
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
                    "tracking": True,
                    "default": "intake",
                },
                {
                    "name": "x_open_date",
                    "ttype": "date",
                    "string": "Opened",
                },
                {
                    "name": "x_close_date",
                    "ttype": "date",
                    "string": "Closed",
                },
                {
                    "name": "x_limitation_date",
                    "ttype": "date",
                    "string": "Limitation / Deadline",
                },
                {
                    "name": "x_court",
                    "ttype": "char",
                    "string": "Court / Forum",
                },
                {
                    "name": "x_docket",
                    "ttype": "char",
                    "string": "Docket / File No.",
                },
                {
                    "name": "x_description",
                    "ttype": "text",
                    "string": "Synopsis",
                },
                {
                    "name": "x_lead_id",
                    "ttype": "many2one",
                    "string": "CRM Lead",
                    "relation": "crm.lead",
                    "help": "Intake lives in CRM. This links the qualified lead to the matter file.",
                },
                {
                    "name": "x_sale_order_id",
                    "ttype": "many2one",
                    "string": "Quotation / Sales Order",
                    "relation": "sale.order",
                    "help": "Stock quotation — do not invent a parallel fee invoice.",
                },
                {
                    "name": "x_invoice_id",
                    "ttype": "many2one",
                    "string": "Customer Invoice",
                    "relation": "account.move",
                    "help": "Link-only into Accounting (PCM). Invoices stay account.move.",
                },
                {
                    "name": "x_analytic_account_id",
                    "ttype": "many2one",
                    "string": "Analytic / Timesheet Account",
                    "relation": "account.analytic.account",
                    "help": "Billable hours are stock timesheets on this analytic account.",
                },
                {
                    "name": "x_confirm_date",
                    "ttype": "datetime",
                    "string": "Confirm Date",
                },
                {
                    "name": "x_company_id",
                    "ttype": "many2one",
                    "string": "Company",
                    "relation": "res.company",
                },
                {
                    "name": "x_matter_party_ids",
                    "ttype": "one2many",
                    "relation": "x_matter_party",
                    "relation_field": "x_matter_id",
                    "string": "Parties",
                },
                {
                    "name": "x_matter_line_ids",
                    "ttype": "one2many",
                    "relation": "x_matter_line",
                    "relation_field": "x_matter_id",
                    "string": "Billable Time",
                },
                {
                    "name": "x_conflict_check_ids",
                    "ttype": "one2many",
                    "relation": "x_conflict_check",
                    "relation_field": "x_matter_id",
                    "string": "Conflict Checks",
                },
                {
                    "name": "x_matter_document_ids",
                    "ttype": "one2many",
                    "relation": "x_matter_document",
                    "relation_field": "x_matter_id",
                    "string": "Documents",
                },
            ],
            "state_field": {
                "field": "x_status",
                "states": ["intake", "open", "billed", "on_hold", "closed"],
                "statusbar_visible": ["intake", "open", "billed", "closed"],
                "transitions": [
                    ["intake", "open"],
                    ["open", "billed"],
                    ["open", "on_hold"],
                    ["on_hold", "open"],
                    ["billed", "closed"],
                    ["on_hold", "closed"],
                ],
            },
        },
        {
            "model": "x_matter_party",
            "description": "Matter party / role",
            "mode": "new",
            "is_workflow": False,
            "fields": [
                {
                    "name": "x_name",
                    "ttype": "char",
                    "string": "Label",
                    "required": True,
                },
                {
                    "name": "x_matter_id",
                    "ttype": "many2one",
                    "string": "Matter",
                    "relation": "x_matter",
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
                {
                    "name": "x_company_id",
                    "ttype": "many2one",
                    "string": "Company",
                    "relation": "res.company",
                },
            ],
        },
        {
            "model": "x_matter_line",
            "description": "Billable time narrative",
            "mode": "new",
            "is_workflow": False,
            "mixins": [],
            "fields": [
                {
                    "name": "x_name",
                    "ttype": "char",
                    "string": "Narrative",
                    "required": True,
                },
                {
                    "name": "x_code",
                    "ttype": "char",
                    "string": "Reference",
                },
                {
                    "name": "x_matter_id",
                    "ttype": "many2one",
                    "string": "Matter",
                    "relation": "x_matter",
                    "required": True,
                },
                {
                    "name": "x_employee_id",
                    "ttype": "many2one",
                    "string": "Fee Earner",
                    "relation": "hr.employee",
                },
                {
                    "name": "x_date",
                    "ttype": "date",
                    "string": "Date",
                    "default": "today",
                },
                {
                    "name": "x_hours",
                    "ttype": "float",
                    "string": "Hours",
                    "required": True,
                },
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "string": "Currency",
                    "relation": "res.currency",
                },
                {
                    "name": "x_rate",
                    "ttype": "monetary",
                    "string": "Rate",
                    "currency_field": "x_currency_id",
                    "widget": "monetary",
                },
                {
                    "name": "x_amount",
                    "ttype": "monetary",
                    "string": "Amount",
                    "currency_field": "x_currency_id",
                    "widget": "monetary",
                },
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Billing Status",
                    "selection": time_status,
                    "default": "draft",
                },
                {
                    "name": "x_timesheet_id",
                    "ttype": "many2one",
                    "string": "Timesheet Line",
                    "relation": "account.analytic.line",
                    "help": "Optional link to stock hr_timesheet / analytic line.",
                },
                {
                    "name": "x_company_id",
                    "ttype": "many2one",
                    "string": "Company",
                    "relation": "res.company",
                    "on_delete": "restrict",
                },
            ],
        },
        {
            "model": "x_conflict_check",
            "description": "Conflict-of-interest clearance before (or while) a matter is open",
            "mode": "new",
            "is_workflow": True,
            "is_mail_thread": True,
            "is_mail_activity": True,
            "mixins": ["mail.thread", "mail.activity.mixin"],
            "fields": [
                {
                    "name": "x_name",
                    "ttype": "char",
                    "string": "Subject",
                    "required": True,
                },
                {
                    "name": "x_code",
                    "ttype": "char",
                    "string": "Check No.",
                    "help": "Auto-numbered via ir.sequence (CONF/00001)",
                },
                _m2o("x_matter_id", "x_matter", "Matter"),
                _m2o("x_partner_id", "res.partner", "Party searched", required=True),
                _m2o("x_employee_id", "hr.employee", "Checked by"),
                {
                    "name": "x_status",
                    "ttype": "selection",
                    "string": "Status",
                    "selection": conflict_status,
                    "default": "pending",
                    "required": True,
                },
                {"name": "x_checked_at", "ttype": "datetime", "string": "Cleared / blocked at"},
                {"name": "x_notes", "ttype": "text", "string": "Findings"},
                _m2o("x_company_id", "res.company", "Company"),
            ],
            "state_field": {
                "field": "x_status",
                "states": ["pending", "cleared", "blocked"],
                "statusbar_visible": ["pending", "cleared", "blocked"],
                "transitions": [
                    ["pending", "cleared"],
                    ["pending", "blocked"],
                    ["blocked", "pending"],
                ],
            },
        },
        {
            "model": "x_matter_document",
            "description": "Legal document register (type, version, confidentiality) — not a parallel DMS",
            "mode": "new",
            "is_workflow": False,
            "fields": [
                {
                    "name": "x_name",
                    "ttype": "char",
                    "string": "Title",
                    "required": True,
                },
                _m2o("x_matter_id", "x_matter", "Matter", required=True),
                {
                    "name": "x_doc_type",
                    "ttype": "selection",
                    "string": "Type",
                    "selection": doc_type,
                    "default": "correspondence",
                },
                {"name": "x_version", "ttype": "char", "string": "Version"},
                {"name": "x_date", "ttype": "date", "string": "Date", "default": "today"},
                {
                    "name": "x_confidential",
                    "ttype": "boolean",
                    "string": "Confidential",
                    "default": True,
                },
                {"name": "x_notes", "ttype": "text", "string": "Notes"},
                _m2o("x_company_id", "res.company", "Company"),
            ],
        },
        _inherit(
            "calendar.event",
            "Hearings and meetings sit on the diary, linked to the matter",
            [
                _m2o("x_matter_id", "x_matter", "Matter"),
                _m2o("x_employee_id", "hr.employee", "Lawyer"),
            ],
        ),
        _inherit(
            "hr.employee",
            "Fee-earner profile on stock HR — never a parallel x_attorney",
            [
                {"name": "x_bar_number", "ttype": "char", "string": "Bar number"},
                {
                    "name": "x_practice_area",
                    "ttype": "selection",
                    "string": "Practice area",
                    "selection": practice,
                },
                {"name": "x_hourly_rate", "ttype": "float", "string": "Hourly rate"},
                _m2o("x_currency_id", "res.currency", "Currency"),
            ],
        ),
        _inherit(
            "sale.order",
            "Quotations hang off the matter — never a parallel x_bill",
            [_m2o("x_matter_id", "x_matter", "Matter")],
        ),
        _inherit(
            "account.move",
            "Customer invoices hang off the matter — never a parallel invoice model",
            [_m2o("x_matter_id", "x_matter", "Matter")],
        ),
        _inherit(
            "crm.lead",
            "Intake opportunity linked to the matter file",
            [_m2o("x_matter_id", "x_matter", "Matter")],
        ),
        _inherit(
            "project.task",
            "Internal deadlines on stock Project, linked to the matter",
            [_m2o("x_matter_id", "x_matter", "Matter")],
        ),
    ]
    return {
        "technical_name": "law_firm_management",
        "display_name": "Law Firm Management",
        "domain_pack": "law_firm",
        "document_shape": "workspace",
        "depends": [
            "base",
            "mail",
            "contacts",
            "crm",
            "sale",
            "account",
            "hr",
            "hr_timesheet",
            "calendar",
            "project",
        ],
        "multi_company": False,
        "tags": [
            "law",
            "legal",
            "lawyer",
            "attorney",
            "matter",
            "case",
            "litigation",
            "law firm",
            "practice management",
            "retainer",
            "trust",
            "billable",
            "counsel",
        ],
        "reuse_stock": [
            {
                "model": "res.partner",
                "modules": ["contacts"],
                "reason": "Clients and opposing parties — never x_client",
                "forbid_parallel": ["x_client", "x_customer"],
            },
            {
                "model": "hr.employee",
                "modules": ["hr"],
                "reason": "Responsible lawyer / fee earner — never x_attorney",
                "forbid_parallel": ["x_attorney", "x_lawyer", "x_staff"],
            },
            {
                "model": "crm.lead",
                "modules": ["crm"],
                "reason": "Intake pipeline (new → qualified → engaged)",
                "forbid_parallel": ["x_lead", "x_intake"],
            },
            {
                "model": "sale.order",
                "modules": ["sale"],
                "reason": "Quotations and retainers (link-only)",
                "link_only": True,
                "forbid_parallel": ["x_quotation", "x_retainer"],
            },
            {
                "model": "account.move",
                "modules": ["account"],
                "reason": "Customer invoices — never a parallel x_bill",
                "link_only": True,
                "forbid_parallel": ["x_invoice", "x_bill", "x_payment"],
            },
            {
                "model": "account.analytic.line",
                "modules": ["hr_timesheet", "analytic"],
                "reason": "Billable hours (stock timesheets)",
                "link_only": True,
                "forbid_parallel": ["x_timesheet"],
            },
            {
                "model": "calendar.event",
                "modules": ["calendar"],
                "reason": "Hearings and meetings sit on the diary; they do not replace the matter",
                "link_only": True,
                "forbid_parallel": ["x_event", "x_hearing", "x_appointment"],
            },
            {
                "model": "project.task",
                "modules": ["project"],
                "reason": "Internal deadlines — Project is not a substitute for the matter file",
                "link_only": True,
                "forbid_parallel": ["x_task"],
            },
        ],
        "reuse": {
            "models": [
                "res.partner",
                "hr.employee",
                "crm.lead",
                "sale.order",
                "account.move",
                "account.analytic.line",
                "calendar.event",
                "project.task",
            ]
        },
        "anti_patterns": [
            "Do NOT invent x_client / x_customer — use res.partner + x_matter_party roles",
            "Do NOT invent x_attorney — responsible lawyer is hr.employee",
            "Do NOT invent x_bill / x_payment / x_deposit — invoices and trust journals are stock Accounting",
            "Do NOT invent x_task / x_event — inherit project.task and calendar.event with x_matter_id",
            "Do NOT emit Python code automations",
            "Matter status is intake → open → billed → closed (Confirm is a server action)",
            "Conflict checks are x_conflict_check, not a matter status named discovery/trial",
            "Document register is x_matter_document, not x_document / a second DMS",
            "Two offices of one company are not multi-company",
        ],
        "models": models,
        "_pack_model_ids": [str(m["model"]) for m in models],
        "smart_buttons": [
            {
                "on_model": "x_matter",
                "label": "Quotations",
                "related_model": "sale.order",
                "relation_field": "x_matter_id",
                "icon": "fa-file-text-o",
            },
            {
                "on_model": "x_matter",
                "label": "Invoices",
                "related_model": "account.move",
                "relation_field": "x_matter_id",
                "icon": "fa-pencil-square-o",
            },
            {
                "on_model": "x_matter",
                "label": "Meetings",
                "related_model": "calendar.event",
                "relation_field": "x_matter_id",
                "icon": "fa-calendar",
            },
            {
                "on_model": "x_matter",
                "label": "Tasks",
                "related_model": "project.task",
                "relation_field": "x_matter_id",
                "icon": "fa-check-square-o",
            },
            {
                "on_model": "res.partner",
                "label": "Matters",
                "related_model": "x_matter",
                "relation_field": "x_partner_id",
                "icon": "fa-briefcase",
                "requires_inherit_view": True,
            },
            {
                "on_model": "hr.employee",
                "label": "Matters",
                "related_model": "x_matter",
                "relation_field": "x_employee_id",
                "icon": "fa-briefcase",
                "requires_inherit_view": True,
            },
        ],
        "automations": [
            {
                "name": "Activity before limitation date",
                "model": "x_matter",
                "trigger": "on_time",
                "trg_date_field_name": "x_limitation_date",
                "description": "Remind counsel of an approaching limitation",
                "filter_domain": "[('x_status', 'not in', ['closed'])]",
                "safe_actions": [
                    {
                        "kind": "next_activity",
                        "summary": "Limitation date approaching",
                        "activity_type_xml_id": "mail.mail_activity_data_todo",
                    }
                ],
            },
            {
                "name": "Activity when matter opened",
                "model": "x_matter",
                "trigger": "on_create",
                "description": "Kick off intake follow-up",
                "safe_actions": [
                    {
                        "kind": "next_activity",
                        "summary": "Complete matter intake checklist",
                        "activity_type_xml_id": "mail.mail_activity_data_todo",
                    }
                ],
            },
            {
                "name": "Activity when conflict is blocked",
                "model": "x_conflict_check",
                "trigger": "on_write",
                "description": "Escalate a blocked conflict of interest",
                "filter_domain": "[('x_status', '=', 'blocked')]",
                "safe_actions": [
                    {
                        "kind": "next_activity",
                        "summary": "Conflict blocked — do not open or bill this matter",
                        "activity_type_xml_id": "mail.mail_activity_data_todo",
                    }
                ],
            },
        ],
        "actions": [
            {
                "name": "Matters",
                "model": "x_matter",
                "view_mode": "list,kanban,form",
                "technical_name": "action_x_matter",
            },
            {
                "name": "Matter Parties",
                "model": "x_matter_party",
                "view_mode": "list,form",
                "technical_name": "action_x_matter_party",
            },
            {
                "name": "Billable Time",
                "model": "x_matter_line",
                "view_mode": "list,form",
                "technical_name": "action_x_matter_line",
            },
            {
                "name": "Conflict Checks",
                "model": "x_conflict_check",
                "view_mode": "list,kanban,form",
                "technical_name": "action_x_conflict_check",
            },
            {
                "name": "Documents",
                "model": "x_matter_document",
                "view_mode": "list,form",
                "technical_name": "action_x_matter_document",
            },
        ],
        "menus": [
            {
                "name": "Law Firm",
                "sequence": 10,
                "technical_name": "root_law_firm_management",
                "xml_id": "menu_root_law_firm_management",
                "groups": ["group_law_firm_management_user"],
                "web_icon": "fa-balance-scale,#714B67",
            },
            {
                "name": "Operations",
                "parent_xml_id": "menu_root_law_firm_management",
                "sequence": 10,
                "technical_name": "menu_sub_operations_root_law_firm_management",
                "xml_id": "menu_sub_operations_root_law_firm_management",
            },
            {
                "name": "Matters",
                "action_xml_id": "action_x_matter",
                "parent_xml_id": "menu_sub_operations_root_law_firm_management",
                "sequence": 10,
                "technical_name": "menu_x_matter",
            },
            {
                "name": "Parties",
                "action_xml_id": "action_x_matter_party",
                "parent_xml_id": "menu_sub_operations_root_law_firm_management",
                "sequence": 20,
                "technical_name": "menu_x_matter_party",
            },
            {
                "name": "Time",
                "action_xml_id": "action_x_matter_line",
                "parent_xml_id": "menu_sub_operations_root_law_firm_management",
                "sequence": 30,
                "technical_name": "menu_x_matter_line",
            },
            {
                "name": "Conflicts",
                "action_xml_id": "action_x_conflict_check",
                "parent_xml_id": "menu_sub_operations_root_law_firm_management",
                "sequence": 40,
                "technical_name": "menu_x_conflict_check",
            },
            {
                "name": "Documents",
                "action_xml_id": "action_x_matter_document",
                "parent_xml_id": "menu_sub_operations_root_law_firm_management",
                "sequence": 50,
                "technical_name": "menu_x_matter_document",
            },
        ],
        "views": [
            {
                "name": "x_matter.list",
                "model": "x_matter",
                "type": "list",
                "mode": "primary",
                "arch": (
                    '<list string="Matters" sample="1">'
                    '<field name="x_code"/><field name="x_name"/>'
                    '<field name="x_partner_id"/><field name="x_employee_id"/>'
                    '<field name="x_practice_area"/><field name="x_status"/>'
                    '<field name="x_limitation_date"/>'
                    "</list>"
                ),
            },
            {
                "name": "x_matter.form",
                "model": "x_matter",
                "type": "form",
                "mode": "primary",
                "arch": (
                    '<form string="Matter">'
                    "<header>"
                    '<field name="x_status" widget="statusbar" '
                    'statusbar_visible="intake,open,billed,closed"/>'
                    '<button string="Confirm" type="object" class="oe_highlight" '
                    "invisible=\"x_status != 'intake'\" data-transition-to=\"open\"/>"
                    '<button string="Mark billed" type="object" '
                    "invisible=\"x_status != 'open'\" data-transition-to=\"billed\"/>"
                    '<button string="On hold" type="object" '
                    "invisible=\"x_status != 'open'\" data-transition-to=\"on_hold\"/>"
                    '<button string="Reopen" type="object" '
                    "invisible=\"x_status != 'on_hold'\" data-transition-to=\"open\"/>"
                    '<button string="Close" type="object" class="oe_highlight" '
                    "invisible=\"x_status not in ('billed', 'on_hold')\" "
                    'data-transition-to="closed"/>'
                    "</header>"
                    "<sheet>"
                    '<group string="Matter">'
                    '<field name="x_name"/><field name="x_code"/>'
                    '<field name="x_partner_id"/><field name="x_employee_id"/>'
                    '<field name="x_practice_area"/><field name="x_company_id"/>'
                    "</group>"
                    '<group string="Dates &amp; court">'
                    '<field name="x_open_date"/><field name="x_close_date"/>'
                    '<field name="x_limitation_date"/><field name="x_confirm_date"/>'
                    '<field name="x_court"/><field name="x_docket"/>'
                    "</group>"
                    '<group string="Analytic">'
                    '<field name="x_analytic_account_id"/>'
                    "</group>"
                    '<group string="Synopsis"><field name="x_description" colspan="2"/></group>'
                    "<notebook>"
                    '<page string="Parties">'
                    '<field name="x_matter_party_ids">'
                    '<list editable="bottom">'
                    '<field name="x_partner_id"/><field name="x_role"/>'
                    '<field name="x_name"/><field name="x_notes"/>'
                    "</list></field></page>"
                    '<page string="Billable time">'
                    '<field name="x_matter_line_ids">'
                    '<list editable="bottom">'
                    '<field name="x_date"/><field name="x_employee_id"/>'
                    '<field name="x_name"/><field name="x_hours"/>'
                    '<field name="x_rate"/><field name="x_amount"/>'
                    '<field name="x_status"/>'
                    "</list></field></page>"
                    '<page string="Conflicts">'
                    '<field name="x_conflict_check_ids">'
                    '<list editable="bottom">'
                    '<field name="x_name"/><field name="x_partner_id"/>'
                    '<field name="x_employee_id"/><field name="x_status"/>'
                    "</list></field></page>"
                    '<page string="Documents">'
                    '<field name="x_matter_document_ids">'
                    '<list editable="bottom">'
                    '<field name="x_name"/><field name="x_doc_type"/>'
                    '<field name="x_date"/><field name="x_version"/>'
                    '<field name="x_confidential"/>'
                    "</list></field></page>"
                    "</notebook></sheet><chatter/></form>"
                ),
            },
            {
                "name": "x_matter.kanban",
                "model": "x_matter",
                "type": "kanban",
                "mode": "primary",
                "arch": (
                    '<kanban default_group_by="x_status" class="o_kanban_small_column" sample="1">'
                    "<templates><t t-name=\"card\">"
                    '<field name="x_name"/><field name="x_code"/>'
                    '<field name="x_partner_id"/><field name="x_employee_id"/>'
                    "</t></templates></kanban>"
                ),
            },
            {
                "name": "x_matter.search",
                "model": "x_matter",
                "type": "search",
                "mode": "primary",
                "arch": (
                    '<search string="Matters">'
                    '<filter string="Intake" name="status_intake" domain="[(\'x_status\',\'=\',\'intake\')]"/>'
                    '<filter string="Open" name="status_open" domain="[(\'x_status\',\'=\',\'open\')]"/>'
                    '<filter string="Billed" name="status_billed" domain="[(\'x_status\',\'=\',\'billed\')]"/>'
                    '<filter string="Closed" name="status_closed" domain="[(\'x_status\',\'=\',\'closed\')]"/>'
                    '<filter string="Client" name="group_x_partner_id" context="{\'group_by\': \'x_partner_id\'}"/>'
                    '<filter string="Lawyer" name="group_x_employee_id" context="{\'group_by\': \'x_employee_id\'}"/>'
                    '<filter string="Status" name="group_x_status" context="{\'group_by\': \'x_status\'}"/>'
                    "</search>"
                ),
            },
            {
                "name": "x_matter_party.list",
                "model": "x_matter_party",
                "type": "list",
                "mode": "primary",
                "arch": (
                    '<list string="Matter Parties" sample="1">'
                    '<field name="x_matter_id"/><field name="x_partner_id"/>'
                    '<field name="x_role"/><field name="x_name"/>'
                    "</list>"
                ),
            },
            {
                "name": "x_matter_party.form",
                "model": "x_matter_party",
                "type": "form",
                "mode": "primary",
                "arch": (
                    '<form string="Matter Party"><sheet>'
                    '<group><field name="x_matter_id"/><field name="x_partner_id"/>'
                    '<field name="x_role"/><field name="x_name"/>'
                    '<field name="x_notes"/><field name="x_company_id"/></group>'
                    "</sheet></form>"
                ),
            },
            {
                "name": "x_matter_line.list",
                "model": "x_matter_line",
                "type": "list",
                "mode": "primary",
                "arch": (
                    '<list string="Billable Time" sample="1">'
                    '<field name="x_date"/><field name="x_matter_id"/>'
                    '<field name="x_employee_id"/><field name="x_name"/>'
                    '<field name="x_hours"/><field name="x_rate"/>'
                    '<field name="x_amount"/><field name="x_status"/>'
                    "</list>"
                ),
            },
            {
                "name": "x_matter_line.form",
                "model": "x_matter_line",
                "type": "form",
                "mode": "primary",
                "arch": (
                    '<form string="Billable Time"><sheet>'
                    '<group string="Entry">'
                    '<field name="x_matter_id"/><field name="x_employee_id"/>'
                    '<field name="x_name"/><field name="x_date"/>'
                    "</group>"
                    '<group string="Fees">'
                    '<field name="x_hours"/><field name="x_currency_id"/>'
                    '<field name="x_rate"/><field name="x_amount"/>'
                    '<field name="x_status"/><field name="x_timesheet_id"/>'
                    "</group></sheet></form>"
                ),
            },
            {
                "name": "x_conflict_check.list",
                "model": "x_conflict_check",
                "type": "list",
                "mode": "primary",
                "arch": (
                    '<list string="Conflict Checks" sample="1">'
                    '<field name="x_code"/><field name="x_name"/>'
                    '<field name="x_matter_id"/><field name="x_partner_id"/>'
                    '<field name="x_employee_id"/><field name="x_status"/>'
                    "</list>"
                ),
            },
            {
                "name": "x_conflict_check.form",
                "model": "x_conflict_check",
                "type": "form",
                "mode": "primary",
                "arch": (
                    '<form string="Conflict Check">'
                    "<header>"
                    '<field name="x_status" widget="statusbar" '
                    'statusbar_visible="pending,cleared,blocked"/>'
                    '<button string="Clear" type="object" class="oe_highlight" '
                    "invisible=\"x_status != 'pending'\" data-transition-to=\"cleared\"/>"
                    '<button string="Block" type="object" '
                    "invisible=\"x_status != 'pending'\" data-transition-to=\"blocked\"/>"
                    '<button string="Re-open" type="object" '
                    "invisible=\"x_status != 'blocked'\" data-transition-to=\"pending\"/>"
                    "</header>"
                    "<sheet>"
                    '<group><field name="x_name"/><field name="x_code"/>'
                    '<field name="x_matter_id"/><field name="x_partner_id"/>'
                    '<field name="x_employee_id"/><field name="x_checked_at"/>'
                    '<field name="x_notes" colspan="2"/><field name="x_company_id"/>'
                    "</group></sheet><chatter/></form>"
                ),
            },
            {
                "name": "x_conflict_check.kanban",
                "model": "x_conflict_check",
                "type": "kanban",
                "mode": "primary",
                "arch": (
                    '<kanban default_group_by="x_status" class="o_kanban_small_column" sample="1">'
                    "<templates><t t-name=\"card\">"
                    '<field name="x_name"/><field name="x_partner_id"/>'
                    '<field name="x_matter_id"/>'
                    "</t></templates></kanban>"
                ),
            },
            {
                "name": "x_matter_document.list",
                "model": "x_matter_document",
                "type": "list",
                "mode": "primary",
                "arch": (
                    '<list string="Documents" sample="1">'
                    '<field name="x_name"/><field name="x_matter_id"/>'
                    '<field name="x_doc_type"/><field name="x_date"/>'
                    '<field name="x_version"/><field name="x_confidential"/>'
                    "</list>"
                ),
            },
            {
                "name": "x_matter_document.form",
                "model": "x_matter_document",
                "type": "form",
                "mode": "primary",
                "arch": (
                    '<form string="Document"><sheet>'
                    '<group><field name="x_name"/><field name="x_matter_id"/>'
                    '<field name="x_doc_type"/><field name="x_version"/>'
                    '<field name="x_date"/><field name="x_confidential"/>'
                    '<field name="x_notes" colspan="2"/><field name="x_company_id"/>'
                    "</group></sheet></form>"
                ),
            },
        ],
        "sequences": [
            {
                "model": "x_matter",
                "field": "x_code",
                "name": "Matter Sequence",
                "prefix": "MATTER/",
                "padding": 5,
                "implementation": "base_automation_on_create",
            },
            {
                "model": "x_conflict_check",
                "field": "x_code",
                "name": "Conflict Check Sequence",
                "prefix": "CONF/",
                "padding": 5,
                "implementation": "base_automation_on_create",
            },
        ],
        "custom_code_blocks": [
            {
                "source_file": "models/x_matter_line.py",
                "kind": "python",
                "model": "x_matter_line",
                "reason": "apply_readiness: line subtotal compute",
                "content": (
                    "from odoo import api, fields, models\n\n\n"
                    "class XMatterLineSubtotal(models.Model):\n"
                    "    _inherit = 'x_matter_line'\n\n"
                    "    x_amount = fields.Monetary(\n"
                    "        string='Amount',\n"
                    "        compute='_compute_x_amount',\n"
                    "        store=True,\n"
                    "        currency_field='x_currency_id',\n"
                    "    )\n\n"
                    "    @api.depends('x_hours', 'x_rate')\n"
                    "    def _compute_x_amount(self):\n"
                    "        for rec in self:\n"
                    "            rec.x_amount = (rec.x_hours or 0.0) * (rec.x_rate or 0.0)\n"
                ),
            }
        ],
        "groups": [
            {
                "id": "group_law_firm_management_user",
                "name": "Law Firm User",
                "category_id": "base.module_category_custom",
            },
            {
                "id": "group_law_firm_management_manager",
                "name": "Law Firm Manager",
                "implied_ids": ["group_law_firm_management_user"],
                "category_id": "base.module_category_custom",
            },
        ],
        "access_rules": [
            {
                "id": "access_x_matter_user",
                "name": "Matter user",
                "model": "model_x_matter",
                "group": "group_law_firm_management_user",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 0,
            },
            {
                "id": "access_x_matter_manager",
                "name": "Matter manager",
                "model": "model_x_matter",
                "group": "group_law_firm_management_manager",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 1,
            },
            {
                "id": "access_x_matter_party_user",
                "name": "Matter party user",
                "model": "model_x_matter_party",
                "group": "group_law_firm_management_user",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 0,
            },
            {
                "id": "access_x_matter_party_manager",
                "name": "Matter party manager",
                "model": "model_x_matter_party",
                "group": "group_law_firm_management_manager",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 1,
            },
            {
                "id": "access_x_matter_line_user",
                "name": "Billable time user",
                "model": "model_x_matter_line",
                "group": "group_law_firm_management_user",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 0,
            },
            {
                "id": "access_x_matter_line_manager",
                "name": "Billable time manager",
                "model": "model_x_matter_line",
                "group": "group_law_firm_management_manager",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 1,
            },
            {
                "id": "access_x_conflict_check_user",
                "name": "Conflict check user",
                "model": "model_x_conflict_check",
                "group": "group_law_firm_management_user",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 0,
            },
            {
                "id": "access_x_conflict_check_manager",
                "name": "Conflict check manager",
                "model": "model_x_conflict_check",
                "group": "group_law_firm_management_manager",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 1,
            },
            {
                "id": "access_x_matter_document_user",
                "name": "Document user",
                "model": "model_x_matter_document",
                "group": "group_law_firm_management_user",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 0,
            },
            {
                "id": "access_x_matter_document_manager",
                "name": "Document manager",
                "model": "model_x_matter_document",
                "group": "group_law_firm_management_manager",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 1,
            },
        ],
    }


def scaffold_teaching_blob(
    scaffold: dict[str, Any] | None, *, max_chars: int = 12000
) -> str:
    """Compact world-class scaffold for the LLM prompt (teach before merge)."""
    if not scaffold:
        return ""
    models_out: list[dict[str, Any]] = []
    for m in scaffold.get("models") or []:
        if not isinstance(m, dict) or not m.get("model"):
            continue
        fields_out: list[dict[str, Any]] = []
        for f in (m.get("fields") or [])[:22]:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            row: dict[str, Any] = {
                "name": f.get("name"),
                "ttype": f.get("ttype"),
                "string": f.get("string"),
            }
            if f.get("relation"):
                row["relation"] = f["relation"]
            if f.get("relation_field"):
                row["relation_field"] = f["relation_field"]
            if f.get("selection"):
                row["selection"] = str(f["selection"])[:140]
            if f.get("required"):
                row["required"] = True
            fields_out.append(row)
        models_out.append(
            {
                "model": m.get("model"),
                "description": m.get("description"),
                "is_workflow": bool(m.get("is_workflow")),
                "fields": fields_out,
            }
        )
    payload = {
        "instruction": (
            "Study this senior Odoo Community scaffold. Prefer STOCK apps "
            "(res.partner, hr.employee, crm.lead, sale.order, account.move, "
            "calendar.event, project.task, account.analytic.line) over cloning them "
            "as x_*. Custom models[] are the residual the stock apps do not cover. "
            "Inherit sale.order / account.move / calendar.event / hr.employee / "
            "crm.lead / project.task with x_matter_id (fee-earner fields on hr.employee). "
            "Also include x_conflict_check and x_matter_document. "
            "Do NOT add x_attorney, x_bill, x_payment, x_deposit, x_task, or x_event. "
            "Responsible lawyer many2ones relation hr.employee (login stays res.users "
            "only as x_user_id on employees). Matter status is intake → open → billed "
            "→ closed with a Confirm server action. Party/role-link models are NOT "
            "is_workflow. Adapt labels to the user domain; do not invent hollow type "
            "models or a parallel invoice."
        ),
        "required_models": [m["model"] for m in models_out],
        "domain_pack": scaffold.get("domain_pack"),
        "document_shape": scaffold.get("document_shape") or "workspace",
        "models": models_out,
        "reuse_stock": scaffold.get("reuse_stock") or [],
        "automations": (scaffold.get("automations") or [])[:8],
        "smart_buttons": (scaffold.get("smart_buttons") or [])[:12],
        "anti_patterns": scaffold.get("anti_patterns") or [],
    }
    return json.dumps(payload, indent=None)[:max_chars]


__all__ = ["law_firm_pack", "scaffold_teaching_blob"]
