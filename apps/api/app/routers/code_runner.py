"""Code runner v2 editor services (BRIDGE_RUNNER_SPEC 1-7). Reads only; scripts still run via the runner."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.code_runner import ai as cr_ai
from app.code_runner import schema as cs
from app.code_runner.lint import lint
from app.code_runner.snippets import SNIPPETS
from app.code_runner.versions import compare
from app.db import get_db
from app.odoo_service import client_from_connection, get_connection_or_404
from app.routers.view_engine import ODOO_ERRORS

router = APIRouter(prefix="/connections/{connection_id}/code-runner", tags=["code-runner"])


def _conn(connection_id: str, db: Session) -> tuple[Any, Any, int]:
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        client = client_from_connection(row)
    except ODOO_ERRORS as exc:
        raise HTTPException(status_code=502, detail="Can't reach Odoo right now.") from exc
    major = cs.major_of(row.server_version or row.last_seen_version)
    if not major:  # not recorded yet: ask Odoo (cached per connection)
        try:
            major = cs.major_of(cs._cached((row.id, "version"), lambda: str(client.server_version().get("server_version") or "")))
        except ODOO_ERRORS:
            major = 0
    return row, client, major


def _key(row: Any) -> str:
    return f"{row.id}:{row.server_version or row.db_name}"


def _fields_fn(client: Any, key: str):
    def get(model: str) -> dict[str, Any] | None:
        try:
            return cs.fields(client, key, model)
        except ODOO_ERRORS:
            return None
    return get


@router.get("/schema")
def schema(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row, client, major = _conn(connection_id, db)
    try:
        models = cs.models(client, _key(row))
    except ODOO_ERRORS as exc:
        raise HTTPException(status_code=502, detail="Couldn't read the models from Odoo.") from exc
    return {"major": major, "models": models, "methods": cs.methods_for(major),
            "deprecated": {k: {"since": v[0], "message": v[1], "use": v[2]} for k, v in cs.DEPRECATED.items() if major >= v[0]}}


@router.get("/schema/fields")
def schema_fields(connection_id: str, model: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row, client, major = _conn(connection_id, db)
    got = _fields_fn(client, _key(row))(model)
    if got is None:
        raise HTTPException(status_code=404, detail=f"There is no model '{model}' on this database.")
    return {"model": model, "major": major, "fields": got}


class LintBody(BaseModel):
    code: str = Field(default="", max_length=200_000)


@router.post("/lint")
def lint_code(connection_id: str, body: LintBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    row, client, major = _conn(connection_id, db)
    try:
        names = {m["model"] for m in cs.models(client, _key(row))}
    except ODOO_ERRORS:
        names = set()
    return {"major": major, "issues": lint(body.code, major=major, model_names=names, fields_of=_fields_fn(client, _key(row)))}


class VersionsBody(BaseModel):
    model: str
    connection_ids: list[str] = Field(default_factory=list, max_length=6)


@router.post("/versions")
def versions(connection_id: str, body: VersionsBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    per: dict[str, Any] = {}
    labels: dict[str, str] = {}
    for cid in dict.fromkeys([connection_id, *body.connection_ids]):
        row, client, major = _conn(cid, db)
        v = str(major or row.server_version or cid)
        per[v] = _fields_fn(client, _key(row))(body.model)
        labels[v] = row.name
    return {"model": body.model, "labels": labels, **compare(per)}


@router.get("/snippets")
def snippets(connection_id: str) -> dict[str, Any]:
    return {"snippets": SNIPPETS}


class AIBody(BaseModel):
    action: Literal["explain", "comment_to_code", "fix"]
    code: str = Field(default="", max_length=20_000)
    request: str = Field(default="", max_length=2_000)
    error: str = Field(default="", max_length=4_000)


@router.post("/ai")
def inline_ai(connection_id: str, body: AIBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.ai_client.ai_scope import ai_scope
    from app.view_engine_ai import AIUnavailable

    row, client, major = _conn(connection_id, db)
    try:
        names = [m["model"] for m in cs.models(client, _key(row))]
    except ODOO_ERRORS:
        names = []
    try:
        from app.code_runner import store as _st

        setting = _st.load("settings", f"set_{row.workspace_id or 'local'}", {"ai_mode": "local", "consent": None})
        with ai_scope(reads=("ir.model", "ir.model.fields")):
            out = cr_ai.propose(body.action, body.code, request=body.request, error=body.error, major=major,
                                models_hint=[n for n in names if n in body.code or not n.startswith(("ir.", "base", "bus."))],
                                mode=setting.get("ai_mode", "local"), consent=setting.get("consent"))
    except cr_ai.ConsentRequired as exc:
        raise HTTPException(status_code=409, detail={"error": "consent_required", "message": str(exc)}) from exc
    except AIUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if body.action == "explain":
        out["code"] = ""
    check = cr_ai.authorize(out["code"], body.code, lambda c: lint(
        c, major=major, model_names=set(names), fields_of=_fields_fn(client, _key(row))))
    if not check["ok"]:
        return {"ok": False, "reason": check["reason"], "explanation": out["explanation"], "code": ""}
    return {"ok": True, "explanation": out["explanation"], "code": out["code"], "issues": check["issues"], "money": check["money"]}


# ---------------------------------------------------------------- R2: runs (items 8-18)
import csv  # noqa: E402
import io  # noqa: E402

from fastapi.responses import Response  # noqa: E402

from app.code_runner import runs as rr  # noqa: E402
from app.script_runner.service import connection_config_dict  # noqa: E402
from app.workspace_auth import WorkspaceAuth, require_app_auth  # noqa: E402
from app.code_studio_gating import assert_developer_role  # noqa: E402
from app.code_runner import vault  # noqa: E402


def record_url(base: str, major: int, model: str, rid: int) -> str:
    base = base.rstrip("/")
    return f"{base}/odoo/{model}/{rid}" if major >= 17 else f"{base}/web#model={model}&id={rid}"


class RunBody(BaseModel):
    code: str = Field(max_length=200_000)
    mode: Literal["dry", "real"] = "dry"
    sample: bool = False
    receipt_id: str | None = None
    name: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    wait: bool = False
    script_id: str | None = None


def _refused(exc: rr.Refused) -> HTTPException:
    return HTTPException(status_code=409, detail={"error": exc.code, "message": exc.message})


def _own_run(connection_id: str, run_id: str) -> dict[str, Any]:
    run = rr.get(run_id)
    if not run or run.get("connection_id") != connection_id:
        raise HTTPException(status_code=404, detail="No such run on this connection.")
    return run


@router.post("/runs")
def start_run(connection_id: str, body: RunBody, db: Session = Depends(get_db),
              auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    row = get_connection_or_404(db, connection_id)
    if body.mode == "real":
        try:
            rr.check_real_run(rr.get(body.receipt_id or "") if body.receipt_id else None, connection_id=connection_id,
                              script=body.code, write_mode=row.write_mode or "standard", params=body.params)
        except rr.Refused as exc:
            raise _refused(exc) from exc
    run = rr.start(connection_id, connection_config_dict(row), body.code, mode=body.mode, user=auth.user_id,
                   name=body.name, sample=body.sample and body.mode == "dry", receipt_of=body.receipt_id,
                   params=body.params, wait=body.wait, script_id=body.script_id,
                   secrets=vault.for_run(row.workspace_id, connection_id, body.code))
    return rr.summary(run)


@router.get("/runs")
def runs_list(connection_id: str) -> dict[str, Any]:
    return {"runs": rr.list_runs(connection_id)}


@router.get("/runs/{run_id}")
def run_detail(connection_id: str, run_id: str, after: int = 0, db: Session = Depends(get_db)) -> dict[str, Any]:
    run = _own_run(connection_id, run_id)
    row = get_connection_or_404(db, connection_id)
    major = cs.major_of(row.server_version or row.last_seen_version) or 17
    changes = run["changes"][:2000]
    for c in changes:
        if isinstance(c.get("id"), int) and c["id"] > 0:
            c["url"] = record_url(row.url, major, c["model"], c["id"])
    return {**rr.summary(run), "events": run["events"][after:after + 2000], "events_total": len(run["events"]),
            "changes": changes, "changes_total": len(run["changes"]), "results": run["results"][:5000],
            "profile": run.get("profile"), "calls_total": len(run["calls"]), "timing_ms": run.get("timing_ms"),
            "code": run.get("code", "")}


class ControlBody(BaseModel):
    action: Literal["pause", "resume", "stop"]


@router.post("/runs/{run_id}/control")
def run_control(connection_id: str, run_id: str, body: ControlBody, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    _own_run(connection_id, run_id)
    return {"state": rr.control(run_id, body.action)}


@router.post("/runs/{run_id}/approve")
def run_approve(connection_id: str, run_id: str, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    run = _own_run(connection_id, run_id)
    if run.get("mode") != "dry" or run.get("status") != "done":
        raise HTTPException(status_code=409, detail={"error": "not_a_receipt", "message": "Only a finished dry run can be approved."})
    try:
        return rr.approve(run, approver=auth.user_id, role="superadmin" if auth.is_superadmin else auth.role,
                          auth_on=auth.mode == "accounts" and not auth.api_key_authenticated, requester_ok=False)
    except rr.Refused as exc:
        raise _refused(exc) from exc


@router.post("/runs/{run_id}/resume")
def run_resume(connection_id: str, run_id: str, db: Session = Depends(get_db),
               auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    prev = _own_run(connection_id, run_id)
    if prev.get("mode") != "real" or prev.get("status") not in {"failed", "stopped"}:
        raise HTTPException(status_code=409, detail={"error": "not_resumable", "message": "Only a stopped or failed real run can be resumed."})
    row = get_connection_or_404(db, connection_id)
    try:
        rr.check_real_run(rr.get(prev.get("receipt_of") or ""), connection_id=connection_id, script=prev["code"],
                          write_mode=row.write_mode or "standard", params=prev.get("params"))
    except rr.Refused as exc:
        raise _refused(exc) from exc
    run = rr.start(connection_id, connection_config_dict(row), prev["code"], mode="real", user=auth.user_id,
                   name=f"Resume of {prev.get('name') or run_id[:8]}", receipt_of=prev.get("receipt_of"), resume_of=run_id,
                   params=prev.get("params"), secrets=vault.for_run(row.workspace_id, connection_id, prev["code"]))
    return rr.summary(run)


@router.get("/runs/{run_id}/undo-preview")
def run_undo_preview(connection_id: str, run_id: str) -> dict[str, Any]:
    run = _own_run(connection_id, run_id)
    return {"code": rr.undo_script(run), "undoable": (run.get("safety") or {}).get("undoable", True)}


@router.post("/runs/{run_id}/undo")
def run_undo(connection_id: str, run_id: str, db: Session = Depends(get_db),
             auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    prev = _own_run(connection_id, run_id)
    if prev.get("mode") != "real" or prev.get("status") in {"queued", "running", "paused", "stopping"}:
        raise HTTPException(status_code=409, detail={"error": "not_undoable", "message": "Only a finished real run can be undone."})
    if prev.get("undone_by"):
        raise HTTPException(status_code=409, detail={"error": "already_undone", "message": "This run was already undone."})
    row = get_connection_or_404(db, connection_id)
    if (row.write_mode or "standard") == "observer":
        raise _refused(rr.Refused("observer_connection", "This connection is read-only."))
    run = rr.start(connection_id, connection_config_dict(row), rr.undo_script(prev), mode="real", user=auth.user_id,
                   name=f"Undo of {prev.get('name') or run_id[:8]}", undo_of=run_id)
    prev["undone_by"] = run["id"]
    rr._save(prev)
    return rr.summary(run)


@router.get("/runs/{run_id}/export")
def run_export(connection_id: str, run_id: str, fmt: Literal["csv", "json"] = "csv") -> Response:
    rows = _own_run(connection_id, run_id)["results"]
    if fmt == "json":
        import json as _json
        return Response(_json.dumps(rows, default=str), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="run-{run_id[:8]}.json"'})
    buf = io.StringIO()
    cols = list(dict.fromkeys(k for r in rows for k in r))
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: (v if isinstance(v, (str, int, float)) or v is None else str(v)) for k, v in r.items()})
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="run-{run_id[:8]}.csv"'})


# ---------------------------------------------------------------- R3: library, sharing, promotion, audit, vault, AI mode (19-29)
from app.code_runner import library as lib  # noqa: E402
from app.code_runner import promote as pm  # noqa: E402
from app.code_runner import store as crs  # noqa: E402
from app.code_runner import testing as crt  # noqa: E402


def _ws(db: Session, connection_id: str) -> str | None:
    return get_connection_or_404(db, connection_id).workspace_id


def _script(db: Session, connection_id: str, sid: str) -> tuple[str | None, dict[str, Any]]:
    ws = _ws(db, connection_id)
    s = lib.get(ws, sid)
    if not s:
        raise HTTPException(status_code=404, detail="No such script.")
    return ws, s


def _audit(connection_id: str, kind: str, by: str | None, detail: dict[str, Any]) -> None:
    with crs.lock():
        log = crs.load("audit", f"audit_{connection_id}", [])
        log.append({"kind": kind, "by": by, "at": __import__("time").time(), **detail})
        crs.save("audit", f"audit_{connection_id}", log[-5000:])


class ScriptBody(BaseModel):
    name: str = Field(default="Untitled", max_length=120)
    code: str = Field(default="", max_length=200_000)
    folder: str = Field(default="", max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=20)
    kind: Literal["script", "notebook"] = "script"
    cells: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


@router.get("/library")
def library_search(connection_id: str, q: str = "", folder: str = "", tag: str = "", db: Session = Depends(get_db)) -> dict[str, Any]:
    return lib.search(_ws(db, connection_id), q, folder, tag)


@router.post("/library")
def library_create(connection_id: str, body: ScriptBody, db: Session = Depends(get_db),
                   auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    s = lib.create(_ws(db, connection_id), name=body.name, code=body.code, by=auth.user_id, folder=body.folder,
                   tags=body.tags, kind=body.kind, cells=body.cells)
    return {**lib.summary(s), "code": s["code"], "cells": s["cells"]}


@router.get("/library/{sid}")
def library_get(connection_id: str, sid: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _, s = _script(db, connection_id, sid)
    return {**lib.summary(s), "code": s["code"], "cells": s.get("cells") or [], "comments": s.get("comments") or [],
            "tests": s.get("tests") or [], "params": lib.detect_params(s["code"]),
            "version_list": [{k: v.get(k) for k in ("n", "at", "by", "note")} for v in s.get("versions") or []]}


class MetaBody(BaseModel):
    name: str | None = None
    folder: str | None = None
    tags: list[str] | None = None
    tests: list[dict[str, Any]] | None = None


@router.patch("/library/{sid}")
def library_meta(connection_id: str, sid: str, body: MetaBody, db: Session = Depends(get_db),
                 auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    ws, _ = _script(db, connection_id, sid)
    return lib.summary(lib.update_meta(ws, sid, **body.model_dump()))


@router.delete("/library/{sid}")
def library_delete(connection_id: str, sid: str, db: Session = Depends(get_db),
                   auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    ws, _ = _script(db, connection_id, sid)
    return {"deleted": lib.delete(ws, sid)}


class VersionBody(BaseModel):
    note: str = ""


@router.post("/library/{sid}/versions")
def library_version(connection_id: str, sid: str, body: VersionBody, db: Session = Depends(get_db),
                    auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    ws, _ = _script(db, connection_id, sid)
    v = lib.save_version(ws, sid, by=auth.user_id, note=body.note)
    return {k: v.get(k) for k in ("n", "at", "by", "note")}


@router.get("/library/{sid}/diff")
def library_diff(connection_id: str, sid: str, a: int, b: int | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    _, s = _script(db, connection_id, sid)
    vs = {v["n"]: v for v in s.get("versions") or []}
    if a not in vs or (b is not None and b not in vs):
        raise HTTPException(status_code=404, detail="No such version.")
    right = vs[b]["code"] if b is not None else s["code"]
    return {"diff": lib.diff(vs[a]["code"], right, f"version {a}", f"version {b}" if b else "current"),
            "left": vs[a]["code"], "right": right}


@router.post("/library/{sid}/restore/{n}")
def library_restore(connection_id: str, sid: str, n: int, db: Session = Depends(get_db),
                    auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    ws, s = _script(db, connection_id, sid)
    v = next((v for v in s.get("versions") or [] if v["n"] == n), None)
    if not v:
        raise HTTPException(status_code=404, detail="No such version.")
    out = lib.live_put(ws, sid, base_rev=s["rev"], code=v["code"], by=auth.user_id, cells=v.get("cells"))
    lib.save_version(ws, sid, by=auth.user_id, note=f"Restored version {n}")
    return out


class LivePut(BaseModel):
    base_rev: int
    code: str = Field(max_length=200_000)
    cells: list[dict[str, Any]] | None = None


@router.get("/library/{sid}/live")
def library_live_get(connection_id: str, sid: str, line: int | None = None, db: Session = Depends(get_db),
                     auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    ws, _ = _script(db, connection_id, sid)
    return lib.live_get(ws, sid, by=auth.email or auth.user_id, cursor_line=line)


@router.put("/library/{sid}/live")
def library_live_put(connection_id: str, sid: str, body: LivePut, db: Session = Depends(get_db),
                     auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    ws, _ = _script(db, connection_id, sid)
    out = lib.live_put(ws, sid, base_rev=body.base_rev, code=body.code, by=auth.email or auth.user_id, cells=body.cells)
    if not out["ok"]:
        raise HTTPException(status_code=409, detail={"error": "edit_conflict", **out})
    return out


class CommentBody(BaseModel):
    line: int = 1
    text: str = Field(default="", max_length=2000)


class CommentPatch(BaseModel):
    reply: str = ""
    resolved: bool | None = None


@router.post("/library/{sid}/comments")
def library_comment(connection_id: str, sid: str, body: CommentBody, db: Session = Depends(get_db),
                    auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    ws, _ = _script(db, connection_id, sid)
    return lib.comment(ws, sid, line=body.line, text=body.text, by=auth.email or auth.user_id)


@router.patch("/library/{sid}/comments/{cid}")
def library_comment_patch(connection_id: str, sid: str, cid: str, body: CommentPatch, db: Session = Depends(get_db),
                          auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    ws, _ = _script(db, connection_id, sid)
    return lib.resolve_comment(ws, sid, cid, reply=body.reply, by=auth.email or auth.user_id, resolved=body.resolved)


# -- 21 parameter forms
class ParamsBody(BaseModel):
    code: str = Field(max_length=200_000)
    values: dict[str, Any] = Field(default_factory=dict)


@router.post("/params")
def params_form(connection_id: str, body: ParamsBody) -> dict[str, Any]:
    spec = lib.detect_params(body.code)
    values, errors = lib.coerce_params(spec, body.values) if body.values else ({}, [])
    return {"fields": spec, "values": values, "errors": errors}


# -- 22 share across connections, re-checked per version
class ShareBody(BaseModel):
    connection_ids: list[str] = Field(max_length=20)


@router.post("/library/{sid}/share")
def library_share(connection_id: str, sid: str, body: ShareBody, db: Session = Depends(get_db),
                  auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    ws, s = _script(db, connection_id, sid)
    checks, ok = [], []
    for cid in dict.fromkeys(body.connection_ids):
        try:
            row, client, major = _conn(cid, db)
        except HTTPException as exc:
            checks.append({"connection_id": cid, "ok": False, "errors": [str(exc.detail)]})
            continue
        if row.workspace_id != ws:
            checks.append({"connection_id": cid, "ok": False, "errors": ["That connection belongs to another workspace."]})
            continue
        try:
            names = {m["model"] for m in cs.models(client, _key(row))}
        except ODOO_ERRORS:
            names = set()
        issues = lint(s["code"], major=major, model_names=names, fields_of=_fields_fn(client, _key(row)))
        errs = [f"Line {i['line']}: {i['message']}" for i in issues if i["severity"] == "error"]
        warns = [f"Line {i['line']}: {i['message']}" for i in issues if i["severity"] == "warning"]
        checks.append({"connection_id": cid, "name": row.name, "major": major, "ok": not errs, "errors": errs, "warnings": warns})
        if not errs:
            ok.append(cid)
    lib.update_meta(ws, sid, shared_connections=sorted(set((s.get("shared_connections") or [])) | set(ok)))
    return {"checks": checks, "shared": ok}


# -- 23 starter gallery
@router.get("/gallery")
def gallery(connection_id: str) -> dict[str, Any]:
    return {"starters": [{**g, "params": lib.detect_params(g["code"])} for g in lib.GALLERY]}


# -- 26 notebooks / runbooks
class RunbookBody(BaseModel):
    mode: Literal["dry", "real"] = "dry"
    receipts: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/library/{sid}/runbook")
def library_runbook(connection_id: str, sid: str, body: RunbookBody, db: Session = Depends(get_db),
                    auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    """Runs code cells in order and stops at the first failure. Real steps each need their own dry-run receipt."""
    assert_developer_role(auth)
    ws, s = _script(db, connection_id, sid)
    row = get_connection_or_404(db, connection_id)
    steps = []
    for cell in [c for c in s.get("cells") or [] if c.get("type") == "code"]:
        code = str(cell.get("source") or "")
        if body.mode == "real":
            try:
                rr.check_real_run(rr.get(body.receipts.get(cell.get("id"), "")), connection_id=connection_id, script=code,
                                  write_mode=row.write_mode or "standard", params=body.params)
            except rr.Refused as exc:
                steps.append({"cell": cell.get("id"), "status": "refused", "error": exc.code, "message": exc.message})
                break
        run = rr.start(connection_id, connection_config_dict(row), code, mode=body.mode, user=auth.user_id,
                       name=f"{s['name']} · step {len(steps) + 1}", receipt_of=body.receipts.get(cell.get("id")),
                       params=body.params, wait=True, script_id=sid, secrets=vault.for_run(ws, connection_id, code))
        steps.append({"cell": cell.get("id"), "run_id": run["id"], "status": run["status"], "error": run.get("error"),
                      "counts": run.get("counts"), "safety": run.get("safety")})
        if run["status"] != "done":
            break
    if body.mode == "real":
        _audit(connection_id, "runbook", auth.user_id, {"script": s["name"], "steps": len(steps)})
    return {"steps": steps, "complete": len(steps) == sum(1 for c in s.get("cells") or [] if c.get("type") == "code")
            and all(x["status"] == "done" for x in steps)}


# -- 27 tests on a disposable copy
@router.post("/library/{sid}/tests/run")
def library_tests(connection_id: str, sid: str, db: Session = Depends(get_db),
                  auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    ws, s = _script(db, connection_id, sid)
    row = get_connection_or_404(db, connection_id)
    tests = s.get("tests") or [{"name": "Runs without errors", "expect": {"no_error": True}}]
    sec = vault.for_run(ws, connection_id, s["code"] + '\nsecret("odoo_master_password")')
    master = sec.pop("odoo_master_password", None)
    results = [{"name": t.get("name"), **crt.run_test(connection_id, connection_config_dict(row), s["code"], t, master, sec)}
               for t in tests]
    return {"results": results, "passed": all(r["passed"] for r in results)}


# -- 20 promote: test then publish
class PromoteBody(BaseModel):
    script_id: str | None = None
    name: str = Field(max_length=120)
    code: str = Field(max_length=200_000)
    params: dict[str, Any] = Field(default_factory=dict)
    kind: Literal["cron", "action", "button"]
    model: str = "res.partner"
    interval: dict[str, Any] | None = None
    receipt_id: str


@router.post("/promotions/check")
def promotion_check(connection_id: str, body: ParamsBody) -> dict[str, Any]:
    reasons = pm.check(body.code)
    return {"ok": not reasons, "reasons": reasons}


@router.get("/promotions")
def promotions(connection_id: str) -> dict[str, Any]:
    return {"promotions": pm.list_promotions(connection_id)}


@router.post("/promotions")
def promotion_test(connection_id: str, body: PromoteBody, db: Session = Depends(get_db),
                   auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    row, client, _major = _conn(connection_id, db)
    try:  # the same proof as a real run: a fresh, matching, approved-if-needed dry run
        rr.check_real_run(rr.get(body.receipt_id), connection_id=connection_id, script=body.code,
                          write_mode=row.write_mode or "standard", params=body.params)
        item = pm.test(client, connection_id, name=pm.safe_name(body.name), code=body.code, params=body.params, kind=body.kind,
                       model=body.model, interval=body.interval, by=auth.user_id, receipt_id=body.receipt_id)
    except rr.Refused as exc:
        raise _refused(exc) from exc
    except pm.NotPromotable as exc:
        raise HTTPException(status_code=422, detail={"error": "not_promotable", "message": str(exc)}) from exc
    except ODOO_ERRORS as exc:
        raise HTTPException(status_code=422, detail={"error": "odoo_rejected", "message": f"Odoo didn't accept the code: {str(exc)[:300]}"}) from exc
    _audit(connection_id, "promotion_test", auth.user_id, {"promotion": item["id"], "name": item["name"], "kind": item["kind"]})
    return item


@router.post("/promotions/{pid}/{action}")
def promotion_action(connection_id: str, pid: str, action: Literal["run-once", "publish", "remove"],
                     db: Session = Depends(get_db), auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    _row, client, _major = _conn(connection_id, db)
    try:
        if action == "publish":
            item = pm.publish(client, connection_id, pid, by=auth.user_id)
        elif action == "run-once":
            item = pm.run_once(client, connection_id, pid)
        else:
            item = pm.remove(client, connection_id, pid)
    except pm.NotPromotable as exc:
        raise HTTPException(status_code=409, detail={"error": "promotion", "message": str(exc)}) from exc
    except ODOO_ERRORS as exc:
        raise HTTPException(status_code=422, detail={"error": "odoo_rejected", "message": str(exc)[:300]}) from exc
    _audit(connection_id, f"promotion_{action}", auth.user_id, {"promotion": pid, "name": item["name"]})
    return item


# -- 25 audit trail with undo links
@router.get("/audit")
def audit(connection_id: str) -> dict[str, Any]:
    items = [{"kind": "undo" if r.get("undo_of") else "real_run", "at": r.get("created_at"), "by": r.get("requested_by"),
              "run_id": r["id"], "name": r.get("name"), "status": r.get("status"), "counts": r.get("counts"),
              "undo": None if (r.get("undo_of") or r.get("undone_by") or not r.get("counts")) else f"runs/{r['id']}/undo",
              "undone_by": r.get("undone_by")}
             for r in rr.list_runs(connection_id, limit=200) if r.get("mode") == "real"]
    for a in crs.load("audit", f"audit_{connection_id}", []):
        undo = f"promotions/{a['promotion']}/remove" if a["kind"] in {"promotion_test", "promotion_publish"} else None
        items.append({**a, "undo": undo})
    return {"items": sorted(items, key=lambda x: -(x.get("at") or 0))[:500]}


# -- 28 secrets vault
class SecretBody(BaseModel):
    name: str = Field(max_length=64)
    value: str = Field(max_length=10_000)
    connections: list[str] = Field(default_factory=list)


@router.get("/vault")
def vault_list(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"secrets": vault.names(_ws(db, connection_id))}


@router.post("/vault")
def vault_put(connection_id: str, body: SecretBody, db: Session = Depends(get_db),
              auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    try:
        vault.put(_ws(db, connection_id), body.name, body.value, auth.user_id, body.connections)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _audit(connection_id, "secret_set", auth.user_id, {"secret": body.name})
    return {"ok": True, "name": body.name}


@router.delete("/vault/{name}")
def vault_delete(connection_id: str, name: str, db: Session = Depends(get_db),
                 auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    assert_developer_role(auth)
    hit = vault.delete(_ws(db, connection_id), name)
    _audit(connection_id, "secret_deleted", auth.user_id, {"secret": name})
    return {"deleted": hit}


# -- 29 local AI default, cloud with consent
class AISettingsBody(BaseModel):
    mode: Literal["local", "cloud"]
    consent: bool = False


@router.get("/settings")
def runner_settings(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return crs.load("settings", f"set_{_ws(db, connection_id) or 'local'}", {"ai_mode": "local", "consent": None})


@router.put("/settings")
def runner_settings_put(connection_id: str, body: AISettingsBody, db: Session = Depends(get_db),
                        auth: WorkspaceAuth = Depends(require_app_auth)) -> dict[str, Any]:
    key = f"set_{_ws(db, connection_id) or 'local'}"
    if body.mode == "cloud" and not body.consent:
        raise HTTPException(status_code=409, detail={"error": "consent_required",
                            "message": "Turning on the cloud assistant sends your script text to the AI provider. Tick the consent box to continue."})
    val = {"ai_mode": body.mode, "consent": {"by": auth.email or auth.user_id, "by_at": __import__("time").time()} if body.mode == "cloud" else None}
    crs.save("settings", key, val)
    _audit(connection_id, "ai_mode", auth.user_id, {"mode": body.mode})
    return val
