"""Library management domain pack — books, loans, fines, reservations, branches."""

from __future__ import annotations

from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def library_management_pack() -> dict[str, Any]:
    loan_status = _sel(
        ("draft", "Draft"),
        ("active", "Active"),
        ("returned", "Returned"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    )
    book_status = _sel(
        ("available", "Available"),
        ("loaned", "Loaned"),
        ("reserved", "Reserved"),
        ("lost", "Lost"),
    )
    reservation_status = _sel(
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
    )
    fine_status = _sel(
        ("draft", "Draft"),
        ("open", "Open"),
        ("paid", "Paid"),
        ("waived", "Waived"),
    )

    return {
        "technical_name": "library_management",
        "display_name": "Library Management",
        "depends": ["base", "contacts", "mail", "product"],
        "domain_pack": "library_management",
        "tags": [
            "library",
            "libraries",
            "library management",
            "sophisticated",
            "book",
            "books",
            "loan",
            "loans",
            "member",
            "members",
            "isbn",
            "barcode",
            "reservation",
            "reservations",
            "fine",
            "fines",
            "overdue",
            "reminder",
            "reminders",
            "catalog",
            "author",
            "branch",
            "branches",
            "management",
        ],
        "reuse_stock": [
            {
                "model": "res.partner",
                "modules": ["contacts"],
                "reason": "Library members (link-only)",
                "link_only": True,
                "forbid_parallel": ["x_member", "x_lib_member"],
            },
            {
                "model": "product.product",
                "modules": ["product"],
                "reason": "Optional sellable items / fines SKU",
                "link_only": True,
            },
        ],
        "models": [
            {
                "model": "x_lib_branch",
                "description": "Library Branch",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Branch Name", "required": True},
                    {"name": "x_code", "ttype": "char", "string": "Code"},
                    {"name": "x_address", "ttype": "text", "string": "Address"},
                    {"name": "x_phone", "ttype": "char", "string": "Phone"},
                    {"name": "x_manager_id", "ttype": "many2one", "string": "Manager", "relation": "res.users"},
                ],
            },
            {
                "model": "x_lib_category",
                "description": "Book Category",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Category", "required": True},
                    {"name": "x_description", "ttype": "text", "string": "Description"},
                ],
            },
            {
                "model": "x_lib_author",
                "description": "Author",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Author Name", "required": True},
                    {"name": "x_bio", "ttype": "text", "string": "Biography"},
                    {"name": "x_country_id", "ttype": "many2one", "string": "Country", "relation": "res.country"},
                ],
            },
            {
                "model": "x_lib_book",
                "description": "Book",
                "mode": "new",
                "is_workflow": True,
                "state_field": {
                    "name": "x_status",
                    "selection": book_status,
                    "transitions": [
                        ("available", "loaned"),
                        ("available", "reserved"),
                        ("loaned", "available"),
                        ("reserved", "available"),
                        ("available", "lost"),
                    ],
                    "statusbar_visible": ["available", "loaned", "reserved"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Title", "required": True},
                    {"name": "x_isbn", "ttype": "char", "string": "ISBN"},
                    {"name": "x_barcode", "ttype": "char", "string": "Barcode"},
                    {"name": "x_copies", "ttype": "integer", "string": "Copies"},
                    {"name": "x_available_copies", "ttype": "integer", "string": "Available Copies"},
                    {"name": "x_status", "ttype": "selection", "string": "Status", "selection": book_status},
                    {"name": "x_fine_rate", "ttype": "float", "string": "Daily Fine Rate"},
                    {"name": "x_category_id", "ttype": "many2one", "string": "Category", "relation": "x_lib_category"},
                    {"name": "x_author_id", "ttype": "many2one", "string": "Author", "relation": "x_lib_author"},
                    {"name": "x_branch_id", "ttype": "many2one", "string": "Branch", "relation": "x_lib_branch"},
                    {
                        "name": "x_loan_ids",
                        "ttype": "one2many",
                        "string": "Loans",
                        "relation": "x_lib_loan",
                        "relation_field": "x_book_id",
                    },
                ],
            },
            {
                "model": "x_lib_loan",
                "description": "Book Loan",
                "mode": "new",
                "is_workflow": True,
                "state_field": {
                    "name": "x_status",
                    "selection": loan_status,
                    "transitions": [
                        ("draft", "active"),
                        ("active", "returned"),
                        ("active", "overdue"),
                        ("overdue", "returned"),
                        ("draft", "cancelled"),
                        ("active", "cancelled"),
                    ],
                    "statusbar_visible": ["draft", "active", "returned"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Reference", "required": True},
                    {"name": "x_status", "ttype": "selection", "string": "Status", "selection": loan_status},
                    {"name": "x_book_id", "ttype": "many2one", "string": "Book", "relation": "x_lib_book", "required": True},
                    {"name": "x_member_id", "ttype": "many2one", "string": "Member", "relation": "res.partner", "required": True},
                    {"name": "x_branch_id", "ttype": "many2one", "string": "Branch", "relation": "x_lib_branch"},
                    {"name": "x_loan_date", "ttype": "date", "string": "Loan Date"},
                    {"name": "x_due_date", "ttype": "date", "string": "Due Date"},
                    {"name": "x_return_date", "ttype": "date", "string": "Return Date"},
                    {"name": "x_returned", "ttype": "boolean", "string": "Returned"},
                    {"name": "x_days_overdue", "ttype": "integer", "string": "Days Overdue"},
                    {"name": "x_fine_amount", "ttype": "monetary", "string": "Fine Amount"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            },
            {
                "model": "x_lib_reservation",
                "description": "Book Reservation",
                "mode": "new",
                "is_workflow": True,
                "state_field": {
                    "name": "x_status",
                    "selection": reservation_status,
                    "transitions": [
                        ("pending", "confirmed"),
                        ("confirmed", "fulfilled"),
                        ("pending", "cancelled"),
                        ("confirmed", "cancelled"),
                    ],
                    "statusbar_visible": ["pending", "confirmed", "fulfilled"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Reference", "required": True},
                    {"name": "x_status", "ttype": "selection", "string": "Status", "selection": reservation_status},
                    {"name": "x_book_id", "ttype": "many2one", "string": "Book", "relation": "x_lib_book", "required": True},
                    {"name": "x_member_id", "ttype": "many2one", "string": "Member", "relation": "res.partner", "required": True},
                    {"name": "x_reservation_date", "ttype": "date", "string": "Reservation Date"},
                    {"name": "x_pickup_date", "ttype": "date", "string": "Pickup Date"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            },
            {
                "model": "x_lib_fine",
                "description": "Library Fine",
                "mode": "new",
                "is_workflow": True,
                "state_field": {
                    "name": "x_status",
                    "selection": fine_status,
                    "transitions": [
                        ("draft", "open"),
                        ("open", "paid"),
                        ("open", "waived"),
                        ("draft", "waived"),
                    ],
                    "statusbar_visible": ["draft", "open", "paid"],
                },
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Reference", "required": True},
                    {"name": "x_status", "ttype": "selection", "string": "Status", "selection": fine_status},
                    {"name": "x_loan_id", "ttype": "many2one", "string": "Loan", "relation": "x_lib_loan", "required": True},
                    {"name": "x_member_id", "ttype": "many2one", "string": "Member", "relation": "res.partner"},
                    {"name": "x_amount", "ttype": "monetary", "string": "Amount"},
                    {"name": "x_paid_date", "ttype": "date", "string": "Paid Date"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            },
        ],
        "vocab": {
            "loan": "Book loan",
            "fine": "Overdue fine",
            "reservation": "Book reservation",
            "member": "Library member",
            "reminder": "Overdue reminder",
            "sophisticated": "Advanced library",
            "management": "Library operations",
        },
        "automations": [
            {
                "name": "Mark loan overdue",
                "model": "x_lib_loan",
                "trigger": "on_write",
                "action_type": "object_write",
                "action_values": {"x_status": "overdue"},
                "filter_domain": "[('x_returned', '=', False), ('x_due_date', '<', context_today())]",
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_lib_book",
                "related_model": "x_lib_loan",
                "relation_field": "x_book_id",
                "label": "Loans",
            },
            {
                "on_model": "x_lib_loan",
                "related_model": "x_lib_fine",
                "relation_field": "x_loan_id",
                "label": "Fines",
            },
        ],
    }


__all__ = ["library_management_pack"]
