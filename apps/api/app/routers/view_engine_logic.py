"""View Designer logic endpoints (Builders stage 2a).

Conditions, preview as a role or person, "Who can see it", access to the
record type, version side by side, history, comments, command bar, and the
report draft proof. AI proposes (view_engine_ai); everything that writes is
deterministic code and goes through the same checks as stage 1 publish.
"""

from __future__ import annotations

import base64
import json
import secrets
from typing import Any, Literal
from urllib import error, request
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import view_engine as ve
from app import view_engine_access as va
from app import view_engine_ai as vai
from app import view_engine_logic as vl
from app import view_engine_report as vr
from app import view_engine_store as vs
from app.db import get_db
from app.odoo_service import OdooClientError
from app.routers.view_engine import (
    ODOO_ERRORS,
    _annotate,
    _check_model,
    _client,
    _combined_raw,
    _compile_kwargs,
    _engine_error,
    _expected_for_user,
    _fields_get,
    _find_layer,
    _get_views,
    _major,
    _odoo_error,
    _record_names,
    _report_context,
    _stock_hashes,
    _vt,
)

router = APIRouter(prefix="/connections/{connection_id}/views/engine", tags=["view-engine"])
reports_router = APIRouter(prefix="/connections/{connection_id}/reports/engine", tags=["view-engine"])


class ScreenBody(BaseModel):
    model: str
    view_type: str = "form"
    view_id: int | None = None
    ops: list[dict[str, Any]] = Field(default_factory=list)


def _screen(client: Any, body: ScreenBody) -> tuple[str, str, dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    """(model, vt, view, fields, working_arch, tree) for the base screen plus pending ops."""
    model, vt = _check_model(body.model), _vt(body.view_type)
    view = _get_views(client, model, vt, body.view_id)
    fields = _fields_get(client, model)
    arch = view["arch"]
    if body.ops:
        try:
            arch = ve.compile_ops(arch, fields, body.ops, **_compile_kwargs(client, fields, body.ops, model)).expected_arch
        except ve.EngineError as exc:
            raise _engine_error(exc) from exc
    tree = ve.normalize(arch, fields).tree
    touched = {str(o.get("node")) for o in body.ops if isinstance(o, dict) and o.get("op") == "set_access"}
    _annotate(client, tree, fields, _combined_raw(client, view["id"]), skip_groups=touched)
    return model, vt, view, fields, arch, tree


def _walk(tree: dict[str, Any]):
    yield tree
    for c in tree.get("children") or []:
        yield from _walk(c)


def _model_label(client: Any, model: str) -> str:
    try:
        rows = client.execute_kw("ir.model", "search_read", [[("model", "=", model)]], {"fields": ["name"], "limit": 1})
        return str(rows[0]["name"]) if rows else model
    except OdooClientError:
        return model


# ----------------------------------------------------------------------------
# Conditions (SPEC 3.2)
# ----------------------------------------------------------------------------

class ValuesBody(BaseModel):
    model: str
    field: str
    query: str = ""


@router.post("/conditions/values")
def condition_values(connection_id: str, body: ValuesBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    fields = _fields_get(client, _check_model(body.model))
    meta = fields.get(body.field)
    if not meta:
        raise HTTPException(status_code=422, detail="That field isn't on this record type.")
    ftype = meta.get("type")
    out: dict[str, Any] = {"type": ftype, "ops": [{"op": o, "label": vl.OP_WORDS[o]} for o in vl.OPS_BY_TYPE.get(ftype, ())]}
    if ftype == "selection":
        full = client.execute_kw(body.model, "fields_get", [[body.field]], {"attributes": ["selection"]})
        out["values"] = [{"value": k, "label": lbl} for k, lbl in (full.get(body.field) or {}).get("selection") or []]
    elif ftype == "many2one" and meta.get("relation"):
        try:
            hits = client.execute_kw(meta["relation"], "name_search", [], {"name": body.query[:80], "limit": 40})
        except ODOO_ERRORS as exc:
            raise _odoo_error(exc) from exc
        out["values"] = [{"value": int(h[0]), "label": str(h[1])} for h in hits or []]
    return out


def _fields_with_selection(client: Any, model: str) -> dict[str, Any]:
    return client.execute_kw(model, "fields_get", [], {"attributes": ["string", "type", "relation", "selection", "required"]}) or {}


class CheckBody(BaseModel):
    model: str
    attr: str = "invisible"
    sense: Literal["show", "hide"] = "show"
    condition: dict[str, Any]


@router.post("/conditions/check")
def condition_check(connection_id: str, body: CheckBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Validate a rule built with the dropdowns and write its sentence in code."""
    client = _client(connection_id, db)
    fields = _fields_with_selection(client, _check_model(body.model))
    names = _record_names(client, fields, _ids_in_condition(body.condition, fields))
    try:
        clean = vl.validate_condition(body.condition, fields, record_names=names)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    sentence = vl.condition_sentence(clean, fields, names)
    return {
        "condition": clean, "sentence": sentence, "expression": vl.compile_condition(clean),
        "rule_sentence": vl.rule_sentence(body.attr, body.sense, sentence),
    }


def _ids_in_condition(cond: Any, fields: dict[str, Any]) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for r in (cond or {}).get("rules") or [] if isinstance(cond, dict) else []:
        if isinstance(r, dict) and (fields.get(str(r.get("field"))) or {}).get("type") == "many2one":
            vals = r.get("value") if isinstance(r.get("value"), list) else [r.get("value")]
            ids = {int(v) for v in vals if isinstance(v, int) and not isinstance(v, bool)}
            if ids:
                out.setdefault(str(r["field"]), set()).update(ids)
    return out


class WordsBody(BaseModel):
    model: str
    attr: str = "invisible"
    text: str


@router.post("/conditions/words")
def condition_from_words(connection_id: str, body: WordsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """'Show when Stage is Won' -> up to two readings, each validated and written back by code."""
    client = _client(connection_id, db)
    model = _check_model(body.model)
    fields = _fields_with_selection(client, model)

    def lookup(relation: str, name: str | None, ids: list[int] | None) -> list[tuple[int, str]]:
        try:
            if ids:
                rows = client.execute_kw(relation, "read", [ids], {"fields": ["display_name"]})
                return [(int(r["id"]), str(r["display_name"])) for r in rows or []]
            hits = client.execute_kw(relation, "name_search", [], {"name": name or "", "limit": 5})
            return [(int(h[0]), str(h[1])) for h in hits or []]
        except OdooClientError:
            return []

    values: dict[str, list[dict[str, Any]]] = {}
    for fname, meta in fields.items():
        if meta.get("type") == "many2one" and meta.get("relation"):
            try:
                if int(client.execute_kw(meta["relation"], "search_count", [[]])) <= 30:
                    hits = client.execute_kw(meta["relation"], "name_search", [], {"name": "", "limit": 30})
                    values[fname] = [{"value": int(h[0]), "label": str(h[1])} for h in hits or []]
            except OdooClientError:
                continue
    try:
        readings, unclear = vai.propose_condition(body.text, body.attr, fields, values, lookup)
    except vai.AIUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    for r in readings:
        r["rule_sentence"] = vl.rule_sentence(body.attr, r["sense"], r["sentence"])
    return {"readings": readings, "unclear": unclear}


# ----------------------------------------------------------------------------
# Roles, people, preview as
# ----------------------------------------------------------------------------

@router.post("/roles")
def list_roles(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    cat = va.group_catalog(client)
    users = va.users_with_groups(client, cat)
    roles = []
    for x, gid in cat.id_of.items():
        n = sum(1 for u in users if x in u["member_of"])
        roles.append({"xmlid": x, "id": gid, "name": cat.name(x), "people": n})
    roles.sort(key=lambda r: (-r["people"], r["name"]))
    return {"roles": roles, "admin_role": va.SYSTEM_GROUP, "based_on": "Based on group rules. Ingenium can't log in as another person."}


class PeopleBody(BaseModel):
    query: str = ""


@router.post("/people")
def search_people(connection_id: str, body: PeopleBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    q = body.query.strip()[:80]
    domain: list[Any] = [("share", "=", False)]
    if q:
        domain = ["&", ("share", "=", False), "|", ("name", "ilike", q), ("login", "ilike", q)]
    rows = client.execute_kw("res.users", "search_read", [domain], {"fields": ["id", "name", "login"], "limit": 10})
    return {"people": [{"id": int(r["id"]), "name": str(r["name"]), "login": str(r.get("login") or "")} for r in rows or []]}


class PreviewAsBody(ScreenBody):
    role: str | None = None
    user_id: int | None = None


@router.post("/preview-as")
def preview_as(connection_id: str, body: PreviewAsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Which items a role or a person sees on this screen and why. Evaluated from
    group rules in code (Odoo's own rule: comma list is OR, '!' is NOT)."""
    client = _client(connection_id, db)
    model, vt, view, fields, arch, tree = _screen(client, body)
    cat = va.group_catalog(client)
    who: dict[str, Any]
    if body.user_id:
        people = va.users_with_groups(client, cat, [int(body.user_id)])
        if not people:
            raise HTTPException(status_code=404, detail="That person isn't in this database.")
        member = people[0]["member_of"]
        who = {"kind": "person", "id": people[0]["id"], "name": people[0]["name"]}
    elif body.role:
        if body.role not in cat.id_of:
            raise HTTPException(status_code=404, detail="That role isn't in this database.")
        member = cat.member_of_role(body.role)
        who = {"kind": "role", "xmlid": body.role, "name": cat.name(body.role)}
    else:
        raise HTTPException(status_code=422, detail="Pick a role or a person.")
    fgroups = va.field_level_groups(client, model, cat)
    dev_kept = _major(client) >= 19
    vis = vl.visibility_for(tree, member, fgroups, cat.names(), dev_kept)
    limits = _screen_limits(client, model, int(view["id"]), member, cat)
    for nid, n in ((n["id"], n) for n in _walk(tree)):
        if n.get("tag") == "field" and n.get("name") in limits["hidden_fields"] and vis.get(nid, {}).get("visible"):
            vis[nid] = {"visible": False, "reason": f"Added by a part of this screen only {', '.join(limits['hidden_fields'][n['name']])} get."}
    # Items the Ingenium login can't see itself are missing from the tree; read
    # them from Odoo's full screen definition so nothing the role sees is left out.
    also_sees: list[dict[str, str]] = []
    raw = _combined_raw(client, view["id"])
    if raw:
        try:
            rarch = raw
            if body.ops:
                layer = ve.compile_ops(view["arch"], fields, body.ops, **_compile_kwargs(client, fields, body.ops, model)).arch
                rarch = ve.apply_inherit_local(raw, layer)
            rtree = ve.normalize(rarch, fields).tree
            rvis = vl.visibility_for(rtree, member, fgroups, cat.names(), dev_kept)
            known = {n.get("name") for n in _walk(tree) if n.get("tag") == "field"}
            seen: set[str] = set()
            for n in _walk(rtree):
                nm = n.get("name")
                if n.get("tag") == "field" and nm and nm not in known and nm not in seen and rvis.get(n["id"], {}).get("visible"):
                    seen.add(nm)
                    also_sees.append({"name": nm, "label": n.get("label") or nm})
        except ve.EngineError:
            also_sees = []
    perms = va.effective_perms(va.access_rows(client, model, cat), member)
    hidden = [nid for nid, v in vis.items() if not v["visible"]]
    hidden_fields = [nid for nid in hidden if nid.startswith("field:")]
    label = _model_label(client, model)
    if not perms["read"]:
        summary = f"{who['name']} can't open {label} at all."
    else:
        can = [va.PERM_WORDS[p] for p in va.PERMS if perms[p]]
        summary = f"{who['name']} can {', '.join(can[:-1]) + ' and ' + can[-1] if len(can) > 1 else can[0]} {label}."
        if hidden_fields:
            summary += f" {len(hidden_fields)} field{'s are' if len(hidden_fields) != 1 else ' is'} hidden for them on this screen."
        if not perms["write"]:
            summary += " Everything is read-only for them."
    if not limits["base_ok"]:
        summary += f" This screen is only for {', '.join(limits['base_for'])}; they see Odoo's other screen for this record type."
    if also_sees and perms["read"]:
        summary += f" They also see {len(also_sees)} item{'s' if len(also_sees) != 1 else ''} you don't: {', '.join(a['label'] for a in also_sees[:5])}."
    return {"who": who, "visibility": vis, "also_sees": also_sees, "perms": perms, "summary": summary,
            "read_only": not perms["write"], "based_on": "Based on group rules. Conditions that depend on the record are shown, not evaluated."}


def _screen_limits(client: Any, model: str, base_id: int, member: set[str], cat: va.GroupCatalog) -> dict[str, Any]:
    from app import view_engine_library as lib

    gfield = "group_ids" if va._has_field(client, "ir.ui.view", "group_ids") else "groups_id"
    try:
        rows = client.execute_kw("ir.ui.view", "search_read", [[("model", "=", model)]],
                                 {"fields": ["id", "inherit_id", "arch_db", gfield, "name"], "limit": 500})
    except ODOO_ERRORS:
        return {"hidden_fields": {}, "base_ok": True, "base_for": []}
    views = [{"id": r["id"], "inherit_id": (r.get("inherit_id") or [None])[0] if r.get("inherit_id") else None,
              "arch": r.get("arch_db") or "", "groups": r.get(gfield) or [], "name": r.get("name")} for r in rows or []]
    return lib.restricted_parts(views, base_id, member, cat.xmlid_of, cat.names())


# ----------------------------------------------------------------------------
# Who can see it: field level
# ----------------------------------------------------------------------------

class FieldAccessBody(ScreenBody):
    node: str
    edit: list[str] = Field(default_factory=list)
    see: list[str] = Field(default_factory=list)
    also: list[str] = Field(default_factory=list)  # other items changed together (multi-select)


def _used_elsewhere(raw_arch: str | None, fname: str) -> bool:
    """True when another element's settings (context, domain, rules...) read the field."""
    if not raw_arch:
        return False
    import re

    pat = re.compile(rf"(?<![\w.]){re.escape(fname)}(?![\w])")
    try:
        root = ve.parse_arch(raw_arch)
    except ve.EngineError:
        return False
    for el in root.iter():
        for k, val in el.attrib.items():
            if k in {"name", "string", "help", "placeholder", "class", "groups"}:
                continue
            if el.tag == "field" and el.get("name") == fname and k not in {"context", "domain"}:
                continue
            if pat.search(val or ""):
                return True
    return False


@router.post("/access/field-impact")
def field_access_impact(connection_id: str, body: FieldAccessBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, arch, tree = _screen(client, body)
    node = next((n for n in _walk(tree) if n["id"] == body.node), None)
    if node is None:
        raise HTTPException(status_code=404, detail="That item is no longer on this screen.")
    try:
        edit, see = vl.access_level_groups(body.edit, body.see)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    cat = va.group_catalog(client)
    unknown = [g for g in [*edit, *see] if g not in cat.id_of]
    if unknown:
        raise HTTPException(status_code=422, detail="A role you picked no longer exists in this database. Reload the roles.")
    users = va.users_with_groups(client, cat)
    rows = va.access_rows(client, model, cat)
    fname = node.get("name") if node.get("tag") == "field" else None
    meta = fields.get(fname or "") or {}
    required = bool(meta.get("required")) or (node.get("attrs") or {}).get("required") in {"1", "True"}
    has_default = False
    if required and fname:
        try:
            has_default = bool((client.execute_kw(model, "default_get", [[fname]]) or {}).get(fname))
        except OdooClientError:
            has_default = False
    result = va.field_access_impact(
        label=node.get("label") or fname or "this item", users=users,
        before_groups=(node.get("attrs") or {}).get("groups"), edit=edit, see=see,
        field_required=required, has_default=has_default,
        can_create_member=lambda member: va.effective_perms(rows, member)["create"],
        connection_uid=int(client.uid), cat=cat,
    )
    if fname:
        others = [n for n in _walk(tree) if n.get("tag") == "field" and n.get("name") == fname and n["id"] != body.node]
        limited = bool(edit or see)
        open_copies = [n for n in others if n["id"] not in set(body.also) and not (n.get("attrs") or {}).get("groups")]
        if limited and not open_copies and _major(client) == 17 and _used_elsewhere(_combined_raw(client, view["id"]), fname):
            label = node.get("label") or fname
            result["blocks"].append(
                f"On Odoo 17, other parts of this screen use {label}, so Odoo won't let it be limited to some roles. "
                "Use a show/hide rule instead, or keep one copy visible for everyone."
            )
            result["alternative"] = {"kind": "rule", "node": body.node, "attr": "invisible", "sense": "hide",
                                     "nodes": [body.node, *[n for n in body.also if n != body.node]],
                                     "label": "Use a show/hide rule instead"}
        others = [n for n in others if n["id"] not in set(body.also)]
        if others:
            label = node.get("label") or fname
            result["warnings"].append(
                f"{label} appears {len(others)} more time{'s' if len(others) != 1 else ''} on this screen. "
                "This change only covers this one, so people may still see the other copy. "
                "Select them all to change them together."
            )
            result["same_field_nodes"] = [n["id"] for n in others]
    result["op"] = {"op": "set_access", "node": body.node, "edit": edit, "see": see}
    return result


# ----------------------------------------------------------------------------
# Access to this record type (model level)
# ----------------------------------------------------------------------------

class ModelBody(BaseModel):
    model: str


def _guard_model(model: str) -> None:
    if va.PROTECTED_MODELS_RE.match(model):
        raise HTTPException(status_code=403, detail="Access to system record types can't be changed here. Use Odoo's settings.")


@router.post("/access/model")
def model_access(connection_id: str, body: ModelBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = _check_model(body.model)
    cat = va.group_catalog(client)
    rows = va.access_rows(client, model, cat)
    users = va.users_with_groups(client, cat)
    roles = sorted({r["group"] for r in rows if r.get("group")})
    by_role = []
    for g in roles:
        member = cat.member_of_role(g)
        by_role.append({"group": g, "name": cat.name(g), "perms": va.effective_perms(rows, member),
                        "people": sum(1 for u in users if g in u["member_of"])})
    everyone = next((r for r in rows if r.get("group") is None), None)
    return {
        "model": model, "label": _model_label(client, model), "rows": rows, "roles": by_role,
        "everyone": {p: bool(everyone and everyone[p]) for p in va.PERMS} if everyone else None,
        "rules": va.record_rules(client, model, cat), "editable": not va.PROTECTED_MODELS_RE.match(model),
        "rules_link": f"/connections/{connection_id}/access?model={quote(model)}",
    }


class ModelChangeBody(ModelBody):
    changes: list[dict[str, Any]]


def _plan(client: Any, body: ModelChangeBody) -> dict[str, Any]:
    model = _check_model(body.model)
    _guard_model(model)
    cat = va.group_catalog(client)
    rows = va.access_rows(client, model, cat)
    actions, blocks = va.model_access_plan(rows, body.changes, cat)
    if va.access_model_name(client) == "ir.access":
        for a in actions:
            if a["type"] == "create":
                dom, ok_ = va.grant_domain(rows, cat.member_of_role(a["group"]))
                if not ok_:
                    blocks.append(f"{cat.name(a['group'])} reaches these records through several rules with different limits. "
                                  "Change this one in Odoo's access settings so no records open up by mistake.")
                a["domain"] = dom
    after = va.apply_plan_to_rows(rows, actions)
    users = va.users_with_groups(client, cat)
    impact, more_blocks = va.model_access_impact(_model_label(client, model), users, rows, after, int(client.uid))
    return {"model": model, "cat": cat, "actions": actions, "impact": impact, "blocks": blocks + more_blocks}


@router.post("/access/model/preview")
def model_access_preview(connection_id: str, body: ModelChangeBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    plan = _plan(client, body)
    return {"impact": plan["impact"], "blocks": plan["blocks"], "actions": len(plan["actions"])}


@router.post("/access/model/apply")
def model_access_apply(connection_id: str, body: ModelChangeBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    plan = _plan(client, body)
    if plan["blocks"]:
        raise HTTPException(status_code=409, detail={"message": "Nothing was changed.", "blocks": plan["blocks"]})
    if not plan["actions"]:
        return {"ok": True, "impact": plan["impact"], "undo": []}
    model = plan["model"]
    backend = va.access_model_name(client)
    undo: list[dict[str, Any]] = []
    model_id = client.execute_kw("ir.model", "search", [[("model", "=", model)]], {"limit": 1})
    try:
        for a in plan["actions"]:
            if a["type"] == "deactivate":
                client.execute_kw(backend, "write", [[a["id"]], {"active": False}])
                undo.append({"type": "activate", "id": a["id"]})
            elif a["type"] == "write":
                before = va.read_row_perms(client, backend, a["id"])
                client.execute_kw(backend, "write", [[a["id"]], va.row_values(backend, a.get("perms") or {})])
                undo.append({"type": "write", "id": a["id"], "perms": before})
            elif a["type"] == "create":
                vals: dict[str, Any] = {"name": f"ingenium_access {model} {a['group']}", "model_id": model_id[0], "group_id": a["group_id"]}
                if backend == "ir.access":
                    vals.update({"kind": "permission", "operation": va.perms_to_operation(a.get("perms") or {})})
                    if a.get("domain"):
                        vals["domain"] = a["domain"]
                else:
                    vals.update(va.row_values(backend, a.get("perms") or {}))
                new_id = client.execute_kw(backend, "create", [vals])
                undo.append({"type": "delete", "id": int(new_id)})
    except ODOO_ERRORS as exc:
        _undo_access(client, model, list(reversed(undo)))
        raise _odoo_error(exc) from exc
    return {"ok": True, "impact": plan["impact"], "undo": list(reversed(undo))}


def _undo_access(client: Any, model: str, undo: list[dict[str, Any]]) -> None:
    backend = va.access_model_name(client)
    for u in undo:
        rid = int(u.get("id") or 0)
        rows = client.execute_kw(backend, "search_read", [[("id", "=", rid)]],
                                 {"fields": ["name", "model_id"], "context": {"active_test": False}})
        if not rows:
            continue
        rmodel = client.execute_kw("ir.model", "read", [[rows[0]["model_id"][0]]], {"fields": ["model"]})[0]["model"]
        if rmodel != model:
            raise HTTPException(status_code=403, detail="That undo belongs to another record type.")
        if u["type"] == "activate":
            client.execute_kw(backend, "write", [[rid], {"active": True}])
        elif u["type"] == "write":
            client.execute_kw(backend, "write", [[rid], va.row_values(backend, u.get("perms") or {})])
        elif u["type"] == "delete":
            if not str(rows[0]["name"]).startswith("ingenium_access"):
                raise HTTPException(status_code=403, detail="Only access rows made in Ingenium can be removed here.")
            client.execute_kw(backend, "unlink", [[rid]])


class ModelUndoBody(ModelBody):
    undo: list[dict[str, Any]]


@router.post("/access/model/undo")
def model_access_undo(connection_id: str, body: ModelUndoBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = _check_model(body.model)
    _guard_model(model)
    try:
        _undo_access(client, model, body.undo[:20])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    return {"ok": True}


# ----------------------------------------------------------------------------
# Versions side by side (stock catalogue per Odoo major)
# ----------------------------------------------------------------------------

@router.post("/versions")
def compare_versions(connection_id: str, body: ScreenBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    current = _major(client)
    used = vl.ops_fields(body.ops)
    out = []
    for v in vl.catalog_versions():
        cat = vl.load_catalog(v) or {}
        entry = (cat.get("views") or {}).get(f"{model}:{vt}")
        cfields = (cat.get("fields") or {}).get(model) or {}
        row: dict[str, Any] = {"version": v, "current": v == current, "flags": [], "tree": None,
                               "source": cat.get("source", f"Standard Odoo {v}")}
        if not entry:
            row["available"] = False
            row["flags"].append(f"No standard copy of this screen for Odoo {v}, so it can't be checked.")
            out.append(row)
            continue
        row["available"] = True
        missing = sorted(f for f in used if f not in cfields)
        for f in missing:
            row["flags"].append(f"This won't work on Odoo {v}: the field '{f}' isn't there.")
        arch = entry["arch"]
        if body.ops and not missing:
            try:
                arch = ve.compile_ops(arch, cfields, body.ops).expected_arch
            except ve.EngineError as exc:
                row["flags"].append(f"This won't work on Odoo {v}: {exc}")
        try:
            row["tree"] = ve.normalize(arch, cfields).tree
        except ve.EngineError:
            row["tree"] = None
        out.append(row)
    return {"current": current, "versions": out}


# ----------------------------------------------------------------------------
# History: named versions, compare, restore, scrubber
# ----------------------------------------------------------------------------

class HistoryBody(BaseModel):
    model: str
    view_type: str = "form"


def _layer_name_for(client: Any, model: str, vt: str) -> tuple[str, dict[str, Any]]:
    view = _get_views(client, model, vt)
    # The base view id is the root of the combined screen; the layer is keyed on it.
    return ve.layer_name(model, vt, view["id"]), view


@router.post("/history/list")
def history_list(connection_id: str, body: HistoryBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    name, _view = _layer_name_for(client, model, vt)
    rows = vs.list_versions(db, connection_id, name)
    return {"versions": [vs.version_out(r) for r in rows]}


class NameBody(BaseModel):
    version_id: str
    label: str


@router.post("/history/name")
def history_name(connection_id: str, body: NameBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = vs.get_version(db, connection_id, body.version_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That version isn't in the history.")
    vs.name_version(db, row, body.label)
    return vs.version_out(row)


class VersionBody(BaseModel):
    version_id: str


@router.post("/history/tree")
def history_tree(connection_id: str, body: VersionBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    row = vs.get_version(db, connection_id, body.version_id)
    if row is None or not row.combined_arch:
        raise HTTPException(status_code=404, detail="That version isn't in the history.")
    fields = _fields_get(client, row.model)
    tree = ve.normalize(row.combined_arch, fields).tree
    _annotate(client, tree, fields)
    return {"version": vs.version_out(row), "tree": tree}


class CompareBody(BaseModel):
    model: str
    view_type: str = "form"
    from_id: str
    to_id: str = "current"


@router.post("/history/compare")
def history_compare(connection_id: str, body: CompareBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    fields = _fields_get(client, model)

    def arch_of(vid: str) -> str:
        if vid == "current":
            return _get_views(client, model, vt)["arch"]
        row = vs.get_version(db, connection_id, vid)
        if row is None or not row.combined_arch:
            raise HTTPException(status_code=404, detail="That version isn't in the history.")
        return row.combined_arch

    old = ve.normalize(arch_of(body.from_id), fields).tree
    new = ve.normalize(arch_of(body.to_id), fields).tree
    diff = vl.compare_trees(old, new)
    return {"from_tree": old, "to_tree": new, **diff}


@router.post("/history/restore")
def history_restore(connection_id: str, body: VersionBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Put a past version back through the same checks as publish."""
    client = _client(connection_id, db)
    row = vs.get_version(db, connection_id, body.version_id)
    if row is None or row.kind != "view":
        raise HTTPException(status_code=404, detail="That version isn't in the history.")
    model, vt = row.model, row.view_type
    fields = _fields_get(client, model)
    existing = _find_layer(client, row.layer_name)
    prev_arch = str(existing.get("arch") or "") if existing else None
    prev_active = bool(existing.get("active")) if existing else False
    stock_before = _stock_hashes(client, model)
    layer_id = int(existing["id"]) if existing else None

    def put_back() -> None:
        if layer_id is None:
            return
        try:
            if prev_arch is not None:
                client.execute_kw("ir.ui.view", "write", [[layer_id], {"arch": prev_arch, "active": prev_active}])
        except OdooClientError:
            pass

    try:
        if layer_id is not None and prev_active:
            client.execute_kw("ir.ui.view", "write", [[layer_id], {"active": False}])
        base = _get_views(client, model, vt)
        if not row.layer_arch or not row.layer_active:
            expected = base["arch"]
        else:
            expected = ve.apply_inherit_local(base["arch"], row.layer_arch)
            if layer_id is None:
                layer_id = int(client.execute_kw("ir.ui.view", "create", [{
                    "name": row.layer_name, "model": model, "type": vt if vt != "list" or _major(client) >= 18 else "tree",
                    "inherit_id": base["id"], "mode": "extension", "priority": ve.LAYER_PRIORITY,
                    "arch": row.layer_arch, "active": False,
                }]))
            client.execute_kw("ir.ui.view", "write", [[layer_id], {"arch": row.layer_arch, "active": False}])
            client.execute_kw("ir.ui.view", "write", [[layer_id], {"active": True}])
    except ve.EngineError as exc:
        put_back()
        raise HTTPException(status_code=409, detail=f"That version no longer fits Odoo's current screen: {exc}") from exc
    except ODOO_ERRORS as exc:
        put_back()
        raise _odoo_error(exc) from exc
    after = _get_views(client, model, vt)
    diffs = ve.diff_signatures(
        ve.signature(ve.normalize(_expected_for_user(client, expected), fields).tree),
        ve.signature(ve.normalize(after["arch"], fields).tree),
    )
    stock_ok = stock_before == _stock_hashes(client, model)
    if diffs or not stock_ok:
        put_back()
        raise HTTPException(status_code=409, detail={"message": "Odoo shows that version differently, so nothing changed.",
                                                     "differences": diffs[:10], "stock_unchanged": stock_ok})
    new_id = vs.record_version(
        db, connection_id=connection_id, kind="view", model=model, view_type=vt, layer_name=row.layer_name,
        layer_view_id=layer_id, action="restore",
        summary=[f"Restored {row.label or 'a version from ' + (row.created_at.isoformat()[:16] if row.created_at else 'earlier')}"],
        layer_arch=row.layer_arch if row.layer_active else prev_arch, layer_active=bool(row.layer_arch and row.layer_active),
        combined_arch=after["arch"], odoo_major=_major(client),
    )
    return {"ok": True, "version_id": new_id, "layer_view_id": layer_id, "previous_arch": prev_arch,
            "previous_active": prev_active, "arch_hash_after": ve.arch_hash(after["arch"]), "stock_unchanged": stock_ok}


# ----------------------------------------------------------------------------
# Comments pinned to fields (Ingenium DB only)
# ----------------------------------------------------------------------------

class CommentListBody(BaseModel):
    model: str
    view_type: str = "form"


@router.post("/comments/list")
def comments_list(connection_id: str, body: CommentListBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    model, vt = _check_model(body.model), _vt(body.view_type)
    return {"comments": [vs.comment_out(r) for r in vs.list_comments(db, connection_id, model, vt)]}


class CommentAddBody(CommentListBody):
    node_id: str
    body: str
    parent_id: str | None = None
    author: str | None = None


@router.post("/comments/add")
def comments_add(connection_id: str, body: CommentAddBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    model, vt = _check_model(body.model), _vt(body.view_type)
    text = body.body.strip()
    if not text or len(text) > 2000:
        raise HTTPException(status_code=422, detail="Comments need 1 to 2,000 characters.")
    if not body.node_id or len(body.node_id) > 255:
        raise HTTPException(status_code=422, detail="Pick something on the screen to pin the comment to.")
    if body.parent_id and vs.get_comment(db, connection_id, body.parent_id) is None:
        raise HTTPException(status_code=404, detail="That comment thread was deleted.")
    row = vs.add_comment(db, connection_id=connection_id, model=model, view_type=vt, node_id=body.node_id,
                         parent_id=body.parent_id, author=(body.author or "You").strip()[:120] or "You", body=text)
    return vs.comment_out(row)


class CommentStateBody(BaseModel):
    id: str
    resolved: bool = True


@router.post("/comments/resolve")
def comments_resolve(connection_id: str, body: CommentStateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = vs.get_comment(db, connection_id, body.id)
    if row is None:
        raise HTTPException(status_code=404, detail="That comment was deleted.")
    vs.set_resolved(db, row, body.resolved)
    return vs.comment_out(row)


class CommentIdBody(BaseModel):
    id: str


@router.post("/comments/delete")
def comments_delete(connection_id: str, body: CommentIdBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = vs.get_comment(db, connection_id, body.id)
    if row is None:
        raise HTTPException(status_code=404, detail="That comment was already deleted.")
    vs.delete_comment(db, row)
    return {"ok": True}


# ----------------------------------------------------------------------------
# Command bar: plain-English edit (SPEC 3.1). AI proposes, code authorizes.
# ----------------------------------------------------------------------------

class CommandBody(ScreenBody):
    text: str


def _describe(op: dict[str, Any], by_id: dict[str, dict[str, Any]], fields: dict[str, Any]) -> str:
    def nm(nid: Any) -> str:
        n = by_id.get(str(nid)) or {}
        return n.get("label") or n.get("tag") or str(nid)

    kind = op.get("op")
    if kind == "move":
        return f"Move {nm(op.get('node'))} {'into' if op.get('position') == 'inside' else op.get('position')} {nm(op.get('target'))}"
    if kind == "insert_field":
        return f"Add {(fields.get(op.get('field')) or {}).get('string') or op.get('field')} {'into' if op.get('position') == 'inside' else op.get('position')} {nm(op.get('target'))}"
    if kind == "hide":
        return f"Hide {nm(op.get('node'))}"
    if kind == "set_attr":
        if op.get("attr") == "string":
            return f"Rename {nm(op.get('node'))} to {op.get('value')}"
        return f"Change {nm(op.get('node'))}"
    if kind == "wrap":
        return f"Put {len(op.get('nodes') or [])} items in a new {'tab' if op.get('kind') == 'page' else op.get('kind')}"
    if kind == "set_condition":
        return f"Change when {nm(op.get('node'))} shows"
    return "Change the screen"


@router.post("/command")
def command(connection_id: str, body: CommandBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, arch, tree = _screen(client, body)
    by_id = {n["id"]: n for n in _walk(tree)}
    from app.ai_client.ai_scope import ai_scope

    cat = va.group_catalog(client)
    groups = [{"id": x, "name": n} for x, n in sorted(cat.names().items())][:300]
    choices: list[str] = []
    try:
        with ai_scope(reads=("ir.ui.view", "ir.model.fields", "res.groups")):
            ops, unclear = vai.propose_edit(body.text, tree, fields, groups, choices)
        check_ai_groups(ops, by_id, cat)
    except vai.AIUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ve.EngineError as exc:
        return {"ops": [], "unclear": str(exc), "descriptions": [], "markers": {}, "choices": []}
    if not ops:
        return {"ops": [], "unclear": unclear, "descriptions": [], "markers": {}, "choices": choices}
    try:
        result = ve.compile_ops(view["arch"], fields, [*body.ops, *ops], **_compile_kwargs(client, fields, [*body.ops, *ops], model))
    except ve.EngineError as exc:
        return {"ops": [], "unclear": f"That change can't be made safely: {exc}", "descriptions": [], "markers": {}}
    new_tree = ve.normalize(result.expected_arch, fields).tree
    diff = vl.compare_trees(tree, new_tree)
    return {"ops": ops, "unclear": unclear, "descriptions": merge_descriptions([_describe(o, by_id, fields) for o in ops]),
            "op_descriptions": [_describe(o, by_id, fields) for o in ops], "markers": diff["markers"], "expected_tree": new_tree, "choices": []}


INNER_TAGS = frozenset({"field", "button", "group", "page", "div", "label", "separator"})


def check_ai_groups(ops: list[dict[str, Any]], by_id: dict[str, dict[str, Any]], cat: Any) -> None:
    """Groups from a sentence: only on inner elements, only roles that exist on this database."""
    for op in ops:
        if op.get("op") != "set_attr" or op.get("attr") != "groups":
            continue
        node = by_id.get(str(op.get("node"))) or {}
        if node.get("tag") not in INNER_TAGS:
            raise ve.EngineError("Who-can-see rules go on a field or button, not on the whole screen. Nothing was changed.")
        for x in [g.strip().lstrip("!") for g in str(op.get("value") or "").split(",") if g.strip()]:
            if x not in cat.id_of:
                raise ve.EngineError(f"The assistant named a role that doesn't exist here ({x}). Nothing was changed.")


def merge_descriptions(items: list[str]) -> list[str]:
    """'Hide Phone' twice becomes 'Hide Phone (2 copies)'; order kept."""
    counts: dict[str, int] = {}
    for d in items:
        counts[d] = counts.get(d, 0) + 1
    out: list[str] = []
    for d in items:
        if d in counts and counts[d] > 0:
            out.append(f"{d} ({counts[d]} copies)" if counts[d] > 1 else d)
            counts[d] = 0
    return out


# ----------------------------------------------------------------------------
# Report draft proof: the real PDF of unpublished blocks, visible only to this request
# ----------------------------------------------------------------------------

class DraftBody(BaseModel):
    report_id: int
    record_id: int
    slot: str = "bottom"
    blocks: list[dict[str, Any]] = Field(default_factory=list)


def _print_companies(client: Any, model: str, record_id: int, wanted: list[int] | None) -> list[int] | None:
    """Companies to print with: the record's own company first (Odoo refuses a record from a company
    the print isn't allowed in), then the user's other companies. None when the record has no company."""
    try:
        rows = client.execute_kw(model, "read", [[int(record_id)], ["company_id"]])
    except (OdooClientError, *ODOO_ERRORS):
        return wanted
    rec_co = (rows[0].get("company_id") or [None])[0] if rows and isinstance(rows[0].get("company_id"), list) else None
    try:
        mine = client.execute_kw("res.users", "read", [[int(client.uid)], ["company_ids"]])[0].get("company_ids") or []
    except (OdooClientError, *ODOO_ERRORS):
        mine = []
    first = [int(c) for c in (wanted or ([rec_co] if rec_co else []))]
    if rec_co and rec_co not in first:
        raise HTTPException(status_code=422, detail="That record belongs to another company. Pick a record from the company you want to preview.")
    if mine and any(c not in mine for c in first):
        raise HTTPException(status_code=403, detail="You don't have access to that company in Odoo.")
    if not first:
        return None
    return first + [int(c) for c in mine if int(c) not in first]


def _report_http(client: Any, kind: str, report_name: str, record_id: int, ctx: dict[str, Any], model: str | None = None) -> bytes:
    from odoo_client.report_render import _session_opener

    if model:
        cids = _print_companies(client, model, record_id, ctx.get("allowed_company_ids"))
        if cids:
            ctx = {**ctx, "allowed_company_ids": cids}
    url = (f"{client.config.url}/report/{kind}/{quote(report_name, safe='.')}/{int(record_id)}"
           f"?context={quote(json.dumps(ctx))}")
    try:
        with _session_opener(client).open(request.Request(url, method="GET"), timeout=client.config.timeout) as resp:
            return resp.read()
    except error.HTTPError as exc:
        reason = _odoo_print_reason(exc)
        if reason:
            raise HTTPException(status_code=422, detail=f"Odoo can't print this record: {reason}") from exc
        raise HTTPException(status_code=502, detail=f"Odoo couldn't print the draft: {exc}") from exc
    except (error.URLError, OdooClientError) as exc:
        raise HTTPException(status_code=502, detail=f"Odoo couldn't print the draft: {exc}") from exc


def _odoo_print_reason(exc: Any) -> str | None:
    """Odoo's own message from its error page (e.g. "Only invoices could be printed."), as plain text."""
    import html as _html
    import re

    try:
        body = exc.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None
    m = re.search(r'"message":\s*"((?:[^"\\]|\\.){1,400})"', body) or re.search(r"<pre[^>]*>(.{1,400}?)</pre>", body, re.S)
    if not m:
        return None
    text = re.sub(r"<[^>]+>", " ", _html.unescape(m.group(1).replace("\\n", " ")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:300] or None


@reports_router.post("/draft")
def report_draft(connection_id: str, body: DraftBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Draft layer shown only when this request's token is in the context; the
    published layer is hidden for that request; the draft is removed afterwards."""
    client = _client(connection_id, db)
    ctx = _report_context(client, body.report_id)
    slot = next((s for s in ctx["slots"] if s["id"] == body.slot), None)
    if slot is None:
        raise HTTPException(status_code=422, detail="That place isn't available on this print layout.")
    fields = _fields_get(client, str(ctx["report"]["model"]))
    var = ctx["record_var"]
    token = secrets.token_hex(8)
    try:
        blocks = vr.validate_blocks(body.blocks, fields) if body.blocks else []
        arch = vr.compile_report_draft(slot, blocks, var, token,
                                       hide_published=bool((_find_layer(client, vr.report_layer_name(ctx["document"]["key"])) or {}).get("active")))
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"That content isn't allowed in a print layout: {exc}") from exc
    doc_id = int(ctx["document"]["view_id"])
    draft_id: int | None = None
    try:
        draft_id = int(client.execute_kw("ir.ui.view", "create", [{
            "name": f"{ve.LAYER_PREFIX} draft {ctx['document']['key']} {token}", "type": "qweb", "inherit_id": doc_id,
            "mode": "extension", "priority": ve.LAYER_PRIORITY + 5, "arch": arch, "active": True,
        }]))
        rctx = {"ingenium_draft": token}
        pdf = _report_http(client, "pdf", str(ctx["report"]["report_name"]), body.record_id, rctx, str(ctx["report"]["model"]))
        html = _report_http(client, "html", str(ctx["report"]["report_name"]), body.record_id, rctx, str(ctx["report"]["model"])).decode("utf-8", "replace")
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    finally:
        if draft_id:
            try:
                client.execute_kw("ir.ui.view", "unlink", [[draft_id]])
            except OdooClientError:
                pass
    if not pdf.startswith(b"%PDF"):
        raise HTTPException(status_code=502, detail="Odoo didn't return a PDF for the draft. Check the record can be printed.")
    missing = [t for t in vr.expected_texts(blocks) if t not in html]
    return {"ok": not missing, "pages": vr.pdf_page_count(pdf), "missing": missing,
            "content_base64": base64.b64encode(pdf).decode("ascii")}
