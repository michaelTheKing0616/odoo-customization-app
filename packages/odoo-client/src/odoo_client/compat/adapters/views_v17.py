"""Odoo 17 view-inject — inherit naming like v19; create/store list as ``tree``."""

from __future__ import annotations

from odoo_client.compat.adapters.views_v16 import (  # noqa: F401
    default_window_view_mode,
    list_arch_root,
    list_type_fallbacks,
    normalize_view_mode,
)
from odoo_client.compat.adapters.views_v19 import (  # noqa: F401
    ALLOWED_INJECT_STRATEGIES,
    DEFAULT_INJECT_STRATEGY,
    InjectStrategy,
    custom_field_view_name,
    normalize_inject_strategy,
    smart_buttons_view_name,
)


def default_field_inject_view_types() -> list[str]:
    return ["form", "tree", "search"]


__all__ = [
    "ALLOWED_INJECT_STRATEGIES",
    "DEFAULT_INJECT_STRATEGY",
    "InjectStrategy",
    "custom_field_view_name",
    "default_field_inject_view_types",
    "default_window_view_mode",
    "list_arch_root",
    "list_type_fallbacks",
    "normalize_inject_strategy",
    "normalize_view_mode",
    "smart_buttons_view_name",
]
