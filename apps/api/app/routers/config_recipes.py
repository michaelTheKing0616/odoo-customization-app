"""Few-click configuration recipes (P0–P2).

Day-1 setup, document numbering, apps packs, settings board,
multi-company, and master-data stubs. Uses the same confirm gate as config_ops.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config_packet.settings import SETTINGS_ALLOWLIST, apply_settings, capture_settings
from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import ConfirmAdvancedBody
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)

router = APIRouter(
    prefix="/connections/{connection_id}/config/recipes",
    tags=["config-recipes"],
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


class RecipeCard(BaseModel):
    id: str
    phase: str
    title: str
    blurb: str
    clicks: str


class RecipeStep(BaseModel):
    op: str
    target: str
    detail: str
    would_write: bool = True


class RecipePlanOut(BaseModel):
    ok: bool
    dry_run: bool
    steps: list[RecipeStep]
    applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str = ""


@router.get("", response_model=list[RecipeCard])
def list_recipes(connection_id: str) -> list[RecipeCard]:
    return [
        RecipeCard(
            id="day1",
            phase="p0",
            title="Day-1 setup",
            blurb="Company name, currency, country, language — one apply.",
            clicks="3 clicks",
        ),
        RecipeCard(
            id="numbering",
            phase="p0",
            title="Document numbering",
            blurb="SO / INV / PO / payment prefixes as a pack.",
            clicks="2 clicks",
        ),
        RecipeCard(
            id="apps-pack",
            phase="p1",
            title="Apps pack",
            blurb="Install Sales+CRM / Accounting / Inventory with deps preview.",
            clicks="3 clicks",
        ),
        RecipeCard(
            id="import-seeds",
            phase="p1",
            title="Import starter packs",
            blurb="Open the Import gallery for partners, products, users.",
            clicks="Open Import",
        ),
        RecipeCard(
            id="bulk-recipes",
            phase="p1",
            title="Bulk recipes",
            blurb="Recipe chips on Bulk Suite for common mass ops.",
            clicks="Open Bulk Suite",
        ),
        RecipeCard(
            id="settings-board",
            phase="p2",
            title="Settings toggles",
            blurb="Searchable allowlisted res.config.settings board.",
            clicks="2 clicks",
        ),
        RecipeCard(
            id="multi-company",
            phase="p2",
            title="Add company",
            blurb="Create a second company with currency + country.",
            clicks="3 clicks",
        ),
        RecipeCard(
            id="master-packs",
            phase="p2",
            title="Master data packs",
            blurb="UoM categories + fiscal position stubs with preview.",
            clicks="3 clicks",
        ),
    ]


def _currency_id(client: Any, code: str) -> int | None:
    code = (code or "").strip().upper()
    if not code:
        return None
    try:
        ids = client.execute_kw(
            "res.currency", "search", [[("name", "=", code)]], {"limit": 1}
        )
        return int(ids[0]) if ids else None
    except OdooClientError:
        return None


def _country_id(client: Any, code: str | None) -> int | None:
    if not code:
        return None
    code = code.strip().upper()
    try:
        ids = client.execute_kw(
            "res.country", "search", [[("code", "=", code)]], {"limit": 1}
        )
        return int(ids[0]) if ids else None
    except OdooClientError:
        return None


# --- Day-1 -----------------------------------------------------------------

class Day1Body(ConfirmAdvancedBody):
    company_id: int | None = None
    name: str = Field(..., min_length=1, max_length=128)
    currency_code: str = Field("USD", min_length=3, max_length=8)
    country_code: str | None = Field(None, max_length=2)
    language_code: str | None = Field(None, max_length=16)
    email: str | None = None
    phone: str | None = None
    dry_run: bool = True


@router.post("/day1", response_model=RecipePlanOut)
def run_day1(
    connection_id: str, body: Day1Body, db: Session = Depends(get_db)
) -> RecipePlanOut:
    client = _client(connection_id, db)
    warnings: list[str] = []
    steps: list[RecipeStep] = [
        RecipeStep(
            op="write_company",
            target="res.company.name",
            detail=f"Rename company to {body.name.strip()!r}",
        )
    ]
    vals: dict[str, Any] = {"name": body.name.strip()}
    if body.email:
        vals["email"] = body.email.strip()
    if body.phone:
        vals["phone"] = body.phone.strip()

    cur = _currency_id(client, body.currency_code)
    if cur:
        vals["currency_id"] = cur
        steps.append(
            RecipeStep(
                op="write_company",
                target="res.company.currency_id",
                detail=f"Currency {body.currency_code.upper()} (id={cur})",
            )
        )
    else:
        warnings.append(f"Currency {body.currency_code} not found — skipped")

    country = _country_id(client, body.country_code)
    if country:
        steps.append(
            RecipeStep(
                op="write_country",
                target="res.partner.country_id",
                detail=f"Country {body.country_code.upper()} (id={country})",
            )
        )
    elif body.country_code:
        warnings.append(f"Country {body.country_code} not found — skipped")

    lang_id: int | None = None
    if body.language_code:
        try:
            found = client.execute_kw(
                "res.lang",
                "search",
                [[("code", "=", body.language_code), ("active", "in", [True, False])]],
                {"limit": 1},
            )
            if found:
                lang_id = int(found[0])
                steps.append(
                    RecipeStep(
                        op="activate_lang",
                        target="res.lang",
                        detail=f"Activate {body.language_code}",
                    )
                )
            else:
                warnings.append(f"Language {body.language_code} missing — skipped")
        except OdooClientError as exc:
            warnings.append(f"Language probe failed: {exc}")

    try:
        if body.company_id:
            company_id = int(body.company_id)
        else:
            ids = client.execute_kw("res.company", "search", [[]], {"limit": 1})
            if not ids:
                raise HTTPException(status_code=400, detail="No company on instance")
            company_id = int(ids[0])
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.dry_run:
        return RecipePlanOut(
            ok=True,
            dry_run=True,
            steps=steps,
            warnings=warnings,
            message=f"Dry-run: would update company {company_id}",
        )

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Day-1 setup writes company, currency, and language on this Odoo.",
            risks=[
                "Changes the live company record",
                "Currency change can affect accounting displays",
                "Language activation changes available UI languages",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    applied: list[str] = []
    try:
        client.execute_kw("res.company", "write", [[company_id], vals])
        applied.append(f"company {company_id} {sorted(vals)}")
        if country:
            rows = client.execute_kw(
                "res.company", "read", [[company_id]], {"fields": ["partner_id"]}
            )
            partner = rows[0].get("partner_id") if rows else None
            partner_id = (
                int(partner[0])
                if isinstance(partner, (list, tuple)) and partner
                else int(partner)
                if isinstance(partner, int)
                else None
            )
            if partner_id:
                client.execute_kw(
                    "res.partner", "write", [[partner_id], {"country_id": country}]
                )
                applied.append(f"partner {partner_id} country={country}")
            else:
                try:
                    client.execute_kw(
                        "res.company", "write", [[company_id], {"country_id": country}]
                    )
                    applied.append(f"company country={country}")
                except OdooClientError as exc:
                    warnings.append(f"Country write skipped: {exc}")
        if lang_id:
            client.execute_kw("res.lang", "write", [[lang_id], {"active": True}])
            applied.append(f"lang {body.language_code} active")
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RecipePlanOut(
        ok=True,
        dry_run=False,
        steps=steps,
        applied=applied,
        warnings=warnings,
        message=f"Day-1 applied on company {company_id}",
    )


# --- Numbering -------------------------------------------------------------

NUMBERING_PACK: list[dict[str, Any]] = [
    {
        "key": "sale",
        "name": "Sales Orders",
        "code": "sale.order",
        "prefix": "SO/%(year)s/",
        "padding": 5,
    },
    {
        "key": "invoice",
        "name": "Customer Invoices",
        "code": "account.move",
        "prefix": "INV/%(year)s/",
        "padding": 5,
    },
    {
        "key": "purchase",
        "name": "Purchase Orders",
        "code": "purchase.order",
        "prefix": "PO/%(year)s/",
        "padding": 5,
    },
    {
        "key": "payment",
        "name": "Customer Payments",
        "code": "account.payment.customer.invoice",
        "prefix": "PAY/%(year)s/",
        "padding": 5,
    },
]


class NumberingBody(ConfirmAdvancedBody):
    dry_run: bool = True
    prefix_year: bool = True
    keys: list[str] = Field(default_factory=lambda: [p["key"] for p in NUMBERING_PACK])


@router.get("/numbering/catalog")
def numbering_catalog(connection_id: str) -> list[dict[str, Any]]:
    return NUMBERING_PACK


@router.post("/numbering", response_model=RecipePlanOut)
def run_numbering(
    connection_id: str, body: NumberingBody, db: Session = Depends(get_db)
) -> RecipePlanOut:
    client = _client(connection_id, db)
    selected = [p for p in NUMBERING_PACK if p["key"] in set(body.keys)]
    if not selected:
        raise HTTPException(status_code=400, detail="No numbering keys selected")

    steps: list[RecipeStep] = []
    warnings: list[str] = []
    for pack in selected:
        prefix = (
            pack["prefix"]
            if body.prefix_year
            else pack["prefix"].replace("%(year)s/", "")
        )
        try:
            existing = client.execute_kw(
                "ir.sequence",
                "search",
                [[("code", "=", pack["code"])]],
                {"limit": 1},
            )
        except OdooClientError as exc:
            warnings.append(f"Probe {pack['code']}: {exc}")
            existing = []
        if existing:
            steps.append(
                RecipeStep(
                    op="update_sequence",
                    target=pack["code"],
                    detail=f"Update {pack['name']} → {prefix}",
                )
            )
        else:
            steps.append(
                RecipeStep(
                    op="create_sequence",
                    target=pack["code"],
                    detail=f"Create {pack['name']} → {prefix}",
                )
            )

    if body.dry_run:
        return RecipePlanOut(
            ok=True,
            dry_run=True,
            steps=steps,
            warnings=warnings,
            message=f"Dry-run: {len(steps)} sequence change(s)",
        )

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Document numbering pack updates ir.sequence prefixes.",
            risks=[
                "Changes invoice/order number formats",
                "Does not renumber existing documents",
                "Wrong prefix can confuse finance ops",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    applied: list[str] = []
    for pack in selected:
        prefix = (
            pack["prefix"]
            if body.prefix_year
            else pack["prefix"].replace("%(year)s/", "")
        )
        try:
            existing = client.execute_kw(
                "ir.sequence",
                "search",
                [[("code", "=", pack["code"])]],
                {"limit": 1},
            )
            if existing:
                client.execute_kw(
                    "ir.sequence",
                    "write",
                    [
                        [int(existing[0])],
                        {
                            "prefix": prefix,
                            "padding": pack["padding"],
                            "name": pack["name"],
                        },
                    ],
                )
                applied.append(f"updated {pack['code']} → {prefix}")
            else:
                sid = client.execute_kw(
                    "ir.sequence",
                    "create",
                    [
                        {
                            "name": pack["name"],
                            "code": pack["code"],
                            "prefix": prefix,
                            "padding": pack["padding"],
                            "number_next": 1,
                            "implementation": "standard",
                        }
                    ],
                )
                applied.append(f"created {pack['code']} id={sid}")
        except OdooClientError as exc:
            warnings.append(f"{pack['key']}: {exc}")

    return RecipePlanOut(
        ok=bool(applied),
        dry_run=False,
        steps=steps,
        applied=applied,
        warnings=warnings,
        message=f"Numbering pack applied ({len(applied)} ok)",
    )


# --- Apps packs (P1) -------------------------------------------------------

APPS_PACKS: list[dict[str, Any]] = [
    {
        "id": "sales_desk",
        "title": "Sales desk",
        "modules": ["sale_management", "crm", "sales_team"],
        "blurb": "CRM + Sales + teams",
    },
    {
        "id": "accounting_lite",
        "title": "Accounting lite",
        "modules": ["account", "account_payment"],
        "blurb": "Invoicing / payments core",
    },
    {
        "id": "inventory",
        "title": "Inventory",
        "modules": ["stock", "product"],
        "blurb": "Warehouse + products",
    },
    {
        "id": "purchase",
        "title": "Purchase",
        "modules": ["purchase", "purchase_stock"],
        "blurb": "Vendor POs",
    },
    {
        "id": "website_lead",
        "title": "Website + leads",
        "modules": ["website", "website_crm"],
        "blurb": "Public site + CRM form",
    },
]


class AppsPackBody(ConfirmAdvancedBody):
    pack_id: str
    dry_run: bool = True


@router.get("/apps-packs")
def list_apps_packs(connection_id: str) -> list[dict[str, Any]]:
    return APPS_PACKS


@router.post("/apps-packs/run", response_model=RecipePlanOut)
def run_apps_pack(
    connection_id: str, body: AppsPackBody, db: Session = Depends(get_db)
) -> RecipePlanOut:
    client = _client(connection_id, db)
    pack = next((p for p in APPS_PACKS if p["id"] == body.pack_id), None)
    if not pack:
        raise HTTPException(status_code=404, detail="Unknown apps pack")

    steps: list[RecipeStep] = []
    warnings: list[str] = []
    to_install: list[str] = []
    for mod in pack["modules"]:
        try:
            rows = client.execute_kw(
                "ir.module.module",
                "search_read",
                [[("name", "=", mod)]],
                {"fields": ["name", "state", "shortdesc"], "limit": 1},
            )
            if not rows:
                warnings.append(f"{mod} not in Apps list")
                steps.append(
                    RecipeStep(
                        op="missing_module",
                        target=mod,
                        detail="Not found on instance",
                        would_write=False,
                    )
                )
                continue
            state = str(rows[0].get("state") or "")
            if state == "installed":
                steps.append(
                    RecipeStep(
                        op="already_installed",
                        target=mod,
                        detail=str(rows[0].get("shortdesc") or mod),
                        would_write=False,
                    )
                )
            else:
                to_install.append(mod)
                steps.append(
                    RecipeStep(
                        op="install_module",
                        target=mod,
                        detail=f"state={state} → install",
                    )
                )
        except OdooClientError as exc:
            warnings.append(f"{mod}: {exc}")

    if body.dry_run:
        return RecipePlanOut(
            ok=True,
            dry_run=True,
            steps=steps,
            warnings=warnings,
            message=f"Dry-run pack {pack['id']}: {len(to_install)} to install",
        )

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=f"Install apps pack “{pack['title']}” on this Odoo.",
            risks=[
                "Installs modules and their dependencies",
                "Can take minutes and briefly lock the registry",
                "Hard to fully uninstall later",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    applied: list[str] = []
    if to_install:
        try:
            ids = client.execute_kw(
                "ir.module.module", "search", [[("name", "in", to_install)]]
            )
            if ids:
                try:
                    client.execute_kw(
                        "ir.module.module", "button_immediate_install", [ids]
                    )
                except OdooClientError:
                    client.execute_kw("ir.module.module", "button_install", [ids])
                applied.append(f"install requested: {to_install}")
        except OdooClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RecipePlanOut(
        ok=True,
        dry_run=False,
        steps=steps,
        applied=applied,
        warnings=warnings,
        message=f"Apps pack {pack['id']} install kicked off",
    )


# --- Settings board (P2) ---------------------------------------------------

class SettingsPatchBody(ConfirmAdvancedBody):
    values: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True


@router.get("/settings")
def get_settings_board(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    current = capture_settings(client)
    return {
        "allowlist": sorted(SETTINGS_ALLOWLIST),
        "values": current,
        "message": f"{len(current)} allowlisted setting(s) readable",
    }


@router.post("/settings", response_model=RecipePlanOut)
def patch_settings_board(
    connection_id: str, body: SettingsPatchBody, db: Session = Depends(get_db)
) -> RecipePlanOut:
    client = _client(connection_id, db)
    steps = [
        RecipeStep(op="write_settings", target=k, detail=f"→ {v!r}")
        for k, v in (body.values or {}).items()
        if k in SETTINGS_ALLOWLIST
    ]
    if not steps:
        raise HTTPException(status_code=400, detail="No allowlisted settings in payload")

    if body.dry_run:
        return RecipePlanOut(
            ok=True,
            dry_run=True,
            steps=steps,
            message=f"Dry-run: {len(steps)} setting(s)",
        )

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Apply allowlisted res.config.settings toggles.",
            risks=[
                "Changes global Odoo settings",
                "May enable features that need modules",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    note = apply_settings(client, body.values)
    return RecipePlanOut(
        ok=True,
        dry_run=False,
        steps=steps,
        applied=[note or "settings applied"],
        message="Settings board applied",
    )


# --- Multi-company (P2) ----------------------------------------------------

class MultiCompanyBody(ConfirmAdvancedBody):
    name: str = Field(..., min_length=1, max_length=128)
    currency_code: str = Field("USD", min_length=3, max_length=8)
    country_code: str | None = None
    dry_run: bool = True


@router.post("/multi-company", response_model=RecipePlanOut)
def run_multi_company(
    connection_id: str, body: MultiCompanyBody, db: Session = Depends(get_db)
) -> RecipePlanOut:
    client = _client(connection_id, db)
    cur = _currency_id(client, body.currency_code)
    steps = [
        RecipeStep(
            op="create_company",
            target="res.company",
            detail=f"Create {body.name!r} currency={body.currency_code}",
        )
    ]
    warnings: list[str] = []
    if not cur:
        warnings.append(f"Currency {body.currency_code} missing")

    if body.dry_run:
        return RecipePlanOut(
            ok=True,
            dry_run=True,
            steps=steps,
            warnings=warnings,
            message="Dry-run multi-company",
        )

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Create an additional res.company on this Odoo.",
            risks=[
                "Adds a company record",
                "Users must be granted company access separately",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    vals: dict[str, Any] = {"name": body.name.strip()}
    if cur:
        vals["currency_id"] = cur
    try:
        new_id = int(client.execute_kw("res.company", "create", [vals]))
        country = _country_id(client, body.country_code)
        if country:
            rows = client.execute_kw(
                "res.company", "read", [[new_id]], {"fields": ["partner_id"]}
            )
            partner = rows[0].get("partner_id") if rows else None
            partner_id = (
                int(partner[0])
                if isinstance(partner, (list, tuple)) and partner
                else None
            )
            if partner_id:
                client.execute_kw(
                    "res.partner", "write", [[partner_id], {"country_id": country}]
                )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RecipePlanOut(
        ok=True,
        dry_run=False,
        steps=steps,
        applied=[f"company id={new_id}"],
        warnings=warnings,
        message=f"Created company {new_id}",
    )


# --- Master packs (P2) -----------------------------------------------------

MASTER_PACKS = {
    "uom_basic": {
        "title": "Basic UoM categories",
        "categories": ["Unit", "Weight", "Volume"],
    },
    "fiscal_stubs": {
        "title": "Fiscal position stubs",
        "positions": ["Domestic", "EU B2B", "Export"],
    },
}


class MasterPackBody(ConfirmAdvancedBody):
    pack_id: str = Field("uom_basic")
    dry_run: bool = True


@router.get("/master-packs")
def list_master_packs(connection_id: str) -> list[dict[str, Any]]:
    return [{"id": k, **v} for k, v in MASTER_PACKS.items()]


@router.post("/master-packs/run", response_model=RecipePlanOut)
def run_master_pack(
    connection_id: str, body: MasterPackBody, db: Session = Depends(get_db)
) -> RecipePlanOut:
    client = _client(connection_id, db)
    pack = MASTER_PACKS.get(body.pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Unknown master pack")

    steps: list[RecipeStep] = []
    warnings: list[str] = []

    if body.pack_id == "uom_basic":
        try:
            client.execute_kw("uom.category", "fields_get", [], {"attributes": ["string"]})
        except OdooClientError:
            warnings.append("uom.category unavailable — install Inventory/UoM first")
            return RecipePlanOut(
                ok=False,
                dry_run=body.dry_run,
                steps=[],
                warnings=warnings,
                message="UoM missing",
            )
        for name in pack["categories"]:
            existing = client.execute_kw(
                "uom.category", "search", [[("name", "=", name)]], {"limit": 1}
            )
            steps.append(
                RecipeStep(
                    op="exists" if existing else "create_uom_category",
                    target=name,
                    detail="uom.category",
                    would_write=not bool(existing),
                )
            )
    else:
        try:
            client.execute_kw(
                "account.fiscal.position", "fields_get", [], {"attributes": ["string"]}
            )
        except OdooClientError:
            warnings.append("account.fiscal.position unavailable — install Accounting")
            return RecipePlanOut(
                ok=False,
                dry_run=body.dry_run,
                steps=[],
                warnings=warnings,
                message="Fiscal missing",
            )
        for name in pack["positions"]:
            existing = client.execute_kw(
                "account.fiscal.position",
                "search",
                [[("name", "=", name)]],
                {"limit": 1},
            )
            steps.append(
                RecipeStep(
                    op="exists" if existing else "create_fiscal",
                    target=name,
                    detail="fiscal.position",
                    would_write=not bool(existing),
                )
            )

    if body.dry_run:
        return RecipePlanOut(
            ok=True,
            dry_run=True,
            steps=steps,
            warnings=warnings,
            message="Dry-run master pack",
        )

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=f"Apply master data pack “{pack['title']}”.",
            risks=[
                "Creates master-data records",
                "Does not replace localization CoA",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    applied: list[str] = []
    try:
        if body.pack_id == "uom_basic":
            for name in pack["categories"]:
                existing = client.execute_kw(
                    "uom.category", "search", [[("name", "=", name)]], {"limit": 1}
                )
                if not existing:
                    cid = client.execute_kw("uom.category", "create", [{"name": name}])
                    applied.append(f"uom.category {name} id={cid}")
        else:
            for name in pack["positions"]:
                existing = client.execute_kw(
                    "account.fiscal.position",
                    "search",
                    [[("name", "=", name)]],
                    {"limit": 1},
                )
                if not existing:
                    fid = client.execute_kw(
                        "account.fiscal.position", "create", [{"name": name}]
                    )
                    applied.append(f"fiscal {name} id={fid}")
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RecipePlanOut(
        ok=True,
        dry_run=False,
        steps=steps,
        applied=applied,
        warnings=warnings,
        message=f"Master pack {body.pack_id} applied",
    )
