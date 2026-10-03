"""Forbidden RPC checks that cannot be turned off.

Every ``OdooClient.execute_kw`` runs this before the optional ``rpc_guard`` hook.
Approval flags are not accepted here. A forbidden call never reaches the transport.
"""

from __future__ import annotations

from typing import Any

NEVER_ALLOWED: tuple[tuple[str, str], ...] = (
    ("res.users", "unlink"),
    ("res.company", "unlink"),
    ("ir.model.data", "unlink"),
    ("ir.config_parameter", "unlink"),
    ("res.users.apikeys", "*"),
)

PROTECTED_PARAMS: frozenset[str] = frozenset(
    {
        "database.secret",
        "database.uuid",
        "database.create_date",
        "web.base.url",
        "database.enterprise_code",
        "database.expiration_date",
    }
)

_READ_METHODS = frozenset(
    {
        "search",
        "search_read",
        "read",
        "search_count",
        "fields_get",
        "name_search",
        "default_get",
        "read_group",
        "formatted_read_group",
        "context_get",
        "exists",
        "get_views",
    }
)


def _touches_protected(obj: object) -> bool:
    if isinstance(obj, str):
        return obj in PROTECTED_PARAMS
    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(key, str) and key in PROTECTED_PARAMS:
                return True
            if isinstance(val, dict) and val.get("key") in PROTECTED_PARAMS:
                return True
            if _touches_protected(val):
                return True
        return False
    if isinstance(obj, (list, tuple)):
        return any(_touches_protected(item) for item in obj)
    return False


def builtin_forbidden(
    model: str,
    method: str,
    args: list[Any] | tuple[Any, ...] | None,
    kwargs: dict[str, Any] | None,
) -> str | None:
    """Return a reason string when the call must not be sent. Otherwise None."""
    for blocked_model, blocked_method in NEVER_ALLOWED:
        if model == blocked_model and (blocked_method == "*" or blocked_method == method):
            return "never_allowed"
    if _touches_protected(args) or _touches_protected(kwargs):
        return "protected_param"
    return None


def scrub_config_param_result(model: str, method: str, result: Any) -> Any:
    """Drop protected system parameters from read results.

    A search of all parameters returns their ids. The following read must not
    hand the secret value to the caller.
    """
    if model != "ir.config_parameter" or method not in _READ_METHODS:
        return result
    if isinstance(result, list):
        kept = []
        for row in result:
            if isinstance(row, dict) and row.get("key") in PROTECTED_PARAMS:
                continue
            kept.append(row)
        return kept
    if isinstance(result, dict) and result.get("key") in PROTECTED_PARAMS:
        return {}
    return result
