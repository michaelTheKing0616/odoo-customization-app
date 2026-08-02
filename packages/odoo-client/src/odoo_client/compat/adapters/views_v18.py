"""Odoo 18 view-inject policies — same naming/strategy as v19 for M2 safe subset."""

from __future__ import annotations

from odoo_client.compat.adapters.views_v19 import (  # noqa: F401
    ALLOWED_INJECT_STRATEGIES,
    DEFAULT_INJECT_STRATEGY,
    InjectStrategy,
    custom_field_view_name,
    default_field_inject_view_types,
    default_window_view_mode,
    list_arch_root,
    list_type_fallbacks,
    normalize_inject_strategy,
    normalize_view_mode,
    smart_buttons_view_name,
)

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
