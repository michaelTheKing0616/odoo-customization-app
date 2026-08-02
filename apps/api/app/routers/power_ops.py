"""Power Ops — multi-step bulk RPC recipes (Online power parity)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.power_ops_recipes import (
    list_recipes,
    probe_connection_capabilities,
    run_recipe,
)
from app.schemas import ConfirmAdvancedBody
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)

router = APIRouter(
    prefix="/connections/{connection_id}/power-ops",
    tags=["power-ops"],
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


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class PowerOpsRunBody(ConfirmAdvancedBody):
    recipe_id: str
    model: str | None = None
    domain: list[Any] = Field(default_factory=list)
    ids: list[int] | None = None
    dry_run: bool = True
    batch_size: int = Field(40, ge=1, le=200)
    continue_on_error: bool = True


class StepLogOut(BaseModel):
    record_id: int
    step: str
    ok: bool
    error: str | None = None


class PowerOpsRunOut(BaseModel):
    ok: bool
    dry_run: bool
    processed: int
    succeeded: int
    failed: int
    message: str
    available: bool = True
    unavailable_reason: str | None = None
    logs: list[StepLogOut] = Field(default_factory=list)


@router.get("/recipes")
def get_recipes(connection_id: str) -> dict[str, Any]:
    _ = connection_id
    return {"recipes": list_recipes()}


@router.get("/capabilities")
def get_capabilities(
    connection_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    client = _client(connection_id, db)
    try:
        return probe_connection_capabilities(client)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/run", response_model=PowerOpsRunOut)
def run_power_ops(
    connection_id: str,
    body: PowerOpsRunBody,
    db: Session = Depends(get_db),
) -> PowerOpsRunOut:
    from app.power_ops_recipes import get_recipe

    recipe = get_recipe(body.recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail=f"Unknown recipe {body.recipe_id}")

    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Power Ops “{recipe.name}” will mutate live Odoo records "
                    f"via multi-step RPC (same class of power as Odoo.sh scripts)."
                ),
                risks=list(recipe.risks)
                + [
                    "Online UI limits do not apply — you are explicitly opting into bulk power",
                    "Failed rows are reported; successful destructive steps are not auto-undone",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    client = _client(connection_id, db)
    try:
        result = run_recipe(
            client,
            recipe_id=body.recipe_id,
            model=body.model,
            domain=body.domain,
            ids=body.ids,
            dry_run=body.dry_run,
            batch_size=body.batch_size,
            continue_on_error=body.continue_on_error,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PowerOpsRunOut(
        ok=result.ok,
        dry_run=result.dry_run,
        processed=result.processed,
        succeeded=result.succeeded,
        failed=result.failed,
        message=result.message,
        available=result.available,
        unavailable_reason=result.unavailable_reason,
        logs=[
            StepLogOut(
                record_id=l.record_id,
                step=l.step,
                ok=l.ok,
                error=l.error,
            )
            for l in result.logs[:2000]
        ],
    )
