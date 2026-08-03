"""Access rights + simple record rules (Studio ACL parity)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odoo_client import (
    CreateAccessRightRequest,
    CreateRecordRuleRequest,
    UpdateAccessRightRequest,
    UpdateRecordRuleRequest,
)

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import (
    ConfirmAdvancedBody,
    DeleteAccessOut,
    DeleteRuleOut,
    UpdateAccessBody,
    UpdateRuleBody,
)
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
    snapshot_access,
    snapshot_rule,
)

router = APIRouter(prefix="/connections/{connection_id}/access", tags=["access"])


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _confirm_http(exc: ConfirmationRequired) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "requires_confirmation": True,
            "confirm_phrase": CONFIRM_PHRASE,
            "warning": exc.warning,
            "risks": exc.risks,
        },
    )


class GroupOut(BaseModel):
    id: int
    name: str
    full_name: str | None = None
    share: bool = False


class AccessRightOut(BaseModel):
    id: int
    name: str
    model: str
    model_id: int
    group_id: int | None = None
    group_name: str | None = None
    perm_read: bool
    perm_write: bool
    perm_create: bool
    perm_unlink: bool
    active: bool


class CreateAccessBody(BaseModel):
    model: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    group_id: int | None = None
    perm_read: bool = True
    perm_write: bool = True
    perm_create: bool = True
    perm_unlink: bool = True
    active: bool = True


class RecordRuleOut(BaseModel):
    id: int
    name: str
    model: str
    model_id: int
    domain_force: str | None = None
    group_ids: list[int] = Field(default_factory=list)
    perm_read: bool
    perm_write: bool
    perm_create: bool
    perm_unlink: bool
    active: bool
    global_: bool = Field(False, alias="global")

    model_config = {"populate_by_name": True}


class CreateRuleBody(BaseModel):
    model: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    domain_force: str = Field(..., min_length=1)
    group_ids: list[int] = Field(default_factory=list)
    perm_read: bool = True
    perm_write: bool = True
    perm_create: bool = True
    perm_unlink: bool = True
    active: bool = True


@router.get("/groups", response_model=list[GroupOut])
def list_groups(connection_id: str, db: Session = Depends(get_db)) -> list[GroupOut]:
    client = _client(connection_id, db)
    try:
        rows = client.list_groups()
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [GroupOut.model_validate(r.model_dump()) for r in rows]


@router.get("/rights", response_model=list[AccessRightOut])
def list_rights(
    connection_id: str,
    model: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[AccessRightOut]:
    client = _client(connection_id, db)
    try:
        rows = client.list_access_rights(model=model)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [AccessRightOut.model_validate(r.model_dump()) for r in rows]


class MatrixCell(BaseModel):
    model: str
    group_id: int | None = None
    access_id: int | None = None
    name: str | None = None
    perm_read: bool = False
    perm_write: bool = False
    perm_create: bool = False
    perm_unlink: bool = False
    active: bool = True


class AccessMatrixOut(BaseModel):
    models: list[str]
    groups: list[GroupOut]
    cells: list[MatrixCell]


@router.get("/matrix", response_model=AccessMatrixOut)
def access_matrix(
    connection_id: str,
    models: str = Query(
        ...,
        description="Comma-separated technical model names",
        min_length=1,
    ),
    db: Session = Depends(get_db),
) -> AccessMatrixOut:
    """Groups × models ACL grid for Studio-style access editing."""
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    if not model_list:
        raise HTTPException(status_code=400, detail="Provide at least one model")
    if len(model_list) > 40:
        raise HTTPException(status_code=400, detail="At most 40 models per matrix request")

    client = _client(connection_id, db)
    try:
        groups = client.list_groups()
        cells: list[MatrixCell] = []
        for model in model_list:
            for row in client.list_access_rights(model=model):
                cells.append(
                    MatrixCell(
                        model=row.model,
                        group_id=row.group_id,
                        access_id=row.id,
                        name=row.name,
                        perm_read=row.perm_read,
                        perm_write=row.perm_write,
                        perm_create=row.perm_create,
                        perm_unlink=row.perm_unlink,
                        active=row.active,
                    )
                )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AccessMatrixOut(
        models=model_list,
        groups=[GroupOut.model_validate(g.model_dump()) for g in groups],
        cells=cells,
    )


@router.post("/rights", response_model=AccessRightOut, status_code=201)
def create_right(
    connection_id: str, body: CreateAccessBody, db: Session = Depends(get_db)
) -> AccessRightOut:
    client = _client(connection_id, db)
    try:
        created = client.create_access_right(
            CreateAccessRightRequest(
                model=body.model,
                name=body.name,
                group_id=body.group_id,
                perm_read=body.perm_read,
                perm_write=body.perm_write,
                perm_create=body.perm_create,
                perm_unlink=body.perm_unlink,
                active=body.active,
            )
        )
        try:
            from app.snapshots import snapshot_created_access

            snapshot_created_access(db, connection_id, client, created.id)
        except Exception:  # noqa: BLE001 — snapshot best-effort after create
            pass
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AccessRightOut.model_validate(created.model_dump())


@router.patch("/rights/{access_id}", response_model=AccessRightOut)
def update_right(
    connection_id: str,
    access_id: int,
    body: UpdateAccessBody,
    db: Session = Depends(get_db),
) -> AccessRightOut:
    client = _client(connection_id, db)
    try:
        snapshot_access(db, connection_id, client, access_id)
    except Exception:  # noqa: BLE001 — snapshot best-effort before mutate
        pass
    try:
        updated = client.update_access(
            access_id,
            UpdateAccessRightRequest(
                name=body.name,
                group_id=body.group_id,
                clear_group=body.clear_group,
                perm_read=body.perm_read,
                perm_write=body.perm_write,
                perm_create=body.perm_create,
                perm_unlink=body.perm_unlink,
                active=body.active,
            ),
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AccessRightOut.model_validate(updated.model_dump())


@router.delete("/rights/{access_id}", response_model=DeleteAccessOut)
def delete_right(
    connection_id: str,
    access_id: int,
    body: ConfirmAdvancedBody,
    db: Session = Depends(get_db),
) -> DeleteAccessOut:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Deleting an access right changes who can read/write this model.",
            risks=[
                "Users may lose or gain unintended access",
                "Can lock operators out of custom models if no other ACL remains",
                "Snapshot allows restoring the access line when possible",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        snap = snapshot_access(db, connection_id, client, access_id)
        client.delete_access(access_id)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DeleteAccessOut(ok=True, access_id=access_id, snapshot_id=snap.id)


@router.get("/rules", response_model=list[RecordRuleOut])
def list_rules(
    connection_id: str,
    model: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[RecordRuleOut]:
    client = _client(connection_id, db)
    try:
        rows = client.list_record_rules(model=model)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        RecordRuleOut.model_validate(r.model_dump(by_alias=True)) for r in rows
    ]


@router.post("/rules", response_model=RecordRuleOut, status_code=201)
def create_rule(
    connection_id: str, body: CreateRuleBody, db: Session = Depends(get_db)
) -> RecordRuleOut:
    client = _client(connection_id, db)
    try:
        created = client.create_record_rule(
            CreateRecordRuleRequest(
                model=body.model,
                name=body.name,
                domain_force=body.domain_force,
                group_ids=body.group_ids,
                perm_read=body.perm_read,
                perm_write=body.perm_write,
                perm_create=body.perm_create,
                perm_unlink=body.perm_unlink,
                active=body.active,
            )
        )
        try:
            from app.snapshots import snapshot_created_rule

            snapshot_created_rule(db, connection_id, client, created.id)
        except Exception:  # noqa: BLE001 — snapshot best-effort after create
            pass
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RecordRuleOut.model_validate(created.model_dump(by_alias=True))


@router.patch("/rules/{rule_id}", response_model=RecordRuleOut)
def update_rule(
    connection_id: str,
    rule_id: int,
    body: UpdateRuleBody,
    db: Session = Depends(get_db),
) -> RecordRuleOut:
    client = _client(connection_id, db)
    try:
        snapshot_rule(db, connection_id, client, rule_id)
    except Exception:  # noqa: BLE001 — snapshot best-effort before mutate
        pass
    try:
        updated = client.update_rule(
            rule_id,
            UpdateRecordRuleRequest(
                name=body.name,
                domain_force=body.domain_force,
                group_ids=body.group_ids,
                perm_read=body.perm_read,
                perm_write=body.perm_write,
                perm_create=body.perm_create,
                perm_unlink=body.perm_unlink,
                active=body.active,
            ),
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RecordRuleOut.model_validate(updated.model_dump(by_alias=True))


@router.delete("/rules/{rule_id}", response_model=DeleteRuleOut)
def delete_rule(
    connection_id: str,
    rule_id: int,
    body: ConfirmAdvancedBody,
    db: Session = Depends(get_db),
) -> DeleteRuleOut:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Deleting a record rule changes which records users can see or edit.",
            risks=[
                "May expose records previously filtered by domain",
                "Or hide records if other rules still apply",
                "Snapshot allows restoring the rule definition when possible",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        snap = snapshot_rule(db, connection_id, client, rule_id)
        client.delete_rule(rule_id)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DeleteRuleOut(ok=True, rule_id=rule_id, snapshot_id=snap.id)


class MultiCompanyGuidanceOut(BaseModel):
    title: str
    body: str


class ApplyMultiCompanyDraftBody(BaseModel):
    draft: dict[str, Any] = Field(default_factory=dict)


class ApplyMultiCompanyDraftOut(BaseModel):
    ok: bool
    draft: dict[str, Any]


class ApplyMultiCompanyLiveBody(BaseModel):
    models: list[str] = Field(..., min_length=1)


class ApplyMultiCompanyLiveOut(BaseModel):
    ok: bool
    models: list[str]
    fields_created: int
    rules_created: int
    warnings: list[str] = Field(default_factory=list)


@router.get("/multi-company/guidance", response_model=MultiCompanyGuidanceOut)
def get_multi_company_guidance() -> MultiCompanyGuidanceOut:
    from app.multi_company_pack import multi_company_guidance

    return MultiCompanyGuidanceOut(**multi_company_guidance())


@router.post("/multi-company/apply-draft", response_model=ApplyMultiCompanyDraftOut)
def apply_multi_company_draft(body: ApplyMultiCompanyDraftBody) -> ApplyMultiCompanyDraftOut:
    from app.multi_company_pack import apply_multi_company_to_draft

    return ApplyMultiCompanyDraftOut(
        ok=True,
        draft=apply_multi_company_to_draft(body.draft or {}),
    )


@router.post("/multi-company/apply-live", response_model=ApplyMultiCompanyLiveOut)
def apply_multi_company_live_route(
    connection_id: str,
    body: ApplyMultiCompanyLiveBody,
    db: Session = Depends(get_db),
) -> ApplyMultiCompanyLiveOut:
    from app.multi_company_pack import apply_multi_company_live

    client = _client(connection_id, db)
    result = apply_multi_company_live(client, body.models)
    return ApplyMultiCompanyLiveOut.model_validate(result)


class MultiCompanyGuidanceOut(BaseModel):
    title: str
    body: str


class ApplyMultiCompanyDraftBody(BaseModel):
    draft: dict[str, Any] = Field(default_factory=dict)


class ApplyMultiCompanyDraftOut(BaseModel):
    ok: bool
    draft: dict[str, Any]


class ApplyMultiCompanyLiveBody(BaseModel):
    models: list[str] = Field(..., min_length=1)


class ApplyMultiCompanyLiveOut(BaseModel):
    ok: bool
    models: list[str]
    fields_created: int
    rules_created: int
    warnings: list[str] = Field(default_factory=list)


@router.get("/multi-company/guidance", response_model=MultiCompanyGuidanceOut)
def get_multi_company_guidance() -> MultiCompanyGuidanceOut:
    from app.multi_company_pack import multi_company_guidance

    return MultiCompanyGuidanceOut(**multi_company_guidance())


@router.post("/multi-company/apply-draft", response_model=ApplyMultiCompanyDraftOut)
def apply_multi_company_draft(body: ApplyMultiCompanyDraftBody) -> ApplyMultiCompanyDraftOut:
    from app.multi_company_pack import apply_multi_company_to_draft

    return ApplyMultiCompanyDraftOut(
        ok=True,
        draft=apply_multi_company_to_draft(body.draft or {}),
    )


@router.post("/multi-company/apply-live", response_model=ApplyMultiCompanyLiveOut)
def apply_multi_company_live_route(
    connection_id: str,
    body: ApplyMultiCompanyLiveBody,
    db: Session = Depends(get_db),
) -> ApplyMultiCompanyLiveOut:
    from app.multi_company_pack import apply_multi_company_live

    client = _client(connection_id, db)
    result = apply_multi_company_live(client, body.models)
    return ApplyMultiCompanyLiveOut.model_validate(result)
