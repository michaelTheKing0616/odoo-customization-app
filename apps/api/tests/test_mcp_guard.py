"""MCP stays read-only. A trigger is not an approval."""

from __future__ import annotations

import pytest

from app.mcp_guard import McpWriteForbidden, mcp_call, trigger_is_not_approval


def test_mcp_read_is_allowed() -> None:
    assert mcp_call("search_read") == "read"


def test_mcp_write_is_refused() -> None:
    with pytest.raises(McpWriteForbidden):
        mcp_call("write")
    with pytest.raises(McpWriteForbidden):
        mcp_call("unlink")


def test_trigger_existence_is_not_approval() -> None:
    assert trigger_is_not_approval(True) is False
