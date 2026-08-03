"""Hotel / PMS domain pack — rooms, bookings, housekeeping, rate plans."""

from __future__ import annotations

from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def hotel_pack() -> dict[str, Any]:
    room_status = _sel(
        ("available", "Available"),
        ("occupied", "Occupied"),
        ("dirty", "Dirty"),
        ("cleaning", "Cleaning"),
        ("maintenance", "Maintenance"),
        ("blocked", "Blocked"),
    )
    booking_status = _sel(
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("checked_in", "Checked in"),
        ("checked_out", "Checked out"),
        ("no_show", "No-show"),
        ("cancelled", "Cancelled"),
    )
    hk_status = _sel(
        ("draft", "Draft"),
        ("assigned", "Assigned"),
        ("in_progress", "In progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    )
    bill_status = _sel(
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    )
    guest_role = _sel(
        ("primary", "Primary guest"),
        ("additional", "Additional guest"),
        ("child", "Child"),
    )

    return {
        "technical_name": "hotel_management",
        "display_name": "Hotel Management",
        "depends": ["base", "contacts", "mail"],
        "domain_pack": "hotel",
        "tags": [
            "hotel",
            "pms",
            "property management",
            "room",
            "booking",
            "reservation",
            "check-in",
            "check-out",
            "housekeeping",
            "front desk",
            "rate plan",
            "guest",
            "lodging",
        ],
        "anti_patterns": [
            "Do NOT implement payment capture or folio settlement — x_bill is link-only",
            "Do NOT invent x_guest customer model — use res.partner + x_guest_party",
            "x_guest_party is NOT is_workflow",
            "Room amenities are selections/char fields — not separate models",
        ],
        "models": [
            {
                "model": "x_hotel",
                "description": "Hotel Property",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Hotel", "required": True},
                    {"name": "x_code", "ttype": "char", "string": "Code"},
                    {"name": "x_address", "ttype": "char", "string": "Address"},
                    {"name": "x_phone", "ttype": "char", "string": "Phone"},
                    {
                        "name": "x_room_ids",
                        "ttype": "one2many",
                        "string": "Rooms",
                        "relation": "x_room",
                        "relation_field": "x_hotel_id",
                    },
                ],
            },
            {
                "model": "x_room_type",
                "description": "Room Type",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Type", "required": True},
                    {"name": "x_capacity", "ttype": "integer", "string": "Max Guests"},
                    {"name": "x_base_rate", "ttype": "float", "string": "Base Rate"},
                    {
                        "name": "x_room_ids",
                        "ttype": "one2many",
                        "string": "Rooms",
                        "relation": "x_room",
                        "relation_field": "x_room_type_id",
                    },
                ],
            },
            {
                "model": "x_room",
                "description": "Hotel Room",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Room", "required": True},
                    {"name": "x_number", "ttype": "char", "string": "Room Number", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": room_status,
                        "required": True,
                    },
                    {
                        "name": "x_hotel_id",
                        "ttype": "many2one",
                        "string": "Hotel",
                        "relation": "x_hotel",
                        "required": True,
                    },
                    {
                        "name": "x_room_type_id",
                        "ttype": "many2one",
                        "string": "Room Type",
                        "relation": "x_room_type",
                        "required": True,
                    },
                    {"name": "x_floor", "ttype": "char", "string": "Floor"},
                ],
            },
            {
                "model": "x_rate_plan",
                "description": "Rate Plan",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Plan", "required": True},
                    {
                        "name": "x_room_type_id",
                        "ttype": "many2one",
                        "string": "Room Type",
                        "relation": "x_room_type",
                        "required": True,
                    },
                    {"name": "x_nightly_rate", "ttype": "float", "string": "Nightly Rate"},
                    {"name": "x_valid_from", "ttype": "date", "string": "Valid From"},
                    {"name": "x_valid_to", "ttype": "date", "string": "Valid To"},
                ],
            },
            {
                "model": "x_hotel_staff",
                "description": "Hotel Staff",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_user_id",
                        "ttype": "many2one",
                        "string": "Login User",
                        "relation": "res.users",
                    },
                    {
                        "name": "x_hotel_id",
                        "ttype": "many2one",
                        "string": "Hotel",
                        "relation": "x_hotel",
                    },
                    {"name": "x_role", "ttype": "char", "string": "Role"},
                ],
            },
            {
                "model": "x_booking",
                "description": "Room Booking",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "state_field": {
                    "field": "x_status",
                    "transitions": [
                        ["draft", "confirmed"],
                        ["confirmed", "checked_in"],
                        ["checked_in", "checked_out"],
                        ["confirmed", "cancelled"],
                        ["confirmed", "no_show"],
                    ],
                    "states": [
                        "draft",
                        "confirmed",
                        "checked_in",
                        "checked_out",
                        "no_show",
                        "cancelled",
                    ],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Booking", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Primary Guest",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": booking_status,
                        "required": True,
                    },
                    {
                        "name": "x_hotel_id",
                        "ttype": "many2one",
                        "string": "Hotel",
                        "relation": "x_hotel",
                        "required": True,
                    },
                    {
                        "name": "x_room_id",
                        "ttype": "many2one",
                        "string": "Room",
                        "relation": "x_room",
                    },
                    {
                        "name": "x_room_type_id",
                        "ttype": "many2one",
                        "string": "Room Type",
                        "relation": "x_room_type",
                        "required": True,
                    },
                    {
                        "name": "x_rate_plan_id",
                        "ttype": "many2one",
                        "string": "Rate Plan",
                        "relation": "x_rate_plan",
                    },
                    {"name": "x_check_in", "ttype": "datetime", "string": "Check-in", "required": True},
                    {"name": "x_check_out", "ttype": "datetime", "string": "Check-out", "required": True},
                    {"name": "x_guest_count", "ttype": "integer", "string": "Guests"},
                    {
                        "name": "x_guest_party_ids",
                        "ttype": "one2many",
                        "string": "Guest Parties",
                        "relation": "x_guest_party",
                        "relation_field": "x_booking_id",
                    },
                    {
                        "name": "x_bill_id",
                        "ttype": "many2one",
                        "string": "Bill (link)",
                        "relation": "x_bill",
                    },
                ],
            },
            {
                "model": "x_guest_party",
                "description": "Guest Role on Booking",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Label", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Guest",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {
                        "name": "x_role",
                        "ttype": "selection",
                        "string": "Role",
                        "selection": guest_role,
                        "required": True,
                    },
                    {
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "string": "Booking",
                        "relation": "x_booking",
                        "required": True,
                    },
                ],
            },
            {
                "model": "x_housekeeping_task",
                "description": "Housekeeping Task",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread"],
                "state_field": {
                    "field": "x_status",
                    "transitions": [
                        ["draft", "assigned"],
                        ["assigned", "in_progress"],
                        ["in_progress", "done"],
                        ["draft", "cancelled"],
                    ],
                    "states": ["draft", "assigned", "in_progress", "done", "cancelled"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Task", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": hk_status,
                        "required": True,
                    },
                    {
                        "name": "x_room_id",
                        "ttype": "many2one",
                        "string": "Room",
                        "relation": "x_room",
                        "required": True,
                    },
                    {
                        "name": "x_staff_id",
                        "ttype": "many2one",
                        "string": "Assigned To",
                        "relation": "x_hotel_staff",
                    },
                    {"name": "x_due_at", "ttype": "datetime", "string": "Due At"},
                ],
            },
            {
                "model": "x_bill",
                "description": "Folio / Invoice Link",
                "mode": "new",
                "mixins": ["mail.thread"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Bill", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Guest",
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
                        "name": "x_booking_id",
                        "ttype": "many2one",
                        "string": "Booking",
                        "relation": "x_booking",
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
                "on_model": "x_booking",
                "label": "Guests",
                "related_model": "x_guest_party",
                "relation_field": "x_booking_id",
                "icon": "fa-users",
            },
            {
                "on_model": "x_hotel",
                "label": "Rooms",
                "related_model": "x_room",
                "relation_field": "x_hotel_id",
                "icon": "fa-bed",
            },
        ],
        "automations": [
            {
                "name": "Activity on new booking",
                "model": "x_booking",
                "trigger": "on_create",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Confirm booking with guest"}
                ],
            },
            {
                "name": "Occupy room on check-in",
                "model": "x_booking",
                "trigger": "on_write",
                "filter_domain": "[('x_status', '=', 'checked_in'), ('x_room_id', '!=', False)]",
                "safe_actions": [
                    {
                        "kind": "related_write",
                        "relation_field": "x_room_id",
                        "field": "x_status",
                        "value": "occupied",
                    }
                ],
            },
            {
                "name": "Housekeeping on checkout",
                "model": "x_booking",
                "trigger": "on_write",
                "filter_domain": "[('x_status', '=', 'checked_out'), ('x_room_id', '!=', False)]",
                "safe_actions": [
                    {
                        "kind": "related_write",
                        "relation_field": "x_room_id",
                        "field": "x_status",
                        "value": "dirty",
                    },
                    {"kind": "next_activity", "summary": "Schedule housekeeping"},
                ],
            },
        ],
        "reuse_hints": [
            {"model": "res.partner", "reason": "Guests and corporate accounts as Contacts"},
            {"model": "res.users", "reason": "Staff login via x_hotel_staff.x_user_id only"},
        ],
    }


__all__ = ["hotel_pack"]
