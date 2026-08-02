"""Version-specific adapters for Odoo RPC encoding."""

from odoo_client.compat.adapters import (
    automation_v16,
    automation_v17,
    automation_v18,
    automation_v19,
    views_v16,
    views_v17,
    views_v18,
    views_v19,
)

__all__ = [
    "automation_v16",
    "automation_v17",
    "automation_v18",
    "automation_v19",
    "views_v16",
    "views_v17",
    "views_v18",
    "views_v19",
]
