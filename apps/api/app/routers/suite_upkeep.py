"""Configuration Suite stage 2: Upkeep (scheduled actions, files), Safety (after an upgrade, money) and Ask."""

from __future__ import annotations

import base64
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import time

from app import suite_ask as sa
from app.ai_client import ai_cache
from app import suite_upkeep as su
from app import view_engine_store as vs
from app.db import get_db
from app.dry_run_ledger import dry_run_was_seen, remember_dry_run
from app.mutation_lock import ConnectionMutationBusy, connection_mutation_lock
from app.odoo_service import get_connection_or_404
from app.routers import suite as rs
from app.routers import suite_change as rsc
from app.routers.view_engine import _client
from app.suite_setup import fault_line

router = APIRouter(prefix="/connections/{connection_id}/suite", tags=["suite"])
PAUSE, DESC, FRUN = "suite_cron_pause", "suite_cron_desc", "suite_frun"
FILES_TOOL = "suite.files.clean"
ARCHIVE_DIR = Path.home() / ".ingenium" / "suite_archive"


def _now() -> datetime:
    return datetime.now(UTC)


def _cloud(db: Session, cid: str) -> bool:
    return bool(rs._policy(db, cid).get("cloud_ai"))


# ---------------------------------------------------------------- scheduled actions
def _crons(client: Any) -> list[dict[str, Any]]:
    meta = client.execute_kw("ir.cron", "fields_get", [], {"attributes": ["type"]})
    want = [f for f in ("cron_name", "name", "model_id", "interval_number", "interval_type", "nextcall", "lastcall", "active", "user_id",
                        "failure_count", "first_failure_date", "priority") if f in meta]
    return client.execute_kw("ir.cron", "search_read", [[]], {"fields": want, "context": {"active_test": False}, "order": "nextcall"})


@router.get("/upkeep/schedules")
def schedules(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Every scheduled action in plain words: what it does, how often, last result, next 24 hours. No method names."""
    client = _client(connection_id, db)
    now = _now()
    pauses = {it.key: vs.item_out(it)["payload"] for it in vs.list_items(db, connection_id, PAUSE)}
    cached = {it.key: vs.item_out(it)["payload"].get("text") for it in vs.list_items(db, connection_id, DESC)}
    cloud = _cloud(db, connection_id)
    out = []
    ai_budget = 8
    for c in _crons(client):
        name = su.plain_name(c.get("cron_name") or c.get("name") or "")
        record_type = (c.get("model_id") or [0, "records"])[1]
        often = su.how_often(int(c.get("interval_number") or 1), str(c.get("interval_type") or "days"))
        text, source = su.known_description(name), "catalogue"
        if not text and name in cached:
            text, source = cached[name], "ai (checked)"
        if not text and ai_budget > 0 and sa.ai_allowed(cloud):
            ai_budget -= 1
            raw = sa.ai_json(sa.PROMPT_94, {"name": name, "record_type": record_type, "how_often": often, "action": name}, cloud_ai=cloud, step="cron")
            text = su.validate_cron_sentence((raw or {}).get("sentence") if isinstance(raw, dict) else raw, often, record_type)
            source = "ai (checked)"
            vs.save_item(db, connection_id=connection_id, kind=DESC, key=name, name=name, payload={"text": text}, replace_key=True)
        if not text:
            text, source = su.fallback_sentence(often, record_type), "plain fallback"
        fails = int(c.get("failure_count") or 0)
        last = (f"Failed {fails} time{'s' if fails != 1 else ''} in a row since {c.get('first_failure_date')}" if fails
                else (f"Last ran {c.get('lastcall')}" if c.get("lastcall") else "Has not run yet"))
        p = pauses.get(str(c["id"]))
        out.append({"id": c["id"], "name": name, "record_type": record_type, "how_often": often, "description": text, "description_source": source,
                    "active": bool(c.get("active")), "next_run": c.get("nextcall"), "last_result": last, "failing": fails > 0,
                    "paused": p if (p and not c.get("active")) else None,
                    "next_24h": su.timeline(c.get("nextcall"), int(c.get("interval_number") or 1), str(c.get("interval_type") or "days"), now=now)
                    if c.get("active") else []})
    return {"schedules": out, "now": now.isoformat(timespec="seconds")}


class PauseBody(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/upkeep/schedules/{cron_id}/pause")
def schedule_pause(connection_id: str, cron_id: int, body: PauseBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    who = rs._who(request)
    client.execute_kw("ir.cron", "write", [[cron_id], {"active": False}], {})
    rec = {"by": who.get("email") or "you", "at": _now().isoformat(timespec="seconds"), "reason": body.reason.strip()}
    vs.save_item(db, connection_id=connection_id, kind=PAUSE, key=str(cron_id), name=f"pause {cron_id}", payload=rec, replace_key=True)
    return {"id": cron_id, "active": False, "paused": rec}


@router.post("/upkeep/schedules/{cron_id}/resume")
def schedule_resume(connection_id: str, cron_id: int, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    client.execute_kw("ir.cron", "write", [[cron_id], {"active": True}], {})
    for it in vs.list_items(db, connection_id, PAUSE, key=str(cron_id)):
        p = vs.item_out(it)["payload"]
        p.update({"resumed_by": rs._who(request).get("email") or "you", "resumed_at": _now().isoformat(timespec="seconds")})
        vs.update_item(db, it, p)
    return {"id": cron_id, "active": True}


# ---------------------------------------------------------------- files
FILE_FIELDS = ["name", "res_model", "res_id", "res_field", "file_size", "checksum", "type", "url", "public", "mimetype", "create_date"]


def _files(client: Any) -> list[dict[str, Any]]:
    dom = [("type", "=", "binary"), "|", ("res_field", "=", False), ("res_field", "!=", False)]
    return client.execute_kw("ir.attachment", "search_read", [dom], {"fields": FILE_FIELDS, "order": "id", "limit": 20000})


@router.get("/upkeep/files")
def files_scan(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Measured storage, a breakdown by record type, unattached files and repeated copies. Accounting files are never offered."""
    rows = _files(_client(connection_id, db))
    scan = su.file_scan(rows)
    offer = {u["id"] for u in scan["unattached"]} | {c for rp in scan["repeats"] for c in rp["copies"]}
    scan["space_if_all_cleaned"] = su.space_freed(rows, offer)
    return scan


class FilesBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=2000)


@router.post("/upkeep/files/dry-run")
def files_check(connection_id: str, body: FilesBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = _files(_client(connection_id, db))
    verdicts = su.file_verdicts(rows, body.ids)
    ready = sorted(v["id"] for v in verdicts if v["verdict"] == "ready")
    freed = su.space_freed(rows, set(ready))
    remember_dry_run(FILES_TOOL, {"cid": connection_id, "ids": ready})
    return {"verdicts": verdicts, "ready": len(ready), "blocked": len(verdicts) - len(ready), "space_freed": freed,
            "note": "Each file is copied into a zip archive first, so Undo can put it back.", "receipt": True}


def _content_field(client: Any) -> str:
    """'datas' up to 19; Odoo 20 keeps only 'raw'."""
    return "datas" if "datas" in client.execute_kw("ir.attachment", "fields_get", [], {"attributes": ["type"]}) else "raw"


def _archive(cid: str, run_id: str) -> Path:
    d = ARCHIVE_DIR / cid
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{run_id}.zip"


@router.post("/upkeep/files/run")
def files_run(connection_id: str, body: FilesBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Archive first, then remove. Needs the receipt from Check for exactly these files."""
    client = _client(connection_id, db)
    ids = sorted(set(body.ids))
    if not dry_run_was_seen(FILES_TOOL, {"cid": connection_id, "ids": ids}):
        raise HTTPException(status_code=428, detail="Run Check first. The files to clean must match the last Check.")
    rows = _files(client)
    verdicts = su.file_verdicts(rows, ids)
    if any(v["verdict"] != "ready" for v in verdicts):
        raise HTTPException(status_code=409, detail="Some files changed since Check. Run Check again.")
    freed = su.space_freed(rows, set(ids))
    try:
        with connection_mutation_lock(connection_id, "suite files clean"):
            cf = _content_field(client)
            full = client.execute_kw("ir.attachment", "read", [ids], {"fields": ["name", cf, "res_model", "res_id", "mimetype", "description"]})
            row = vs.save_item(db, connection_id=connection_id, kind=FRUN, key="files", name=f"Clean {len(ids)} files",
                               payload={"state": "running", "by": rs._who(request).get("email"), "at": _now().isoformat(timespec="seconds")})
            path = _archive(connection_id, row.id)
            meta = []
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                for f in full:
                    content = f.get(cf) or ""
                    if isinstance(content, dict):  # Odoo 20 reads files as {filename, content, size}
                        content = content.get("content") or ""
                    z.writestr(f"{f['id']}", base64.b64decode(content))
                    meta.append({k: f.get(k) for k in ("id", "name", "res_model", "res_id", "mimetype", "description")})
                z.writestr("files.json", json.dumps(meta))
            client.execute_kw("ir.attachment", "unlink", [ids], {})
            p = {**vs.item_out(row)["payload"], "state": "done", "files": meta, "archive": str(path), "space_freed": freed}
            vs.update_item(db, row, p)
    except ConnectionMutationBusy as exc:
        raise HTTPException(status_code=409, detail=f"Another change is running on this database ({exc.holder}).") from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=fault_line(exc)) from exc
    return {"run_id": row.id, "removed": len(ids), "space_freed": freed, "archive": path.name}


@router.post("/upkeep/files/runs/{run_id}/undo")
def files_undo(connection_id: str, run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    row = vs.get_item(db, connection_id, run_id)
    if row is None or row.kind != FRUN:
        raise HTTPException(status_code=404, detail="Not found.")
    p = vs.item_out(row)["payload"]
    if p.get("state") != "done":
        raise HTTPException(status_code=409, detail="This clean was already undone or did not finish.")
    restored = []
    cf = _content_field(client)
    with zipfile.ZipFile(p["archive"]) as z:
        for f in p["files"]:
            vals = {"name": f["name"], cf: base64.b64encode(z.read(str(f["id"]))).decode(), "mimetype": f.get("mimetype")}
            if f.get("res_model") and f.get("res_id"):
                vals.update({"res_model": f["res_model"], "res_id": f["res_id"]})
            restored.append(client.execute_kw("ir.attachment", "create", [vals], {}))
    p.update({"state": "undone", "restored_ids": restored})
    vs.update_item(db, row, p)
    return {"restored": len(restored), "ids": restored}


# ---------------------------------------------------------------- safety: after an upgrade, money
def _tracked(client: Any) -> list[dict[str, Any]]:
    return client.execute_kw("ir.ui.view", "search_read", [[("name", "=like", "ingenium%")]],
                             {"fields": ["name", "model", "type", "arch_db", "inherit_id"], "context": {"active_test": False}})


@router.get("/safety/upgrade")
def upgrade_check(connection_id: str, target: str | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Your tracked changes against the facts of the target version. target = another connection (the upgraded copy)."""
    row = get_connection_or_404(db, connection_id)
    client = _client(connection_id, db)
    here = int(client.capabilities.major)
    tmajor = int(_client(target, db).capabilities.major) if target else here
    changes = [{"id": v["id"], "name": v["name"], "model": v["model"], "type": v["type"], "arch": v.get("arch_db") or "",
                "parent": (v.get("inherit_id") or [0, ""])[1]} for v in _tracked(client)]
    timeline = [{"what": "Version seen now", "value": row.last_seen_version or row.server_version}]
    if getattr(row, "upgrade_detected", False):
        timeline.append({"what": "Upgrade detected", "value": str(row.upgrade_detected_at or "")})
    matrix = su.upgrade_matrix(changes, tmajor)
    for m, c in zip(matrix, changes, strict=True):
        m["parent"] = c["parent"]
    return {"from_version": here, "target_version": tmajor, "timeline": timeline, "changes": matrix,
            "needs_fix": sum(1 for m in matrix if m["status"] == "needs_fix")}


@router.get("/safety/upgrade/forecast")
def upgrade_forecast(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Stage 4 "Before you upgrade": for every newer version up to 20, what would need a fix. Reads only; the
    real check still runs on an upgraded copy (GET /safety/upgrade?target=)."""
    client = _client(connection_id, db)
    here = int(client.capabilities.major)
    changes = [{"id": v["id"], "name": v["name"], "model": v["model"], "type": v["type"], "arch": v.get("arch_db") or ""}
               for v in _tracked(client)]
    installed = {r["name"] for r in client.execute_kw("ir.module.module", "search_read",
                                                      [[("state", "=", "installed")]], {"fields": ["name"]})}
    steps = []
    for major in range(here + 1, 21):
        matrix = su.upgrade_matrix(changes, major)
        data_moves = [m["text"] for m in su.DATA_MOVES if m["since"] == major and (not m.get("app") or m["app"] in installed)]
        steps.append({"version": major, "screens_to_fix": sum(1 for m in matrix if m["status"] == "needs_fix"),
                      "auto_fixable": sum(1 for m in matrix if m["status"] == "needs_fix" and m["fixed_arch"]),
                      "screens": [{"name": m["name"], "flags": [f["text"] for f in m["flags"]]} for m in matrix if m["flags"]][:30],
                      "data_moves": data_moves})
    worst = max((s["screens_to_fix"] + len(s["data_moves"]) for s in steps), default=0)
    return {"from_version": here, "steps": steps,
            "summary": ("You're on the newest version." if not steps else
                        "Nothing we track needs changing." if worst == 0 else
                        f"{sum(s['screens_to_fix'] for s in steps)} screen change(s) and "
                        f"{sum(len(s['data_moves']) for s in steps)} data move(s) to plan for. Rehearse on a copy first.")}


class FixBody(BaseModel):
    target: str
    view_id: int


@router.post("/safety/upgrade/fix/dry-run")
def upgrade_fix_check(connection_id: str, body: FixBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Fix ticket Check: the rewritten change must attach to the target database's screen. Writes nothing."""
    client = _client(connection_id, db)
    tclient = _client(body.target, db)
    v = client.execute_kw("ir.ui.view", "read", [[body.view_id]], {"fields": ["name", "model", "type", "arch_db", "inherit_id"]})
    if not v:
        raise HTTPException(status_code=404, detail="Change not found.")
    v = v[0]
    mrow = su.upgrade_matrix([{"id": v["id"], "name": v["name"], "model": v["model"], "type": v["type"], "arch": v["arch_db"]}],
                             int(tclient.capabilities.major))[0]
    arch = mrow["fixed_arch"] or v["arch_db"]
    if mrow["flags"] and not mrow["fixed_arch"]:
        return {"ticket": {"view": v["name"], "flags": mrow["flags"]}, "passes": False, "missing": [], "note": "This needs a person to rewrite it."}
    vtype = "list" if v["type"] in ("tree", "list") and int(tclient.capabilities.major) >= 18 else v["type"]
    combined = tclient.execute_kw(v["model"], "get_views", [[[False, vtype]]], {}).get("views", {}).get(vtype, {}).get("arch", "")
    ok, missing = su.xpaths_resolve(arch, combined)
    return {"ticket": {"view": v["name"], "model": v["model"], "flags": mrow["flags"], "fixed_arch": arch}, "passes": ok, "missing": missing}


@router.get("/safety/localization")
def localization(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The money guard card: country, installed country package and where money settings change in Odoo."""
    client = _client(connection_id, db)
    comp = client.execute_kw("res.company", "search_read", [[]], {"fields": ["name", "country_id", "currency_id"], "limit": 20})
    pk = client.execute_kw("ir.module.module", "search_read", [[("name", "=like", "l10n_%"), ("state", "=", "installed")]], {"fields": ["name", "shortdesc"]})
    return {"companies": [{"name": c["name"], "country": (c.get("country_id") or [0, None])[1], "currency": (c.get("currency_id") or [0, None])[1]} for c in comp],
            "country_packages": [p["shortdesc"] for p in pk],
            "routes": {"Taxes": sa.MONEY_TOPICS[0][1], "Chart of accounts": sa.MONEY_TOPICS[1][1], "Journals": sa.MONEY_TOPICS[2][1],
                       "Fiscal positions": sa.MONEY_TOPICS[3][1], "Invoices and bills": sa.MONEY_TOPICS[4][1]},
            "rule": "The suite never changes taxes, accounts, journals, fiscal positions or posted documents. Those change in Odoo's own screens."}


# ---------------------------------------------------------------- ask
class AskBody(BaseModel):
    text: str = Field(min_length=2, max_length=1000)


def answer_timing(hit: bool | None, seconds: float) -> dict[str, Any]:
    """Q2 touch 111: honest timing; cached is True only when the AI answer came from the cache."""
    return {"cached": hit is True, "seconds": round(max(seconds, 0.0), 2)}


def ask_events(connection_id: str, text: str, db: Session):
    """Q2 touch 105: the Ask pipeline as events. Each step is emitted by the stage that just ran,
    with its real numbers; the last event is the result. /ask and /ask/stream both use this."""
    route = sa.money_route_for(text)
    if route:
        yield {"type": "step", "text": "Spotted a money topic, so code routes it"}
        yield {"type": "result", "data": {"kind": "money", "route": route, "answer": "The suite doesn't change money settings. " + route}}
        return
    client = _client(connection_id, db)
    pk = sa.packet(client)
    types = pk.get("record_types", [])
    n_fields = sum(len(t["fields"]) for t in types)
    yield {"type": "step", "text": f"Read {n_fields} fields on {len(types)} record types"}
    cloud = _cloud(db, connection_id)
    ai_cache.LAST_HIT.set(None)
    t0 = time.perf_counter()
    raw = sa.ai_json(sa.PROMPT_92, {"request": text, **pk}, cloud_ai=cloud, step="batch_plan")
    instant = answer_timing(ai_cache.LAST_HIT.get(), time.perf_counter() - t0)
    source = "ai (checked by code)" if raw is not None else "plain code reader"
    if raw is None:
        yield {"type": "step", "text": "AI not available, so the plain code reader read the request"}
        raw = sa.read_request(text, pk)
    else:
        yield {"type": "step", "text": "Saved answer reused" if instant["cached"] else f"AI drafted a plan in {instant['seconds']} s"}
    res = sa.validate_plan(raw, pk)
    dropped = len(res["dropped"])
    yield {"type": "step", "text": "Checked the plan against your live fields" + (f", dropped {dropped} unknown {'part' if dropped == 1 else 'parts'}" if dropped else "")}
    if res["plan"] is None:
        yield {"type": "result", "data": {"kind": "unclear", "unclear": res["unclear"], "dropped": res["dropped"], "source": source, "timing": instant}}
        return
    yield {"type": "result", "data": {"kind": "plan", "plan": res["plan"], "dropped": res["dropped"], "source": source, "timing": instant}}


@router.post("/ask")
def ask(connection_id: str, body: AskBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Copilot: money topics are routed by code; batch requests become a checked plan (AI 9.2 when allowed, else the code reader)."""
    out: dict[str, Any] = {}
    for ev in ask_events(connection_id, body.text, db):
        if ev["type"] == "result":
            out = ev["data"]
    return out


@router.post("/ask/stream")
def ask_stream(connection_id: str, body: AskBody, db: Session = Depends(get_db)) -> StreamingResponse:
    """Same as /ask, streamed as NDJSON: step events while each stage runs, then the result."""
    def gen():
        try:
            for ev in ask_events(connection_id, body.text, db):
                yield json.dumps(ev, default=str) + "\n"
        except HTTPException as exc:
            yield json.dumps({"type": "error", "status": exc.status_code, "detail": exc.detail}) + "\n"
    return StreamingResponse(gen(), media_type="application/x-ndjson")


class TicketBody(BaseModel):
    plan: dict[str, Any]


@router.post("/ask/ticket")
def ask_ticket(connection_id: str, body: TicketBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Fix it: turn a checked plan into a Change records batch. It still goes through Check and Run."""
    pk = sa.packet(_client(connection_id, db), [str(body.plan.get("record_type"))])
    res = sa.validate_plan(body.plan, pk)
    if res["plan"] is None:
        raise HTTPException(status_code=422, detail=res["unclear"])
    p = res["plan"]
    ch = dict(p["change"])
    tool = ch.pop("tool")
    out = rsc.batch_create(connection_id, rsc.BatchBody(tool=tool, model=p["record_type"], name=f"From Ask: {p['label']}", domain=p["filters"], change=ch),
                           request, db)
    return {"batch": out, "next": f"/connections/{connection_id}/suite/change/{tool}?batch={out['id']}"}


GUIDE_TOPICS = {"multi_company": "Companies and branches", "delivery_steps": "Delivery steps", "costing": "Costing method"}


def _count(client: Any, model: str, dom: list[Any]) -> int:
    try:
        return int(client.execute_kw(model, "search_count", [dom], {}))
    except Exception:  # noqa: BLE001
        return 0


def guide_facts(client: Any, topic: str) -> list[dict[str, Any]]:
    mods = {m["name"] for m in client.execute_kw("ir.module.module", "search_read", [[("state", "=", "installed"), ("name", "in", ["stock", "account"])]], {"fields": ["name"]})}
    facts = [{"id": "companies", "label": "Companies", "value": _count(client, "res.company", [])},
             {"id": "stock_installed", "label": "Inventory installed", "value": "stock" in mods},
             {"id": "posted_entries", "label": "Posted journal entries", "value": _count(client, "account.move", [("state", "=", "posted")]) if "account" in mods else 0}]
    if topic in ("delivery_steps", "costing") and "stock" in mods:
        wh = client.execute_kw("stock.warehouse", "search_read", [[]], {"fields": ["name", "delivery_steps"]})
        facts += [{"id": "warehouses", "label": "Warehouses", "value": len(wh)},
                  {"id": "delivery_steps", "label": "Delivery steps now", "value": ", ".join(sorted({w["delivery_steps"] for w in wh}))},
                  {"id": "done_moves", "label": "Finished stock moves", "value": _count(client, "stock.move", [("state", "=", "done")])},
                  {"id": "categories", "label": "Product categories", "value": _count(client, "product.category", [])}]
    if topic == "multi_company":
        facts.append({"id": "multi_company_on", "label": "More than one company", "value": facts[0]["value"] > 1})
    return facts


@router.get("/ask/guide")
def guide_topics(connection_id: str) -> dict[str, Any]:
    return {"topics": [{"key": k, "label": v} for k, v in GUIDE_TOPICS.items()]}


@router.get("/ask/guide/{topic}")
def guide(connection_id: str, topic: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    if topic not in GUIDE_TOPICS:
        raise HTTPException(status_code=404, detail="Unknown topic.")
    client = _client(connection_id, db)
    facts = guide_facts(client, topic)
    base = sa.guide(topic, facts)
    cloud = _cloud(db, connection_id)
    raw = sa.ai_json(sa.PROMPT_93, {"topic": GUIDE_TOPICS[topic], "facts": facts, "docs": []}, cloud_ai=cloud, step="guide") if not base.get("decided") else None
    checked = sa.validate_guide(raw, {f["id"] for f in facts}) if raw is not None else None
    if checked:
        return {**base, **checked, "source": "ai (checked by code)"}
    return {**base, "source": "code"}
