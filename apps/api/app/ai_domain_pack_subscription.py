"""Subscription / membership domain pack — plans, renewals, usage lines."""

from __future__ import annotations

from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def subscription_pack() -> dict[str, Any]:
    plan_interval = _sel(
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("yearly", "Yearly"),
        ("custom", "Custom"),
    )
    sub_status = _sel(
        ("draft", "Draft"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("renewal_due", "Renewal due"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    )
    bill_status = _sel(
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    )
    subscriber_role = _sel(
        ("primary", "Primary subscriber"),
        ("billing", "Billing contact"),
        ("user", "End user"),
    )

    return {
        "technical_name": "subscription_management",
        "display_name": "Subscription Management",
        "depends": ["base", "contacts", "mail"],
        "domain_pack": "subscription",
        "tags": [
            "subscription",
            "membership",
            "plan",
            "renewal",
            "recurring",
            "usage",
            "saas",
            "member",
            "tier",
        ],
        "anti_patterns": [
            "Do NOT implement recurring billing engines or payment capture — x_bill link-only",
            "Do NOT copy sale_subscription logic — invoicing is external link pattern only",
            "x_subscriber_party is NOT is_workflow",
            "Plan tier/features are selections — not separate tag models",
        ],
        "models": [
            {
                "model": "x_subscription_plan",
                "description": "Subscription Plan",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Plan", "required": True},
                    {"name": "x_code", "ttype": "char", "string": "Code"},
                    {
                        "name": "x_interval",
                        "ttype": "selection",
                        "string": "Billing Interval",
                        "selection": plan_interval,
                        "required": True,
                    },
                    {"name": "x_price", "ttype": "float", "string": "Price"},
                    {"name": "x_description", "ttype": "text", "string": "Description"},
                    {
                        "name": "x_subscription_ids",
                        "ttype": "one2many",
                        "string": "Subscriptions",
                        "relation": "x_subscription",
                        "relation_field": "x_plan_id",
                    },
                ],
            },
            {
                "model": "x_subscription",
                "description": "Subscription",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "state_field": {
                    "field": "x_status",
                    "transitions": [
                        ["draft", "active"],
                        ["active", "renewal_due"],
                        ["renewal_due", "active"],
                        ["active", "paused"],
                        ["paused", "active"],
                        ["active", "expired"],
                        ["active", "cancelled"],
                    ],
                    "states": [
                        "draft",
                        "active",
                        "paused",
                        "renewal_due",
                        "expired",
                        "cancelled",
                    ],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Subscription", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Subscriber",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": sub_status,
                        "required": True,
                    },
                    {
                        "name": "x_plan_id",
                        "ttype": "many2one",
                        "string": "Plan",
                        "relation": "x_subscription_plan",
                        "required": True,
                    },
                    {"name": "x_start_date", "ttype": "date", "string": "Start", "required": True},
                    {"name": "x_end_date", "ttype": "date", "string": "End"},
                    {"name": "x_renewal_date", "ttype": "date", "string": "Next Renewal"},
                    {
                        "name": "x_subscriber_party_ids",
                        "ttype": "one2many",
                        "string": "Subscriber Parties",
                        "relation": "x_subscriber_party",
                        "relation_field": "x_subscription_id",
                    },
                    {
                        "name": "x_usage_line_ids",
                        "ttype": "one2many",
                        "string": "Usage Lines",
                        "relation": "x_usage_line",
                        "relation_field": "x_subscription_id",
                    },
                    {
                        "name": "x_bill_ids",
                        "ttype": "one2many",
                        "string": "Bills",
                        "relation": "x_bill",
                        "relation_field": "x_subscription_id",
                    },
                ],
            },
            {
                "model": "x_subscriber_party",
                "description": "Subscriber Role",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Label", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Contact",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {
                        "name": "x_role",
                        "ttype": "selection",
                        "string": "Role",
                        "selection": subscriber_role,
                        "required": True,
                    },
                    {
                        "name": "x_subscription_id",
                        "ttype": "many2one",
                        "string": "Subscription",
                        "relation": "x_subscription",
                        "required": True,
                    },
                ],
            },
            {
                "model": "x_usage_line",
                "description": "Usage Line",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Usage", "required": True},
                    {
                        "name": "x_subscription_id",
                        "ttype": "many2one",
                        "string": "Subscription",
                        "relation": "x_subscription",
                        "required": True,
                    },
                    {"name": "x_quantity", "ttype": "float", "string": "Quantity", "required": True},
                    {"name": "x_usage_date", "ttype": "date", "string": "Usage Date"},
                    {"name": "x_metric", "ttype": "char", "string": "Metric"},
                ],
            },
            {
                "model": "x_bill",
                "description": "Invoice Link",
                "mode": "new",
                "mixins": ["mail.thread"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Bill", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Subscriber",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": bill_status,
                        "required": True,
                    },
                    {
                        "name": "x_subscription_id",
                        "ttype": "many2one",
                        "string": "Subscription",
                        "relation": "x_subscription",
                    },
                    {"name": "x_amount", "ttype": "float", "string": "Amount"},
                    {
                        "name": "x_invoice_ref",
                        "ttype": "char",
                        "string": "External Invoice Ref",
                        "help": "Link-only — wire to account.move manually",
                    },
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_subscription",
                "label": "Usage",
                "related_model": "x_usage_line",
                "relation_field": "x_subscription_id",
                "icon": "fa-bar-chart",
            }
        ],
        "automations": [
            {
                "name": "Renewal follow-up",
                "model": "x_subscription",
                "trigger": "on_time",
                "filter_domain": "[('x_status', 'in', ['active', 'renewal_due'])]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Review subscription renewal"}
                ],
            },
            {
                "name": "Mark renewal due before end date",
                "model": "x_subscription",
                "trigger": "on_time",
                "filter_domain": "[('x_status', '=', 'active')]",
                "safe_actions": [
                    {
                        "kind": "object_write",
                        "field": "x_status",
                        "value": "renewal_due",
                    }
                ],
            },
        ],
        "reuse_hints": [
            {"model": "res.partner", "reason": "Subscribers and billing contacts as Contacts"},
        ],
    }


__all__ = ["subscription_pack"]
