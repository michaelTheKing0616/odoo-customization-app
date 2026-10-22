"""Configuration Suite stage 2 (addition): record editor API. Reads are live; edits become a checked plan."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import suite_records as sr
from app.db import get_db
from app.routers import suite as rs
from app.routers.view_engine import _client

router = APIRouter(prefix="/connections/{connection_id}/suite/records", tags=["suite"])


def _meta(client: Any, model: str) -> dict[str, Any]:
    try:
        return client.execute_kw(model, "fields_get", [], {"attributes": ["string", "type", "relation", "readonly", "required", "store", "selection", "sortable", "groupable"]})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="This record type is not on this database, or this login can't read it.") from exc


def _can(client: Any, model: str, op: str) -> bool:
    try:
        return bool(client.execute_kw(model, "has_access", [[], op], {}))
    except Exception:  # noqa: BLE001  17: no has_access
        try:
            return bool(client.execute_kw(model, "check_access_rights", [op], {"raise_exception": False}))
        except Exception:  # noqa: BLE001
            return False


@router.get("/models")
def records_models(connection_id: str, q: str = "", db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    dom: list[Any] = [("transient", "=", False)]
    if q.strip():
        dom += ["|", ("name", "ilike", q.strip()), ("model", "ilike", q.strip())]
    rows = client.execute_kw("ir.model", "search_read", [dom], {"fields": ["model", "name"], "order": "name", "limit": 60})
    return {"models": [{"model": r["model"], "label": r["name"], "view_only": sr.view_only_reason(r["model"])} for r in rows]}


@router.get("/{model}/meta")
def records_meta(connection_id: str, model: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Fields with what code allows here, the list view's columns, and whether this login may read or write."""
    client = _client(connection_id, db)
    fmeta = _meta(client, model)
    if not _can(client, model, "read"):
        raise HTTPException(status_code=403, detail="This login can't read these records.")
    cols: list[str] = []
    try:
        major = int(client.capabilities.major)
        vt = "list" if major >= 18 else "tree"
        arch = client.execute_kw(model, "get_views", [[[False, vt]]], {}).get("views", {}).get(vt, {}).get("arch", "")
        import re

        cols = [f for f in re.findall(r'<field[^>]*\bname="([^"]+)"', arch) if f in fmeta and fmeta[f].get("type") not in sr.NOT_EDITABLE_TYPES][:10]
    except Exception:  # noqa: BLE001  no list view
        cols = []
    if not cols:
        cols = [f for f in ("display_name", "name", "email", "phone", "state") if f in fmeta][:5] or ["display_name"]
    can_write = _can(client, model, "write")
    locked = sr.view_only_reason(model) or (None if can_write else "This login can't change these records.")
    rules = sr.field_rules(fmeta, model)
    if locked:
        for f in rules:
            f.update(editable=False, why_not=f["why_not"] or locked)
    label = (client.execute_kw("ir.model", "search_read", [[("model", "=", model)]], {"fields": ["name"], "limit": 1}) or [{"name": model}])[0]["name"]
    return {"model": model, "label": label, "fields": rules, "columns": cols, "view_only": locked, "has_active": "active" in fmeta}


class SearchBody(BaseModel):
    search: str = Field(default="", max_length=200)
    filters: list[Any] = Field(default_factory=list, max_length=20)
    fields: list[str] = Field(default_factory=list, max_length=40)
    group_by: str | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=80, ge=1, le=sr.MAX_PAGE)
    order: str | None = Field(default=None, max_length=80)
    archived: bool = False


@router.post("/{model}/search")
def records_search(connection_id: str, model: str, body: SearchBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """One page of records (server-side paging), the total, and group counts when grouped. Reads only."""
    client = _client(connection_id, db)
    fmeta = _meta(client, model)
    dom: list[Any] = sr.clean_filters(body.filters, fmeta)
    if body.search.strip():
        dom.append(("display_name", "ilike", body.search.strip()))
    fields = [f for f in body.fields if f in fmeta and fmeta[f].get("type") not in {"binary"}] or ["display_name"]
    ctx = {"active_test": not body.archived}
    order = None
    if body.order:
        f, _, d = body.order.partition(" ")
        if f in fmeta and fmeta[f].get("store", True) and d.lower() in {"", "asc", "desc"}:
            order = f"{f} {d or 'asc'}"
    total = client.execute_kw(model, "search_count", [dom], {"context": ctx})
    rows = client.execute_kw(model, "search_read", [dom], {"fields": sorted(set(fields + ["display_name"])), "offset": body.offset, "limit": body.limit,
                                                           "order": order or "id", "context": ctx})
    groups = None
    if body.group_by and body.group_by in fmeta:
        try:
            g = client.execute_kw(model, "read_group", [dom, [body.group_by], [body.group_by]], {"lazy": True, "context": ctx, "limit": 200})
            groups = []
            for x in g:
                v = x.get(body.group_by)
                groups.append({"value": v[0] if isinstance(v, list | tuple) and v else v, "label": (v[1] if isinstance(v, list | tuple) and len(v) > 1 else str(v) if v not in (False, None) else "None"),
                               "count": x.get(f"{body.group_by}_count", x.get("__count", 0))})
        except Exception as exc:  # noqa: BLE001
            groups = [{"value": None, "label": f"Can't group by this here: {rs.ss.fault_line(exc)}", "count": 0}]
    return {"total": total, "offset": body.offset, "limit": body.limit, "rows": rows, "groups": groups}


class ReplaceBody(BaseModel):
    field: str
    find: str = Field(min_length=1, max_length=200)
    replace: str = Field(default="", max_length=200)
    ids: list[int] = Field(default_factory=list, max_length=sr.MAX_EDITS)
    filters: list[Any] = Field(default_factory=list)
    search: str = ""
    whole: bool = False
    case: bool = False


@router.post("/{model}/replace/preview")
def records_replace_preview(connection_id: str, model: str, body: ReplaceBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Find and replace in one text field: shows old and new for each record. Writes nothing."""
    client = _client(connection_id, db)
    fmeta = _meta(client, model)
    m = fmeta.get(body.field)
    if not m or m.get("type") not in {"char", "text", "html"}:
        raise HTTPException(status_code=422, detail="Find and replace works on text fields.")
    _, problem = sr.validate_edit(fmeta, model, body.field, "x")
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    dom: list[Any] = [("id", "in", body.ids)] if body.ids else sr.clean_filters(body.filters, fmeta)
    if body.search.strip() and not body.ids:
        dom.append(("display_name", "ilike", body.search.strip()))
    dom.append((body.field, "ilike", body.find))
    rows = client.execute_kw(model, "search_read", [dom], {"fields": [body.field, "display_name"], "limit": sr.MAX_EDITS})
    edits = sr.replace_edits(rows, body.field, body.find, body.replace, whole=body.whole, case=body.case, html=m.get("type") == "html")
    names = {r["id"]: r["display_name"] for r in rows}
    if m.get("required"):
        bad = [e for e in edits if not e["value"].strip()]
        if bad:
            raise HTTPException(status_code=422, detail=f"Odoo needs a value for '{m.get('string')}'; {len(bad)} record(s) would be left empty.")
    return {"edits": [{**e, "name": names.get(e["id"])} for e in edits], "count": len(edits)}


class Edit(BaseModel):
    id: int
    field: str
    value: Any = None


class StageBody(BaseModel):
    edits: list[Edit] = Field(min_length=1, max_length=sr.MAX_EDITS)
    name: str = Field(default="", max_length=120)


@router.post("/{model}/plan")
def records_plan(connection_id: str, model: str, body: StageBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Turn staged edits into one setup plan of update steps. Refusals come back per edit; nothing is written here."""
    client = _client(connection_id, db)
    fmeta = _meta(client, model)
    locked = sr.view_only_reason(model)
    if locked:
        raise HTTPException(status_code=403, detail={"error": "view_only", "message": locked, "route": "Move records forward > Journal entries" if model == "account.move" else "Odoo Accounting"})
    if not _can(client, model, "write"):
        raise HTTPException(status_code=403, detail="This login can't change these records.")
    ok, refused = [], []
    for e in body.edits:
        v, problem = sr.validate_edit(fmeta, model, e.field, e.value)
        (refused if problem else ok).append({"id": e.id, "field": e.field, "value": v, **({"problem": problem} if problem else {})})
    if refused and not ok:
        raise HTTPException(status_code=422, detail={"error": "refused", "message": refused[0]["problem"], "refused": refused[:50]})
    ids = sorted({e["id"] for e in ok})
    names = {r["id"]: r["display_name"] for r in client.execute_kw(model, "read", [ids, ["display_name"]], {"context": {"active_test": False}})}
    missing = [i for i in ids if i not in names]
    if missing:
        raise HTTPException(status_code=409, detail=f"These records are gone: {', '.join(map(str, missing[:10]))}.")
    labels = {f: (m.get("string") or f) for f, m in fmeta.items()}
    steps = sr.plan_steps(ok, model, names, labels)
    plan = rs.suite_plan_create(connection_id, rs.PlanBody(name=body.name or f"Edit {len(steps)} records", steps=steps), request, db)
    return {"plan": plan, "steps": len(steps), "refused": refused}
