"""Odoo 20 view tags. List is list. Tree is not the primary root."""

from __future__ import annotations

from odoo_client.compat.adapters.views_v19 import (
    ALLOWED_INJECT_STRATEGIES,
    DEFAULT_INJECT_STRATEGY,
    InjectStrategy,
    custom_field_view_name,
    default_field_inject_view_types,
    normalize_inject_strategy,
    smart_buttons_view_name,
)


def list_type_fallbacks(view_type: str) -> list[str]:
    if view_type in {"list", "tree"}:
        return ["list"]
    return [view_type]


def list_arch_root(view_type: str = "list") -> str:
    return "list" if view_type in {"list", "tree"} else view_type


def normalize_view_mode(view_mode: str) -> str:
    parts = [p.strip() for p in (view_mode or "").split(",") if p.strip()]
    return ",".join("list" if part == "tree" else part for part in parts)
