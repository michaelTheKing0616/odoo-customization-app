"""Real-estate / property domain pack — units, leases, viewings, maintenance."""

from __future__ import annotations

from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def real_estate_pack() -> dict[str, Any]:
    property_type = _sel(
        ("residential", "Residential"),
        ("commercial", "Commercial"),
        ("mixed", "Mixed Use"),
        ("land", "Land"),
    )
    unit_status = _sel(
        ("available", "Available"),
        ("reserved", "Reserved"),
        ("leased", "Leased"),
        ("maintenance", "Under maintenance"),
        ("offline", "Offline"),
    )
    lease_status = _sel(
        ("draft", "Draft"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("terminated", "Terminated"),
        ("cancelled", "Cancelled"),
    )
    viewing_status = _sel(
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("no_show", "No-show"),
    )
    maint_status = _sel(
        ("draft", "Draft"),
        ("reported", "Reported"),
        ("in_progress", "In progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    )
    deposit_status = _sel(
        ("draft", "Draft"),
        ("held", "Held"),
        ("applied", "Applied"),
        ("refunded", "Refunded"),
        ("forfeited", "Forfeited"),
    )
    bill_status = _sel(
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    )
    tenant_role = _sel(
        ("primary", "Primary tenant"),
        ("co_tenant", "Co-tenant"),
        ("guarantor", "Guarantor"),
        ("occupant", "Occupant"),
    )

    return {
        "technical_name": "real_estate_management",
        "display_name": "Real Estate Management",
        "depends": ["base", "contacts", "mail"],
        "domain_pack": "real_estate",
        "tags": [
            "real estate",
            "property",
            "rental",
            "lease",
            "tenant",
            "landlord",
            "unit",
            "apartment",
            "viewing",
            "maintenance",
            "deposit",
            "listing",
        ],
        "anti_patterns": [
            "Do NOT implement rent collection or payment gateways — x_bill is link-only",
            "Do NOT invent x_tenant customer model — use res.partner + x_tenant_party roles",
            "x_tenant_party is NOT is_workflow",
            "Lease type / property class are selections — not separate models",
        ],
        "models": [
            {
                "model": "x_property",
                "description": "Property / Building",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Property", "required": True},
                    {"name": "x_address", "ttype": "char", "string": "Address"},
                    {"name": "x_city", "ttype": "char", "string": "City"},
                    {
                        "name": "x_type",
                        "ttype": "selection",
                        "string": "Type",
                        "selection": property_type,
                        "required": True,
                    },
                    {
                        "name": "x_unit_ids",
                        "ttype": "one2many",
                        "string": "Units",
                        "relation": "x_unit",
                        "relation_field": "x_property_id",
                    },
                ],
            },
            {
                "model": "x_unit",
                "description": "Rentable Unit",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Unit", "required": True},
                    {"name": "x_code", "ttype": "char", "string": "Unit Code"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": unit_status,
                        "required": True,
                    },
                    {
                        "name": "x_property_id",
                        "ttype": "many2one",
                        "string": "Property",
                        "relation": "x_property",
                        "required": True,
                    },
                    {"name": "x_bedrooms", "ttype": "integer", "string": "Bedrooms"},
                    {"name": "x_rent_amount", "ttype": "float", "string": "List Rent"},
                    {
                        "name": "x_lease_ids",
                        "ttype": "one2many",
                        "string": "Leases",
                        "relation": "x_lease",
                        "relation_field": "x_unit_id",
                    },
                ],
            },
            {
                "model": "x_agent",
                "description": "Leasing Agent",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Agent", "required": True},
                    {
                        "name": "x_user_id",
                        "ttype": "many2one",
                        "string": "Login User",
                        "relation": "res.users",
                    },
                    {"name": "x_phone", "ttype": "char", "string": "Phone"},
                ],
            },
            {
                "model": "x_lease",
                "description": "Lease Agreement",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "state_field": {
                    "field": "x_status",
                    "transitions": [
                        ["draft", "active"],
                        ["active", "expired"],
                        ["active", "terminated"],
                        ["draft", "cancelled"],
                    ],
                    "states": ["draft", "active", "expired", "terminated", "cancelled"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Lease", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Primary Tenant",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": lease_status,
                        "required": True,
                    },
                    {
                        "name": "x_unit_id",
                        "ttype": "many2one",
                        "string": "Unit",
                        "relation": "x_unit",
                        "required": True,
                    },
                    {
                        "name": "x_agent_id",
                        "ttype": "many2one",
                        "string": "Agent",
                        "relation": "x_agent",
                    },
                    {"name": "x_start_date", "ttype": "date", "string": "Start", "required": True},
                    {"name": "x_end_date", "ttype": "date", "string": "End"},
                    {"name": "x_rent_amount", "ttype": "float", "string": "Monthly Rent"},
                    {
                        "name": "x_tenant_party_ids",
                        "ttype": "one2many",
                        "string": "Tenant Parties",
                        "relation": "x_tenant_party",
                        "relation_field": "x_lease_id",
                    },
                    {
                        "name": "x_deposit_ids",
                        "ttype": "one2many",
                        "string": "Deposits",
                        "relation": "x_deposit",
                        "relation_field": "x_lease_id",
                    },
                    {
                        "name": "x_bill_ids",
                        "ttype": "one2many",
                        "string": "Bills",
                        "relation": "x_bill",
                        "relation_field": "x_lease_id",
                    },
                ],
            },
            {
                "model": "x_tenant_party",
                "description": "Tenant / Guarantor Role",
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
                        "selection": tenant_role,
                        "required": True,
                    },
                    {
                        "name": "x_lease_id",
                        "ttype": "many2one",
                        "string": "Lease",
                        "relation": "x_lease",
                        "required": True,
                    },
                ],
            },
            {
                "model": "x_viewing",
                "description": "Property Viewing",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread"],
                "state_field": {
                    "field": "x_status",
                    "transitions": [
                        ["draft", "scheduled"],
                        ["scheduled", "completed"],
                        ["scheduled", "cancelled"],
                        ["scheduled", "no_show"],
                    ],
                    "states": ["draft", "scheduled", "completed", "cancelled", "no_show"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Viewing", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Prospect",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": viewing_status,
                        "required": True,
                    },
                    {
                        "name": "x_unit_id",
                        "ttype": "many2one",
                        "string": "Unit",
                        "relation": "x_unit",
                        "required": True,
                    },
                    {
                        "name": "x_agent_id",
                        "ttype": "many2one",
                        "string": "Agent",
                        "relation": "x_agent",
                    },
                    {"name": "x_scheduled_at", "ttype": "datetime", "string": "Scheduled At"},
                ],
            },
            {
                "model": "x_maintenance_request",
                "description": "Maintenance Request",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "state_field": {
                    "field": "x_status",
                    "transitions": [
                        ["draft", "reported"],
                        ["reported", "in_progress"],
                        ["in_progress", "done"],
                        ["draft", "cancelled"],
                    ],
                    "states": ["draft", "reported", "in_progress", "done", "cancelled"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Request", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": maint_status,
                        "required": True,
                    },
                    {
                        "name": "x_unit_id",
                        "ttype": "many2one",
                        "string": "Unit",
                        "relation": "x_unit",
                        "required": True,
                    },
                    {
                        "name": "x_lease_id",
                        "ttype": "many2one",
                        "string": "Lease",
                        "relation": "x_lease",
                    },
                    {"name": "x_description", "ttype": "text", "string": "Description"},
                    {"name": "x_reported_at", "ttype": "datetime", "string": "Reported At"},
                ],
            },
            {
                "model": "x_deposit",
                "description": "Security Deposit Hold",
                "mode": "new",
                "mixins": ["mail.thread"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Deposit", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": deposit_status,
                        "required": True,
                    },
                    {
                        "name": "x_lease_id",
                        "ttype": "many2one",
                        "string": "Lease",
                        "relation": "x_lease",
                        "required": True,
                    },
                    {"name": "x_amount", "ttype": "float", "string": "Amount", "required": True},
                    {"name": "x_held_date", "ttype": "date", "string": "Held Date"},
                ],
            },
            {
                "model": "x_bill",
                "description": "Rent Bill / Invoice Link",
                "mode": "new",
                "mixins": ["mail.thread"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Bill", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Tenant",
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
                        "name": "x_lease_id",
                        "ttype": "many2one",
                        "string": "Lease",
                        "relation": "x_lease",
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
                "on_model": "x_lease",
                "label": "Deposits",
                "related_model": "x_deposit",
                "relation_field": "x_lease_id",
                "icon": "fa-lock",
            },
            {
                "on_model": "x_property",
                "label": "Units",
                "related_model": "x_unit",
                "relation_field": "x_property_id",
                "icon": "fa-building",
            },
        ],
        "automations": [
            {
                "name": "Activity before lease end",
                "model": "x_lease",
                "trigger": "on_time",
                "filter_domain": "[('x_status', '=', 'active')]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Lease renewal review"}
                ],
            },
            {
                "name": "Mark unit leased on active lease",
                "model": "x_lease",
                "trigger": "on_write",
                "filter_domain": "[('x_status', '=', 'active')]",
                "safe_actions": [
                    {
                        "kind": "related_write",
                        "relation_field": "x_unit_id",
                        "field": "x_status",
                        "value": "leased",
                    }
                ],
            },
        ],
        "reuse_hints": [
            {"model": "res.partner", "reason": "Tenants, prospects, and owners as Contacts"},
            {"model": "res.users", "reason": "Agent login via x_agent.x_user_id only"},
        ],
    }


__all__ = ["real_estate_pack"]
