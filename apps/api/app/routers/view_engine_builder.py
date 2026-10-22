"""View Designer stage 2b (part 2): new screens, translations, upgrade guard,
reusable sections and the portable staging -> production package.

Same rules as every other edit: stock views are never written; layers go
through the checked publish path; anything created here is named
``ingenium_*`` so it can be found and removed.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import view_engine as ve
from app import view_engine_portable as vp
from app import view_engine_store as vs
from app.db import get_db
from app.routers.view_engine import (
    ODOO_ERRORS,
    OpsBody,
    _check_model,
    _client,
    _combined_raw,
    _engine_error,
    _fields_get,
    _find_layer,
    _get_views,
    _major,
    _odoo_error,
    _stock_hashes,
    _vt,
    engine_publish,
    publish_layer_arch,
)

router = APIRouter(prefix="/connections/{connection_id}/views/engine", tags=["view-engine"])

LANG_RE = re.compile(r"^[a-z]{2,3}(_[A-Za-z0-9@]{2,10})?$")
CUSTOM_TTYPES = frozenset({"char", "text", "integer", "float", "monetary", "date", "datetime", "boolean", "selection",
                           "many2one", "many2many", "one2many", "binary", "html"})


class ScreenRef(BaseModel):
    model: str
    view_type: str = "form"
    view_id: int | None = None


def _odoo_vt(vt: str, major: int) -> str:
    return "tree" if vt == "list" and major < 18 else vt


# ----------------------------------------------------------------------------
# New screens
# ----------------------------------------------------------------------------

class TemplatesBody(BaseModel):
    model: str


@router.post("/screens/templates")
def screen_templates(connection_id: str, body: TemplatesBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = _check_model(body.model)
    fields = _fields_get(client, model)
    return {"templates": vp.screen_templates(fields), "screens": _screens(client, db, connection_id, model)}


def _screens(client: Any, db: Session, connection_id: str, model: str) -> list[dict[str, Any]]:
    out = []
    for row in vs.list_items(db, connection_id, "screen", model):
        item = vs.item_out(row)
        vid = int(item["payload"].get("view_id") or 0)
        exists = bool(vid and client.execute_kw("ir.ui.view", "search_count", [[("id", "=", vid)]]))
        out.append({**item, "exists": exists})
    return out


class CreateScreenBody(BaseModel):
    model: str
    view_type: str = "form"
    template: str = "blank"
    label: str = Field(min_length=1, max_length=80)
    make_menu: bool = False
    parent_menu_id: int | None = None


@router.post("/screens/create")
def screen_create(connection_id: str, body: CreateScreenBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """A new screen of its own (Odoo 'primary' view at priority 1000, so it never
    replaces the default screen). Optionally a menu item that opens it."""
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    major = _major(client)
    fields = _fields_get(client, model)
    label = body.label.strip()
    try:
        arch = vp.build_screen_arch(vt, body.template, fields, major, label)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    created: list[tuple[str, int]] = []

    def undo() -> None:
        for m, rid in reversed(created):
            try:
                client.execute_kw(m, "unlink", [[rid]])
            except ODOO_ERRORS:
                pass

    try:
        view_id = int(client.execute_kw("ir.ui.view", "create", [{
            "name": vp.screen_view_name(model, vt, label), "model": model, "type": _odoo_vt(vt, major),
            "mode": "primary", "priority": vp.SCREEN_PRIORITY, "arch": arch}]))
        created.append(("ir.ui.view", view_id))
        action_id = menu_id = None
        if body.make_menu:
            if vt == "search":
                raise HTTPException(status_code=422, detail="A search screen can't open from a menu by itself.")
            action_id = int(client.execute_kw("ir.actions.act_window", "create", [{
                "name": label, "res_model": model, "view_mode": _odoo_vt(vt, major), "view_id": view_id}]))
            created.append(("ir.actions.act_window", action_id))
            menu_vals: dict[str, Any] = {"name": label, "action": f"ir.actions.act_window,{action_id}", "sequence": 90}
            if body.parent_menu_id:
                menu_vals["parent_id"] = int(body.parent_menu_id)
            menu_id = int(client.execute_kw("ir.ui.menu", "create", [menu_vals]))
            created.append(("ir.ui.menu", menu_id))
        # Check: Odoo opens it and shows what we built.
        shown = _get_views(client, model, vt, view_id)
        if shown["id"] != view_id:
            raise HTTPException(status_code=409, detail="Odoo didn't open the new screen, so it was removed.")
        ve.normalize(shown["arch"], fields)
    except HTTPException:
        undo()
        raise
    except ODOO_ERRORS as exc:
        undo()
        raise _odoo_error(exc) from exc
    except ve.EngineError as exc:
        undo()
        raise _engine_error(exc) from exc
    row = vs.save_item(db, connection_id=connection_id, kind="screen", key=model, name=label,
                       payload={"view_id": view_id, "action_id": action_id, "menu_id": menu_id, "view_type": vt, "template": body.template})
    return {"ok": True, "item_id": row.id, "view_id": view_id, "action_id": action_id, "menu_id": menu_id, "view_type": vt}


class ItemBody(BaseModel):
    item_id: str


@router.post("/screens/delete")
def screen_delete(connection_id: str, body: ItemBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    row = vs.get_item(db, connection_id, body.item_id)
    if not row or row.kind != "screen":
        raise HTTPException(status_code=404, detail="That screen wasn't made in Ingenium.")
    p = vs.item_out(row)["payload"]
    vid = int(p.get("view_id") or 0)
    try:
        if p.get("menu_id"):
            client.execute_kw("ir.ui.menu", "unlink", [[int(p["menu_id"])]])
        if p.get("action_id"):
            client.execute_kw("ir.actions.act_window", "unlink", [[int(p["action_id"])]])
        if vid:
            names = client.execute_kw("ir.ui.view", "search_read", [[("id", "=", vid)]], {"fields": ["name"], "context": {"active_test": False}})
            if names and not str(names[0].get("name") or "").startswith(vp.SCREEN_PREFIX):
                raise HTTPException(status_code=409, detail="That screen wasn't made in Ingenium, so it wasn't removed.")
            layers = client.execute_kw("ir.ui.view", "search", [[("inherit_id", "=", vid), ("name", "=like", ve.LAYER_PREFIX + "%")]],
                                       {"context": {"active_test": False}})
            if layers:
                client.execute_kw("ir.ui.view", "unlink", [layers])
            if names:
                client.execute_kw("ir.ui.view", "unlink", [[vid]])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    vs.delete_item(db, row)
    return {"ok": True}


# ----------------------------------------------------------------------------
# Translations
# ----------------------------------------------------------------------------

def _langs(client: Any) -> list[dict[str, str]]:
    rows = client.execute_kw("res.lang", "search_read", [[("active", "=", True)]], {"fields": ["code", "name"]})
    return [{"code": str(r["code"]), "name": str(r["name"])} for r in rows or []]


def _labels(client: Any, model: str, vt: str, view_id: int | None, lang: str) -> dict[str, str]:
    ctx = {"lang": lang}
    res = client.execute_kw(model, "get_views", [], {"views": [[int(view_id) if view_id else False, vt]], "options": {"toolbar": False}, "context": ctx})
    arch = ((res or {}).get("views") or {}).get(vt, {}).get("arch") or ""
    fields = client.execute_kw(model, "fields_get", [], {"attributes": ["string", "type"], "context": ctx}) or {}
    norm = ve.normalize(arch, fields)
    out = {}
    for nid, node in norm.by_id.items():
        if "/" in nid or nid == "root" or node.get("helper") or not node.get("label"):
            continue  # only items with a stable name; labels drawn from text can't be matched across languages
        if node["tag"] in {"field", "page", "group", "button", "separator", "filter", "notebook"}:
            out[nid] = str(node["label"])
    return out


class TranslationsBody(ScreenRef):
    pass


@router.post("/translations/list")
def translations_list(connection_id: str, body: TranslationsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    langs = _langs(client)
    base = _labels(client, model, vt, body.view_id, "en_US")
    others = [lg for lg in langs if lg["code"] != "en_US"]
    per = {lg["code"]: _labels(client, model, vt, body.view_id, lg["code"]) for lg in others[:8]}
    rows = [{"node": nid, "en": label, "langs": {code: per[code].get(nid, "") for code in per}} for nid, label in base.items()]
    return {"languages": others[:8], "rows": rows,
            "hint": None if others else "Only English is turned on in this Odoo. Add a language in Odoo's Settings first."}


class TranslationSaveBody(ScreenRef):
    node: str
    translations: dict[str, str]
    base_layer_hash: str | None = None


@router.post("/translations/save")
def translations_save(connection_id: str, body: TranslationSaveBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Pin the label on the screen layer (stock untouched), then store its translation
    on that layer; checked by reading the screen back in each language."""
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    active = {lg["code"] for lg in _langs(client)}
    clean = {}
    for code, text in (body.translations or {}).items():
        text = str(text or "").strip()
        if code == "en_US" or not LANG_RE.match(code) or code not in active:
            raise HTTPException(status_code=422, detail=f"The language {code} isn't turned on in this Odoo.")
        if not text or len(text) > 80:
            raise HTTPException(status_code=422, detail="Translations need 1 to 80 characters.")
        clean[code] = text
    if not clean:
        raise HTTPException(status_code=422, detail="There's nothing to translate.")
    en = _labels(client, model, vt, body.view_id, "en_US")
    if body.node not in en:
        raise HTTPException(status_code=422, detail="That item can't be translated here (it has no stable name).")
    term = en[body.node]
    view = _get_views(client, model, vt, body.view_id)
    name = ve.layer_name(model, vt, view["id"])
    existing = _find_layer(client, name)
    if not existing or f'<attribute name="string">{term}</attribute>' not in str(existing.get("arch") or "") or not existing.get("active"):
        engine_publish(connection_id, OpsBody(model=model, view_type=vt, view_id=body.view_id, base_layer_hash=body.base_layer_hash,
                                              ops=[{"op": "set_attr", "node": body.node, "attr": "string", "value": term, "force": True}],
                                              summary=[f"Pinned the label '{term}' for translation"]), db)
        existing = _find_layer(client, name)
    assert existing
    layer_id = int(existing["id"])
    try:
        prev_rows, _ctx = client.execute_kw("ir.ui.view", "get_field_translations", [[layer_id], "arch_db"], {"langs": list(clean)})
    except ODOO_ERRORS:
        prev_rows = []
    previous = {r["lang"]: r.get("value") or r.get("source") for r in prev_rows or [] if r.get("source") == term}
    try:
        client.execute_kw("ir.ui.view", "update_field_translations", [[layer_id], "arch_db", {code: {term: text} for code, text in clean.items()}])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    wrong = []
    for code, text in clean.items():
        if _labels(client, model, vt, body.view_id, code).get(body.node) != text:
            wrong.append(code)
    if wrong:
        restore = {code: {term: previous.get(code) or term} for code in clean}
        try:
            client.execute_kw("ir.ui.view", "update_field_translations", [[layer_id], "arch_db", restore])
        except ODOO_ERRORS:
            pass
        raise HTTPException(status_code=409, detail=f"Odoo didn't show the translation in {', '.join(wrong)}, so it was put back.")
    vs.record_version(db, connection_id=connection_id, kind="view", model=model, view_type=vt, layer_name=name, layer_view_id=layer_id,
                      action="translate", summary=[f"Translated '{term}' into {', '.join(sorted(clean))}"],
                      layer_arch=str(existing.get("arch") or ""), layer_active=True, combined_arch=None, odoo_major=_major(client))
    return {"ok": True, "term": term, "saved": clean, "previous": previous}


# ----------------------------------------------------------------------------
# Upgrade guard
# ----------------------------------------------------------------------------

@router.post("/guard/check")
def guard_check(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    """After an Odoo update or a new app: does every step of this screen's layer still work?"""
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    screen_ok, base_id, problem = True, int(body.view_id or 0), None
    try:
        view = _get_views(client, model, vt, body.view_id)
        base_id = view["id"]
    except HTTPException as exc:
        screen_ok, problem = False, str(exc.detail)
    if not base_id:
        return {"has_layer": False, "screen_ok": screen_ok, "problem": problem}
    name = ve.layer_name(model, vt, base_id)
    layer = _find_layer(client, name)
    if not layer or not layer.get("active"):
        return {"has_layer": False, "screen_ok": screen_ok, "problem": problem}
    baseline = vs.get_guard(db, connection_id, name)
    current = vp.stock_signature(_stock_hashes(client, model))
    steps = vp.guard_report(str(layer.get("arch") or ""), _combined_raw(client, base_id))
    bad = [s for s in steps if s["status"] != "ok"]
    return {
        "has_layer": True, "screen_ok": screen_ok, "problem": problem,
        "odoo_changed": bool(baseline and baseline.get("stock") != current),
        "baseline_at": (baseline or {}).get("at"), "baseline_major": (baseline or {}).get("major"), "major": _major(client),
        "steps": steps, "problems": len(bad), "ok": screen_ok and not bad,
        "summary": ("All your changes still work." if screen_ok and not bad else
                    f"{len(bad)} of your {len(steps)} changes no longer work as made." if bad else "Odoo can't show this screen right now."),
    }


@router.post("/guard/fix")
def guard_fix(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Keep what still applies, drop what no longer can, and put this layer after
    anything that now overrides it. Published through the checked path."""
    from app.routers.view_engine_2c import require_approval_ok

    require_approval_ok(db, connection_id)  # same approval rule as normal publishing
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    view = _get_views(client, model, vt, body.view_id)
    name = ve.layer_name(model, vt, view["id"])
    layer = _find_layer(client, name)
    if not layer or not layer.get("active"):
        raise HTTPException(status_code=404, detail="This screen has no Ingenium changes to check.")
    layer_arch = str(layer.get("arch") or "")
    report = vp.guard_report(layer_arch, _combined_raw(client, view["id"]))
    overridden = [s for s in report if s["status"] == "overridden"]
    layer_id = int(layer["id"])
    try:
        client.execute_kw("ir.ui.view", "write", [[layer_id], {"active": False}])
        stock_arch = _get_views(client, model, vt, body.view_id)["arch"]
    finally:
        client.execute_kw("ir.ui.view", "write", [[layer_id], {"active": True}])
    import xml.etree.ElementTree as ET

    working, kept, dropped = stock_arch, ET.Element("data"), []
    for i, spec in enumerate(vp.layer_specs(layer_arch)):
        chunk = ET.Element("data")
        chunk.append(spec)
        try:
            working = ve.apply_inherit_local(working, ET.tostring(chunk, encoding="unicode"))
            kept.append(spec)
        except ve.EngineError:
            dropped.append(report[i]["text"] if i < len(report) else f"Step {i + 1}")
    priority = None
    if overridden:
        rows = client.execute_kw("ir.ui.view", "search_read", [[("model", "=", model), ("mode", "=", "extension"),
                                                                ("name", "not ilike", ve.LAYER_PREFIX), ("priority", ">=", int(layer.get("priority") or ve.LAYER_PRIORITY))]],
                                 {"fields": ["priority"]})
        if rows:
            priority = max(int(r["priority"]) for r in rows) + 1
    if not dropped and not priority:
        return {"ok": True, "changed": False, "message": "Nothing needed fixing.", "dropped": [], "priority": None}
    new_arch = ET.tostring(kept, encoding="unicode")
    summary = [f"Upgrade fix: dropped '{d}'" for d in dropped] + ([f"Upgrade fix: put Ingenium changes after other apps (order {priority})"] if priority else [])
    result = publish_layer_arch(client, db, connection_id, model, vt, body.view_id, new_arch, summary, action="fix", priority=priority)
    after = vp.guard_report(new_arch, _combined_raw(client, view["id"]))
    return {**result, "changed": True, "dropped": dropped, "priority": priority,
            "still_wrong": [s for s in after if s["status"] != "ok"]}


# ----------------------------------------------------------------------------
# Reusable sections
# ----------------------------------------------------------------------------

class SectionSaveBody(ScreenRef):
    node: str
    name: str = Field(min_length=1, max_length=80)


@router.post("/sections/save")
def section_save(connection_id: str, body: SectionSaveBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    view = _get_views(client, model, vt, body.view_id)
    fields = _fields_get(client, model)
    norm = ve.normalize(view["arch"], fields)
    el = norm.el_by_id.get(body.node)
    if el is None:
        raise HTTPException(status_code=422, detail="That part of the screen has changed. Reload and pick it again.")
    try:
        sec = vp.extract_section(el, fields)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    row = vs.save_item(db, connection_id=connection_id, kind="section", key=model, name=body.name.strip(),
                       payload={**sec, "model": model, "view_type": vt})
    return {"ok": True, "section": vs.item_out(row)}


class SectionListBody(BaseModel):
    model: str


@router.post("/sections/list")
def section_list(connection_id: str, body: SectionListBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Every saved section on this connection, with how well it fits this record type."""
    client = _client(connection_id, db)
    model = _check_model(body.model)
    fields = _fields_get(client, model)
    rows = vs.list_items(db, connection_id, "section")
    out = []
    for r in rows:
        item = vs.item_out(r)
        out.append({**item, "fit": vp.section_fit(item["payload"], fields)})
    return {"sections": out}


@router.post("/sections/delete")
def section_delete(connection_id: str, body: ItemBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = vs.get_item(db, connection_id, body.item_id)
    if not row or row.kind != "section":
        raise HTTPException(status_code=404, detail="That section isn't saved here.")
    vs.delete_item(db, row)
    return {"ok": True}


# ----------------------------------------------------------------------------
# Portable package (staging -> production)
# ----------------------------------------------------------------------------

def _xmlid(client: Any, view_id: int) -> str | None:
    rows = client.execute_kw("ir.model.data", "search_read", [[("model", "=", "ir.ui.view"), ("res_id", "=", int(view_id))]],
                             {"fields": ["module", "name"], "limit": 1})
    return f"{rows[0]['module']}.{rows[0]['name']}" if rows else None


def _custom_field_defs(client: Any, model: str, names: set[str]) -> list[dict[str, Any]]:
    wanted = sorted(n for n in names if n.startswith("x_"))
    if not wanted:
        return []
    rows = client.execute_kw("ir.model.fields", "search_read", [[("model", "=", model), ("name", "in", wanted), ("state", "=", "manual")]],
                             {"fields": ["name", "ttype", "field_description", "relation", "relation_field", "required", "help",
                                         "related", "store", "selection_ids", "copied", "compute"]})
    out = []
    for r in rows:
        d = {k: r.get(k) for k in ("name", "ttype", "field_description", "relation", "relation_field", "required", "help", "related", "store", "copied")}
        if r.get("selection_ids"):
            sel = client.execute_kw("ir.model.fields.selection", "read", [r["selection_ids"]], {"fields": ["value", "name", "sequence"]})
            d["selection"] = [[s["value"], s["name"]] for s in sorted(sel, key=lambda s: s.get("sequence") or 0)]
        if r.get("compute"):
            spec = vp.count_spec(r["name"], r.get("compute"))
            if not spec:
                raise HTTPException(status_code=422, detail=f"The field {r['name']} is calculated by code, so it can't be moved by a package.")
            d["count_of"] = spec
            d.pop("store", None)
        out.append({k: v for k, v in d.items() if v not in (None, False, "")} | {"name": r["name"], "ttype": r["ttype"]})
    return out


def _package_actions(client: Any, arch: str) -> list[dict[str, Any]]:
    """Each button action by meaning: Odoo's fixed name when it has one, else the smart-button list it opens."""
    out: list[dict[str, Any]] = []
    for aid in sorted(vp.action_refs(arch)):
        kind = client.execute_kw("ir.actions.actions", "search_read", [[("id", "=", aid)]], {"fields": ["type"], "limit": 1})
        if not kind:
            raise HTTPException(status_code=422, detail="A button on this screen opens something that no longer exists. Fix the button first.")
        rows = client.execute_kw("ir.model.data", "search_read", [[("model", "=", kind[0]["type"]), ("res_id", "=", aid), ("module", "!=", "__export__")]],
                                 {"fields": ["module", "name", "model"], "limit": 1})
        if rows:
            out.append({"id": aid, "xmlid": f"{rows[0]['module']}.{rows[0]['name']}", "model": rows[0]["model"]})
            continue
        act = client.execute_kw("ir.actions.act_window", "search_read", [[("id", "=", aid)]], {"fields": ["name", "res_model", "domain"], "limit": 1})
        spec = vp.link_action_spec(act[0]) if act else None
        if not spec:
            raise HTTPException(status_code=422, detail="A button on this screen opens something that only exists in this database, so the screen can't be packaged.")
        out.append({"id": aid, "define": spec})
    return out


@router.post("/package/export")
def package_export(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    view = _get_views(client, model, vt, body.view_id)
    layer = _find_layer(client, ve.layer_name(model, vt, view["id"]))
    if not layer or not layer.get("active"):
        raise HTTPException(status_code=404, detail="This screen has no published Ingenium changes to package.")
    arch = str(layer.get("arch") or "")
    pkg: dict[str, Any] = {
        "format": vp.PACKAGE_FORMAT, "model": model, "view_type": vt, "odoo_major": _major(client),
        "base_view_xmlid": _xmlid(client, view["id"]), "layer_arch": arch,
        "custom_fields": _custom_field_defs(client, model, vp.referenced_fields(arch)),
        "actions": _package_actions(client, arch),
        "steps": ve.count_layer_steps(arch),
    }
    if not pkg["base_view_xmlid"]:
        rows = client.execute_kw("ir.ui.view", "read", [[view["id"]]], {"fields": ["name", "arch"]})
        if rows and str(rows[0]["name"]).startswith(vp.SCREEN_PREFIX):
            pkg["screen"] = {"name": rows[0]["name"], "arch": rows[0]["arch"]}
        else:
            raise HTTPException(status_code=422, detail="This screen has no fixed name in Odoo, so it can't be matched in another database.")
    pkg["checksum"] = vp.package_checksum(pkg)
    return {"package": pkg, "file_name": f"ingenium-{model.replace('.', '-')}-{vt}.json"}


class PackageBody(BaseModel):
    package: dict[str, Any]
    replace: bool = False


def _package_plan(client: Any, pkg: dict[str, Any]) -> dict[str, Any]:
    try:
        vp.check_package(pkg)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    model, vt, major = _check_model(str(pkg["model"])), _vt(str(pkg["view_type"])), _major(client)
    try:
        arch = vp.adapt_layer(str(pkg["layer_arch"]), int(pkg["odoo_major"]), major)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    fields = _fields_get(client, model)
    problems: list[str] = []
    base_id: int | None = None
    if pkg.get("base_view_xmlid"):
        mod, _, nm = str(pkg["base_view_xmlid"]).partition(".")
        rows = client.execute_kw("ir.model.data", "search_read", [[("model", "=", "ir.ui.view"), ("module", "=", mod), ("name", "=", nm)]],
                                 {"fields": ["res_id"], "limit": 1})
        if not rows:
            problems.append(f"This database doesn't have the screen {pkg['base_view_xmlid']} (is the same app installed?).")
        else:
            base_id = int(rows[0]["res_id"])
    defs = [d for d in pkg.get("custom_fields") or [] if isinstance(d, dict)]
    to_create = [d for d in defs if d.get("name") not in fields]
    for d in defs:
        if not str(d.get("name") or "").startswith("x_") or d.get("ttype") not in CUSTOM_TTYPES:
            problems.append(f"The field {d.get('name')} can't be created by a package.")
        elif d.get("name") in fields and fields[d["name"]].get("type") != d.get("ttype"):
            problems.append(f"The field {d['name']} exists here with a different type.")
        elif d.get("relation"):
            if not client.execute_kw("ir.model", "search_count", [[("model", "=", d["relation"])]]):
                problems.append(f"The field {d['name']} needs the record type {d['relation']}, which isn't here.")
    action_map: dict[int, int] = {}
    actions_to_create: list[dict[str, Any]] = []
    for a in pkg.get("actions") or []:
        if a.get("xmlid"):
            mod, _, nm = str(a["xmlid"]).partition(".")
            rows = client.execute_kw("ir.model.data", "search_read", [[("module", "=", mod), ("name", "=", nm), ("model", "=", str(a.get("model") or ""))]],
                                     {"fields": ["res_id"], "limit": 1})
            if rows:
                action_map[int(a["id"])] = int(rows[0]["res_id"])
            else:
                problems.append(f"A button opens {a['xmlid']}, which this database doesn't have (is the same app installed?).")
            continue
        d = a.get("define") or {}
        rel, link = str(d.get("res_model") or ""), str(d.get("link_field") or "")
        try:
            rel_meta = (_fields_get(client, _check_model(rel)) or {}).get(link) or {}
        except (HTTPException, *ODOO_ERRORS):
            rel_meta = {}
        if rel_meta.get("type") != "many2one" or rel_meta.get("relation") != model:
            problems.append(f"A button lists {rel or 'records'} linked by {link or '?'}, which doesn't exist here.")
            continue
        domain = f"[('{link}', '=', active_id)]"
        same = client.execute_kw("ir.actions.act_window", "search", [[("name", "=", str(d.get("name") or "")), ("res_model", "=", rel), ("domain", "=", domain)]], {"limit": 1})
        if same:
            action_map[int(a["id"])] = int(same[0])
        else:
            actions_to_create.append({"id": int(a["id"]), "name": str(d.get("name") or "Related")[:80], "res_model": rel, "link_field": link})
    for d in defs:
        c = d.get("count_of")
        if c and d.get("name") not in fields:
            try:
                vp.count_compute(str(d["name"]), str(c.get("relation") or ""), str(c.get("link_field") or ""))
                ok = ((_fields_get(client, _check_model(str(c["relation"]))) or {}).get(str(c["link_field"])) or {}).get("relation") == model
            except (ve.EngineError, HTTPException, *ODOO_ERRORS):
                ok = False
            if not ok:
                problems.append(f"The count field {d['name']} counts something that doesn't exist here.")
    missing = sorted(n for n in vp.referenced_fields(arch) if n not in fields and n not in {d.get("name") for d in defs}
                     and not n.startswith(ve.LAYER_PREFIX) and n in _field_refs_only(arch))
    problems += [f"The field {n} isn't on {model} in this database." for n in missing]
    existing = None
    if base_id:
        existing = _find_layer(client, ve.layer_name(model, vt, base_id))
        if not to_create and not problems:
            try:
                ve.apply_inherit_local(_get_views(client, model, vt, base_id)["arch"] if not (existing and existing.get("active"))
                                       else _stock_screen(client, model, vt, base_id, int(existing["id"])), arch)
            except ve.EngineError as exc:
                problems.append(f"The changes don't fit this database's screen: {exc}")
    return {"model": model, "view_type": vt, "arch": arch, "base_view_id": base_id, "fields_to_create": to_create, "problems": problems,
            "has_changes_here": bool(existing and existing.get("active")), "steps": ve.count_layer_steps(arch),
            "from_major": int(pkg["odoo_major"]), "to_major": major, "screen": pkg.get("screen"),
            "action_map": action_map, "actions_to_create": actions_to_create}


def _field_refs_only(arch: str) -> set[str]:
    out: set[str] = set()
    for spec in vp.layer_specs(arch):
        for el in spec.iter("field"):
            out.add(el.get("name") or "")
        for x in spec.iter("xpath"):
            for m in re.finditer(r"field\[@name='([^']+)'\]", x.get("expr") or ""):
                out.add(m.group(1))
    return out


def _stock_screen(client: Any, model: str, vt: str, base_id: int, layer_id: int) -> str:
    client.execute_kw("ir.ui.view", "write", [[layer_id], {"active": False}])
    try:
        return _get_views(client, model, vt, base_id)["arch"]
    finally:
        client.execute_kw("ir.ui.view", "write", [[layer_id], {"active": True}])


@router.post("/package/check")
def package_check(connection_id: str, body: PackageBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    plan = _package_plan(client, body.package)
    plan.pop("arch", None)
    plan.pop("action_map", None)
    plan["actions_to_create"] = [a["name"] for a in plan["actions_to_create"]]
    return {**plan, "ok": not plan["problems"]}


@router.post("/package/import")
def package_import(connection_id: str, body: PackageBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.routers.view_engine_2c import require_approval_ok

    require_approval_ok(db, connection_id)  # same approval rule as normal publishing
    client = _client(connection_id, db)
    plan = _package_plan(client, body.package)
    if plan["problems"] and not (plan["screen"] and not plan["base_view_id"] and all("doesn't have the screen" in p for p in plan["problems"])):
        raise HTTPException(status_code=422, detail={"message": "The package can't go into this database.", "problems": plan["problems"]})
    if plan["has_changes_here"] and not body.replace:
        raise HTTPException(status_code=409, detail={"message": "This screen already has Ingenium changes here. Importing replaces them.",
                                                     "needs_confirm": True})
    model, vt = plan["model"], plan["view_type"]
    created_fields: list[int] = []
    created_actions: list[int] = []
    created_screen: int | None = None
    try:
        model_id = client.execute_kw("ir.model", "search", [[("model", "=", model)]], {"limit": 1})[0]
        for d in plan["fields_to_create"]:
            vals: dict[str, Any] = {"model_id": model_id, "name": d["name"], "ttype": d["ttype"], "state": "manual",
                                    "field_description": str(d.get("field_description") or d["name"])[:120]}
            for k in ("relation", "relation_field", "required", "help", "related", "copied"):
                if d.get(k) not in (None, ""):
                    vals[k] = d[k]
            if d.get("related"):
                vals["store"] = bool(d.get("store"))
            if d.get("selection"):
                vals["selection_ids"] = [(0, 0, {"value": str(v), "name": str(n), "sequence": i}) for i, (v, n) in enumerate(d["selection"])]
            if d.get("count_of"):
                vals.update({"store": False, "depends": "",
                             "compute": vp.count_compute(str(d["name"]), str(d["count_of"]["relation"]), str(d["count_of"]["link_field"]))})
            created_fields.append(int(client.execute_kw("ir.model.fields", "create", [vals])))
        base_id = plan["base_view_id"]
        if not base_id and plan["screen"]:
            scr = plan["screen"]
            created_screen = int(client.execute_kw("ir.ui.view", "create", [{
                "name": str(scr["name"]), "model": model, "type": _odoo_vt(vt, _major(client)), "mode": "primary",
                "priority": vp.SCREEN_PRIORITY, "arch": vp.adapt_layer(str(scr["arch"]), plan["from_major"], plan["to_major"])}]))
            base_id = created_screen
        action_map = dict(plan["action_map"])
        for a in plan["actions_to_create"]:
            new_id = int(client.execute_kw("ir.actions.act_window", "create", [{
                "name": a["name"], "res_model": a["res_model"], "view_mode": "list,form" if plan["to_major"] >= 18 else "tree,form",
                "domain": f"[('{a['link_field']}', '=', active_id)]", "context": f"{{'default_{a['link_field']}': active_id}}"}]))
            created_actions.append(new_id)
            action_map[a["id"]] = new_id
        arch = vp.rewrite_action_ids(plan["arch"], action_map) if action_map else plan["arch"]
        result = publish_layer_arch(client, db, connection_id, model, vt, base_id, arch,
                                    [f"Imported a layout package ({plan['steps']} changes)"], action="import")
    except (HTTPException, *ODOO_ERRORS, ve.EngineError, IndexError) as exc:
        for aid in created_actions:
            try:
                client.execute_kw("ir.actions.act_window", "unlink", [[aid]])
            except ODOO_ERRORS:
                pass
        for fid in reversed(created_fields):
            try:
                client.execute_kw("ir.model.fields", "unlink", [[fid]])
            except ODOO_ERRORS:
                pass
        if created_screen:
            try:
                client.execute_kw("ir.ui.view", "unlink", [[created_screen]])
            except ODOO_ERRORS:
                pass
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, ve.EngineError):
            raise _engine_error(exc) from exc
        if isinstance(exc, IndexError):
            raise HTTPException(status_code=404, detail=f"{model} isn't in this database.") from exc
        raise _odoo_error(exc) from exc
    return {**result, "fields_created": [d["name"] for d in plan["fields_to_create"]], "screen_created": created_screen,
            "actions_created": len(created_actions)}
