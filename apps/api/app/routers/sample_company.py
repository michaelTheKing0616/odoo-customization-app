"""Touch 126: 'Load sample company'. Disposable ingenium_* or test-copy databases only, through the write gate."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import write_gate as wg
from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.sample_company import COMPANY, CUSTOMERS, PRODUCTS, assert_disposable, seed

router = APIRouter(prefix="/connections/{connection_id}/sample-company", tags=["sample-company"])


class _Creator:
    def __init__(self, client: Any) -> None:
        self.client = client

    def create(self, model: str, vals: dict[str, Any]) -> Any:
        return self.client.execute_kw(model, "create", [vals])


@router.get("")
def sample_company_info(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        assert_disposable(row.db_name, is_test_copy=row.is_test_copy)
        allowed, why = True, None
    except ValueError as exc:
        allowed, why = False, str(exc)
    return {"company": COMPANY["name"], "customers": len(CUSTOMERS), "products": len(PRODUCTS), "allowed": allowed, "why_not": why}


@router.post("")
def load_sample_company(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        assert_disposable(row.db_name, is_test_copy=row.is_test_copy)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        client = client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    try:
        made = seed(_Creator(client), row.db_name, is_test_copy=row.is_test_copy,
                    before_create=lambda m: wg.guard_record_create(db, connection_id, model=m, source="Sample company"))
    except (wg.WriteRefused, wg.WriteNeedsApproval) as exc:
        raise wg.http_error(exc) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"created": made, "company": COMPANY["name"]}
