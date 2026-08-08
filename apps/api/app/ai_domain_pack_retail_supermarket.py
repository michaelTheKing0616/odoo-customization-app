"""Retail / supermarket domain pack — branches, store orders, promotions, transfers."""

from __future__ import annotations

from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def retail_supermarket_pack() -> dict[str, Any]:
    order_status = _sel(
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("picking", "Picking"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    )
    promo_status = _sel(
        ("draft", "Draft"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    )
    transfer_status = _sel(
        ("draft", "Draft"),
        ("in_transit", "In transit"),
        ("received", "Received"),
        ("cancelled", "Cancelled"),
    )

    return {
        "technical_name": "retail_supermarket",
        "display_name": "Retail Supermarket",
        "depends": ["base", "contacts", "mail", "product"],
        "domain_pack": "retail_supermarket",
        "tags": [
            "supermarket",
            "grocery",
            "retail",
            "store",
            "shop",
            "mega",
            "branch",
            "branches",
            "chain",
            "inventory",
            "purchase",
            "supplier",
            "promotion",
            "pos",
            "warehouse",
        ],
        "reuse_stock": [
            {
                "model": "product.template",
                "modules": ["product"],
                "reason": "Product catalog (installed Products app)",
                "forbid_parallel": ["x_product", "x_product_template"],
            },
            {
                "model": "product.product",
                "modules": ["product"],
                "reason": "Product variants",
                "forbid_parallel": ["x_product"],
            },
            {
                "model": "uom.uom",
                "modules": ["uom"],
                "reason": "Units of measure for pack sizes",
            },
            {
                "model": "purchase.order",
                "modules": ["purchase"],
                "reason": "Supplier purchase orders (link-only)",
                "link_only": True,
            },
            {
                "model": "sale.order",
                "modules": ["sale"],
                "reason": "Customer sales orders (link-only)",
                "link_only": True,
                "forbid_parallel": ["x_sale_order"],
            },
            {
                "model": "account.move",
                "modules": ["account"],
                "reason": "Invoices / bills (link-only)",
                "link_only": True,
                "forbid_parallel": ["x_invoice", "x_bill"],
            },
            {
                "model": "stock.warehouse",
                "modules": ["stock"],
                "reason": "Warehouse / stock locations (link-only)",
                "link_only": True,
                "forbid_parallel": ["x_warehouse"],
            },
        ],
        "vocab": {
            "deposit": "Supplier deposit",
            "retainer": "Supplier deposit",
            "compliance": "Food safety check",
            "conflict check": "Supplier approval",
            "matter": "Store record",
        },
        "display_prefix": "Super Market",
        "anti_patterns": [
            "Do NOT duplicate product.template as x_product — reuse stock Products",
            "Do NOT implement payment capture — link purchase/sale documents only",
            "Branch is x_branch — not a selection on orders alone",
            "Supplier is res.partner with supplier rank — not x_supplier mini-CRM",
        ],
        "models": [
            {
                "model": "x_branch",
                "description": "Branch / Store location",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Branch", "required": True},
                    {"name": "x_code", "ttype": "char", "string": "Code"},
                    {"name": "x_address", "ttype": "char", "string": "Address"},
                    {"name": "x_phone", "ttype": "char", "string": "Phone"},
                    {
                        "name": "x_manager_id",
                        "ttype": "many2one",
                        "relation": "res.users",
                        "string": "Manager",
                    },
                    {
                        "name": "x_company_id",
                        "ttype": "many2one",
                        "relation": "res.company",
                        "string": "Company",
                    },
                    {
                        "name": "x_order_ids",
                        "ttype": "one2many",
                        "string": "Store orders",
                        "relation": "x_store_order",
                        "relation_field": "x_branch_id",
                    },
                ],
            },
            {
                "model": "x_store_order",
                "description": "Store sales order",
                "mode": "new",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Order", "required": True},
                    {"name": "x_code", "ttype": "char", "string": "Reference"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": order_status,
                        "required": True,
                    },
                    {
                        "name": "x_branch_id",
                        "ttype": "many2one",
                        "relation": "x_branch",
                        "string": "Branch",
                        "required": True,
                    },
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Customer",
                    },
                    {
                        "name": "x_date_order",
                        "ttype": "datetime",
                        "string": "Order date",
                    },
                    {
                        "name": "x_amount_total",
                        "ttype": "float",
                        "string": "Total",
                    },
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "relation": "res.currency",
                        "string": "Currency",
                    },
                    {
                        "name": "x_line_ids",
                        "ttype": "one2many",
                        "string": "Lines",
                        "relation": "x_store_order_line",
                        "relation_field": "x_order_id",
                    },
                ],
            },
            {
                "model": "x_store_order_line",
                "description": "Order line",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Description", "required": True},
                    {
                        "name": "x_order_id",
                        "ttype": "many2one",
                        "relation": "x_store_order",
                        "string": "Order",
                        "required": True,
                    },
                    {
                        "name": "x_product_id",
                        "ttype": "many2one",
                        "relation": "product.product",
                        "string": "Product",
                    },
                    {"name": "x_qty", "ttype": "float", "string": "Quantity", "required": True},
                    {"name": "x_price_unit", "ttype": "float", "string": "Unit price"},
                    {"name": "x_subtotal", "ttype": "float", "string": "Subtotal"},
                ],
            },
            {
                "model": "x_promotion",
                "description": "Promotion / discount campaign",
                "mode": "new",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Promotion", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": promo_status,
                        "required": True,
                    },
                    {"name": "x_date_start", "ttype": "date", "string": "Start"},
                    {"name": "x_date_end", "ttype": "date", "string": "End"},
                    {"name": "x_discount_pct", "ttype": "float", "string": "Discount %"},
                    {
                        "name": "x_branch_id",
                        "ttype": "many2one",
                        "relation": "x_branch",
                        "string": "Branch",
                    },
                ],
            },
            {
                "model": "x_branch_transfer",
                "description": "Inter-branch stock transfer",
                "mode": "new",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Transfer", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": transfer_status,
                        "required": True,
                    },
                    {
                        "name": "x_branch_from_id",
                        "ttype": "many2one",
                        "relation": "x_branch",
                        "string": "From branch",
                        "required": True,
                    },
                    {
                        "name": "x_branch_to_id",
                        "ttype": "many2one",
                        "relation": "x_branch",
                        "string": "To branch",
                        "required": True,
                    },
                    {"name": "x_date_scheduled", "ttype": "datetime", "string": "Scheduled"},
                    {
                        "name": "x_product_id",
                        "ttype": "many2one",
                        "relation": "product.product",
                        "string": "Product",
                    },
                    {"name": "x_qty", "ttype": "float", "string": "Quantity"},
                ],
            },
            {
                "model": "x_supplier_agreement",
                "description": "Supplier terms / rebate",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Agreement", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                        "string": "Supplier",
                        "required": True,
                    },
                    {
                        "name": "x_branch_id",
                        "ttype": "many2one",
                        "relation": "x_branch",
                        "string": "Branch",
                    },
                    {"name": "x_rebate_pct", "ttype": "float", "string": "Rebate %"},
                    {"name": "x_date_start", "ttype": "date", "string": "Start"},
                    {"name": "x_date_end", "ttype": "date", "string": "End"},
                ],
            },
            {
                "model": "x_staff_shift",
                "description": "Staff shift / roster line",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Shift", "required": True},
                    {
                        "name": "x_branch_id",
                        "ttype": "many2one",
                        "relation": "x_branch",
                        "string": "Branch",
                        "required": True,
                    },
                    {
                        "name": "x_employee_id",
                        "ttype": "many2one",
                        "relation": "hr.employee",
                        "string": "Employee",
                    },
                    {"name": "x_date_start", "ttype": "datetime", "string": "Start"},
                    {"name": "x_date_end", "ttype": "datetime", "string": "End"},
                    {"name": "x_hours", "ttype": "float", "string": "Hours"},
                ],
            },
            {
                "model": "x_inventory_count",
                "description": "Stock count session",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Count", "required": True},
                    {
                        "name": "x_branch_id",
                        "ttype": "many2one",
                        "relation": "x_branch",
                        "string": "Branch",
                        "required": True,
                    },
                    {"name": "x_date", "ttype": "date", "string": "Count date", "required": True},
                    {
                        "name": "x_product_id",
                        "ttype": "many2one",
                        "relation": "product.product",
                        "string": "Product",
                    },
                    {"name": "x_qty_system", "ttype": "float", "string": "System qty"},
                    {"name": "x_qty_counted", "ttype": "float", "string": "Counted qty"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            },
        ],
        "smart_buttons": [],
        "automations": [],
    }
