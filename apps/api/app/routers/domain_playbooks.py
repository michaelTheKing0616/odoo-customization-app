"""Domain app playbooks (CRM / Project / Sale) — mastery M3-P2."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404

router = APIRouter(
    prefix="/connections/{connection_id}/domain-playbooks",
    tags=["domain-playbooks"],
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


def _module_installed(client: Any, module_name: str) -> bool:
    try:
        rows = client.execute_kw(
            "ir.module.module",
            "search_read",
            [[("name", "=", module_name)]],
            {"fields": ["state"], "limit": 1},
        )
    except Exception:  # noqa: BLE001
        return False
    return bool(
        rows and rows[0].get("state") in {"installed", "to upgrade", "to remove"}
    )


def _any_module(client: Any, names: list[str]) -> bool:
    return any(_module_installed(client, n) for n in names)


class DomainAvailabilityOut(BaseModel):
    available: bool
    reason: str | None = None
    model: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)


class DomainPlaybookOut(BaseModel):
    id: str
    name: str
    description: str
    requires_modules: list[str]
    available: bool
    reason: str


PLAYBOOKS: list[dict[str, Any]] = [
    {
        "id": "crm_stages",
        "name": "CRM stages",
        "requires_modules": ["crm"],
        "description": "List crm.stage when CRM is installed.",
    },
    {
        "id": "project_stages",
        "name": "Project stages",
        "requires_modules": ["project"],
        "description": "List project.task.type or project.project.stage when Project is installed.",
    },
    {
        "id": "sale_pricelists",
        "name": "Sale pricelists",
        "requires_modules": ["sale", "product"],
        "description": "List product.pricelist when sale/product is installed.",
    },
]


@router.get("", response_model=list[DomainPlaybookOut])
def list_domain_playbooks(
    connection_id: str, db: Session = Depends(get_db)
) -> list[DomainPlaybookOut]:
    client = _client(connection_id, db)
    out: list[DomainPlaybookOut] = []
    for pb in PLAYBOOKS:
        mods = list(pb["requires_modules"])
        if pb["id"] == "sale_pricelists":
            available = _any_module(client, mods)
        else:
            available = all(_module_installed(client, m) for m in mods)
        if available:
            reason = "RPC available"
        else:
            reason = f"Modules not installed: {', '.join(mods)}"
        out.append(
            DomainPlaybookOut(
                id=pb["id"],
                name=pb["name"],
                description=pb["description"],
                requires_modules=mods,
                available=available,
                reason=reason,
            )
        )
    return out


@router.get("/crm/stages", response_model=DomainAvailabilityOut)
def list_crm_stages(
    connection_id: str, db: Session = Depends(get_db)
) -> DomainAvailabilityOut:
    client = _client(connection_id, db)
    if not _module_installed(client, "crm") and not client.model_exists("crm.stage"):
        return DomainAvailabilityOut(
            available=False,
            reason="crm module / crm.stage not installed",
            model="crm.stage",
        )
    if not client.model_exists("crm.stage"):
        return DomainAvailabilityOut(
            available=False,
            reason="crm.stage model not found on this major",
            model="crm.stage",
        )
    try:
        rows = client.execute_kw(
            "crm.stage",
            "search_read",
            [[]],
            {"fields": ["name", "sequence", "fold"], "limit": 200, "order": "sequence, id"},
        )
    except OdooClientError as exc:
        return DomainAvailabilityOut(
            available=False, reason=str(exc), model="crm.stage"
        )
    return DomainAvailabilityOut(
        available=True,
        model="crm.stage",
        rows=[
            {
                "id": int(r["id"]),
                "name": r.get("name"),
                "sequence": r.get("sequence"),
                "fold": r.get("fold"),
            }
            for r in rows
        ],
    )


@router.get("/project/stages", response_model=DomainAvailabilityOut)
def list_project_stages(
    connection_id: str, db: Session = Depends(get_db)
) -> DomainAvailabilityOut:
    client = _client(connection_id, db)
    if not _module_installed(client, "project"):
        return DomainAvailabilityOut(
            available=False,
            reason="project module not installed",
        )
    model = None
    if client.model_exists("project.task.type"):
        model = "project.task.type"
    elif client.model_exists("project.project.stage"):
        model = "project.project.stage"
    if model is None:
        return DomainAvailabilityOut(
            available=False,
            reason="project.task.type / project.project.stage not found on this major",
        )
    fields = ["name", "sequence"]
    try:
        fg = client.execute_kw(model, "fields_get", [], {"attributes": ["type"]})
        if isinstance(fg, dict):
            fields = [f for f in ["name", "sequence", "fold", "project_ids"] if f in fg]
            if "name" not in fields:
                fields = ["name"]
    except Exception:  # noqa: BLE001
        pass
    try:
        rows = client.execute_kw(
            model,
            "search_read",
            [[]],
            {"fields": fields, "limit": 200, "order": "sequence, id"},
        )
    except OdooClientError as exc:
        return DomainAvailabilityOut(available=False, reason=str(exc), model=model)
    return DomainAvailabilityOut(
        available=True,
        model=model,
        rows=[{"id": int(r["id"]), **{k: r.get(k) for k in fields}} for r in rows],
    )


@router.get("/sale/pricelists", response_model=DomainAvailabilityOut)
def list_sale_pricelists(
    connection_id: str, db: Session = Depends(get_db)
) -> DomainAvailabilityOut:
    client = _client(connection_id, db)
    if not _any_module(client, ["sale", "product"]) and not client.model_exists(
        "product.pricelist"
    ):
        return DomainAvailabilityOut(
            available=False,
            reason="sale/product module / product.pricelist not installed",
            model="product.pricelist",
        )
    if not client.model_exists("product.pricelist"):
        return DomainAvailabilityOut(
            available=False,
            reason="product.pricelist model not found on this major",
            model="product.pricelist",
        )
    try:
        rows = client.execute_kw(
            "product.pricelist",
            "search_read",
            [[]],
            {"fields": ["name", "currency_id", "active"], "limit": 200, "order": "name"},
        )
    except OdooClientError as exc:
        return DomainAvailabilityOut(
            available=False, reason=str(exc), model="product.pricelist"
        )
    return DomainAvailabilityOut(
        available=True,
        model="product.pricelist",
        rows=[
            {
                "id": int(r["id"]),
                "name": r.get("name"),
                "currency_id": (
                    r["currency_id"][0]
                    if isinstance(r.get("currency_id"), (list, tuple))
                    else r.get("currency_id")
                ),
                "active": r.get("active"),
            }
            for r in rows
        ],
    )
