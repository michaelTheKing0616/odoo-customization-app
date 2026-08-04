"""Mutating customization endpoints (Phase 2: models & fields + Wave B delete)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from odoo_client import CreateFieldRequest, CreateModelRequest, FieldType

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.protected_enforcement import (
    ProtectedViolation,
    check_field_create,
    check_field_delete_or_stock_mutate,
    check_invoicing_draft_create,
    check_model_delete,
    check_relational_pair,
    manifest_for_connection,
)
from app.protected_modules import protected_models_for, safe_alternative_for
from app.schemas import (
    ConfirmAdvancedBody,
    CreateFieldBody,
    CreateModelBody,
    CreateModelOut,
    DeleteFieldBody,
    DeleteFieldOut,
    DeleteModelOut,
    FieldCreateOut,
    FieldOut,
    ModelOut,
    PropertyDefinitionWriteBody,
    PropertyDefinitionWriteOut,
    PropertyFieldsProbeOut,
    PropertyFieldsSetupBody,
    PropertyFieldsSetupOut,
    InvoicingConnectBody,
    InvoicingConnectOut,
    InvoicingDraftInvoiceBody,
    InvoicingDraftInvoiceOut,
    InvoicingMergeSpecBody,
    InvoicingMergeSpecOut,
    InvoicingModuleSpecBody,
    InvoicingModuleSpecOut,
    InvoicingPreflightOut,
    RelationalPairBody,
    RelationalPairOut,
    UpdateFieldBody,
)
from app.field_lifecycle import FieldLifecycleError, deprecate_field, export_field_column_csv
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
    save_snapshot,
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


def _protected_http(violation: ProtectedViolation) -> HTTPException:
    return HTTPException(status_code=422, detail=violation.http_detail())


def _connection_and_manifest(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return row, manifest_for_connection(row)


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
    _row, manifest = _connection_and_manifest(connection_id, db)
    pair_viol = check_relational_pair(
        manifest, parent_model=body.parent_model, child_model=body.child_model
    )
    if pair_viol:
        raise _protected_http(pair_viol)

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
        from app.model_lifecycle import ModelLifecycleError, export_model_records_json
        from app.snapshots import save_snapshot

        data_export = export_model_records_json(client, model=model)
        data_artifact = save_snapshot(
            db,
            connection_id=connection_id,
            resource_type="model_data_export",
            resource_key=f"model_data:{model}",
            label=f"Record export {model} before delete",
            payload={
                "format": "model_records_json",
                "model": model,
                "json": data_export.json_text,
                "record_count": data_export.record_count,
                "truncated": data_export.truncated,
            },
            reversible="no",
        )
        snap = snapshot_model(db, connection_id, client, model)
        client.delete_model(model)
    except ModelLifecycleError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "model_export_failed", "message": str(exc)},
        ) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    artifact_url = f"/api/connections/{connection_id}/snapshots/{data_artifact.id}/artifact.json"
    return DeleteModelOut(
        ok=True,
        model=model,
        snapshot_id=snap.id,
        data_artifact_id=data_artifact.id,
        artifact_url=artifact_url,
        record_count=data_export.record_count,
        truncated=data_export.truncated,
        overflow_warning=data_export.overflow_warning,
    )


@router.get("/builder/niche-widgets")
def list_niche_widgets(
    view_type: str = Query("form", min_length=1),
) -> dict[str, object]:
    from odoo_client.niche_widget_catalog import COLOR_PALETTE, niche_widgets_for_view

    return {
        "widgets": [
            {
                "id": w.id,
                "label": w.label,
                "recommended_ttypes": list(w.recommended_ttypes),
                "view_types": list(w.view_types),
                "hint": w.hint,
                "supporting_field": w.supporting_field,
            }
            for w in niche_widgets_for_view(view_type)
        ],
        "color_palette": list(COLOR_PALETTE),
    }




@router.get("/builder/widgets")
def list_widgets(ttype: str = Query(..., min_length=1)) -> list[dict[str, str]]:
    from odoo_client.widget_catalog import widgets_for_ttype

    return [{"id": w.id, "label": w.label, "hint": w.hint} for w in widgets_for_ttype(ttype)]


@router.get("/builder/related-paths")
def related_paths(
    connection_id: str,
    model: str = Query(..., min_length=1),
    depth: int = Query(2, ge=1, le=2),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    from app.field_helpers import list_related_paths

    client = _client(connection_id, db)
    try:
        return list_related_paths(client, model, depth=depth)
    except (OdooClientError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/fields", response_model=FieldCreateOut, status_code=201)
def create_field(
    connection_id: str, body: CreateFieldBody, db: Session = Depends(get_db)
) -> FieldCreateOut:
    _row, manifest = _connection_and_manifest(connection_id, db)
    field_viol = check_field_create(
        manifest,
        model=body.model,
        ttype=body.ttype,
        relation=body.relation,
        field_name=body.name,
    )
    if field_viol:
        raise _protected_http(field_viol)

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
    currency_created = False
    try:
        from odoo_client.widget_catalog import validate_widget_for_ttype

        if body.view_widget:
            try:
                validate_widget_for_ttype(body.ttype, body.view_widget)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

        ttype = FieldType(body.ttype)
        currency_field = body.currency_field
        if ttype == FieldType.MONETARY:
            from app.field_helpers import ensure_currency_field_for_monetary

            currency_field, currency_created = ensure_currency_field_for_monetary(
                client, body.model, currency_field=currency_field
            )

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
            currency_field=currency_field,
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
    if currency_created:
        data["currency_field_created"] = currency_field
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
    body: DeleteFieldBody,
    db: Session = Depends(get_db),
) -> DeleteFieldOut:
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    mode = body.mode or "deprecate"
    if mode == "hard_delete":
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Hard-deleting field id={field_id} removes the column. "
                    "A CSV of id→value is exported first."
                ),
                risks=[
                    "Column data is removed from the database",
                    "Views referencing the field can break until edited",
                    "Operation refused if column export fails",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc
    elif not body.confirm_advanced:
        raise _confirm_http(
            ConfirmationRequired(
                warning=f"Deprecate field id={field_id} (rename to x_deprecated_* and hide)?",
                risks=[
                    "Field stays in the database under a new name",
                    "Views may still reference the old name until updated",
                    "Use hard delete only when you need the column dropped",
                ],
            )
        )

    client = _client(connection_id, db)
    try:
        raw = client.read_field_raw(field_id)
    except OdooClientError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    model_name = str(raw.get("model") or "")
    field_name = str(raw.get("name") or "")
    manifest = manifest_for_connection(row)
    violation = check_field_delete_or_stock_mutate(
        manifest, model=model_name, field_name=field_name
    )
    if violation is not None:
        raise _protected_http(violation)

    if mode == "deprecate":
        try:
            updated = deprecate_field(client, field_id)
            snap = snapshot_field(db, connection_id, client, field_id)
        except FieldLifecycleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OdooClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return DeleteFieldOut(
            ok=True,
            field_id=field_id,
            mode="deprecate",
            snapshot_id=snap.id,
            new_field_name=str(updated.get("name")),
        )

    try:
        export = export_field_column_csv(
            client, model=model_name, field_name=field_name
        )
    except FieldLifecycleError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "field_export_failed",
                "message": str(exc),
            },
        ) from exc

    artifact = save_snapshot(
        db,
        connection_id=connection_id,
        resource_type="field_data_export",
        resource_key=f"field_data:{field_id}",
        label=f"Column export {model_name}.{field_name}",
        payload={
            "format": "csv",
            "model": export.model,
            "field_name": export.field_name,
            "csv": export.csv_text,
            "row_count": export.row_count,
            "truncated": export.truncated,
        },
        reversible="no",
    )
    try:
        meta_snap = snapshot_field(db, connection_id, client, field_id)
        client.delete_field(field_id)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    artifact_url = f"/api/connections/{connection_id}/snapshots/{artifact.id}/artifact.csv"
    return DeleteFieldOut(
        ok=True,
        field_id=field_id,
        mode="hard_delete",
        snapshot_id=meta_snap.id,
        artifact_id=artifact.id,
        artifact_url=artifact_url,
        row_count=export.row_count,
        truncated=export.truncated,
    )


@router.get("/properties/probe", response_model=PropertyFieldsProbeOut)
def property_fields_probe(
    connection_id: str, db: Session = Depends(get_db)
) -> PropertyFieldsProbeOut:
    from app.property_fields_probe import probe_property_fields

    client = _client(connection_id, db)
    data = probe_property_fields(client)
    return PropertyFieldsProbeOut(
        major=int(data["major"]),
        source=str(data["source"]),
        supported=bool(data["supported"]),
        probe_table=[PropertyFieldsProbeRow.model_validate(r) for r in data["probe_table"]],
    )


@router.post("/properties/setup", response_model=PropertyFieldsSetupOut)
def property_fields_setup(
    connection_id: str,
    body: PropertyFieldsSetupBody,
    db: Session = Depends(get_db),
) -> PropertyFieldsSetupOut:
    from app.property_fields_service import ensure_properties_field_on_child
    from app.snapshots import require_advanced_confirmation

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                f"Create Properties field on {body.child_model} bound to "
                f"{body.parent_m2o_field} → {body.definition_field}."
            ),
            risks=[
                "Adds manual ir.model.fields rows on live Odoo",
                "Parent model receives a PropertiesDefinition field if missing",
                "Unsupported on Odoo majors that fail the property-fields probe",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    from app.property_fields_probe import probe_property_fields

    client = _client(connection_id, db)
    probe = probe_property_fields(client)
    if not probe.get("supported"):
        raise HTTPException(
            status_code=400,
            detail="Properties fields not supported on this Odoo major (see /properties/probe).",
        )
    try:
        result = ensure_properties_field_on_child(
            client,
            child_model=body.child_model,
            parent_m2o_field=body.parent_m2o_field,
            definition_field=body.definition_field,
            properties_field=body.properties_field,
            field_description=body.properties_label,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PropertyFieldsSetupOut(
        ok=True,
        properties_field=str(result["properties_field"]),
        definition_field=str(result["definition_field"]),
        parent_model=str(result["parent_model"]),
        created=bool(result.get("created")),
        definition_field_created=result.get("definition_field_created"),
    )


@router.post("/properties/definition", response_model=PropertyDefinitionWriteOut)
def write_property_definition(
    connection_id: str,
    body: PropertyDefinitionWriteBody,
    db: Session = Depends(get_db),
) -> PropertyDefinitionWriteOut:
    from app.property_fields_service import write_properties_definition
    from app.snapshots import require_advanced_confirmation

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                f"Write properties definition on {body.parent_model} "
                f"record {body.parent_record_id}."
            ),
            risks=[
                "Overwrites properties_definition JSON on the parent record",
                "Child records inherit the updated property schema",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        result = write_properties_definition(
            client,
            parent_model=body.parent_model,
            parent_record_id=body.parent_record_id,
            definition_field=body.definition_field,
            entries=[e.model_dump(exclude_none=True) for e in body.entries],
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PropertyDefinitionWriteOut.model_validate(result)


@router.get("/invoicing/preflight", response_model=InvoicingPreflightOut)
def invoicing_preflight(
    connection_id: str, db: Session = Depends(get_db)
) -> InvoicingPreflightOut:
    from app.invoicing_l10n import detect_l10n

    client = _client(connection_id, db)
    data = detect_l10n(client)
    return InvoicingPreflightOut.model_validate(data)


@router.post("/invoicing/connect", response_model=InvoicingConnectOut)
def invoicing_connect(
    connection_id: str,
    body: InvoicingConnectBody,
    db: Session = Depends(get_db),
) -> InvoicingConnectOut:
    from app.invoicing_connect import connect_live_metadata
    from app.invoicing_l10n import detect_l10n

    _row, manifest = _connection_and_manifest(connection_id, db)
    viol = check_field_create(
        manifest,
        model=body.model,
        ttype="many2many",
        relation="account.move",
        field_name=body.invoice_field,
    )
    if viol:
        raise _protected_http(viol)

    preflight = detect_l10n(_client(connection_id, db))
    if not preflight.get("account_installed"):
        raise HTTPException(
            status_code=400,
            detail=str(preflight.get("message") or "Accounting module not installed."),
        )

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                f"Connect {body.model} to Invoicing: adds {body.invoice_field} "
                "many2many → account.move (live-metadata path, no account.move fields)."
            ),
            risks=[
                "Creates ir.model.fields and act_window on live Odoo",
                "Draft invoices still require explicit create action",
                "Fiscal localization should be installed before billing go-live",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        result = connect_live_metadata(
            client,
            model=body.model,
            invoice_field=body.invoice_field,
            smart_button_name=body.smart_button_name,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InvoicingConnectOut.model_validate(result)


@router.post("/invoicing/draft-invoice", response_model=InvoicingDraftInvoiceOut)
def invoicing_draft_invoice(
    connection_id: str,
    body: InvoicingDraftInvoiceBody,
    db: Session = Depends(get_db),
) -> InvoicingDraftInvoiceOut:
    from app.invoicing_connect import create_draft_invoice_linked
    from app.invoicing_l10n import detect_l10n

    viol = check_invoicing_draft_create(source_model=body.source_model)
    if viol:
        raise _protected_http(viol)

    preflight = detect_l10n(_client(connection_id, db))
    if not preflight.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=str(preflight.get("message") or "Invoicing preflight failed."),
        )

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                f"Create draft customer invoice from {body.source_model} "
                f"record {body.record_id} (never posts)."
            ),
            risks=[
                "Creates account.move in draft on live Odoo",
                "Links invoice via many2many on the custom record",
                "Taxes/accounts use Odoo defaults — verify l10n is installed",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        result = create_draft_invoice_linked(
            client,
            source_model=body.source_model,
            record_id=body.record_id,
            invoice_field=body.invoice_field,
            partner_field=body.partner_field,
            amount_field=body.amount_field,
            description_field=body.description_field,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InvoicingDraftInvoiceOut.model_validate(result)


@router.post("/invoicing/module-spec", response_model=InvoicingModuleSpecOut)
def invoicing_module_spec(
    connection_id: str,
    body: InvoicingModuleSpecBody,
    db: Session = Depends(get_db),
) -> InvoicingModuleSpecOut:
    from app.invoicing_connect import module_spec_fragment

    if not body.model.startswith("x_"):
        raise HTTPException(status_code=400, detail="Module spec requires custom x_* model")
    fragment = module_spec_fragment(
        model=body.model,
        invoice_field=body.invoice_field,
        origin_field_on_move=body.origin_field_on_move,
        partner_field=body.partner_field,
    )
    return InvoicingModuleSpecOut(ok=True, fragment=fragment)


@router.post("/invoicing/merge-into-spec", response_model=InvoicingMergeSpecOut)
def invoicing_merge_into_spec(
    connection_id: str,
    body: InvoicingMergeSpecBody,
    db: Session = Depends(get_db),
) -> InvoicingMergeSpecOut:
    from app.invoicing_connect import module_spec_fragment
    from app.module_spec_codec import merge_module_spec_fragment

    _ = _client(connection_id, db)  # ensure connection valid
    if not body.model.startswith("x_"):
        raise HTTPException(status_code=400, detail="Model must be custom x_*")
    fragment = module_spec_fragment(
        model=body.model,
        invoice_field=body.invoice_field,
        origin_field_on_move=body.origin_field_on_move,
        partner_field=body.partner_field,
    )
    merged = merge_module_spec_fragment(body.base_spec or {}, fragment)
    return InvoicingMergeSpecOut(ok=True, merged=merged)


class DocumentsGateOut(BaseModel):
    ok: bool
    available: bool
    verify_state: str | None = None
    folder_model: str | None = None
    message: str | None = None
    note: str | None = None


class DocumentsFolderMapOut(BaseModel):
    ok: bool
    mapping: dict[str, int]


class DocumentsFolderSetBody(BaseModel):
    model: str = Field(..., min_length=1)
    folder_id: int | None = None


class DocumentsMergeSpecBody(BaseModel):
    model: str = Field(..., min_length=1)
    folder_id: int
    base_spec: dict[str, Any] | None = None


class DocumentsMergeSpecOut(BaseModel):
    ok: bool
    merged: dict[str, Any]


@router.get("/documents/gate", response_model=DocumentsGateOut)
def documents_gate_route(
    connection_id: str,
    db: Session = Depends(get_db),
) -> DocumentsGateOut:
    from app.documents_connect import documents_gate

    client = _client(connection_id, db)
    return DocumentsGateOut.model_validate(documents_gate(client))


@router.get("/documents/folder-map", response_model=DocumentsFolderMapOut)
def documents_folder_map(
    connection_id: str,
    db: Session = Depends(get_db),
) -> DocumentsFolderMapOut:
    from app.documents_connect import get_folder_map

    client = _client(connection_id, db)
    return DocumentsFolderMapOut.model_validate(get_folder_map(client))


@router.post("/documents/folder-map", response_model=DocumentsFolderMapOut)
def documents_set_folder(
    connection_id: str,
    body: DocumentsFolderSetBody,
    db: Session = Depends(get_db),
) -> DocumentsFolderMapOut:
    from app.documents_connect import set_model_folder

    client = _client(connection_id, db)
    try:
        result = set_model_folder(client, model=body.model, folder_id=body.folder_id)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DocumentsFolderMapOut(ok=True, mapping=result["mapping"])


@router.post("/documents/merge-into-spec", response_model=DocumentsMergeSpecOut)
def documents_merge_into_spec(
    connection_id: str,
    body: DocumentsMergeSpecBody,
    db: Session = Depends(get_db),
) -> DocumentsMergeSpecOut:
    from app.documents_connect import module_spec_fragment
    from app.module_spec_codec import merge_module_spec_fragment

    _ = _client(connection_id, db)
    if not body.model.startswith("x_"):
        raise HTTPException(status_code=400, detail="Model must be custom x_*")
    fragment = module_spec_fragment(model=body.model, folder_id=body.folder_id)
    merged = merge_module_spec_fragment(body.base_spec or {}, fragment)
    return DocumentsMergeSpecOut(ok=True, merged=merged)
