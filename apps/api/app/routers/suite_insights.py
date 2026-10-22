"""Suite ideas that only look (spec §16). GET only; nothing here writes to Odoo."""

from __future__ import annotations

from typing import Any

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import suite_insights as si
from app import view_engine_store as vs
from app.db import get_db
from app.routers.suite_change import CRUN
from app.routers.view_engine import _client
from app.suite_setup import fault_line

router = APIRouter(prefix="/connections/{connection_id}/suite/insights", tags=["suite"])

CATALOGUE = [
    {"key": "data-quality", "idea": 5, "title": "Data quality", "what": "Fields left empty in practice, bad emails and phones."},
    {"key": "archive-check", "idea": 8, "title": "Archive check", "what": "Which records can be archived because nothing open uses them."},
    {"key": "role-xray", "idea": 12, "title": "Role x-ray", "what": "Everything one person can do, and which role grants it."},
    {"key": "access-hygiene", "idea": 13, "title": "Access hygiene", "what": "Idle admins, users with no role, quiet portal users."},
    {"key": "numbering", "idea": 15, "title": "Numbering check", "what": "Gaps or duplicates in document numbers. Look only."},
    {"key": "translations", "idea": 17, "title": "Translation coverage", "what": "How much of your custom wording each language has."},
    {"key": "automations", "idea": 18, "title": "Automation catalogue", "what": "Every automation and schedule, when it fires and when it last did."},
    {"key": "unused-apps", "idea": 19, "title": "Unused apps", "what": "Apps with no new records lately, and what removing them would remove."},
    {"key": "custom-fields", "idea": 20, "title": "Custom field clean-up", "what": "Fields made here that are never filled, and where they're used."},
    {"key": "storage", "idea": 21, "title": "Storage forecast", "what": "File growth by month and when it reaches a size you set."},
    {"key": "import-aftercare", "idea": 22, "title": "Import aftercare", "what": "Recently imported records that look duplicated or incomplete."},
    {"key": "timeline", "idea": 24, "title": "Record time-travel", "what": "One record's tracked changes, oldest first."},
    {"key": "compare", "idea": 10, "title": "Compare two databases", "what": "Apps, custom fields, screens and schedules that differ."},
    {"key": "day-1", "idea": 29, "title": "Day-1 review", "what": "A checklist for a fresh database."},
    {"key": "hotspots", "idea": 33, "title": "Hot spots", "what": "Record types you change in bulk most often."},
]


def _guard(fn: Any) -> Any:
    try:
        return fn()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001  turn Odoo's refusal into a plain message
        raise HTTPException(status_code=422, detail=f"Couldn't read this: {fault_line(exc)}") from exc


@router.get("")
def insights_catalogue(connection_id: str) -> dict[str, Any]:
    return {"insights": CATALOGUE}


@router.get("/data-quality")
def data_quality(connection_id: str, model: str = "res.partner", db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.data_quality(_client(connection_id, db), model))


@router.get("/archive-check")
def archive_check(connection_id: str, model: str, ids: str = Query(..., max_length=20000), db: Session = Depends(get_db)) -> dict[str, Any]:
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()][:2000]
    return _guard(lambda: si.archive_check(_client(connection_id, db), model, id_list))


@router.get("/role-xray")
def role_xray(connection_id: str, user_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.role_xray(_client(connection_id, db), user_id))


@router.get("/access-hygiene")
def access_hygiene(connection_id: str, days: int = Query(90, ge=7, le=730), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.access_hygiene(_client(connection_id, db), days))


@router.get("/numbering")
def numbering(connection_id: str, model: str = "sale.order", db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.numbering_check(_client(connection_id, db), model))


@router.get("/translations")
def translations(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.translation_coverage(_client(connection_id, db)))


@router.get("/automations")
def automations(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.automation_catalogue(_client(connection_id, db)))


@router.get("/unused-apps")
def unused_apps(connection_id: str, days: int = Query(90, ge=7, le=730), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.unused_apps(_client(connection_id, db), days))


@router.get("/custom-fields")
def custom_fields(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.custom_fields(_client(connection_id, db)))


@router.get("/storage")
def storage(connection_id: str, limit_mb: float | None = Query(None, gt=0), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.storage_forecast(_client(connection_id, db), limit_mb))


@router.get("/import-aftercare")
def import_aftercare(connection_id: str, model: str = "res.partner", days: int = Query(14, ge=1, le=365), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.import_aftercare(_client(connection_id, db), model, days))


@router.get("/timeline")
def timeline(connection_id: str, model: str, id: int, db: Session = Depends(get_db)) -> dict[str, Any]:  # noqa: A002
    return _guard(lambda: si.record_timeline(_client(connection_id, db), model, id))


@router.get("/compare")
def compare(connection_id: str, other: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.compare(si.setup_snapshot(_client(connection_id, db)), si.setup_snapshot(_client(other, db))))


@router.get("/day-1")
def day1(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.day1_review(_client(connection_id, db)))


@router.get("/hotspots")
def hotspots(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    runs = []
    for r in vs.list_items(db, connection_id, CRUN):
        p = vs.item_out(r)["payload"]
        if p.get("kind") == "run":
            runs.append({"model": p.get("model"), "count": sum(1 for x in p.get("records") or [] if x.get("state") == "done")})
    return si.hotspots(runs)


CATALOGUE += [
    {"key": "multi-company", "idea": 16, "title": "Company consistency", "what": "Records visible in every company that may belong to one."},
    {"key": "setup-score", "idea": 38, "title": "Setup progress", "what": "Day-1 steps done, from real counts."},
    {"key": "import-health", "idea": 48, "title": "Import health", "what": "Imported records nothing has used since (never sold, never invoiced)."},
]


@router.get("/multi-company")
def multi_company(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.multi_company(_client(connection_id, db)))


@router.get("/setup-score")
def setup_score(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.setup_score(_client(connection_id, db)))


@router.get("/import-health")
def import_health(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _guard(lambda: si.import_health(_client(connection_id, db)))


class PriceDiffBody(BaseModel):
    old_name: str = ""
    old_b64: str = Field(max_length=14_000_000)
    new_name: str = ""
    new_b64: str = Field(max_length=14_000_000)
    key: str | None = None


@router.post("/price-diff")
def price_diff(connection_id: str, body: PriceDiffBody) -> dict[str, Any]:
    """Idea 46: compare an old and a new supplier price list; only changed rows go on to an import plan. Reads only."""
    import base64

    from app import suite_import as simp

    def table(name: str, b64: str) -> list[dict[str, str]]:
        t, _ = simp.read_document(name, base64.b64decode(b64))
        if not t:
            raise HTTPException(status_code=422, detail=f"No table found in {name or 'the file'}.")
        return [dict(zip(t[0]["headers"], r, strict=False)) for r in t[0]["rows"]]

    old, new = table(body.old_name, body.old_b64), table(body.new_name, body.new_b64)
    key = body.key or next(iter(new[0].keys()), "") if new else ""
    return {"key": key, **si.price_list_diff(old, new, key)}


@router.get("/handover")
def handover(connection_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """Ideas 11 + 44: a readable handover pack (print to PDF from the browser), with how this was set up."""
    from app.routers.suite import PLAN, RUN

    plans_raw = [vs.item_out(r) for r in vs.list_items(db, connection_id, PLAN)]
    runs_by_plan = {}
    for r in vs.list_items(db, connection_id, RUN):
        p = vs.item_out(r)["payload"]
        runs_by_plan[p.get("plan_id")] = f"{p.get('state')} {str(p.get('finished_at') or '')[:16]}"
    plans = [{"name": p["name"], "steps": len(p["payload"].get("steps") or []), "run": runs_by_plan.get(p["id"])} for p in plans_raw]
    runs = [{**{k: vs.item_out(r)["payload"].get(k) for k in ("model", "started_at", "by")}, "name": r.name}
            for r in vs.list_items(db, connection_id, CRUN) if vs.item_out(r)["payload"].get("kind") == "run"]
    html = _guard(lambda: si.handover_html(_client(connection_id, db), plans, runs))
    return HTMLResponse(html, headers={"Content-Disposition": 'inline; filename="handover-pack.html"'})


# ------------------------------------------------------------------------------------------------ playbooks
playbooks = APIRouter(prefix="/connections/{connection_id}/suite/playbooks", tags=["suite"])


class ReassignBody(BaseModel):
    model: str
    field: str = "user_id"
    from_user: int
    to_users: list[int] = Field(min_length=1, max_length=20)


class LeaverBody(BaseModel):
    from_user: int
    to_user: int


class TagRenameBody(BaseModel):
    model: str
    tag_id: int
    new_name: str = Field(min_length=1, max_length=120)


def _draft(db: Session, connection_id: str, request: Request, out: dict[str, Any]) -> dict[str, Any]:
    """Save each proposed batch as a normal Change batch (not checked, not run)."""
    from app.routers import suite as rs
    from app.routers.suite_change import BATCH

    who = rs._who(request)
    made = []
    for b in out.get("batches", []):
        p = {**b, "domain": [], "limits": {}, "check": None, "created_by": who.get("email"), "created_by_id": who.get("user_id"),
             "created_at": datetime.now(UTC).isoformat()}
        row = vs.save_item(db, connection_id=connection_id, kind=BATCH, key=f"batch:{b['tool']}", name=b["name"], payload=p)
        made.append({"id": row.id, "name": b["name"], "count": len(b.get("ids") or []),
                     "href": f"/connections/{connection_id}/suite/change/{b['tool']}?batch={row.id}"})
    return {**{k: v for k, v in out.items() if k != "batches"}, "drafted": made,
            "next": "Each batch is drafted only. Open it, Check it, then Run. Each run can be undone."}


@playbooks.post("/reassign")
def pb_reassign(connection_id: str, body: ReassignBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app import suite_playbooks as sp
    return _draft(db, connection_id, request, _guard(lambda: sp.reassign(_client(connection_id, db), body.model, body.field, body.from_user, body.to_users)))


@playbooks.post("/leaver")
def pb_leaver(connection_id: str, body: LeaverBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app import suite_playbooks as sp
    return _draft(db, connection_id, request, _guard(lambda: sp.leaver(_client(connection_id, db), body.from_user, body.to_user)))


@playbooks.get("/tags")
def pb_tags(connection_id: str, model: str = "res.partner.category", db: Session = Depends(get_db)) -> dict[str, Any]:
    from app import suite_playbooks as sp
    return _guard(lambda: sp.tags(_client(connection_id, db), model))


@playbooks.post("/tags/rename")
def pb_tag_rename(connection_id: str, body: TagRenameBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app import suite_playbooks as sp
    if body.model not in sp.TAG_MODELS:
        raise HTTPException(status_code=422, detail="That isn't a tag list.")
    return _draft(db, connection_id, request, sp.tag_rename(body.model, body.tag_id, body.new_name))


@playbooks.get("/rehearsal/{batch_id}")
def pb_rehearsal(connection_id: str, batch_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Idea 1: after Check, five sample records with exactly what Odoo will do to each."""
    from app.routers.suite_change import BATCH
    row = vs.get_item(db, connection_id, batch_id)
    if row is None or row.kind != BATCH:
        raise HTTPException(status_code=404, detail="Not found.")
    ck = vs.item_out(row)["payload"].get("check") or {}
    if not ck.get("records"):
        raise HTTPException(status_code=409, detail="Check this batch first.")
    ready = [r for r in ck["records"] if r["verdict"] == "ready"]
    pick = ready[:: max(1, len(ready) // 5)][:5]
    return {"samples": [{"record": r.get("name"), "now": r.get("now_label") or r.get("now"), "after": r.get("after")} for r in pick],
            "of": len(ready), "note": "Read from the check. Odoo may also run its own automations on save."}


@playbooks.get("/undo-today")
def pb_undo_today(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Idea 32: today's reversible bulk runs, newest first, in the order Undo all would reverse them."""
    today = datetime.now(UTC).date().isoformat()
    out = []
    items = [(r, vs.item_out(r)["payload"]) for r in vs.list_items(db, connection_id, CRUN)]
    undone = {p.get("undo_of") for _, p in items if p.get("kind") == "undo"}
    for r, p in items:
        if p.get("kind") == "run" and str(p.get("started_at") or "").startswith(today) and p.get("state") in {"done", "stopped", "paused"} and r.id not in undone:
            out.append({"run_id": r.id, "name": r.name, "started_at": p.get("started_at"), "changed": sum(1 for x in p.get("records") or [] if x.get("state") == "done")})
    out.sort(key=lambda x: x["started_at"], reverse=True)
    return {"runs": out, "note": "Undo goes newest first. Records changed again since a run are left alone and listed."}
