"""Path policy for client_approver and client_viewer.

These roles are not a rung on the consultant ladder. A grant names the
connections they may see. Every other route is refused, and a connection id
outside the grant is hidden (404) so the API does not confirm it exists.
"""

from __future__ import annotations

import re
from typing import Literal

Decision = str  # allow | deny | hide

RouteGroup = Literal[
    "account_self",
    "connections_list",
    "connections_mutate",
    "approvals_read",
    "approvals_decide",
    "inbox_read",
    "inbox_submit",
    "inbox_decide",
    "other_client_connection",
]

# Product roles: Owner/Admin/Consultant (builder in memberships), Client Approver, Client Viewer.
_WORKSPACE_CONSULTANT = frozenset(
    {
        "account_self",
        "connections_list",
        "connections_mutate",
        "approvals_read",
        "approvals_decide",
        "inbox_read",
        "inbox_submit",
        "inbox_decide",
    }
)

ROLE_CAPABILITIES: dict[str, frozenset[RouteGroup]] = {
    "owner": _WORKSPACE_CONSULTANT,
    "admin": _WORKSPACE_CONSULTANT,
    "builder": _WORKSPACE_CONSULTANT,
    "developer": _WORKSPACE_CONSULTANT,
    "viewer": frozenset(
        {
            "account_self",
            "connections_list",
            "approvals_read",
            "inbox_read",
        }
    ),
    "client_approver": frozenset(
        {
            "account_self",
            "connections_list",
            "approvals_read",
            "approvals_decide",
            "inbox_read",
            "inbox_decide",
        }
    ),
    "client_viewer": frozenset(
        {
            "account_self",
            "connections_list",
            "approvals_read",
            "inbox_read",
        }
    ),
}

ROUTE_GROUPS: tuple[RouteGroup, ...] = (
    "account_self",
    "connections_list",
    "connections_mutate",
    "approvals_read",
    "approvals_decide",
    "inbox_read",
    "inbox_submit",
    "inbox_decide",
    "other_client_connection",
)

T6_MATRIX_ROLES: tuple[str, ...] = (
    "owner",
    "admin",
    "builder",
    "client_approver",
    "client_viewer",
)


def role_allows_route_group(role: str | None, group: RouteGroup) -> bool:
    if not role:
        return False
    caps = ROLE_CAPABILITIES.get(role)
    if caps is None:
        return False
    return group in caps

_CONNECTION_ID = re.compile(r"^/api/connections/([^/]+)(?:/|$)")
_APPROVAL_READ = re.compile(
    r"^/api/connections/([^/]+)/approvals/"
    r"(?:gate|entries|processes/gate|processes/requests)$"
)
_APPROVAL_DECIDE = re.compile(
    r"^/api/connections/([^/]+)/approvals/"
    r"(?:entries/[^/]+/approve|processes/requests/[^/]+/(?:approve|refuse))$"
)

_ACCOUNT_ALLOW = {
    ("GET", "/api/accounts/me"),
    ("POST", "/api/accounts/logout"),
    ("POST", "/api/accounts/totp/enroll"),
    ("POST", "/api/accounts/totp/verify"),
    ("POST", "/api/accounts/totp/disable"),
}


def client_request_decision(method: str, path: str, role: str, scope: frozenset[str]) -> Decision:
    method = method.upper()
    path = path.split("?", 1)[0].rstrip("/") or "/"
    if (method, path) in _ACCOUNT_ALLOW:
        return "allow"
    if method == "GET" and path == "/api/connections":
        return "allow"

    match = _CONNECTION_ID.match(path)
    if match is not None and match.group(1) not in scope:
        return "hide"

    if _APPROVAL_READ.match(path) and method == "GET":
        return "allow"
    if _APPROVAL_DECIDE.match(path) and method == "POST":
        return "allow" if role_allows_route_group(role, "approvals_decide") else "deny"

    if method == "GET" and path == "/api/inbox/plans":
        return "allow" if role_allows_route_group(role, "inbox_read") else "deny"
    if method == "POST" and path == "/api/inbox/plans":
        return "deny"
    if method == "POST" and re.match(r"^/api/inbox/plans/[^/]+/decide$", path):
        return "allow" if role_allows_route_group(role, "inbox_decide") else "deny"

    return "deny"
