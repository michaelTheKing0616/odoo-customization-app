"""Company settings, sequences, field-label CSV, and simple menu builder.

Mastery Phase M3 also covers paperformat, ir.default, ir.property, ir.cron,
and website page/menu surfaces (graceful when modules/models are absent).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import ConfirmAdvancedBody
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)

router = APIRouter(prefix="/connections/{connection_id}/config", tags=["config"])


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


def _m2o_id(val: Any) -> int | None:
    if isinstance(val, (list, tuple)) and val:
        return int(val[0])
    if isinstance(val, int):
        return val
    return None


def _m2o_name(val: Any) -> str | None:
    if isinstance(val, (list, tuple)) and len(val) > 1:
        return str(val[1]) if val[1] is not False else None
    return None


def _intersect_fields(client: Any, model: str, preferred: list[str]) -> list[str]:
    """Return preferred fields that exist on the model; fall back to preferred on failure."""
    try:
        meta = client.execute_kw(model, "fields_get", [], {"attributes": ["string"]})
        if isinstance(meta, dict) and meta:
            available = set(meta.keys())
            found = [f for f in preferred if f in available]
            return found or ["name"] if "name" in available else list(preferred)
    except Exception:  # noqa: BLE001 — degrade gracefully across majors
        pass
    return list(preferred)


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
    return bool(rows and rows[0].get("state") == "installed")


# --- Company ---


class CompanyOut(BaseModel):
    id: int
    name: str
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    street: str | None = None
    street2: str | None = None
    city: str | None = None
    zip: str | None = None
    vat: str | None = None
    company_registry: str | None = None
    currency_id: int | None = None
    currency_name: str | None = None


class UpdateCompanyBody(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    street: str | None = None
    street2: str | None = None
    city: str | None = None
    zip: str | None = None
    vat: str | None = None
    company_registry: str | None = None


_COMPANY_FIELDS = [
    "name",
    "email",
    "phone",
    "website",
    "street",
    "street2",
    "city",
    "zip",
    "vat",
    "company_registry",
    "currency_id",
]


def _company_out(row: dict[str, Any]) -> CompanyOut:
    cur = row.get("currency_id")
    currency_id = None
    currency_name = None
    if isinstance(cur, (list, tuple)) and cur:
        currency_id = int(cur[0])
        currency_name = str(cur[1]) if len(cur) > 1 else None
    elif isinstance(cur, int):
        currency_id = cur
    return CompanyOut(
        id=int(row["id"]),
        name=str(row.get("name") or ""),
        email=row.get("email") or None,
        phone=row.get("phone") or None,
        website=row.get("website") or None,
        street=row.get("street") or None,
        street2=row.get("street2") or None,
        city=row.get("city") or None,
        zip=row.get("zip") or None,
        vat=row.get("vat") or None,
        company_registry=row.get("company_registry") or None,
        currency_id=currency_id,
        currency_name=currency_name,
    )


@router.get("/companies", response_model=list[CompanyOut])
def list_companies(connection_id: str, db: Session = Depends(get_db)) -> list[CompanyOut]:
    client = _client(connection_id, db)
    try:
        ids = client.execute_kw("res.company", "search", [[]], {"limit": 50})
        rows = client.execute_kw(
            "res.company", "read", [ids], {"fields": _COMPANY_FIELDS}
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_company_out(r) for r in rows]


@router.patch("/companies/{company_id}", response_model=CompanyOut)
def update_company(
    connection_id: str,
    company_id: int,
    body: UpdateCompanyBody,
    db: Session = Depends(get_db),
) -> CompanyOut:
    client = _client(connection_id, db)
    vals = {k: v for k, v in body.model_dump().items() if v is not None}
    if not vals:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        client.execute_kw("res.company", "write", [[company_id], vals])
        rows = client.execute_kw(
            "res.company", "read", [[company_id]], {"fields": _COMPANY_FIELDS}
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Company not found")
    return _company_out(rows[0])


# --- Sequences ---


class SequenceOut(BaseModel):
    id: int
    name: str
    code: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    padding: int = 0
    number_next: int = 1
    number_increment: int = 1
    active: bool = True


class UpdateSequenceBody(BaseModel):
    name: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    padding: int | None = Field(None, ge=0, le=16)
    number_next: int | None = Field(None, ge=1)
    number_increment: int | None = Field(None, ge=1)
    active: bool | None = None


_SEQ_FIELDS = [
    "name",
    "code",
    "prefix",
    "suffix",
    "padding",
    "number_next_actual",
    "number_increment",
    "active",
]


def _seq_out(row: dict[str, Any]) -> SequenceOut:
    next_val = row.get("number_next_actual")
    if next_val is False or next_val is None:
        next_val = row.get("number_next") or 1
    return SequenceOut(
        id=int(row["id"]),
        name=str(row.get("name") or ""),
        code=row.get("code") or None,
        prefix=row.get("prefix") or None,
        suffix=row.get("suffix") or None,
        padding=int(row.get("padding") or 0),
        number_next=int(next_val or 1),
        number_increment=int(row.get("number_increment") or 1),
        active=bool(row.get("active", True)),
    )


@router.get("/sequences", response_model=list[SequenceOut])
def list_sequences(
    connection_id: str,
    q: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[SequenceOut]:
    client = _client(connection_id, db)
    domain: list[Any] = []
    if q:
        domain = ["|", ("name", "ilike", q), ("code", "ilike", q)]
    try:
        ids = client.execute_kw(
            "ir.sequence", "search", [domain], {"limit": 200, "order": "name"}
        )
        rows = client.execute_kw("ir.sequence", "read", [ids], {"fields": _SEQ_FIELDS})
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_seq_out(r) for r in rows]


@router.patch("/sequences/{sequence_id}", response_model=SequenceOut)
def update_sequence(
    connection_id: str,
    sequence_id: int,
    body: UpdateSequenceBody,
    db: Session = Depends(get_db),
) -> SequenceOut:
    client = _client(connection_id, db)
    vals: dict[str, Any] = {}
    raw = body.model_dump(exclude_none=True)
    if "number_next" in raw:
        vals["number_next"] = raw.pop("number_next")
    vals.update(raw)
    if not vals:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        client.execute_kw("ir.sequence", "write", [[sequence_id], vals])
        rows = client.execute_kw(
            "ir.sequence", "read", [[sequence_id]], {"fields": _SEQ_FIELDS}
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return _seq_out(rows[0])


# --- Field labels (translation-style CSV) ---


@router.get("/field-labels.csv")
def export_field_labels(
    connection_id: str,
    model: str = Query(..., min_length=1),
    lang: str | None = Query(None),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    """Export customizable field labels as CSV (model,name,ttype,string[,lang])."""
    client = _client(connection_id, db)
    kwargs: dict[str, Any] = {
        "fields": ["name", "ttype", "field_description", "state"],
        "limit": 2000,
        "order": "name",
    }
    if lang:
        kwargs["context"] = {"lang": lang}
    try:
        rows = client.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "=", model)]],
            kwargs,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    buf = io.StringIO()
    w = csv.writer(buf)
    header = ["model", "name", "ttype", "string", "state"]
    if lang:
        header.append("lang")
    w.writerow(header)
    for r in rows:
        line = [
            model,
            r.get("name") or "",
            r.get("ttype") or "",
            r.get("field_description") or "",
            r.get("state") or "",
        ]
        if lang:
            line.append(lang)
        w.writerow(line)
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{model.replace(".", "_")}_labels.csv"'
        },
    )


class FieldLabelRow(BaseModel):
    model: str
    name: str
    string: str


class ImportFieldLabelsBody(BaseModel):
    rows: list[FieldLabelRow]
    dry_run: bool = True


class ImportFieldLabelsOut(BaseModel):
    ok: bool
    updated: int
    skipped: int
    failed: int
    message: str
    errors: list[str] = Field(default_factory=list)


@router.post("/field-labels", response_model=ImportFieldLabelsOut)
def import_field_labels(
    connection_id: str,
    body: ImportFieldLabelsBody,
    db: Session = Depends(get_db),
) -> ImportFieldLabelsOut:
    """Update field_description from CSV-like rows (manual translation polish)."""
    client = _client(connection_id, db)
    updated = skipped = failed = 0
    errors: list[str] = []
    for row in body.rows:
        try:
            found = client.execute_kw(
                "ir.model.fields",
                "search",
                [[("model", "=", row.model), ("name", "=", row.name)]],
                {"limit": 1},
            )
            if not found:
                failed += 1
                errors.append(f"{row.model}.{row.name}: field not found")
                continue
            if body.dry_run:
                updated += 1
                continue
            client.execute_kw(
                "ir.model.fields",
                "write",
                [[int(found[0])], {"field_description": row.string}],
            )
            updated += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append(f"{row.model}.{row.name}: {exc}")
    message = (
        f"{'Dry-run' if body.dry_run else 'Commit'}: "
        f"{updated} update, {failed} failed, {skipped} skipped"
    )
    return ImportFieldLabelsOut(
        ok=failed == 0,
        updated=updated,
        skipped=skipped,
        failed=failed,
        message=message,
        errors=errors[:50],
    )


# --- Menus ---


class MenuOut(BaseModel):
    id: int
    name: str
    parent_id: int | None = None
    parent_name: str | None = None
    action: str | None = None
    sequence: int = 10
    web_icon: str | None = None


class CreateAppMenuBody(BaseModel):
    root_name: str = Field(..., min_length=1, max_length=120)
    model: str = Field(..., min_length=1)
    child_label: str | None = None
    web_icon: str = "base,static/description/icon.png"


class CreateAppMenuOut(BaseModel):
    ok: bool
    root_menu_id: int
    child_menu_id: int | None = None
    action_id: int | None = None
    message: str


@router.get("/menus", response_model=list[MenuOut])
def list_menus(
    connection_id: str,
    roots_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[MenuOut]:
    client = _client(connection_id, db)
    domain: list[Any] = [("parent_id", "=", False)] if roots_only else []
    try:
        rows = client.execute_kw(
            "ir.ui.menu",
            "search_read",
            [domain],
            {
                "fields": ["name", "parent_id", "action", "sequence", "web_icon"],
                "limit": 300,
                "order": "sequence, id",
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    out: list[MenuOut] = []
    for r in rows:
        parent = r.get("parent_id")
        parent_id = int(parent[0]) if isinstance(parent, (list, tuple)) and parent else None
        parent_name = (
            str(parent[1]) if isinstance(parent, (list, tuple)) and len(parent) > 1 else None
        )
        action = r.get("action")
        out.append(
            MenuOut(
                id=int(r["id"]),
                name=str(r.get("name") or ""),
                parent_id=parent_id,
                parent_name=parent_name,
                action=action if isinstance(action, str) else None,
                sequence=int(r.get("sequence") or 10),
                web_icon=r.get("web_icon") or None,
            )
        )
    return out


@router.post("/menus/app", response_model=CreateAppMenuOut, status_code=201)
def create_app_menu(
    connection_id: str, body: CreateAppMenuBody, db: Session = Depends(get_db)
) -> CreateAppMenuOut:
    """Create root app menu + child action menu for a model (idempotent by names)."""
    client = _client(connection_id, db)
    child_label = body.child_label or body.model
    try:
        menu_ids = client.ensure_app_menus(
            root_name=body.root_name,
            model_entries=[(body.model, child_label)],
            web_icon=body.web_icon,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    root_id = int(menu_ids[0]) if menu_ids else 0
    child_id = int(menu_ids[1]) if len(menu_ids) > 1 else None
    return CreateAppMenuOut(
        ok=True,
        root_menu_id=root_id,
        child_menu_id=child_id,
        message=f"App menu '{body.root_name}' ready with child '{child_label}'",
    )


# --- Create sequence ---


class CreateSequenceBody(BaseModel):
    name: str = Field(..., min_length=1)
    code: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    padding: int = Field(5, ge=0, le=16)
    number_next: int = Field(1, ge=1)
    number_increment: int = Field(1, ge=1)


@router.post("/sequences", response_model=SequenceOut, status_code=201)
def create_sequence(
    connection_id: str, body: CreateSequenceBody, db: Session = Depends(get_db)
) -> SequenceOut:
    client = _client(connection_id, db)
    vals: dict[str, Any] = {
        "name": body.name,
        "padding": body.padding,
        "number_next": body.number_next,
        "number_increment": body.number_increment,
    }
    if body.code:
        vals["code"] = body.code
    if body.prefix is not None:
        vals["prefix"] = body.prefix
    if body.suffix is not None:
        vals["suffix"] = body.suffix
    try:
        seq_id = int(client.execute_kw("ir.sequence", "create", [vals]))
        rows = client.execute_kw(
            "ir.sequence", "read", [[seq_id]], {"fields": _SEQ_FIELDS}
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _seq_out(rows[0])


# --- Mail templates ---


class MailTemplateOut(BaseModel):
    id: int
    name: str
    model: str | None = None
    subject: str | None = None
    body_html: str | None = None
    email_to: str | None = None
    description: str | None = None


class CreateMailTemplateBody(BaseModel):
    name: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    body_html: str = Field(..., min_length=1)
    email_to: str = Field(
        "{{ object.email or (object.partner_id.email if object.partner_id else '') }}",
        min_length=1,
    )
    description: str | None = None


class UpdateMailTemplateBody(BaseModel):
    name: str | None = None
    subject: str | None = None
    body_html: str | None = None
    email_to: str | None = None
    description: str | None = None


def _mail_out(row: dict[str, Any]) -> MailTemplateOut:
    return MailTemplateOut(
        id=int(row["id"]),
        name=str(row.get("name") or ""),
        model=row.get("model") or None,
        subject=row.get("subject") or None,
        body_html=row.get("body_html") or None,
        email_to=row.get("email_to") or None,
        description=row.get("description") or None,
    )


@router.get("/mail-templates", response_model=list[MailTemplateOut])
def list_mail_templates_config(
    connection_id: str,
    model: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[MailTemplateOut]:
    client = _client(connection_id, db)
    try:
        rows = client.list_mail_templates(model=model, limit=200)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_mail_out(r) for r in rows]


@router.post("/mail-templates", response_model=MailTemplateOut, status_code=201)
def create_mail_template_config(
    connection_id: str, body: CreateMailTemplateBody, db: Session = Depends(get_db)
) -> MailTemplateOut:
    client = _client(connection_id, db)
    try:
        tid = client.create_mail_template(
            name=body.name,
            model=body.model,
            subject=body.subject,
            body_html=body.body_html,
            email_to=body.email_to,
            description=body.description,
        )
        rows = client.execute_kw(
            "mail.template",
            "read",
            [[tid]],
            {
                "fields": [
                    "name",
                    "model",
                    "subject",
                    "body_html",
                    "email_to",
                    "description",
                ]
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _mail_out(rows[0])


@router.patch("/mail-templates/{template_id}", response_model=MailTemplateOut)
def update_mail_template_config(
    connection_id: str,
    template_id: int,
    body: UpdateMailTemplateBody,
    db: Session = Depends(get_db),
) -> MailTemplateOut:
    client = _client(connection_id, db)
    vals = {k: v for k, v in body.model_dump().items() if v is not None}
    if not vals:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        client.execute_kw("mail.template", "write", [[template_id], vals])
        rows = client.execute_kw(
            "mail.template",
            "read",
            [[template_id]],
            {
                "fields": [
                    "name",
                    "model",
                    "subject",
                    "body_html",
                    "email_to",
                    "description",
                ]
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Template not found")
    return _mail_out(rows[0])


# --- Activity types ---


class ActivityTypeOut(BaseModel):
    id: int
    name: str
    summary: str | None = None
    icon: str | None = None
    category: str | None = None
    active: bool = True


class CreateActivityTypeBody(BaseModel):
    name: str = Field(..., min_length=1)
    summary: str | None = None
    icon: str | None = "fa-tasks"
    category: str | None = None


@router.get("/activity-types", response_model=list[ActivityTypeOut])
def list_activity_types_config(
    connection_id: str, db: Session = Depends(get_db)
) -> list[ActivityTypeOut]:
    client = _client(connection_id, db)
    try:
        rows = client.execute_kw(
            "mail.activity.type",
            "search_read",
            [[]],
            {
                "fields": ["name", "summary", "icon", "category", "active"],
                "limit": 200,
                "order": "sequence, id",
            },
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        ActivityTypeOut(
            id=int(r["id"]),
            name=str(r.get("name") or ""),
            summary=r.get("summary") or None,
            icon=r.get("icon") or None,
            category=r.get("category") or None,
            active=bool(r.get("active", True)),
        )
        for r in rows
    ]


@router.post("/activity-types", response_model=ActivityTypeOut, status_code=201)
def create_activity_type(
    connection_id: str, body: CreateActivityTypeBody, db: Session = Depends(get_db)
) -> ActivityTypeOut:
    client = _client(connection_id, db)
    vals: dict[str, Any] = {"name": body.name}
    if body.summary:
        vals["summary"] = body.summary
    if body.icon:
        vals["icon"] = body.icon
    if body.category:
        vals["category"] = body.category
    try:
        tid = int(client.execute_kw("mail.activity.type", "create", [vals]))
        rows = client.execute_kw(
            "mail.activity.type",
            "read",
            [[tid]],
            {"fields": ["name", "summary", "icon", "category", "active"]},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    r = rows[0]
    return ActivityTypeOut(
        id=tid,
        name=str(r.get("name") or ""),
        summary=r.get("summary") or None,
        icon=r.get("icon") or None,
        category=r.get("category") or None,
        active=bool(r.get("active", True)),
    )


# --- Languages + fuller translation CSV ---


class LangOut(BaseModel):
    id: int
    code: str
    name: str
    active: bool = True


@router.get("/languages", response_model=list[LangOut])
def list_languages(connection_id: str, db: Session = Depends(get_db)) -> list[LangOut]:
    client = _client(connection_id, db)
    try:
        rows = client.execute_kw(
            "res.lang",
            "search_read",
            [[("active", "=", True)]],
            {"fields": ["code", "name", "active"], "limit": 100, "order": "name"},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        LangOut(
            id=int(r["id"]),
            code=str(r.get("code") or ""),
            name=str(r.get("name") or ""),
            active=bool(r.get("active", True)),
        )
        for r in rows
    ]


@router.get("/translations.csv")
def export_translations_csv(
    connection_id: str,
    model: str = Query(..., min_length=1),
    lang: str = Query("en_US", min_length=2),
    include_menus: bool = Query(True),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    """Export field labels (+ optional root menu names) for a language.

    Uses ``context={'lang': lang}`` reads — works on Odoo 19 without ``ir.translation``.
    """
    client = _client(connection_id, db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["type", "model", "name", "lang", "source", "value"])
    try:
        fields = client.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "=", model)]],
            {
                "fields": ["name", "field_description", "ttype"],
                "limit": 2000,
                "order": "name",
                "context": {"lang": lang},
            },
        )
        for f in fields:
            w.writerow(
                [
                    "field",
                    model,
                    f.get("name") or "",
                    lang,
                    f.get("ttype") or "",
                    f.get("field_description") or "",
                ]
            )
        if include_menus:
            menus = client.execute_kw(
                "ir.ui.menu",
                "search_read",
                [[("parent_id", "=", False)]],
                {
                    "fields": ["name", "complete_name"],
                    "limit": 200,
                    "context": {"lang": lang},
                },
            )
            for m in menus:
                w.writerow(
                    [
                        "menu",
                        "ir.ui.menu",
                        str(m.get("id")),
                        lang,
                        m.get("complete_name") or "",
                        m.get("name") or "",
                    ]
                )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{model.replace(".", "_")}_{lang}_translations.csv"'
            )
        },
    )


class TranslationRow(BaseModel):
    type: str = "field"  # field | menu
    model: str
    name: str
    lang: str
    value: str


class ImportTranslationsBody(BaseModel):
    rows: list[TranslationRow]
    dry_run: bool = True


class ImportTranslationsOut(BaseModel):
    ok: bool
    updated: int
    failed: int
    skipped: int
    message: str
    errors: list[str] = Field(default_factory=list)


@router.post("/translations", response_model=ImportTranslationsOut)
def import_translations(
    connection_id: str,
    body: ImportTranslationsBody,
    db: Session = Depends(get_db),
) -> ImportTranslationsOut:
    """Import lang-scoped field labels and root menu names."""
    client = _client(connection_id, db)
    updated = failed = skipped = 0
    errors: list[str] = []
    for row in body.rows:
        try:
            if row.type == "field":
                found = client.execute_kw(
                    "ir.model.fields",
                    "search",
                    [[("model", "=", row.model), ("name", "=", row.name)]],
                    {"limit": 1},
                )
                if not found:
                    failed += 1
                    errors.append(f"field {row.model}.{row.name}: not found")
                    continue
                if body.dry_run:
                    updated += 1
                    continue
                client.execute_kw(
                    "ir.model.fields",
                    "write",
                    [[int(found[0])], {"field_description": row.value}],
                    {"context": {"lang": row.lang}},
                )
                updated += 1
            elif row.type == "menu":
                try:
                    menu_id = int(row.name)
                except ValueError:
                    failed += 1
                    errors.append(f"menu name must be id, got {row.name!r}")
                    continue
                if body.dry_run:
                    updated += 1
                    continue
                client.execute_kw(
                    "ir.ui.menu",
                    "write",
                    [[menu_id], {"name": row.value}],
                    {"context": {"lang": row.lang}},
                )
                updated += 1
            else:
                skipped += 1
                errors.append(f"unknown type {row.type!r}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append(f"{row.type}:{row.model}.{row.name}: {exc}")
    return ImportTranslationsOut(
        ok=failed == 0,
        updated=updated,
        failed=failed,
        skipped=skipped,
        message=(
            f"{'Dry-run' if body.dry_run else 'Commit'}: "
            f"{updated} update, {failed} failed, {skipped} skipped"
        ),
        errors=errors[:50],
    )


# --- CMP-11: i18n probe + ModuleSpec artifact translations ---


class I18nProbeOut(BaseModel):
    ok: bool
    major: int | None = None
    method: str
    context_lang_reads: bool
    ir_translation_model: bool
    message: str


class SpecTranslationsExportBody(BaseModel):
    spec: dict[str, Any] = Field(default_factory=dict)
    lang: str = Field("fr_FR", min_length=2)


class SpecTranslationsImportBody(BaseModel):
    csv_text: str = Field(..., min_length=1)
    dry_run: bool = True


class SpecTranslationsImportOut(BaseModel):
    ok: bool
    dry_run: bool
    updated: int
    skipped: int
    preview: list[dict[str, str]] = Field(default_factory=list)


@router.get("/i18n/probe", response_model=I18nProbeOut)
def i18n_probe(connection_id: str, db: Session = Depends(get_db)) -> I18nProbeOut:
    from app.i18n_probe import probe_i18n

    client = _client(connection_id, db)
    return I18nProbeOut.model_validate(probe_i18n(client))


@router.post("/i18n/spec-export")
def export_spec_translations(
    connection_id: str,
    body: SpecTranslationsExportBody,
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    from app.i18n_artifacts import export_spec_translations_csv

    client = _client(connection_id, db)
    try:
        csv_text = export_spec_translations_csv(client, spec=body.spec, lang=body.lang)
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlainTextResponse(
        csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="modulespec_{body.lang}_translations.csv"'
            )
        },
    )


@router.post("/i18n/spec-import", response_model=SpecTranslationsImportOut)
def import_spec_translations(
    connection_id: str,
    body: SpecTranslationsImportBody,
    db: Session = Depends(get_db),
) -> SpecTranslationsImportOut:
    from app.i18n_artifacts import import_spec_translations_csv

    client = _client(connection_id, db)
    reader = csv.reader(io.StringIO(body.csv_text))
    rows = list(reader)
    result = import_spec_translations_csv(client, rows=rows, dry_run=body.dry_run)
    return SpecTranslationsImportOut.model_validate(result)


# --- M3: Paperformat ---


_PAPERFORMAT_PREFERRED = [
    "name",
    "format",
    "orientation",
    "margin_top",
    "margin_bottom",
    "margin_left",
    "margin_right",
    "header_line",
    "header_spacing",
    "dpi",
    "page_height",
    "page_width",
]


class PaperFormatOut(BaseModel):
    id: int
    name: str
    format: str | None = None
    orientation: str | None = None
    margin_top: float | None = None
    margin_bottom: float | None = None
    margin_left: float | None = None
    margin_right: float | None = None
    header_line: bool | None = None
    header_spacing: float | None = None
    dpi: int | None = None
    page_height: float | None = None
    page_width: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class UpsertPaperFormatBody(BaseModel):
    """Create (no id) or update (id set) a report.paperformat row."""

    id: int | None = None
    name: str | None = None
    format: str | None = None
    orientation: str | None = None
    margin_top: float | None = None
    margin_bottom: float | None = None
    margin_left: float | None = None
    margin_right: float | None = None
    header_line: bool | None = None
    header_spacing: float | None = None
    dpi: int | None = None
    page_height: float | None = None
    page_width: float | None = None


def _float_or_none(val: Any) -> float | None:
    if val is None or val is False:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _paperformat_out(row: dict[str, Any], known: set[str]) -> PaperFormatOut:
    known_core = {
        "id",
        "name",
        "format",
        "orientation",
        "margin_top",
        "margin_bottom",
        "margin_left",
        "margin_right",
        "header_line",
        "header_spacing",
        "dpi",
        "page_height",
        "page_width",
    }
    extra = {
        k: v
        for k, v in row.items()
        if k in known and k not in known_core and v is not False
    }
    header_line: bool | None = None
    if "header_line" in row and row.get("header_line") is not None:
        header_line = bool(row.get("header_line"))
    return PaperFormatOut(
        id=int(row["id"]),
        name=str(row.get("name") or ""),
        format=row.get("format") or None,
        orientation=row.get("orientation") or None,
        margin_top=_float_or_none(row.get("margin_top")),
        margin_bottom=_float_or_none(row.get("margin_bottom")),
        margin_left=_float_or_none(row.get("margin_left")),
        margin_right=_float_or_none(row.get("margin_right")),
        header_line=header_line,
        header_spacing=_float_or_none(row.get("header_spacing")),
        dpi=int(row["dpi"]) if row.get("dpi") not in (None, False) else None,
        page_height=_float_or_none(row.get("page_height")),
        page_width=_float_or_none(row.get("page_width")),
        extra=extra,
    )


@router.get("/paperformats", response_model=list[PaperFormatOut])
def list_config_paperformats(
    connection_id: str, db: Session = Depends(get_db)
) -> list[PaperFormatOut]:
    client = _client(connection_id, db)
    fields = _intersect_fields(client, "report.paperformat", _PAPERFORMAT_PREFERRED)
    known = set(fields)
    try:
        rows = client.execute_kw(
            "report.paperformat",
            "search_read",
            [[]],
            {"fields": fields, "limit": 100, "order": "name"},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_paperformat_out(r, known) for r in rows]


@router.post("/paperformats", response_model=PaperFormatOut)
def upsert_config_paperformat(
    connection_id: str, body: UpsertPaperFormatBody, db: Session = Depends(get_db)
) -> PaperFormatOut:
    client = _client(connection_id, db)
    fields = _intersect_fields(client, "report.paperformat", _PAPERFORMAT_PREFERRED)
    known = set(fields)
    raw = body.model_dump(exclude_none=True)
    pf_id = raw.pop("id", None)
    vals = {k: v for k, v in raw.items() if k in known}
    if not vals and pf_id is None:
        raise HTTPException(status_code=400, detail="No paperformat fields to write")
    if pf_id is None and "name" not in vals:
        raise HTTPException(status_code=400, detail="name is required when creating")
    try:
        from app.snapshots import snapshot_paperformat

        if pf_id is not None:
            try:
                snapshot_paperformat(db, connection_id, client, int(pf_id))
            except Exception:  # noqa: BLE001 — snapshot best-effort before mutate
                pass
        if pf_id is None:
            new_id = int(client.execute_kw("report.paperformat", "create", [vals]))
            try:
                snap = snapshot_paperformat(db, connection_id, client, new_id)
                import json as _json

                payload = _json.loads(snap.payload_json)
                payload["created"] = True
                snap.payload_json = _json.dumps(payload)
                db.add(snap)
                db.commit()
            except Exception:  # noqa: BLE001
                pass
        else:
            if vals:
                client.execute_kw("report.paperformat", "write", [[pf_id], vals])
            new_id = int(pf_id)
        rows = client.execute_kw(
            "report.paperformat", "read", [[new_id]], {"fields": fields}
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Paperformat not found")
    return _paperformat_out(rows[0], known)


# --- M3: ir.default ---


_DEFAULT_PREFERRED = [
    "field_id",
    "json_value",
    "user_id",
    "company_id",
    "condition",
]


class IrDefaultOut(BaseModel):
    id: int
    field_id: int | None = None
    field_name: str | None = None
    model: str | None = None
    json_value: str | None = None
    user_id: int | None = None
    company_id: int | None = None
    condition: str | None = None


class UpsertIrDefaultBody(BaseModel):
    model_id: int | None = None
    model: str | None = Field(None, description="Technical model name, e.g. res.partner")
    field_id: int | None = None
    field_name: str | None = None
    json_value: str | None = None
    value: Any | None = Field(
        None, description="Plain value; serialized to json_value when json_value omitted"
    )
    user_id: int | None = None
    company_id: int | None = None
    condition: str | None = None


def _default_out(row: dict[str, Any], *, model_name: str | None = None) -> IrDefaultOut:
    field = row.get("field_id")
    return IrDefaultOut(
        id=int(row["id"]),
        field_id=_m2o_id(field),
        field_name=_m2o_name(field),
        model=model_name,
        json_value=row.get("json_value") or None,
        user_id=_m2o_id(row.get("user_id")),
        company_id=_m2o_id(row.get("company_id")),
        condition=row.get("condition") or None,
    )


def _resolve_field_id(
    client: Any,
    *,
    field_id: int | None,
    field_name: str | None,
    model: str | None,
    model_id: int | None,
) -> tuple[int, str | None]:
    if field_id is not None:
        rows = client.execute_kw(
            "ir.model.fields",
            "read",
            [[field_id]],
            {"fields": ["name", "model", "model_id"]},
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"field_id {field_id} not found")
        return int(field_id), rows[0].get("model") or model

    if not field_name:
        raise HTTPException(status_code=400, detail="field_id or field_name is required")

    model_name = model
    if model_id is not None and not model_name:
        mrows = client.execute_kw(
            "ir.model", "read", [[model_id]], {"fields": ["model"]}
        )
        if not mrows:
            raise HTTPException(status_code=404, detail=f"model_id {model_id} not found")
        model_name = str(mrows[0].get("model") or "")

    if not model_name:
        raise HTTPException(
            status_code=400,
            detail="model or model_id is required when resolving by field_name",
        )

    found = client.execute_kw(
        "ir.model.fields",
        "search",
        [[("model", "=", model_name), ("name", "=", field_name)]],
        {"limit": 1},
    )
    if not found:
        raise HTTPException(
            status_code=404, detail=f"Field {model_name}.{field_name} not found"
        )
    return int(found[0]), model_name


@router.get("/defaults", response_model=list[IrDefaultOut])
def list_ir_defaults(
    connection_id: str,
    model: str = Query(..., min_length=1, description="Technical model name"),
    db: Session = Depends(get_db),
) -> list[IrDefaultOut]:
    client = _client(connection_id, db)
    fields = _intersect_fields(client, "ir.default", _DEFAULT_PREFERRED)
    try:
        rows = client.execute_kw(
            "ir.default",
            "search_read",
            [[("field_id.model", "=", model)]],
            {"fields": fields, "limit": 500},
        )
    except OdooClientError as exc:
        # Some majors may not allow dotted path — resolve field ids first.
        try:
            field_ids = client.execute_kw(
                "ir.model.fields",
                "search",
                [[("model", "=", model)]],
                {"limit": 5000},
            )
            if not field_ids:
                return []
            rows = client.execute_kw(
                "ir.default",
                "search_read",
                [[("field_id", "in", field_ids)]],
                {"fields": fields, "limit": 500},
            )
        except OdooClientError as exc2:
            raise HTTPException(status_code=400, detail=str(exc2)) from exc2
    return [_default_out(r, model_name=model) for r in rows]


@router.post("/defaults", response_model=IrDefaultOut)
def upsert_ir_default(
    connection_id: str, body: UpsertIrDefaultBody, db: Session = Depends(get_db)
) -> IrDefaultOut:
    client = _client(connection_id, db)
    fields = _intersect_fields(client, "ir.default", _DEFAULT_PREFERRED)
    known = set(fields)

    try:
        field_id, model_name = _resolve_field_id(
            client,
            field_id=body.field_id,
            field_name=body.field_name,
            model=body.model,
            model_id=body.model_id,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.json_value is not None:
        json_value = body.json_value
    elif body.value is not None:
        json_value = json.dumps(body.value)
    else:
        raise HTTPException(status_code=400, detail="json_value or value is required")

    vals: dict[str, Any] = {"field_id": field_id}
    if "json_value" in known:
        vals["json_value"] = json_value
    elif "value" in known:
        vals["value"] = body.value if body.value is not None else json_value
    else:
        raise HTTPException(
            status_code=400,
            detail="ir.default has neither json_value nor value on this database",
        )

    if body.user_id is not None and "user_id" in known:
        vals["user_id"] = body.user_id
    if body.company_id is not None and "company_id" in known:
        vals["company_id"] = body.company_id
    if body.condition is not None and "condition" in known:
        vals["condition"] = body.condition

    domain: list[Any] = [("field_id", "=", field_id)]
    if body.user_id is not None:
        domain.append(("user_id", "=", body.user_id))
    else:
        domain.append(("user_id", "=", False))
    if body.company_id is not None:
        domain.append(("company_id", "=", body.company_id))

    try:
        existing = client.execute_kw(
            "ir.default", "search", [domain], {"limit": 1}
        )
        from app.snapshots import snapshot_ir_default
        import json as _json

        if existing:
            try:
                snapshot_ir_default(db, connection_id, client, int(existing[0]))
            except Exception:  # noqa: BLE001 — snapshot best-effort before mutate
                pass
            write_vals = {k: v for k, v in vals.items() if k != "field_id"}
            client.execute_kw("ir.default", "write", [[int(existing[0])], write_vals])
            rid = int(existing[0])
        else:
            rid = int(client.execute_kw("ir.default", "create", [vals]))
            try:
                snap = snapshot_ir_default(db, connection_id, client, rid)
                payload = _json.loads(snap.payload_json)
                payload["created"] = True
                snap.payload_json = _json.dumps(payload)
                db.add(snap)
                db.commit()
            except Exception:  # noqa: BLE001
                pass
        rows = client.execute_kw("ir.default", "read", [[rid]], {"fields": fields})
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="ir.default row not found after upsert")
    return _default_out(rows[0], model_name=model_name)


# --- M3: ir.property ---


_PROPERTY_PREFERRED = [
    "name",
    "fields_id",
    "res_id",
    "company_id",
    "value_text",
    "value_integer",
    "value_float",
    "value_datetime",
    "value_binary",
    "value_reference",
    "type",
]


class IrPropertyOut(BaseModel):
    id: int
    name: str | None = None
    fields_id: int | None = None
    field_name: str | None = None
    res_id: str | None = None
    company_id: int | None = None
    type: str | None = None
    value_text: str | None = None
    value_integer: int | None = None
    value_float: float | None = None
    value_reference: str | None = None


@router.get("/properties", response_model=list[IrPropertyOut])
def list_ir_properties(
    connection_id: str,
    model: str | None = Query(None, description="Optional model filter via fields_id.model"),
    db: Session = Depends(get_db),
) -> list[IrPropertyOut]:
    client = _client(connection_id, db)
    try:
        exists = client.model_exists("ir.property")
    except Exception:  # noqa: BLE001
        exists = False
    if not exists:
        raise HTTPException(
            status_code=404,
            detail="ir.property not available on this database",
        )

    fields = _intersect_fields(client, "ir.property", _PROPERTY_PREFERRED)
    domain: list[Any] = []
    if model:
        domain = [("fields_id.model", "=", model)]
    try:
        rows = client.execute_kw(
            "ir.property",
            "search_read",
            [domain],
            {"fields": fields, "limit": 500},
        )
    except OdooClientError as exc:
        if model:
            try:
                field_ids = client.execute_kw(
                    "ir.model.fields",
                    "search",
                    [[("model", "=", model)]],
                    {"limit": 5000},
                )
                rows = client.execute_kw(
                    "ir.property",
                    "search_read",
                    [[("fields_id", "in", field_ids or [0])]],
                    {"fields": fields, "limit": 500},
                )
            except OdooClientError as exc2:
                raise HTTPException(status_code=400, detail=str(exc2)) from exc2
        else:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    out: list[IrPropertyOut] = []
    for r in rows:
        fid = r.get("fields_id")
        out.append(
            IrPropertyOut(
                id=int(r["id"]),
                name=r.get("name") or None,
                fields_id=_m2o_id(fid),
                field_name=_m2o_name(fid),
                res_id=(
                    None
                    if r.get("res_id") in (None, False)
                    else str(r.get("res_id"))
                ),
                company_id=_m2o_id(r.get("company_id")),
                type=r.get("type") or None,
                value_text=r.get("value_text") or None,
                value_integer=(
                    int(r["value_integer"])
                    if r.get("value_integer") not in (None, False)
                    else None
                ),
                value_float=_float_or_none(r.get("value_float")),
                value_reference=r.get("value_reference") or None,
            )
        )
    return out


# --- M3: ir.cron ---


_CRON_PREFERRED = [
    "name",
    "model_id",
    "model_name",
    "interval_number",
    "interval_type",
    "active",
    "nextcall",
    "lastcall",
    "priority",
    "user_id",
]


class IrCronOut(BaseModel):
    id: int
    name: str
    model_id: int | None = None
    model_name: str | None = None
    interval_number: int | None = None
    interval_type: str | None = None
    active: bool = True
    nextcall: str | None = None
    lastcall: str | None = None
    priority: int | None = None


class PatchCronActiveBody(ConfirmAdvancedBody):
    active: bool


def _cron_out(row: dict[str, Any]) -> IrCronOut:
    mid = row.get("model_id")
    model_name = row.get("model_name") or None
    if not model_name:
        model_name = _m2o_name(mid)
    return IrCronOut(
        id=int(row["id"]),
        name=str(row.get("name") or ""),
        model_id=_m2o_id(mid),
        model_name=model_name if model_name else None,
        interval_number=(
            int(row["interval_number"])
            if row.get("interval_number") not in (None, False)
            else None
        ),
        interval_type=row.get("interval_type") or None,
        active=bool(row.get("active", True)),
        nextcall=str(row["nextcall"]) if row.get("nextcall") else None,
        lastcall=str(row["lastcall"]) if row.get("lastcall") else None,
        priority=(
            int(row["priority"]) if row.get("priority") not in (None, False) else None
        ),
    )


@router.get("/crons", response_model=list[IrCronOut])
def list_ir_crons(
    connection_id: str,
    q: str | None = Query(None),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> list[IrCronOut]:
    client = _client(connection_id, db)
    fields = _intersect_fields(client, "ir.cron", _CRON_PREFERRED)
    domain: list[Any] = []
    if q:
        domain.append(("name", "ilike", q))
    if active is not None:
        domain.append(("active", "=", active))
    try:
        rows = client.execute_kw(
            "ir.cron",
            "search_read",
            [domain],
            {"fields": fields, "limit": 300, "order": "name"},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_cron_out(r) for r in rows]


@router.patch("/crons/{cron_id}", response_model=IrCronOut)
def patch_ir_cron_active(
    connection_id: str,
    cron_id: int,
    body: PatchCronActiveBody,
    db: Session = Depends(get_db),
) -> IrCronOut:
    """Set ir.cron active flag. Deactivate requires advanced confirm phrase."""
    client = _client(connection_id, db)
    if not body.active:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    "Deactivating a scheduled action (ir.cron) stops automated jobs "
                    "on this Odoo database. Missed runs are not replayed automatically."
                ),
                risks=[
                    "Background jobs stop until re-enabled",
                    "Dependent business processes may stall (reminders, sync, cleanup)",
                    "Confirm phrase must be exactly: I understand the risks",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    fields = _intersect_fields(client, "ir.cron", _CRON_PREFERRED)
    try:
        from app.snapshots import save_snapshot

        try:
            before = client.execute_kw(
                "ir.cron", "read", [[cron_id]], {"fields": ["name", "active"]}
            )
            if before:
                save_snapshot(
                    db,
                    connection_id=connection_id,
                    resource_type="ir_cron",
                    resource_key=f"ir_cron:{cron_id}",
                    label=f"Cron {before[0].get('name')}",
                    payload={"ir_cron": before[0]},
                    reversible="yes",
                )
        except Exception:  # noqa: BLE001 — snapshot best-effort before mutate
            pass
        client.execute_kw("ir.cron", "write", [[cron_id], {"active": body.active}])
        rows = client.execute_kw("ir.cron", "read", [[cron_id]], {"fields": fields})
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Cron not found")
    return _cron_out(rows[0])


# --- M3: Website pages / menus ---


class WebsiteAvailabilityOut(BaseModel):
    available: bool
    reason: str | None = None
    pages: list[dict[str, Any]] | None = None
    menus: list[dict[str, Any]] | None = None


def _website_unavailable() -> WebsiteAvailabilityOut:
    return WebsiteAvailabilityOut(
        available=False,
        reason="website module not installed",
        pages=None,
        menus=None,
    )


@router.get("/website/pages", response_model=WebsiteAvailabilityOut)
def list_website_pages(
    connection_id: str, db: Session = Depends(get_db)
) -> WebsiteAvailabilityOut:
    client = _client(connection_id, db)
    if not _module_installed(client, "website"):
        return _website_unavailable()
    preferred = ["name", "url", "website_id", "is_published", "view_id", "website_indexed"]
    fields = _intersect_fields(client, "website.page", preferred)
    try:
        rows = client.execute_kw(
            "website.page",
            "search_read",
            [[]],
            {"fields": fields, "limit": 200, "order": "url"},
        )
    except OdooClientError as exc:
        # Module listed installed but model missing / ACL — honest unavailable, not 500.
        return WebsiteAvailabilityOut(
            available=False,
            reason=f"website module not installed ({exc})",
            pages=None,
            menus=None,
        )
    pages = [
        {
            "id": int(r["id"]),
            "name": r.get("name") or None,
            "url": r.get("url") or None,
            "website_id": _m2o_id(r.get("website_id")),
            "is_published": bool(r.get("is_published")) if "is_published" in r else None,
            "view_id": _m2o_id(r.get("view_id")),
        }
        for r in rows
    ]
    return WebsiteAvailabilityOut(available=True, reason=None, pages=pages, menus=None)


@router.get("/website/menus", response_model=WebsiteAvailabilityOut)
def list_website_menus(
    connection_id: str, db: Session = Depends(get_db)
) -> WebsiteAvailabilityOut:
    client = _client(connection_id, db)
    if not _module_installed(client, "website"):
        return _website_unavailable()
    preferred = [
        "name",
        "url",
        "website_id",
        "parent_id",
        "sequence",
        "is_visible",
        "page_id",
    ]
    fields = _intersect_fields(client, "website.menu", preferred)
    try:
        rows = client.execute_kw(
            "website.menu",
            "search_read",
            [[]],
            {"fields": fields, "limit": 300, "order": "sequence, id"},
        )
    except OdooClientError as exc:
        return WebsiteAvailabilityOut(
            available=False,
            reason=f"website module not installed ({exc})",
            pages=None,
            menus=None,
        )
    menus = [
        {
            "id": int(r["id"]),
            "name": r.get("name") or None,
            "url": r.get("url") or None,
            "website_id": _m2o_id(r.get("website_id")),
            "parent_id": _m2o_id(r.get("parent_id")),
            "sequence": int(r.get("sequence") or 0),
            "is_visible": bool(r.get("is_visible")) if "is_visible" in r else None,
            "page_id": _m2o_id(r.get("page_id")),
        }
        for r in rows
    ]
    return WebsiteAvailabilityOut(available=True, reason=None, pages=None, menus=menus)


# --- M4: ir.config_parameter (snapshot-backed mutate) ---


class ConfigParameterOut(BaseModel):
    id: int
    key: str
    value: str | None = None


class UpsertConfigParameterBody(BaseModel):
    key: str = Field(..., min_length=1)
    value: str = ""


@router.get("/parameters", response_model=list[ConfigParameterOut])
def list_config_parameters(
    connection_id: str,
    key: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[ConfigParameterOut]:
    client = _client(connection_id, db)
    domain: list[Any] = []
    if key:
        domain.append(("key", "=", key))
    try:
        rows = client.execute_kw(
            "ir.config_parameter",
            "search_read",
            [domain],
            {"fields": ["key", "value"], "limit": 200, "order": "key"},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        ConfigParameterOut(id=int(r["id"]), key=str(r.get("key") or ""), value=r.get("value"))
        for r in rows
    ]


@router.post("/parameters", response_model=ConfigParameterOut)
def upsert_config_parameter(
    connection_id: str, body: UpsertConfigParameterBody, db: Session = Depends(get_db)
) -> ConfigParameterOut:
    client = _client(connection_id, db)
    from app.snapshots import snapshot_config_parameter
    import json as _json

    try:
        existing = client.execute_kw(
            "ir.config_parameter",
            "search",
            [[("key", "=", body.key)]],
            {"limit": 1},
        )
        if existing:
            rid = int(existing[0])
            try:
                snapshot_config_parameter(db, connection_id, client, rid)
            except Exception:  # noqa: BLE001 — snapshot best-effort before mutate
                pass
            client.execute_kw(
                "ir.config_parameter", "write", [[rid], {"value": body.value}]
            )
        else:
            rid = int(
                client.execute_kw(
                    "ir.config_parameter",
                    "create",
                    [{"key": body.key, "value": body.value}],
                )
            )
            try:
                snap = snapshot_config_parameter(db, connection_id, client, rid)
                payload = _json.loads(snap.payload_json)
                payload["created"] = True
                snap.payload_json = _json.dumps(payload)
                db.add(snap)
                db.commit()
            except Exception:  # noqa: BLE001
                pass
        rows = client.execute_kw(
            "ir.config_parameter", "read", [[rid]], {"fields": ["key", "value"]}
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Config parameter not found after upsert")
    r = rows[0]
    return ConfigParameterOut(id=int(r["id"]), key=str(r.get("key") or ""), value=r.get("value"))


# --- M3-P1: Currency / UoM / fiscal (module-gated honesty) ---


class MasterDataAvailabilityOut(BaseModel):
    available: bool
    reason: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/currencies", response_model=MasterDataAvailabilityOut)
def list_currencies(
    connection_id: str, db: Session = Depends(get_db)
) -> MasterDataAvailabilityOut:
    client = _client(connection_id, db)
    fields = _intersect_fields(
        client, "res.currency", ["name", "symbol", "active", "rate"]
    )
    try:
        rows = client.execute_kw(
            "res.currency",
            "search_read",
            [[("active", "=", True)]],
            {"fields": fields, "limit": 200, "order": "name"},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MasterDataAvailabilityOut(
        available=True,
        rows=[
            {
                "id": int(r["id"]),
                "name": r.get("name"),
                "symbol": r.get("symbol"),
                "rate": r.get("rate"),
            }
            for r in rows
        ],
    )


@router.get("/currency-rates", response_model=MasterDataAvailabilityOut)
def list_currency_rates(
    connection_id: str,
    currency_id: int | None = Query(None),
    db: Session = Depends(get_db),
) -> MasterDataAvailabilityOut:
    """List res.currency.rate when present; empty available list is still OK."""
    client = _client(connection_id, db)
    if not client.model_exists("res.currency.rate"):
        return MasterDataAvailabilityOut(
            available=False,
            reason="res.currency.rate not available on this database",
        )
    fields = _intersect_fields(
        client, "res.currency.rate", ["name", "rate", "currency_id", "company_id"]
    )
    domain: list[Any] = []
    if currency_id is not None:
        domain.append(("currency_id", "=", currency_id))
    try:
        rows = client.execute_kw(
            "res.currency.rate",
            "search_read",
            [domain],
            {"fields": fields, "limit": 200, "order": "name desc"},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MasterDataAvailabilityOut(
        available=True,
        rows=[
            {
                "id": int(r["id"]),
                "name": r.get("name"),
                "rate": r.get("rate"),
                "currency_id": _m2o_id(r.get("currency_id")),
            }
            for r in rows
        ],
    )


@router.get("/uom", response_model=MasterDataAvailabilityOut)
def list_uom(connection_id: str, db: Session = Depends(get_db)) -> MasterDataAvailabilityOut:
    client = _client(connection_id, db)
    if not _module_installed(client, "uom") and not client.model_exists("uom.uom"):
        return MasterDataAvailabilityOut(
            available=False,
            reason="uom module / uom.uom not installed",
        )
    fields = _intersect_fields(client, "uom.uom", ["name", "category_id", "factor", "uom_type"])
    try:
        rows = client.execute_kw(
            "uom.uom",
            "search_read",
            [[]],
            {"fields": fields, "limit": 200, "order": "name"},
        )
    except OdooClientError as exc:
        return MasterDataAvailabilityOut(
            available=False,
            reason=f"uom.uom not readable ({exc})",
        )
    return MasterDataAvailabilityOut(
        available=True,
        rows=[
            {
                "id": int(r["id"]),
                "name": r.get("name"),
                "category_id": _m2o_id(r.get("category_id")),
                "factor": r.get("factor"),
            }
            for r in rows
        ],
    )


@router.get("/fiscal-positions", response_model=MasterDataAvailabilityOut)
def list_fiscal_positions(
    connection_id: str, db: Session = Depends(get_db)
) -> MasterDataAvailabilityOut:
    client = _client(connection_id, db)
    if not _module_installed(client, "account") and not client.model_exists(
        "account.fiscal.position"
    ):
        return MasterDataAvailabilityOut(
            available=False,
            reason="account module / account.fiscal.position not installed",
        )
    fields = _intersect_fields(
        client, "account.fiscal.position", ["name", "company_id", "auto_apply", "country_id"]
    )
    try:
        rows = client.execute_kw(
            "account.fiscal.position",
            "search_read",
            [[]],
            {"fields": fields, "limit": 200, "order": "name"},
        )
    except OdooClientError as exc:
        return MasterDataAvailabilityOut(
            available=False,
            reason=f"account.fiscal.position not readable ({exc})",
        )
    return MasterDataAvailabilityOut(
        available=True,
        rows=[
            {
                "id": int(r["id"]),
                "name": r.get("name"),
                "company_id": _m2o_id(r.get("company_id")),
                "auto_apply": bool(r.get("auto_apply")) if "auto_apply" in r else None,
            }
            for r in rows
        ],
    )
