"""Shared view engine endpoints (Builders stage 1).

Views:   load / records / compile / publish / revert
Reports: load / proof / publish / revert

Everything that writes is deterministic code: ops are validated and compiled
here; the stock views are never written; every publish is checked against what
Odoo itself returns afterwards.
"""

from __future__ import annotations

import base64
import re
import xmlrpc.client
from typing import Any, Literal
from urllib import error, request
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from odoo_client.xpath_locator import blocking_issues, classify_xpath_arch
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import view_engine as ve
from app import view_engine_access as va
from app import view_engine_logic as vl
from app import view_engine_report as vr
from app import view_engine_store as vs
from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404

router = APIRouter(prefix="/connections/{connection_id}/views/engine", tags=["view-engine"])
reports_router = APIRouter(prefix="/connections/{connection_id}/reports/engine", tags=["view-engine"])

FIELD_ATTRS = ["string", "type", "required", "readonly", "relation", "selection", "store"]
MODEL_RE = re.compile(r"^[a-z_][a-z0-9_.]{1,127}$")


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def _client(connection_id: str, db: Session) -> Any:
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except ODOO_ERRORS as exc:
        raise HTTPException(status_code=502, detail=f"Can't reach Odoo: {exc}") from exc


def _major(client: Any) -> int:
    try:
        return int(client.capabilities.major)
    except Exception:  # noqa: BLE001
        return 0


# Some Odoo refusals arrive as raw XML-RPC faults rather than client errors.
ODOO_ERRORS = (OdooClientError, xmlrpc.client.Fault)

_RESTRICTED_RE = re.compile(r"Field '([^']+)' used in .* is restricted to the group", re.S)


def _odoo_error(exc: Exception) -> HTTPException:
    raw = str(getattr(exc, "faultString", "") or exc)
    m = _RESTRICTED_RE.search(raw)
    if m:
        return HTTPException(status_code=409, detail=(
            f"Odoo needs '{m.group(1)}' for other parts of this screen, so it can't be limited to some roles here. "
            "Nothing was published. Use a show/hide rule instead, or keep one copy visible for everyone."))
    text = raw.strip().splitlines()
    first = next((ln for ln in reversed(text) if ln.strip()), "") if text else ""
    return HTTPException(status_code=400, detail=f"Odoo refused the change: {first[:400]}")


def _engine_error(exc: ve.EngineError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


def _vt(view_type: str) -> str:
    vt = "list" if view_type == "tree" else view_type
    if vt not in {"form", "list", "kanban", "search", "calendar"}:
        raise HTTPException(status_code=422, detail="Choose a form, list, card, search or calendar screen.")
    return vt


def _check_model(model: str) -> str:
    if not MODEL_RE.match(model or ""):
        raise HTTPException(status_code=422, detail="That record type name isn't valid.")
    return model


def _get_views(client: Any, model: str, vt: str, view_id: int | None = None) -> dict[str, Any]:
    try:
        result = client.execute_kw(model, "get_views", [], {"views": [[int(view_id) if view_id else False, vt]], "options": {"toolbar": False}})
    except ODOO_ERRORS as exc:
        raise HTTPException(status_code=404, detail=f"Odoo has no {vt} screen for {model}: {exc}") from exc
    views = (result or {}).get("views") or {}
    bucket = views.get(vt) or {}
    arch = bucket.get("arch")
    if not isinstance(arch, str) or not arch.strip():
        raise HTTPException(status_code=404, detail=f"Odoo has no {vt} screen for {model}.")
    return {"arch": arch, "id": int(bucket.get("id") or 0)}


def _fields_get(client: Any, model: str) -> dict[str, Any]:
    try:
        return client.execute_kw(model, "fields_get", [], {"attributes": FIELD_ATTRS}) or {}
    except ODOO_ERRORS as exc:
        raise HTTPException(status_code=404, detail=f"Odoo doesn't know the record type {model}: {exc}") from exc


def _find_layer(client: Any, name: str) -> dict[str, Any] | None:
    rows = client.execute_kw(
        "ir.ui.view",
        "search_read",
        [[("name", "=", name)]],
        {"fields": ["id", "arch", "active", "inherit_id", "priority"], "limit": 1, "context": {"active_test": False}},
    )
    return rows[0] if rows else None


def _stock_hashes(client: Any, model: str) -> dict[int, str]:
    rows = client.execute_kw(
        "ir.ui.view",
        "search_read",
        [[("model", "=", model), ("name", "not ilike", ve.LAYER_PREFIX)]],
        {"fields": ["id", "arch"], "context": {"active_test": False}},
    )
    return {int(r["id"]): ve.arch_hash(str(r.get("arch") or "")) for r in rows}


def _view_hash(client: Any, view_id: int) -> str:
    rows = client.execute_kw("ir.ui.view", "read", [[int(view_id)]], {"fields": ["arch"]})
    return ve.arch_hash(str((rows or [{}])[0].get("arch") or ""))


def _slim_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        k: {a: v.get(a) for a in ("string", "type", "required", "readonly", "relation", "store") if a in v}
        for k, v in fields.items()
    }


def _combined_raw(client: Any, view_id: int) -> str | None:
    """Combined arch before Odoo strips ``groups`` for the logged-in user."""
    try:
        arch = client.execute_kw("ir.ui.view", "get_combined_arch", [[int(view_id)]])
        return arch if isinstance(arch, str) and arch.strip() else None
    except Exception:  # noqa: BLE001
        return None


def _record_names(client: Any, fields: dict[str, Any], ids_by_field: dict[str, set[int]]) -> dict[str, dict[int, str]]:
    out: dict[str, dict[int, str]] = {}
    for fname, ids in ids_by_field.items():
        rel = (fields.get(fname) or {}).get("relation")
        if not rel or not ids:
            continue
        try:
            rows = client.execute_kw(rel, "read", [sorted(ids)[:100]], {"fields": ["display_name"]})
        except Exception:  # noqa: BLE001
            continue
        out[fname] = {int(r["id"]): str(r.get("display_name") or "") for r in rows or []}
    return out


def _ops_m2o_ids(ops: list[dict[str, Any]], fields: dict[str, Any]) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for op in ops or []:
        cond = op.get("condition") if isinstance(op, dict) else None
        if not isinstance(cond, dict):
            continue
        for r in cond.get("rules") or []:
            if not isinstance(r, dict):
                continue
            f = str(r.get("field") or "")
            if (fields.get(f) or {}).get("type") != "many2one":
                continue
            vals = r.get("value") if isinstance(r.get("value"), list) else [r.get("value")]
            for v in vals:
                if isinstance(v, int) and not isinstance(v, bool):
                    out.setdefault(f, set()).add(int(v))
    return out


def _annotate(
    client: Any, tree: dict[str, Any], fields: dict[str, Any], raw_arch: str | None = None,
    skip_groups: set[str] | None = None,
) -> dict[str, Any]:
    """Add plain 'why' sentences for rules, and ``groups`` read from the raw
    combined arch, to every node. Mutates and returns the tree."""
    raw_groups: dict[str, str] = {}
    if raw_arch:
        try:
            raw = ve.normalize(raw_arch, fields)
            raw_groups = {nid: n["attrs"]["groups"] for nid, n in raw.by_id.items() if (n.get("attrs") or {}).get("groups")}
        except ve.EngineError:
            raw_groups = {}
    ids: dict[str, set[int]] = {}
    nodes: list[dict[str, Any]] = []

    def walk(n: dict[str, Any]) -> None:
        nodes.append(n)
        for attr in vl.RULE_ATTRS:
            expr = (n.get("attrs") or {}).get(attr)
            if expr:
                for f, xs in vl.expression_m2o_ids(expr, fields).items():
                    ids.setdefault(f, set()).update(xs)
        for c in n.get("children") or []:
            walk(c)

    walk(tree)
    names = _record_names(client, fields, ids) if ids else {}
    for n in nodes:
        if n["id"] in raw_groups and "groups" not in n["attrs"] and n["id"] not in (skip_groups or set()):
            n["attrs"]["groups"] = raw_groups[n["id"]]
        rules: dict[str, str] = {}
        for attr in vl.RULE_ATTRS:
            expr = (n.get("attrs") or {}).get(attr)
            if expr:
                sentence = vl.why_sentence(attr, expr, fields, names)
                rules[attr] = sentence or "Odoo uses a rule here that's too complex to put in words. Turn on Show code to see it."
        if rules:
            n["rules"] = rules
    return tree


def _connection_member_of(client: Any, cat: va.GroupCatalog | None = None) -> set[str]:
    cat = cat or va.group_catalog(client)
    me = va.users_with_groups(client, cat, [int(client.uid)])
    return me[0]["member_of"] if me else set()


def _button_methods(client: Any, model: str) -> set[str]:
    """Methods this record type already offers as buttons in its stock screens."""
    try:
        rows = client.execute_kw("ir.ui.view", "search_read", [[("model", "=", model), ("name", "not ilike", ve.LAYER_PREFIX)]],
                                 {"fields": ["arch_db"], "limit": 400})
    except ODOO_ERRORS:
        return set()
    out: set[str] = set()
    for r in rows or []:
        for m in re.finditer(r"<button\b[^>]*>", str(r.get("arch_db") or "")):
            tag = m.group(0)
            if re.search(r'type="object"', tag):
                nm = re.search(r'\bname="([a-z][a-z0-9_]*)"', tag)
                if nm:
                    out.add(nm.group(1))
    return out


def _known_actions(client: Any, ids: set[int]) -> set[int]:
    found: set[int] = set()
    for model in ("ir.actions.act_window", "ir.actions.server", "ir.actions.report"):
        if not ids - found:
            break
        try:
            found |= {int(r["id"]) for r in client.execute_kw(model, "search_read", [[("id", "in", sorted(ids - found))]], {"fields": ["id"]})}
        except ODOO_ERRORS:
            continue
    return found


def _compile_kwargs(client: Any, fields: dict[str, Any], ops: list[dict[str, Any]], model: str | None = None) -> dict[str, Any]:
    kw: dict[str, Any] = {"major": _major(client)}
    els = [o for o in ops or [] if isinstance(o, dict) and o.get("op") == "insert_element"]
    if els:
        ids = {int(o["props"]["action_id"]) for o in els if isinstance(o.get("props"), dict)
               and isinstance(o["props"].get("action_id"), int) and not isinstance(o["props"].get("action_id"), bool)}
        kw["actions"] = _known_actions(client, ids) if ids else set()
        if model and any(isinstance(o.get("props"), dict) and o["props"].get("method") for o in els):
            kw["methods"] = _button_methods(client, model)
    ids = _ops_m2o_ids(ops, fields)
    if ids:
        kw["record_names"] = _record_names(client, fields, ids)
    if any(isinstance(o, dict) and o.get("op") == "set_access" for o in ops or []):
        kw["known_groups"] = set(va.group_catalog(client).id_of)
    return kw


def _expected_for_user(client: Any, expected_arch: str) -> str:
    """What get_views will show the Ingenium login: group-restricted nodes pruned."""
    if "groups=" not in expected_arch:
        return expected_arch
    import xml.etree.ElementTree as ET

    root = ve.parse_arch(expected_arch)
    vl.prune_for(root, _connection_member_of(client), _major(client) >= 19)
    return ET.tostring(root, encoding="unicode")


# ----------------------------------------------------------------------------
# Views
# ----------------------------------------------------------------------------

class LoadBody(BaseModel):
    model: str
    view_type: str = "form"
    view_id: int | None = None  # a specific screen (e.g. one made in Ingenium); default screen otherwise


class OpsBody(LoadBody):
    ops: list[dict[str, Any]] = Field(default_factory=list)
    summary: list[str] | None = None
    base_layer_hash: str | None = None  # layer as it was when this editor loaded; guards silent overwrites


class RecordsBody(LoadBody):
    limit: int = 80


class RevertBody(LoadBody):
    layer_view_id: int
    mode: Literal["deactivate", "restore", "remove"] = "deactivate"
    restore_arch: str | None = None


def _layer_info(client: Any, model: str, vt: str, base_id: int) -> dict[str, Any] | None:
    row = _find_layer(client, ve.layer_name(model, vt, base_id))
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "active": bool(row.get("active")),
        "steps": ve.count_layer_steps(str(row.get("arch") or "")),
        "arch": str(row.get("arch") or ""),
    }


def _layer_hash(client: Any, model: str, vt: str, base_id: int) -> str:
    row = _find_layer(client, ve.layer_name(model, vt, base_id))
    return ve.arch_hash(str(row.get("arch") or "")) if row and row.get("active") else ""


def _touched_access_fields(ops: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for o in ops or []:
        if isinstance(o, dict) and o.get("op") == "set_access" and str(o.get("node", "")).startswith("field:"):
            out.add(str(o["node"]).split(":", 1)[1].split("~")[0])
    return out


def _cleanup_layer(previous_arch: str | None, fields_touched: set[str]) -> str | None:
    """Earlier 'Who can see it' steps for fields being changed again: the see-only
    copy and the groups/read-only settings. Returns the layer without them, or
    None when there is nothing to clean."""
    if not previous_arch or not fields_touched:
        return None
    import xml.etree.ElementTree as ET

    root = ve.parse_arch(previous_arch)
    specs = list(root) if root.tag == "data" else [root]
    keep, removed = [], 0
    for spec in specs:
        expr = spec.get("expr") or ""
        names = set(re.findall(r"@name='([^']+)'", expr))
        kids = [c for c in spec if isinstance(c.tag, str)]
        is_copy = (spec.get("position") == "after" and len(kids) == 1 and kids[0].tag == "field"
                   and kids[0].get("name") in fields_touched and kids[0].get("readonly") == "1" and kids[0].get("groups"))
        is_groups = (spec.get("position") == "attributes" and names & fields_touched and kids
                     and all(k.tag == "attribute" and k.get("name") in {"groups", "readonly"} for k in kids)
                     and any(k.get("name") == "groups" for k in kids))
        if is_copy or is_groups:
            removed += 1
            continue
        keep.append(spec)
    if not removed:
        return None
    out = ET.Element("data")
    for spec in keep:
        out.append(spec)
    return ET.tostring(out, encoding="unicode")


# Presence: who else has this screen open (in memory, per API process).
_PRESENCE: dict[tuple[str, str, str], dict[str, tuple[str, float]]] = {}
PRESENCE_TTL = 45.0


class PresenceBody(LoadBody):
    editor_id: str = Field(min_length=6, max_length=64)
    name: str = Field(default="Someone", max_length=80)
    leaving: bool = False


@router.post("/presence")
def presence(connection_id: str, body: PresenceBody) -> dict[str, Any]:
    import time

    key = (connection_id, _check_model(body.model), _vt(body.view_type) + (f":{body.view_id}" if body.view_id else ""))
    now = time.time()
    room = _PRESENCE.setdefault(key, {})
    for eid in [e for e, (_n, ts) in room.items() if now - ts > PRESENCE_TTL]:
        room.pop(eid, None)
    if body.leaving:
        room.pop(body.editor_id, None)
    else:
        room[body.editor_id] = (body.name.strip() or "Someone", now)
    others = [{"editor_id": e, "name": n, "seen_seconds_ago": round(now - ts)} for e, (n, ts) in room.items() if e != body.editor_id]
    return {"others": others, "ttl": PRESENCE_TTL}


@router.post("/load")
def engine_load(connection_id: str, body: LoadBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    view = _get_views(client, model, vt, getattr(body, "view_id", None))
    fields = _fields_get(client, model)
    try:
        norm = ve.normalize(view["arch"], fields)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    _annotate(client, norm.tree, fields, _combined_raw(client, view["id"]))
    return {
        "major": _major(client),
        "model": model,
        "view_type": vt,
        "base_view_id": view["id"],
        "combined_arch": view["arch"],
        "arch_hash": ve.arch_hash(view["arch"]),
        "tree": norm.tree,
        "fields": _slim_fields(fields),
        "layer": _layer_info(client, model, vt, view["id"]),
        "layer_hash": _layer_hash(client, model, vt, view["id"]),
    }


@router.post("/records")
def engine_records(connection_id: str, body: RecordsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Live sample for the canvas: visible fields only, at most 80, never stored."""
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    view = _get_views(client, model, vt, getattr(body, "view_id", None))
    fields = _fields_get(client, model)
    norm = ve.normalize(view["arch"], fields)
    names = ve.record_fields(norm.tree, fields)
    limit = max(1, min(int(body.limit or ve.MAX_SAMPLE), ve.MAX_SAMPLE))
    try:
        total = int(client.execute_kw(model, "search_count", [[]]))
        rows = client.execute_kw(
            model, "search_read", [[]], {"fields": ["display_name", *names], "limit": limit, "order": "id desc"}
        )
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    records = []
    for row in rows or []:
        rec = {"id": int(row["id"]), "display_name": str(row.get("display_name") or "")}
        for n in names:
            rec[n] = ve.display_value(row.get(n), fields.get(n) or {})
        records.append(rec)
    return {"records": records, "total": total, "fields": names, "picks": ve.stress_picks(records, names)}


def _compile(client: Any, body: OpsBody) -> tuple[dict[str, Any], dict[str, Any], ve.CompileResult]:
    model, vt = _check_model(body.model), _vt(body.view_type)
    view = _get_views(client, model, vt, getattr(body, "view_id", None))
    fields = _fields_get(client, model)
    try:
        result = ve.compile_ops(view["arch"], fields, body.ops, **_compile_kwargs(client, fields, body.ops, model))
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    return view, fields, result


@router.post("/compile")
def engine_compile(connection_id: str, body: OpsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    view, fields, result = _compile(client, body)
    issues = classify_xpath_arch(result.arch, parent_arch=view["arch"])
    expected = ve.normalize(result.expected_arch, fields)
    touched = {str(o.get("node")) for o in body.ops if isinstance(o, dict) and o.get("op") == "set_access"}
    _annotate(client, expected.tree, fields, _combined_raw(client, view["id"]), skip_groups=touched)
    return {
        "arch": result.arch,
        "steps": result.steps,
        "dropped": result.dropped,
        "warnings": result.warnings,
        "issues": [i.as_dict() for i in issues],
        "blocking": bool(blocking_issues(issues)),
        "expected_tree": expected.tree,
    }


@router.post("/publish")
def engine_publish(connection_id: str, body: OpsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Stage 2e: role layouts (step-by-step mode, layout tests) go off while the change
    publishes, then are rebuilt on top of it; if publishing fails they come back as they were."""
    from app.routers.view_engine_2c import require_approval_ok, role_layers_paused

    require_approval_ok(db, connection_id)
    client = _client(connection_id, db)
    view = _get_views(client, _check_model(body.model), _vt(body.view_type), body.view_id)
    with role_layers_paused(client, db, connection_id, _check_model(body.model), int(view["id"])) as notes:
        res = _engine_publish_core(connection_id, body, db)
    return {**res, "role_layouts": notes} if notes else res


def _engine_publish_core(connection_id: str, body: OpsBody, db: Session) -> dict[str, Any]:
    """Preview then promote: write the layer, compare Odoo's result with the
    expected tree, roll back on any difference. Stock views are never written."""
    from app.routers.view_engine_2c import require_approval_ok

    require_approval_ok(db, connection_id)  # stage 2c: when approval is required, only approved changes publish
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    view = _get_views(client, model, vt, body.view_id)
    name = ve.layer_name(model, vt, view["id"])
    existing = _find_layer(client, name)
    previous_arch = str(existing.get("arch") or "") if existing and existing.get("active") else None
    if body.base_layer_hash is not None and body.base_layer_hash != (ve.arch_hash(previous_arch) if previous_arch else ""):
        raise HTTPException(status_code=409, detail={
            "message": "Someone else published changes to this screen since you opened it. Nothing was overwritten. "
                       "Reload to see their changes, then publish yours again.",
            "conflict": True})
    cleaned = _cleanup_layer(previous_arch, _touched_access_fields(body.ops))
    fields = _fields_get(client, model)
    if cleaned is not None and existing:
        # Read the stock screen (layer off for a moment) so earlier access steps are rebuilt, not stacked.
        try:
            client.execute_kw("ir.ui.view", "write", [[int(existing["id"])], {"active": False}])
            stock_arch = _get_views(client, model, vt, body.view_id)["arch"]
            base_arch = ve.apply_inherit_local(stock_arch, cleaned) if len(ve.parse_arch(cleaned)) else stock_arch
            result = ve.compile_ops(base_arch, fields, body.ops, **_compile_kwargs(client, fields, body.ops, model))
        except (ve.EngineError, HTTPException, *ODOO_ERRORS) as exc:
            _rollback(client, int(existing["id"]), False, previous_arch)
            if isinstance(exc, ve.EngineError):
                raise _engine_error(exc) from exc
            if isinstance(exc, HTTPException):
                raise
            raise _odoo_error(exc) from exc
        view = {**view, "arch": base_arch}
        merge_base = cleaned if len(ve.parse_arch(cleaned)) else None
    else:
        try:
            result = ve.compile_ops(view["arch"], fields, body.ops, **_compile_kwargs(client, fields, body.ops, model))
        except ve.EngineError as exc:
            raise _engine_error(exc) from exc
        merge_base = previous_arch
    issues = classify_xpath_arch(result.arch, parent_arch=view["arch"])
    if blocking_issues(issues):
        if cleaned is not None and existing:
            _rollback(client, int(existing["id"]), False, previous_arch)
        raise HTTPException(status_code=422, detail="Can't publish: " + "; ".join(i.message for i in blocking_issues(issues)))
    stock_before = _stock_hashes(client, model)
    new_arch = ve.merge_layers(merge_base, result.arch)
    layer_id: int | None = int(existing["id"]) if existing else None
    created = False
    try:
        if layer_id is None:
            layer_id = int(
                client.execute_kw(
                    "ir.ui.view",
                    "create",
                    [{
                        "name": name,
                        "model": model,
                        "type": vt if vt != "list" or _major(client) >= 18 else "tree",
                        "inherit_id": view["id"],
                        "mode": "extension",
                        "priority": ve.LAYER_PRIORITY,
                        "arch": new_arch,
                        "active": False,
                    }],
                )
            )
            created = True
        else:
            client.execute_kw("ir.ui.view", "write", [[layer_id], {"arch": new_arch, "active": False}])
        # Promote: Odoo validates the combined screen when the layer turns on.
        client.execute_kw("ir.ui.view", "write", [[layer_id], {"active": True}])
    except ODOO_ERRORS as exc:
        _rollback(client, layer_id, created, previous_arch)
        raise _odoo_error(exc) from exc

    after = _get_views(client, model, vt, body.view_id)
    expected_sig = ve.signature(ve.normalize(_expected_for_user(client, result.expected_arch), fields).tree)
    actual_sig = ve.signature(ve.normalize(after["arch"], fields).tree)
    diffs = ve.diff_signatures(expected_sig, actual_sig)
    for marker in result.expect:
        if after["arch"].count(marker) < result.expected_arch.count(marker):
            diffs.append(f"Odoo doesn't show the new item ({marker}).")
    stock_after = _stock_hashes(client, model)
    stock_unchanged = stock_before == stock_after
    if diffs or not stock_unchanged:
        _rollback(client, layer_id, created, previous_arch)
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Odoo shows this differently, so nothing was published.",
                "differences": diffs[:10],
                "stock_unchanged": stock_unchanged,
            },
        )
    version_id = vs.record_version(
        db, connection_id=connection_id, kind="view", model=model, view_type=vt, layer_name=name,
        layer_view_id=layer_id, action="publish", summary=list(getattr(body, "summary", None) or [s["op"] for s in result.steps]),
        layer_arch=new_arch, layer_active=True, combined_arch=after["arch"], odoo_major=_major(client),
    )
    _save_guard(db, connection_id, name, stock_after, view["id"], client)
    return {
        "ok": True,
        "version_id": version_id,
        "layer_view_id": layer_id,
        "previous_arch": previous_arch,
        "layer_arch": new_arch,
        "steps": len(result.steps),
        "dropped": result.dropped,
        "warnings": result.warnings,
        "fidelity": {"ok": True, "differences": []},
        "stock_unchanged": stock_unchanged,
        "arch_hash_before": ve.arch_hash(view["arch"]),
        "arch_hash_after": ve.arch_hash(after["arch"]),
        "layer_hash": ve.arch_hash(new_arch),
        "cleaned_access": cleaned is not None,
    }


def _rollback(client: Any, layer_id: int | None, created: bool, previous_arch: str | None) -> None:
    if layer_id is None:
        return
    try:
        if created:
            client.execute_kw("ir.ui.view", "unlink", [[layer_id]])
        elif previous_arch:
            client.execute_kw("ir.ui.view", "write", [[layer_id], {"arch": previous_arch, "active": True}])
        else:
            client.execute_kw("ir.ui.view", "write", [[layer_id], {"active": False}])
    except OdooClientError:
        pass


@router.post("/revert")
def engine_revert(connection_id: str, body: RevertBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Stage 2e: role layouts are rebuilt after an undo too, so the role loses the change as well."""
    from app.routers.view_engine_2c import role_layers_paused

    client = _client(connection_id, db)
    view = _get_views(client, _check_model(body.model), _vt(body.view_type), body.view_id)
    with role_layers_paused(client, db, connection_id, _check_model(body.model), int(view["id"])) as notes:
        res = _engine_revert_core(connection_id, body, db)
    return {**res, "role_layouts": notes} if notes else res


def _engine_revert_core(connection_id: str, body: RevertBody, db: Session) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    rows = client.execute_kw(
        "ir.ui.view", "read", [[int(body.layer_view_id)]], {"fields": ["name", "model"], "context": {"active_test": False}}
    )
    if not rows or not str(rows[0].get("name") or "").startswith(ve.LAYER_PREFIX) or rows[0].get("model") != model:
        raise HTTPException(status_code=404, detail="Those changes were not made in Ingenium, so they can't be undone here.")
    try:
        if body.mode == "remove":
            client.execute_kw("ir.ui.view", "unlink", [[int(body.layer_view_id)]])
        elif body.mode == "restore" and body.restore_arch:
            ve.parse_arch(body.restore_arch)
            client.execute_kw("ir.ui.view", "write", [[int(body.layer_view_id)], {"arch": body.restore_arch, "active": True}])
        else:
            client.execute_kw("ir.ui.view", "write", [[int(body.layer_view_id)], {"active": False}])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    after = _get_views(client, model, vt, body.view_id)
    layer_row = None if body.mode == "remove" else _find_layer(client, str(rows[0].get("name")))
    vs.record_version(
        db, connection_id=connection_id, kind="view", model=model, view_type=vt, layer_name=str(rows[0].get("name")),
        layer_view_id=None if body.mode == "remove" else int(body.layer_view_id),
        action={"remove": "remove", "restore": "undo", "deactivate": "undo"}[body.mode],
        summary=["Removed all changes" if body.mode == "remove" else "Undid the last publish"],
        layer_arch=str((layer_row or {}).get("arch") or "") or None, layer_active=bool((layer_row or {}).get("active")),
        combined_arch=after["arch"], odoo_major=_major(client),
    )
    _save_guard(db, connection_id, str(rows[0].get("name")), _stock_hashes(client, model), after["id"], client)
    return {"ok": True, "mode": body.mode, "arch_hash_after": ve.arch_hash(after["arch"])}


def _save_guard(db: Session, connection_id: str, layer: str, stock: dict[int, str], base_id: int, client: Any) -> None:
    """Upgrade guard baseline: what Odoo's own screens looked like when this layer last worked."""
    from datetime import UTC, datetime

    from app import view_engine_portable as vp

    vs.save_guard(db, connection_id, layer, {"stock": vp.stock_signature(stock), "base_view_id": int(base_id),
                                              "major": _major(client), "at": datetime.now(UTC).isoformat()})


def publish_layer_arch(
    client: Any, db: Session, connection_id: str, model: str, vt: str, view_id: int | None, new_arch: str,
    summary: list[str], action: str = "publish", priority: int | None = None,
) -> dict[str, Any]:
    """Stage 2e wrapper: role layouts go off while the whole layer publishes, then are rebuilt."""
    from app.routers.view_engine_2c import role_layers_paused

    base = _get_views(client, model, vt, view_id)
    with role_layers_paused(client, db, connection_id, model, int(base["id"])) as notes:
        res = _publish_layer_arch_core(client, db, connection_id, model, vt, view_id, new_arch, summary, action, priority)
    return {**res, "role_layouts": notes} if notes else res


def _publish_layer_arch_core(
    client: Any, db: Session, connection_id: str, model: str, vt: str, view_id: int | None, new_arch: str,
    summary: list[str], action: str = "publish", priority: int | None = None,
) -> dict[str, Any]:
    """Publish a whole layer (not ops): used by the upgrade guard fix and package import.
    Same checks as publish: written inactive, turned on, compared with what Odoo shows,
    rolled back on any difference; stock untouched."""
    view = _get_views(client, model, vt, view_id)
    name = ve.layer_name(model, vt, view["id"])
    existing = _find_layer(client, name)
    previous_arch = str(existing.get("arch") or "") if existing and existing.get("active") else None
    fields = _fields_get(client, model)
    layer_id: int | None = int(existing["id"]) if existing else None
    try:
        if existing and existing.get("active"):
            client.execute_kw("ir.ui.view", "write", [[layer_id], {"active": False}])
        stock_arch = _get_views(client, model, vt, view_id)["arch"]
        expected = ve.apply_inherit_local(stock_arch, new_arch) if len(ve.parse_arch(new_arch)) else stock_arch
    except (ve.EngineError, HTTPException, *ODOO_ERRORS) as exc:
        _rollback(client, layer_id, False, previous_arch)
        if isinstance(exc, ve.EngineError):
            raise _engine_error(exc) from exc
        if isinstance(exc, HTTPException):
            raise
        raise _odoo_error(exc) from exc
    stock_before = _stock_hashes(client, model)
    created = False
    vals: dict[str, Any] = {"arch": new_arch, "active": False}
    if priority:
        vals["priority"] = int(priority)
    try:
        if layer_id is None:
            layer_id = int(client.execute_kw("ir.ui.view", "create", [{
                "name": name, "model": model, "type": vt if vt != "list" or _major(client) >= 18 else "tree",
                "inherit_id": view["id"], "mode": "extension", "priority": int(priority or ve.LAYER_PRIORITY), **vals}]))
            created = True
        else:
            client.execute_kw("ir.ui.view", "write", [[layer_id], vals])
        client.execute_kw("ir.ui.view", "write", [[layer_id], {"active": True}])
    except ODOO_ERRORS as exc:
        _rollback(client, layer_id, created, previous_arch)
        raise _odoo_error(exc) from exc
    after = _get_views(client, model, vt, view_id)
    diffs = ve.diff_signatures(ve.signature(ve.normalize(_expected_for_user(client, expected), fields).tree),
                               ve.signature(ve.normalize(after["arch"], fields).tree))
    stock_after = _stock_hashes(client, model)
    if diffs or stock_before != stock_after:
        _rollback(client, layer_id, created, previous_arch)
        if priority and not created and existing:
            try:
                client.execute_kw("ir.ui.view", "write", [[layer_id], {"priority": int(existing.get("priority") or ve.LAYER_PRIORITY)}])
            except ODOO_ERRORS:
                pass
        raise HTTPException(status_code=409, detail={"message": "Odoo shows this differently, so nothing was published.",
                                                     "differences": diffs[:10], "stock_unchanged": stock_before == stock_after})
    version_id = vs.record_version(
        db, connection_id=connection_id, kind="view", model=model, view_type=vt, layer_name=name, layer_view_id=layer_id,
        action=action, summary=summary, layer_arch=new_arch, layer_active=True, combined_arch=after["arch"], odoo_major=_major(client))
    _save_guard(db, connection_id, name, stock_after, view["id"], client)
    return {"ok": True, "version_id": version_id, "layer_view_id": layer_id, "previous_arch": previous_arch,
            "layer_arch": new_arch, "layer_hash": ve.arch_hash(new_arch), "base_view_id": view["id"],
            "arch_hash_after": ve.arch_hash(after["arch"])}


# ----------------------------------------------------------------------------
# Reports
# ----------------------------------------------------------------------------

class ReportLoadBody(BaseModel):
    model: str = "account.move"
    report_id: int | None = None


class ReportEditBody(BaseModel):
    report_id: int
    record_id: int
    slot: str = "bottom"
    blocks: list[dict[str, Any]] = Field(default_factory=list)


class ReportRevertBody(BaseModel):
    layer_view_id: int
    mode: Literal["deactivate", "remove"] = "deactivate"


def _qweb_view(client: Any, key: str) -> dict[str, Any] | None:
    rows = client.execute_kw(
        "ir.ui.view",
        "search_read",
        [[("key", "=", key), ("type", "=", "qweb"), ("inherit_id", "=", False)]],
        {"fields": ["id", "arch", "key"], "limit": 1},
    )
    return rows[0] if rows else None


def _print_domain(client: Any, report_names: list[str]) -> list[Any]:
    """Which records Odoo will print: the filter set on the report or on the reports it calls
    (e.g. account.report_invoice only prints invoices, not journal entries). [] when none."""
    import ast

    try:
        if not client.execute_kw("ir.actions.report", "fields_get", [["domain"]], {"attributes": ["type"]}):
            return []
        rows = client.execute_kw("ir.actions.report", "search_read", [[("report_name", "in", list(dict.fromkeys(report_names)))]],
                                 {"fields": ["domain"], "limit": 10})
    except ODOO_ERRORS:
        return []
    out: list[Any] = []
    for r in rows or []:
        raw = r.get("domain")
        if not raw or not isinstance(raw, str):
            continue
        try:
            dom = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            continue
        ok = isinstance(dom, list) and all(
            (isinstance(t, (list, tuple)) and len(t) == 3 and isinstance(t[0], str) and isinstance(t[1], str)) or t in ("&", "|", "!")
            for t in dom)
        if ok and dom:
            out += [list(t) if isinstance(t, tuple) else t for t in dom]  # complete domains side by side = AND
    return out


def _report_context(client: Any, report_id: int) -> dict[str, Any]:
    rows = client.execute_kw(
        "ir.actions.report", "read", [[int(report_id)]], {"fields": ["id", "name", "report_name", "model", "report_type"]}
    )
    if not rows:
        raise HTTPException(status_code=404, detail="That print layout no longer exists.")
    rep = rows[0]
    if rep.get("report_type") != "qweb-pdf":
        raise HTTPException(status_code=422, detail="Only PDF print layouts can be edited here.")
    main = _qweb_view(client, str(rep["report_name"]))
    if not main:
        raise HTTPException(status_code=404, detail="Odoo has no template for this print layout.")
    # Follow the t-call chain (report -> loop wrapper -> document) to the template that draws the page,
    # e.g. account.report_invoice_with_payments -> account.report_invoice -> account.report_invoice_document.
    doc_key, doc = str(rep["report_name"]), main
    seen = {doc_key}
    for _hop in range(4):
        if vr.draws_page(str(doc.get("arch") or "")):
            break
        nxt = vr.document_template_key(doc_key, str(doc.get("arch") or ""))
        if nxt in seen:
            break
        found = _qweb_view(client, nxt)
        if not found:
            break
        seen.add(nxt)
        doc_key, doc = nxt, found
    doc_arch = str(doc.get("arch") or "")
    return {
        "print_domain": _print_domain(client, [str(rep["report_name"]), *sorted(seen)]),
        "report": rep,
        "document": {"key": doc_key, "view_id": int(doc["id"])},
        "doc_arch": doc_arch,
        "slots": vr.slots_for(doc_arch),
        "record_var": vr.record_var(doc_arch),
    }


def _render_pdf(client: Any, report_id: int, record_id: int) -> bytes:
    from odoo_client.report_render import render_report_pdf

    try:
        return render_report_pdf(client, int(report_id), [int(record_id)])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc


def _render_html(client: Any, report_name: str, record_id: int) -> str:
    from odoo_client.report_render import _session_opener

    url = f"{client.config.url}/report/html/{quote(report_name, safe='.')}/{int(record_id)}"
    try:
        with _session_opener(client).open(request.Request(url, method="GET"), timeout=client.config.timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (error.URLError, OdooClientError) as exc:
        raise HTTPException(status_code=502, detail=f"Odoo couldn't show the print layout: {exc}") from exc


@reports_router.post("/load")
def report_engine_load(connection_id: str, body: ReportLoadBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = _check_model(body.model)
    reps = client.execute_kw(
        "ir.actions.report",
        "search_read",
        [[("model", "=", model), ("report_type", "=", "qweb-pdf")]],
        {"fields": ["id", "name", "report_name"], "order": "id asc", "limit": 40},
    )
    if not reps:
        return {"major": _major(client), "model": model, "reports": [], "report": None, "records": []}
    report_id = int(body.report_id or reps[0]["id"])
    ctx = _report_context(client, report_id)
    fields = _fields_get(client, model)
    records = client.execute_kw(model, "search_read", [ctx["print_domain"]], {"fields": ["display_name"], "limit": ve.MAX_SAMPLE, "order": "id desc"})
    layer = _find_layer(client, vr.report_layer_name(ctx["document"]["key"]))
    return {
        "major": _major(client),
        "model": model,
        "reports": reps,
        "report": ctx["report"],
        "document": ctx["document"],
        "slots": ctx["slots"],
        "record_var": ctx["record_var"],
        "fields": _slim_fields(fields),
        "records": [{"id": int(r["id"]), "display_name": str(r.get("display_name") or "")} for r in records or []],
        "layer": {"id": int(layer["id"]), "active": bool(layer.get("active"))} if layer else None,
    }


@reports_router.post("/proof")
def report_engine_proof(connection_id: str, body: ReportEditBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Real PDF from Odoo's renderer for the published layout on one record."""
    client = _client(connection_id, db)
    pdf = _render_pdf(client, body.report_id, body.record_id)
    return {"ok": True, "pages": vr.pdf_page_count(pdf), "content_base64": base64.b64encode(pdf).decode("ascii")}


@reports_router.post("/publish")
def report_engine_publish(connection_id: str, body: ReportEditBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    ctx = _report_context(client, body.report_id)
    slot = next((s for s in ctx["slots"] if s["id"] == body.slot), None)
    if slot is None:
        raise HTTPException(status_code=422, detail="That place isn't available on this print layout.")
    fields = _fields_get(client, str(ctx["report"]["model"]))
    try:
        blocks = vr.validate_blocks(body.blocks, fields)
        arch = vr.compile_report_layer(slot, blocks, ctx["record_var"])
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"That content isn't allowed in a print layout: {exc}") from exc
    doc_id = int(ctx["document"]["view_id"])
    stock_before = _view_hash(client, doc_id)
    name = vr.report_layer_name(ctx["document"]["key"])
    existing = _find_layer(client, name)
    previous_arch = str(existing.get("arch") or "") if existing and existing.get("active") else None
    layer_id: int | None = int(existing["id"]) if existing else None
    created = False
    try:
        if layer_id is None:
            layer_id = int(client.execute_kw("ir.ui.view", "create", [{
                "name": name, "type": "qweb", "inherit_id": doc_id, "mode": "extension",
                "priority": ve.LAYER_PRIORITY, "arch": arch, "active": False,
            }]))
            created = True
        else:
            client.execute_kw("ir.ui.view", "write", [[layer_id], {"arch": arch, "active": False}])
        client.execute_kw("ir.ui.view", "write", [[layer_id], {"active": True}])
    except ODOO_ERRORS as exc:
        _rollback(client, layer_id, created, previous_arch)
        raise _odoo_error(exc) from exc
    try:
        pdf = _render_pdf(client, body.report_id, body.record_id)
        html = _render_html(client, str(ctx["report"]["report_name"]), body.record_id)
    except HTTPException:
        _rollback(client, layer_id, created, previous_arch)
        raise
    missing = [t for t in vr.expected_texts(blocks) if t not in html]
    stock_unchanged = stock_before == _view_hash(client, doc_id)
    if missing or not stock_unchanged:
        _rollback(client, layer_id, created, previous_arch)
        raise HTTPException(status_code=409, detail={
            "message": "Odoo's print doesn't show the change, so nothing was published.",
            "missing": missing, "stock_unchanged": stock_unchanged,
        })
    return {
        "ok": True,
        "layer_view_id": layer_id,
        "previous_arch": previous_arch,
        "layer_arch": arch,
        "pages": vr.pdf_page_count(pdf),
        "stock_unchanged": stock_unchanged,
        "content_base64": base64.b64encode(pdf).decode("ascii"),
    }


@reports_router.post("/revert")
def report_engine_revert(connection_id: str, body: ReportRevertBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    rows = client.execute_kw("ir.ui.view", "read", [[int(body.layer_view_id)]], {"fields": ["name"], "context": {"active_test": False}})
    if not rows or not str(rows[0].get("name") or "").startswith(ve.LAYER_PREFIX):
        raise HTTPException(status_code=404, detail="Those changes were not made in Ingenium, so they can't be undone here.")
    try:
        if body.mode == "remove":
            client.execute_kw("ir.ui.view", "unlink", [[int(body.layer_view_id)]])
        else:
            client.execute_kw("ir.ui.view", "write", [[int(body.layer_view_id)], {"active": False}])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    return {"ok": True, "mode": body.mode}
