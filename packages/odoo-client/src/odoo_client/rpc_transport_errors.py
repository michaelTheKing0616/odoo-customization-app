"""XML-RPC exception types and the normalized Odoo transport errors.

``XmlRpcFault`` and ``XmlRpcProtocolError`` stay isinstance checks against the
stdlib classes. ``map_transport_error`` turns a fault, a JSON-2 body, or a
socket failure into one of the contract names. It does not open a connection.
"""

from __future__ import annotations

import re
import xmlrpc.client
from typing import Any

XmlRpcFault = xmlrpc.client.Fault
XmlRpcProtocolError = xmlrpc.client.ProtocolError


class OdooRpcError(Exception):
    """Normalized transport failure. Callers branch on the subclass."""


class AccessError(OdooRpcError):
    pass


class UserError(OdooRpcError):
    pass


class ValidationError(OdooRpcError):
    pass


class MissingError(OdooRpcError):
    pass


class RedirectWarning(OdooRpcError):
    pass


class ConcurrencyError(OdooRpcError):
    pass


class DeadlockDetected(OdooRpcError):
    pass


class Timeout(OdooRpcError):
    pass


class AuthFailed(OdooRpcError):
    pass


class ApiUnavailable(OdooRpcError):
    pass


class ServerError(OdooRpcError):
    pass


class Unknown(OdooRpcError):
    pass


# First match wins. AccessError is not UserError even though Odoo subclasses it.
_NAMED: tuple[tuple[str, type[OdooRpcError]], ...] = (
    ("DeadlockDetected", DeadlockDetected),
    ("SerializationFailure", ConcurrencyError),
    ("ConcurrencyError", ConcurrencyError),
    ("RedirectWarning", RedirectWarning),
    ("ValidationError", ValidationError),
    ("MissingError", MissingError),
    ("AccessDenied", AuthFailed),
    ("AccessError", AccessError),
    ("UserError", UserError),
)


def map_transport_error(
    error: BaseException | str,
    *,
    status: int | None = None,
    body: Any = None,
) -> OdooRpcError:
    """Map a transport failure onto the contract error names.

    Class names in a fault string or a JSON-2 ``name`` win over the HTTP
    status, so a 500 whose body is ``ValidationError`` stays a validation
    failure. Connection and timeout failures do not need an Odoo class name.
    """
    if isinstance(error, OdooRpcError):
        return error

    text = error if isinstance(error, str) else str(error)
    if not isinstance(error, str):
        fault = getattr(error, "faultString", None)
        if isinstance(fault, str) and fault:
            text = fault
        if status is None:
            raw_status = getattr(error, "status", None)
            if isinstance(raw_status, int):
                status = raw_status
        if body is None:
            body = getattr(error, "body", None)

    name = ""
    if isinstance(body, dict):
        name = str(body.get("name") or "")
        message = str(body.get("message") or "")
        text = "\n".join(part for part in (name, message, text) if part)

    named = _class_from_text(f"{name}\n{text}")
    if named is not None:
        return named(text or named.__name__)

    lower = text.lower()
    if "deadlock detected" in lower:
        return DeadlockDetected(text or "DeadlockDetected")
    if "could not serialize access" in lower or "concurrent update" in lower:
        return ConcurrencyError(text or "ConcurrencyError")
    if isinstance(error, TimeoutError) or "timed out" in lower:
        return Timeout(text or "Timeout")
    if any(
        phrase in lower
        for phrase in (
            "invalid apikey",
            "authentication failed",
            "access denied",
            "wrong login",
        )
    ):
        return AuthFailed(text or "AuthFailed")
    if isinstance(error, ConnectionError) or any(
        phrase in lower
        for phrase in (
            "connection refused",
            "name or service not known",
            "nodename nor servname",
            "network is unreachable",
            "connection reset",
            "temporarily unavailable",
        )
    ):
        return ApiUnavailable(text or "ApiUnavailable")

    if status in {401, 403}:
        return AuthFailed(text or "AuthFailed")
    if status in {408, 504}:
        return Timeout(text or "Timeout")
    if status in {502, 503}:
        return ApiUnavailable(text or "ApiUnavailable")
    if status is not None and status >= 500:
        return ServerError(text or "ServerError")
    return Unknown(text or "Unknown")


def _class_from_text(text: str) -> type[OdooRpcError] | None:
    for token, kind in _NAMED:
        if re.search(rf"\b{re.escape(token)}\b", text):
            return kind
    return None


__all__ = [
    "AccessError",
    "ApiUnavailable",
    "AuthFailed",
    "ConcurrencyError",
    "DeadlockDetected",
    "MissingError",
    "OdooRpcError",
    "RedirectWarning",
    "ServerError",
    "Timeout",
    "Unknown",
    "UserError",
    "ValidationError",
    "XmlRpcFault",
    "XmlRpcProtocolError",
    "map_transport_error",
]
