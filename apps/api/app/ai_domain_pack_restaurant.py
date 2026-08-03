"""Restaurant / POS-lite domain pack — tables, reservations, orders, kitchen flow."""

from __future__ import annotations

from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def restaurant_pack() -> dict[str, Any]:
    table_status = _sel(
        ("available", "Available"),
        ("reserved", "Reserved"),
        ("seated", "Seated"),
        ("dirty", "Needs cleaning"),
        ("blocked", "Blocked"),
    )
    reservation_status = _sel(
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("seated", "Seated"),
        ("completed", "Completed"),
        ("no_show", "No-show"),
        ("cancelled", "Cancelled"),
    )
    order_status = _sel(
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("in_kitchen", "In kitchen"),
        ("ready", "Ready to serve"),
        ("served", "Served"),
        ("cancelled", "Cancelled"),
    )
    line_kitchen = _sel(
        ("pending", "Pending"),
        ("in_kitchen", "In kitchen"),
        ("ready", "Ready"),
        ("served", "Served"),
        ("cancelled", "Cancelled"),
    )
    bill_status = _sel(
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    )
    meal_period = _sel(
        ("breakfast", "Breakfast"),
        ("lunch", "Lunch"),
        ("dinner", "Dinner"),
        ("brunch", "Brunch"),
    )
    dietary = _sel(
        ("none", "None"),
        ("vegetarian", "Vegetarian"),
        ("vegan", "Vegan"),
        ("gluten_free", "Gluten-free"),
        ("halal", "Halal"),
    )

    return {
        "technical_name": "restaurant_management",
        "display_name": "Restaurant Management",
        "depends": ["base", "contacts", "mail"],
        "domain_pack": "restaurant",
        "tags": [
            "restaurant",
            "dining",
            "table",
            "reservation",
            "booking",
            "menu",
            "kitchen",
            "pos",
            "order",
            "waiter",
            "server",
            "food service",
            "cafe",
            "bistro",
        ],
        "anti_patterns": [
            "Do NOT implement payment gateways or card capture — x_bill is link-only",
            "Do NOT invent x_customer mini-CRM — use res.partner + x_partner_id",
            "Kitchen tickets are order lines — do not add a separate payment model",
            "Party/guest role rows are NOT is_workflow",
        ],
        "models": [
            {
                "model": "x_restaurant",
                "description": "Restaurant / Venue",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {"name": "x_code", "ttype": "char", "string": "Code"},
                    {"name": "x_address", "ttype": "char", "string": "Address"},
                    {"name": "x_phone", "ttype": "char", "string": "Phone"},
                    {
                        "name": "x_table_ids",
                        "ttype": "one2many",
                        "string": "Tables",
                        "relation": "x_dining_table",
                        "relation_field": "x_restaurant_id",
                    },
                ],
            },
            {
                "model": "x_dining_table",
                "description": "Dining Table",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Table", "required": True},
                    {"name": "x_seats", "ttype": "integer", "string": "Seats"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": table_status,
                        "required": True,
                    },
                    {
                        "name": "x_restaurant_id",
                        "ttype": "many2one",
                        "string": "Restaurant",
                        "relation": "x_restaurant",
                        "required": True,
                    },
                    {"name": "x_section", "ttype": "char", "string": "Section"},
                ],
            },
            {
                "model": "x_menu_category",
                "description": "Menu Category",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Category", "required": True},
                    {"name": "x_sequence", "ttype": "integer", "string": "Sequence"},
                    {
                        "name": "x_item_ids",
                        "ttype": "one2many",
                        "string": "Items",
                        "relation": "x_menu_item",
                        "relation_field": "x_category_id",
                    },
                ],
            },
            {
                "model": "x_menu_item",
                "description": "Menu Item",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Item", "required": True},
                    {"name": "x_price", "ttype": "float", "string": "Price"},
                    {"name": "x_description", "ttype": "text", "string": "Description"},
                    {
                        "name": "x_category_id",
                        "ttype": "many2one",
                        "string": "Category",
                        "relation": "x_menu_category",
                    },
                    {
                        "name": "x_dietary",
                        "ttype": "selection",
                        "string": "Dietary",
                        "selection": dietary,
                    },
                    {"name": "x_active", "ttype": "boolean", "string": "Active"},
                ],
            },
            {
                "model": "x_server",
                "description": "Wait Staff",
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
                        "name": "x_restaurant_id",
                        "ttype": "many2one",
                        "string": "Restaurant",
                        "relation": "x_restaurant",
                    },
                ],
            },
            {
                "model": "x_reservation",
                "description": "Table Reservation",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "state_field": {
                    "field": "x_status",
                    "transitions": [
                        ["draft", "confirmed"],
                        ["confirmed", "seated"],
                        ["seated", "completed"],
                        ["draft", "cancelled"],
                        ["confirmed", "cancelled"],
                        ["confirmed", "no_show"],
                    ],
                    "states": ["draft", "confirmed", "seated", "completed", "no_show", "cancelled"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Reference", "required": True},
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
                        "selection": reservation_status,
                        "required": True,
                    },
                    {
                        "name": "x_table_id",
                        "ttype": "many2one",
                        "string": "Table",
                        "relation": "x_dining_table",
                    },
                    {
                        "name": "x_restaurant_id",
                        "ttype": "many2one",
                        "string": "Restaurant",
                        "relation": "x_restaurant",
                        "required": True,
                    },
                    {"name": "x_party_size", "ttype": "integer", "string": "Party Size"},
                    {"name": "x_start", "ttype": "datetime", "string": "Start", "required": True},
                    {"name": "x_end", "ttype": "datetime", "string": "End"},
                    {
                        "name": "x_meal_period",
                        "ttype": "selection",
                        "string": "Meal Period",
                        "selection": meal_period,
                    },
                    {
                        "name": "x_server_id",
                        "ttype": "many2one",
                        "string": "Server",
                        "relation": "x_server",
                    },
                ],
            },
            {
                "model": "x_order",
                "description": "Dining Order",
                "mode": "new",
                "is_workflow": True,
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "state_field": {
                    "field": "x_status",
                    "transitions": [
                        ["draft", "confirmed"],
                        ["confirmed", "in_kitchen"],
                        ["in_kitchen", "ready"],
                        ["ready", "served"],
                        ["draft", "cancelled"],
                        ["confirmed", "cancelled"],
                    ],
                    "states": ["draft", "confirmed", "in_kitchen", "ready", "served", "cancelled"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Order", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Guest",
                        "relation": "res.partner",
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": order_status,
                        "required": True,
                    },
                    {
                        "name": "x_table_id",
                        "ttype": "many2one",
                        "string": "Table",
                        "relation": "x_dining_table",
                    },
                    {
                        "name": "x_restaurant_id",
                        "ttype": "many2one",
                        "string": "Restaurant",
                        "relation": "x_restaurant",
                        "required": True,
                    },
                    {
                        "name": "x_server_id",
                        "ttype": "many2one",
                        "string": "Server",
                        "relation": "x_server",
                    },
                    {
                        "name": "x_reservation_id",
                        "ttype": "many2one",
                        "string": "Reservation",
                        "relation": "x_reservation",
                    },
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "string": "Lines",
                        "relation": "x_order_line",
                        "relation_field": "x_order_id",
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
                "model": "x_order_line",
                "description": "Order Line / Kitchen Ticket",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Line", "required": True},
                    {
                        "name": "x_order_id",
                        "ttype": "many2one",
                        "string": "Order",
                        "relation": "x_order",
                        "required": True,
                    },
                    {
                        "name": "x_menu_item_id",
                        "ttype": "many2one",
                        "string": "Menu Item",
                        "relation": "x_menu_item",
                        "required": True,
                    },
                    {"name": "x_qty", "ttype": "float", "string": "Qty", "required": True},
                    {"name": "x_unit_price", "ttype": "float", "string": "Unit Price"},
                    {"name": "x_notes", "ttype": "text", "string": "Special Instructions"},
                    {
                        "name": "x_kitchen_status",
                        "ttype": "selection",
                        "string": "Kitchen Status",
                        "selection": line_kitchen,
                        "required": True,
                    },
                ],
            },
            {
                "model": "x_bill",
                "description": "Bill / Invoice Link",
                "mode": "new",
                "mixins": ["mail.thread"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Bill", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Customer",
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
                        "name": "x_order_id",
                        "ttype": "many2one",
                        "string": "Order",
                        "relation": "x_order",
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
                "on_model": "x_order",
                "label": "Lines",
                "related_model": "x_order_line",
                "relation_field": "x_order_id",
                "icon": "fa-list",
            },
            {
                "on_model": "x_restaurant",
                "label": "Tables",
                "related_model": "x_dining_table",
                "relation_field": "x_restaurant_id",
                "icon": "fa-th",
            },
        ],
        "automations": [
            {
                "name": "Activity on new reservation",
                "model": "x_reservation",
                "trigger": "on_create",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Confirm reservation with guest"}
                ],
            },
            {
                "name": "Mark table seated on reservation seated",
                "model": "x_reservation",
                "trigger": "on_write",
                "filter_domain": "[('x_status', '=', 'seated'), ('x_table_id', '!=', False)]",
                "safe_actions": [
                    {
                        "kind": "related_write",
                        "relation_field": "x_table_id",
                        "field": "x_status",
                        "value": "seated",
                    }
                ],
            },
            {
                "name": "Kitchen follow-up when order in kitchen",
                "model": "x_order",
                "trigger": "on_write",
                "filter_domain": "[('x_status', '=', 'in_kitchen')]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Expedite kitchen tickets"}
                ],
            },
        ],
        "reuse_hints": [
            {"model": "res.partner", "reason": "Guests and walk-in customers as Contacts"},
            {"model": "res.users", "reason": "Map wait staff login via x_server.x_user_id only"},
        ],
    }


__all__ = ["restaurant_pack"]
