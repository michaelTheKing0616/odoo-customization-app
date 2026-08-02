"""Mutating customization endpoints (Phase 2: models & fields + Wave B delete)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from odoo_client import CreateFieldRequest, CreateModelRequest, FieldType

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import (
    ConfirmAdvancedBody,
    CreateFieldBody,
    CreateModelBody,
    CreateModelOut,
    DeleteFieldOut,
    DeleteModelOut,
    FieldCreateOut,
    FieldOut,
    ModelOut,
    RelationalPairBody,
    RelationalPairOut,
    UpdateFieldBody,
)
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
    snapshot_field,
    snapshot_model,
)

router = APIRouter(prefix="/connections/{connection_id}", tags=["builder"])


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


@router.post("/models", response_model=CreateModelOut, status_code=201)
def create_model(
    connection_id: str, body: CreateModelBody, db: Session = Depends(get_db)
) -> CreateModelOut:
    client = _client(connection_id, db)
    warnings: list[str] = []
    mail_thread_enabled = False
    try:
        created = client.create_model(
            CreateModelRequest(
                name=body.name,
                model=body.model,
                transient=body.transient,
            ),
            with_defaults=body.with_defaults,
        )
        if body.enable_mail_thread:
            # Full chatter requires Python export with mail.thread mixins.
            # Live ir.model may expose is_mail_thread — probe and set when present.
            try:
                client.ensure_module_installed("mail")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Could not ensure mail module: {exc}")
            try:
                fg = client.execute_kw(
                    "ir.model",
                    "fields_get",
                    [],
                    {"attributes": ["type", "string"]},
                )
            except Exception as exc:  # noqa: BLE001
                fg = {}
                warnings.append(f"fields_get on ir.model failed: {exc}")
            write_vals: dict = {}
            if isinstance(fg, dict) and "is_mail_thread" in fg:
                write_vals["is_mail_thread"] = True
            if isinstance(fg, dict) and "is_mail_activity" in fg:
                write_vals["is_mail_activity"] = True
            if write_vals:
                try:
                    client.execute_kw("ir.model", "write", [[created.id], write_vals])
                    mail_thread_enabled = True
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"Failed to set mail flags on ir.model: {exc}")
            else:
                warnings.append(
                    "is_mail_thread not available on ir.model in this Odoo 19 — "
                    "full chatter requires python module export with "
                    "mixins=['mail.thread', 'mail.activity.mixin']"
                )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface Odoo fault strings
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data = created.model_dump()
    data["warnings"] = warnings
    data["mail_thread_enabled"] = mail_thread_enabled
    try:
        snap = snapshot_model(
            db, connection_id, client, created.model, created=True
        )
        data["snapshot_id"] = snap.id
    except Exception:  # noqa: BLE001 — post-create snapshot best-effort (partial rollback)
        pass
    return CreateModelOut.model_validate(data)


@router.post("/fields/relational_pair", response_model=RelationalPairOut, status_code=201)
def create_relational_pair(
    connection_id: str, body: RelationalPairBody, db: Session = Depends(get_db)
) -> RelationalPairOut:
    """Create child M2O + parent O2M pair (Studio-like one2many-from-parent)."""
    client = _client(connection_id, db)
    warnings: list[str] = []
    m2o_created = False
    o2m_created = False
    injected_ids: list[int] = []
    try:
        if not client.model_exists(body.parent_model):
            raise HTTPException(
                status_code=400, detail=f"Parent model {body.parent_model!r} not found"
            )
        if not client.model_exists(body.child_model):
            raise HTTPException(
                status_code=400, detail=f"Child model {body.child_model!r} not found"
            )

        if not client.field_exists(body.child_model, body.child_m2o_name):
            client.create_field(
                CreateFieldRequest(
                    model=body.child_model,
                    name=body.child_m2o_name,
                    field_description=body.child_m2o_string,
                    ttype=FieldType.MANY2ONE,
                    required=True,
                    relation=body.parent_model,
                    on_delete="restrict",
                )
            )
            m2o_created = True
        else:
            warnings.append(
                f"{body.child_model}.{body.child_m2o_name} already exists — skipped M2O create"
            )

        if not client.field_exists(body.parent_model, body.parent_o2m_name):
            client.create_field(
                CreateFieldRequest(
                    model=body.parent_model,
                    name=body.parent_o2m_name,
                    field_description=body.parent_o2m_string,
                    ttype=FieldType.ONE2MANY,
                    relation=body.child_model,
                    relation_field=body.child_m2o_name,
                )
            )
            o2m_created = True
        else:
            warnings.append(
                f"{body.parent_model}.{body.parent_o2m_name} already exists — skipped O2M create"
            )

        if body.inject_into_views:
            # Inject O2M into parent form even if field already existed (idempotent inject)
            from app.snapshots import snapshot_view

            for view in client.list_views(body.parent_model, limit=50):
                if view.type == "form":
                    try:
                        snapshot_view(db, connection_id, client, view.id)
                    except Exception:  # noqa: BLE001
                        pass
            for view in client.inject_field_into_views(
                body.parent_model, body.parent_o2m_name, strategy="inherit"
            ):
                injected_ids.append(view.id)
    except HTTPException:
        raise
    except (ValidationError, ValueError) as exc:
        detail = exc.errors() if isinstance(exc, ValidationError) else str(exc)
        raise HTTPException(status_code=422, detail=detail) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RelationalPairOut(
        ok=True,
        parent_model=body.parent_model,
        child_model=body.child_model,
        parent_o2m_name=body.parent_o2m_name,
        child_m2o_name=body.child_m2o_name,
        m2o_created=m2o_created,
        o2m_created=o2m_created,
        injected_view_ids=injected_ids,
        warnings=warnings,
    )


@router.delete("/models/{model}", response_model=DeleteModelOut)
def delete_model(
    connection_id: str,
    model: str,
    body: ConfirmAdvancedBody,
    db: Session = Depends(get_db),
) -> DeleteModelOut:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                "Deleting a custom model removes its metadata from this database. "
                "Stored data and related views may be lost or left residual."
            ),
            risks=[
                "Often irreversible — dropped tables / records may not restore",
                "Dependent views, menus, and automations can break",
                "Snapshot stores definition only (reversible=partial)",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        snap = snapshot_model(db, connection_id, client, model)
        client.delete_model(model)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DeleteModelOut(ok=True, model=model, snapshot_id=snap.id)


@router.post("/fields", response_model=FieldCreateOut, status_code=201)
def create_field(
    connection_id: str, body: CreateFieldBody, db: Session = Depends(get_db)
) -> FieldCreateOut:
    strategy = body.inject_strategy or "inherit"
    if body.inject_into_views and strategy == "mutate":
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    "Mutating parent view arch overwrites existing module XML. "
                    "Prefer inherit (default) for interop with installed modules."
                ),
                risks=[
                    "Parent ir.ui.view arch is rewritten in place",
                    "Module upgrades may conflict or overwrite your change",
                    "Harder to uninstall cleanly than an extension view",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        ttype = FieldType(body.ttype)
        req = CreateFieldRequest(
            model=body.model,
            name=body.name,
            field_description=body.field_description,
            ttype=ttype,
            required=body.required,
            readonly=body.readonly,
            relation=body.relation,
            relation_field=body.relation_field,
            selection=body.selection_odoo_string(),
            help=body.help,
            related=body.related,
            currency_field=body.currency_field,
            on_delete=body.on_delete,
        )
        created = client.create_field(req)
        injected_ids: list[int] = []
        if body.inject_into_views:
            from app.snapshots import snapshot_view

            for view in client.list_views(body.model, limit=50):
                if view.type in {"form", "list", "search", "tree"}:
                    try:
                        snapshot_view(db, connection_id, client, view.id)
                    except Exception:  # noqa: BLE001 — best-effort; inject still proceeds
                        pass
            for view in client.inject_field_into_views(
                body.model,
                created.name,
                strategy=strategy,
                widget=body.view_widget,
            ):
                injected_ids.append(view.id)
    except (ValidationError, ValueError) as exc:
        detail = exc.errors() if isinstance(exc, ValidationError) else str(exc)
        raise HTTPException(status_code=422, detail=detail) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data = created.model_dump()
    data["injected_view_ids"] = injected_ids
    try:
        snap = snapshot_field(db, connection_id, client, created.id, created=True)
        data["snapshot_id"] = snap.id
    except Exception:  # noqa: BLE001 — post-create snapshot best-effort (partial rollback)
        pass
    return FieldCreateOut.model_validate(data)


@router.patch("/fields/{field_id}", response_model=FieldOut)
def update_field(
    connection_id: str,
    field_id: int,
    body: UpdateFieldBody,
    db: Session = Depends(get_db),
) -> FieldOut:
    """Safe metadata update — no advanced confirm (label/help/flags only)."""
    client = _client(connection_id, db)
    attrs = body.model_dump(exclude_none=True)
    if not attrs:
        raise HTTPException(status_code=422, detail="No fields to update")
    try:
        updated = client.update_field(field_id, **attrs)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FieldOut.model_validate(updated.model_dump())


@router.delete("/fields/{field_id}", response_model=DeleteFieldOut)
def delete_field(
    connection_id: str,
    field_id: int,
    body: ConfirmAdvancedBody,
    db: Session = Depends(get_db),
) -> DeleteFieldOut:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                "Deleting a custom field removes it from the model. "
                "Column data is often not recoverable."
            ),
            risks=[
                "Dropped DB columns / field data may be unrestorable",
                "Views referencing the field can break until edited",
                "Snapshot stores field definition only (reversible=partial)",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        snap = snapshot_field(db, connection_id, client, field_id)
        client.delete_field(field_id)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DeleteFieldOut(ok=True, field_id=field_id, snapshot_id=snap.id)
