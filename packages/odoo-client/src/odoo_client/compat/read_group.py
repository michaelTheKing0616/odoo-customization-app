"""Aggregate RPC method per Odoo major (``read_group`` version-table row V31)."""

from __future__ import annotations

from typing import Any

from odoo_client.compat.version_table import difference

_LEGACY_FACT = "legacy"
_FORMATTED_FACTS = frozenset({"formatted added", "aggregates and tuples"})

_AGGREGATE_ALIASES = frozenset({"read_group", "formatted_read_group"})


def aggregate_rpc_method(major: int) -> str:
    """Return the ORM method name for grouped aggregates on ``major``."""
    fact = difference("read_group", major)
    if fact == _LEGACY_FACT:
        return "read_group"
    if fact in _FORMATTED_FACTS:
        return "formatted_read_group"
    raise ValueError(f"unsupported read_group fact {fact!r} on Odoo {major}")


def resolve_aggregate_rpc_method(method: str, major: int) -> str:
    """Map legacy or formatted caller names to the version-table method for ``major``."""
    if method not in _AGGREGATE_ALIASES:
        return method
    return aggregate_rpc_method(major)


def build_aggregate_execute_kw(
    domain: list[Any],
    fields: list[str],
    groupby: list[str],
    *,
    major: int,
    limit: int | None = None,
    offset: int = 0,
    orderby: str | bool = False,
    lazy: bool = True,
) -> tuple[str, list[Any], dict[str, Any]]:
    """Build ``(method, args, kwargs)`` for ``execute_kw(model, method, args, kwargs)``."""
    method = aggregate_rpc_method(major)
    kwargs: dict[str, Any] = {"offset": offset, "lazy": lazy}
    if limit is not None:
        kwargs["limit"] = limit
    if orderby is not False:
        kwargs["orderby"] = orderby
    return method, [domain, fields, groupby], kwargs
