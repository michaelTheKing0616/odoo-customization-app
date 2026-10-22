"""Configuration Suite stage 2: Change records API (Check -> Run -> Review -> Undo) for the five tools."""

from __future__ import annotations

import contextvars
import csv
import io
import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import suite_change as sc
from app import suite_store as vs
from app.db import get_db
from app.dry_run_ledger import dry_run_was_seen, remember_dry_run
from app.mutation_lock import ConnectionMutationBusy, connection_mutation_lock
from app.odoo_service import get_connection_or_404
from app.routers import suite as rs
from app.routers.view_engine import _client

log = logging.getLogger(__name__)
router = APIRouter(prefix="/connections/{connection_id}/suite/change", tags=["suite"])
BATCH, CRUN = "suite_batch", "suite_crun"
RECEIPT_TOOL = "suite.change.run"
RUN_INLINE = False
HARD_TO_UNDO = {"transitions", "security", "message", "recompute"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _fields(client: Any, model: str) -> dict[str, Any] | None:
    try:
        return client.execute_kw(model, "fields_get", [], {"attributes": ["string", "type", "relation", "readonly", "store", "selection", "required"]})
    except Exception:  # noqa: BLE001
        return None


def _get(db: Session, cid: str, item_id: str, kind: str) -> Any:
    row = vs.get_item(db, cid, item_id)
    if row is None or row.kind != kind:
        raise HTTPException(status_code=404, detail="Not found.")
    return row


@router.get("/buttons")
def change_buttons(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Record types and the Odoo buttons this suite runs in bulk, only where installed."""
    client = _client(connection_id, db)
    live = {r["model"]: r["name"] for r in client.execute_kw("ir.model", "search_read", [[("model", "in", list(sc.BUTTONS))]], {"fields": ["model", "name"]})}
    return {"record_types": [{"model": m, "label": live[m], "buttons": [{"key": k, "label": b["label"], "money": bool(b.get("money")), "effects": b["effects"]}
                                                                        for k, b in sc.BUTTONS[m].items()]} for m in sc.BUTTONS if m in live]}


@router.get("/users")
def change_users(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Active internal users, for sharing out activities."""
    client = _client(connection_id, db)
    rows = client.execute_kw("res.users", "search_read", [[("share", "=", False)]], {"fields": ["name", "login"], "order": "name", "limit": 500})
    return {"users": [{"id": r["id"], "name": r["name"]} for r in rows]}


@router.get("/groups")
def change_groups(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Security groups for bulk security; accounting groups come back locked (money guard)."""
    client = _client(connection_id, db)
    rows = client.execute_kw("res.groups", "search_read", [[]], {"fields": ["full_name"], "order": "full_name", "limit": 1000})
    xs = sc._xmlids(client, "res.groups", [r["id"] for r in rows])
    return {"groups": [{"id": r["id"], "name": r.get("full_name") or str(r["id"]), "xmlid": xs.get(r["id"]),
                        "locked": sc.is_money_group(xs.get(r["id"], ""))} for r in rows]}


@router.get("/computed/{model}")
def change_computed(connection_id: str, model: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Stored computed fields Odoo can be asked to refresh."""
    client = _client(connection_id, db)
    if model in sc.GUARDED_MODELS or model.startswith("account."):
        raise HTTPException(status_code=403, detail={"code": "money_guard", "message": f"Refused by the money guard. {sc.money_route(model)}"})
    meta = client.execute_kw(model, "fields_get", [], {"attributes": ["string", "store", "readonly", "depends"]})
    return {"fields": [{"name": f, "label": m.get("string") or f} for f, m in sorted(meta.items(), key=lambda kv: str(kv[1].get("string")))
                       if m.get("store") and m.get("readonly") and m.get("depends") and f not in sc.NEVER_EDIT]}


@router.get("/fields/{model}")
def change_fields(connection_id: str, model: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Fields that can be set in bulk on this record type (code decides; computed, list and file fields are left out)."""
    meta = _fields(_client(connection_id, db), model)
    if meta is None:
        raise HTTPException(status_code=404, detail="This record type is not on this database.")
    out = [{"name": f, "label": m.get("string") or f, "type": m.get("type"), "relation": m.get("relation"),
            "choices": [{"value": k, "label": v} for k, v in (m.get("selection") or [])]}
           for f, m in meta.items() if m.get("store") and not m.get("readonly") and f not in sc.NEVER_EDIT and m.get("type") not in {"one2many", "many2many", "binary", "html"}]
    return {"model": model, "fields": sorted(out, key=lambda x: x["label"].lower())}


class BatchBody(BaseModel):
    tool: str
    model: str
    name: str = Field(default="", max_length=120)
    domain: list[Any] = Field(default_factory=list)
    ids: list[int] = Field(default_factory=list, max_length=5000)
    change: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, int] = Field(default_factory=dict)


def _view(row: Any) -> dict[str, Any]:
    out = vs.item_out(row)
    out["payload"]["hash"] = sc.batch_hash(out["payload"])
    return out


@router.post("/batches")
def batch_create(connection_id: str, body: BatchBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.tool not in sc.TOOLS:
        raise HTTPException(status_code=422, detail="Unknown tool.")
    who = rs._who(request)
    p = {**body.model_dump(), "check": None, "created_by": who.get("email"), "created_by_id": who.get("user_id"), "created_at": _now()}
    row = vs.save_item(db, connection_id=connection_id, kind=BATCH, key=f"batch:{body.tool}", name=body.name or f"{body.tool} on {body.model}", payload=p)
    return _view(row)


@router.put("/batches/{batch_id}")
def batch_update(connection_id: str, batch_id: str, body: BatchBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _get(db, connection_id, batch_id, BATCH)
    p = vs.item_out(row)["payload"]
    p.update({**body.model_dump(), "check": None})  # going back keeps choices but clears the check
    vs.update_item(db, row, p)
    return _view(row)


@router.get("/batches/{batch_id}")
def batch_get(connection_id: str, batch_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    out = _view(_get(db, connection_id, batch_id, BATCH))
    ck = out["payload"].get("check") or {}
    out["payload"]["approval"] = rs.find_approval(db, connection_id, "suite_change", batch_id, ck.get("hash", "")) if ck else None
    return out


@router.get("/batches")
def batch_list(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"batches": [{"id": r.id, "name": r.name, "tool": vs.item_out(r)["payload"].get("tool")} for r in vs.list_items(db, connection_id, BATCH)]}


class ScanBody(BaseModel):
    model: str = "res.partner"
    domain: list[Any] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=lambda: ["email", "phone", "name"])


@router.post("/duplicates/scan")
def duplicates_scan(connection_id: str, body: ScanBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Read only: groups with Strong / Possible and the reasons."""
    client = _client(connection_id, db)
    groups = sc.scan_duplicates(client, body.model, body.domain, body.fields)
    return {"groups": groups, "count": len(groups)}


@router.post("/batches/{batch_id}/dry-run")
def batch_check(connection_id: str, batch_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Check: reads only. Every record gets Ready / Nothing to change / Blocked with the reason."""
    row = _get(db, connection_id, batch_id, BATCH)
    p = vs.item_out(row)["payload"]
    client = _client(connection_id, db)
    fmeta = _fields(client, p["model"])
    lim = sc.limits_for(p)
    refused = sc.refuse(p, fmeta)
    h = sc.batch_hash(p)
    if refused:
        rep = {"hash": h, "refused": refused, "records": [], "counts": {"ready": 0, "no_change": 0, "blocked": 0}, "receipt": None, "limits": lim}
    else:
        ids = [] if p["tool"] == "duplicates" else sc.pick_ids(client, p)
        recs = sc.check_records(client, p, fmeta or {}, ids)
        ready = [r for r in recs if r["verdict"] == "ready"]
        over = max(0, len(ready) - lim["cap"])
        for r in ready[lim["cap"]:]:
            r.update(verdict="over_cap", reason=f"Over this run's limit of {lim['cap']}. Run again after this one.")
        counts = {k: sum(1 for r in recs if r["verdict"] == k) for k in ("ready", "no_change", "blocked", "over_cap")}
        pol = rs._policy(db, connection_id)
        money = p["tool"] == "transitions" and sc.BUTTONS[p["model"]][p["change"]["button"]].get("money")
        approval = bool(money) or (p["tool"] in HARD_TO_UNDO and counts["ready"] > int(pol["approval_threshold"]))
        installed = {m["name"] for m in client.execute_kw("ir.module.module", "search_read", [[("state", "=", "installed"), ("name", "in", ["stock", "mail"])]], {"fields": ["name"]})}
        rep = {"hash": h, "refused": None, "records": recs, "counts": counts, "over_cap": over, "limits": lim, "needs_approval": approval,
               "threshold": pol["approval_threshold"], "also": sc.explain(p, installed), "receipt": None, "checked_at": _now()}
        if counts["ready"]:
            rep["receipt"] = remember_dry_run(RECEIPT_TOOL, {"connection_id": connection_id, "batch_id": batch_id, "hash": h,
                                                             "ready": sorted(int(r["id"]) for r in ready[: lim["cap"]])})
    p["check"] = rep
    vs.update_item(db, row, p)
    return rep


@router.post("/batches/{batch_id}/request-approval")
def batch_request_approval(connection_id: str, batch_id: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _get(db, connection_id, batch_id, BATCH)
    p = vs.item_out(row)["payload"]
    ck = p.get("check") or {}
    if not ck or ck.get("hash") != sc.batch_hash(p):
        raise HTTPException(status_code=409, detail="Check this batch before asking for approval.")
    return rs.ask_approval(connection_id, db, request, "suite_change", batch_id, ck["hash"],
                           [f"{row.name}", f"{ck['counts']['ready']} records ready", *(ck.get("also") or [])[:3]])


def _ready(ck: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in ck.get("records", []) if r["verdict"] == "ready"]


def execute_change(client: Any, db: Session, cid: str, run_row: Any) -> dict[str, Any]:
    run = vs.item_out(run_row)["payload"]
    batch = vs.item_out(vs.get_item(db, cid, run["batch_id"]))["payload"]
    fmeta = _fields(client, batch["model"]) or {}
    lim = run["limits"]
    undo_mode = run["kind"] == "undo"
    try:
        with connection_mutation_lock(cid, f"suite change {run_row.id}"):
            run["state"] = "running"
            vs.update_item(db, run_row, run)
            for n, rec in enumerate(run["records"]):
                if rec["state"] != "waiting":
                    continue
                if n and n % lim["batch"] == 0 or rec is run["records"][0]:
                    db.refresh(run_row)
                    if vs.item_out(run_row)["payload"].get("stop_requested"):
                        run.update(state="stopped", finished_at=_now())
                        vs.update_item(db, run_row, run)
                        return run
                try:
                    if undo_mode:
                        res = sc.undo_record(client, batch, rec["source"])
                        rec.update(state=res["state"], message=res["message"])
                    else:
                        res = sc.run_record(client, batch, fmeta, rec["check"])
                        rec.update(state=res["state"], after=res.get("after"), undo=res.get("undo"), message="; ".join(res.get("notes") or []))
                except sc.RecordChanged as exc:
                    rec.update(state="skipped", message=str(exc))
                except Exception as exc:  # noqa: BLE001  Odoo refused this one record
                    rec.update(state="failed", message=f"Odoo refused: {sc.fault_line(exc)}")
                rec["at"] = _now()
                if lim.get("pace_ms"):
                    time.sleep(lim["pace_ms"] / 1000)
                if (n + 1) % lim["batch"] == 0:
                    vs.update_item(db, run_row, run)
            run.update(state="done", finished_at=_now())
            vs.update_item(db, run_row, run)
            return run
    except ConnectionMutationBusy as exc:
        run.update(state="failed", message=f"Another change is running on this database ({exc.holder}). Wait or open it.", finished_at=_now())
        vs.update_item(db, run_row, run)
        return run


def _start(cid: str, run_id: str) -> None:
    from app.db import SessionLocal
    from app.odoo_service import client_from_connection

    def work() -> None:
        db = SessionLocal()
        try:
            execute_change(client_from_connection(get_connection_or_404(db, cid)), db, cid, vs.get_item(db, cid, run_id))
        except Exception as exc:  # noqa: BLE001
            log.exception("suite change run %s crashed", run_id)
            row = vs.get_item(db, cid, run_id)
            if row is not None:
                p = vs.item_out(row)["payload"]
                p.update(state="failed", message=f"The run stopped unexpectedly: {exc}", finished_at=_now())
                vs.update_item(db, row, p)
        finally:
            db.close()

    ctx = contextvars.copy_context()
    threading.Thread(target=lambda: ctx.run(work), name=f"suite-change-{run_id}", daemon=True).start()


def _launch(db: Session, cid: str, run_row: Any) -> dict[str, Any]:
    if RUN_INLINE:
        execute_change(_client(cid, db), db, cid, run_row)
        run_row = vs.get_item(db, cid, run_row.id)
    else:
        _start(cid, run_row.id)
    return vs.item_out(run_row)


def _gate(db: Session, cid: str, batch_id: str, p: dict[str, Any]) -> list[dict[str, Any]]:
    ck = p.get("check") or {}
    h = sc.batch_hash(p)
    ready = _ready(ck)
    if not ck or ck.get("hash") != h or not ready or not dry_run_was_seen(
            RECEIPT_TOOL, {"connection_id": cid, "batch_id": batch_id, "hash": h, "ready": sorted(int(r["id"]) for r in ready)}):
        raise HTTPException(status_code=428, detail={"error": "check_required", "message": "Check this batch first. The check lasts one hour and covers only the records it marked ready.",
                                                     "options": ["Check again"]})
    if ck.get("needs_approval"):
        ap = rs.find_approval(db, cid, "suite_change", batch_id, h)
        if not ap or ap["status"] != "approved":
            raise HTTPException(status_code=403, detail={"error": "approval_required", "message": f"Over {ck.get('threshold')} records, or an accounting button, needs a manager's approval.",
                                                         "options": ["Ask for approval"], "approval": ap})
    return ready


@router.post("/batches/{batch_id}/run")
def batch_run(connection_id: str, batch_id: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Run on the ready records only. Each is re-checked right before Odoo is asked to change it."""
    row = _get(db, connection_id, batch_id, BATCH)
    p = vs.item_out(row)["payload"]
    ready = _gate(db, connection_id, batch_id, p)
    run = {"batch_id": batch_id, "kind": "run", "tool": p["tool"], "model": p["model"], "state": "queued", "stop_requested": False,
           "limits": p["check"]["limits"], "started_at": _now(), "finished_at": None, "by": rs._who(request).get("email"),
           "records": [{"id": r["id"], "name": r.get("name"), "state": "waiting", "check": r} for r in ready]}
    when = sc.send_at(p.get("change") or {}) if p["tool"] == "message" else None
    if when is not None and when <= datetime.now(UTC):
        raise HTTPException(status_code=409, detail={"error": "send_time_passed", "message": "The send time has passed. Pick a new time, or choose Send now.",
                                                     "options": ["Pick a new time", "Send now"]})
    if when is not None:
        # Send later: the check and approval are spent now; each record is still re-checked when it fires.
        run.update(state="scheduled", fire_at=when.isoformat())
        rep = (p.get("change") or {}).get("repeat")
        if rep:
            run.update(repeat={"every": rep["every"], "until": rep["until"]}, occurrence=1)
        run_row = vs.save_item(db, connection_id=connection_id, kind=CRUN, key=f"crun:{batch_id}", name=row.name, payload=run)
        _ensure_scheduler()
        return vs.item_out(run_row)
    run_row = vs.save_item(db, connection_id=connection_id, kind=CRUN, key=f"crun:{batch_id}", name=row.name, payload=run)
    return _launch(db, connection_id, run_row)


SCHEDULE_TICK_S = 15
_sched_lock = threading.Lock()
_sched_started = False


def fire_due(db: Session, now: datetime | None = None) -> list[str]:
    """Start every scheduled run whose time has come. Claims each run (scheduled -> queued) before starting it."""
    from app.db_models import ViewBuilderItem

    now = now or datetime.now(UTC)
    fired: list[str] = []
    vs._ensure_tables(db)
    for row in db.query(ViewBuilderItem).filter(ViewBuilderItem.kind == CRUN).all():
        p = vs.item_out(row)["payload"]
        if p.get("state") != "scheduled" or not p.get("fire_at"):
            continue
        try:
            due = datetime.fromisoformat(p["fire_at"]) <= now
        except ValueError:
            due = False
        if not due:
            continue
        p.update(state="queued", fired_at=_now())
        if not _claim(db, row, p):
            continue  # another API process (or a cancel) got there first
        fired.append(row.id)
        _schedule_next(db, row, p)
        if RUN_INLINE:
            execute_change(_client(row.connection_id, db), db, row.connection_id, vs.get_item(db, row.connection_id, row.id))
        else:
            _start(row.connection_id, row.id)
    return fired


def _schedule_next(db: Session, row: Any, p: dict[str, Any]) -> str | None:
    """Repeating send: the next occurrence is queued when this one fires, so cancelling the pending one ends the series.
    Each occurrence re-checks every record when it fires."""
    rep = p.get("repeat")
    if not rep:
        return None
    nxt = sc.next_send(datetime.fromisoformat(p.get("planned_at") or p["fire_at"]), rep["every"])
    until = sc.send_at({"send_at": rep["until"]})
    if until is None or nxt > until:
        return None
    run = {**{k: v for k, v in p.items() if k != "planned_at"}, "state": "scheduled", "fire_at": nxt.isoformat(), "fired_at": None, "started_at": _now(), "finished_at": None,
           "stop_requested": False, "occurrence": int(p.get("occurrence") or 1) + 1, "series_of": p.get("series_of") or row.id,
           "records": [{"id": r["id"], "name": r.get("name"), "state": "waiting", "check": r.get("check")} for r in p["records"]]}
    return vs.save_item(db, connection_id=row.connection_id, kind=CRUN, key=row.key, name=row.name, payload=run).id


def _ensure_scheduler() -> None:
    global _sched_started
    with _sched_lock:
        if _sched_started or RUN_INLINE:
            return
        _sched_started = True

    def loop() -> None:
        from app.db import SessionLocal
        while True:
            db = SessionLocal()
            try:
                fire_due(db)
            except Exception:  # noqa: BLE001
                log.exception("send-later tick failed")
            finally:
                db.close()
            time.sleep(SCHEDULE_TICK_S)

    threading.Thread(target=loop, name="suite-send-later", daemon=True).start()


@router.get("/runs/{run_id}")
def change_run_get(connection_id: str, run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    out = vs.item_out(_get(db, connection_id, run_id, CRUN))
    recs = out["payload"]["records"]
    out["payload"]["counts"] = {k: sum(1 for r in recs if r["state"] == k) for k in ("waiting", "done", "no_change", "skipped", "failed")}
    return out


@router.get("/runs")
def change_runs(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"runs": [{"id": r.id, "name": r.name, **{k: vs.item_out(r)["payload"].get(k) for k in ("state", "kind", "tool", "batch_id", "started_at", "fire_at", "repeat", "occurrence")}}
                     for r in vs.list_items(db, connection_id, CRUN)]}


@router.post("/runs/{run_id}/stop")
def change_run_stop(connection_id: str, run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _get(db, connection_id, run_id, CRUN)
    p = vs.item_out(row)["payload"]
    if p["state"] == "scheduled":
        return change_run_cancel(connection_id, run_id, db)
    if p["state"] in {"queued", "running"}:
        p["stop_requested"] = True
        vs.update_item(db, row, p)
    return {"ok": True, "state": p["state"], "stop_requested": p.get("stop_requested", False)}


class RescheduleBody(BaseModel):
    send_at: str
    # Repeating sends: "this" moves only this send (later sends keep their times); "series" shifts the rest too.
    move: str = Field(default="this", pattern="^(this|series)$")


@router.post("/runs/{run_id}/reschedule")
def change_run_reschedule(connection_id: str, run_id: str, body: RescheduleBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Move a pending send. Only the time changes, so the check isn't redone; every record is still re-checked when it fires."""
    row = _get(db, connection_id, run_id, CRUN)
    db.refresh(row)
    p = vs.item_out(row)["payload"]
    when = sc.send_at({"send_at": body.send_at})
    now = datetime.now(UTC)
    problem = None
    if when is None:
        problem = "Pick a valid date and time to send."
    elif when <= now:
        problem = "Pick a time in the future."
    elif (when - now).days >= sc.SEND_LATER_MAX_DAYS:
        problem = f"Send later can wait up to {sc.SEND_LATER_MAX_DAYS} days."
    elif p.get("repeat") and when > (sc.send_at({"send_at": p["repeat"]["until"]}) or when):
        problem = "That's after the repeating send ends."
    if problem:
        raise HTTPException(status_code=422, detail={"error": "bad_time", "message": problem, "options": ["Pick another time"]})
    new = {**p, "fire_at": when.isoformat(), "rescheduled_at": _now()}
    if p.get("repeat"):
        if body.move == "this":
            new["planned_at"] = p.get("planned_at") or p["fire_at"]  # the series keeps counting from the planned time
        else:
            new.pop("planned_at", None)
    if p["state"] != "scheduled" or not _claim(db, row, new):
        raise HTTPException(status_code=409, detail={"error": "not_scheduled", "message": "This send already started, so it can't be moved.", "options": ["Stop"]})
    return {"ok": True, "state": "scheduled", "fire_at": when.isoformat()}


@router.post("/runs/{run_id}/cancel")
def change_run_cancel(connection_id: str, run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Cancel a Send later run before it fires. Nothing was sent, so there is nothing to undo."""
    row = _get(db, connection_id, run_id, CRUN)
    db.refresh(row)
    p = vs.item_out(row)["payload"]
    ok = p["state"] == "scheduled"
    if ok:
        p.update(state="cancelled", finished_at=_now(), message="Cancelled before it was sent.")
        for r in p["records"]:
            r["state"] = "skipped"
        ok = _claim(db, row, p)
    if not ok:
        raise HTTPException(status_code=409, detail={"error": "not_scheduled", "message": "This run already started, so it can't be cancelled. Stop it instead.",
                                                     "options": ["Stop"]})
    return {"ok": True, "state": "cancelled"}


def _claim(db: Session, row: Any, new: dict[str, Any]) -> bool:
    """Compare-and-set on the stored payload, so a scheduled run is fired or cancelled exactly once across processes."""
    import json

    from sqlalchemy import update

    from app.db_models import ViewBuilderItem

    old = row.payload
    res = db.execute(update(ViewBuilderItem).where(ViewBuilderItem.id == row.id, ViewBuilderItem.payload == old)
                     .values(payload=json.dumps(new), updated_at=datetime.now(UTC)))
    db.commit()
    db.refresh(row)
    return res.rowcount == 1


@router.post("/runs/{run_id}/undo")
def change_run_undo(connection_id: str, run_id: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Undo what this run did, newest first. Records changed again since the run are left alone and listed."""
    row = _get(db, connection_id, run_id, CRUN)
    p = vs.item_out(row)["payload"]
    if p["kind"] != "run" or p["state"] in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Only a finished or stopped run can be undone.")
    done = [r for r in p["records"] if r["state"] == "done"]
    if not done:
        raise HTTPException(status_code=409, detail="This run changed nothing.")
    if p["tool"] == "transitions" and not any((r.get("undo") or {}).get("method") for r in done):
        raise HTTPException(status_code=409, detail={"error": "one_way", "message": "Odoo has no button to undo this. Change these records back in Odoo if needed."})
    undo = {"batch_id": p["batch_id"], "kind": "undo", "undo_of": run_id, "tool": p["tool"], "model": p["model"], "state": "queued", "stop_requested": False,
            "limits": {**p["limits"], "pace_ms": p["limits"].get("pace_ms", 0)}, "started_at": _now(), "finished_at": None, "by": rs._who(request).get("email"),
            "records": [{"id": r["id"], "name": r.get("name"), "state": "waiting", "source": {"id": r["id"], "undo": r.get("undo")}} for r in reversed(done)]}
    urow = vs.save_item(db, connection_id=connection_id, kind=CRUN, key=f"crun:{p['batch_id']}", name=f"Undo: {row.name}"[:120], payload=undo)
    return _launch(db, connection_id, urow)


@router.get("/runs/{run_id}/export")
def change_run_export(connection_id: str, run_id: str, db: Session = Depends(get_db)) -> Response:
    p = vs.item_out(_get(db, connection_id, run_id, CRUN))["payload"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Record", "Name", "Result", "Why"])
    for r in p["records"]:
        w.writerow([r["id"], r.get("name") or "", r["state"], r.get("message") or ""])
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="run-{run_id[:8]}.csv"'})


# ---------------------------------------------------------------- scheduled runs (re-check before running)
SCHED = "suite_csched"
_ticker_started = False


class ScheduleBody(BaseModel):
    run_at: str


@router.post("/batches/{batch_id}/schedule")
def batch_schedule(connection_id: str, batch_id: str, body: ScheduleBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _get(db, connection_id, batch_id, BATCH)
    p = vs.item_out(row)["payload"]
    _gate(db, connection_id, batch_id, p)
    try:
        when = datetime.fromisoformat(body.run_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Give a date and time.") from exc
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    srow = vs.save_item(db, connection_id=connection_id, kind=SCHED, key=f"sched:{batch_id}", name=row.name, payload={
        "batch_id": batch_id, "run_at": when.isoformat(), "status": "scheduled", "ready_ids": sorted(int(r["id"]) for r in _ready(p["check"])),
        "by": rs._who(request).get("email")})
    _ensure_ticker()
    return {"ok": True, "schedule_id": srow.id, "run_at": when.isoformat(), "note": "It checks again first and runs only if the same records are still ready."}


def run_due_schedules(db: Session, cid: str, client: Any, now: datetime | None = None) -> list[dict[str, Any]]:
    """Fire due schedules. Each re-checks; if the ready records differ, it waits for a person instead of running."""
    now = now or datetime.now(UTC)
    out = []
    for srow in vs.list_items(db, cid, SCHED):
        s = vs.item_out(srow)["payload"]
        if s["status"] != "scheduled" or datetime.fromisoformat(s["run_at"]) > now:
            continue
        brow = vs.get_item(db, cid, s["batch_id"])
        if brow is None:
            continue
        rep = batch_check(cid, s["batch_id"], db) if client is None else _check_with(client, db, cid, brow)
        now_ready = sorted(int(r["id"]) for r in _ready(rep))
        if now_ready != s["ready_ids"]:
            s.update(status="needs_check", message="The records that are ready changed since it was scheduled. Check and schedule again.")
        else:
            try:
                res = batch_run(cid, s["batch_id"], None, db)  # type: ignore[arg-type]
                s.update(status="started", run_id=res["id"])
            except HTTPException as exc:
                s.update(status="needs_check", message=str(exc.detail))
        vs.update_item(db, srow, s)
        out.append(s)
    return out


def _check_with(client: Any, db: Session, cid: str, brow: Any) -> dict[str, Any]:
    return batch_check(cid, brow.id, db)


def _ensure_ticker() -> None:
    global _ticker_started
    if _ticker_started or RUN_INLINE:
        return
    _ticker_started = True

    def loop() -> None:
        from app.db import SessionLocal

        while True:
            time.sleep(60)
            db = SessionLocal()
            try:
                cids = {r.connection_id for r in db.query(vs.ViewBuilderItem).filter(vs.ViewBuilderItem.kind == SCHED).all()}
                for cid in cids:
                    try:
                        run_due_schedules(db, cid, None)
                    except Exception:  # noqa: BLE001
                        log.exception("suite schedule tick failed for %s", cid)
            finally:
                db.close()

    threading.Thread(target=loop, name="suite-schedules", daemon=True).start()


# Scheduled sends must survive an API restart, so the ticker starts with the app (not under tests).
if "pytest" not in __import__("sys").modules:
    _ensure_scheduler()
