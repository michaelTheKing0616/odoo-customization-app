"""Configuration Suite API (stage 1).

Read endpoints for the suite home, capabilities and the model inspector, plus
the Bulk Setup foundation: catalog, plans (change sets), Check with a receipt,
Run in waves under the connection's mutation lock, Stop/Continue, and Undo as
a reverse plan. Code authorizes every write; nothing here trusts AI output.
"""

from __future__ import annotations

import json

import base64
import contextvars
import logging
import threading
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import suite_catalog as cat
from app import suite_setup as ss
from app import suite_workbook as swb
from app import suite_store as vs
from app.db import get_db
from app import suite_changeset as sc
from app.dry_run_ledger import dry_run_was_seen, remember_dry_run
from app.mutation_lock import ConnectionMutationBusy, connection_mutation_lock
from app.odoo_service import get_connection_or_404
from app.routers.view_engine import _client
from app.tier_matrix import build_tier_context, evaluate_tier_matrix

log = logging.getLogger(__name__)
router = APIRouter(prefix="/connections/{connection_id}/suite", tags=["suite"])

PLAN, RUN, POLICY = "suite_plan", "suite_run", "suite_policy"
RUN_INLINE = False  # tests flip this to run synchronously


def _who(request: Request | None) -> dict[str, Any]:
    auth = getattr(getattr(request, "state", None), "auth", None) if request is not None else None
    mode = str(getattr(auth, "mode", "off") or "off")
    return {"mode": mode, "user_id": getattr(auth, "user_id", None), "email": getattr(auth, "email", None),
            "verified": mode == "accounts" and bool(getattr(auth, "user_id", None))}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _x(client: Any, model: str, method: str, args: list[Any] | None = None, kw: dict[str, Any] | None = None) -> Any:
    return client.execute_kw(model, method, args or [], kw or {})


def _try(fn: Any, default: Any) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001  app missing or access refused
        return default


def _row(db: Session, connection_id: str) -> Any:
    try:
        return get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _major(client: Any) -> int:
    try:
        return int(client.capabilities.major)
    except Exception:  # noqa: BLE001
        return 0


def _version(client: Any, row: Any) -> str:
    v = _try(lambda: str(client.server_version().get("server_version") or ""), "")
    return v or str(getattr(row, "server_version", "") or "")


def _installed(client: Any) -> list[str]:
    return [r["name"] for r in _try(lambda: _x(client, "ir.module.module", "search_read", [[("state", "=", "installed")]], {"fields": ["name"]}), [])]


def _policy(db: Session, connection_id: str) -> dict[str, Any]:
    rows = vs.list_items(db, connection_id, POLICY, "policy")
    base = {"approval_threshold": ss.APPROVAL_THRESHOLD, "approval_for_accounting": True, "cloud_ai": False, "cloud_ai_consent_by": None}
    if rows:
        base.update(vs.item_out(rows[0])["payload"])
    return base


# ---------------------------------------------------------------- home, capabilities, inspector
@router.get("/home")
def suite_home(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _row(db, connection_id)
    client = _client(connection_id, db)
    version = _version(client, row)
    mods = _installed(client)
    ctx = build_tier_context(url=row.url, saved_hosting=getattr(row, "hosting", None), server_version=version, installed_modules=mods)
    apps = _try(lambda: _x(client, "ir.module.module", "search_read", [[("state", "=", "installed"), ("application", "=", True)]], {"fields": ["shortdesc"]}), [])
    companies = _try(lambda: _x(client, "res.company", "search_read", [[]], {"fields": ["name", "country_id", "currency_id"]}), [])
    langs = _try(lambda: _x(client, "res.lang", "search_read", [[("active", "=", True)]], {"fields": ["code"]}), [])
    facts = ss.db_facts(client)
    needs: list[dict[str, Any]] = []
    cmeta = _try(lambda: _x(client, "ir.cron", "fields_get", [["failure_count"]], {"attributes": ["type"]}), {})
    if "failure_count" in cmeta:
        bad = _try(lambda: _x(client, "ir.cron", "search_read", [[("failure_count", ">", 0)]], {"fields": ["name", "failure_count"], "limit": 5}), [])
        for c in bad:
            needs.append({"kind": "schedule_failing", "text": f"Scheduled action '{c['name']}' failed {c['failure_count']} time(s) in a row.",
                          "href": f"/connections/{connection_id}/suite/upkeep/schedules"})
    runs = [vs.item_out(r) for r in vs.list_items(db, connection_id, RUN)][:5]
    for r in runs:
        if r["payload"].get("state") in {"paused", "failed"}:
            needs.append({"kind": "run_paused", "text": f"Setup run '{r['name']}' is paused and needs a decision.",
                          "href": f"/connections/{connection_id}/suite/setup?run={r['id']}&view=run"})
    mode = str(getattr(row, "write_mode", "standard") or "standard")
    writes_on = mode != "observer" and not bool(getattr(row, "writes_paused", False))
    return {
        "passport": {"version": version, "major": _major(client), "edition": ctx.edition, "hosting": ctx.hosting,
                     "database": row.db_name, "url": row.url, "apps": sorted(a["shortdesc"] for a in apps),
                     "companies": [{"id": c["id"], "name": c["name"], "country": (c.get("country_id") or [None, ""])[1],
                                    "currency": (c.get("currency_id") or [None, ""])[1]} for c in companies],
                     "languages": [lg["code"] for lg in langs],
                     "localization": sorted(m for m in mods if m.startswith("l10n_") and m.count("_") == 1)},
        "writes": {"on": writes_on, "mode": mode, "paused": bool(getattr(row, "writes_paused", False))},
        "facts": facts,
        "needs_you": needs,
        "recent_runs": [{"id": r["id"], "name": r["name"], "state": r["payload"].get("state"), "kind": r["payload"].get("kind"),
                         "started_at": r["payload"].get("started_at")} for r in runs],
    }


@router.get("/capabilities")
def suite_capabilities(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _row(db, connection_id)
    client = _client(connection_id, db)
    version = _version(client, row)
    mods = _installed(client)
    ctx = build_tier_context(url=row.url, saved_hosting=getattr(row, "hosting", None), server_version=version, installed_modules=mods)
    rows = [{"key": r.key, "label": r.label, "available": r.available, "reason": r.reason, "options": list(r.options)} for r in evaluate_tier_matrix(ctx)]
    extra = [
        ("automations", "Automations", "base_automation", "Install Automation Rules (base_automation)."),
        ("portal", "Portal access", "portal", "Install Customer Portal (portal)."),
        ("spreadsheet_import", "Data import", "base_import", "Install base_import."),
    ]
    for key, label, mod, fix in extra:
        ok = mod in mods
        rows.append({"key": key, "label": label, "available": "yes" if ok else "no", "reason": "" if ok else "Its app is not installed.",
                     "options": [] if ok else [fix]})
    return {"version": version, "edition": ctx.edition, "hosting": ctx.hosting, "capabilities": rows}


def _view_stack(client: Any, model: str, vtype: str = "form") -> list[dict[str, Any]]:
    """Layers in Odoo's own order: each primary view, then its extensions by (priority, id), depth first."""
    rows = _x(client, "ir.ui.view", "search_read", [[("model", "=", model), ("type", "=", vtype)]],
              {"fields": ["name", "priority", "inherit_id", "mode", "key"], "order": "priority, id"})
    kids: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        if r.get("inherit_id") and r.get("mode") == "extension":
            kids.setdefault(int(r["inherit_id"][0]), []).append(r)
    out: list[dict[str, Any]] = []

    def walk(v: dict[str, Any], depth: int, root: int) -> None:
        out.append({"id": v["id"], "name": v["name"], "key": v.get("key") or "", "priority": v["priority"], "depth": depth,
                    "mode": v.get("mode"), "root": root})
        for k in sorted(kids.get(int(v["id"]), []), key=lambda r: (r["priority"], r["id"])):
            walk(k, depth + 1, root)

    for r in rows:
        if r.get("mode") == "primary":
            walk(r, 0, int(r["id"]))
    return out


@router.get("/inspector/{model}")
def suite_inspector(connection_id: str, model: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    if not _try(lambda: _x(client, "ir.model", "search", [[("model", "=", model)]]), []):
        raise HTTPException(status_code=404, detail=f"{model} is not on this database.")
    meta = _x(client, model, "fields_get", [], {"attributes": ["string", "type", "relation", "required", "store", "readonly"]})
    total = int(_try(lambda: _x(client, model, "search_count", [[]]), 0))
    fields_out = []
    filled_budget = 60
    for name, m in sorted(meta.items(), key=lambda kv: kv[0]):
        filled = None
        if m.get("store") and filled_budget > 0 and m.get("type") not in {"binary", "one2many", "many2many"} and total:
            filled_budget -= 1
            filled = int(_try(lambda n=name: _x(client, model, "search_count", [[(n, "!=", False)]]), 0))
        fields_out.append({"name": name, "label": m.get("string") or name, "type": m.get("type"), "relation": m.get("relation"),
                           "required": bool(m.get("required")), "stored": bool(m.get("store")), "filled": filled})
    links = sorted({m["relation"] for m in meta.values() if m.get("relation")})
    access: list[dict[str, Any]] = []
    acc = _try(lambda: _x(client, "ir.model.access", "search_read", [[("model_id.model", "=", model)]],
                          {"fields": ["name", "group_id", "perm_read", "perm_write", "perm_create", "perm_unlink"]}), None)
    if acc is None:
        acc = _try(lambda: _x(client, "ir.access", "search_read", [[("model_id.model", "=", model)]], {"fields": ["name", "group_id"]}), [])
    for a in acc:
        access.append({"name": a.get("name"), "group": (a.get("group_id") or [None, "Everyone"])[1],
                       **{k: a.get(k) for k in ("perm_read", "perm_write", "perm_create", "perm_unlink") if k in a}})
    return {"model": model, "records": total, "fields": fields_out, "links": links,
            "views": {"form": _try(lambda: _view_stack(client, model, "form"), []), "list": _try(lambda: _view_stack(client, model, _list_type(client)), [])},
            "access": access}


def _list_type(client: Any) -> str:
    return "list" if _major(client) >= 18 else "tree"


# ---------------------------------------------------------------- catalog and targets
def _live_models(client: Any) -> set[str]:
    return {r["model"] for r in _try(lambda: _x(client, "ir.model", "search_read", [[]], {"fields": ["model"]}), [])}


@router.get("/setup/catalog")
def suite_setup_catalog(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _row(db, connection_id)
    client = _client(connection_id, db)
    version = _version(client, row)
    major = _major(client)
    ctx = build_tier_context(url=row.url, saved_hosting=getattr(row, "hosting", None), server_version=version, installed_modules=_installed(client))
    sfields = set(_try(lambda: _x(client, "res.config.settings", "fields_get", [], {"attributes": ["type"]}), {}).keys())
    tasks = cat.catalog_for(major, models=_live_models(client), settings_fields=sfields, edition=ctx.edition)
    return {"version": version, "major": major, "edition": ctx.edition, "ranks": cat.RANK_LABEL,
            "counts": {"total": len(tasks), "available": sum(1 for t in tasks if t["state"] == "available")}, "tasks": tasks}


@router.get("/setup/import-targets")
def suite_import_targets(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Only models installed here that this login can create (code decides, not the AI)."""
    client = _client(connection_id, db)
    wanted = cat.document_targets()
    rows = _try(lambda: _x(client, "ir.model", "search_read", [[("model", "in", wanted), ("transient", "=", False)]], {"fields": ["model", "name"]}), [])
    out = []
    for r in rows:
        ok = _try(lambda m=r["model"]: bool(_x(client, m, "has_access", [[], "create"])), None)  # 18+: recordset method
        if ok is None:
            ok = _try(lambda m=r["model"]: bool(_x(client, m, "check_access_rights", ["create"], {"raise_exception": False})), False)
        if ok:
            out.append({"model": r["model"], "label": r["name"], "guarded": r["model"] in ss.GUARDED_MODELS})
    return {"targets": sorted(out, key=lambda t: t["label"]), "considered": len(wanted)}


@router.get("/setup/builder-options")
def suite_builder_options(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Choices for the plain step builder, read from this database (settings, units, categories)."""
    client = _client(connection_id, db)
    sf = swb.setting_fields(client)
    cur = _try(lambda: _x(client, "res.config.settings", "default_get", [[f["field"] for f in sf]]), {}) if sf else {}
    units = _try(lambda: [r["name"] for r in _x(client, "uom.uom", "search_read", [[]], {"fields": ["name"], "order": "name", "limit": 500})], [])
    cats = _try(lambda: [r["complete_name"] for r in _x(client, "product.category", "search_read", [[]], {"fields": ["complete_name"], "order": "complete_name", "limit": 500})], [])
    return {"settings": [{**f, "value": cur.get(f["field"])} for f in sf], "units": units, "categories": cats}


class ImportPreviewBody(BaseModel):
    filename: str = Field(default="", max_length=200)
    content_b64: str | None = Field(default=None, max_length=14_000_000)
    text: str | None = Field(default=None, max_length=2_000_000)
    model: str | None = None  # choose the target for every table
    job: str | None = Field(default=None, max_length=16)


@router.post("/setup/import/preview")
def suite_import_preview(connection_id: str, body: ImportPreviewBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Read a pasted text or file, suggest targets (only ones this login can create), map columns by code. Writes nothing."""
    import uuid

    from app import suite_import as si

    if body.text is None and not body.content_b64:
        raise HTTPException(status_code=422, detail="Paste some rows or choose a file.")
    try:
        raw = base64.b64decode(body.content_b64) if body.content_b64 else None
        tables, notes = si.read_document(body.filename, raw, body.text)
    except Exception as exc:  # noqa: BLE001  unreadable file
        raise HTTPException(status_code=422, detail=f"Could not read this file: {exc}") from exc
    client = _client(connection_id, db)
    targets = [t for t in suite_import_targets(connection_id, db)["targets"] if not t["guarded"]]
    labels = {t["model"]: t["label"] for t in targets}
    fcache: dict[str, Any] = {}
    metas = {m: ss._fields(client, m, fcache) or {} for m in ([body.model] if body.model else list(labels))}
    if body.model and body.model not in labels:
        raise HTTPException(status_code=422, detail="That record type isn't an import target you can create here.")
    job = body.job or uuid.uuid4().hex[:8]
    out = []
    for n, t in enumerate(tables, start=1):
        ranked = si.rank_targets(t["headers"], metas, labels)
        model = body.model or (ranked[0]["model"] if ranked else None)
        mapping, questions = si.map_columns(t["headers"], metas[model]) if model else ({}, [])
        out.append({"table": n, "name": t["name"], "headers": t["headers"], "rows": t["rows"], "row_count": len(t["rows"]),
                    "sample": t["rows"][:5], "candidates": ranked, "model": model, "mapping": mapping, "questions": questions,
                    "missing_required": si.required_missing(mapping, metas[model]) if model else [],
                    "step": {"type": "import", "inputs": {"model": model, "headers": t["headers"], "rows": t["rows"], "mapping": mapping, "skip": [],
                                                          "job": job, "table": n}} if model else None})
    return {"job": job, "tables": out, "notes": notes, "targets": targets}


# ---------------------------------------------------------------- policy (D3, D6)
class PolicyBody(BaseModel):
    approval_threshold: int | None = Field(default=None, ge=1, le=100000)
    cloud_ai: bool | None = None


@router.get("/setup/policy")
def suite_policy_get(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _policy(db, connection_id)


@router.put("/setup/policy")
def suite_policy_put(connection_id: str, body: PolicyBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    cur = _policy(db, connection_id)
    if body.approval_threshold is not None:
        cur["approval_threshold"] = body.approval_threshold
    if body.cloud_ai is not None:
        cur["cloud_ai"] = body.cloud_ai
        cur["cloud_ai_consent_by"] = (_who(request).get("email") or "this workspace") if body.cloud_ai else None
        cur["cloud_ai_consent_at"] = _now() if body.cloud_ai else None
    vs.save_item(db, connection_id=connection_id, kind=POLICY, key="policy", name="Setup policy", payload=cur, replace_key=True)
    return cur


# ---------------------------------------------------------------- plans
class PlanBody(BaseModel):
    name: str = Field(default="Setup plan", max_length=120)
    steps: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)


def _plan_view(row: Any) -> dict[str, Any]:
    out = vs.item_out(row)
    p = out["payload"]
    waves, errs = ss.order_waves(p.get("steps", []))
    p["waves"] = waves
    p["order_errors"] = errs
    p["hash"] = ss.plan_hash(p.get("steps", []))
    p["rank_labels"] = {s["id"]: cat.RANK_LABEL.get(s["rank"], "") for s in p.get("steps", [])}
    return out


def _with_approval(db: Session, connection_id: str, out: dict[str, Any]) -> dict[str, Any]:
    out["payload"]["approval"] = find_approval(db, connection_id, "suite_plan", out["id"], out["payload"]["hash"])
    return out


def _get(db: Session, connection_id: str, item_id: str, kind: str) -> Any:
    row = vs.get_item(db, connection_id, item_id)
    if row is None or row.kind != kind:
        raise HTTPException(status_code=404, detail="Not found.")
    return row


@router.get("/setup/plans")
def suite_plans(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = vs.list_items(db, connection_id, PLAN)
    return {"plans": [{"id": r.id, "name": r.name, "kind": vs.item_out(r)["payload"].get("kind"),
                       "steps": len(vs.item_out(r)["payload"].get("steps", [])), "created_at": vs.item_out(r)["created_at"]} for r in rows]}


def _save_plan(db: Session, connection_id: str, name: str, steps: list[dict[str, Any]], *, kind: str = "setup",
               who: dict[str, Any] | None = None, extra: dict[str, Any] | None = None) -> Any:
    norm, errors = ss.normalise_steps(steps, kind=kind)
    if errors:
        raise HTTPException(status_code=422, detail={"error": "plan_invalid", "message": " ".join(errors[:5]), "errors": errors})
    waves, oerr = ss.order_waves(norm)
    if oerr:
        raise HTTPException(status_code=422, detail={"error": "plan_order", "message": " ".join(oerr), "errors": oerr})
    payload = {"kind": kind, "steps": norm, "created_by": (who or {}).get("email"), "created_by_id": (who or {}).get("user_id"),
               "created_at": _now(), "check": None, "approval": None, **(extra or {})}
    return vs.save_item(db, connection_id=connection_id, kind=PLAN, key=f"plan:{kind}", name=name, payload=payload)


@router.post("/setup/plans")
def suite_plan_create(connection_id: str, body: PlanBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    _row(db, connection_id)
    return _plan_view(_save_plan(db, connection_id, body.name, body.steps, who=_who(request)))


@router.get("/setup/plans/{plan_id}")
def suite_plan_get(connection_id: str, plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _with_approval(db, connection_id, _plan_view(_get(db, connection_id, plan_id, PLAN)))


@router.put("/setup/plans/{plan_id}")
def suite_plan_update(connection_id: str, plan_id: str, body: PlanBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _get(db, connection_id, plan_id, PLAN)
    p = vs.item_out(row)["payload"]
    norm, errors = ss.normalise_steps(body.steps, kind=p.get("kind", "setup"))
    if errors:
        raise HTTPException(status_code=422, detail={"error": "plan_invalid", "message": " ".join(errors[:5]), "errors": errors})
    p.update(steps=norm, check=None, approval=None)  # any edit voids the old check and approval
    row.name = body.name[:120]
    vs.update_item(db, row, p)
    return _plan_view(row)


@router.post("/setup/plans/{plan_id}/dry-run")
def suite_plan_check(connection_id: str, plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Check: reads only. Gives each step a verdict and, when everything can run, a one-hour receipt."""
    row = _get(db, connection_id, plan_id, PLAN)
    p = vs.item_out(row)["payload"]
    client = _client(connection_id, db)
    pol = _policy(db, connection_id)
    report = ss.check_plan(client, p["steps"], threshold=int(pol["approval_threshold"]))
    phash = ss.plan_hash(p["steps"])
    report.update(plan_hash=phash, checked_at=_now(), receipt=None)
    gate = sc.gate(p["steps"])  # shared change-set validator + protected registry + policy
    report["changeset"] = gate
    for sid, why in gate["blocked"].items():
        report["steps"].setdefault(sid, {}).update(verdict="blocked", message=why)
        report["can_apply"] = False
    if report["can_apply"]:
        report["receipt"] = remember_dry_run(ss.RECEIPT_TOOL, ss.receipt_args(connection_id, plan_id, phash))
        report["receipt_expires_in_s"] = 3600
    p["check"] = report
    vs.update_item(db, row, p)
    return report


class EveryVersionBody(BaseModel):
    targets: list[str] = Field(default_factory=list, max_length=8)


@router.post("/setup/plans/{plan_id}/check-every-version")
def suite_plan_check_every_version(connection_id: str, plan_id: str, body: EveryVersionBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Stage 4 "Check on every version": the same plan checked (reads only) on other saved databases, for
    example test copies on Odoo 17-20. No receipt is given for them: each database still needs its own Check."""
    row = _get(db, connection_id, plan_id, PLAN)
    p = vs.item_out(row)["payload"]
    out = []
    for cid in [connection_id, *[t for t in body.targets if t != connection_id]]:
        try:
            client = _client(cid, db)
            rep = ss.check_plan(client, p["steps"])
            out.append({"connection_id": cid, "version": str(client.capabilities.major), "counts": rep["counts"],
                        "can_apply": rep["can_apply"],
                        "problems": [{"step": sid, "verdict": r["verdict"], "message": r["message"]}
                                     for sid, r in rep["steps"].items() if r["verdict"] in {"blocked", "needs_input"}][:20]})
        except HTTPException as exc:
            out.append({"connection_id": cid, "error": str(exc.detail)})
        except Exception as exc:  # noqa: BLE001  one unreachable database must not hide the others
            out.append({"connection_id": cid, "error": f"Couldn't check this database: {ss.fault_line(exc)}"})
    same = len({json.dumps(o.get("counts"), sort_keys=True) for o in out if "counts" in o}) <= 1
    return {"results": out, "same_everywhere": same}


def find_approval(db: Session, connection_id: str, action: str, ref_id: str, ref_hash: str) -> dict[str, Any] | None:
    """The builders' approval item for exactly this checked plan or batch, if any."""
    for r in vs.list_items(db, connection_id, "approval"):
        p = vs.item_out(r)["payload"]
        ap = p.get("action_payload") or {}
        if p.get("action") == action and ap.get("ref_id") == ref_id and ap.get("ref_hash") == ref_hash:
            return {"id": r.id, **{k: p.get(k) for k in ("status", "requested_by", "decided_by", "decided_at", "decider_verified", "reason")}}
    return None


def approval_still_matches(connection_id: str, db: Session, action: str, ref: Any) -> dict[str, Any]:
    """Called by the approvals flow when a manager approves: the plan must still be the one that was checked."""
    row = vs.get_item(db, connection_id, ref.ref_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That plan or batch no longer exists.")
    p = vs.item_out(row)["payload"]
    current = ss.plan_hash(p.get("steps", [])) if action == "suite_plan" else (p.get("check") or {}).get("hash")
    if current != ref.ref_hash:
        raise HTTPException(status_code=409, detail="It changed after it was sent for approval. Check it again and ask again.")
    return {"ok": True, "approved": ref.ref_id, "note": "Approved. The person who asked can run it now."}


def ask_approval(connection_id: str, db: Session, request: Request | None, action: str, ref_id: str, ref_hash: str, summary: list[str]) -> dict[str, Any]:
    from app.routers import view_engine_2c as r2c

    found = find_approval(db, connection_id, action, ref_id, ref_hash)
    if found and found["status"] in {"pending", "approved"}:
        return {"ok": True, "item_id": found["id"], "status": found["status"]}
    return r2c.approval_request_action(connection_id, r2c.ApprovalActionBody(
        action=action, payload={"ref_id": ref_id, "ref_hash": ref_hash, "kind": action}, summary=summary), request, db)  # type: ignore[arg-type]


@router.post("/setup/plans/{plan_id}/request-approval")
def suite_plan_request_approval(connection_id: str, plan_id: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """D3: goes to the builders' approvals list; someone else approves there."""
    row = _get(db, connection_id, plan_id, PLAN)
    p = vs.item_out(row)["payload"]
    phash = ss.plan_hash(p["steps"])
    if not p.get("check") or p["check"].get("plan_hash") != phash:
        raise HTTPException(status_code=409, detail="Check the plan before asking for approval.")
    c = p["check"]["counts"]
    out = ask_approval(connection_id, db, request, "suite_plan", plan_id, phash,
                       [f"Run setup plan: {row.name}", f"{c['ready']} steps ready", *[s["label"] for s in p["steps"]][:8]])
    card = sc.submit_to_inbox(db, connection_id, row.name, p["steps"], requester_id=str(_who(request).get("email") or ""))
    if card:
        p["inbox_cards"] = card
        vs.update_item(db, row, p)
    return out


# ---------------------------------------------------------------- runs
def _new_run(plan_row: Any, plan: dict[str, Any], who: dict[str, Any]) -> dict[str, Any]:
    by_id = {s["id"]: s for s in plan["steps"]}
    check = plan["check"]
    return {"plan_id": plan_row.id, "plan_name": plan_row.name, "kind": plan.get("kind", "setup"), "state": "queued",
            "stop_requested": False, "started_at": _now(), "finished_at": None, "by": who.get("email"),
            "plan_hash": check["plan_hash"],
            "waves": [{"n": i + 1, "steps": [{"id": sid, "label": by_id[sid]["label"], "state": "waiting",
                                              "message": check["steps"].get(sid, {}).get("message", ""), "undo": None} for sid in w]}
                      for i, w in enumerate(check["waves"])]}


def _deps_closure(steps: list[dict[str, Any]], failed: str) -> set[str]:
    deps = ss.implied_deps(steps)
    out = {failed}
    changed = True
    while changed:
        changed = False
        for sid, ds in deps.items():
            if sid not in out and ds & out:
                out.add(sid)
                changed = True
    return out - {failed}


def _planned_names(steps: list[dict[str, Any]]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for s in steps:
        inp = s.get("inputs") or {}
        if s.get("type") == "create" and (inp.get("values") or {}).get("name"):
            out.add((str(inp["model"]), str(inp["values"]["name"])))
        if s.get("type") == "units" and inp.get("name"):
            out.add(("uom.uom", str(inp["name"])))
    return out


def execute_run(client: Any, db: Session, connection_id: str, run_row: Any) -> dict[str, Any]:
    """Run waves in order under the connection's mutation lock. Stops on the first failure in a wave."""
    run = vs.item_out(run_row)["payload"]
    plan_row = vs.get_item(db, connection_id, run["plan_id"])
    plan = vs.item_out(plan_row)["payload"]
    by_id = {s["id"]: s for s in plan["steps"]}
    checked = plan["check"]["steps"]
    made: dict[str, int] = dict(run.get("made") or {})
    try:
        with connection_mutation_lock(connection_id, f"suite setup run {run_row.id}"):
            run["state"] = "running"
            vs.update_item(db, run_row, run)
            for wave in run["waves"]:
                for st in wave["steps"]:
                    if st["state"] != "waiting":
                        continue
                    db.refresh(run_row)
                    if vs.item_out(run_row)["payload"].get("stop_requested"):
                        run["state"] = "stopped"
                        run["finished_at"] = _now()
                        vs.update_item(db, run_row, run)
                        return run
                    if checked.get(st["id"], {}).get("verdict") == "no_change":
                        st.update(state="no_change", message=checked[st["id"]].get("message", ""))
                        continue
                    st["state"] = "running"
                    vs.update_item(db, run_row, run)
                    try:
                        chk = checked.get(st["id"], {})
                        if chk.get("after_install") or chk.get("after_create"):
                            # The record type arrived with an earlier wave's install: check it for real now.
                            chk = ss.check_step(client, by_id[st["id"]], facts=ss.db_facts(client), fcache={},
                                                planned=set() if chk.get("after_create") else _planned_names(plan["steps"]))
                            if chk["verdict"] == "no_change":
                                st.update(state="no_change", message=chk.get("message", ""), at=_now())
                                vs.update_item(db, run_row, run)
                                continue
                            if chk["verdict"] != "ready":
                                raise ss.StepChanged(chk.get("message") or "It can't run after the install.")
                        res = ss.apply_step(client, by_id[st["id"]], chk, made)
                        st.update(state=res["state"], message=res["message"], undo=res.get("undo"), at=_now())
                    except ss.StepChanged as exc:
                        st.update(state="failed", message=f"Paused: {exc}", at=_now())
                    except Exception as exc:  # noqa: BLE001  Odoo refused the write
                        st.update(state="failed", message=f"Odoo refused: {ss.fault_line(exc)}", at=_now())
                    run["made"] = made
                    vs.update_item(db, run_row, run)
                    if st["state"] == "failed":
                        held = _deps_closure(plan["steps"], st["id"])
                        for w in run["waves"]:
                            for o in w["steps"]:
                                if o["id"] in held and o["state"] == "waiting":
                                    o["message"] = f"Waiting: it needs {st['id']}, which failed."
                        run["state"] = "paused"
                        run["paused_on"] = st["id"]
                        vs.update_item(db, run_row, run)
                        return run
            run["state"] = "done"
            run["finished_at"] = _now()
            vs.update_item(db, run_row, run)
            return run
    except ConnectionMutationBusy as exc:
        run["state"] = "failed"
        run["message"] = f"Another change is running on this database ({exc.holder}). Try again when it ends."
        run["finished_at"] = _now()
        vs.update_item(db, run_row, run)
        return run


def _start(connection_id: str, run_id: str) -> None:
    from app.db import SessionLocal
    from app.odoo_service import client_from_connection

    def work() -> None:
        db = SessionLocal()
        try:
            row = vs.get_item(db, connection_id, run_id)
            client = client_from_connection(get_connection_or_404(db, connection_id))
            execute_run(client, db, connection_id, row)
        except Exception as exc:  # noqa: BLE001
            log.exception("suite run %s crashed", run_id)
            row = vs.get_item(db, connection_id, run_id)
            if row is not None:
                p = vs.item_out(row)["payload"]
                p.update(state="failed", message=f"The run stopped unexpectedly: {exc}", finished_at=_now())
                vs.update_item(db, row, p)
        finally:
            db.close()

    ctx = contextvars.copy_context()
    threading.Thread(target=lambda: ctx.run(work), name=f"suite-run-{run_id}", daemon=True).start()


@router.post("/setup/plans/{plan_id}/run")
def suite_plan_run(connection_id: str, plan_id: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Apply. Refused without a fresh Check receipt for this exact plan."""
    row = _get(db, connection_id, plan_id, PLAN)
    p = vs.item_out(row)["payload"]
    phash = ss.plan_hash(p["steps"])
    check = p.get("check") or {}
    if not check or check.get("plan_hash") != phash or not dry_run_was_seen(ss.RECEIPT_TOOL, ss.receipt_args(connection_id, plan_id, phash)):
        raise HTTPException(status_code=428, detail={"error": "check_required", "message": "Check this plan first. A check is good for one hour and only for the plan exactly as checked.",
                                                     "options": ["Run Check"]})
    if not check.get("can_apply"):
        raise HTTPException(status_code=409, detail={"error": "not_ready", "message": "Some steps are blocked or need input. Fix them and check again."})
    if check.get("needs_approval"):
        ap = find_approval(db, connection_id, "suite_plan", plan_id, phash)
        if not ap or ap["status"] != "approved":
            raise HTTPException(status_code=403, detail={"error": "approval_required", "message": "This plan needs a manager's approval before it runs.",
                                                         "options": ["Ask for approval"], "approval": ap})
    gate = sc.gate(p["steps"])  # pre-flight through the shared gates; writes stay in apply_step (same undo/receipts)
    if not gate["ok"]:
        raise HTTPException(status_code=409, detail={"error": "changeset_refused", "message": "The shared change checks refuse this plan. Check it again.",
                                                     "blocked": gate["blocked"]})
    run = _new_run(row, p, _who(request))
    run_row = vs.save_item(db, connection_id=connection_id, kind=RUN, key=f"run:{plan_id}", name=row.name, payload=run)
    if RUN_INLINE:
        execute_run(_client(connection_id, db), db, connection_id, run_row)
        run_row = vs.get_item(db, connection_id, run_row.id)
    else:
        _start(connection_id, run_row.id)
    return vs.item_out(run_row)


@router.get("/setup/runs")
def suite_runs(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"runs": [{"id": r.id, "name": r.name, **{k: vs.item_out(r)["payload"].get(k) for k in ("state", "kind", "plan_id", "started_at", "finished_at")}}
                     for r in vs.list_items(db, connection_id, RUN)]}


@router.get("/setup/runs/{run_id}")
def suite_run_get(connection_id: str, run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return vs.item_out(_get(db, connection_id, run_id, RUN))


@router.post("/setup/runs/{run_id}/stop")
def suite_run_stop(connection_id: str, run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _get(db, connection_id, run_id, RUN)
    p = vs.item_out(row)["payload"]
    if p.get("state") in {"queued", "running"}:
        p["stop_requested"] = True
    elif p.get("state") == "paused":
        p.update(state="stopped", finished_at=_now())
    vs.update_item(db, row, p)
    return p


class ContinueBody(BaseModel):
    skip_failed: bool = True


@router.post("/setup/runs/{run_id}/continue")
def suite_run_continue(connection_id: str, run_id: str, body: ContinueBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Skip the failed step (and what needs it) and carry on. Every remaining step still re-checks before writing."""
    row = _get(db, connection_id, run_id, RUN)
    p = vs.item_out(row)["payload"]
    if p.get("state") != "paused":
        raise HTTPException(status_code=409, detail="Only a paused run can continue.")
    plan = vs.item_out(_get(db, connection_id, p["plan_id"], PLAN))["payload"]
    if not dry_run_was_seen(ss.RECEIPT_TOOL, ss.receipt_args(connection_id, p["plan_id"], p["plan_hash"])):
        raise HTTPException(status_code=428, detail={"error": "check_required", "message": "The check is over an hour old. Check the plan again."})
    failed = p.get("paused_on")
    held = _deps_closure(plan["steps"], failed) if failed else set()
    for w in p["waves"]:
        for st in w["steps"]:
            if st["id"] == failed:
                st["state"] = "skipped"
            elif st["id"] in held and st["state"] == "waiting":
                st.update(state="skipped", message=f"Skipped because {failed} was skipped.")
    p.update(state="queued", stop_requested=False, paused_on=None)
    vs.update_item(db, row, p)
    if RUN_INLINE:
        execute_run(_client(connection_id, db), db, connection_id, row)
    else:
        _start(connection_id, row.id)
    return vs.item_out(vs.get_item(db, connection_id, run_id))


@router.post("/setup/runs/{run_id}/undo-plan")
def suite_run_undo_plan(connection_id: str, run_id: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Build the undo plan: what the run changed, in reverse order. It goes through Check and Run like any plan."""
    row = _get(db, connection_id, run_id, RUN)
    run = {**vs.item_out(row)["payload"], "id": row.id}
    if run.get("state") in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Wait for the run to finish or stop it first.")
    plan = vs.item_out(_get(db, connection_id, run["plan_id"], PLAN))["payload"]
    steps, cannot = ss.undo_steps(plan["steps"], run)
    if not steps:
        raise HTTPException(status_code=409, detail={"error": "nothing_to_undo", "message": "This run changed nothing that can be undone here.", "cannot": cannot})
    prow = _save_plan(db, connection_id, f"Undo: {row.name}"[:120], steps, kind="undo", who=_who(request),
                      extra={"undo_of": row.id, "cannot_undo": cannot})
    return _plan_view(prow)


# ---------------------------------------------------------------- workbook
@router.get("/setup/workbook")
def suite_workbook_download(connection_id: str, db: Session = Depends(get_db)) -> Response:
    row = _row(db, connection_id)
    client = _client(connection_id, db)
    data = swb.build_workbook(client, connection_id=connection_id, server_version=_version(client, row))
    return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="setup-{row.db_name}.xlsx"'})


class WorkbookBody(BaseModel):
    name: str = Field(default="Workbook setup", max_length=120)
    content_b64: str = Field(max_length=20_000_000)


@router.post("/setup/workbook")
def suite_workbook_upload(connection_id: str, body: WorkbookBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    try:
        data = base64.b64decode(body.content_b64, validate=True)
        out = swb.workbook_steps(client, data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"That file could not be read as a workbook: {exc}") from exc
    meta_conn = out["meta"].get("connection_id")
    if meta_conn and meta_conn != connection_id:
        out["notes"].insert(0, "This workbook was downloaded from a different database. Rows were compared with this one.")
    plan = _plan_view(_save_plan(db, connection_id, body.name, out["steps"], who=_who(request))) if out["steps"] else None
    return {"steps": len(out["steps"]), "notes": out["notes"], "plan": plan}


# ---------------------------------------------------------------- safety
@router.get("/safety/money")
def suite_money(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    client = _client(connection_id, db)
    facts = ss.db_facts(client)
    pol = _policy(db, connection_id)
    return {"facts": facts,
            "rules": [
                {"key": "guarded_models", "text": "Accounts, taxes, journals, entries, payments and reconciliations are never written in bulk.", "models": sorted(ss.GUARDED_MODELS)},
                {"key": "package_only", "text": "Taxes and the chart of accounts come only from the country package."},
                {"key": "currency_costing", "text": "Company currency and product costing change only before the first posted entry and stock move.",
                 "allowed_now": not facts["posted_entries"] and not facts["done_moves"]},
                {"key": "installs_d4", "text": "Installs and country packages run only on databases with no posted entries.", "allowed_now": not facts["posted_entries"]},
                {"key": "approval_d3", "text": f"Accounting steps and runs over {pol['approval_threshold']} hard-to-undo records need a manager's approval.",
                 "threshold": pol["approval_threshold"]},
                {"key": "invoice_buttons_d2", "text": "Post, reset and cancel on invoices are allowed only under these rules with a manager's approval."},
                {"key": "opening_last", "text": "Opening balances and initial stock come last, with approval."},
            ],
            "policy": pol}
