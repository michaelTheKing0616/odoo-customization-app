"""BOT-APPROVAL-TIERS: list pending bot plans, show the plan card, approve or reject.

Tier, record count and card are server-computed (app.bots.approval); the request body
carries nothing that can change them. Deciding needs a signed-in workspace owner/admin who
is not the requester; every decision is written to the hash-chained bot audit log.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.bots.approval import ApprovalError, ApprovalStore
from app.db import get_db
from app.workspace_auth import WorkspaceAuth, get_scoped_connection_or_404, get_workspace_auth

router = APIRouter(prefix="/connections/{connection_id}/bot-approvals", tags=["bot-approvals"])

StoreFor = Callable[[str], ApprovalStore]  # actor -> store whose switch owner is that actor
_STATUS = {"not_found": 404, "conflict": 409, "forbidden": 403}
_DECIDERS = ("owner", "admin")


def store_for() -> StoreFor:
    from app import db as appdb
    from app.bots.audit import AuditLog
    from app.bots.guard import KillSwitch

    def make(actor: str) -> ApprovalStore:
        eng = appdb.engine
        return ApprovalStore(eng, KillSwitch(eng, lambda _scope: actor or None), AuditLog(eng))

    return make


def _conn_id(connection_id: str, request: Request, db: Annotated[Session, Depends(get_db)]) -> str:
    row = get_scoped_connection_or_404(db, connection_id, get_workspace_auth(request))
    return str(row.id)


Conn = Annotated[str, Depends(_conn_id)]
Make = Annotated[StoreFor, Depends(store_for)]


def _decider(request: Request) -> str:
    auth: WorkspaceAuth = get_workspace_auth(request)
    who = (auth.email or auth.user_id or "").strip()
    if auth.mode != "accounts" or not who:
        raise HTTPException(403, "Sign in with your own account to approve or reject.")
    if not (auth.is_superadmin or (auth.role or "").lower() in _DECIDERS):
        raise HTTPException(403, "Only a workspace owner or admin can approve or reject.")
    return who


def _call(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except ApprovalError as exc:
        raise HTTPException(_STATUS.get(exc.code, 400), exc.message) from exc


@router.get("")
def list_approvals(conn: Conn, make: Make) -> dict:
    return {"items": _call(lambda: make("").list(conn))}


@router.get("/{approval_id}")
def get_approval(approval_id: str, conn: Conn, make: Make) -> dict:
    return _call(lambda: make("").get(conn, approval_id))


@router.post("/{approval_id}/approve")
def approve(
    approval_id: str,
    request: Request,
    conn: Conn,
    make: Make,
) -> dict:
    who = _decider(request)
    return _call(lambda: make(who).approve(conn, approval_id, who))


@router.post("/{approval_id}/reject")
def reject(
    approval_id: str,
    request: Request,
    conn: Conn,
    make: Make,
) -> dict:
    who = _decider(request)
    return _call(lambda: make(who).reject(conn, approval_id, who))
