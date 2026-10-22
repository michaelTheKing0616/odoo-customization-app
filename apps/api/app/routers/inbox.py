"""Hash-bound approval inbox HTTP API."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.changeset.inbox import InboxError
from app.changeset.store import FreezeWindow, PlanStale, decide_plan, list_plans, submit_plan
from app.db import get_db
from app.workspace_auth import WorkspaceAuth, get_scoped_connection_or_404, get_workspace_auth, require_route_group

router = APIRouter(prefix="/inbox", tags=["inbox"])


class SubmitBody(BaseModel):
    connection_id: str = Field(min_length=1)
    requester_id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    environment: Literal["staging", "production"]
    known_models: list[str] = Field(min_length=1)
    changeset: list[dict[str, Any]] = Field(min_length=1, max_length=50)
    schema_slice: dict[str, Any] | None = None


class AllowedWindowBody(BaseModel):
    start: str = Field(min_length=1)
    end: str = Field(min_length=1)


class DecideBody(BaseModel):
    connection_id: str
    approver_id: str
    decision: str
    plan_hash: str = Field(min_length=1, max_length=128)
    schema_fp: str = Field(min_length=1, max_length=128)
    user_id: str | None = None
    simulation_passed: bool | None = None
    backup_id: str | None = None
    allowed_window: AllowedWindowBody | None = None
    domain_owner: bool | None = None
    role: str | None = None

    @field_validator("decision")
    @classmethod
    def _decision_choice(cls, value: str) -> str:
        if value == "deny-and-stop":
            value = "deny_and_stop"
        if value not in {"approve", "deny", "deny_and_stop"}:
            raise ValueError("decision must be approve, deny, or deny-and-stop")
        return value


@router.get("/plans")
def get_plans(
    connection_id: str,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(get_workspace_auth),
) -> dict:
    require_route_group(auth, "inbox_read")
    get_scoped_connection_or_404(db, connection_id, auth)
    return {"plans": list_plans(db, connection_id)}


@router.post("/plans")
def post_plan(
    body: SubmitBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(get_workspace_auth),
) -> dict:
    require_route_group(auth, "inbox_submit")
    get_scoped_connection_or_404(db, body.connection_id, auth)
    result = submit_plan(
        db,
        changeset=body.changeset,
        goal=body.goal,
        assumptions=body.assumptions,
        environment=body.environment,
        requester_id=body.requester_id,
        known_models=set(body.known_models),
        connection_id=body.connection_id,
        schema_slice=body.schema_slice,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail={"error": "plan_invalid", "report": result.get("report")})
    return result


@router.post("/plans/{plan_hash}/decide")
def post_decide(
    plan_hash: str,
    body: DecideBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(get_workspace_auth),
) -> dict:
    require_route_group(auth, "inbox_decide")
    get_scoped_connection_or_404(db, body.connection_id, auth)
    try:
        window = (
            {"start": body.allowed_window.start, "end": body.allowed_window.end}
            if body.allowed_window is not None
            else None
        )
        card = decide_plan(
            db,
            plan_hash,
            approver_id=body.approver_id,
            decision=body.decision,
            connection_id=body.connection_id,
            body_plan_hash=body.plan_hash,
            schema_fp=body.schema_fp,
            user_id=body.user_id,
            domain_owner=body.domain_owner,
            role=body.role,
            simulation_passed=body.simulation_passed,
            backup_id=body.backup_id,
            allowed_window=window,
        )
    except PlanStale as exc:
        raise HTTPException(status_code=409, detail={"error": "plan_stale"}) from exc
    except FreezeWindow as exc:
        raise HTTPException(status_code=409, detail={"error": "frozen"}) from exc
    except InboxError as exc:
        status = 404 if "not found" in str(exc) else 403
        raise HTTPException(status_code=status, detail={"error": str(exc)}) from exc
    return {"card": card}
