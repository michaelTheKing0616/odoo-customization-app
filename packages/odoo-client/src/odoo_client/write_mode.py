"""Write-mode enforcement for Odoo RPC (TRUST-1)."""

from __future__ import annotations

WriteMode = str  # observer | standard | production

OBSERVER_ALLOWED_METHODS = frozenset(
    {
        "search",
        "search_read",
        "search_count",
        "read",
        "fields_get",
        "name_get",
        "name_search",
        "default_get",
        "load_views",
        "get_views",
        "check_access_rights",
        "check_access_rule",
        "exists",
        "formatted_read_group",
        "web_search_read",
        "web_read_group",
        "get_metadata",
        "has_group",
        "get_field_translations",
        "get_export_fields",
        "read_group",
        "message_fetch",
        "message_format",
    }
)

OBSERVER_BLOCKED_METHODS = frozenset(
    {
        "create",
        "write",
        "unlink",
        "copy",
        "toggle_active",
        "message_post",
        "message_subscribe",
        "message_unsubscribe",
        "action_archive",
        "action_unarchive",
    }
)


def observer_allows_method(method: str) -> bool:
    if method in OBSERVER_ALLOWED_METHODS:
        return True
    if method in OBSERVER_BLOCKED_METHODS:
        return False
    if method.startswith("action_") or method.startswith("button_"):
        return False
    return False


def is_rpc_blocked_in_observer(write_mode: WriteMode, method: str) -> bool:
    return write_mode == "observer" and not observer_allows_method(method)

