"""Read-only Odoo metadata introspection for a saved connection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.ai_stock_catalog import (
    STOCK_CATALOG_LIMIT,
    filter_catalog,
    load_connection_stock_catalog,
)
from app.schemas import FieldOut, ModelOut, ModuleOut, ReuseModelOut, ViewOut

router = APIRouter(prefix="/connections/{connection_id}", tags=["introspection"])


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/modules", response_model=list[ModuleOut])
def list_modules(
    connection_id: str,
    applications_only: bool = Query(False),
    installed_only: bool = Query(True),
    db: Session = Depends(get_db),
) -> list[ModuleOut]:
    client = _client(connection_id, db)
    return [
        ModuleOut.model_validate(m.model_dump())
        for m in client.list_modules(
            applications_only=applications_only,
            installed_only=installed_only,
        )
    ]


@router.get("/modules/installed", response_model=list[ModuleOut])
def list_installed_modules(
    connection_id: str,
    q: str | None = Query(None, description="Filter on name / shortdesc"),
    db: Session = Depends(get_db),
) -> list[ModuleOut]:
    """Installed modules (all, not just applications) for peer-depends pickers."""
    client = _client(connection_id, db)
    rows = [
        ModuleOut.model_validate(m.model_dump())
        for m in client.list_modules(installed_only=True, applications_only=False)
    ]
    needle = (q or "").strip().lower()
    if not needle:
        return rows
    return [
        m
        for m in rows
        if needle in m.name.lower()
        or (m.shortdesc and needle in m.shortdesc.lower())
    ]


@router.get("/models", response_model=list[ModelOut])
def list_models(
    connection_id: str,
    custom_only: bool = Query(False),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> list[ModelOut]:
    client = _client(connection_id, db)
    return [
        ModelOut.model_validate(m.model_dump())
        for m in client.list_models(custom_only=custom_only, limit=limit)
    ]


@router.get("/reuse-catalog", response_model=list[ReuseModelOut])
def list_reuse_catalog(
    connection_id: str,
    q: str | None = Query(None, description="Filter on model / display name / app"),
    stock_only: bool = Query(True, description="Exclude custom x_* models"),
    limit: int = Query(STOCK_CATALOG_LIMIT, ge=1, le=STOCK_CATALOG_LIMIT),
    db: Session = Depends(get_db),
) -> list[ReuseModelOut]:
    """All stock Odoo models on the connection for manual reuse and AI catalog."""
    client = _client(connection_id, db)
    catalog = load_connection_stock_catalog(client, limit=limit)
    rows = filter_catalog(
        catalog["stock"] if stock_only else catalog["all"],
        q=q,
        stock_only=stock_only,
    )
    return [ReuseModelOut.model_validate(r) for r in rows[:limit]]


@router.get("/models/{model_name}/fields", response_model=list[FieldOut])
def list_fields(
    connection_id: str, model_name: str, db: Session = Depends(get_db)
) -> list[FieldOut]:
    client = _client(connection_id, db)
    return [FieldOut.model_validate(f.model_dump()) for f in client.list_fields(model_name)]


@router.get("/models/{model_name}/views", response_model=list[ViewOut])
def list_views(
    connection_id: str, model_name: str, db: Session = Depends(get_db)
) -> list[ViewOut]:
    client = _client(connection_id, db)
    return [ViewOut.model_validate(v.model_dump()) for v in client.list_views(model_name)]
