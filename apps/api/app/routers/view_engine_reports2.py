"""Report and email designer, stage 2b.

Reports: blocks anywhere, line tables with totals, conditional blocks, QR /
barcode / signature / watermark / page breaks, page checks, language / currency
/ company preview, before/after compare, page numbers, brand once via Odoo's
document layout, starter gallery and saved block sets.
Emails: an Ingenium copy of a stock template (stock never edited) built from the
same blocks, previewed through Odoo's own composer.
"""

from __future__ import annotations

import base64
import re
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import view_engine as ve
from app import view_engine_report as vr
from app import view_engine_ai as vai
from app import view_engine_report_blocks as rb
from app import view_engine_store as vs
from app.db import get_db
from app.workspace_auth import require_app_auth
from app.odoo_service import OdooClientError
from app.routers.view_engine import (
    ODOO_ERRORS,
    _check_model,
    _client,
    _engine_error,
    _fields_get,
    _find_layer,
    _major,
    _odoo_error,
    _record_names,
    _render_html,
    _render_pdf,
    _report_context,
    _rollback,
    _view_hash,
)
from app.routers.view_engine_logic import _ids_in_condition, _report_http

reports_router = APIRouter(prefix="/connections/{connection_id}/reports/engine", tags=["view-engine"])
emails_router = APIRouter(prefix="/connections/{connection_id}/emails/engine", tags=["view-engine"])

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
LANG_RE = re.compile(r"^[a-z]{2,3}(_[A-Za-z0-9@]{2,10})?$")


def _b64(pdf: bytes) -> str:
    return base64.b64encode(pdf).decode("ascii")


def _related(client: Any, fields: dict[str, Any], names: set[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for n in names:
        meta = fields.get(n) or {}
        if meta.get("type") in {"one2many", "many2many"} and meta.get("relation"):
            try:
                out[n] = client.execute_kw(meta["relation"], "fields_get", [], {"attributes": ["string", "type"]}) or {}
            except ODOO_ERRORS:
                out[n] = {}
    return out


def _line_fields_used(placements: Any) -> set[str]:
    out: set[str] = set()
    for p in placements or []:
        for b in (p or {}).get("blocks") or []:
            if isinstance(b, dict) and b.get("type") == "line_table" and isinstance(b.get("field"), str):
                out.add(b["field"])
    return out


def _report_setup(client: Any, report_id: int) -> dict[str, Any]:
    ctx = _report_context(client, report_id)
    model = str(ctx["report"]["model"])
    fields = _fields_get(client, model)
    ctx["model"] = model
    ctx["fields"] = fields
    ctx["slots2"] = rb.slots_anywhere(ctx["doc_arch"], fields, ctx["record_var"])
    return ctx


def _validated(client: Any, ctx: dict[str, Any], placements: Any) -> list[dict[str, Any]]:
    related = _related(client, ctx["fields"], _line_fields_used(placements))
    try:
        return rb.validate_placements(placements, ctx["slots2"], ctx["fields"], related, record_names=_condition_names(client, ctx["fields"], placements))
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc


def _line_markers(client: Any, ctx: dict[str, Any], record_id: int) -> list[str]:
    """Names of the first and last line of the record's line lists the document prints."""
    var, fields = ctx["record_var"], ctx["fields"]
    used = {m for m in re.findall(rf"\b{var}\.([a-z_][a-z0-9_]*)", ctx["doc_arch"]) if (fields.get(m) or {}).get("type") == "one2many"}
    if not used:
        return []
    try:
        row = client.execute_kw(ctx["model"], "read", [[int(record_id)]], {"fields": sorted(used)})[0]
    except (ODOO_ERRORS, IndexError):
        return []
    out: list[str] = []
    for n in sorted(used):
        ids = row.get(n) or []
        if len(ids) < 2:
            continue
        rel = fields[n].get("relation")
        try:
            names = client.execute_kw(rel, "read", [[ids[0], ids[-1]]], {"fields": ["display_name"]})
        except ODOO_ERRORS:
            continue
        out += [str(r.get("display_name") or "").splitlines()[0][:40] for r in names if r.get("display_name")]
    return [m for m in out if len(m) >= 4]


def _report_layout_item(db: Session, connection_id: str, doc_key: str) -> dict[str, Any] | None:
    rows = vs.list_items(db, connection_id, "report_layout", doc_key)
    return vs.item_out(rows[0])["payload"] if rows else None


# ----------------------------------------------------------------------------
# Reports
# ----------------------------------------------------------------------------

class ReportRef(BaseModel):
    report_id: int


class LinesBody(ReportRef):
    field: str


class PlacementsBody(ReportRef):
    record_id: int
    placements: list[dict[str, Any]] = Field(default_factory=list)
    lang: str | None = None
    company_id: int | None = None
    published_pages: int | None = None


@reports_router.post("/layout/load")
def layout_load(connection_id: str, body: ReportRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    ctx = _report_setup(client, body.report_id)
    layer = _find_layer(client, vr.report_layer_name(ctx["document"]["key"]))
    stored = _report_layout_item(db, connection_id, ctx["document"]["key"])
    active = bool(layer and layer.get("active"))
    return {
        "major": _major(client), "report": ctx["report"], "document": ctx["document"], "record_var": ctx["record_var"],
        "slots": ctx["slots2"], "placements": (stored or {}).get("placements") if active else [],
        "earlier_changes": active and not stored,
        "line_fields": sorted(n for n, m in ctx["fields"].items() if m.get("type") in {"one2many", "many2many"}),
        "layer": {"id": int(layer["id"]), "active": active} if layer else None,
        "blocks": sorted(rb.BLOCK_TYPES),
    }


@reports_router.post("/lines-fields")
def lines_fields(connection_id: str, body: LinesBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    ctx = _report_setup(client, body.report_id)
    return {"field": body.field, "columns": _line_columns(client, ctx["fields"], body.field)}


def _line_columns(client: Any, fields: dict[str, Any], field: str) -> list[dict[str, Any]]:
    """Columns a lines table can show for one one2many/many2many field."""
    rel = _related(client, fields, {field}).get(field)
    if rel is None:
        raise HTTPException(status_code=422, detail="That isn't a list of lines on this record type.")
    return [{"name": n, "label": str(m.get("string") or n), "type": m.get("type"), "can_total": m.get("type") in rb.NUMERIC}
            for n, m in sorted(rel.items(), key=lambda kv: str(kv[1].get("string") or kv[0]))
            if m.get("type") not in {"binary", "one2many", "many2many", "properties", "json"} and not n.startswith("__")]


def _draft_render(client: Any, ctx: dict[str, Any], placements: list[dict[str, Any]], record_id: int,
                  lang: str | None, company_id: int | None) -> tuple[bytes, str]:
    token = secrets.token_hex(8)
    layer = _find_layer(client, vr.report_layer_name(ctx["document"]["key"]))
    hide = rb.published_markers(str(layer.get("arch") or "")) if layer and layer.get("active") else []
    try:
        arch = rb.compile_layer(placements, ctx["slots2"], ctx["record_var"], ctx["fields"], token=token, hide_published=hide)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    rctx: dict[str, Any] = {"ingenium_draft": token}
    if lang:
        if not LANG_RE.match(lang):
            raise HTTPException(status_code=422, detail="That language isn't valid.")
        rctx["lang"] = lang
    if company_id:
        rctx["allowed_company_ids"] = [int(company_id)]
    draft_id: int | None = None
    try:
        if placements or hide:
            draft_id = int(client.execute_kw("ir.ui.view", "create", [{
                "name": f"{ve.LAYER_PREFIX} draft {ctx['document']['key']} {token}", "type": "qweb",
                "inherit_id": int(ctx["document"]["view_id"]), "mode": "extension", "priority": ve.LAYER_PRIORITY + 5,
                "arch": arch, "active": True}]))
        name = str(ctx["report"]["report_name"])
        pdf = _report_http(client, "pdf", name, record_id, rctx, str(ctx["model"]))
        html = _report_http(client, "html", name, record_id, rctx, str(ctx["model"])).decode("utf-8", "replace")
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    finally:
        if draft_id:
            try:
                client.execute_kw("ir.ui.view", "unlink", [[draft_id]])
            except OdooClientError:
                pass
    if not pdf.startswith(b"%PDF"):
        raise HTTPException(status_code=502, detail="Odoo didn't return a PDF. Check the record can be printed.")
    return pdf, html


@reports_router.post("/layout/draft")
def layout_draft(connection_id: str, body: PlacementsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Real PDF of the unsaved layout (only this request sees it), with page checks."""
    client = _client(connection_id, db)
    ctx = _report_setup(client, body.report_id)
    placements = _validated(client, ctx, body.placements) if body.placements else []
    pdf, html = _draft_render(client, ctx, placements, body.record_id, body.lang, body.company_id)
    missing = [t for t in rb.expected_texts(placements) if t not in html]
    checks = rb.page_checks(pdf, line_markers=_line_markers(client, ctx, body.record_id), published_pages=body.published_pages)
    return {"ok": not missing, "pages": vr.pdf_page_count(pdf), "missing": missing, "checks": checks, "content_base64": _b64(pdf)}


@reports_router.post("/layout/compare")
def layout_compare(connection_id: str, body: PlacementsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Published print vs. this draft on the same record: both PDFs plus what text moved."""
    client = _client(connection_id, db)
    ctx = _report_setup(client, body.report_id)
    placements = _validated(client, ctx, body.placements) if body.placements else []
    before = _render_pdf(client, body.report_id, body.record_id)
    after, _html = _draft_render(client, ctx, placements, body.record_id, body.lang, body.company_id)
    return {"before_base64": _b64(before), "after_base64": _b64(after), "diff": rb.compare_texts(before, after),
            "checks": rb.page_checks(after, line_markers=_line_markers(client, ctx, body.record_id), published_pages=vr.pdf_page_count(before))}


@reports_router.post("/layout/compare-visual")
def layout_compare_visual(connection_id: str, body: PlacementsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Published print vs. this draft as page pictures with changes highlighted (green new, red gone)."""
    client = _client(connection_id, db)
    ctx = _report_setup(client, body.report_id)
    placements = _validated(client, ctx, body.placements) if body.placements else []
    before = _render_pdf(client, body.report_id, body.record_id)
    after, _html = _draft_render(client, ctx, placements, body.record_id, body.lang, body.company_id)
    try:
        visual = rb.visual_compare(before, after)
    except Exception as exc:  # noqa: BLE001 - a broken PDF must not break the designer
        raise HTTPException(status_code=502, detail="The pages couldn't be turned into pictures for comparing.") from exc
    return {"visual": visual, "diff": rb.compare_texts(before, after)}


@reports_router.post("/layout/publish")
def layout_publish(connection_id: str, body: PlacementsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    ctx = _report_setup(client, body.report_id)
    placements = _validated(client, ctx, body.placements)
    try:
        arch = rb.compile_layer(placements, ctx["slots2"], ctx["record_var"], ctx["fields"])
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
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
                "priority": ve.LAYER_PRIORITY, "arch": arch, "active": False}]))
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
    missing = [t for t in rb.expected_texts(placements) if t not in html]
    stock_unchanged = stock_before == _view_hash(client, doc_id)
    if missing or not stock_unchanged:
        _rollback(client, layer_id, created, previous_arch)
        raise HTTPException(status_code=409, detail={"message": "Odoo's print doesn't show the change, so nothing was published.",
                                                     "missing": missing, "stock_unchanged": stock_unchanged})
    previous_layout = _report_layout_item(db, connection_id, ctx["document"]["key"])
    vs.save_item(db, connection_id=connection_id, kind="report_layout", key=ctx["document"]["key"], name=str(ctx["report"]["name"]),
                 payload={"placements": placements, "report_id": body.report_id}, replace_key=True)
    vs.record_version(db, connection_id=connection_id, kind="report", model=ctx["model"], view_type="qweb", layer_name=name,
                      layer_view_id=layer_id, action="publish", summary=[f"{len(p['blocks'])} blocks: {p['slot']}" for p in placements],
                      layer_arch=arch, layer_active=True, combined_arch=None, odoo_major=_major(client))
    return {"ok": True, "layer_view_id": layer_id, "previous_arch": previous_arch, "previous_placements": (previous_layout or {}).get("placements"),
            "layer_arch": arch, "pages": vr.pdf_page_count(pdf), "stock_unchanged": True,
            "checks": rb.page_checks(pdf, line_markers=_line_markers(client, ctx, body.record_id)), "content_base64": _b64(pdf)}


@reports_router.post("/variants")
def report_variants(connection_id: str, body: ReportRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Sample records to preview the print in each language, currency and company."""
    client = _client(connection_id, db)
    ctx = _report_setup(client, body.report_id)
    model, fields = ctx["model"], ctx["fields"]
    out: dict[str, list[dict[str, Any]]] = {"languages": [], "currencies": [], "companies": []}
    langs = client.execute_kw("res.lang", "search_read", [[("active", "=", True)]], {"fields": ["code", "name"]})
    for lg in langs:
        rid = None
        if (fields.get("partner_id") or {}).get("type") == "many2one":
            ids = client.execute_kw(model, "search", [[("partner_id.lang", "=", lg["code"]), *ctx.get("print_domain", [])]], {"limit": 1, "order": "id desc"})
            rid = ids[0] if ids else None
        out["languages"].append({"code": lg["code"], "name": lg["name"], "record_id": rid,
                                 "note": None if rid else "No record for a customer in this language; Odoo's print may still use the customer's language."})
    for key, fname in (("currencies", "currency_id"), ("companies", "company_id")):
        if (fields.get(fname) or {}).get("type") != "many2one":
            continue
        rel = fields[fname]["relation"]
        values = client.execute_kw(rel, "search_read", [[]] if key == "companies" else [[("active", "=", True)]], {"fields": ["display_name"], "limit": 20})
        for v in values:
            ids = client.execute_kw(model, "search", [[(fname, "=", v["id"]), *ctx.get("print_domain", [])]], {"limit": 1, "order": "id desc"})
            if ids:
                out[key].append({"id": v["id"], "name": v["display_name"], "record_id": ids[0]})
    return out


# -- page numbers: on the company's chosen layout (shared by every document) --

class CompanyBody(BaseModel):
    company_id: int | None = None


def _company(client: Any, company_id: int | None) -> dict[str, Any]:
    dom = [("id", "=", int(company_id))] if company_id else []
    # Only the brand settings this Odoo version has (Odoo 20 dropped layout_background, for example).
    have = client.execute_kw("res.company", "fields_get", [list(BRAND_FIELDS)], {"attributes": ["type"]}) or {}
    rows = client.execute_kw("res.company", "search_read", [dom], {"fields": ["id", "name", *[f for f in BRAND_FIELDS if f in have]], "limit": 1})
    if not rows:
        raise HTTPException(status_code=404, detail="That company doesn't exist.")
    return rows[0]


def _layout_view(client: Any, company: dict[str, Any]) -> dict[str, Any]:
    vid = (company.get("external_report_layout_id") or [None])[0]
    if not vid:
        rows = client.execute_kw("ir.ui.view", "search_read", [[("key", "=", "web.external_layout_standard")]], {"fields": ["id", "key", "arch"], "limit": 1})
    else:
        rows = client.execute_kw("ir.ui.view", "read", [[int(vid)]], {"fields": ["id", "key", "arch"]})
    if not rows:
        raise HTTPException(status_code=404, detail="Odoo has no document layout for this company.")
    return rows[0]


def _shows_page_numbers(client: Any, arch: str, depth: int = 2) -> bool:
    """True when the layout, or a template it calls (Odoo 20 keeps the pager in
    web.external_layout_footer_content), prints <span class="page"/>."""
    if re.search(r'<span[^>]*class="page"', arch or ""):
        return True
    if depth <= 0:
        return False
    for key in dict.fromkeys(re.findall(r't-call="(web\.[\w.]+)"', arch or "")):
        rows = client.execute_kw("ir.ui.view", "search_read", [[("key", "=", key), ("type", "=", "qweb")]], {"fields": ["arch"], "limit": 1})
        if rows and _shows_page_numbers(client, str(rows[0].get("arch") or ""), depth - 1):
            return True
    return False


def _footer_expr(arch: str) -> str | None:
    """Where the footer is: a fixed class (Odoo 17-19) or a built class like t-attf-class="footer ..." (Odoo 20)."""
    if re.search(r'<div[^>]*\sclass="(?:[^"]*\s)?footer(?:\s[^"]*)?"', arch or ""):
        return "//div[hasclass('footer')]"
    if re.search(r'<div[^>]*\st-attf-class="footer[\s"]', arch or ""):
        return "//div[starts-with(@t-attf-class, 'footer')]"
    return None


@reports_router.post("/page-numbers/check")
def page_numbers_check(connection_id: str, body: CompanyBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    company = _company(client, body.company_id)
    lay = _layout_view(client, company)
    stock = _shows_page_numbers(client, str(lay.get("arch") or ""))
    layer = _find_layer(client, vr.report_layer_name(str(lay["key"])) + " page numbers")
    return {"layout": lay["key"], "stock_shows_numbers": stock, "ingenium_added": bool(layer and layer.get("active")),
            "message": "Odoo's layout already prints page numbers." if stock else "This layout doesn't print page numbers."}


class PageNumbersBody(CompanyBody):
    on: bool = True


@reports_router.post("/page-numbers/set")
def page_numbers_set(connection_id: str, body: PageNumbersBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    company = _company(client, body.company_id)
    lay = _layout_view(client, company)
    name = vr.report_layer_name(str(lay["key"])) + " page numbers"
    layer = _find_layer(client, name)
    if not body.on:
        if layer:
            client.execute_kw("ir.ui.view", "write", [[int(layer["id"])], {"active": False}])
        return {"ok": True, "on": False}
    if _shows_page_numbers(client, str(lay.get("arch") or "")):
        return {"ok": True, "on": True, "note": "Odoo's layout already prints page numbers, so nothing was added."}
    expr = _footer_expr(str(lay.get("arch") or ""))
    if not expr:
        raise HTTPException(status_code=422, detail="This layout has no footer to put page numbers in.")
    arch = (f"<data><xpath expr=\"{expr}\" position=\"inside\">"
            f'<div class="{ve.LAYER_PREFIX}_pagenum text-end small">Page <span class="page"/> / <span class="topage"/></div></xpath></data>')
    try:
        if layer:
            client.execute_kw("ir.ui.view", "write", [[int(layer["id"])], {"arch": arch, "active": True}])
            lid = int(layer["id"])
        else:
            lid = int(client.execute_kw("ir.ui.view", "create", [{"name": name, "type": "qweb", "inherit_id": int(lay["id"]), "mode": "extension",
                                                                  "priority": ve.LAYER_PRIORITY, "arch": arch, "active": True}]))
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    return {"ok": True, "on": True, "layer_view_id": lid}


# -- brand once (Odoo's own document layout settings on the company) --

BRAND_FIELDS = ("external_report_layout_id", "primary_color", "secondary_color", "font", "report_header", "report_footer", "layout_background")


class BrandBody(CompanyBody):
    values: dict[str, Any] = Field(default_factory=dict)


def _brand_values(client: Any, values: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    meta = client.execute_kw("base.document.layout", "fields_get", [], {"attributes": ["type", "selection"]}) or {}
    for k, v in (values or {}).items():
        if k not in BRAND_FIELDS or k not in meta:
            raise HTTPException(status_code=422, detail=f"'{k}' isn't a brand setting.")
        if k in {"primary_color", "secondary_color"}:
            if not (isinstance(v, str) and HEX_RE.match(v)):
                raise HTTPException(status_code=422, detail="Colours need to look like #1A2B3C.")
        elif k in {"font", "layout_background"}:
            allowed = {s[0] for s in meta[k].get("selection") or []}
            if v not in allowed:
                raise HTTPException(status_code=422, detail=f"Pick one of: {', '.join(sorted(allowed))}.")
        elif k == "external_report_layout_id":
            ok = client.execute_kw("report.layout", "search_count", [[("view_id", "=", int(v))]])
            if not ok:
                raise HTTPException(status_code=422, detail="That layout isn't one of Odoo's document layouts.")
            v = int(v)
        elif k in {"report_header", "report_footer"}:
            v = str(v or "")[:500]
            if re.search(r"[<>]", v):
                raise HTTPException(status_code=422, detail="Header and footer text can't contain code.")
        clean[k] = v
    return clean


@reports_router.post("/brand/options")
def brand_options(connection_id: str, body: CompanyBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    company = _company(client, body.company_id)
    layouts = client.execute_kw("report.layout", "search_read", [[]], {"fields": ["name", "view_id"]})
    meta = client.execute_kw("base.document.layout", "fields_get", [], {"attributes": ["type", "selection"]}) or {}
    return {"company": {k: company.get(k) for k in ("id", "name", *BRAND_FIELDS)},
            "layouts": [{"name": r["name"], "view_id": (r.get("view_id") or [None])[0]} for r in layouts],
            "fonts": [s[0] for s in (meta.get("font") or {}).get("selection") or []],
            "backgrounds": [s[0] for s in (meta.get("layout_background") or {}).get("selection") or []]}


@reports_router.post("/brand/preview")
def brand_preview(connection_id: str, body: BrandBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Odoo's own document-layout preview with these settings; nothing is saved."""
    client = _client(connection_id, db)
    company = _company(client, body.company_id)
    vals = _brand_values(client, body.values)
    before = _brand_snapshot(company)
    try:
        # Odoo only draws the preview for a chosen layout; a new database has none set yet.
        layout_view = vals.get("external_report_layout_id") or _m2o_id(company.get("external_report_layout_id")) or _standard_layout_view(client)
        rl = client.execute_kw("report.layout", "search", [[("view_id", "=", layout_view)]], {"limit": 1}) if layout_view else []
        rl = rl or client.execute_kw("report.layout", "search", [[]], {"limit": 1})
        wid = client.execute_kw("base.document.layout", "create", [{"company_id": company["id"], **vals, **({"report_layout_id": rl[0]} if rl else {})}])
        row = client.execute_kw("base.document.layout", "read", [[wid]], {"fields": ["preview"]})[0]
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    finally:
        # Nothing is saved: if Odoo wrote any setting through to the company, put it back.
        after = _brand_snapshot(_company(client, company["id"]))
        changed = {k: v for k, v in before.items() if after.get(k) != v}
        if changed:
            client.execute_kw("res.company", "write", [[company["id"]], changed])
    return {"html": str(row.get("preview") or "")}


def _m2o_id(v: Any) -> int | None:
    return int(v[0]) if isinstance(v, list) and v else (int(v) if isinstance(v, int) and not isinstance(v, bool) else None)


def _brand_snapshot(company: dict[str, Any]) -> dict[str, Any]:
    return {k: (_m2o_id(company.get(k)) or False if k == "external_report_layout_id" else company.get(k)) for k in BRAND_FIELDS if k in company}


def _standard_layout_view(client: Any) -> int | None:
    rows = client.execute_kw("ir.model.data", "search_read", [[("module", "=", "web"), ("name", "=", "external_layout_standard")]], {"fields": ["res_id"], "limit": 1})
    return int(rows[0]["res_id"]) if rows else None


@reports_router.post("/brand/apply")
def brand_apply(connection_id: str, body: BrandBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Save once on the company; every document using Odoo's layout picks it up. Returns what to put back."""
    client = _client(connection_id, db)
    company = _company(client, body.company_id)
    vals = _brand_values(client, body.values)
    if not vals:
        raise HTTPException(status_code=422, detail="There's nothing to change.")
    previous = {k: (company.get(k)[0] if isinstance(company.get(k), list) else company.get(k)) for k in vals}
    from app import write_gate as _wg  # A5: shared guards + undo point in History

    _wg.guard_one(db, connection_id, client, "res.company", [int(company["id"])], vals, "Document branding")
    try:
        client.execute_kw("res.company", "write", [[company["id"]], vals])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    after = _company(client, company["id"])
    got = {k: (after.get(k)[0] if isinstance(after.get(k), list) else after.get(k)) for k in vals}
    if any(str(got[k] or "").lower() != str(vals[k] or "").lower() for k in vals):
        client.execute_kw("res.company", "write", [[company["id"]], previous])
        raise HTTPException(status_code=409, detail="Odoo didn't keep the brand settings, so they were put back.")
    vs.save_item(db, connection_id=connection_id, kind="brand", key=str(company["id"]), name=str(company["name"]),
                 payload={"previous": previous, "applied": vals})
    return {"ok": True, "previous": previous, "applied": vals}


class BrandUndoBody(CompanyBody):
    previous: dict[str, Any]


@reports_router.post("/brand/undo")
def brand_undo(connection_id: str, body: BrandUndoBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    company = _company(client, body.company_id)
    # Put back what the server recorded before the last apply (not values sent by the browser).
    stored = next((vs.item_out(r)["payload"] for r in vs.list_items(db, connection_id, "brand", str(company["id"]))), None)
    if not stored or not isinstance(stored.get("previous"), dict):
        raise HTTPException(status_code=409, detail="There is no earlier branding to go back to.")
    vals = {k: v for k, v in stored["previous"].items() if k in BRAND_FIELDS}
    try:
        client.execute_kw("res.company", "write", [[company["id"]], vals])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    return {"ok": True, "restored": vals}


# -- starter gallery and saved block sets --

@reports_router.post("/gallery")
def gallery(connection_id: str, body: ReportRef, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    ctx = _report_setup(client, body.report_id)
    names = {o2m for s in rb.STARTERS if s["model"] == ctx["model"] for o2m in (s.get("lines") or {})}
    items = rb.gallery_for(ctx["model"], ctx["fields"], _related(client, ctx["fields"], names), ctx["slots2"])
    return {"starters": items, "major": _major(client)}


class BlockSetBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    model: str
    blocks: list[dict[str, Any]]


@reports_router.post("/blocks/save")
def blocks_save(connection_id: str, body: BlockSetBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """A named set of blocks reusable in print layouts and emails of the same record type."""
    client = _client(connection_id, db)
    model = _check_model(body.model)
    fields = _fields_get(client, model)
    try:
        blocks = rb.validate_blocks(body.blocks, fields, _related(client, fields, _line_fields_used([{"blocks": body.blocks}])))
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    row = vs.save_item(db, connection_id=connection_id, kind="blocks", key=model, name=body.name.strip(), payload={"blocks": blocks})
    email_ok = all(b["type"] in rb.EMAIL_BLOCK_TYPES for b in blocks)
    return {"ok": True, "item": vs.item_out(row), "usable_in_email": email_ok}


class ModelBody(BaseModel):
    model: str


@reports_router.post("/blocks/list")
def blocks_list(connection_id: str, body: ModelBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    model = _check_model(body.model)
    out = []
    for r in vs.list_items(db, connection_id, "blocks", model):
        item = vs.item_out(r)
        item["usable_in_email"] = all(b.get("type") in rb.EMAIL_BLOCK_TYPES for b in item["payload"].get("blocks") or [])
        out.append(item)
    return {"sets": out}


class ItemBody(BaseModel):
    item_id: str


@reports_router.post("/blocks/delete")
def blocks_delete(connection_id: str, body: ItemBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = vs.get_item(db, connection_id, body.item_id)
    if not row or row.kind != "blocks":
        raise HTTPException(status_code=404, detail="That block set isn't saved here.")
    vs.delete_item(db, row)
    return {"ok": True}


# ----------------------------------------------------------------------------
# Emails
# ----------------------------------------------------------------------------

def _template(client: Any, template_id: int) -> dict[str, Any]:
    rows = client.execute_kw("mail.template", "read", [[int(template_id)]], {"fields": ["id", "name", "subject", "body_html", "model"]})
    if not rows:
        raise HTTPException(status_code=404, detail="That email template no longer exists.")
    return rows[0]


def _email_item(db: Session, connection_id: str, template_id: int) -> Any:
    for r in vs.list_items(db, connection_id, "email"):
        if int(vs.item_out(r)["payload"].get("template_id") or 0) == int(template_id):
            return r
    return None


@emails_router.post("/list")
def email_list(connection_id: str, body: ModelBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = _check_model(body.model)
    rows = client.execute_kw("mail.template", "search_read", [[("model", "=", model)]], {"fields": ["id", "name", "subject"], "order": "name"})
    ours = {int(vs.item_out(r)["payload"].get("template_id") or 0): vs.item_out(r) for r in vs.list_items(db, connection_id, "email")}
    return {"templates": [{**r, "ingenium_copy": r["id"] in ours, "copied_from": (ours.get(r["id"]) or {}).get("payload", {}).get("source_id")}
                          for r in rows]}


class TemplateBody(BaseModel):
    template_id: int


@emails_router.post("/copy")
def email_copy(connection_id: str, body: TemplateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Work on a copy so Odoo's own template is never changed."""
    client = _client(connection_id, db)
    src = _template(client, body.template_id)
    try:
        res = client.execute_kw("mail.template", "copy", [int(src["id"])], {"default": {"name": f"{src['name']} (Ingenium)"}})
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    new_id = int(res[0] if isinstance(res, list) else res)
    row = vs.save_item(db, connection_id=connection_id, kind="email", key=str(src.get("model") or ""), name=f"{src['name']} (Ingenium)",
                       payload={"template_id": new_id, "source_id": int(src["id"]), "placements": []})
    return {"ok": True, "template_id": new_id, "item_id": row.id}


@emails_router.post("/load")
def email_load(connection_id: str, body: TemplateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    tpl = _template(client, body.template_id)
    item = _email_item(db, connection_id, body.template_id)
    model = str(tpl.get("model") or "")
    fields = _fields_get(client, model) if model else {}
    records = client.execute_kw(model, "search_read", [[]], {"fields": ["display_name"], "limit": 20, "order": "id desc"}) if model else []
    return {"template": {k: tpl.get(k) for k in ("id", "name", "subject", "model")}, "editable": item is not None,
            "placements": vs.item_out(item)["payload"].get("placements") if item else [], "slots": rb.EMAIL_SLOTS,
            "blocks": sorted(rb.EMAIL_BLOCK_TYPES),
            "line_fields": sorted(n for n, m in fields.items() if m.get("type") in {"one2many", "many2many"}),
            "fields": {n: {"string": m.get("string"), "type": m.get("type")} for n, m in fields.items()
                       if not n.startswith("__") and m.get("type") not in {"binary", "properties", "json"}},
            "records": [{"id": r["id"], "display_name": r["display_name"]} for r in records]}


class EmailLinesBody(TemplateBody):
    field: str = Field(min_length=1, max_length=64)


@emails_router.post("/lines-fields")
def email_lines_fields(connection_id: str, body: EmailLinesBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    model = str(_template(client, body.template_id).get("model") or "")
    if not model:
        raise HTTPException(status_code=422, detail="This email template isn't linked to a record type.")
    return {"field": body.field, "columns": _line_columns(client, _fields_get(client, model), body.field)}


class EmailPlacementsBody(TemplateBody):
    record_id: int
    placements: list[dict[str, Any]] | None = None
    highlight: list[dict[str, Any]] | None = None  # preview only: blocks Edit with AI changed, outlined


def _render_email(client: Any, template_id: int, model: str, record_id: int) -> dict[str, str]:
    """Odoo's own composer renders the template for one record (nothing is sent)."""
    try:
        cid = client.execute_kw("mail.compose.message", "create", [{
            "composition_mode": "comment", "model": model, "res_ids": repr([int(record_id)]), "template_id": int(template_id)}],
            {"context": {"default_model": model, "default_res_ids": [int(record_id)], "default_composition_mode": "comment"}})
        row = client.execute_kw("mail.compose.message", "read", [[cid]], {"fields": ["subject", "body"]})[0]
        try:
            client.execute_kw("mail.compose.message", "unlink", [[cid]])
        except ODOO_ERRORS:
            pass
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    return {"subject": str(row.get("subject") or ""), "html": str(row.get("body") or "")}


def _bodies(client: Any, template_id: int) -> dict[str, str]:
    """The email body in every active language (Odoo keeps a separate copy per translation)."""
    langs = [r["code"] for r in client.execute_kw("res.lang", "search_read", [[("active", "=", True)]], {"fields": ["code"]})] or ["en_US"]
    langs = ["en_US"] + [lang for lang in langs if lang != "en_US"] if "en_US" in langs else langs
    out: dict[str, str] = {}
    for lang in langs:
        row = client.execute_kw("mail.template", "read", [[int(template_id)], ["body_html"]], {"context": {"lang": lang}})
        out[lang] = str((row[0] if row else {}).get("body_html") or "")
    return out


def _write_bodies(client: Any, template_id: int, bodies: dict[str, str]) -> None:
    for lang, html in bodies.items():  # source language first, then each translation
        client.execute_kw("mail.template", "write", [[int(template_id)], {"body_html": html}], {"context": {"lang": lang}})


def _with_blocks(bodies: dict[str, str], placements: list[dict[str, Any]], fields: dict[str, Any],
                 highlight: set[tuple[str, int]] | None = None) -> dict[str, str]:
    return {lang: (rb.email_body(html, placements, fields, highlight) if placements else rb.strip_email_blocks(html)) for lang, html in bodies.items()}


def _condition_names(client: Any, fields: dict[str, Any], placements: Any) -> dict[str, dict[int, str]]:
    """Names of linked records used in block show/hide conditions (only ids that exist in Odoo count)."""
    ids: dict[str, set[int]] = {}
    for p in placements if isinstance(placements, list) else []:
        for b in (p.get("blocks") or []) if isinstance(p, dict) else []:
            if isinstance(b, dict):
                for f, found in _ids_in_condition(b.get("condition"), fields).items():
                    ids.setdefault(f, set()).update(found)
    return _record_names(client, fields, ids) if ids else {}


def _email_placements(client: Any, model: str, placements: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fields = _fields_get(client, model)
    try:
        return rb.validate_placements(placements, rb.EMAIL_SLOTS, fields, _related(client, fields, _line_fields_used(placements)), email=True,
                                      record_names=_condition_names(client, fields, placements)), fields
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc


@emails_router.post("/preview")
def email_preview(connection_id: str, body: EmailPlacementsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Rendered email for one record; with unsaved blocks a short-lived copy is used, then removed."""
    client = _client(connection_id, db)
    tpl = _template(client, body.template_id)
    model = str(tpl["model"])
    tmp_id = None
    target = int(tpl["id"])
    try:
        if body.placements is not None:
            placements, fields = _email_placements(client, model, body.placements)
            marks = {(str(h.get("slot")), int(h.get("index", -1))) for h in body.highlight or [] if isinstance(h, dict)}
            new_bodies = _with_blocks(_bodies(client, int(tpl["id"])), placements, fields, marks)
            tmp_id = client.execute_kw("mail.template", "copy", [int(tpl["id"])], {"default": {"name": f"{ve.LAYER_PREFIX} preview {secrets.token_hex(4)}"}})
            target = int(tmp_id[0] if isinstance(tmp_id, list) else tmp_id)
            _write_bodies(client, target, new_bodies)
        out = _render_email(client, target, model, body.record_id)
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    finally:
        if tmp_id:
            try:
                client.execute_kw("mail.template", "unlink", [[target]])
            except ODOO_ERRORS:
                pass
    return {**out, "widths": {"desktop": 600, "phone": 375}}


def own_address(db: Session, auth: Any) -> str:
    """Touch 132: a test goes only to the signed-in person's own account address. Never anyone else."""
    from app.account_models import User

    user = db.get(User, auth.user_id) if getattr(auth, "user_id", None) else None
    email = (getattr(user, "email", None) or "").strip()
    if not user or "@" not in email:
        raise HTTPException(status_code=401, detail="Sign in to send yourself a test. It only goes to your own account address.")
    return email


@emails_router.post("/test-send")
def email_test_send(connection_id: str, body: EmailPlacementsBody, db: Session = Depends(get_db), auth: Any = Depends(require_app_auth)) -> dict[str, Any]:
    """'Send me a test': the same rendered preview, sent through Ingenium's own mailer to your own address only."""
    from app.email_transport import send_email

    to = own_address(db, auth)
    out = email_preview(connection_id, body, db)
    html = str(out.get("html") or "")
    subject = f"[Test] {out.get('subject') or 'Email preview'}"
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()[:5000]
    send_email(to=to, subject=subject, body=text or "Test email.", html=html)
    return {"sent_to": to, "subject": subject}


@emails_router.post("/save")
def email_save(connection_id: str, body: EmailPlacementsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    item = _email_item(db, connection_id, body.template_id)
    if item is None:
        raise HTTPException(status_code=409, detail="Make an Ingenium copy first; Odoo's own email templates are never changed.")
    tpl = _template(client, body.template_id)
    model = str(tpl["model"])
    placements, fields = _email_placements(client, model, body.placements or [])
    try:
        previous_bodies = _bodies(client, int(tpl["id"]))
        _write_bodies(client, int(tpl["id"]), _with_blocks(previous_bodies, placements, fields))
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    previous = previous_bodies.get("en_US") or next(iter(previous_bodies.values()), "")
    rendered = _render_email(client, int(tpl["id"]), model, body.record_id)
    missing = [t for t in rb.expected_texts(placements) if t not in rendered["html"]]
    if missing:
        _write_bodies(client, int(tpl["id"]), previous_bodies)
        raise HTTPException(status_code=409, detail={"message": "Odoo's email doesn't show the change, so it was put back.", "missing": missing})
    payload = vs.item_out(item)["payload"]
    vs.update_item(db, item, {**payload, "placements": placements, "previous_body": previous, "previous_bodies": previous_bodies,
                              "previous_placements": payload.get("placements") or []})
    return {"ok": True, "previous_body": previous, **rendered}


class EmailRestoreBody(TemplateBody):
    body_html: str | None = None  # ignored: the body saved before the last save is restored (never client HTML)


@emails_router.post("/restore")
def email_restore(connection_id: str, body: EmailRestoreBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    item = _email_item(db, connection_id, body.template_id)
    if item is None:
        raise HTTPException(status_code=409, detail="Only Ingenium copies can be changed here.")
    payload = vs.item_out(item)["payload"]
    previous = payload.get("previous_body")
    bodies = payload.get("previous_bodies")
    if not isinstance(bodies, dict) or not all(isinstance(v, str) for v in bodies.values()):
        bodies = {"en_US": previous} if isinstance(previous, str) else None
    if not bodies:
        raise HTTPException(status_code=409, detail="There is no earlier version of this email to go back to.")
    try:
        _write_bodies(client, int(body.template_id), bodies)
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    vs.update_item(db, item, {**payload, "placements": payload.get("previous_placements") or [], "previous_body": None,
                              "previous_bodies": None, "previous_placements": []})
    return {"ok": True}


@emails_router.post("/delete")
def email_delete(connection_id: str, body: TemplateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    item = _email_item(db, connection_id, body.template_id)
    if item is None:
        raise HTTPException(status_code=409, detail="Only Ingenium copies can be removed here.")
    try:
        client.execute_kw("mail.template", "unlink", [[int(body.template_id)]])
    except ODOO_ERRORS as exc:
        raise _odoo_error(exc) from exc
    vs.delete_item(db, item)
    return {"ok": True}



# ----------------------------------------------------------------------------
# Edit with AI (SPEC 20.1): the AI proposes block ops, the block validator authorizes, nothing is written here.
# ----------------------------------------------------------------------------

class AIEditBody(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    placements: list[dict[str, Any]] = Field(default_factory=list)


class ReportAIEditBody(AIEditBody):
    report_id: int


class EmailAIEditBody(AIEditBody):
    template_id: int


class AIApplyOps(BaseModel):
    placements: list[dict[str, Any]] = Field(default_factory=list)
    ops: list[dict[str, Any]] = Field(default_factory=list)


class ReportAIApply(AIApplyOps):
    report_id: int


class EmailAIApply(AIApplyOps):
    template_id: int


def _ai_result(prop: dict[str, Any], base: list[dict[str, Any]], authorize: Any) -> dict[str, Any]:
    from app import ai_edit_blocks as aeb

    if not prop["ops"]:
        return {**prop, "placements": base}
    try:
        return {**prop, "placements": authorize(aeb.apply_ops(base, prop["ops"]))}
    except (ve.EngineError, HTTPException) as exc:
        why = exc.detail if isinstance(exc, HTTPException) else str(exc)
        return {"ops": [], "descriptions": [], "choices": [], "placements": base,
                "unclear": f"That change can't be made safely: {why if isinstance(why, str) else 'it failed the checks'}"}


def _ai_call(fn: Any) -> Any:
    try:
        return fn()
    except vai.AIUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ve.EngineError as exc:
        return {"ops": [], "descriptions": [], "choices": [], "unclear": str(exc)}


@reports_router.post("/ai-edit")
def report_ai_edit(connection_id: str, body: ReportAIEditBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app import ai_edit_blocks as aeb
    from app.ai_client.ai_scope import ai_scope

    client = _client(connection_id, db)
    ctx = _report_setup(client, body.report_id)
    with ai_scope(reads=("ir.ui.view", "ir.actions.report", "ir.model.fields")):
        prop = _ai_call(lambda: aeb.propose(body.text, body.placements, ctx["slots2"], ctx["fields"], email=False))
    if not prop.get("ops"):
        return {**prop, "placements": body.placements}
    return _ai_result(prop, body.placements, lambda p: _validated(client, ctx, p))


@reports_router.post("/ai-edit/apply")
def report_ai_apply(connection_id: str, body: ReportAIApply, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Accept a subset of the proposed ops: re-shaped and re-validated, never trusted from the browser."""
    from app import ai_edit_blocks as aeb

    client = _client(connection_id, db)
    ctx = _report_setup(client, body.report_id)
    try:
        ops = aeb.shape_ops({"ops": body.ops, "unclear": None}, ctx["slots2"], rb.BLOCK_TYPES)[0] if body.ops else []
        return {"placements": _validated(client, ctx, aeb.apply_ops(body.placements, ops))}
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc


@emails_router.post("/ai-edit")
def email_ai_edit(connection_id: str, body: EmailAIEditBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app import ai_edit_blocks as aeb
    from app.ai_client.ai_scope import ai_scope

    client = _client(connection_id, db)
    model = str(_template(client, body.template_id)["model"])
    fields = _fields_get(client, model)
    with ai_scope(reads=("mail.template", "ir.model.fields")):
        prop = _ai_call(lambda: aeb.propose(body.text, body.placements, rb.EMAIL_SLOTS, fields, email=True))
    if not prop.get("ops"):
        return {**prop, "placements": body.placements}
    return _ai_result(prop, body.placements, lambda p: _email_placements(client, model, p)[0])


@emails_router.post("/ai-edit/apply")
def email_ai_apply(connection_id: str, body: EmailAIApply, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app import ai_edit_blocks as aeb

    client = _client(connection_id, db)
    model = str(_template(client, body.template_id)["model"])
    try:
        ops = aeb.shape_ops({"ops": body.ops, "unclear": None}, rb.EMAIL_SLOTS, rb.EMAIL_BLOCK_TYPES)[0] if body.ops else []
        return {"placements": _email_placements(client, model, aeb.apply_ops(body.placements, ops))[0]}
    except ve.EngineError as exc:
        raise _engine_error(exc) from exc
