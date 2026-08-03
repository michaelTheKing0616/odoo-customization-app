"""Enterprise driver HTTP endpoints (TIER-5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.ee_drivers import (
    EeDriverUnavailable,
    create_approval_rule,
    delete_approval_rule,
    driver_response_note,
    list_approval_rules,
    probe_all_drivers,
    read_approval_rule,
    update_approval_rule,
)
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404

router = APIRouter(prefix="/connections/{connection_id}/ee-drivers", tags=["ee-drivers"])


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _driver_http(exc: EeDriverUnavailable) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


class DriverStatusOut(BaseModel):
    driver_id: str
    label: str
    model: str | None = None
    available: bool
    verify_state: str
    reason: str
    verified_fields: list[str] = Field(default_factory=list)
    pending_fields: list[str] = Field(default_factory=list)
    requires_modules: list[str] = Field(default_factory=list)
    note: str | None = None


class ApprovalRuleOut(BaseModel):
    id: int
    data: dict[str, Any]
    verify_state: str
    note: str | None = None


class ApprovalRuleCreateBody(BaseModel):
    name: str | None = None
    model_id: int | None = None
    method: str | None = None
    action_id: int | None = None
    domain: str | list | None = None
    user_ids: list[int] | None = None
    group_id: int | None = None
    exclusive_user: bool | None = None
    notification_order: int | None = None
    active: bool | None = True


@router.get("/status", response_model=list[DriverStatusOut])
def get_driver_status(connection_id: str, db: Session = Depends(get_db)) -> list[DriverStatusOut]:
    client = _client(connection_id, db)
    rows = probe_all_drivers(client)
    return [
        DriverStatusOut(
            **{
                **s.to_dict(),
                "note": driver_response_note(s),
            }
        )
        for s in rows
    ]


@router.get("/approval-rules", response_model=list[ApprovalRuleOut])
def get_approval_rules(connection_id: str, db: Session = Depends(get_db)) -> list[ApprovalRuleOut]:
    client = _client(connection_id, db)
    try:
        rows, status = list_approval_rules(client)
    except EeDriverUnavailable as exc:
        raise _driver_http(exc) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    note = driver_response_note(status)
    return [
        ApprovalRuleOut(
            id=int(r["id"]),
            data=r,
            verify_state=status.verify_state,
            note=note,
        )
        for r in rows
    ]


@router.get("/approval-rules/{rule_id}", response_model=ApprovalRuleOut)
def get_approval_rule(
    connection_id: str, rule_id: int, db: Session = Depends(get_db)
) -> ApprovalRuleOut:
    client = _client(connection_id, db)
    try:
        row, status = read_approval_rule(client, rule_id)
    except EeDriverUnavailable as exc:
        raise _driver_http(exc) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApprovalRuleOut(
        id=int(row["id"]),
        data=row,
        verify_state=status.verify_state,
        note=driver_response_note(status),
    )


@router.post("/approval-rules", response_model=ApprovalRuleOut, status_code=201)
def post_approval_rule(
    connection_id: str, body: ApprovalRuleCreateBody, db: Session = Depends(get_db)
) -> ApprovalRuleOut:
    client = _client(connection_id, db)
    payload = body.model_dump(exclude_none=True)
    try:
        rule_id, status = create_approval_rule(client, payload)
        row, status = read_approval_rule(client, rule_id)
    except EeDriverUnavailable as exc:
        raise _driver_http(exc) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApprovalRuleOut(
        id=int(row["id"]),
        data=row,
        verify_state=status.verify_state,
        note=driver_response_note(status),
    )


@router.patch("/approval-rules/{rule_id}", response_model=ApprovalRuleOut)
def patch_approval_rule(
    connection_id: str,
    rule_id: int,
    body: ApprovalRuleCreateBody,
    db: Session = Depends(get_db),
) -> ApprovalRuleOut:
    client = _client(connection_id, db)
    payload = body.model_dump(exclude_none=True)
    try:
        update_approval_rule(client, rule_id, payload)
        row, status = read_approval_rule(client, rule_id)
    except EeDriverUnavailable as exc:
        raise _driver_http(exc) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApprovalRuleOut(
        id=int(row["id"]),
        data=row,
        verify_state=status.verify_state,
        note=driver_response_note(status),
    )


@router.delete("/approval-rules/{rule_id}", status_code=204)
def remove_approval_rule(
    connection_id: str, rule_id: int, db: Session = Depends(get_db)
) -> None:
    client = _client(connection_id, db)
    try:
        delete_approval_rule(client, rule_id)
    except EeDriverUnavailable as exc:
        raise _driver_http(exc) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
