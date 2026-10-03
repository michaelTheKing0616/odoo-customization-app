"""``name_search`` execute_kw shape per Odoo major (``name_search_kw`` version table)."""

from __future__ import annotations

from typing import Any

from odoo_client.compat.version_table import difference


def name_search_filter_param(major: int) -> str:
    """Return ``args`` (16–18) or ``domain`` (19–20) from the version table."""
    return difference("name_search_kw", major)


def build_name_search_execute_kw(
    name: str,
    *,
    major: int,
    limit: int = 100,
    operator: str = "ilike",
    filter_domain: list[Any] | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    """Build ``(args, kwargs)`` for ``execute_kw(model, 'name_search', args, kwargs)``."""
    param = name_search_filter_param(major)
    kwargs: dict[str, Any] = {"limit": limit}
    if operator != "ilike":
        kwargs["operator"] = operator
    domain = [] if filter_domain is None else list(filter_domain)
    if param == "domain":
        kwargs["domain"] = domain
        return [name], kwargs
    if param == "args":
        if domain:
            return [name, domain], kwargs
        return [name], kwargs
    raise ValueError(f"unsupported name_search_kw {param!r} on Odoo {major}")
