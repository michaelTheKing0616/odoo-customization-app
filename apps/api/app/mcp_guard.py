"""MCP is read-only from Ingenium. A write method is refused before any client is built."""

from __future__ import annotations

_READS = frozenset(
    {
        "search",
        "search_read",
        "read",
        "search_count",
        "fields_get",
        "read_group",
        "formatted_read_group",
    }
)


class McpWriteForbidden(Exception):
    pass


def mcp_call(method: str) -> str:
    if method not in _READS:
        raise McpWriteForbidden(f"MCP cannot call {method}")
    return "read"


def trigger_is_not_approval(trigger_exists: bool) -> bool:
    """A trigger existing does not approve the write it will perform."""
    del trigger_exists
    return False
