"""Odoo 19 view-inject naming and strategy policies (extracted from OdooClient).

Arch XML builders stay in ``view_arch.py``; this module owns stable view names
and inject strategy allowlists so future majors can diverge without router ifs.
"""

from __future__ import annotations

from typing import Literal

InjectStrategy = Literal["inherit", "mutate"]

DEFAULT_INJECT_STRATEGY: InjectStrategy = "inherit"
ALLOWED_INJECT_STRATEGIES: frozenset[str] = frozenset({"inherit", "mutate"})


def smart_buttons_view_name(model: str, *, override: str | None = None) -> str:
    """Stable inherit name — must not change per apply (see ERRORS.md stacking)."""
    return override or f"{model}.studio.smart_buttons"


def custom_field_view_name(model: str, field_name: str, view_type: str) -> str:
    return f"{model}.custom.{field_name}.{view_type}"


def default_field_inject_view_types() -> list[str]:
    return ["form", "list", "search"]


def normalize_inject_strategy(strategy: str) -> InjectStrategy:
    if strategy not in ALLOWED_INJECT_STRATEGIES:
        raise ValueError(
            f"Unknown inject strategy {strategy!r}; "
            f"allowed: {sorted(ALLOWED_INJECT_STRATEGIES)}"
        )
    return strategy  # type: ignore[return-value]


def list_type_fallbacks(view_type: str) -> list[str]:
    """Search order for view type aliases (Odoo 17+ list may still be tree)."""
    if view_type == "list":
        return ["list", "tree"]
    return [view_type]


def list_arch_root(view_type: str = "list") -> str:
    """XML root tag for a list/tree view arch on this major (``list`` on 18+)."""
    primary = list_type_fallbacks(view_type)[0]
    return "tree" if primary == "tree" else "list"


def normalize_view_mode(view_mode: str) -> str:
    """Normalize act_window ``view_mode`` tokens for this major.

    On 18/19, ``list`` is preferred; callers may still pass ``tree`` (kept as-is
    unless rewriting list aliases — 19 accepts both in many places).
    """
    parts = [p.strip() for p in (view_mode or "").split(",") if p.strip()]
    if not parts:
        return "list,form"
    out: list[str] = []
    for p in parts:
        if p == "tree":
            out.append(list_type_fallbacks("list")[0])
        else:
            out.append(p)
    return ",".join(out)


def default_window_view_mode() -> str:
    return normalize_view_mode("list,form")


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
