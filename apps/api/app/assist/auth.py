"""HOWDO-01: stub dependency for the bridge addon's short-lived assistant token.

The contract card does not check a real sign-in token (that is the later L3 card),
so this stub refuses every request with 401. Tests override it with a fake.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class HowdoPrincipal:
    connection_id: str
    odoo_uid: int | None
    scope: str


def require_howdo_token(request: Request) -> HowdoPrincipal:
    raw = request.headers.get("authorization", "")
    if not raw.lower().startswith("bearer ") or not raw[7:].strip():
        message = "Missing assistant token. Send Authorization: Bearer <token>."
    else:
        message = "Assistant tokens can't be checked on this server yet."
    raise HTTPException(
        status_code=401,
        detail={"error": "unauthorized", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )
