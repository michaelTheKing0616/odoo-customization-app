"""Form-bound Odoo actions — server actions, related windows, smart-button bundles."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odoo_client import (
    CreateRelatedWindowAction,
    CreateUpdateFieldServerAction,
)
from odoo_client.actions import (
    CreateMailPostServerAction,
    CreateNextActivityServerAction,
    CreateRelatedCountField,
    CreateSmartButtonBundle,
    assert_safe_server_state,
)

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired, require_advanced_confirmation

router = APIRouter(prefix="/connections/{connection_id}/actions", tags=["actions"])


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class BindableActionOut(BaseModel):
    id: int
    name: str
    action_type: Literal["ir.actions.server", "ir.actions.act_window"]
    model: str
    detail: str | None = None


class ServerActionOut(BaseModel):
    id: int
    name: str
    model: str
    model_id: int
    state: str
    binding_model_id: int | None = None
    binding_type: str | None = None


class WindowActionOut(BaseModel):
    id: int
    name: str
    res_model: str
    view_mode: str
    domain: str | None = None
    context: str | None = None


class CreateUpdateFieldActionBody(BaseModel):
    name: str
    model: str
    field_name: str
    value: str
    bind_to_model: bool = True


class CreateNextActivityBody(BaseModel):
    name: str
    model: str
    activity_type_id: int
    summary: str = "Follow up"
    note: str | None = None
    user_type: Literal["specific", "generic"] = "generic"
    user_id: int | None = None
    user_field_name: str | None = None
    bind_to_model: bool = True


class CreateMailPostBody(BaseModel):
    name: str
    model: str
    template_id: int | None = None
    mail_post_method: Literal["email", "comment", "note"] = "email"
    subject: str | None = None
    body_html: str | None = None
    email_to: str | None = None
    bind_to_model: bool = True


class CreateRelatedWindowBody(BaseModel):
    name: str
    source_model: str
    target_model: str
    relation_field: str
    view_mode: str = "list,form"


class CreateSmartButtonBody(BaseModel):
    name: str
    source_model: str
    target_model: str
    relation_field: str
    one2many_field: str | None = None
    count_field_name: str | None = None
    create_count_field: bool = False
    icon: str = "fa-list"
    view_mode: str = "list,form"
    confirm_advanced: bool = False
    confirm_phrase: str | None = None


class SmartButtonBundleOut(BaseModel):
    window_action: WindowActionOut
    count_field: str | None = None
    count_field_id: int | None = None
    button_spec: dict[str, Any] = Field(default_factory=dict)


class ButtonBindHintOut(BaseModel):
    action_id: int
    action_type: str
    button_type: Literal["action"] = "action"
    name: str
    note: str


class MailTemplateOut(BaseModel):
    id: int
    name: str
    model: str | None = None
    subject: str | None = None


@router.get("/bindable", response_model=list[BindableActionOut])
def list_bindable(
    connection_id: str,
    model: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> list[BindableActionOut]:
    client = _client(connection_id, db)
    try:
        rows = client.list_bindable_actions(model)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [BindableActionOut.model_validate(r.model_dump()) for r in rows]


@router.get("/server", response_model=list[ServerActionOut])
def list_server(
    connection_id: str,
    model: str | None = None,
    db: Session = Depends(get_db),
) -> list[ServerActionOut]:
    client = _client(connection_id, db)
    try:
        rows = client.list_server_actions(model)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [ServerActionOut.model_validate(r.model_dump()) for r in rows]


@router.get("/mail-templates", response_model=list[MailTemplateOut])
def list_mail_templates(
    connection_id: str,
    model: str | None = None,
    db: Session = Depends(get_db),
) -> list[MailTemplateOut]:
    client = _client(connection_id, db)
    try:
        rows = client.list_mail_templates(model=model)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [
        MailTemplateOut(
            id=int(r["id"]),
            name=str(r.get("name") or ""),
            model=r.get("model") or None,
            subject=r.get("subject") or None,
        )
        for r in rows
    ]


@router.post("/server/update-field", response_model=ServerActionOut)
def create_update_field_action(
    connection_id: str,
    body: CreateUpdateFieldActionBody,
    db: Session = Depends(get_db),
) -> ServerActionOut:
    client = _client(connection_id, db)
    try:
        assert_safe_server_state("object_write")
        created = client.create_update_field_server_action(
            CreateUpdateFieldServerAction.model_validate(body.model_dump())
        )
        try:
            from app.snapshots import snapshot_action

            snapshot_action(
                db,
                connection_id,
                client,
                model="ir.actions.server",
                action_id=created.id,
                created=True,
            )
        except Exception:  # noqa: BLE001 — snapshot best-effort after create
            pass
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ServerActionOut.model_validate(created.model_dump())


@router.post("/server/next-activity", response_model=ServerActionOut)
def create_next_activity_action(
    connection_id: str,
    body: CreateNextActivityBody,
    db: Session = Depends(get_db),
) -> ServerActionOut:
    client = _client(connection_id, db)
    try:
        created = client.create_next_activity_server_action(
            CreateNextActivityServerAction.model_validate(body.model_dump())
        )
        try:
            from app.snapshots import snapshot_action

            snapshot_action(
                db,
                connection_id,
                client,
                model="ir.actions.server",
                action_id=created.id,
                created=True,
            )
        except Exception:  # noqa: BLE001 — snapshot best-effort after create
            pass
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ServerActionOut.model_validate(created.model_dump())


@router.post("/server/mail-post", response_model=ServerActionOut)
def create_mail_post_action(
    connection_id: str,
    body: CreateMailPostBody,
    db: Session = Depends(get_db),
) -> ServerActionOut:
    client = _client(connection_id, db)
    try:
        created = client.create_mail_post_server_action(
            CreateMailPostServerAction.model_validate(body.model_dump())
        )
        try:
            from app.snapshots import snapshot_action

            snapshot_action(
                db,
                connection_id,
                client,
                model="ir.actions.server",
                action_id=created.id,
                created=True,
            )
        except Exception:  # noqa: BLE001 — snapshot best-effort after create
            pass
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ServerActionOut.model_validate(created.model_dump())


@router.post("/window/related", response_model=WindowActionOut)
def create_related_window(
    connection_id: str,
    body: CreateRelatedWindowBody,
    db: Session = Depends(get_db),
) -> WindowActionOut:
    client = _client(connection_id, db)
    try:
        created = client.create_related_window_action(
            CreateRelatedWindowAction.model_validate(body.model_dump())
        )
        try:
            from app.snapshots import snapshot_action

            snapshot_action(
                db,
                connection_id,
                client,
                model="ir.actions.act_window",
                action_id=created.id,
                created=True,
            )
        except Exception:  # noqa: BLE001 — snapshot best-effort after create
            pass
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return WindowActionOut.model_validate(created.model_dump())


@router.post("/smart-button", response_model=SmartButtonBundleOut)
def create_smart_button_bundle(
    connection_id: str,
    body: CreateSmartButtonBody,
    db: Session = Depends(get_db),
) -> SmartButtonBundleOut:
    """Related window + optional computed count field (confirm required for compute)."""
    if body.create_count_field:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    "Creating a computed count field runs Odoo compute code on the model "
                    "(equation/compute). Review before using on production data."
                ),
                risks=[
                    "Compute runs with ORM privileges on this database",
                    "Bad depends/compute can slow form loads",
                    "Field removal may leave residual metadata",
                ],
            )
        except ConfirmationRequired as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "requires_confirmation": True,
                    "confirm_phrase": CONFIRM_PHRASE,
                    "warning": exc.warning,
                    "risks": exc.risks,
                },
            ) from exc

    client = _client(connection_id, db)
    try:
        # Best-effort: snapshot related form view if present before inject.
        try:
            from app.snapshots import snapshot_view

            form = client.find_view(
                body.source_model, "form", primary_only=True
            ) or client.find_view(body.source_model, "form")
            if form is not None:
                snapshot_view(db, connection_id, client, form.id)
        except Exception:  # noqa: BLE001
            pass
        created = client.create_smart_button_bundle(
            CreateSmartButtonBundle.model_validate(
                body.model_dump(
                    exclude={"confirm_advanced", "confirm_phrase"},
                )
            )
        )
        try:
            from app.snapshots import snapshot_action

            snapshot_action(
                db,
                connection_id,
                client,
                model="ir.actions.act_window",
                action_id=created.window_action.id,
                created=True,
            )
        except Exception:  # noqa: BLE001 — snapshot best-effort after create
            pass
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SmartButtonBundleOut(
        window_action=WindowActionOut.model_validate(created.window_action.model_dump()),
        count_field=created.count_field,
        count_field_id=created.count_field_id,
        button_spec=created.button_spec,
    )


@router.post("/count-field")
def create_count_field(
    connection_id: str,
    body: CreateRelatedCountField,
    confirm_advanced: bool = False,
    confirm_phrase: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        require_advanced_confirmation(
            confirm_advanced=confirm_advanced,
            confirm_phrase=confirm_phrase,
            warning="Computed count fields use Odoo field compute (advanced).",
            risks=[
                "Compute runs with ORM privileges",
                "May impact form performance",
            ],
        )
    except ConfirmationRequired as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "requires_confirmation": True,
                "confirm_phrase": CONFIRM_PHRASE,
                "warning": exc.warning,
                "risks": exc.risks,
            },
        ) from exc
    client = _client(connection_id, db)
    try:
        field = client.create_related_count_field(body)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return field.model_dump()


@router.get("/bind-hint", response_model=ButtonBindHintOut)
def bind_hint(
    connection_id: str,
    action_id: int = Query(...),
    action_type: Literal["ir.actions.server", "ir.actions.act_window"] = Query(
        "ir.actions.server"
    ),
) -> ButtonBindHintOut:
    _ = connection_id
    return ButtonBindHintOut(
        action_id=action_id,
        action_type=action_type,
        name=str(action_id),
        note=(
            f'<button name="{action_id}" type="action" string="…"/> — '
            "works for ir.actions.server and ir.actions.act_window ids. "
            "type=object needs a Python method (Option A module)."
        ),
    )
