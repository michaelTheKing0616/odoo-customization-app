"""Builders stage 2c endpoints (SPEC section 18, approved Oct 15 2026).

Views: field dependency map, conditional-required impact, what blocks saving,
usage heatmap, labelled sample data, accessibility check, industry starter
screens, explain this screen, step-by-step mode per role, role compare,
dashboard designer, approval before publish, scheduled publish, post-publish
watch with one-click undo, weekly digest, layout comparison test, live co-editing.
Reports: per-company brands, report from a photo or PDF. Emails: email app checks.

Everything that writes goes through the same checked paths as 2a/2b (written
inactive, turned on so Odoo validates it, compared, rolled back on any difference).
"""

from __future__ import annotations

import base64
import contextlib
import contextvars
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import view_engine as ve
from app import view_engine_2c as v2
from app import view_engine_access as va
from app import view_engine_library as lib
from app import view_engine_logic as vl
from app import view_engine_portable as vp
from app import view_engine_store as vs
from app.db import get_db
from app.db_models import ViewBuilderItem, ViewLayerVersion
from app.routers.view_engine import (
    ODOO_ERRORS,
    OpsBody,
    RevertBody,
    _annotate,
    _check_model,
    _client,
    _combined_raw,
    _compile_kwargs,
    _connection_member_of,
    _engine_error,
    _fields_get,
    _find_layer,
    _get_views,
    _layer_hash,
    _major,
    _odoo_error,
    _record_names,
    _stock_hashes,
    _vt,
    engine_publish,
    engine_revert,
)
from app.routers.view_engine_logic import _ids_in_condition
from app.routers.view_engine_studio import ScreenRef, _counts, _rich_fields, _screen

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections/{connection_id}/views/engine", tags=["view-engine"])
reports_router = APIRouter(prefix="/connections/{connection_id}/reports/engine", tags=["view-engine"])
emails_router = APIRouter(prefix="/connections/{connection_id}/emails/engine", tags=["view-engine"])

# Set while an approved (or approved-then-scheduled) change is being published.
APPROVED_PUBLISH: contextvars.ContextVar[bool] = contextvars.ContextVar("ingenium_approved_publish", default=False)


def _who(request: Request | None) -> dict[str, Any]:
    auth = getattr(getattr(request, "state", None), "auth", None) if request is not None else None
    mode = str(getattr(auth, "mode", "off") or "off")
    return {"mode": mode, "user_id": getattr(auth, "user_id", None), "email": getattr(auth, "email", None),
            "verified": mode == "accounts" and bool(getattr(auth, "user_id", None))}


def _safe(fn: Any, default: Any) -> Any:
    try:
        return fn()
    except (*ODOO_ERRORS, HTTPException):
        return default


def _model_label(client: Any, model: str) -> str:
    rows = _safe(lambda: client.execute_kw("ir.model", "search_read", [[("model", "=", model)]], {"fields": ["name"], "limit": 1}), [])
    return str(rows[0]["name"]) if rows else model


def _has_model(client: Any, model: str) -> bool:
    return bool(_safe(lambda: client.execute_kw("ir.model", "search_count", [[("model", "=", model)]]), 0))


def _model_fields(client: Any, model: str, wanted: list[str]) -> list[str]:
    if not wanted:
        return []
    have = _safe(lambda: client.execute_kw(model, "fields_get", [wanted], {"attributes": ["type"]}), {}) or {}
    return [w for w in wanted if w in have]


def _group_counts(client: Any, model: str, domain: list[Any], groupby: str, aggregates: list[str] | None = None,
                  limit: int = 80) -> list[dict[str, Any]]:
    """Grouped counts (and sums) on every Odoo major: formatted_read_group (19+), read_group before."""
    aggregates = aggregates or []
    try:
        rows = client.execute_kw(model, "formatted_read_group", [domain], {
            "groupby": [groupby], "aggregates": ["__count", *[f"{a}:sum" for a in aggregates]], "limit": limit})
        return [{"key": r.get(groupby), "count": int(r.get("__count") or 0), **{a: r.get(f"{a}:sum") for a in aggregates}} for r in rows or []]
    except ODOO_ERRORS:
        pass
    base = groupby.split(":")[0]
    rows = client.execute_kw(model, "read_group", [domain, [f"{a}:sum" for a in aggregates] or [base], [groupby]], {"lazy": True, "limit": limit})
    return [{"key": r.get(groupby) if groupby in r else r.get(base), "count": int(r.get(f"{base}_count") or r.get("__count") or 0),
             **{a: r.get(a) for a in aggregates}} for r in rows or []]


def _key_label(k: Any) -> str:
    if isinstance(k, (list, tuple)) and len(k) == 2:
        return str(k[1])
    if k is False or k is None:
        return "Not set"
    return str(k)


def _screen_key(model: str, vt: str, view_id: int | None) -> str:
    return f"{model}|{vt}|{int(view_id or 0)}"


def _detail_text(exc: HTTPException, default: str = "Publishing failed.") -> str:
    d = exc.detail
    return d if isinstance(d, str) else str((d or {}).get("message") or default)


class ItemRef(BaseModel):
    item_id: str


class ModelOnly(BaseModel):
    model: str


class ModelFilter(BaseModel):
    model: str | None = None


# ============================================================================
# 1. Field dependency map
# ============================================================================

class DepsBody(ScreenRef):
    field: str = Field(min_length=1, max_length=64)
    removing: bool = False


def field_dependencies(client: Any, model: str, field: str, tree: dict[str, Any], fields: dict[str, Any],
                       this_view_id: int) -> list[dict[str, Any]]:
    """Every place in this database that reads the field (structure only, no record contents)."""
    items: list[dict[str, Any]] = []
    meta = fields.get(field) or {}
    if meta.get("required") is True:
        items.append({"kind": "required", "name": "Odoo needs it to save a record", "detail": "Hiding it can make saving fail unless it has a default."})
    for u in v2.uses_in_screen(tree, field):
        items.append({"kind": "screen_rule", "name": u["label"], "detail": f"Its {u['how']} reads this field.", "node": u["node"]})
    views = _safe(lambda: client.execute_kw("ir.ui.view", "search_read", [[("model", "=", model), ("arch_db", "ilike", field), ("type", "!=", "qweb")]],
                                            {"fields": ["id", "name", "type", "arch_db"], "limit": 200}), [])
    for v in views or []:
        if int(v["id"]) == int(this_view_id) or str(v.get("name") or "").startswith(ve.LAYER_PREFIX):
            continue
        if v2.arch_mentions(str(v.get("arch_db") or ""), field):
            items.append({"kind": "view", "name": str(v.get("name") or ""), "detail": f"A {v.get('type')} screen shows or uses it.", "id": v["id"]})
    reports = _safe(lambda: client.execute_kw("ir.actions.report", "search_read", [[("model", "=", model)]], {"fields": ["name", "report_name"]}), [])
    if reports:
        names = {str(r["report_name"]): str(r["name"]) for r in reports}
        keys = list(names) + [k + "_document" for k in names]
        qweb = _safe(lambda: client.execute_kw("ir.ui.view", "search_read", [[("type", "=", "qweb"), ("key", "in", keys)]],
                                               {"fields": ["key", "arch_db"]}), [])
        seen: set[str] = set()
        for q in qweb or []:
            base = str(q["key"]).removesuffix("_document")
            if base not in seen and v2.arch_mentions(str(q.get("arch_db") or ""), field):
                seen.add(base)
                items.append({"kind": "report", "name": names.get(base, str(q["key"])), "detail": "This printed document prints it."})
    tpls = _safe(lambda: client.execute_kw("mail.template", "search_read", [[("model", "=", model), "|", ("body_html", "ilike", field), ("subject", "ilike", field)]],
                                           {"fields": ["name", "body_html", "subject"], "limit": 100}), [])
    for t in tpls or []:
        if v2.arch_mentions(f"{t.get('subject') or ''} {t.get('body_html') or ''}", field):
            items.append({"kind": "email", "name": str(t["name"]), "detail": "This email template includes it."})
    fid_rows = _safe(lambda: client.execute_kw("ir.model.fields", "search", [[("model", "=", model), ("name", "=", field)]], {"limit": 1}), [])
    fid = int(fid_rows[0]) if fid_rows else -1
    if _has_model(client, "base.automation"):
        flds = _model_fields(client, "base.automation", ["name", "filter_domain", "filter_pre_domain", "trigger_field_ids", "on_change_field_ids"])
        autos = _safe(lambda: client.execute_kw("base.automation", "search_read", [[("model_name", "=", model)]], {"fields": flds}), [])
        for a in autos or []:
            hit = v2.domain_mentions(a.get("filter_domain"), field) or v2.domain_mentions(a.get("filter_pre_domain"), field)
            if hit or fid in (a.get("trigger_field_ids") or []) or fid in (a.get("on_change_field_ids") or []):
                items.append({"kind": "automation", "name": str(a.get("name") or "Automation"), "detail": "An automation watches or checks it."})
    acts = _safe(lambda: client.execute_kw("ir.actions.server", "search_read", [[("model_name", "=", model), ("state", "=", "code"), ("code", "ilike", field)]],
                                           {"fields": ["name", "code"], "limit": 50}), [])
    for a in acts or []:
        if re.search(rf"\b(record|records)\.{re.escape(field)}\b|['\"]{re.escape(field)}['\"]", str(a.get("code") or "")):
            items.append({"kind": "server_action", "name": str(a["name"]), "detail": "A server action's code uses it."})
    rules = _safe(lambda: client.execute_kw("ir.rule", "search_read", [[("model_id.model", "=", model), ("domain_force", "ilike", field)]],
                                            {"fields": ["name", "domain_force"]}), [])
    for r in rules or []:
        if v2.domain_mentions(r.get("domain_force"), field):
            items.append({"kind": "record_rule", "name": str(r.get("name") or "Record rule"), "detail": "Decides who can see which records."})
    filters = _safe(lambda: client.execute_kw("ir.filters", "search_read", [[("model_id", "=", model), "|", ("domain", "ilike", field), ("context", "ilike", field)]],
                                              {"fields": ["name", "domain", "context"], "limit": 50}), [])
    for f in filters or []:
        if v2.domain_mentions(f.get("domain"), field) or re.search(rf"['\"]{re.escape(field)}['\"]", str(f.get("context") or "")):
            items.append({"kind": "filter", "name": str(f["name"]), "detail": "A saved filter or grouping uses it."})
    defaults = _safe(lambda: client.execute_kw("ir.default", "search_count", [[("field_id", "=", fid)]]), 0) if fid > 0 else 0
    if defaults:
        items.append({"kind": "default", "name": f"{defaults} default value{'s' if defaults != 1 else ''}", "detail": "New records get a value for it."})
    computed = _safe(lambda: client.execute_kw("ir.model.fields", "search_read", [[("model", "=", model), "|", ("depends", "ilike", field), ("related", "ilike", field)]],
                                               {"fields": ["name", "field_description", "depends", "related"]}), [])
    for c in computed or []:
        if c["name"] == field:
            continue
        deps = [d.strip().split(".")[0] for d in str(c.get("depends") or "").split(",")] + [str(c.get("related") or "").split(".")[0]]
        if field in deps:
            items.append({"kind": "computed", "name": str(c.get("field_description") or c["name"]), "detail": "Calculated from this field."})
    return items


@router.post("/2c/deps")
def deps(connection_id: str, body: DepsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, _tag = _screen(client, body)
    if body.field not in fields:
        raise HTTPException(status_code=404, detail="That field isn't on this record type.")
    items = field_dependencies(client, model, body.field, tree, fields, int(view["id"]))
    label = str(fields[body.field].get("string") or body.field)
    return {"field": body.field, "label": label, **v2.dependency_summary(items, label, body.removing)}


# ============================================================================
# 2. Conditional required: who is affected today
# ============================================================================

class RequiredImpactBody(BaseModel):
    model: str
    field: str
    condition: dict[str, Any] | None = None  # None = always required


@router.post("/2c/required-impact")
def required_impact(connection_id: str, body: RequiredImpactBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = _check_model(body.model)
    fields = _rich_fields(client, model)
    meta = fields.get(body.field)
    if not meta:
        raise HTTPException(status_code=404, detail="That field isn't on this record type.")
    if meta.get("store") is False:
        return {"countable": False, "text": "This field isn't saved in the database, so Ingenium can't count records for it."}
    label = str(meta.get("string") or body.field)
    if body.condition:
        try:
            names = _record_names(client, fields, _ids_in_condition(body.condition, fields))
            cond = vl.validate_condition(body.condition, fields, record_names=names)
        except ve.EngineError as exc:
            raise _engine_error(exc) from exc
        dom = v2.condition_domain(cond)
        sentence = vl.condition_sentence(cond, fields, names)
    else:
        dom, sentence = [], "any record"
    empty = v2.empty_domain(body.field, meta)
    try:
        matching = int(client.execute_kw(model, "search_count", [dom]))
        missing = int(client.execute_kw(model, "search_count", [["&", *dom, *empty] if dom else empty]))
    except ODOO_ERRORS as exc:
        return {"countable": False, "text": f"Odoo couldn't count these records ({str(exc)[:120]})."}
    return {"countable": True, "matching": matching, "missing": missing, "sentence": sentence,
            "text": v2.required_impact_text(label, sentence, matching, missing)}


# ============================================================================
# 3. What blocks saving
# ============================================================================

@router.post("/2c/save-blockers")
def save_blockers(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, tag = _screen(client, body)
    if tag != "form":
        raise HTTPException(status_code=422, detail="Open a form screen to see what blocks saving.")
    sfield, skind = v2.stage_choices(fields)
    stages: list[dict[str, Any]] = []
    if skind == "many2one":
        rel = str(fields[sfield].get("relation"))
        have = _model_fields(client, rel, sorted(v2.stage_attr_names(tree, sfield)))
        rows = _safe(lambda: client.execute_kw(rel, "search_read", [[]], {"fields": ["display_name", *have], "limit": 25}), [])
        stages = [{"value": int(r["id"]), "label": str(r.get("display_name") or r["id"]), "attrs": {k: r.get(k) for k in have}} for r in rows or []]
    elif skind == "selection":
        stages = [{"value": k, "label": str(lbl)} for k, lbl in fields[sfield].get("selection") or []][:25]
    if not stages:
        stages = [{"value": None, "label": "Any record"}]
    rows = v2.save_blockers(tree, fields, sfield or "__none__", stages)
    budget = 40  # counts only, capped
    for row in rows:
        for item in row["at_stage"] + row["always"]:
            if budget <= 0 or not sfield or (fields.get(item["field"]) or {}).get("store") is False:
                continue
            budget -= 1
            dom = ["&", (sfield, "=", row["value"]), *v2.empty_domain(item["field"], fields.get(item["field"]) or {})]
            item["missing_now"] = _safe(lambda d=dom: int(client.execute_kw(model, "search_count", [d])), None)
    blocked = sum(1 for r in rows if r["always"] or r["at_stage"])
    return {"stage_field": sfield, "stage_label": str((fields.get(sfield or "") or {}).get("string") or ""), "stages": rows,
            "summary": (f"Checked {len(rows)} stage{'s' if len(rows) != 1 else ''}. {blocked} of them need fields filled in before saving."
                        if sfield else "This record type has no stages, so the same fields are needed every time.")}


# ============================================================================
# 4. Usage heatmap
# ============================================================================

class HeatBody(ScreenRef):
    days: int = 90


@router.post("/2c/heatmap")
def heatmap(connection_id: str, body: HeatBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, _tag = _screen(client, body)
    counts, total = _counts(client, model, tree, fields)
    days = max(7, min(365, int(body.days)))
    since = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    changes: dict[str, int] = {}
    try:
        rows = _group_counts(client, "mail.tracking.value", [("mail_message_id.model", "=", model), ("create_date", ">=", since)], "field_id")
        ids = {int(r["key"][0]): int(r["count"]) for r in rows if isinstance(r.get("key"), (list, tuple)) and r["key"]}
        if ids:
            names = client.execute_kw("ir.model.fields", "read", [list(ids)], {"fields": ["name"]})
            changes = {str(n["name"]): ids[int(n["id"])] for n in names}
    except ODOO_ERRORS:
        changes = {}
    tracked = {k: v for k, v in changes.items() if k in counts}
    heat = v2.heat_levels(counts, total, tracked, days)
    return {"total": total, "days": days, "heat": {f"field:{n}": h for n, h in heat.items()}, "tracked_fields": len(tracked),
            "legend": ["Rarely used", "Sometimes", "Often", "Very often", "Almost always"],
            "note": "Counts only: how many records have each field filled, and how often tracked fields were changed. No record contents are read."}


# ============================================================================
# 5. Sample data (labelled, never saved)
# ============================================================================

class SampleBody(ScreenRef):
    count: int = 3


@router.post("/2c/sample")
def sample(connection_id: str, body: SampleBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, _tag = _screen(client, body)
    names = list(dict.fromkeys(n.get("name") for n, h in v2.screen_field_nodes(tree) if not h and n.get("name")))[:80]
    return {"records": v2.sample_records(names, fields, body.count), "label": "Sample", "note": v2.SAMPLE_NOTE}


# ============================================================================
# 6. Accessibility
# ============================================================================

A11Y_SIMULATIONS = [{"key": "protanopia", "label": "Red-blind"}, {"key": "deuteranopia", "label": "Green-blind"},
                    {"key": "tritanopia", "label": "Blue-blind"}, {"key": "achromatopsia", "label": "No colour"},
                    {"key": "low_vision", "label": "Blurred vision"}, {"key": "zoom200", "label": "Zoomed to 200%"}]


@router.post("/2c/a11y")
def a11y(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, tag = _screen(client, body)
    return {**v2.a11y_report(tree, fields, tag), "simulations": A11Y_SIMULATIONS}


# ============================================================================
# 7. Industry starter screens
# ============================================================================

class StarterCreateBody(BaseModel):
    model: str
    key: str
    label: str = Field(min_length=1, max_length=80)
    make_menu: bool = False
    parent_menu_id: int | None = None


@router.post("/2c/starters")
def starters(connection_id: str, body: ModelOnly, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = _check_model(body.model)
    fields = _fields_get(client, model)
    opts = v2.starter_options(model, fields)
    return {"starters": opts, "note": "Starters only use fields this database already has. Missing ones are listed, never made up."}


def _create_primary(client: Any, *, model: str, odoo_type: str, label: str, arch: str, make_menu: bool, parent_menu_id: int | None,
                    view_mode: str, check: Any) -> tuple[int, int | None, int | None]:
    """A new screen of its own (priority 1000, never the default) plus optional action and
    menu; removed again if Odoo doesn't show what was built."""
    created: list[tuple[str, int]] = []

    def undo() -> None:
        for m, rid in reversed(created):
            _safe(lambda m=m, rid=rid: client.execute_kw(m, "unlink", [[rid]]), None)

    try:
        view_id = int(client.execute_kw("ir.ui.view", "create", [{
            "name": vp.screen_view_name(model, odoo_type, label), "model": model, "type": odoo_type,
            "mode": "primary", "priority": vp.SCREEN_PRIORITY, "arch": arch}]))
        created.append(("ir.ui.view", view_id))
        action_id = menu_id = None
        if make_menu:
            action_id = int(client.execute_kw("ir.actions.act_window", "create", [{
                "name": label, "res_model": model, "view_mode": view_mode, "view_id": view_id}]))
            created.append(("ir.actions.act_window", action_id))
            vals: dict[str, Any] = {"name": label, "action": f"ir.actions.act_window,{action_id}", "sequence": 95}
            if parent_menu_id:
                vals["parent_id"] = int(parent_menu_id)
            menu_id = int(client.execute_kw("ir.ui.menu", "create", [vals]))
            created.append(("ir.ui.menu", menu_id))
        res = client.execute_kw(model, "get_views", [], {"views": [[view_id, odoo_type]], "options": {"toolbar": False}})
        shown = ((res or {}).get("views") or {}).get(odoo_type) or {}
        if int(shown.get("id") or 0) != view_id:
            raise HTTPException(status_code=409, detail="Odoo didn't open the new screen, so it was removed.")
        problem = check(str(shown.get("arch") or ""))
        if problem:
            raise HTTPException(status_code=409, detail=problem)
    except HTTPException:
        undo()
        raise
    except ODOO_ERRORS as exc:
        undo()
        raise _odoo_error(exc) from exc
    return view_id, action_id, menu_id


@router.post("/2c/starters/create")
def starter_create(connection_id: str, body: StarterCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = _check_model(body.model)
    fields = _fields_get(client, model)
    label = body.label.strip()
    try:
        arch, used, missing = v2.starter_arch(body.key, model, fields, _major(client), label)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc

    def check(shown: str) -> str | None:
        lost = [u for u in used if f'name="{u}"' not in shown]
        return f"Odoo doesn't show {len(lost)} of the fields, so the screen was removed." if lost else None

    view_id, action_id, menu_id = _create_primary(client, model=model, odoo_type="form", label=label, arch=arch, make_menu=body.make_menu,
                                                  parent_menu_id=body.parent_menu_id, view_mode="form", check=check)
    row = vs.save_item(db, connection_id=connection_id, kind="screen", key=model, name=label,
                       payload={"view_id": view_id, "action_id": action_id, "menu_id": menu_id, "view_type": "form", "template": f"starter:{body.key}"})
    return {"ok": True, "item_id": row.id, "view_id": view_id, "action_id": action_id, "menu_id": menu_id,
            "fields_used": len(used), "missing": missing}


# ============================================================================
# 8. Explain this screen
# ============================================================================

@router.post("/2c/explain")
def explain(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, _tag = _screen(client, body)
    _annotate(client, tree, fields, _combined_raw(client, int(view["id"])))
    cat = va.group_catalog(client)
    return {"steps": v2.explain_steps(tree, fields, _model_label(client, model), cat.names()),
            "written_by": "Written by Ingenium from the screen itself, no AI."}


# ============================================================================
# 9. Step-by-step mode for a role, role compare, and 17. layout comparison tests
# ============================================================================

def _scoped_rollback(client: Any, lid: int | None, created: bool, previous: str | None) -> None:
    if lid is None:
        return
    if created:
        _safe(lambda: client.execute_kw("ir.ui.view", "unlink", [[lid]]), None)
    elif previous:
        _safe(lambda: client.execute_kw("ir.ui.view", "write", [[lid], {"arch": previous, "active": True}]), None)
    else:
        _safe(lambda: client.execute_kw("ir.ui.view", "write", [[lid], {"active": False}]), None)


def _scoped_publish(client: Any, db: Session, connection_id: str, *, model: str, vt: str, view: dict[str, Any], view_id: int | None,
                    name: str, arch: str, role: str, cat: va.GroupCatalog, summary: str, expect: list[str]) -> dict[str, Any]:
    """Role-only layer: written inactive, turned on (Odoo validates the whole screen),
    then compared with what Odoo shows when the Ingenium login is in that role."""
    require_approval_ok(db, connection_id)  # stage 2e: role layouts follow the approval rule too
    if cat.id_of.get(role) is None:
        raise HTTPException(status_code=404, detail="That role isn't in this database.")
    existing = _find_layer(client, name)
    previous = str(existing.get("arch") or "") if existing and existing.get("active") else None
    stock_before = _stock_hashes(client, model)
    created = False
    lid = int(existing["id"]) if existing else None
    try:
        if lid is not None and previous is not None:
            client.execute_kw("ir.ui.view", "write", [[lid], {"active": False}])  # compare against the screen without it
        raw = _combined_raw(client, int(view["id"]))
        if not raw:
            raise HTTPException(status_code=422, detail="Odoo didn't return this screen's full layout.")
        try:
            change_arch = arch
            arch = v2.role_variant_arch(raw, ve.apply_inherit_local(raw, change_arch), role)
        except ve.EngineError as exc:
            raise _engine_error(exc) from exc
        if lid is None:
            lid = int(client.execute_kw("ir.ui.view", "create", [{
                "name": name, "model": model, "type": vt if vt != "list" or _major(client) >= 18 else "tree",
                "inherit_id": int(view["id"]), "mode": "extension", "priority": ROLE_PRIORITY, "arch": arch, "active": False}]))
            created = True
        else:
            client.execute_kw("ir.ui.view", "write", [[lid], {"arch": arch, "active": False, "priority": ROLE_PRIORITY}])
        client.execute_kw("ir.ui.view", "write", [[lid], {"active": True}])
    except HTTPException:
        _scoped_rollback(client, lid, created, previous)
        raise
    except ODOO_ERRORS as exc:
        _scoped_rollback(client, lid, created, previous)
        raise _odoo_error(exc) from exc
    checked = "odoo"
    if role in _connection_member_of(client, cat):
        after = _get_views(client, model, vt, view_id)
        missing = [m for m in expect if m not in after["arch"]]
        if missing:
            _scoped_rollback(client, lid, created, previous)
            raise HTTPException(status_code=409, detail={"message": "Odoo shows this differently, so nothing was published.",
                                                         "differences": [f"Missing: {m}" for m in missing[:10]]})
        checked = "compared"
    if _stock_hashes(client, model) != stock_before:
        _scoped_rollback(client, lid, created, previous)
        raise HTTPException(status_code=409, detail="Odoo's own screens changed during publishing, so nothing was published.")
    vid = vs.record_version(db, connection_id=connection_id, kind="view", model=model, view_type=vt, layer_name=name,
                            layer_view_id=lid, action="publish", summary=[summary], layer_arch=arch, layer_active=True,
                            combined_arch=None, odoo_major=_major(client))
    vs.save_item(db, connection_id=connection_id, kind="role_layer", key=name, name=summary[:120],
                 payload={"change_arch": change_arch, "role": role, "model": model, "base_id": int(view["id"])}, replace_key=True)
    return {"ok": True, "layer_view_id": lid, "version_id": vid, "checked": checked,
            "check_note": ("Compared with what Odoo shows." if checked == "compared" else
                           "Odoo accepted the screen. Ingenium's login isn't in that role, so the role's view was checked by Odoo only.")}


ROLE_PRIORITY = v2.SCOPED_PRIORITY + 3  # role copies apply after every other Ingenium layer


def _active_role_layers(client: Any, model: str, base_id: int) -> list[dict[str, Any]]:
    return _safe(lambda: client.execute_kw("ir.ui.view", "search_read", [[("model", "=", model), ("inherit_id", "=", int(base_id)), ("active", "=", True),
                                                                          "|", ("name", "=like", v2.STEPS_PREFIX + "%"), ("name", "=like", v2.TEST_PREFIX + "%")]],
                                           {"fields": ["id", "name", "arch_db"]}), []) or []


def _role_kind(name: str) -> str:
    return "The layout test" if name.startswith(v2.TEST_PREFIX) else "Step-by-step mode"


def _resume_role_layer(client: Any, db: Session, connection_id: str, row: dict[str, Any], base_id: int) -> str:
    """Rebuild a role layout on top of the screen as it is now, so the role also gets the new changes."""
    lid, old = int(row["id"]), str(row.get("arch_db") or "")
    kind = _role_kind(str(row["name"]))
    items = vs.list_items(db, connection_id, "role_layer", str(row["name"]))
    spec = vs.item_out(items[0])["payload"] if items else {}
    if spec.get("change_arch") and spec.get("role"):
        try:
            raw = _combined_raw(client, int(base_id))
            arch = v2.role_variant_arch(raw, ve.apply_inherit_local(raw, spec["change_arch"]), spec["role"])
            client.execute_kw("ir.ui.view", "write", [[lid], {"arch": arch, "priority": ROLE_PRIORITY}])
            client.execute_kw("ir.ui.view", "write", [[lid], {"active": True}])
            return f"{kind} for one role was rebuilt on top of your changes and is on again."
        except (ve.EngineError, HTTPException, *ODOO_ERRORS):
            pass
    try:
        client.execute_kw("ir.ui.view", "write", [[lid], {"arch": old}])
        client.execute_kw("ir.ui.view", "write", [[lid], {"active": True}])
        return f"{kind} is on again as it was, so that role won't see your new changes until it's switched on again (Roles tab)."
    except ODOO_ERRORS:
        return f"{kind} couldn't be put back on top of your changes, so it's off now. Switch it on again from the Roles tab."


@contextlib.contextmanager
def role_layers_paused(client: Any, db: Session, connection_id: str, model: str, base_id: int):
    """Role layouts hold copies of parts of the screen. Turn them off while another
    change publishes, then rebuild them on top of it. On failure, put them back exactly."""
    rows = _active_role_layers(client, model, base_id)
    notes: list[str] = []
    if rows:
        client.execute_kw("ir.ui.view", "write", [[int(r["id"]) for r in rows], {"active": False}])
    try:
        yield notes
    except BaseException:
        if rows:
            _safe(lambda: client.execute_kw("ir.ui.view", "write", [[int(r["id"]) for r in rows], {"active": True}]), None)
        raise
    for r in rows:
        notes.append(_resume_role_layer(client, db, connection_id, r, base_id))


def role_layout_block(client: Any, model: str, base_id: int) -> None:
    """A role-only layout (step-by-step mode or a layout test) holds its own copy
    of parts of this screen, so other changes wouldn't reach that role. Refuse
    plainly instead of publishing something some people won't see."""
    rows = _safe(lambda: client.execute_kw("ir.ui.view", "search_read", [[("model", "=", model), ("inherit_id", "=", int(base_id)), ("active", "=", True),
                                                                          "|", ("name", "=like", v2.STEPS_PREFIX + "%"), ("name", "=like", v2.TEST_PREFIX + "%")]],
                                           {"fields": ["name"]}), [])
    if rows:
        kind = "a layout test" if str(rows[0]["name"]).startswith(v2.TEST_PREFIX) else "step-by-step mode"
        raise HTTPException(status_code=409, detail={
            "message": f"This screen has {kind} switched on for one role. Stop it first (Roles tab), publish your changes, then switch it on again.",
            "role_layout": True})


def _scoped_layers(client: Any, prefix: str, model: str, base_id: int) -> list[dict[str, Any]]:
    rows = _safe(lambda: client.execute_kw("ir.ui.view", "search_read", [[("name", "=like", prefix + "%"), ("model", "=", model),
                                                                          ("inherit_id", "=", int(base_id))]],
                                           {"fields": ["id", "name", "active", "arch_db"], "context": {"active_test": False}}), [])
    return [{**r, "_roles": sorted(set(re.findall(r'groups="([A-Za-z0-9_]+\.[A-Za-z0-9_]+)"', str(r.get("arch_db") or ""))))} for r in rows or []]


@router.post("/2c/steps/options")
def steps_options(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, tag = _screen(client, body)
    if tag != "form":
        raise HTTPException(status_code=422, detail="Step-by-step mode works on form screens.")
    cat = va.group_catalog(client)
    existing = [{"id": r["id"], "active": bool(r.get("active")), "roles": [cat.name(x) for x in r["_roles"]]}
                for r in _scoped_layers(client, v2.STEPS_PREFIX, model, int(view["id"]))]
    return {"sections": v2.step_candidates(tree), "existing": existing,
            "note": "Each step is a tab. Only people in the chosen role see the steps; everyone else keeps the normal screen."}


class StepsPublishBody(ScreenRef):
    role: str
    progress: bool = False  # show 'Step n done' badges worked out from the record's own fields
    sections: list[str] = Field(default_factory=list)  # node ids, in step order


@router.post("/2c/steps/publish")
def steps_publish(connection_id: str, body: StepsPublishBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, tag = _screen(client, ScreenRef(model=body.model, view_type=body.view_type, view_id=body.view_id))
    if tag != "form":
        raise HTTPException(status_code=422, detail="Step-by-step mode works on form screens.")
    cands = {c["node"]: c for c in v2.step_candidates(tree)}
    chosen = [cands[s] for s in body.sections if s in cands]
    if len(chosen) != len(body.sections):
        raise HTTPException(status_code=422, detail="Some of those sections aren't on this screen any more. Reload and try again.")
    try:
        arch = v2.steps_layer_arch(chosen)
        if body.progress:
            from app import view_engine_2d as v2d

            arch = v2d.steps_progress_arch(arch, chosen, fields, _combined_raw(client, int(view["id"])))
        ve.normalize(ve.apply_inherit_local(view["arch"], arch), fields)  # moves must apply to the screen as it is now
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    cat = va.group_catalog(client)
    name = v2.scoped_layer_name(v2.STEPS_PREFIX, model, vt, int(view["id"]), body.role)
    res = _scoped_publish(client, db, connection_id, model=model, vt=vt, view=view, view_id=body.view_id, name=name, arch=arch,
                          role=body.role, cat=cat, summary=f"Step-by-step mode for {cat.name(body.role)}",
                          expect=[f"{v2.STEPS_PREFIX}_{i}" for i in range(1, len(chosen) + 1)])
    return {**res, "steps": len(chosen), "role": cat.name(body.role)}


class LayerIdBody(ScreenRef):
    layer_view_id: int


def _remove_scoped(connection_id: str, body: LayerIdBody, db: Session, prefix: str) -> dict[str, Any]:
    client = _client(connection_id, db)
    rows = _safe(lambda: client.execute_kw("ir.ui.view", "read", [[int(body.layer_view_id)]], {"fields": ["name", "model"], "context": {"active_test": False}}), [])
    if not rows or not str(rows[0].get("name") or "").startswith(prefix) or rows[0].get("model") != body.model:
        raise HTTPException(status_code=404, detail="That wasn't made in Ingenium, so it can't be removed here.")
    try:
        client.execute_kw("ir.ui.view", "unlink", [[int(body.layer_view_id)]])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    vs.record_version(db, connection_id=connection_id, kind="view", model=body.model, view_type=_vt(body.view_type),
                      layer_name=str(rows[0]["name"]), layer_view_id=None, action="remove", summary=["Removed a role-only layout"],
                      layer_arch=None, layer_active=False, combined_arch=None, odoo_major=_major(client))
    return {"ok": True}


@router.post("/2c/steps/remove")
def steps_remove(connection_id: str, body: LayerIdBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _remove_scoped(connection_id, body, db, v2.STEPS_PREFIX)


class CompareRolesBody(ScreenRef):
    role_a: str
    role_b: str


@router.post("/2c/compare-roles")
def compare_roles(connection_id: str, body: CompareRolesBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, _tag = _screen(client, body)
    cat = va.group_catalog(client)
    for r in (body.role_a, body.role_b):
        if r not in cat.id_of:
            raise HTTPException(status_code=404, detail="That role isn't in this database.")
    fgroups = va.field_level_groups(client, model, cat)
    dev = _major(client) >= 19
    rtree = tree
    raw = _combined_raw(client, int(view["id"]))
    if raw and not body.ops:
        try:
            rtree = ve.normalize(raw, fields).tree
        except ve.EngineError:
            rtree = tree
    a = vl.visibility_for(rtree, cat.member_of_role(body.role_a), fgroups, cat.names(), dev)
    b = vl.visibility_for(rtree, cat.member_of_role(body.role_b), fgroups, cat.names(), dev)
    labels = {n["id"]: str(n.get("label") or n.get("name") or n["id"]) for n, _p, _h in v2.walk(rtree)}
    diff = v2.role_differences(a, b, labels)
    na, nb = cat.name(body.role_a), cat.name(body.role_b)
    if not diff["only_a"] and not diff["only_b"]:
        text = f"{na} and {nb} see the same items on this screen."
    else:
        text = f"{na} sees {len(diff['only_a'])} item{'s' if len(diff['only_a']) != 1 else ''} that {nb} doesn't; {nb} sees {len(diff['only_b'])} that {na} doesn't."
    return {"a": na, "b": nb, **diff, "text": text, "based_on": "Based on group rules. Ingenium can't log in as another person."}


class ABStartBody(ScreenRef):
    role_b: str
    metric_field: str
    name: str = Field(default="Layout test", max_length=80)


@router.post("/2c/abtest/start")
def abtest_start(connection_id: str, body: ABStartBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    require_approval_ok(db, connection_id)  # a test changes what some people see, so it follows the approval rule
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    if not body.ops:
        raise HTTPException(status_code=422, detail="Make the layout B changes first, then start the test.")
    view = _get_views(client, model, vt, body.view_id)
    fields = _rich_fields(client, model)
    meta = fields.get(body.metric_field) or {}
    if not meta or meta.get("store") is False or not lib.countable(meta):
        raise HTTPException(status_code=422, detail="Pick a saved field to measure (how often it gets filled in).")
    name = v2.scoped_layer_name(v2.TEST_PREFIX, model, vt, int(view["id"]), body.role_b)
    for r in vs.list_items(db, connection_id, "abtest"):
        p = vs.item_out(r)["payload"]
        if p.get("layer_name") == name and p.get("status") == "running":
            raise HTTPException(status_code=409, detail="A test for this screen and role is already running.")
    try:
        result = ve.compile_ops(view["arch"], fields, body.ops, **_compile_kwargs(client, fields, body.ops, model))
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    cat = va.group_catalog(client)
    res = _scoped_publish(client, db, connection_id, model=model, vt=vt, view=view, view_id=body.view_id, name=name, arch=result.arch,
                          role=body.role_b, cat=cat, summary=f"Layout test: layout B for {cat.name(body.role_b)}", expect=list(result.expect))
    started = datetime.now(UTC).replace(microsecond=0)
    row = vs.save_item(db, connection_id=connection_id, kind="abtest", key=model, name=body.name, payload={
        "model": model, "view_type": vt, "view_id": body.view_id, "layer_name": name, "layer_view_id": res["layer_view_id"],
        "role_b": body.role_b, "role_b_name": cat.name(body.role_b), "metric_field": body.metric_field,
        "metric_label": str(meta.get("string") or body.metric_field), "started_at": started.isoformat(), "status": "running"})
    return {"ok": True, "item_id": row.id, **res}


def _ab_results(client: Any, p: dict[str, Any]) -> dict[str, Any]:
    cat = va.group_catalog(client)
    model, f = p["model"], p["metric_field"]
    meta = _rich_fields(client, model).get(f) or {}
    internal = [u for u in va.users_with_groups(client, cat) if "base.group_user" in u["member_of"]]
    b_ids = [int(u["id"]) for u in internal if p["role_b"] in u["member_of"]]
    a_ids = [int(u["id"]) for u in internal if p["role_b"] not in u["member_of"]]
    since = datetime.fromisoformat(p["started_at"]).strftime("%Y-%m-%d %H:%M:%S")
    fill = list(lib.fill_domain(f, meta))

    def counts(ids: list[int]) -> tuple[int, int]:
        if not ids:
            return 0, 0
        base = [("create_date", ">=", since), ("create_uid", "in", ids)]
        n = int(client.execute_kw(model, "search_count", [base]))
        return (int(client.execute_kw(model, "search_count", [base + fill])) if n else 0), n

    xa, na = counts(a_ids)
    xb, nb = counts(b_ids)
    return {"metric": str(meta.get("string") or f), "a": {"people": len(a_ids), "records": na, "filled": xa},
            "b": {"people": len(b_ids), "records": nb, "filled": xb}, **v2.proportion_test(xa, na, xb, nb), "role_b": cat.name(p["role_b"])}


@router.post("/2c/abtest/list")
def abtest_list(connection_id: str, body: ModelOnly, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"tests": [vs.item_out(r) for r in vs.list_items(db, connection_id, "abtest", body.model)]}


def _ab_row(db: Session, connection_id: str, item_id: str) -> ViewBuilderItem:
    row = vs.get_item(db, connection_id, item_id)
    if not row or row.kind != "abtest":
        raise HTTPException(status_code=404, detail="That test doesn't exist.")
    return row


@router.post("/2c/abtest/results")
def abtest_results(connection_id: str, body: ItemRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    row = _ab_row(db, connection_id, body.item_id)
    try:
        return {"test": vs.item_out(row), **_ab_results(client, vs.item_out(row)["payload"])}
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc


@router.post("/2c/abtest/stop")
def abtest_stop(connection_id: str, body: ItemRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    require_approval_ok(db, connection_id)
    return _abtest_stop(connection_id, body, db)


def _abtest_stop(connection_id: str, body: ItemRef, db: Session) -> dict[str, Any]:
    """Also used when a test ends by its own rule: that ending was part of what was approved."""
    client = _client(connection_id, db)
    row = _ab_row(db, connection_id, body.item_id)
    p = vs.item_out(row)["payload"]
    if p.get("status") != "running":
        raise HTTPException(status_code=409, detail="That test already stopped.")
    final = _safe(lambda: _ab_results(client, p), None)
    lid = int(p.get("layer_view_id") or 0)
    rows = _safe(lambda: client.execute_kw("ir.ui.view", "read", [[lid]], {"fields": ["name"], "context": {"active_test": False}}), [])
    if rows and str(rows[0].get("name") or "").startswith(v2.TEST_PREFIX):
        try:
            client.execute_kw("ir.ui.view", "unlink", [[lid]])
        except ODOO_ERRORS as exc:
            raise _odoo_error(exc) from exc
    vs.update_item(db, row, {**p, "status": "stopped", "stopped_at": datetime.now(UTC).isoformat(), "final": final})
    return {"ok": True, "final": final}


# ============================================================================
# 10. Dashboard designer
# ============================================================================

class DashSpecBody(BaseModel):
    model: str
    spec: dict[str, Any]


class DashCreateBody(DashSpecBody):
    label: str = Field(min_length=1, max_length=80)
    make_menu: bool = True
    parent_menu_id: int | None = None


@router.post("/2c/dashboards/options")
def dash_options(connection_id: str, body: ModelOnly, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = _check_model(body.model)
    fields = _rich_fields(client, model)
    mine = [vs.item_out(r) for r in vs.list_items(db, connection_id, "screen", model)]
    return {"measures": v2.measure_options(fields), "groupbys": v2.groupby_options(fields), "charts": sorted(v2.CHARTS),
            "intervals": ["day", "week", "month", "quarter", "year"],
            "dashboards": [i for i in mine if i["payload"].get("view_type") in {"graph", "pivot"}]}


def _dash_spec(client: Any, body: DashSpecBody) -> tuple[str, dict[str, Any], dict[str, Any]]:
    model = _check_model(body.model)
    fields = _rich_fields(client, model)
    try:
        return model, fields, v2.validate_dashboard(body.spec, fields)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc


@router.post("/2c/dashboards/preview")
def dash_preview(connection_id: str, body: DashSpecBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Real totals from Odoo's own grouping (no record contents)."""
    client = _client(connection_id, db)
    model, fields, spec = _dash_spec(client, body)
    g = spec["rows"][0]
    if (fields.get(g) or {}).get("type") in {"date", "datetime"}:
        g = f"{g}:{spec['interval']}"
    try:
        rows = _group_counts(client, model, [], g, spec["measures"], limit=40)
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    out = [{"label": _key_label(r["key"]), "count": r["count"], **{m: r.get(m) or 0 for m in spec["measures"]}} for r in rows]
    return {"rows": out, "spec": spec, "measure_labels": {m: str(fields[m].get("string") or m) for m in spec["measures"]},
            "empty": not out, "note": "Totals from your database, grouped by Odoo." if out else "No records yet, so the chart is empty."}


@router.post("/2c/dashboards/create")
def dash_create(connection_id: str, body: DashCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, fields, spec = _dash_spec(client, body)
    label = body.label.strip()
    arch = v2.dashboard_arch(spec, fields, label)
    kind = spec["kind"]

    def check(shown: str) -> str | None:
        lost = [m for m in spec["measures"] + spec["rows"] + spec["cols"] if f'name="{m}"' not in shown]
        return "Odoo shows the dashboard differently, so it was removed." if lost else None

    list_mode = "list" if _major(client) >= 18 else "tree"
    view_id, action_id, menu_id = _create_primary(client, model=model, odoo_type=kind, label=label, arch=arch, make_menu=body.make_menu,
                                                  parent_menu_id=body.parent_menu_id, view_mode=f"{kind},{list_mode}", check=check)
    row = vs.save_item(db, connection_id=connection_id, kind="screen", key=model, name=label,
                       payload={"view_id": view_id, "action_id": action_id, "menu_id": menu_id, "view_type": kind, "template": "dashboard", "spec": spec})
    return {"ok": True, "item_id": row.id, "view_id": view_id, "action_id": action_id, "menu_id": menu_id}


# ============================================================================
# 13. Approval before publish
# ============================================================================

def approvers_map(db: Session, connection_id: str) -> dict[str, list[str]]:
    rows = vs.list_items(db, connection_id, "policy", "approvers")
    return dict(vs.item_out(rows[0])["payload"].get("approvers") or {}) if rows else {}


def approval_policy(db: Session, connection_id: str) -> bool:
    rows = vs.list_items(db, connection_id, "policy", "approval")
    return bool(rows and vs.item_out(rows[0])["payload"].get("required"))


def require_approval_ok(db: Session, connection_id: str) -> None:
    """Called by the normal publish endpoint: with the policy on, only approved changes publish."""
    if approval_policy(db, connection_id) and not APPROVED_PUBLISH.get():
        raise HTTPException(status_code=403, detail={"message": "Changes to screens in this database need approval first. "
                                                                "Ask for approval instead of publishing.", "needs_approval": True})


class PolicyBody(BaseModel):
    required: bool


@router.post("/2c/approvals/policy")
def set_policy(connection_id: str, body: PolicyBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    who = _who(request)
    vs.save_item(db, connection_id=connection_id, kind="policy", key="approval", name="Approval before publish",
                 payload={"required": bool(body.required), "set_by": who.get("email") or "unknown", "at": datetime.now(UTC).isoformat()},
                 replace_key=True)
    return {"ok": True, "required": bool(body.required)}


@router.post("/2c/approvals/policy/get")
def get_policy(connection_id: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    who = _who(request)
    return {"required": approval_policy(db, connection_id), "you": who.get("email"), "identity_verified": who["verified"],
            "note": None if who["verified"] else "Sign-in is off here, so Ingenium can't tell who asks and who approves."}


class ApprovalRequestBody(OpsBody):
    note: str = Field(default="", max_length=500)


def _check_ops(client: Any, model: str, vt: str, view_id: int | None, ops: list[dict[str, Any]]) -> dict[str, Any]:
    view = _get_views(client, model, vt, view_id)
    fields = _fields_get(client, model)
    try:
        ve.compile_ops(view["arch"], fields, ops, **_compile_kwargs(client, fields, ops, model))
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    return view


@router.post("/2c/approvals/request")
def approval_request(connection_id: str, body: ApprovalRequestBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    if not body.ops:
        raise HTTPException(status_code=422, detail="There are no changes to approve.")
    view = _check_ops(client, model, vt, body.view_id, body.ops)
    who = _who(request)
    row = vs.save_item(db, connection_id=connection_id, kind="approval", key=_screen_key(model, vt, body.view_id),
                       name=((body.summary or ["Screen change"])[0])[:120], payload={
                           "model": model, "view_type": vt, "view_id": body.view_id, "ops": body.ops, "summary": body.summary or [],
                           "base_layer_hash": _layer_hash(client, model, vt, int(view["id"])), "requested_by": who.get("email") or "someone",
                           "requested_by_id": who.get("user_id"), "identity_verified": who["verified"], "note": body.note,
                           "status": "pending", "requested_at": datetime.now(UTC).isoformat()})
    return {"ok": True, "item_id": row.id, "status": "pending"}


class ApprovalActionBody(BaseModel):
    action: str  # "guard_fix" | "package_import"
    payload: dict[str, Any]
    summary: list[str] = Field(default_factory=list)
    note: str = Field(default="", max_length=500)


APPROVAL_ACTIONS = {"guard_fix": "Upgrade fix", "package_import": "Layout package import",
                    "checklist_publish": "Stage checklist", "steps_publish": "Step-by-step mode",
                    "abtest_start": "Start a layout test", "abtest_stop": "Stop a layout test",
                    "suite_plan": "Setup plan run", "suite_change": "Batch change run",
                    "shared_write": "Large record change"}


class SuiteApprovalRef(BaseModel):
    """A Configuration Suite plan or batch waiting for approval; the hash pins the exact checked version."""
    ref_id: str
    ref_hash: str
    kind: str = "setup"
    model: str = "suite"


def _run_action(connection_id: str, db: Session, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    from app.routers import view_engine_builder as vb

    token = APPROVED_PUBLISH.set(True)
    try:
        if action == "guard_fix":
            return vb.guard_fix(connection_id, vb.ScreenRef(**payload), db)
        if action == "checklist_publish":
            from app.routers import view_engine_2d as r2d

            return r2d.checklist_publish(connection_id, ScreenRef(**payload), db)
        if action == "steps_publish":
            return steps_publish(connection_id, StepsPublishBody(**payload), db)
        if action == "abtest_start":
            return abtest_start(connection_id, ABStartBody(**payload), db)
        if action == "abtest_stop":
            return _abtest_stop(connection_id, ItemRef(**payload), db)
        if action == "shared_write":  # A5: approval only unlocks the exact change; the person runs it again
            return {"ok": True, "message": "Approved. Run the change again to apply it."}
        if action in {"suite_plan", "suite_change"}:
            from app.routers import suite as rs

            return rs.approval_still_matches(connection_id, db, action, SuiteApprovalRef(**payload))
        return vb.package_import(connection_id, vb.PackageBody(**payload), db)
    finally:
        APPROVED_PUBLISH.reset(token)


@router.post("/2c/approvals/request-action")
def approval_request_action(connection_id: str, body: ApprovalActionBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Ask for approval of an upgrade fix or a package import (they publish whole layers)."""
    from app.routers import view_engine_builder as vb

    if body.action not in APPROVAL_ACTIONS:
        raise HTTPException(status_code=422, detail="Only upgrade fixes, package imports, stage checklists, step-by-step mode, layout tests, suite runs and large record changes can be sent for approval here.")
    kinds = {"guard_fix": vb.ScreenRef, "package_import": vb.PackageBody, "checklist_publish": ScreenRef, "steps_publish": StepsPublishBody,
             "abtest_start": ABStartBody, "abtest_stop": ItemRef, "suite_plan": SuiteApprovalRef, "suite_change": SuiteApprovalRef, "shared_write": SuiteApprovalRef}
    try:
        ref = kinds[body.action](**body.payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="The request is incomplete.") from exc
    who = _who(request)
    model = str(getattr(ref, "model", "") or body.payload.get("model") or "")
    row = vs.save_item(db, connection_id=connection_id, kind="approval", key=f"{body.action}|{model}",
                       name=(body.summary or [APPROVAL_ACTIONS[body.action]])[0][:120], payload={
                           "action": body.action, "action_payload": ref.model_dump(), "model": model, "summary": body.summary or [APPROVAL_ACTIONS[body.action]],
                           "requested_by": who.get("email") or "someone", "requested_by_id": who.get("user_id"), "identity_verified": who["verified"],
                           "note": body.note, "status": "pending", "requested_at": datetime.now(UTC).isoformat()})
    return {"ok": True, "item_id": row.id, "status": "pending"}


@router.post("/2c/approvals/list")
def approval_list(connection_id: str, body: ModelFilter, db: Session = Depends(get_db)) -> dict[str, Any]:
    items = [vs.item_out(r) for r in vs.list_items(db, connection_id, "approval")]
    return {"approvals": [i for i in items if not body.model or i["payload"].get("model") == body.model]}


class ApprovalDecideBody(BaseModel):
    item_id: str
    approve: bool
    reason: str = Field(default="", max_length=500)
    run_at: str | None = None  # approve now, or approve and schedule


def _publish_stored(connection_id: str, db: Session, p: dict[str, Any], approved: bool) -> dict[str, Any]:
    token = APPROVED_PUBLISH.set(approved)
    try:
        return engine_publish(connection_id, OpsBody(model=p["model"], view_type=p["view_type"], view_id=p.get("view_id"), ops=p["ops"],
                                                     summary=p.get("summary") or None, base_layer_hash=p.get("base_layer_hash") or ""), db)
    finally:
        APPROVED_PUBLISH.reset(token)


@router.post("/2c/approvals/decide")
def approval_decide(connection_id: str, body: ApprovalDecideBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = vs.get_item(db, connection_id, body.item_id)
    if not row or row.kind != "approval":
        raise HTTPException(status_code=404, detail="That request doesn't exist.")
    p = vs.item_out(row)["payload"]
    if p.get("status") != "pending":
        raise HTTPException(status_code=409, detail="That request was already decided.")
    who = _who(request)
    if who["verified"] and p.get("requested_by_id") and str(p["requested_by_id"]) == str(who["user_id"]):
        raise HTTPException(status_code=403, detail="Someone else has to approve your own change.")
    from app import view_engine_2d as v2d

    not_allowed = v2d.approver_check(approvers_map(db, connection_id), str(p.get("model") or ""), who.get("email"), bool(who["verified"]))
    if not_allowed:
        raise HTTPException(status_code=403, detail=not_allowed)
    decided = {"decided_by": who.get("email") or "someone", "decided_at": datetime.now(UTC).isoformat(),
               "decider_verified": who["verified"], "reason": body.reason}
    if not body.approve:
        vs.update_item(db, row, {**p, **decided, "status": "rejected"})
        return {"ok": True, "status": "rejected"}
    if p.get("action"):
        if body.run_at:
            raise HTTPException(status_code=422, detail="Upgrade fixes and package imports run when approved; they can't be scheduled.")
        res = _run_action(connection_id, db, p["action"], p.get("action_payload") or {})
        vs.update_item(db, row, {**p, **decided, "status": "approved"})
        return {"ok": True, "status": "approved", "result": res}
    if body.run_at:
        try:
            when = v2.parse_when(body.run_at)
        except ve.EngineError as exc:
            raise _engine_error(exc) from exc
        sched = vs.save_item(db, connection_id=connection_id, kind="schedule", key=row.key, name=row.name, payload={
            **{k: p.get(k) for k in ("model", "view_type", "view_id", "ops", "summary", "base_layer_hash")},
            "run_at": when.isoformat(), "status": "scheduled", "approved": True, "approval_id": row.id, "created_by": decided["decided_by"]})
        vs.update_item(db, row, {**p, **decided, "status": "approved_scheduled", "schedule_id": sched.id, "run_at": when.isoformat()})
        return {"ok": True, "status": "approved_scheduled", "schedule_id": sched.id, "run_at": when.isoformat()}
    try:
        res = _publish_stored(connection_id, db, p, True)
    except HTTPException as exc:
        if exc.status_code == 409 and isinstance(exc.detail, dict) and exc.detail.get("conflict"):
            vs.update_item(db, row, {**p, **decided, "status": "stale", "failure": _detail_text(exc)})
            raise HTTPException(status_code=409, detail="The screen changed after this was requested. Nothing was published; ask again from the current screen.") from exc
        raise
    watch_id = _start_watch(db, connection_id, p["model"], p["view_type"], p.get("view_id"), res, by=decided["decided_by"])
    vs.update_item(db, row, {**p, **decided, "status": "approved", "version_id": res.get("version_id")})
    return {"ok": True, "status": "approved", "publish": res, "watch_id": watch_id}


# ============================================================================
# 14. Scheduled publish
# ============================================================================

class ScheduleBody(OpsBody):
    run_at: str


@router.post("/2c/schedule/create")
def schedule_create(connection_id: str, body: ScheduleBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    if approval_policy(db, connection_id):
        raise HTTPException(status_code=403, detail="Changes here need approval. Ask for approval; the approver can pick when it goes live.")
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    if not body.ops:
        raise HTTPException(status_code=422, detail="There are no changes to schedule.")
    try:
        when = v2.parse_when(body.run_at)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    view = _check_ops(client, model, vt, body.view_id, body.ops)
    who = _who(request)
    row = vs.save_item(db, connection_id=connection_id, kind="schedule", key=_screen_key(model, vt, body.view_id),
                       name=((body.summary or ["Screen change"])[0])[:120], payload={
                           "model": model, "view_type": vt, "view_id": body.view_id, "ops": body.ops, "summary": body.summary or [],
                           "base_layer_hash": _layer_hash(client, model, vt, int(view["id"])), "run_at": when.isoformat(),
                           "status": "scheduled", "approved": False, "created_by": who.get("email") or "someone"})
    return {"ok": True, "item_id": row.id, "run_at": when.isoformat()}


@router.post("/2c/schedule/list")
def schedule_list(connection_id: str, body: ModelFilter, db: Session = Depends(get_db)) -> dict[str, Any]:
    items = [vs.item_out(r) for r in vs.list_items(db, connection_id, "schedule")]
    return {"scheduled": [i for i in items if not body.model or i["payload"].get("model") == body.model]}


@router.post("/2c/schedule/cancel")
def schedule_cancel(connection_id: str, body: ItemRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = vs.get_item(db, connection_id, body.item_id)
    if not row or row.kind != "schedule":
        raise HTTPException(status_code=404, detail="That scheduled change doesn't exist.")
    p = vs.item_out(row)["payload"]
    if p.get("status") != "scheduled":
        raise HTTPException(status_code=409, detail="That change already ran or was cancelled.")
    vs.update_item(db, row, {**p, "status": "cancelled", "cancelled_at": datetime.now(UTC).isoformat()})
    return {"ok": True}


def run_due_schedules(db: Session, connection_id: str | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
    """Publish every scheduled change whose time has come, with the same checks as a
    normal publish, including 'the screen changed since this was scheduled'."""
    now = now or datetime.now(UTC)
    vs._ensure_tables(db)
    q = db.query(ViewBuilderItem).filter(ViewBuilderItem.kind == "schedule")
    if connection_id:
        q = q.filter(ViewBuilderItem.connection_id == connection_id)
    out = []
    for row in q.all():
        p = vs.item_out(row)["payload"]
        if p.get("status") != "scheduled" or datetime.fromisoformat(p["run_at"]) > now:
            continue
        cid = row.connection_id
        from app import view_engine_2d as v2d

        pause = v2d.active_pause([vs.item_out(r)["payload"] for r in vs.list_items(db, cid, "pause")], now)
        if pause:
            if p.get("paused_until") != pause["end"]:
                vs.update_item(db, row, {**p, "paused_until": pause["end"]})
            out.append({"id": row.id, "status": "paused", "until": pause["end"]})
            continue
        if approval_policy(db, cid) and not p.get("approved"):
            vs.update_item(db, row, {**p, "status": "failed", "failure": "Approval became required before this ran. Ask for approval."})
            out.append({"id": row.id, "status": "failed"})
            continue
        vs.update_item(db, row, {**p, "status": "running"})
        try:
            res = _publish_stored(cid, db, p, bool(p.get("approved")))
            _start_watch(db, cid, p["model"], p["view_type"], p.get("view_id"), res, by="schedule")
            vs.update_item(db, row, {**p, "status": "done", "ran_at": now.isoformat(), "version_id": res.get("version_id")})
            out.append({"id": row.id, "status": "done"})
        except HTTPException as exc:
            msg = _detail_text(exc)
            if exc.status_code == 409 and isinstance(exc.detail, dict) and exc.detail.get("conflict"):
                msg = "The screen changed after this was scheduled, so it wasn't published."
            vs.update_item(db, row, {**p, "status": "failed", "ran_at": now.isoformat(), "failure": msg})
            out.append({"id": row.id, "status": "failed", "failure": msg})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            vs.update_item(db, row, {**p, "status": "failed", "ran_at": now.isoformat(), "failure": f"Couldn't reach Odoo ({str(exc)[:120]})."})
            out.append({"id": row.id, "status": "failed"})
    return out


@router.post("/2c/schedule/run-due")
def schedule_run_due(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.builders_ticker import single_runner

    with single_runner(db.get_bind()) as mine:
        if not mine:
            return {"ran": [], "busy": True, "note": "Scheduled changes are being published right now. Try again in a minute."}
        return {"ran": run_due_schedules(db, connection_id)}


# ============================================================================
# 15. Post-publish watch + one-click undo
# ============================================================================

def _start_watch(db: Session, connection_id: str, model: str, vt: str, view_id: int | None, publish_result: dict[str, Any], by: str) -> str | None:
    try:
        start = datetime.now(UTC)
        row = vs.save_item(db, connection_id=connection_id, kind="watch", key=_screen_key(model, _vt(vt), view_id), name=f"{model} {vt}",
                           payload={"model": model, "view_type": _vt(vt), "view_id": view_id, "layer_view_id": publish_result.get("layer_view_id"),
                                    "version_id": publish_result.get("version_id"), "previous_arch": publish_result.get("previous_arch"),
                                    "layer_hash": publish_result.get("layer_hash"), "started_at": start.isoformat(),
                                    "due": v2.watch_due_times(start), "results": [], "status": "watching", "by": by})
        return row.id
    except Exception as exc:  # noqa: BLE001
        logger.warning("watch start failed: %s", exc)
        db.rollback()
        return None


class WatchStartBody(BaseModel):
    model: str
    view_type: str = "form"
    view_id: int | None = None
    version_id: str


@router.post("/2c/watch/start")
def watch_start(connection_id: str, body: WatchStartBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Start watching after a normal publish. What to go back to comes from the
    server's own history, never from the browser."""
    model = _check_model(body.model)
    ver = vs.get_version(db, connection_id, body.version_id)
    if not ver or ver.model != model or ver.action != "publish":
        raise HTTPException(status_code=404, detail="That publish isn't in the history.")
    older = [v for v in vs.list_versions(db, connection_id, ver.layer_name) if v.created_at and ver.created_at and v.created_at < ver.created_at]
    prev = older[0] if older else None
    previous_arch = prev.layer_arch if prev is not None and prev.layer_active and prev.layer_arch else None
    wid = _start_watch(db, connection_id, model, body.view_type, body.view_id, {
        "layer_view_id": ver.layer_view_id, "version_id": ver.id, "previous_arch": previous_arch, "layer_hash": ve.arch_hash(ver.layer_arch or "")}, by="publish")
    return {"ok": bool(wid), "item_id": wid, "checks_at": ["5 minutes", "1 hour", "1 day"]}


def watch_check(db: Session, connection_id: str, row: ViewBuilderItem) -> dict[str, Any]:
    p = vs.item_out(row)["payload"]
    model, vt = p["model"], p["view_type"]
    problems: list[str] = []
    try:
        client = _client(connection_id, db)
        view = _get_views(client, model, vt, p.get("view_id"))
        fields = _fields_get(client, model)
        tree = ve.normalize(view["arch"], fields).tree
        names = list(dict.fromkeys(n.get("name") for n, _h in v2.screen_field_nodes(tree)
                                   if n.get("name") and (fields.get(n["name"]) or {}).get("store") is not False))[:40]
        if names:
            client.execute_kw(model, "search_read", [[]], {"fields": names, "limit": 5})
        layer = None
        if p.get("layer_view_id"):
            rows = client.execute_kw("ir.ui.view", "read", [[int(p["layer_view_id"])]], {"fields": ["active", "arch"], "context": {"active_test": False}})
            layer = rows[0] if rows else None
        if not layer:
            problems.append("The published changes are gone from Odoo.")
        elif not layer.get("active"):
            problems.append("Odoo turned the published changes off.")
        elif p.get("layer_hash") and ve.arch_hash(str(layer.get("arch") or "")) != p["layer_hash"]:
            problems.append("Someone changed this screen again after the publish.")
        from app import view_engine_2d as v2d

        req = [f for f in v2d.static_required(tree) if (fields.get(f) or {}).get("store") is not False and (fields.get(f) or {}).get("type") != "boolean"][:10]
        if req and p.get("started_at"):
            since = datetime.fromisoformat(p["started_at"]).strftime("%Y-%m-%d %H:%M:%S")
            dom: list[Any] = [("write_date", ">=", since)] + ["|"] * (len(req) - 1) + [(f, "=", False) for f in req]
            bad = int(client.execute_kw(model, "search_count", [dom]))
            if bad:
                labels = ", ".join(str((fields.get(f) or {}).get("string") or f) for f in req[:4])
                problems.append(f"{bad} record{'s' if bad != 1 else ''} changed since publishing {'are' if bad != 1 else 'is'} missing a field the screen now requires ({labels}), so saving {'them' if bad != 1 else 'it'} will fail until filled in.")
        guard = vs.get_guard(db, connection_id, ve.layer_name(model, vt, int(view["id"])))
        if guard and guard.get("stock") and guard["stock"] != vp.stock_signature(_stock_hashes(client, model)):
            problems.append("Odoo's own screen for this record type changed (an update or another app).")
    except HTTPException as exc:
        problems.append(_detail_text(exc, "The screen didn't open."))
    except ODOO_ERRORS as exc:
        problems.append(f"Odoo refused to open the screen or its records: {str(exc)[:160]}")
    except ve.EngineError as exc:
        problems.append(str(exc))
    now = datetime.now(UTC)
    results = [*p.get("results", []), {"at": now.isoformat(), "ok": not problems, "problems": problems}]
    remaining = [d for d in (p.get("due") or []) if datetime.fromisoformat(d) > now]
    status = "problem" if problems else ("watching" if remaining else "done")
    vs.update_item(db, row, {**p, "results": results, "due": remaining, "status": status})
    return {"ok": not problems, "problems": problems, "status": status}


@router.post("/2c/watch/list")
def watch_list(connection_id: str, body: ModelFilter, db: Session = Depends(get_db)) -> dict[str, Any]:
    items = [vs.item_out(r) for r in vs.list_items(db, connection_id, "watch")]
    items = [i for i in items if not body.model or i["payload"].get("model") == body.model][:30]
    for i in items:
        i["payload"]["can_undo"] = i["payload"].get("status") != "undone" and bool(i["payload"].get("layer_view_id"))
        i["payload"]["goes_back_to"] = "the earlier changes" if i["payload"].pop("previous_arch", None) else "Odoo's standard screen"
    return {"watches": items}


def _watch_row(db: Session, connection_id: str, item_id: str) -> ViewBuilderItem:
    row = vs.get_item(db, connection_id, item_id)
    if not row or row.kind != "watch":
        raise HTTPException(status_code=404, detail="That watch doesn't exist.")
    return row


@router.post("/2c/watch/check")
def watch_check_now(connection_id: str, body: ItemRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    return watch_check(db, connection_id, _watch_row(db, connection_id, body.item_id))


@router.post("/2c/watch/undo")
def watch_undo(connection_id: str, body: ItemRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    """One click back to how the screen was before that publish (server-held copy)."""
    row = _watch_row(db, connection_id, body.item_id)
    p = vs.item_out(row)["payload"]
    if p.get("status") == "undone":
        raise HTTPException(status_code=409, detail="That publish was already undone.")
    if not p.get("layer_view_id"):
        raise HTTPException(status_code=409, detail="There's nothing to undo.")
    prev = p.get("previous_arch")
    res = engine_revert(connection_id, RevertBody(model=p["model"], view_type=p["view_type"], view_id=p.get("view_id"),
                                                  layer_view_id=int(p["layer_view_id"]), mode="restore" if prev else "deactivate",
                                                  restore_arch=prev), db)
    vs.update_item(db, row, {**p, "status": "undone", "undone_at": datetime.now(UTC).isoformat()})
    return {"ok": True, **res}


def run_due_watches(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    vs._ensure_tables(db)
    n = 0
    for row in db.query(ViewBuilderItem).filter(ViewBuilderItem.kind == "watch").all():
        p = vs.item_out(row)["payload"]
        if p.get("status") == "watching" and p.get("due") and datetime.fromisoformat(p["due"][0]) <= now:
            try:
                watch_check(db, row.connection_id, row)
                n += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("watch check failed: %s", exc)
                db.rollback()
    return n


# ============================================================================
# 16. Weekly digest
# ============================================================================

class DigestBody(BaseModel):
    days: int = 7


def _db_label(db: Session, connection_id: str) -> str:
    from app.odoo_service import get_connection_or_404

    try:
        row = get_connection_or_404(db, connection_id)
        return str(getattr(row, "name", "") or getattr(row, "database", "") or "this database")
    except Exception:  # noqa: BLE001
        return "this database"


def build_digest(db: Session, connection_id: str, days: int) -> dict[str, Any]:
    vs._ensure_tables(db)
    since = (datetime.now(UTC) - timedelta(days=days)).replace(tzinfo=None)
    rows = (db.query(ViewLayerVersion).filter(ViewLayerVersion.connection_id == connection_id, ViewLayerVersion.created_at >= since)
            .order_by(ViewLayerVersion.created_at.desc()).limit(500).all())
    versions = [{**vs.version_out(r), "model": r.model, "view_type": r.view_type} for r in rows]
    approvals = [vs.item_out(r)["payload"] for r in vs.list_items(db, connection_id, "approval")]
    schedules = [vs.item_out(r)["payload"] for r in vs.list_items(db, connection_id, "schedule")]
    alerts = []
    for r in vs.list_items(db, connection_id, "watch"):
        p = vs.item_out(r)["payload"]
        if p.get("status") == "problem":
            last = (p.get("results") or [{}])[-1]
            alerts.append({"screen": f"{p.get('model')} · {p.get('view_type')}", "problem": "; ".join(last.get("problems") or [])})
    return v2.digest_payload(versions, approvals, schedules, alerts, days, _db_label(db, connection_id))


@router.post("/2c/digest/preview")
def digest_preview(connection_id: str, body: DigestBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    subs = vs.list_items(db, connection_id, "digest", "weekly")
    return {**build_digest(db, connection_id, max(1, min(31, int(body.days)))),
            "subscription": vs.item_out(subs[0])["payload"] if subs else None}


class DigestSubBody(BaseModel):
    to: str = Field(default="", max_length=200)
    on: bool = True
    weekday: int = 0  # Monday


@router.post("/2c/digest/subscribe")
def digest_subscribe(connection_id: str, body: DigestSubBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    to = body.to.strip() or str(_who(request).get("email") or "")
    if body.on and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", to):
        raise HTTPException(status_code=422, detail="Enter an email address for the digest.")
    vs.save_item(db, connection_id=connection_id, kind="digest", key="weekly", name="Weekly digest",
                 payload={"to": to, "on": bool(body.on), "weekday": max(0, min(6, int(body.weekday))), "last_sent": None}, replace_key=True)
    servers = _mail_servers(_client(connection_id, db))
    return {"ok": True, "on": bool(body.on), "to": to,
            "delivery": ("Sent through this Odoo's outgoing mail server." if servers else
                         "This Odoo has no outgoing mail server set up, so the digest is only written to Ingenium's log. "
                         "Add one in Odoo (Settings > Technical > Outgoing Mail Servers) to get it by email.")}


@router.post("/2c/digest/send-now")
def digest_send_now(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = vs.list_items(db, connection_id, "digest", "weekly")
    p = vs.item_out(rows[0])["payload"] if rows else {}
    if not p.get("to"):
        raise HTTPException(status_code=422, detail="Turn on the weekly digest with an email address first.")
    d = build_digest(db, connection_id, 7)
    res = send_via_odoo(_client(connection_id, db), p["to"], "Weekly screen changes", d["text"])
    if res["status"] == "log_only":
        logger.info("weekly digest for %s (no mail server in Odoo, log only):\n%s", p["to"], d["text"])
    return {"to": p["to"], **res}


def _mail_servers(client: Any) -> int:
    return int(_safe(lambda: client.execute_kw("ir.mail_server", "search_count", [[("active", "=", True)]]), 0) or 0)


def send_via_odoo(client: Any, to: str, subject: str, text: str, html: str | None = None) -> dict[str, Any]:
    """Send through the connected Odoo's own mail (mail.mail + its outgoing server).
    With no outgoing server, nothing is sent and the caller logs it instead."""
    if not _mail_servers(client):
        return {"status": "log_only", "note": "No outgoing mail server in Odoo, so it was only written to the log."}
    mid = int(client.execute_kw("mail.mail", "create", [{"email_to": to, "subject": subject, "body_html": html or v2.plain_html(text), "auto_delete": False}]))
    try:
        client.execute_kw("mail.mail", "send", [[mid]])
    except ODOO_ERRORS as exc:
        if "marshal" not in str(exc).lower() and "None" not in str(exc):
            raise
    rows = client.execute_kw("mail.mail", "read", [[mid]], {"fields": ["state", "failure_reason"]})
    st = (rows[0] if rows else {}).get("state") or "sent"
    if st == "exception":
        return {"status": "failed", "note": f"Odoo couldn't send it: {str(rows[0].get('failure_reason') or '')[:200]}"}
    return {"status": "sent" if st == "sent" else "queued", "note": "Sent by Odoo." if st == "sent" else "Waiting in Odoo's outgoing mail queue."}


def run_due_digests(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    vs._ensure_tables(db)
    sent = 0
    for row in db.query(ViewBuilderItem).filter(ViewBuilderItem.kind == "digest").all():
        p = vs.item_out(row)["payload"]
        if not p.get("on") or not p.get("to") or now.weekday() != int(p.get("weekday") or 0) or now.hour < 7:
            continue
        if p.get("last_sent") and now - datetime.fromisoformat(p["last_sent"]) < timedelta(days=6):
            continue
        d = build_digest(db, row.connection_id, 7)
        try:
            res = send_via_odoo(_client(row.connection_id, db), p["to"], "Weekly screen changes", d["text"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("digest send failed: %s", exc)
            db.rollback()
            continue
        if res["status"] == "log_only":
            logger.info("weekly digest for %s (no mail server in Odoo, log only):\n%s", p["to"], d["text"])
        from app.routers.view_engine_2d import chat_settings, send_chat

        chat = chat_settings(db, row.connection_id)
        if chat:
            try:
                send_chat(chat, "Weekly screen changes", d["text"])
                res = {**res, "chat": "sent"}
            except Exception as exc:  # noqa: BLE001
                res = {**res, "chat": f"failed: {str(exc)[:120]}"}
        vs.update_item(db, row, {**p, "last_sent": now.isoformat(), "last_delivery": res})
        sent += 1
    return sent


# ============================================================================
# 19. Live co-editing
# ============================================================================



class CoeditBody(BaseModel):
    model: str
    view_type: str = "form"
    view_id: int | None = None
    editor_id: str = Field(min_length=4, max_length=64)
    name: str = Field(default="Someone", max_length=80)
    selected: str | None = None
    since: int = 0
    base_seq: int = 0
    ops: list[dict[str, Any]] = Field(default_factory=list)


def _locked_room(db: Session, connection_id: str, key: str) -> ViewBuilderItem:
    """The shared draft for one screen, stored in the app database so it survives a
    restart and is the same for every worker. Row-locked while it is merged
    (PostgreSQL: SELECT ... FOR UPDATE; SQLite serialises writers itself)."""
    vs._ensure_tables(db)

    def q():  # noqa: ANN202
        qq = (db.query(ViewBuilderItem).filter(ViewBuilderItem.connection_id == connection_id, ViewBuilderItem.kind == "coedit",
                                               ViewBuilderItem.key == key).order_by(ViewBuilderItem.created_at, ViewBuilderItem.id))
        return qq.with_for_update() if db.bind is not None and db.bind.dialect.name == "postgresql" else qq

    row = q().first()
    if row is None:
        vs.save_item(db, connection_id=connection_id, kind="coedit", key=key, name="Shared draft", payload={})
        row = q().first()
    return row


@router.post("/2c/coedit")
def coedit(connection_id: str, body: CoeditBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    key = f"{_check_model(body.model)}|{_vt(body.view_type)}|{int(body.view_id or 0)}"
    name = str(_who(request).get("email") or body.name or "Someone")
    row = _locked_room(db, connection_id, key)
    room = vs.item_out(row)["payload"] or {}
    out = v2.merge_coedit(room, body.editor_id, name, body.selected, int(body.since), body.ops, int(body.base_seq), time.time())
    room["log"] = (room.get("log") or [])[-500:]
    vs.update_item(db, row, room)
    return out


# ============================================================================
# Reports: 11. per-company brands, 18. report from a photo or PDF
# ============================================================================

@reports_router.post("/2c/brand/companies")
def brand_companies(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.routers.view_engine_reports2 import BRAND_FIELDS

    client = _client(connection_id, db)
    have = [f for f in BRAND_FIELDS if f in (client.execute_kw("res.company", "fields_get", [list(BRAND_FIELDS)], {"attributes": ["type"]}) or {})]
    rows = client.execute_kw("res.company", "search_read", [[]], {"fields": ["id", "name", *have]})
    out = [{**{k: r.get(k) for k in ("id", "name", *have)}, "can_undo": bool(vs.list_items(db, connection_id, "brand", str(r["id"])))}
           for r in rows or []]
    return {"companies": out, "note": "Each company keeps its own document style. Odoo stores it on the company."}


class BrandCopyBody(BaseModel):
    from_company_id: int
    to_company_ids: list[int] = Field(min_length=1, max_length=50)
    keys: list[str] = Field(default_factory=lambda: ["external_report_layout_id", "primary_color", "secondary_color", "font"])


@reports_router.post("/2c/brand/copy")
def brand_copy(connection_id: str, body: BrandCopyBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Copy one company's style to others, each through the checked brand apply (each with its own undo)."""
    from app.routers.view_engine_reports2 import BRAND_FIELDS, BrandBody, _company, brand_apply

    client = _client(connection_id, db)
    src = _company(client, body.from_company_id)
    vals: dict[str, Any] = {}
    for k in body.keys:
        if k not in BRAND_FIELDS:
            raise HTTPException(status_code=422, detail=f"'{k}' isn't a brand setting.")
        v = src.get(k)
        if v not in (None, False, ""):
            vals[k] = v[0] if isinstance(v, list) else v
    if not vals:
        raise HTTPException(status_code=422, detail="That company has no style set to copy.")
    results = []
    for cid in dict.fromkeys(int(c) for c in body.to_company_ids):
        if cid == int(body.from_company_id):
            continue
        try:
            r = brand_apply(connection_id, BrandBody(company_id=cid, values=vals), db)
            results.append({"company_id": cid, "ok": True, "applied": r["applied"]})
        except HTTPException as exc:
            results.append({"company_id": cid, "ok": False, "error": _detail_text(exc, "Odoo refused.")})
    return {"results": results, "copied": vals}


class FromDocBody(BaseModel):
    report_id: int
    filename: str = Field(max_length=200)
    content_b64: str = Field(max_length=14_000_000)


@reports_router.post("/2c/from-document")
def report_from_document(connection_id: str, body: FromDocBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Read a sample document; AI proposes which printed parts match which fields;
    code keeps only real fields and returns a draft. Nothing is published."""
    from app import view_engine_ai as vai
    from app import view_engine_report_blocks as rb
    from app.routers.view_engine_reports2 import _related, _report_setup

    client = _client(connection_id, db)
    ctx = _report_setup(client, body.report_id)
    fields = ctx["fields"]
    try:
        raw = base64.b64decode(body.content_b64, validate=False)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="The file couldn't be read.") from exc
    name = body.filename.lower()
    if name.endswith(".pdf") or raw[:4] == b"%PDF":
        try:
            lines = v2.pdf_text_lines(raw)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail="That PDF couldn't be read.") from exc
        if not lines:  # a scan: read the page pictures instead (stage 2e)
            from app import view_engine_2d as v2d
            from app.routers.view_engine_2d import read_picture

            try:
                pages = v2d.pdf_page_pngs(raw)
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=422, detail="That PDF couldn't be read.") from exc
            try:
                for png in pages:
                    lines += read_picture(png, "image/png")
            except vai.AIUnavailable as exc:
                return {"placements": [], "blocks": [], "dropped": [], "lines": 0,
                        "unclear": [f"This PDF is a scan with no text in it. {exc}"]}
            if not lines:
                return {"placements": [], "blocks": [], "dropped": [], "lines": 0, "unclear": ["No text could be read in this scanned PDF."]}
    elif name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        from app.routers.view_engine_2d import read_picture

        mime = {"png": "image/png", "webp": "image/webp"}.get(name.rsplit(".", 1)[-1], "image/jpeg")
        if len(raw) < 1000:
            return {"placements": [], "blocks": [], "dropped": [], "lines": 0, "unclear": ["That picture is too small to read."]}
        try:
            lines = read_picture(raw, mime)
        except vai.AIUnavailable as exc:
            return {"placements": [], "blocks": [], "dropped": [], "lines": 0, "unclear": [str(exc)]}
        if not lines:
            return {"placements": [], "blocks": [], "dropped": [], "lines": 0, "unclear": ["No text could be read in that picture."]}
    elif name.endswith((".txt", ".csv")):
        lines = [ln.strip()[:160] for ln in raw.decode("utf-8", "replace").splitlines() if ln.strip()][:200]
    else:
        raise HTTPException(status_code=422, detail="Upload a PDF, a photo or a text file.")
    o2m = sorted(n for n, m in fields.items() if m.get("type") == "one2many")[:6]
    related = _related(client, fields, set(o2m))
    field_list = [{"name": n, "label": m.get("string"), "type": m.get("type")} for n, m in fields.items()
                  if not n.startswith(("message_", "activity_", "__")) and m.get("type") not in {"binary", "properties", "json"}][:250]
    line_fields = {k: [{"name": n, "label": m.get("string"), "type": m.get("type")} for n, m in v.items()][:80] for k, v in related.items()}
    try:
        prop = vai.designer_json(v2.DOC_SYSTEM_PROMPT, {"lines": lines, "fields": field_list, "line_fields": line_fields}, v2.DOC_SCHEMA, "report_from_document")
    except vai.AIUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    blocks: list[dict[str, Any]] = []
    dropped: list[str] = []
    for b in prop.get("blocks") or []:
        f = str(b.get("field") or "") if isinstance(b, dict) else ""
        one, drop = v2.validate_doc_proposal({"blocks": [b]}, fields, related.get(f))
        blocks.extend(one)
        dropped.extend(drop)
    if blocks:
        try:
            blocks = rb.validate_blocks(blocks, fields, related)
        except ve.EngineError as exc:
            dropped.append(str(exc))
            blocks = []
    return {"placements": [{"slot": "bottom", "blocks": blocks}] if blocks else [], "blocks": blocks, "dropped": dropped,
            "unclear": [str(u)[:200] for u in (prop.get("unclear") or [])][:20], "lines": len(lines),
            "note": "A draft for you to check. Nothing is published until you press Publish in the designer."}


# ============================================================================
# Emails: 12. email app checks + dark preview
# ============================================================================

class EmailCheckBody(BaseModel):
    template_id: int
    record_id: int | None = None


@emails_router.post("/2c/checks")
def email_app_checks(connection_id: str, body: EmailCheckBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.routers.view_engine_reports2 import _render_email, _template

    client = _client(connection_id, db)
    tpl = _template(client, body.template_id)
    html = str(tpl.get("body_html") or "")
    rendered = None
    if body.record_id and tpl.get("model"):
        rendered = _render_email(client, body.template_id, str(tpl["model"]), int(body.record_id))
        html = rendered["html"]
    return {**v2.email_checks(html), "checked": "rendered for one record" if rendered else "the template as written",
            "html": html if rendered else None,
            "note": "Checks against what common email apps are known to do. Real inbox tests aren't connected."}
