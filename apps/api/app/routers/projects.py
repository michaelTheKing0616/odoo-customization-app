"""Draft customization projects — CRUD + apply ModuleSpec-like JSON (Phase P2)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_models import CustomizationProject
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.project_apply import apply_project_spec, diff_project_spec
from app.schemas import (
    ProjectApplyBody,
    ProjectApplyOut,
    ProjectCreate,
    ProjectDiffOut,
    ProjectOut,
    ProjectUpdate,
)
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)

router = APIRouter(prefix="/connections/{connection_id}/projects", tags=["projects"])


def _project_out(row: CustomizationProject) -> ProjectOut:
    try:
        spec = json.loads(row.spec_json or "{}")
    except json.JSONDecodeError:
        spec = {}
    return ProjectOut(
        id=row.id,
        connection_id=row.connection_id,
        name=row.name,
        template_id=row.template_id,
        spec_json=spec if isinstance(spec, dict) else {},
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


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


@router.get("", response_model=list[ProjectOut])
def list_projects(connection_id: str, db: Session = Depends(get_db)) -> list[ProjectOut]:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rows = (
        db.query(CustomizationProject)
        .filter(CustomizationProject.connection_id == connection_id)
        .order_by(CustomizationProject.created_at.desc())
        .all()
    )
    return [_project_out(r) for r in rows]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    connection_id: str, body: ProjectCreate, db: Session = Depends(get_db)
) -> ProjectOut:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Prefer portable library ModuleSpec when template_id=library and spec empty
    spec = dict(body.spec_json or {})
    if body.template_id == "library" and not spec.get("models"):
        try:
            from module_generator import library_module_spec

            lib = library_module_spec()
            spec = {
                "technical_name": lib.technical_name,
                "display_name": lib.display_name,
                "depends": list(lib.depends),
                "models": [
                    {
                        "model": m.model,
                        "description": m.description,
                        "mixins": list(m.mixins),
                        "fields": [
                            {
                                "name": f.name,
                                "ttype": f.ttype,
                                "string": f.string,
                                "required": f.required,
                                "readonly": f.readonly,
                                "relation": f.relation,
                                "relation_field": f.relation_field,
                                "selection": f.selection,
                                "help": f.help,
                                "on_delete": f.on_delete,
                            }
                            for f in m.fields
                        ],
                    }
                    for m in lib.models
                ],
            }
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=500, detail=f"Failed to load library template: {exc}"
            ) from exc

    row = CustomizationProject(
        connection_id=connection_id,
        name=body.name,
        template_id=body.template_id,
        spec_json=json.dumps(spec),
        status="draft",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _project_out(row)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    connection_id: str, project_id: str, db: Session = Depends(get_db)
) -> ProjectOut:
    row = (
        db.query(CustomizationProject)
        .filter(
            CustomizationProject.id == project_id,
            CustomizationProject.connection_id == connection_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_out(row)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    connection_id: str,
    project_id: str,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
) -> ProjectOut:
    row = (
        db.query(CustomizationProject)
        .filter(
            CustomizationProject.id == project_id,
            CustomizationProject.connection_id == connection_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.name is not None:
        row.name = body.name
    if body.template_id is not None:
        row.template_id = body.template_id
    if body.spec_json is not None:
        row.spec_json = json.dumps(body.spec_json)
    if body.status is not None:
        row.status = body.status
    db.commit()
    db.refresh(row)
    return _project_out(row)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    connection_id: str, project_id: str, db: Session = Depends(get_db)
) -> None:
    row = (
        db.query(CustomizationProject)
        .filter(
            CustomizationProject.id == project_id,
            CustomizationProject.connection_id == connection_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(row)
    db.commit()


@router.get("/{project_id}/diff", response_model=ProjectDiffOut)
def diff_project(
    connection_id: str, project_id: str, db: Session = Depends(get_db)
) -> ProjectDiffOut:
    """Pre-apply conflict report vs live Odoo introspection."""
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    row = (
        db.query(CustomizationProject)
        .filter(
            CustomizationProject.id == project_id,
            CustomizationProject.connection_id == connection_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        spec = json.loads(row.spec_json or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid spec_json") from exc

    try:
        conn = get_connection_or_404(db, connection_id)
        client = client_from_connection(conn)
        report = diff_project_spec(client, spec if isinstance(spec, dict) else {})
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ProjectDiffOut(**report)


@router.post("/{project_id}/apply", response_model=ProjectApplyOut)
def apply_project(
    connection_id: str,
    project_id: str,
    body: ProjectApplyBody,
    db: Session = Depends(get_db),
) -> ProjectApplyOut:
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                "Applying a draft project creates models and fields on the live "
                "Odoo database. Prefer a sandbox connection."
            ),
            risks=[
                "Creates ir.model / ir.model.fields metadata on the target",
                "Does not fully roll back if a later field fails",
                "Views/menus/ACL from the draft are not applied in v1",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    row = (
        db.query(CustomizationProject)
        .filter(
            CustomizationProject.id == project_id,
            CustomizationProject.connection_id == connection_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        spec = json.loads(row.spec_json or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid spec_json") from exc

    try:
        conn = get_connection_or_404(db, connection_id)
        client = client_from_connection(conn)
        result = apply_project_spec(client, spec if isinstance(spec, dict) else {})
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row.status = "applied"
    db.commit()

    return ProjectApplyOut(
        ok=True,
        project_id=row.id,
        models_created=result.models_created,
        fields_created=result.fields_created,
        skipped=result.skipped,
        warnings=result.warnings,
        message=result.message,
    )
