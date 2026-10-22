"""Bridge HTTP: Tier I contract check + B1 gallery, vault, connect health. No Odoo write."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.bridge.connections import require_verified_connections
from app.bridge.contract import ContractError, validate_contract
from app.db import get_db
from app.db_models import BridgeConnection

from fastapi import Request  # noqa: E402

from app.bridge.ops import client_may  # noqa: E402
from app.workspace_auth import WorkspaceAuth, require_app_auth  # noqa: E402


def _client_mode_guard(request: Request, auth: WorkspaceAuth = Depends(require_app_auth)) -> None:
    """Spec 32: a client-role user can view and approve, nothing else."""
    if (auth.role or "").lower() == "client" and not client_may(request.method, request.url.path):
        raise HTTPException(status_code=403, detail="Client view: you can look and approve, not change.")


router = APIRouter(prefix="/bridge", tags=["bridge"], dependencies=[Depends(_client_mode_guard)])

DbSession = Annotated[Session, Depends(get_db)]


class ValidateBody(BaseModel):
    contract: dict


@router.post("/contracts/validate")
def validate_contract_route(body: ValidateBody, db: DbSession) -> dict:
    try:
        contract = validate_contract(body.contract)
        connection_ids = [contract.odoo_connection_id, contract.third_party_connection_id]
        rows = (
            db.query(BridgeConnection)
            .filter(BridgeConnection.id.in_(connection_ids))
            .all()
        )
        by_id = {row.id: row for row in rows}
        require_verified_connections(contract, by_id)
    except ContractError as exc:
        return {"ok": False, "tier": "I", "error": str(exc)}
    return {
        "ok": True,
        "tier": "I",
        "direction": contract.direction,
        "entities": len(contract.entities),
    }


# ---------------------------------------------------------------- B1: gallery, guided auth, vault, health
from pydantic import Field  # noqa: E402

from app.bridge import gallery as bg  # noqa: E402
from app.bridge import live_probe as lp  # noqa: E402


def _connector(key: str) -> bg.Connector:
    c = bg.BY_KEY.get(key)
    if not c:
        raise HTTPException(status_code=404, detail="No such connector.")
    return c


@router.get("/gallery")
def gallery_list(category: str | None = None, q: str | None = None) -> dict:
    return {"connectors": bg.list_gallery(category, q), "categories": list(bg.CATEGORIES)}


@router.get("/gallery/{key}")
def gallery_item(key: str, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    c = _connector(key)
    return {**c.public(), "auth_plan": bg.auth_plan(key), "stored": lp.secret_names(auth.workspace_id, key),
            "live_check": key in lp._PROBES}


class SecretsBody(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


@router.post("/gallery/{key}/secrets")
def gallery_secrets(key: str, body: SecretsBody, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    _connector(key)
    try:
        stored = lp.put_secrets(auth.workspace_id, key, body.values, auth.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "stored": stored}


@router.delete("/gallery/{key}/secrets")
def gallery_secrets_delete(key: str, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    _connector(key)
    return {"deleted": lp.delete_secrets(auth.workspace_id, key)}


class HealthBody(BaseModel):
    needed_entities: list[str] = Field(default_factory=list)
    odoo_connection_id: str | None = None


@router.post("/gallery/{key}/health")
def gallery_health(key: str, body: HealthBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    _connector(key)
    client = None
    if body.odoo_connection_id:
        from app.odoo_service import client_from_connection, get_connection_or_404
        client = client_from_connection(get_connection_or_404(db, body.odoo_connection_id), db=db)
    return lp.health(auth.workspace_id, key, needed_entities=body.needed_entities, odoo_client=client)


# ---------------------------------------------------------------- B2: any app from API docs / sample payload
from app.bridge.spec_import import SpecError, import_spec  # noqa: E402


class SpecBody(BaseModel):
    text: str = Field(max_length=5_000_000)
    hint: str | None = Field(default=None, max_length=64)


@router.post("/import-spec")
def import_spec_route(body: SpecBody, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    try:
        return import_spec(body.text, body.hint)
    except SpecError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------- B3: field-mapping studio
from app.bridge import mapping as bm  # noqa: E402


class MappingBody(BaseModel):
    odoo_connection_id: str
    model: str = Field(max_length=128)
    remote_fields: dict[str, str]
    samples: list[dict] = Field(default_factory=list, max_length=20)
    mapping: list[dict] | None = None


@router.post("/mapping/suggest")
def mapping_suggest(body: MappingBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    from app.odoo_service import client_from_connection, get_connection_or_404
    client = client_from_connection(get_connection_or_404(db, body.odoo_connection_id), db=db)
    try:
        fields = bm.odoo_fields(client, body.model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not read {body.model} ({exc.__class__.__name__}).") from exc
    mapping = body.mapping if body.mapping is not None else bm.suggest(body.remote_fields, fields)
    return {"mapping": mapping, "errors": bm.validate_mapping(mapping, body.remote_fields, fields),
            "preview": bm.preview(mapping, body.samples), "transforms": list(bm.TRANSFORMS),
            "odoo_fields": {k: {"type": v.get("type"), "string": v.get("string"), "required": bool(v.get("required"))}
                            for k, v in fields.items() if k not in bm.READONLY_SKIP}}


# ---------------------------------------------------------------- B4: matching, field rules, triggers
from app.bridge import sync_rules as sr  # noqa: E402


class MatchBody(BaseModel):
    odoo_connection_id: str
    model: str = Field(default="res.partner", max_length=128)
    incoming: list[dict] = Field(max_length=50)


@router.post("/match")
def match_route(body: MatchBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    from app.odoo_service import client_from_connection, get_connection_or_404
    client = client_from_connection(get_connection_or_404(db, body.odoo_connection_id), db=db)
    out = []
    for rec in body.incoming:
        out.append({"incoming": rec, **sr.match_record(rec, sr.odoo_candidates(client, body.model, rec))})
    return {"results": out, "review": sum(1 for r in out if r["action"] == "review")}


class RulesBody(BaseModel):
    triggers: list[dict] = Field(default_factory=list)
    fields: list[dict] = Field(default_factory=list)


@router.post("/rules/check")
def rules_check(body: RulesBody) -> dict:
    errs = [e for t in body.triggers for e in sr.check_trigger(t)]
    rules = []
    for f in body.fields:
        try:
            rules.append(sr.FieldRule(**f).__dict__)
        except TypeError as exc:
            errs.append(f"field rule: {exc}")
    return {"ok": not errs, "errors": errs, "fields": rules}


# ---------------------------------------------------------------- B5: dead letters, contract tests, drift, sandbox
from app.bridge import reliability as rel  # noqa: E402
from app.db_models import IntegrationEvent  # noqa: E402


def _ws_connection_ids(db: Session, auth: WorkspaceAuth) -> list[str]:
    q = db.query(BridgeConnection.id)
    if auth.workspace_id:
        q = q.filter(BridgeConnection.workspace_id == auth.workspace_id)
    return [r[0] for r in q.all()]


@router.get("/dead-letters")
def dead_letters(db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    items = rel.list_dead(db, _ws_connection_ids(db, auth))
    if (auth.role or "").lower() == "client":
        from app.bridge.ops import mask_record
        items = [{**i, "payload": mask_record(i["payload"])} for i in items]
    return {"items": items}


class ReplayBody(BaseModel):
    payload: dict | None = None


@router.post("/dead-letters/{event_id}/replay")
def dead_letter_replay(event_id: str, body: ReplayBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    ev = db.get(IntegrationEvent, event_id)
    if not ev or ev.connection_id not in _ws_connection_ids(db, auth):
        raise HTTPException(status_code=404, detail="No such event.")
    try:
        new = rel.replay(db, ev, body.payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return {"ok": True, "new_event_id": new.id}


class ContractTestBody(BaseModel):
    odoo_connection_id: str
    model: str = Field(max_length=128)
    remote_fields: dict[str, str]
    mapping: list[dict]
    samples: list[dict] = Field(max_length=20)
    observed_fields: dict[str, str] | None = None


def _client(db: Session, connection_id: str):
    from app.odoo_service import client_from_connection, get_connection_or_404
    return client_from_connection(get_connection_or_404(db, connection_id), db=db)


@router.post("/contract-tests")
def contract_tests_route(body: ContractTestBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    fields = bm.odoo_fields(_client(db, body.odoo_connection_id), body.model)
    out = rel.contract_tests(body.mapping, body.remote_fields, fields, body.samples)
    if body.observed_fields is not None:
        out["drift"] = rel.detect_drift(body.remote_fields, body.observed_fields, body.mapping, fields)
    return out


@router.post("/sandbox-run")
def sandbox_run_route(body: ContractTestBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    return rel.sandbox_run(_client(db, body.odoo_connection_id), body.model, body.mapping, body.remote_fields, body.samples)


# ---------------------------------------------------------------- B6: versioned flows, rollout, backfill, reconciliation, monitor
from app.bridge import flows as fl  # noqa: E402


class ProposeBody(BaseModel):
    odoo_connection_id: str
    proposer_name: str | None = Field(default=None, max_length=80)  # only used when sign-in is off
    odoo_model: str = Field(max_length=128)
    remote_fields: dict[str, str]
    mapping: list[dict]
    samples: list[dict] = Field(max_length=20)
    triggers: list[dict] = Field(default_factory=list)
    field_rules: list[dict] = Field(default_factory=list)


@router.post("/flows/{flow_id}/propose")
def flow_propose(flow_id: str, body: ProposeBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    fields = bm.odoo_fields(_client(db, body.odoo_connection_id), body.odoo_model)
    tests = rel.contract_tests(body.mapping, body.remote_fields, fields, body.samples)  # server re-runs; client can't claim a pass
    trig = [e for t in body.triggers for e in sr.check_trigger(t)]
    if trig:
        raise HTTPException(status_code=422, detail="; ".join(trig))
    try:
        v = fl.propose(auth.workspace_id, flow_id, body.model_dump(exclude={"samples", "proposer_name"}),
                       auth.user_id or (f"name:{body.proposer_name.strip()}" if (body.proposer_name or "").strip() else None), tests["ok"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc), "tests": tests}) from exc
    return {**v, "tests": tests}


class ApproveBody(BaseModel):
    n: int
    hash: str
    approver_name: str | None = Field(default=None, max_length=80)  # only used when sign-in is off


@router.post("/flows/{flow_id}/approve")
def flow_approve(flow_id: str, body: ApproveBody, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    try:
        who = auth.user_id or (f"name:{body.approver_name.strip()}" if (body.approver_name or "").strip() else None)
        return fl.approve(auth.workspace_id, flow_id, body.n, who, body.hash, verified=bool(auth.user_id))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class RolloutBody(BaseModel):
    n: int
    percent: int


@router.post("/flows/{flow_id}/rollout")
def flow_rollout(flow_id: str, body: RolloutBody, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    try:
        return fl.set_rollout(auth.workspace_id, flow_id, body.n, body.percent, by=auth.user_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/flows/{flow_id}/rollback")
def flow_rollback(flow_id: str, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    try:
        return fl.rollback(auth.workspace_id, flow_id, by=auth.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/flows")
def flows_list(auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    return {"flows": fl.list_flows(auth.workspace_id)}


@router.get("/flows/{flow_id}")
def flow_get(flow_id: str, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    f = fl.get_flow(auth.workspace_id, flow_id)
    if not f:
        raise HTTPException(status_code=404, detail="No such flow.")
    return {**f, "monitor": fl.monitor(auth.workspace_id, flow_id)}


@router.get("/flows/{flow_id}/trace/{record_key}")
def flow_trace(flow_id: str, record_key: str, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    return {"events": fl.get_trace(auth.workspace_id, flow_id, record_key)}


class BackfillBody(BaseModel):
    total: int
    batch: int = 200


@router.post("/backfill/plan")
def backfill_plan(body: BackfillBody) -> dict:
    try:
        return fl.plan_backfill(body.total, body.batch)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class ReconcileBody(BaseModel):
    odoo_connection_id: str
    model: str = Field(default="account.move", max_length=128)
    ref_field: str = "ref"
    amount_field: str = "amount_total"
    app_rows: list[dict] = Field(max_length=5000)


@router.post("/reconcile")
def reconcile_route(body: ReconcileBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    refs = [str(r.get("ref")) for r in body.app_rows if r.get("ref") is not None]
    client = _client(db, body.odoo_connection_id)
    if not client.model_exists(body.model):
        raise HTTPException(status_code=422, detail=f"{body.model} isn't installed on this database.")
    try:
        rows = client.execute_kw(body.model, "search_read", [[[body.ref_field, "in", refs]]],
                                 {"fields": [body.ref_field, body.amount_field], "limit": 5000}) if refs else []
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not read {body.model} ({exc.__class__.__name__}).") from exc
    odoo_rows = [{"ref": r.get(body.ref_field), "amount": r.get(body.amount_field)} for r in rows]
    return fl.reconcile(body.app_rows, odoo_rows)


# ---------------------------------------------------------------- B7: alerts, quota, uptime
from app.bridge import ops as bops  # noqa: E402


class AlertBody(BaseModel):
    flow: str = Field(max_length=200)
    error: str = Field(max_length=2000)
    record: str | None = None
    count: int = 1


@router.post("/alerts/preview")
def alert_preview(body: AlertBody) -> dict:
    a = bops.build_alert(body.flow, body.error, body.record, body.count)
    return {"alert": a, "slack": bops.slack_blocks(a), "teams": bops.teams_card(a)}


class QuotaBody(BaseModel):
    used: int
    limit: int | None = None
    cost_per_call: float = 0.0
    budget: float | None = None


@router.post("/quota/watch")
def quota_route(body: QuotaBody) -> dict:
    return bops.quota_watch(body.used, body.limit, body.cost_per_call, body.budget)


# ---------------------------------------------------------------- B8: plain-words drafting, recipes, score
from app.bridge import drafting as bd  # noqa: E402


@router.get("/recipes")
def recipes() -> dict:
    return {"recipes": bd.RECIPES}


class DraftBody(BaseModel):
    text: str = Field(min_length=3, max_length=4000)
    odoo_connection_id: str | None = None


@router.post("/draft")
def draft_route(body: DraftBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    exists = None
    if body.odoo_connection_id:
        exists = _client(db, body.odoo_connection_id).model_exists
    from app.view_engine_ai import AIUnavailable
    try:
        return bd.draft_flow(body.text, model_exists=exists)
    except AIUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/score")
def score_route(body: dict) -> dict:
    return bd.integration_score(body)


# ---------------------------------------------------------------- B9: code export (service / module + handbook)
from fastapi.responses import Response  # noqa: E402

from app.bridge import export as bx  # noqa: E402


@router.get("/flows/{flow_id}/export")
def flow_export(flow_id: str, db: DbSession, kind: str = "service", major: int = 18, footer: bool = True, auth: WorkspaceAuth = Depends(require_app_auth)) -> Response:
    f = fl.get_flow(auth.workspace_id, flow_id)
    if not f:
        raise HTTPException(status_code=404, detail="No such flow.")
    v = next((x for x in f["versions"] if x["status"] in ("approved", "live", "rolled_back")), None)
    if not v:
        raise HTTPException(status_code=409, detail="Export needs an approved version.")
    if kind not in ("service", "module"):
        raise HTTPException(status_code=422, detail="kind is service or module.")
    from app.entitlements import resolve_entitlements

    try:
        ent = resolve_entitlements(db, auth.workspace_id)
        foot = bx.prepared_footer(plan_id=ent.plan_id, white_label=ent.feature_enabled("white_label"), hide=not footer)
    except Exception:  # noqa: BLE001 - no subscription row: treat as free, keep the footer
        foot = bx.PREPARED_FOOTER
    data, errs = bx.build_zip(flow_id, v, kind, major, footer=foot)
    if errs:
        raise HTTPException(status_code=500, detail=errs)
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="bridge-{flow_id}-{kind}.zip"'})


# ---------------------------------------------------------------- B10: canvas + agent call surface
from app.bridge import canvas as bc  # noqa: E402


@router.get("/flows/{flow_id}/canvas")
def flow_canvas(flow_id: str, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    f = fl.get_flow(auth.workspace_id, flow_id)
    if not f or not f.get("live"):
        raise HTTPException(status_code=404, detail="No live version.")
    v = next(x for x in f["versions"] if x["n"] == f["live"])
    return bc.from_defn(flow_id, v["defn"])


class AgentCallBody(BaseModel):
    record: dict
    dry_run: bool = True
    odoo_connection_id: str | None = None


@router.post("/flows/{flow_id}/agent-call")
def agent_call_route(flow_id: str, body: AgentCallBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    f = fl.get_flow(auth.workspace_id, flow_id)
    fields = cands = None
    if body.odoo_connection_id and f and f.get("live"):
        v = next(x for x in f["versions"] if x["n"] == f["live"])
        client = _client(db, body.odoo_connection_id)
        fields = bm.odoo_fields(client, v["defn"]["odoo_model"])
        mapped = {m["odoo"]: body.record.get(m["remote"]) for m in v["defn"].get("mapping") or [] if m.get("odoo")}
        cands = sr.odoo_candidates(client, v["defn"]["odoo_model"], mapped)
    return bc.agent_call(auth.workspace_id, flow_id, body.record, dry_run=body.dry_run,
                         odoo_fields=fields, candidates=cands)


# ---------------------------------------------------------------- delivery engine (10-12): durable queue, retries, ordering
from app.bridge import delivery as dl  # noqa: E402


class EventBody(BaseModel):
    bridge_connection_id: str
    odoo_connection_id: str
    record_key: str = Field(max_length=200)
    record: dict
    idempotency_key: str | None = Field(default=None, max_length=255)


@router.post("/flows/{flow_id}/events")
def flow_event(flow_id: str, body: EventBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    """Receive one record from the outside app. Queued, never written straight away."""
    if body.bridge_connection_id not in _ws_connection_ids(db, auth):
        raise HTTPException(status_code=404, detail="No such Bridge connection.")
    key = body.idempotency_key or sr.idempotency_key(body.bridge_connection_id, flow_id, body.record_key, body.record)
    try:
        ev = dl.submit(db, connection_id=body.bridge_connection_id, idempotency_key=key, flow_id=flow_id,
                       record_key=body.record_key, ws=auth.workspace_id,
                       payload={"flow_id": flow_id, "record_key": body.record_key, "record": body.record,
                                "odoo_connection_id": body.odoo_connection_id})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return {"id": ev.id, "status": ev.status, "duplicate": ev.attempts > 0 or ev.status != "queued"}


class DeliverBody(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    min_gap_ms: int = Field(default=0, ge=0, le=10_000)


@router.post("/deliver")
def deliver(body: DeliverBody, db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    """Deliver what is due: oldest first, one at a time per record, retries with backoff, dead letters after 6 tries."""
    handler = dl.odoo_handler(lambda cid: _client(db, cid), auth.workspace_id)
    out = dl.deliver_due(db, handler, connection_ids=_ws_connection_ids(db, auth), limit=body.limit,
                         min_gap_s=body.min_gap_ms / 1000, ws=auth.workspace_id)
    db.commit()
    return {**out, "queue": dl.queue_stats(db, _ws_connection_ids(db, auth))}


@router.get("/queue")
def queue_view(db: DbSession, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    return {"queue": dl.queue_stats(db, _ws_connection_ids(db, auth))}


@router.post("/gallery/{key}/token/refresh")
def gallery_token_refresh(key: str, auth: WorkspaceAuth = Depends(require_app_auth)) -> dict:
    """Get a fresh access token now (normally automatic). Returns timing only, never the token."""
    from app.bridge import tokens as tk

    _connector(key)
    try:
        out = tk.access_token_for(auth.workspace_id, key, force=True)
    except tk.SignInAgain as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc), "fix": "Sign in again"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {k: v for k, v in out.items() if k != "access_token"}
