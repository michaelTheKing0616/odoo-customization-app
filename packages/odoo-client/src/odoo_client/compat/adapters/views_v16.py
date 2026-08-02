"""Odoo 16 view-inject — same inherit naming; prefer tree via list_type_fallbacks."""

from __future__ import annotations

from odoo_client.compat.adapters.views_v19 import (  # noqa: F401
    ALLOWED_INJECT_STRATEGIES,
    DEFAULT_INJECT_STRATEGY,
    InjectStrategy,
    custom_field_view_name,
    default_field_inject_view_types,
    normalize_inject_strategy,
    smart_buttons_view_name,
)


def list_type_fallbacks(view_type: str) -> list[str]:
    """Odoo 16 stores list views primarily as ``tree``."""
    if view_type == "list":
        return ["tree", "list"]
    if view_type == "tree":
        return ["tree", "list"]
    return [view_type]


def list_arch_root(view_type: str = "list") -> str:
    """XML root tag for a list/tree view arch on this major (``tree`` on ≤17)."""
    return "tree" if list_type_fallbacks(view_type)[0] == "tree" else "list"


def normalize_view_mode(view_mode: str) -> str:
    """Rewrite ``list`` → ``tree`` in act_window view_mode for Odoo ≤17."""
    parts = [p.strip() for p in (view_mode or "").split(",") if p.strip()]
    if not parts:
        return "tree,form"
    out: list[str] = []
    for p in parts:
        if p == "list":
            out.append("tree")
        else:
            out.append(p)
    return ",".join(out)


def default_window_view_mode() -> str:
    return normalize_view_mode("list,form")


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
