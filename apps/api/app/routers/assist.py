"""HOWDO-01: how-do-I assistant routes (contract only).

Each handler calls exactly one injected engine function. The default engines say
plainly that the assistant is not available yet; engine cards replace them.
Nothing here calls Odoo. Every error except 401 leaves as the B5 envelope.
Tenancy: the token route's engine resolves the body connection in the caller's
workspace; /ask takes its connection from the short token (never from the body).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.assist.auth import HowdoPrincipal, require_howdo_token
from app.assist.contract import (
    AskFn,
    AssistAnswer,
    AssistAsk,
    AssistTokenRequest,
    HowdoToken,
    MintFn,
)
from app.auth import require_api_auth
from app.routers.scans import ScanEnvelopeRoute
from app.scans.contract import ScanError, ScanErrorEnvelope
from app.workspace_auth import get_workspace_auth

_ERRORS: dict[int | str, dict[str, Any]] = {
    s: {"model": ScanErrorEnvelope} for s in (403, 404, 422)
}

router = APIRouter(
    prefix="/bridge-assist",
    tags=["bridge-assist"],
    route_class=ScanEnvelopeRoute,
    responses=_ERRORS,
)


def token_caller(request: Request, _key: None = Depends(require_api_auth)) -> str | None:
    """Integration-key caller (bridge addon controller); returns its workspace id."""
    return get_workspace_auth(request).workspace_id


def ask_principal(principal: HowdoPrincipal = Depends(require_howdo_token)) -> HowdoPrincipal:
    if principal.scope != "ask":
        raise ScanError("ROLE_DENIED", "This token can't ask the assistant.")
    return principal


def _not_ready(*_a: Any) -> Any:
    raise ScanError("NOT_FOUND", "The how-do-I assistant isn't available on this server yet.")


def mint_engine() -> MintFn:
    return _not_ready


def ask_engine() -> AskFn:
    return _not_ready


@router.post("/token", response_model=HowdoToken)
def mint_token(
    body: AssistTokenRequest,
    caller: str | None = Depends(token_caller),
    engine: MintFn = Depends(mint_engine),
) -> HowdoToken:
    return engine(caller, body)


@router.post("/ask", response_model=AssistAnswer)
def ask(
    body: AssistAsk,
    principal: HowdoPrincipal = Depends(ask_principal),
    engine: AskFn = Depends(ask_engine),
) -> AssistAnswer:
    return engine(principal, body)
