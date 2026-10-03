"""Security-family risk raises.

The catalog in ``ops.py`` stays the source for base risk. This module raises
that base when a group would imply admin, an ACL has no group, or a user is
assigned admin, system, or service. It does not call Odoo.
"""

from __future__ import annotations

from typing import Any

GROUP_MUST_NOT_IMPLY_ADMIN = "a group must not imply admin"
PRIVILEGED_ASSIGNMENT = "admin, system, or service assignment is prohibited"

_ACCESS_OPS = frozenset({"access.create", "access.update"})
_ADMIN_XMLIDS = frozenset({"base.group_system", "base.group_erp_manager"})
_ADMIN_TAILS = frozenset({"group_system", "group_erp_manager"})
_ADMIN_TOKENS = frozenset(
    {
        "admin",
        "administrator",
        "system",
        "settings",
        "access rights",
        "erp manager",
        "administration / settings",
        "administration / access rights",
    }
)
_SERVICE_TOKENS = frozenset({"service", "service account"})
_SERVICE_TAILS = frozenset({"group_service", "group_service_account"})
_IMPLY_FLAGS = ("admin", "implies_admin", "imply_admin", "implied_admin", "system")
_IMPLY_KEYS = ("implied_ids", "implies", "implied", "implied_groups", "implied_group_ids")
_ASSIGN_FLAGS = ("admin", "system", "service")
_ASSIGN_KEYS = ("groups", "group_ids", "group", "groups_id", "groups_ids")
_REF_KEYS = ("xmlid", "xml_id", "name", "full_name", "id", "group")
_WALK_LIMIT = 6


def security_base_raise(op_type: str, params: dict[str, Any] | None) -> str | None:
    """Catalog raise for a security op, before policy bumps.

    Inputs: op type and params. A missing params dict is treated as empty.
    Outputs: ``R4`` when the op would imply admin, create or update a
    group-less ACL, or assign admin, system, or service. Otherwise ``None``.
    Side effects: none.
    """
    body = params if isinstance(params, dict) else {}
    if op_type == "group.create" and group_implies_admin(body):
        return "R4"
    if op_type in _ACCESS_OPS and not body.get("group"):
        return "R4"
    if op_type == "user.groups.assign" and privileged_assignment(body):
        return "R4"
    return None


def group_implies_admin(params: dict[str, Any]) -> bool:
    """True when a group.create would imply the admin or system group.

    Inputs: op params. Implication is an admin flag or an implied-group
    reference, not the new group's own name.
    Outputs: True when an implication names admin or system.
    Side effects: none.
    """
    for key in _IMPLY_FLAGS:
        if params.get(key):
            return True
    for key in _IMPLY_KEYS:
        if key not in params:
            continue
        for ref in _refs(params.get(key)):
            if _is_admin_ref(ref):
                return True
    return False


def privileged_assignment(params: dict[str, Any]) -> bool:
    """True when a user group assignment grants admin, system, or service.

    Inputs: ``user.groups.assign`` params.
    Outputs: True for an admin, system, or service flag, or a group reference
    that names those privileges. An ordinary group such as ``base.group_user``
    is False.
    Side effects: none.
    """
    for key in _ASSIGN_FLAGS:
        if params.get(key):
            return True
    for key in _ASSIGN_KEYS:
        if key not in params:
            continue
        for ref in _refs(params.get(key)):
            if _is_admin_ref(ref) or _is_service_ref(ref):
                return True
    return False


def _is_admin_ref(value: str) -> bool:
    token = _token(value)
    if token in _ADMIN_XMLIDS or token in _ADMIN_TOKENS:
        return True
    return token.rsplit(".", 1)[-1] in _ADMIN_TAILS


def _is_service_ref(value: str) -> bool:
    token = _token(value)
    if token in _SERVICE_TOKENS:
        return True
    return token.rsplit(".", 1)[-1] in _SERVICE_TAILS


def _token(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _refs(value: Any, depth: int = 0) -> list[str]:
    if depth > _WALK_LIMIT:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        found: list[str] = []
        for key in _REF_KEYS:
            if key in value:
                found.extend(_refs(value[key], depth + 1))
        return found
    if isinstance(value, (list, tuple)):
        found = []
        for item in value:
            found.extend(_refs(item, depth + 1))
        return found
    return []
