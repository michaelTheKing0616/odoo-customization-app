"""App wizard — list templates and scaffold live Odoo apps (Phase P1 / P3)."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.app_templates import list_templates, run_scaffold
from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import (
    AppScaffoldBody,
    AppScaffoldOut,
    AppTemplateOut,
    LibraryExportBody,
    LibraryStatsOut,
    ModuleExportOut,
)
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)
from module_generator import build_module_zip, library_module_spec

router = APIRouter(tags=["apps"])


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


@router.get("/apps/templates", response_model=list[AppTemplateOut])
def get_app_templates() -> list[AppTemplateOut]:
    return [AppTemplateOut.model_validate(t) for t in list_templates()]


@router.post("/apps/templates/library/export", response_model=ModuleExportOut)
def export_library_module(body: LibraryExportBody) -> ModuleExportOut:
    """Portable library zip (fines + reminders + multi_company flags). Does not write to Odoo."""
    spec = library_module_spec(
        body.technical_name,
        body.display_name,
        include_fines=body.fines,
        include_reminders=body.reminders,
        multi_company=body.multi_company,
    )
    zip_bytes = build_module_zip(spec)
    note_parts = [
        f"Library module {spec.technical_name}",
        f"fines={'on' if body.fines else 'off'}",
        f"reminders={'on' if body.reminders else 'off'}",
        f"multi_company={'on' if body.multi_company else 'off'}",
        "sandbox before promote (Option A for Python/code)",
    ]
    return ModuleExportOut(
        technical_name=spec.technical_name,
        filename=f"{spec.technical_name}.zip",
        content_base64=base64.b64encode(zip_bytes).decode("ascii"),
        note="; ".join(note_parts),
        model_count=len(spec.models),
        view_count=len(spec.views),
        warnings=[],
    )


@router.post(
    "/connections/{connection_id}/apps/scaffold",
    response_model=AppScaffoldOut,
)
def scaffold_app(
    connection_id: str,
    body: AppScaffoldBody,
    db: Session = Depends(get_db),
) -> AppScaffoldOut:
    # Confirm before Odoo connect so missing phrase → 403 not 502 (ERRORS.md).
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                "Scaffolding an app creates multiple custom models, fields, and "
                "view extensions on this Odoo database. Re-running is mostly "
                "idempotent (existing models are skipped) but is hard to fully undo."
            ),
            risks=[
                "Creates several x_* models and fields on the live connection",
                "View inherit extensions and optional automations are added",
                "Dropped later via delete may leave residual data / views",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        result = run_scaffold(
            client,
            body.template_id,
            display_name=body.display_name,
            technical_prefix=body.technical_prefix,
            multi_company=body.multi_company,
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AppScaffoldOut(
        ok=True,
        template_id=result.template_id,
        models=result.models,
        models_created=result.models_created,
        models_skipped=result.models_skipped,
        fields_created=result.fields_created,
        view_injects=result.view_injects,
        menus_created=result.menus_created,
        message=result.message,
        warnings=result.warnings,
    )


@router.get(
    "/connections/{connection_id}/library/stats",
    response_model=LibraryStatsOut,
)
def library_stats(connection_id: str, db: Session = Depends(get_db)) -> LibraryStatsOut:
    """Optional aggregates for connection dashboard when library models exist."""
    client = _client(connection_id, db)
    book_model = "x_lib_book"
    loan_model = "x_lib_loan"
    if not client.model_exists(book_model):
        return LibraryStatsOut(
            available=False,
            message="Library models not found (scaffold Library first)",
        )
    books = int(client.execute_kw(book_model, "search_count", [[]]))
    loans: int | None = None
    active: int | None = None
    overdue: int | None = None
    if client.model_exists(loan_model):
        loans = int(client.execute_kw(loan_model, "search_count", [[]]))
        active = int(
            client.execute_kw(
                loan_model,
                "search_count",
                [[("x_returned", "=", False)]],
            )
        )
        # Best-effort overdue: active + due_date before today (context_today via date.today).
        from datetime import date

        today = date.today().isoformat()
        try:
            overdue = int(
                client.execute_kw(
                    loan_model,
                    "search_count",
                    [
                        [
                            ("x_returned", "=", False),
                            ("x_due_date", "<", today),
                        ]
                    ],
                )
            )
        except OdooClientError:
            overdue = None
    return LibraryStatsOut(
        available=True,
        book_model=book_model,
        loan_model=loan_model if loans is not None else None,
        books=books,
        loans=loans,
        active_loans=active,
        overdue_loans=overdue,
        message="ok",
    )
