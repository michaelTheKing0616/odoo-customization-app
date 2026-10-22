"""View Designer stage 2b endpoints: component library, widgets, usage
suggestions, layout checks and health score, Tidy up, performance hints,
inline field creation, related fields, defaults and smart button lists.

Facts come from Odoo (counts only, never record contents); decisions are code
in view_engine_library; AI only proposes Tidy up groups. Everything that edits
a screen returns ops for the normal compile/publish path.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import view_engine as ve
from app import view_engine_ai as vai
from app import view_engine_library as lib
from app import view_engine_portable as vp
from app.db import get_db
from app.routers.view_engine import (
    ODOO_ERRORS,
    _check_model,
    _client,
    _compile_kwargs,
    _engine_error,
    _get_views,
    _major,
    _odoo_error,
    _vt,
)

router = APIRouter(prefix="/connections/{connection_id}/views/engine", tags=["view-engine"])

RICH_ATTRS = ["string", "type", "required", "readonly", "relation", "relation_field", "selection", "store", "related", "depends", "help"]


class ScreenRef(BaseModel):
    model: str
    view_type: str = "form"
    view_id: int | None = None
    ops: list[dict[str, Any]] = Field(default_factory=list)


def _rich_fields(client: Any, model: str) -> dict[str, Any]:
    try:
        return client.execute_kw(model, "fields_get", [], {"attributes": RICH_ATTRS}) or {}
    except ODOO_ERRORS as exc:
        raise HTTPException(status_code=404, detail=f"Odoo doesn't know the record type {model}.") from exc


def _screen(client: Any, body: ScreenRef) -> tuple[str, str, dict[str, Any], dict[str, Any], dict[str, Any], str]:
    model, vt = _check_model(body.model), _vt(body.view_type)
    view = _get_views(client, model, vt, body.view_id)
    fields = _rich_fields(client, model)
    arch = view["arch"]
    if body.ops:
        try:
            arch = ve.compile_ops(arch, fields, body.ops, **_compile_kwargs(client, fields, body.ops, model)).expected_arch
        except ve.EngineError as exc:
            raise _engine_error(exc) from exc
    tree = ve.normalize(arch, fields).tree
    return model, vt, view, fields, tree, ve.parse_arch(arch).tag


def _counts(client: Any, model: str, tree: dict[str, Any], fields: dict[str, Any]) -> tuple[dict[str, int], int]:
    total = int(client.execute_kw(model, "search_count", [[]]))
    counts: dict[str, int] = {}
    if not total:
        return counts, 0
    for item in lib.screen_fields(tree)[:120]:
        name = item["node"].get("name") or ""
        meta = fields.get(name) or {}
        if name in counts or not lib.countable(meta):
            continue
        try:
            counts[name] = int(client.execute_kw(model, "search_count", [lib.fill_domain(name, meta)]))
        except ODOO_ERRORS:
            continue
    return counts, total


def _group_max(client: Any, model: str, field: str) -> int:
    """Largest number of rows linked to one record (counts only)."""
    for method, kw in (("formatted_read_group", {"groupby": [field], "aggregates": ["__count"], "order": "__count desc", "limit": 1}),
                       ("read_group", {"orderby": "__count desc", "limit": 1, "lazy": True})):
        try:
            if method == "read_group":
                rows = client.execute_kw(model, method, [[(field, "!=", False)], [field], [field]], kw)
                return int((rows or [{}])[0].get(f"{field}_count") or (rows or [{}])[0].get("__count") or 0)
            rows = client.execute_kw(model, method, [[(field, "!=", False)]], kw)
            return int((rows or [{}])[0].get("__count") or 0)
        except ODOO_ERRORS:
            continue
    return 0


# ----------------------------------------------------------------------------
# Library and widgets
# ----------------------------------------------------------------------------

@router.post("/library")
def component_library(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, root_tag = _screen(client, body)
    major = _major(client)
    on_screen = {i["node"].get("name") for i in lib.screen_fields(tree)}
    existing = [
        {"name": n, "label": str(m.get("string") or n), "type": m.get("type"), "on_screen": n in on_screen,
         "widgets": lib.widgets_for(str(m.get("type") or ""), major)}
        for n, m in sorted(fields.items(), key=lambda kv: str(kv[1].get("string") or kv[0]).lower())
        if not n.startswith("__") and m.get("type") not in {"properties_definition", "json"}
    ]
    out = lib.library(major, root_tag, fields)
    out.update({"major": major, "root_tag": root_tag, "existing_fields": existing})
    return out


class WidgetsBody(BaseModel):
    field_type: str


@router.post("/widgets")
def widgets(connection_id: str, body: WidgetsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    major = _major(client)
    return {"major": major, "widgets": lib.widgets_for(body.field_type, major)}


# ----------------------------------------------------------------------------
# Usage, checks, health score, performance, Tidy up
# ----------------------------------------------------------------------------

@router.post("/usage")
def usage(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Fill rates from counts only. No record contents leave Odoo."""
    client = _client(connection_id, db)
    model, vt, view, fields, tree, root_tag = _screen(client, body)
    try:
        counts, total = _counts(client, model, tree, fields)
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    rates = {n: {"count": c, "rate": lib.pct(c, total)} for n, c in counts.items()}
    return {"total": total, "fill": rates, "suggestions": lib.usage_suggestions(tree, fields, counts, total)}


@router.post("/checks")
def checks(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, root_tag = _screen(client, body)
    try:
        counts, total = _counts(client, model, tree, fields)
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    suggestions = lib.usage_suggestions(tree, fields, counts, total)
    issues = lib.layout_checks(tree, fields, root_tag)
    line_stats: dict[str, dict[str, int]] = {}
    for item in lib.screen_fields(tree):
        n = item["node"]
        meta = fields.get(n.get("name") or "") or {}
        if meta.get("type") == "one2many" and meta.get("relation") and meta.get("relation_field") and not item["hidden"]:
            line_stats[n["name"]] = {"max": _group_max(client, str(meta["relation"]), str(meta["relation_field"]))}
    hints = lib.performance_hints(tree, fields, root_tag, line_stats)
    visible = [i for i in lib.screen_fields(tree) if not i["hidden"]]
    empty = sum(1 for i in visible if total >= 20 and (i["node"].get("name") in counts) and lib.pct(counts[i["node"]["name"]], total) < 5)
    health = lib.health_score(issues, suggestions, len(visible), empty if total >= 20 else None)
    return {"health": health, "issues": issues, "suggestions": suggestions, "performance": hints, "total": total}


class TidyBody(ScreenRef):
    use_ai: bool = True


@router.post("/tidy")
def tidy(connection_id: str, body: TidyBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Proposal + preview: ops and the screen they would produce. Nothing is published."""
    client = _client(connection_id, db)
    model, vt, view, fields, tree, root_tag = _screen(client, body)
    if root_tag != "form":
        raise HTTPException(status_code=422, detail="Tidy up works on forms.")
    counts, total = _counts(client, model, tree, fields)
    sections: dict[str, str] = {}
    note = None
    if body.use_ai:
        payload = [{"name": i["node"].get("name"), "label": i["node"].get("label"),
                    "type": (fields.get(i["node"].get("name") or "") or {}).get("type")}
                   for i in lib.screen_fields(tree) if not i["hidden"]]
        try:
            sections = lib.validate_sections(vai.propose_sections(payload), tree)
        except vai.AIUnavailable as exc:
            note = f"{exc} Tidy up still balances columns and puts the busiest fields first."
    plan = lib.tidy_plan(tree, fields, counts, total, sections)
    if not plan["ops"]:
        return {"ops": [], "descriptions": [], "note": note or "This screen is already tidy.", "sections": sections}
    try:
        result = ve.compile_ops(view["arch"], fields, [*body.ops, *plan["ops"]], **_compile_kwargs(client, fields, plan["ops"], model))
    except ve.EngineError as exc:
        return {"ops": [], "descriptions": [], "note": f"Tidy up couldn't find a safe way to rearrange this screen: {exc}", "sections": sections}
    return {"ops": plan["ops"], "descriptions": plan["descriptions"], "note": note, "sections": sections,
            "expected_tree": ve.normalize(result.expected_arch, fields).tree}


# ----------------------------------------------------------------------------
# Fields: create inline (stock first), related, delete (undo), defaults
# ----------------------------------------------------------------------------

class FieldCreateBody(BaseModel):
    model: str
    spec: dict[str, Any]
    force: bool = False  # create even though a similar field exists


def _model_id(client: Any, model: str) -> int:
    rows = client.execute_kw("ir.model", "search_read", [[("model", "=", model)]], {"fields": ["id"], "limit": 1})
    if not rows:
        raise HTTPException(status_code=404, detail="That record type isn't in this database.")
    return int(rows[0]["id"])


@router.post("/fields/create")
def field_create(connection_id: str, body: FieldCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = _check_model(body.model)
    fields = _rich_fields(client, model)
    major = _major(client)
    spec = body.spec or {}
    kind = lib.TYPE_BY_KEY.get(str(spec.get("type") or "")) or {}
    if not body.force and spec.get("type") != "related":
        similar = lib.similar_fields(str(spec.get("label") or ""), kind.get("ttype"), fields)
        if similar:
            return {"created": False, "similar": similar,
                    "message": f"{similar[0]['label']} already exists on this record type. Use it, or create a new field anyway."}
    related_meta = None
    if spec.get("type") == "related":
        path = str(spec.get("related") or "").split(".")
        cur_model, meta = model, None
        for i, part in enumerate(path):
            fmeta = (_rich_fields(client, cur_model) if i else fields).get(part)
            if not fmeta:
                break
            meta = fmeta
            cur_model = str(fmeta.get("relation") or "")
            if i < len(path) - 1 and not cur_model:
                meta = None
                break
        related_meta = meta
    relation_models = None
    if kind.get("needs") == "relation":
        rel = str(spec.get("relation") or "")
        relation_models = {rel} if client.execute_kw("ir.model", "search_count", [[("model", "=", rel)]]) else set()
    try:
        plan = lib.plan_new_field(spec, fields, _model_id(client, model), major,
                                  relation_models=relation_models, related_meta=related_meta)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    if spec.get("type") == "lines":
        inv = (_rich_fields(client, str(plan["values"]["relation"])).get(str(plan["values"]["relation_field"])) or {})
        if inv.get("type") != "many2one" or inv.get("relation") != model:
            raise HTTPException(status_code=422, detail="That field on the linked records doesn't point back to this record type.")
    try:
        fid = int(client.execute_kw("ir.model.fields", "create", [plan["values"]]))
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    return {"created": True, "id": fid, "name": plan["name"], "widget": plan["widget"],
            "label": plan["values"]["field_description"], "type": plan["values"].get("ttype")}


class InverseBody(BaseModel):
    model: str
    relation: str


@router.post("/fields/inverse-options")
def inverse_options(connection_id: str, body: InverseBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, rel = _check_model(body.model), _check_model(body.relation)
    fields = _rich_fields(client, rel)
    return {"options": [{"name": n, "label": str(m.get("string") or n)} for n, m in fields.items()
                        if m.get("type") == "many2one" and m.get("relation") == model]}


@router.post("/fields/related")
def related_fields(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = _check_model(body.model)
    fields = _rich_fields(client, model)
    rel_models = sorted({str(m["relation"]) for m in fields.values() if m.get("type") == "many2one" and m.get("relation")})[:30]
    rel_fields: dict[str, dict[str, Any]] = {}
    for rm in rel_models:
        try:
            rel_fields[rm] = client.execute_kw(rm, "fields_get", [], {"attributes": ["string", "type", "relation"]}) or {}
        except ODOO_ERRORS:
            continue
    return {"choices": lib.related_choices(fields, rel_fields)}


class FieldDeleteBody(BaseModel):
    model: str
    name: str


@router.post("/fields/delete")
def field_delete(connection_id: str, body: FieldDeleteBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Undo for a field made here: only custom (x_) fields, and Odoo refuses if a screen still uses it."""
    client = _client(connection_id, db)
    model = _check_model(body.model)
    if not body.name.startswith("x_"):
        raise HTTPException(status_code=422, detail="Only fields made in Ingenium or Studio can be removed here.")
    rows = client.execute_kw("ir.model.fields", "search_read", [[("model", "=", model), ("name", "=", body.name), ("state", "=", "manual")]],
                             {"fields": ["id"], "limit": 1})
    if not rows:
        raise HTTPException(status_code=404, detail="That field isn't a custom field on this record type.")
    try:
        client.execute_kw("ir.model.fields", "unlink", [[int(rows[0]["id"])]])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    return {"ok": True}


class DefaultBody(BaseModel):
    model: str
    field: str
    value: Any = None
    clear: bool = False


def _default_row(client: Any, model: str, field: str) -> dict[str, Any] | None:
    rows = client.execute_kw("ir.default", "search_read",
                             [[("field_id.model", "=", model), ("field_id.name", "=", field), ("user_id", "=", False), ("company_id", "=", False)]],
                             {"fields": ["id", "json_value"], "limit": 1})
    return rows[0] if rows else None


@router.post("/defaults/get")
def default_get(connection_id: str, body: DefaultBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    row = _default_row(client, _check_model(body.model), body.field)
    return {"value": json.loads(row["json_value"]) if row and row.get("json_value") else None, "set": bool(row)}


@router.post("/defaults/set")
def default_set(connection_id: str, body: DefaultBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Stock first: Odoo's own defaults (ir.default) for everyone. Returns the previous value for undo."""
    client = _client(connection_id, db)
    model = _check_model(body.model)
    fields = _rich_fields(client, model)
    meta = fields.get(body.field)
    if not meta or meta.get("store") is False or meta.get("type") in {"binary", "one2many", "many2many", "html"}:
        raise HTTPException(status_code=422, detail="This field can't have a starting value.")
    before = _default_row(client, model, body.field)
    prev = json.loads(before["json_value"]) if before and before.get("json_value") else None
    try:
        if body.clear:
            if before:
                client.execute_kw("ir.default", "unlink", [[int(before["id"])]])
        else:
            value = body.value
            if meta.get("type") == "selection" and value not in {k for k, _ in meta.get("selection") or []}:
                raise HTTPException(status_code=422, detail="Pick one of the choices.")
            if meta.get("type") in {"integer", "float", "monetary"}:
                try:
                    value = float(value) if meta["type"] != "integer" else int(value)
                except (TypeError, ValueError) as exc:
                    raise HTTPException(status_code=422, detail="Enter a number.") from exc
            if meta.get("type") == "boolean":
                value = bool(value)
            if meta.get("type") == "many2one":
                if not isinstance(value, int) or not client.execute_kw(str(meta["relation"]), "search_count", [[("id", "=", value)]]):
                    raise HTTPException(status_code=422, detail="That record wasn't found.")
            client.execute_kw("ir.default", "set", [model, body.field, value])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    return {"ok": True, "previous": prev, "had_previous": bool(before)}


# ----------------------------------------------------------------------------
# Smart buttons: lists of related records to open
# ----------------------------------------------------------------------------

class SmartListBody(BaseModel):
    model: str


@router.post("/smart-button/options")
def smart_options(connection_id: str, body: SmartListBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Records elsewhere that point to this record type (counts made by code, not AI)."""
    client = _client(connection_id, db)
    model = _check_model(body.model)
    rows = client.execute_kw("ir.model.fields", "search_read",
                             [[("relation", "=", model), ("ttype", "=", "many2one"), ("store", "=", True),
                               ("model_id.transient", "=", False), ("model", "not like", "ir.%"), ("model", "not like", "mail.%")]],
                             {"fields": ["name", "field_description", "model", "model_id"], "limit": 200})
    names = {r["model"]: (r.get("model_id") or [0, r["model"]])[1] for r in rows or []}
    return {"options": [{"relation": r["model"], "relation_label": names.get(r["model"]), "field": r["name"],
                         "field_label": r.get("field_description")} for r in rows or []][:120]}


class SmartActionBody(BaseModel):
    model: str
    relation: str
    field: str
    label: str = Field(min_length=1, max_length=80)
    with_count: bool = True


@router.post("/smart-button/action")
def smart_action(connection_id: str, body: SmartActionBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Make the list a smart button opens (a window action) and, if asked, a number
    field that counts it. Returns ids for the insert_element op."""
    client = _client(connection_id, db)
    model, rel = _check_model(body.model), _check_model(body.relation)
    rel_fields = _rich_fields(client, rel)
    meta = rel_fields.get(body.field) or {}
    if meta.get("type") != "many2one" or meta.get("relation") != model or not ve.FIELD_NAME_RE.match(body.field):
        raise HTTPException(status_code=422, detail="That field doesn't point to this record type.")
    created: dict[str, Any] = {}
    try:
        action_id = int(client.execute_kw("ir.actions.act_window", "create", [{
            "name": body.label, "res_model": rel, "view_mode": "list,form" if _major(client) >= 18 else "tree,form",
            "domain": f"[('{body.field}', '=', active_id)]", "context": f"{{'default_{body.field}': active_id}}",
        }]))
        created["action_id"] = action_id
        if body.with_count:
            fields = _rich_fields(client, model)
            name = lib.new_field_name(f"{body.label} count", fields)
            fid = int(client.execute_kw("ir.model.fields", "create", [{
                "name": name, "field_description": f"{body.label} count", "model_id": _model_id(client, model),
                "ttype": "integer", "state": "manual", "store": False,
                "compute": vp.count_compute(name, rel, body.field),
                "depends": "",
            }]))
            created.update({"count_field": name, "count_field_id": fid})
    except ODOO_ERRORS as exc:
        if created.get("action_id"):
            try:
                client.execute_kw("ir.actions.act_window", "unlink", [[created["action_id"]]])
            except ODOO_ERRORS:
                pass
        raise _odoo_error(exc) from exc
    return {"ok": True, **created}


class SmartUndoBody(BaseModel):
    action_id: int | None = None
    count_field_id: int | None = None


@router.post("/smart-button/undo")
def smart_undo(connection_id: str, body: SmartUndoBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    try:
        if body.count_field_id:
            rows = client.execute_kw("ir.model.fields", "read", [[int(body.count_field_id)]], {"fields": ["name", "state"]})
            if rows and rows[0]["name"].startswith("x_") and rows[0]["state"] == "manual":
                client.execute_kw("ir.model.fields", "unlink", [[int(body.count_field_id)]])
        if body.action_id:
            client.execute_kw("ir.actions.act_window", "unlink", [[int(body.action_id)]])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    return {"ok": True}
