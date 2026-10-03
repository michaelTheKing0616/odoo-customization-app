"""Path policy for client_approver and client_viewer.

These roles are not a rung on the consultant ladder. A grant names the
connections they may see. Every other route is refused, and a connection id
outside the grant is hidden (404) so the API does not confirm it exists.
"""

from __future__ import annotations

import re

Decision = str  # allow | deny | hide

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
    if role == "client_approver" and _APPROVAL_DECIDE.match(path) and method == "POST":
        return "allow"
    return "deny"
