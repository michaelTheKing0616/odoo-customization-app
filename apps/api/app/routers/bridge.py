"""HTTP Tier I check. No Odoo write."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.bridge.contract import ContractError, validate_contract

router = APIRouter(prefix="/bridge", tags=["bridge"])


class ValidateBody(BaseModel):
    contract: dict


@router.post("/contracts/validate")
def validate_contract_route(body: ValidateBody) -> dict:
    try:
        contract = validate_contract(body.contract)
    except ContractError as exc:
        return {"ok": False, "tier": "I", "error": str(exc)}
    return {"ok": True, "tier": "I", "direction": contract.direction, "entities": len(contract.entities)}
