"""Builders stage 2d endpoints (the 20 approved follow-up ideas).

Same rules as 2c: Odoo's own screens are never written; every publish is a
named Ingenium layer, checked against what Odoo shows; AI proposes, code
checks; anything sent outside goes only where the user typed it.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import view_engine as ve
from app import view_engine_2c as v2
from app import view_engine_2d as v2d
from app import view_engine_pdf as vpdf
from app import view_engine_store as vs
from app.db import get_db
from app.db_models import ViewBuilderItem
from app.routers import view_engine_2c as r2c
from app.routers.view_engine import (
    ODOO_ERRORS,
    _check_model,
    _client,
    _compile_kwargs,
    _engine_error,
    _fields_get,
    _find_layer,
    _get_views,
    _major,
    _odoo_error,
    _stock_hashes,
    _vt,
)
from app.routers.view_engine_studio import ScreenRef, _counts, _rich_fields, _screen

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connections/{connection_id}/views/engine", tags=["view-engine-2d"])
reports_router = APIRouter(prefix="/connections/{connection_id}/reports/engine", tags=["view-engine-2d"])
emails_router = APIRouter(prefix="/connections/{connection_id}/emails/engine", tags=["view-engine-2d"])
GLOBAL = "__global__"  # items shared by every connection (brand presets)
v2d.register_extra_starters()


def _safe(fn, default):  # noqa: ANN001, ANN202
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


class ItemRef(BaseModel):
    item_id: str


# 2. What changed ------------------------------------------------------------------

@router.post("/2d/approvals/diff")
def approval_diff(connection_id: str, body: ItemRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = vs.get_item(db, connection_id, body.item_id)
    if not row or row.kind not in {"approval", "schedule"}:
        raise HTTPException(status_code=404, detail="That request doesn't exist.")
    p = vs.item_out(row)["payload"]
    if p.get("action"):
        return {"changes": [{"kind": "changed", "node": "", "text": t} for t in p.get("summary") or []],
                "note": "This is an upgrade fix or a package import; Ingenium shows its summary."}
    client = _client(connection_id, db)
    view = _get_views(client, p["model"], p["view_type"], p.get("view_id"))
    fields = _fields_get(client, p["model"])
    try:
        before = ve.normalize(view["arch"], fields).tree
        res = ve.compile_ops(view["arch"], fields, p["ops"], **_compile_kwargs(client, fields, p["ops"], p["model"]))
        after = ve.normalize(res.expected_arch, fields).tree
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    changes = v2d.tree_diff(before, after)
    return {"changes": changes, "note": f"{len(changes)} difference{'s' if len(changes) != 1 else ''} between the screen now and after approval."}


# 3. Approvers per record type -----------------------------------------------------

class ApproversBody(BaseModel):
    approvers: dict[str, list[str]]


@router.post("/2d/approvals/approvers")
def set_approvers(connection_id: str, body: ApproversBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        clean = v2d.clean_approvers(body.approvers)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    vs.save_item(db, connection_id=connection_id, kind="policy", key="approvers", name="Approvers", payload={"approvers": clean}, replace_key=True)
    return {"ok": True, "approvers": clean}


@router.post("/2d/approvals/approvers/get")
def get_approvers(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"approvers": r2c.approvers_map(db, connection_id)}


# 4. Pause scheduled publishing ----------------------------------------------------

class PauseBody(BaseModel):
    start: str
    end: str
    reason: str = Field(default="Odoo upgrade", max_length=200)


@router.post("/2d/pause/set")
def pause_set(connection_id: str, body: PauseBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        s, e = datetime.fromisoformat(body.start), datetime.fromisoformat(body.end)
        if s.tzinfo is None or e.tzinfo is None:
            raise ve.EngineError("The times need a time zone.")
        v2d.check_pause(s, e, datetime.now(UTC))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Those times couldn't be read.") from exc
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    row = vs.save_item(db, connection_id=connection_id, kind="pause", key="schedules", name=body.reason,
                       payload={"start": s.astimezone(UTC).isoformat(), "end": e.astimezone(UTC).isoformat(), "reason": body.reason})
    return {"ok": True, "item_id": row.id}


@router.post("/2d/pause/list")
def pause_list(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    now = datetime.now(UTC)
    items = [vs.item_out(r) for r in vs.list_items(db, connection_id, "pause")]
    items = [i for i in items if datetime.fromisoformat(i["payload"]["end"]) > now]
    act = v2d.active_pause([i["payload"] for i in items], now)
    return {"pauses": items, "paused_now": bool(act), "note": f"Scheduled changes wait until {act['end']}." if act else None}


@router.post("/2d/pause/clear")
def pause_clear(connection_id: str, body: ItemRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = vs.get_item(db, connection_id, body.item_id)
    if not row or row.kind != "pause":
        raise HTTPException(status_code=404, detail="That pause doesn't exist.")
    p = vs.item_out(row)["payload"]
    vs.update_item(db, row, {**p, "end": datetime.now(UTC).isoformat(), "cleared": True})
    return {"ok": True}


# 6. Number tiles -------------------------------------------------------------------

class TileSpec(BaseModel):
    model: str
    measure: str = "__count"
    date_field: str
    period: str = "month"
    label: str = Field(default="", max_length=80)


def _total(client: Any, model: str, domain: list[Any], measure: str) -> float:
    if measure == "__count":
        return float(client.execute_kw(model, "search_count", [domain]))
    if _major(client) >= 19:
        rows = client.execute_kw(model, "formatted_read_group", [domain], {"groupby": [], "aggregates": [f"{measure}:sum"]})
        return float((rows or [{}])[0].get(f"{measure}:sum") or 0)
    rows = client.execute_kw(model, "read_group", [domain, [f"{measure}:sum"], []], {"lazy": True})
    return float((rows or [{}])[0].get(measure) or 0)


def _tile_value(client: Any, spec: TileSpec) -> dict[str, Any]:
    model = _check_model(spec.model)
    fields = _rich_fields(client, model)
    dmeta = fields.get(spec.date_field) or {}
    if dmeta.get("type") not in {"date", "datetime"} or dmeta.get("store") is False:
        raise HTTPException(status_code=422, detail="Pick a saved date to compare periods.")
    if spec.measure != "__count" and spec.measure not in {m["name"] for m in v2.measure_options(fields)}:
        raise HTTPException(status_code=422, detail="That number can't be added up.")
    try:
        cs, ce, ps, pe = v2d.period_bounds(spec.period, date.today())
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    f = spec.date_field
    try:
        cur = _total(client, model, [(f, ">=", cs.isoformat()), (f, "<", ce.isoformat())], spec.measure)
        prev = _total(client, model, [(f, ">=", ps.isoformat()), (f, "<", pe.isoformat())], spec.measure)
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    label = spec.label or (f"{fields[spec.measure].get('string')}" if spec.measure != "__count" else f"Number of {model}")
    return {"label": label, "value": cur, "previous": prev, "change": v2d.change_text(cur, prev, spec.period),
            "period": spec.period, "from": cs.isoformat(), "to": ce.isoformat()}


@router.post("/2d/tiles/preview")
def tile_preview(connection_id: str, body: TileSpec, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _tile_value(_client(connection_id, db), body)


@router.post("/2d/tiles/save")
def tile_save(connection_id: str, body: TileSpec, db: Session = Depends(get_db)) -> dict[str, Any]:
    out = _tile_value(_client(connection_id, db), body)
    row = vs.save_item(db, connection_id=connection_id, kind="tile", key=body.model, name=out["label"], payload=body.model_dump())
    return {"ok": True, "item_id": row.id, **out}


@router.post("/2d/tiles/list")
def tile_list(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    out = []
    for r in vs.list_items(db, connection_id, "tile"):
        i = vs.item_out(r)
        try:
            out.append({"id": i["id"], **_tile_value(client, TileSpec(**i["payload"]))})
        except HTTPException as exc:
            out.append({"id": i["id"], "label": i["name"], "error": r2c._detail_text(exc, "Couldn't count.")})
    return {"tiles": out}


@router.post("/2d/tiles/delete")
def tile_delete(connection_id: str, body: ItemRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = vs.get_item(db, connection_id, body.item_id)
    if not row or row.kind != "tile":
        raise HTTPException(status_code=404, detail="That tile doesn't exist.")
    db.delete(row)
    db.commit()
    return {"ok": True}


# 7. Hide fields nobody fills in ---------------------------------------------------

@router.post("/2d/hide-unused")
def hide_unused(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt, view, fields, tree, _tag = _screen(client, body)
    counts, total = _counts(client, model, tree, fields)
    ops = v2d.unused_field_ops(tree, fields, counts, total)
    labels = [o.pop("label") for o in ops]
    note = ("Needs at least 20 records to tell." if total < 20 else
            f"{len(ops)} field{'s are' if len(ops) != 1 else ' is'} empty on all {total} records." if ops else "Every field on this screen is used.")
    return {"ops": ops, "labels": labels, "total": total, "note": note}


# 8. Stage checklist (own layer) and shared own-layer publish -------------------------

def _own_layer(client: Any, db: Session, connection_id: str, *, model: str, vt: str, view: dict[str, Any], name: str, arch: str,
               summary: str, expect: list[str]) -> dict[str, Any]:
    r2c.require_approval_ok(db, connection_id)  # stage 2e: own layers follow the approval rule too
    with r2c.role_layers_paused(client, db, connection_id, model, int(view["id"])) as notes:
        res = _own_layer_write(client, db, connection_id, model=model, vt=vt, view=view, name=name, arch=arch, summary=summary, expect=expect)
    return {**res, "role_layouts": notes} if notes else res


def _own_layer_write(client: Any, db: Session, connection_id: str, *, model: str, vt: str, view: dict[str, Any], name: str, arch: str,
                     summary: str, expect: list[str]) -> dict[str, Any]:
    existing = _find_layer(client, name)
    previous = str(existing.get("arch") or "") if existing and existing.get("active") else None
    stock_before = _stock_hashes(client, model)
    created, lid = False, (int(existing["id"]) if existing else None)
    try:
        if lid is None:
            lid = int(client.execute_kw("ir.ui.view", "create", [{"name": name, "model": model, "type": vt, "inherit_id": int(view["id"]),
                                                                  "mode": "extension", "priority": v2.SCOPED_PRIORITY, "arch": arch, "active": False}]))
            created = True
        else:
            client.execute_kw("ir.ui.view", "write", [[lid], {"arch": arch, "active": False}])
        client.execute_kw("ir.ui.view", "write", [[lid], {"active": True}])
    except ODOO_ERRORS as exc:
        r2c._scoped_rollback(client, lid, created, previous)
        raise _odoo_error(exc) from exc
    after = _get_views(client, model, vt, None)
    if any(m not in after["arch"] for m in expect) or _stock_hashes(client, model) != stock_before:
        r2c._scoped_rollback(client, lid, created, previous)
        raise HTTPException(status_code=409, detail="Odoo shows this differently, so nothing was published.")
    vid = vs.record_version(db, connection_id=connection_id, kind="view", model=model, view_type=vt, layer_name=name, layer_view_id=lid,
                            action="publish", summary=[summary], layer_arch=arch, layer_active=True, combined_arch=None, odoo_major=_major(client))
    return {"ok": True, "layer_view_id": lid, "version_id": vid}


@router.post("/2d/checklist/publish")
def checklist_publish(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    sb = r2c.save_blockers(connection_id, body, db)
    model, vt, view, fields, _tree, _tag = _screen(client, body)
    if not sb.get("stage_field"):
        raise HTTPException(status_code=422, detail="This screen has no stages, so there's no checklist to show.")
    try:
        arch = v2d.checklist_arch(sb["stage_field"], sb["stages"], fields)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    name = f"{v2d.CHECKLIST_PREFIX}_{model.replace('.', '_')}_{vt}_{int(view['id'])}"
    res = _own_layer(client, db, connection_id, model=model, vt=vt, view=view, name=name, arch=arch,
                     summary="Stage checklist on the record", expect=[f"{v2d.CHECKLIST_PREFIX}_box"])
    return {**res, "lines": arch.count("<div invisible=")}


@router.post("/2d/checklist/remove")
def checklist_remove(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    view = _get_views(client, model, vt, body.view_id)
    layer = _find_layer(client, f"{v2d.CHECKLIST_PREFIX}_{model.replace('.', '_')}_{vt}_{int(view['id'])}")
    if not layer:
        raise HTTPException(status_code=404, detail="There's no checklist on this screen.")
    try:
        client.execute_kw("ir.ui.view", "unlink", [[int(layer["id"])]])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    return {"ok": True}


# 10. Accessibility fixes -------------------------------------------------------------

@router.post("/2d/a11y/fix")
def a11y_fix(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    _model, _vt2, view, fields, tree, _tag = _screen(client, body)
    ops = v2d.a11y_fix_ops(tree, fields, v2d.button_words(str(view.get("arch") or "<form/>")))
    why = [o.pop("why") for o in ops]
    return {"ops": ops, "why": why, "note": "Added to your draft. Check them, then publish." if ops else "Nothing to fix automatically."}


# 11. Sample data per industry ---------------------------------------------------------

class IndustrySampleBody(ScreenRef):
    industry: str
    count: int = 3


@router.post("/2d/sample/industries")
def sample_industries() -> dict[str, Any]:
    return {"industries": sorted(v2d.INDUSTRY_WORDS), "note": v2.SAMPLE_NOTE}


@router.post("/2d/sample")
def sample_industry(connection_id: str, body: IndustrySampleBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    _model, _vt2, _view, fields, tree, _tag = _screen(client, body)
    names = list(dict.fromkeys(n.get("name") for n, _h in v2.screen_field_nodes(tree) if n.get("name")))
    try:
        recs = v2d.industry_sample_records(names, fields, body.industry, body.count)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    return {"records": recs, "label": f"Sample ({body.industry})", "note": v2.SAMPLE_NOTE}


# 12. Brand presets (shared across databases) --------------------------------------------

class PresetSaveBody(BaseModel):
    company_id: int
    name: str = Field(min_length=1, max_length=80)


@reports_router.post("/2d/brand/presets/save")
def preset_save(connection_id: str, body: PresetSaveBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    rows = client.execute_kw("res.company", "read", [[body.company_id]], {"fields": ["primary_color", "secondary_color", "font", "external_report_layout_id"]})
    if not rows:
        raise HTTPException(status_code=404, detail="That company isn't in this database.")
    lay = rows[0].get("external_report_layout_id")
    xmlid = None
    if lay:
        d = client.execute_kw("ir.model.data", "search_read", [[("model", "=", "ir.ui.view"), ("res_id", "=", int(lay[0]))]], {"fields": ["module", "name"], "limit": 1})
        xmlid = f"{d[0]['module']}.{d[0]['name']}" if d else None
    preset = v2d.preset_from_company(rows[0], xmlid)
    row = vs.save_item(db, connection_id=GLOBAL, kind="brand_preset", key=body.name.strip().lower(), name=body.name.strip(), payload=preset, replace_key=True)
    return {"ok": True, "item_id": row.id, "preset": preset}


@reports_router.post("/2d/brand/presets/list")
def preset_list(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"presets": [vs.item_out(r) for r in vs.list_items(db, GLOBAL, "brand_preset")]}


class PresetApplyBody(BaseModel):
    item_id: str
    company_id: int


@reports_router.post("/2d/brand/presets/apply")
def preset_apply(connection_id: str, body: PresetApplyBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.routers.view_engine_reports2 import BrandBody, brand_apply

    row = vs.get_item(db, GLOBAL, body.item_id)
    if not row or row.kind != "brand_preset":
        raise HTTPException(status_code=404, detail="That preset doesn't exist.")
    p = vs.item_out(row)["payload"]
    client = _client(connection_id, db)
    values: dict[str, Any] = {k: p[k] for k in ("primary_color", "secondary_color", "font") if p.get(k)}
    skipped = []
    if p.get("layout_xmlid"):
        mod, nm = p["layout_xmlid"].split(".", 1)
        d = client.execute_kw("ir.model.data", "search_read", [[("module", "=", mod), ("name", "=", nm), ("model", "=", "ir.ui.view")]], {"fields": ["res_id"], "limit": 1})
        if d:
            values["external_report_layout_id"] = int(d[0]["res_id"])
        else:
            skipped.append("The document layout isn't installed in this database, so it was left as is.")
    out = brand_apply(connection_id, BrandBody(company_id=body.company_id, values=values), db)
    return {**out, "skipped": skipped}


# 13. Send a real test email ---------------------------------------------------------------

class TestSendBody(BaseModel):
    template_id: int
    record_id: int
    to: str = Field(min_length=3, max_length=200)


@emails_router.post("/2d/test-send")
def email_test_send(connection_id: str, body: TestSendBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Sends only to the one address typed in, never to the template's recipients."""
    import re

    from app.routers.view_engine_reports2 import _render_email, _template

    if not re.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+", body.to.strip()):
        raise HTTPException(status_code=422, detail="Enter one email address.")
    client = _client(connection_id, db)
    tpl = _template(client, body.template_id)
    if not tpl.get("model"):
        raise HTTPException(status_code=422, detail="That template isn't tied to a record type.")
    html = _render_email(client, body.template_id, str(tpl["model"]), int(body.record_id))["html"]
    res = r2c.send_via_odoo(client, body.to.strip(), f"[Test] {tpl.get('name') or 'Email'}", "", html=html)
    if res["status"] == "log_only":
        res["note"] = "This Odoo has no outgoing mail server, so the test couldn't be sent. Add one in Odoo first."
    return {"to": body.to.strip(), **res}


# 14. Report from a photo or scan (picture reading) -------------------------------------------

def read_picture(raw: bytes, mime: str) -> list[str]:
    """AI reads the picture into text lines; the existing document flow maps them to real fields."""
    from app import view_engine_ai as vai

    prov = vai._provider()
    schema = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "string"}}}, "required": ["lines"]}
    try:
        text = prov.generate_json("Copy every line of text you can read in this document image, top to bottom.",
                                  system="You transcribe document images. Copy text exactly; don't add anything.", timeout_s=60.0,
                                  temperature=0.0, format_schema=schema, image_bytes=raw, mime_type=mime)
    except TypeError as exc:
        raise vai.AIUnavailable("Picture reading isn't available with this workspace's assistant. Upload a PDF that has text instead.") from exc
    except Exception as exc:  # noqa: BLE001
        raise vai.AIUnavailable(f"The picture couldn't be read ({str(exc)[:100]}).") from exc
    data = json.loads(text) if isinstance(text, str) else text
    lines = data.get("lines") if isinstance(data, dict) else data if isinstance(data, list) else None
    return [str(x)[:300] for x in (lines or []) if str(x).strip()][:400]


# 16. Digest to Slack / Teams ------------------------------------------------------------------

class ChatBody(BaseModel):
    url: str = Field(default="", max_length=600)
    on: bool = True


@router.post("/2d/digest/chat")
def digest_chat(connection_id: str, body: ChatBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    if not body.on:
        vs.save_item(db, connection_id=connection_id, kind="digest_chat", key="weekly", name="Chat digest", payload={"on": False}, replace_key=True)
        return {"ok": True, "on": False}
    try:
        kind = v2d.check_webhook(body.url)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    vs.save_item(db, connection_id=connection_id, kind="digest_chat", key="weekly", name="Chat digest",
                 payload={"on": True, "url": body.url.strip(), "kind": kind}, replace_key=True)
    return {"ok": True, "on": True, "kind": kind, "url": v2d.mask_url(body.url.strip())}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None  # a webhook that redirects (to a sign-in page) didn't take the message


def send_chat(p: dict[str, Any], title: str, text: str) -> int:
    v2d.check_webhook(p["url"])  # only the configured Slack/Teams host, checked again at send time
    data = json.dumps(v2d.chat_payload(p["kind"], title, text)).encode()
    req = urllib.request.Request(p["url"], data=data, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.build_opener(_NoRedirect).open(req, timeout=15) as r:  # host checked by check_webhook
        body = r.read(200).decode("utf-8", "replace").strip()
        status = int(r.status)
    if not v2d.chat_accepted(p["url"], status, body):
        raise ValueError(f"it answered {status}" + (f": {body[:80]}" if body else " without confirming"))
    return status


def _chat_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        body = (exc.read() or b"")[:120].decode("utf-8", "replace").strip()
        return f"it answered {exc.code}" + (f": {body}" if body else "")
    if isinstance(exc, urllib.error.URLError):
        return f"it couldn't be reached ({str(exc.reason)[:80]})"
    return str(exc)[:120]


def chat_settings(db: Session, connection_id: str) -> dict[str, Any] | None:
    rows = vs.list_items(db, connection_id, "digest_chat", "weekly")
    p = vs.item_out(rows[0])["payload"] if rows else {}
    return p if p.get("on") and p.get("url") else None


@router.post("/2d/digest/chat/send-now")
def digest_chat_send(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    p = chat_settings(db, connection_id)
    if not p:
        raise HTTPException(status_code=422, detail="Add a Slack or Teams link first.")
    d = r2c.build_digest(db, connection_id, 7)
    name = {"teams": "Teams", "teams_workflow": "Teams Workflows"}.get(p["kind"], "Slack")
    try:  # a test goes only where the user configured it, only when they ask
        status = send_chat(p, "[Test] Weekly screen changes", d["text"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail={"message": f"{name} didn't accept the test message: {_chat_error(exc)}. Check the link in {name}.",
                                                     "sent_to": v2d.mask_url(p["url"])}) from exc
    return {"ok": True, "kind": p["kind"], "status": status, "sent_to": v2d.mask_url(p["url"]), "note": f"Test sent to {name}."}


# 17. Comments pinned to screen items ------------------------------------------------------------

class CommentBody(ScreenRef):
    node: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2000)


def _screen_key(body: ScreenRef) -> str:
    return f"{_check_model(body.model)}|{_vt(body.view_type)}|{int(body.view_id or 0)}"


@router.post("/2d/comments/add")
def comment_add(connection_id: str, body: CommentBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    who = r2c._who(request)
    row = vs.save_item(db, connection_id=connection_id, kind="comment", key=_screen_key(body), name=body.text[:80],
                       payload={"node": body.node, "text": body.text, "by": who.get("email") or "someone", "at": datetime.now(UTC).isoformat(), "resolved": False})
    return {"ok": True, "item_id": row.id}


@router.post("/2d/comments/list")
def comment_list(connection_id: str, body: ScreenRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    items = [vs.item_out(r) for r in vs.list_items(db, connection_id, "comment", _screen_key(body))]
    return {"comments": [i for i in items if not i["payload"].get("resolved")], "resolved": sum(1 for i in items if i["payload"].get("resolved"))}


@router.post("/2d/comments/resolve")
def comment_resolve(connection_id: str, body: ItemRef, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = vs.get_item(db, connection_id, body.item_id)
    if not row or row.kind != "comment":
        raise HTTPException(status_code=404, detail="That comment doesn't exist.")
    p = vs.item_out(row)["payload"]
    vs.update_item(db, row, {**p, "resolved": True, "resolved_by": r2c._who(request).get("email") or "someone"})
    return {"ok": True}


# 18. Move a published screen to another database (with a fresh approval there) ------------------

class PromoteBody(ScreenRef):
    target_connection_id: str
    replace: bool = False  # the other database already has Ingenium changes on this screen; moving replaces them


@router.post("/2d/promote")
def promote(connection_id: str, body: PromoteBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.odoo_service import get_connection_or_404
    from app.routers import view_engine_builder as vb

    if body.target_connection_id == connection_id:
        raise HTTPException(status_code=422, detail="Pick a different database to move it to.")
    target = get_connection_or_404(db, body.target_connection_id)
    pkg = vb.package_export(connection_id, ScreenRef(model=body.model, view_type=body.view_type, view_id=body.view_id), db)
    package = pkg.get("package") or pkg
    check = vb.package_check(body.target_connection_id, vb.PackageBody(package=package), db)
    if check.get("has_changes_here") and not body.replace:
        raise HTTPException(status_code=409, detail={"message": "That database already has Ingenium changes on this screen. Moving replaces them. "
                                                                "Compare side by side, then confirm to ask anyway.", "needs_confirm": True})
    who = r2c._who(request)
    row = vs.save_item(db, connection_id=body.target_connection_id, kind="approval", key=f"package_import|{body.model}",
                       name=f"Move {body.model} {body.view_type} from {connection_id[:8]}", payload={
                           "action": "package_import", "action_payload": {"package": package, "replace": bool(body.replace)}, "model": body.model,
                           "summary": [f"Bring the {body.view_type} screen of {body.model} over from another database"],
                           "requested_by": who.get("email") or "someone", "requested_by_id": who.get("user_id"), "identity_verified": who["verified"],
                           "note": "", "status": "pending", "requested_at": datetime.now(UTC).isoformat(), "source_connection_id": connection_id})
    return {"ok": True, "item_id": row.id, "target": str(getattr(target, "name", "") or body.target_connection_id), "check": check,
            "note": "Waiting for approval in the other database. Nothing changes there until someone approves."}


class CompareBody(ScreenRef):
    target_connection_id: str


@router.post("/2d/promote/compare")
def promote_compare(connection_id: str, body: CompareBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Side by side: this screen here, the same screen in the other database now, and
    how it would look there after the move. Reads only; nothing changes anywhere."""
    from app.routers import view_engine_builder as vb

    if body.target_connection_id == connection_id:
        raise HTTPException(status_code=422, detail="Pick a different database to compare with.")
    src = _client(connection_id, db)
    tgt = _client(body.target_connection_id, db)
    model, vt = _check_model(body.model), _vt(body.view_type)
    pkg = vb.package_export(connection_id, ScreenRef(model=model, view_type=vt, view_id=body.view_id), db)["package"]
    sview = _get_views(src, model, vt, body.view_id)
    tview = _get_views(tgt, model, vt, None)
    sf, tf = _fields_get(src, model), _fields_get(tgt, model)
    s_tree = ve.normalize(sview["arch"], sf).tree
    t_tree = ve.normalize(tview["arch"], tf).tree
    plan = vb._package_plan(tgt, pkg)
    after_tree, problems = None, list(plan.get("problems") or [])
    if not problems and plan.get("arch"):
        try:
            after_tree = ve.normalize(ve.apply_inherit_local(tview["arch"], plan["arch"]), tf).tree
        except ve.EngineError as exc:
            problems.append(f"The changes don't fit the other database's screen: {exc}")
    replaces = bool(plan.get("has_changes_here"))
    changes = v2d.tree_diff(t_tree, after_tree) if after_tree is not None else []
    left = v2d.cross_diff(s_tree, after_tree) if after_tree is not None else []
    return {"source": {"major": _major(src), "items": v2d.outline(s_tree)},
            "target_now": {"major": _major(tgt), "items": v2d.outline(t_tree)},
            "target_after": {"items": v2d.outline(after_tree) if after_tree is not None else []},
            "changes": changes[:80], "still_different": left[:80], "problems": problems, "replaces": replaces,
            "note": ("This screen can't be moved there as it is. See the problems." if problems else
                     ("That database already has its own Ingenium changes on this screen; moving replaces them. 'After' shows the moved changes "
                      "on top of theirs, so items only their changes touched may change back. " if replaces else "")
                     + "Nothing changes until someone approves the move in the other database.")}


# 19. Layout tests end themselves -------------------------------------------------------------------

def run_due_abtests(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    vs._ensure_tables(db)
    n = 0
    for row in db.query(ViewBuilderItem).filter(ViewBuilderItem.kind == "abtest").all():
        p = vs.item_out(row)["payload"]
        if p.get("status") != "running":
            continue
        if p.get("last_eval") and now - datetime.fromisoformat(p["last_eval"]) < timedelta(hours=6):
            continue
        try:
            client = _client(row.connection_id, db)
            res = r2c._ab_results(client, p)
            end, why = v2d.test_should_end(res, datetime.fromisoformat(p["started_at"]), now)
            if end:
                r2c._abtest_stop(row.connection_id, r2c.ItemRef(item_id=row.id), db)
                row2 = vs.get_item(db, row.connection_id, row.id)
                vs.update_item(db, row2, {**vs.item_out(row2)["payload"], "ended_by_itself": why})
                n += 1
            else:
                vs.update_item(db, row, {**p, "last_eval": now.isoformat()})
        except Exception as exc:  # noqa: BLE001
            logger.warning("layout test check failed: %s", exc)
            db.rollback()
            try:  # don't retry a broken test every minute
                row = vs.get_item(db, row.connection_id, row.id)
                vs.update_item(db, row, {**vs.item_out(row)["payload"], "last_eval": now.isoformat(), "last_error": str(exc)[:200]})
            except Exception:  # noqa: BLE001
                db.rollback()
    return n


@router.post("/2d/abtest/evaluate")
def abtest_evaluate(connection_id: str, body: ItemRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = r2c._ab_row(db, connection_id, body.item_id)
    p = vs.item_out(row)["payload"]
    if p.get("status") != "running":
        raise HTTPException(status_code=409, detail="That test already stopped.")
    res = r2c._ab_results(_client(connection_id, db), p)
    end, why = v2d.test_should_end(res, datetime.fromisoformat(p["started_at"]), datetime.now(UTC))
    if end:
        r2c._abtest_stop(connection_id, r2c.ItemRef(item_id=row.id), db)
    return {"ended": end, "why": why or res.get("text"), "result": res}


# 20. Explain sheet as a PDF, in a chosen language ------------------------------------------------------

class ExplainExportBody(ScreenRef):
    lang: str = Field(default="en", max_length=12)


@router.post("/2d/explain/export")
def explain_export(connection_id: str, body: ExplainExportBody, db: Session = Depends(get_db)) -> Response:
    out = r2c.explain(connection_id, ScreenRef(model=body.model, view_type=body.view_type, view_id=body.view_id), db)
    steps = out["steps"]
    note = "Made by Ingenium from this database's screen."
    if body.lang and not body.lang.lower().startswith("en"):
        from app import view_engine_ai as vai

        try:
            got = vai._call(v2d.TRANSLATE_SYSTEM, {"target_language": body.lang, "steps": [{"title": s["title"], "text": s["text"]} for s in steps]},
                            v2d.TRANSLATE_SCHEMA, "explain_translate")
            tr = v2d.check_translation(steps, got)
        except vai.AIUnavailable:
            tr = None
        if tr:
            steps, note = tr, f"Translated by the assistant into {body.lang}; numbers checked against the original."
        else:
            note = f"The translation into {body.lang} couldn't be checked, so this sheet is in English."
    title = steps[0]["text"].split(".")[0] if steps else "Screen guide"
    pdf = vpdf.text_pdf(title, [(s["title"], s["text"]) for s in steps], note)
    if pdf is None:
        return Response(v2d.explain_html(title, steps, note + " Some letters can't go in a PDF here; print this page to save it."), media_type="text/html")
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="screen-guide.pdf"'})


# ticker hook ------------------------------------------------------------------------------------------------

def run_due(db: Session) -> dict[str, int]:
    return {"abtests": run_due_abtests(db)}


