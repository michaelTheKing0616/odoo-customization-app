"""Conversational App Studio — sessions, clarify, generate, refine."""

from __future__ import annotations

import contextvars
import json
from types import SimpleNamespace
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai_conversation.brief_expand import BriefExpansion, maybe_expand_brief
from app.ai_conversation.clarify import apply_clarification_answer, build_clarification
from app.ai_conversation.intent_gate import (
    assess_intent,
    merge_resolved_prompt,
    session_already_admitted,
    should_block_generation,
)
from app.ai_conversation.intent_llm import (
    admit_host_from_packet,
    reset_schema_packet,
    set_schema_packet,
)
from app.ai_conversation.understand import (
    build_understanding,
    diagnosis_clarification,
    diagnosis_confirmed,
    dump_understanding,
    load_understanding,
    parse_locked_diagnosis,
)
from app.ai_conversation.metrics import log_session_metrics
from app.ai_conversation.refine import apply_refinement, artifact_hash
from app.live_schema_context import (
    SchemaPacket,
    prepend_schema_packet,
    studio_schema_packet,
    technical_names,
    unknown_technical_names,
)
from app.ai_conversation.session_store import (
    append_turn,
    create_session,
    get_session,
    session_to_dict,
    update_session,
)
from app.odoo_snapshot import clear_snapshot_cache, set_snapshot, snapshot_for_connection
from app.db import get_db
from app.llm_provider import get_llm_provider, get_llm_provider_for_tier
from app.stock_app_install import (
    INSTALL_DECISION,
    STOCK_APP_CLARIFICATION_KIND,
    StockAppProposal,
    declined_message,
    install_stock_app,
    read_install_facts,
    stock_app_clarification,
)

router = APIRouter(prefix="/ai/sessions", tags=["ai-studio"])


class CreateSessionIn(BaseModel):
    connection_id: str | None = None
    prompt: str = Field(min_length=10, max_length=50000)
    feature: str = "studio"
    # Studio toggle — Enrich Must-do with Flash (None = follow connection pref / env)
    flash_ast_enrich: bool | None = None

    @field_validator("connection_id", mode="before")
    @classmethod
    def _blank_connection_id(cls, value: object) -> object:
        # "" / whitespace must not hit the FK — that was a bare Internal Server Error.
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value


class ClarifyIn(BaseModel):
    merge_key: str
    answer_id: str = ""
    answer_text: str = ""
    understanding: dict[str, Any] | None = None


class RefineIn(BaseModel):
    instruction: str = Field(min_length=3)


class GenerateIn(BaseModel):
    force: bool = False


class StudioApplyIn(BaseModel):
    confirm_advanced: bool = False
    confirm_phrase: str | None = None
    skip_validate_live: bool = False


class StockAppDecisionIn(BaseModel):
    decision: Literal["install", "decline"]


_studio_schema_packet = studio_schema_packet


def _open_stock_app_port(conn: Any) -> Any:
    """Live client for the connection. Tests replace this with a fake port."""
    from app.odoo_service import client_from_connection

    return client_from_connection(conn)


def _stock_app_gate(
    conn: Any,
    prompt: str,
    *,
    host_model: str | None = None,
    port: Any | None = None,
) -> StockAppProposal | None:
    """GND-MOD confirm step: propose the stock app the request needs, or None.

    Inputs: the connection row, the request text, an optional locked host, and
    an optional already-open port. Side effects: read-only RPCs. A connection
    that cannot be reached returns None so the existing path still runs.
    """
    if conn is None:
        return None
    if port is None:
        try:
            port = _open_stock_app_port(conn)
        except Exception:  # noqa: BLE001 — unreachable Odoo must not block session create
            return None
    return _brief_gate(conn, prompt, host_model=host_model, port=port)[0]


def _brief_gate(
    conn: Any,
    prompt: str,
    *,
    host_model: str | None = None,
    port: Any | None = None,
) -> tuple[StockAppProposal | None, dict[str, Any] | None]:
    """Blocking proposal for the PRIMARY host app only, plus the integration plan.

    One missing / Enterprise-only integration app never refuses the brief: it is
    listed in the plan (left out or deferred, with how to enable it later).
    Python-needing pieces are labelled for the custom-code path. Side effects:
    read-only RPCs. Unreachable Odoo returns (None, None).
    """
    if conn is None:
        return None, None
    if port is None:
        try:
            port = _open_stock_app_port(conn)
        except Exception:  # noqa: BLE001 — unreachable Odoo must not block session create
            return None, None
    from app.brief_integrations import build_brief_plan
    from app.hosting import hosting_hint_from_url
    from app.tier_matrix import detect_edition

    url = getattr(conn, "url", None)
    edition = detect_edition(getattr(conn, "server_version", None), url=url)
    proposal, plan = build_brief_plan(
        prompt,
        port,
        host_model=host_model,
        edition=edition,
        hosting_hint=hosting_hint_from_url(url, getattr(conn, "server_version", None), getattr(conn, "hosting", None)),
    )
    return proposal, (plan.as_dict() if plan.has_notes else None)


def _record_integration_plan(db: Session, out: dict[str, Any], plan: dict[str, Any] | None) -> None:
    """Flag left-out / deferred apps and custom code pieces on the session (no block)."""
    if not plan:
        return
    out["integration_plan"] = plan
    row = get_session(db, str(out.get("id") or "")) if out.get("id") else None
    if row is None:
        return
    append_turn(
        db,
        row,
        role="assistant",
        kind="integration_plan",
        content=str(plan.get("summary") or ""),
        metadata={"integration_plan": plan},
    )

def _bind_original_brief(row: Any) -> None:
    """Later turns: quotes stay located in the owner's words (kept on the expansion turn)."""
    from app.ai_conversation.brief_checklist import set_original

    original = row.prompt_original or ""
    try:
        for t in json.loads(row.conversation_json or "[]"):
            exp = ((t or {}).get("metadata") or {}).get("brief_expansion") if isinstance(t, dict) else None
            if isinstance(exp, dict) and exp.get("original"):
                original = str(exp["original"])
    except (TypeError, ValueError):
        pass
    set_original(original)


def _record_brief_expansion(
    db: Session, out: dict[str, Any], expansion: BriefExpansion | None
) -> None:
    """Show the person what their short request was expanded into (no block)."""
    if expansion is None:
        return
    out["brief_expansion"] = expansion.as_dict()
    row = get_session(db, str(out.get("id") or "")) if out.get("id") else None
    if row is None:
        return
    append_turn(
        db,
        row,
        role="assistant",
        kind="brief_expansion",
        content=expansion.summary(),
        metadata={"brief_expansion": expansion.as_dict()},
    )

def _session_next_step(
    prompt: str,
    resolved: dict[str, str],
) -> tuple[Any, dict[str, Any] | None]:
    """Intent gate, then the locked diagnosis. Shared by create and resume."""
    assessment = assess_intent(prompt, resolved_answers=resolved)
    resolved.update(_resolved_from_llm(assessment))
    clarification = None
    if should_block_generation(assessment):
        clarification = build_clarification(assessment, prompt=prompt)
    if clarification is None:
        clarification = _attach_diagnosis(prompt, resolved, assessment)
    return assessment, clarification


def ground_studio_generate(
    prompt: str,
    *,
    schema_packet: SchemaPacket,
    locked: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepend the packet and admit the diagnosis host. Existing GenerateIR admit stays downstream.

    Inputs: operator prompt and a fixture or live packet. Output: the user
    message the model sees, the grounded understanding, and the admitted host.
    Does not call a live model. Does not add a second admit gate.
    """

    token = set_schema_packet(schema_packet)
    try:
        user_message = prepend_schema_packet(prompt, schema_packet)
        understanding = build_understanding(prompt, schema_packet=schema_packet)
        locked_host = str((locked or {}).get("host_model") or "").strip()
        candidate = locked_host or understanding.host_model or ""
        host = admit_host_from_packet(candidate, schema_packet)
        if understanding.host_model and host is None:
            # Discard the unknown host. Do not flip inherit → new residual app.
            understanding.host_model = None
        payload = understanding.to_dict()
        return {
            "user_message": user_message,
            "understanding": payload,
            "host_model": host,
            "placement_anchor": payload.get("placement_anchor"),
        }
    finally:
        reset_schema_packet(token)


def _resolved_from_llm(assessment: Any) -> dict[str, str]:
    resolved: dict[str, str] = {}
    blob = getattr(assessment, "llm_resolved", None) or {}
    if not isinstance(blob, dict):
        return resolved
    if blob.get("pack_id"):
        resolved["pack_choice"] = str(blob["pack_id"])
    if blob.get("residual"):
        resolved["residual"] = str(blob["residual"])
    if blob.get("capability_path") == "stock_first":
        resolved["ir_confidence"] = "stock_first"
    if blob.get("host_model"):
        resolved["host_model"] = str(blob["host_model"])
    return resolved


def _prompt_with_llm(prompt: str, assessment: Any) -> str:
    extra: list[str] = []
    blob = getattr(assessment, "llm_resolved", None) or {}
    if not isinstance(blob, dict):
        return prompt
    if blob.get("pack_id"):
        extra.append(f"Domain pack: {blob['pack_id']}.")
    if blob.get("residual"):
        extra.append(f"Custom code: {blob['residual']}.")
    if blob.get("capability_path") == "stock_first":
        extra.append("Capability path: stock_first")
    if blob.get("host_model"):
        extra.append(f"Host: {blob['host_model']}")
    if blob.get("needs_module"):
        extra.append("Needs module: yes")
    if not extra:
        return prompt
    return merge_resolved_prompt(prompt, _resolved_from_llm(assessment)) + "\n" + "\n".join(extra)


def _provider_meta() -> tuple[str | None, bool]:
    primary = get_llm_provider()
    if primary is None:
        return None, False
    name = primary.name
    fallback = name == "ollama" and (get_llm_provider_for_tier("fast") is not None)
    return name, fallback


def _assessment_payload(assessment: Any, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "clear": bool(getattr(assessment, "clear", False)),
        "triggers": list(getattr(assessment, "triggers", None) or []),
        "ir_confidence": getattr(assessment, "ir_confidence", None),
        "llm_resolved": getattr(assessment, "llm_resolved", None),
    }
    if extra:
        payload.update(extra)
    return payload


def _attach_diagnosis(
    prompt: str,
    resolved: dict[str, str],
    assessment: Any,
) -> dict[str, Any] | None:
    """Intent chips first; then lock a diagnosis before generate."""
    if should_block_generation(assessment):
        return None
    if diagnosis_confirmed(resolved):
        return None
    understanding = load_understanding(resolved) or build_understanding(
        prompt, resolved_answers=resolved
    )
    design = understanding.app_design if isinstance(understanding.app_design, dict) else {}
    from app.ai_conversation import diagnosis_decision as dd

    decision = dd.load(resolved)
    # Prefer the design's checklist meta when present; otherwise run checklist_only so a
    # design-less (or stock-app) path still persists routes/exclusions/stock_plan.
    if decision is None:
        chk = None
        meta = (design.get("llm_outcome") or {}).get("intent_contract") or {}
        if isinstance(meta.get("checklist"), dict) and meta["checklist"].get("items"):
            chk = meta["checklist"]
        elif "_checklist_only_json" in resolved:
            try:
                chk = json.loads(resolved["_checklist_only_json"])
            except (TypeError, ValueError):
                chk = None
        if chk is None:
            from app.ai_conversation.app_design import checklist_only
            chk = checklist_only(prompt, resolved)
            if chk is not None:
                resolved["_checklist_only_json"] = json.dumps(chk, ensure_ascii=False)
        if chk is not None:
            decision = dd.from_checklist(chk)
            dd.persist(resolved, decision)
            said = [f'{r["item"]} ({(r.get("message") or "")[:1].lower() + (r.get("message") or "")[1:]})'
                    for r in decision.get("left_out") or [] if r.get("message")]
            said += [f'{r["item"]}: {(r.get("message") or r.get("reason") or "")}' for r in decision.get("declines") or []
                     if r.get("kind") == "route"]
            understanding.out_of_scope = list(dict.fromkeys(list(understanding.out_of_scope) + said))[:12]
    dump_understanding(resolved, understanding)
    from app.ai_conversation.intent_contract import pending_contract_clarification

    # Contradictions in the owner's own words come first (code-authorized conflict look).
    for cf in (decision or {}).get("conflicts") or []:
        key = f"intent_contract:conflict:{cf.get('a')}"
        if str((resolved or {}).get(key) or "").strip():
            continue
        qa, qb = str(cf.get("quote_a") or "").rstrip(". "), str(cf.get("quote_b") or "").rstrip(". ")
        opts = [str(o) for o in cf.get("options") or [] if str(o).strip()] or [qa, qb]
        return dd.attach_to_clarification({
            "id": f"intent-contract-conflict-{cf.get('a')}", "kind": "intent_contract", "merge_key": key,
            "question": cf.get("question") or "Your brief says two different things here. Which one should App Studio build?",
            "help": f"Your brief says: {qa}. It also says: {qb}.",
            "options": [{"id": f"opt{i}", "label": o} for i, o in enumerate(opts[:3])],
            "default_id": "opt0",
        }, decision)
    # Prefer decision-register questions over legacy contract clarify when present.
    qs = (decision or {}).get("register", {}).get("questions") or []
    if qs and not any(str(k).startswith("intent_contract:") for k in (resolved or {})):
        q0 = qs[0]
        return {
            "id": q0.get("id") or "intent_contract:decision",
            "kind": "intent_contract",
            "merge_key": "intent_contract",
            "question": q0.get("question") or f"About {q0.get('item')}: which option?",
            "help": "This choice changes who can do what or how money is handled.",
            "options": [{"id": o, "label": o} for o in (q0.get("options") or [])] or [
                {"id": "yes", "label": "Yes"}, {"id": "no", "label": "No"}],
            "diagnosis_decision": decision,
            "integration_routes": (decision or {}).get("routes") or [],
        }
    contract_question = pending_contract_clarification(
        design.get("intent_contract") if isinstance(design.get("intent_contract"), list) else [],
        design.get("critic_findings") if isinstance(design.get("critic_findings"), list) else [],
        resolved,
    )
    if contract_question is not None:
        summary = str(getattr(understanding, "summary", "") or design.get("purpose") or "").strip()
        if summary:
            contract_question["understood"] = summary[:400]
        return dd.attach_to_clarification(contract_question, decision)
    out = diagnosis_clarification(understanding)
    out = dd.attach_to_clarification(out, decision)
    # S11: apps the design is built on but that are not installed yet -> one clear install
    # step between the diagnosis and the build (code-checked against the live snapshot).
    from app.ai_conversation.install_step import install_step, session_plans
    from app.odoo_snapshot import current_snapshot

    snap = current_snapshot()
    step = (install_step(design, snap, session_plans(understanding, decision, snap))
            if snap is not None else None)
    if step:
        out["install_step"] = mark_read_only(step, SimpleNamespace(write_mode=_CONN_WRITE_MODE.get()))
    return out


def _session_design(resolved: dict[str, Any]) -> dict[str, Any]:
    u = load_understanding(resolved)
    d = getattr(u, "app_design", None) if u is not None else None
    return d if isinstance(d, dict) else {}


def _session_plans(resolved: dict[str, Any], snap: Any) -> list[dict[str, Any]]:
    from app.ai_conversation import diagnosis_decision as dd
    from app.ai_conversation.install_step import session_plans

    return session_plans(load_understanding(resolved), dd.load(resolved), snap)


def _fresh_install_step(db: Session, row: Any, resolved: dict[str, Any]) -> tuple[Any, dict[str, Any] | None]:
    """(connection, install step from a fresh snapshot) for a session with planned installs."""
    from app.ai_conversation.install_step import install_step

    design = _session_design(resolved)
    if not row.connection_id:
        return None, None
    from app.odoo_service import get_connection_or_404

    try:
        conn = get_connection_or_404(db, row.connection_id)
    except Exception:  # noqa: BLE001
        conn = None
    if conn is None:
        return None, None
    snap = snapshot_for_connection(conn, row.prompt_original or "")
    step = install_step(design, snap, _session_plans(resolved, snap))
    if step is None and resolved.get(DESIGN_REFRESH_KEY):
        from app.ai_conversation.install_step import refresh_step

        step = refresh_step()
    return conn, mark_read_only(step, conn)


DESIGN_REFRESH_KEY = "_design_refresh_pending"
# The request's connection write mode, so the diagnosis can show a read-only install step.
_CONN_WRITE_MODE: "contextvars.ContextVar[str]" = contextvars.ContextVar("studio_conn_write_mode", default="")


def mark_read_only(step: dict[str, Any] | None, conn: Any) -> dict[str, Any] | None:
    """Read-only connections show that up front: Install is disabled, with plain guidance."""
    from app.ai_conversation.install_step import read_only_step

    if step and str(getattr(conn, "write_mode", "") or "") == "observer":
        return read_only_step(step)
    return step


def _refresh_design_after_install(db: Session, row: Any, conn: Any, resolved: dict[str, Any],
                                  snap: Any) -> str:
    """Design refresh on the installed app's real models and fields ('' when done).

    Reuses the session's frozen requirement list and stored decision (the authorization
    graph): the AI redraws the design against the live schema, code re-applies scope,
    maps copies onto stock fields and retargets automations. No new requirement may appear.
    """
    import dataclasses

    from app.ai_conversation.grounding import StudioGrounding, reset_grounding, set_grounding
    from app.ai_conversation.intent_llm import reset_intent_llm_override, set_intent_llm_override

    before = resolved.get("_intent_contract_json")
    try:
        before_ids = {str(r.get("id")) for r in json.loads(before or "[]") if isinstance(r, dict)}
    except (TypeError, ValueError):
        before_ids = set()
    g_token = p_token = o_token = s_token = None
    try:
        try:
            g = StudioGrounding.from_dict(json.loads(resolved.get("_grounding_json") or "null"))
        except (TypeError, ValueError):
            g = None
        if g is not None:
            now = {str(m) for m in getattr(snap, "modules", {}) or {}}
            from app.ai_conversation.install_step import _label

            have = {_label(m).lower() for m in now}
            g = dataclasses.replace(
                g,
                apps_installed=tuple(dict.fromkeys(list(g.apps_installed) + [a for a in g.apps_missing if a.lower() in have])),
                apps_missing=tuple(a for a in g.apps_missing if a.lower() not in have),
            )
            resolved["_grounding_json"] = json.dumps(g.as_dict())
            g_token = set_grounding(g)
        s_token = set_snapshot(snap)
        p_token = set_schema_packet(_studio_schema_packet(conn, prompt=row.prompt_original or ""))
        if resolved.get("_ai_step") in {"on", "off"}:
            o_token = set_intent_llm_override(resolved.get("_ai_step") == "on")
        work = dict(resolved)
        work.pop("understanding_json", None)
        prompt = getattr(row, "prompt_resolved", None) or row.prompt_original or ""
        understanding = build_understanding(prompt, resolved_answers=work)
        design = understanding.app_design if isinstance(understanding.app_design, dict) else {}
        if not design:
            return "The design could not be updated for the installed apps yet. Check again to retry."
        after_ids = {str(r.get("id")) for r in design.get("intent_contract") or [] if isinstance(r, dict)}
        if before_ids and not after_ids <= before_ids:
            return "The updated design asked for something new, so it was not used. Check again to retry."
        for k in list(work):
            resolved[k] = work[k]
        dump_understanding(resolved, understanding)
        resolved.pop(DESIGN_REFRESH_KEY, None)
        if diagnosis_confirmed(resolved):
            resolved.pop("diagnosis", None)  # the design changed: review it again before building
        return ""
    except Exception:  # noqa: BLE001 - fail closed: the gate stays until the refresh works
        import logging

        logging.getLogger(__name__).exception("Design refresh after install failed")
        return "The design could not be updated for the installed apps yet. Check again to retry."
    finally:
        if s_token is not None:
            from app.odoo_snapshot import _SNAPSHOT

            _SNAPSHOT.reset(s_token)
        if p_token is not None:
            reset_schema_packet(p_token)
        if g_token is not None:
            reset_grounding(g_token)
        if o_token is not None:
            reset_intent_llm_override(o_token)


def _install_gate(db: Session, row: Any, resolved: dict[str, Any]) -> None:
    """S11: Build/Apply stay closed until the design's planned apps are installed (409, plain)."""
    _, step = _fresh_install_step(db, row, resolved)
    if step:
        raise HTTPException(
            status_code=409,
            detail={"message": step["blocked_message"], "install_step": step},
        )



def _clear_conn_snapshot(conn: Any) -> None:
    """After Apply, drop only this connection's cached live snapshot."""
    key = str(getattr(conn, "id", "") or getattr(conn, "url", ""))
    if key:
        clear_snapshot_cache(key)


@router.post("")
def create_session_route(body: CreateSessionIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    prompt = body.prompt.strip()
    connection_id = body.connection_id
    conn_row = None
    if connection_id:
        from app.odoo_service import get_connection_or_404

        try:
            conn_row = get_connection_or_404(db, connection_id)
        except LookupError as exc:
            raise HTTPException(
                status_code=404,
                detail="Connection not found — open App Studio from a connection page, then Start new app.",
            ) from exc
        _CONN_WRITE_MODE.set(str(getattr(conn_row, "write_mode", "") or ""))

    # Flash AST enrich toggle: request body > connection studio pref > env
    from app.ai_conversation.intent_llm import reset_intent_llm_override, set_intent_llm_override
    from app.studio_prefs import get_studio_prefs, resolve_flash_ast_enrich

    conn_pref = None
    if conn_row is not None:
        conn_pref = get_studio_prefs(conn_row).get("flash_ast_enrich")
    enrich_override = resolve_flash_ast_enrich(
        connection_pref=conn_pref if isinstance(conn_pref, bool) else None,
        request_override=body.flash_ast_enrich,
        prompt=prompt,
    )
    override_token = set_intent_llm_override(enrich_override)
    packet_token = None
    from app.ai_conversation.grounding import grounding_from_connection, reset_grounding, set_grounding

    grounding_token = None
    try:
        # Vague one-line requests become a structured brief so they reach the
        # design step. Precise / structured briefs are left untouched.
        from concurrent.futures import ThreadPoolExecutor as _TPE
        import contextvars as _ctxv

        from app.ai_conversation.brief_checklist import set_original

        set_original(prompt)  # the owner's words stay the evidence authority
        # Expansion runs in parallel with the brief gate / snapshot read; it only enriches design.
        _xpool = _TPE(max_workers=1)
        _xfut = _xpool.submit(_ctxv.copy_context().run, maybe_expand_brief, prompt, conn=conn_row)
        _xpool.shutdown(wait=False)
        _owner_prompt = prompt
        try:
            from app.odoo_snapshot import snapshot_for_connection as _sfc
            _pre_snap = _sfc(conn_row, prompt)
        except Exception:  # noqa: BLE001
            _pre_snap = None
        try:
            expansion = _xfut.result(timeout=90)
        except Exception:  # noqa: BLE001 - expansion is optional
            expansion = None
        if expansion is not None:
            prompt = expansion.expanded
            # The AI-step choice was made from the short request. The expanded
            # brief is long and structured, so decide again from its text.
            # removed: reset_intent_llm_override(override_token)
            # removed: enrich_override = resolve_flash_ast_enrich(
                # removed: connection_pref=conn_pref if isinstance(conn_pref, bool) else None,
                # removed: request_override=None,
                # removed: prompt=prompt,
            # removed: )
            # removed: override_token = set_intent_llm_override(enrich_override)
        proposal, plan = _brief_gate(conn_row, prompt)
        grounding_token = set_grounding(grounding_from_connection(conn_row, plan))
        set_snapshot(_pre_snap if (_pre_snap is not None and prompt == _owner_prompt) else snapshot_for_connection(conn_row, prompt))        
        from app.ai_conversation.brief_checklist import enabled as _bc_enabled

        # S11: an installable missing app no longer parks the request on "install X first";
        # the design is made on the planned-install app and the install step follows it.
        if proposal is not None and not (_bc_enabled() and getattr(proposal, "installable", False)):
            out = _create_stock_app_session(body, db, prompt, connection_id, proposal)
            _record_brief_expansion(db, out, expansion)
            return out
        packet = _studio_schema_packet(conn_row, prompt=prompt)
        packet_token = set_schema_packet(packet)
        out = _create_session_inner(body, db, prompt, connection_id, enrich_override)
        _record_integration_plan(db, out, plan)
        _record_brief_expansion(db, out, expansion)
        return out
    finally:
        if packet_token is not None:
            reset_schema_packet(packet_token)
        if grounding_token is not None:
            reset_grounding(grounding_token)
        reset_intent_llm_override(override_token)


def _create_stock_app_session(
    body: CreateSessionIn,
    db: Session,
    prompt: str,
    connection_id: str | None,
    proposal: StockAppProposal,
) -> dict[str, Any]:
    """Park the request on the install confirm step. The same session resumes after."""
    clarification = stock_app_clarification(proposal)
    provider, fallback = _provider_meta()
    # Stock-app path still persists the canonical decision (exclusions, routes, stock plan).
    seed: dict[str, str] = {}
    try:
        from app.ai_conversation import diagnosis_decision as dd
        from app.ai_conversation.app_design import checklist_only

        chk = checklist_only(prompt, {})
        if chk is not None:
            seed["_checklist_only_json"] = json.dumps(chk, ensure_ascii=False)
            dd.persist(seed, dd.from_checklist(chk))
            if isinstance(clarification, dict):
                clarification = dd.attach_to_clarification(clarification, dd.load(seed))
    except Exception:  # noqa: BLE001 - the install step must not break
        import logging; logging.getLogger(__name__).exception("Stock-app path: checklist decision failed")
    try:
        row = create_session(
            db,
            connection_id=connection_id,
            feature=body.feature or "studio",
            prompt=prompt,
            status="clarifying",
            resolved_answers=seed,
            provider_used=provider,
            fallback_used=fallback,
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not create the App Studio session for this connection. "
                "Refresh the connection page and try Start new app again."
            ),
        ) from exc
    update_session(db, row, pending_clarification=clarification, prompt_resolved=prompt)
    append_turn(
        db,
        row,
        role="assistant",
        kind="stock_app_install",
        content=clarification["question"],
        metadata={"clarification": clarification},
    )
    out = session_to_dict(row)
    out["clarification"] = clarification
    return out


def _create_session_inner(body, db, prompt, connection_id, enrich_override):
    from app.ai_conversation.grounding import current_grounding

    resolved: dict[str, str] = {}
    # Underscore keys never reach the resolved prompt; clarify reuses them.
    if enrich_override is not None:
        resolved["_ai_step"] = "on" if enrich_override else "off"
    grounding = current_grounding()
    if grounding is not None:
        resolved["_grounding_json"] = json.dumps(grounding.as_dict())
    provider, fallback = _provider_meta()
    assessment, clarification = _session_next_step(prompt, resolved)

    try:
        if clarification:
            row = create_session(
                db,
                connection_id=connection_id,
                feature=body.feature or "studio",
                prompt=prompt,
                status="clarifying",
                resolved_answers=resolved,
                provider_used=provider,
                fallback_used=fallback,
            )
            update_session(
                db,
                row,
                pending_clarification=clarification,
                prompt_resolved=prompt,
            )
            append_turn(
                db,
                row,
                role="assistant",
                kind="clarify",
                content=str((clarification or {}).get("question") or ""),
                metadata={"clarification": clarification},
            )
            log_session_metrics(db, row.id, clarify_count=1)
            out = session_to_dict(row)
            out["assessment"] = _assessment_payload(assessment)
            out["clarification"] = clarification
            out["understanding"] = (clarification or {}).get("understanding")
            return out

        row = create_session(
            db,
            connection_id=connection_id,
            feature=body.feature or "studio",
            prompt=prompt,
            status="ready",
            resolved_answers=resolved,
            provider_used=provider,
            fallback_used=fallback,
        )
        update_session(db, row, prompt_resolved=_prompt_with_llm(prompt, assessment))
        out = session_to_dict(row)
        out["assessment"] = _assessment_payload(assessment, extra={"clear": True, "triggers": []})
        return out
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not create the App Studio session for this connection. "
                "Refresh the connection page and try Start new app again."
            ),
        ) from exc


@router.get("/{session_id}")
def get_session_route(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    out = session_to_dict(row)
    artifact = out.get("artifact") if isinstance(out.get("artifact"), dict) else {}
    stored_hash = row.artifact_hash
    if artifact and stored_hash:
        from app.ai_conversation.refine import artifact_hash

        live_hash = artifact_hash(artifact)
        out["artifact_consistent"] = live_hash == stored_hash
    else:
        out["artifact_consistent"] = True
    return out


@router.post("/{session_id}/clarify")
def clarify_session_route(
    session_id: str,
    body: ClarifyIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if body.merge_key.startswith("_"):
        # Underscore keys hold server state (frozen contract, seal, decision); never client-set.
        raise HTTPException(status_code=422, detail={"message": "That answer can't be saved. Pick one of the options shown."})
    row = get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        resolved = json.loads(row.resolved_answers_json or "{}")
    except json.JSONDecodeError:
        resolved = {}
    if not isinstance(resolved, dict):
        resolved = {}
    # Same grounding + AI-step choice as session create (sync route: context is per request).
    from app.ai_conversation.grounding import StudioGrounding, set_grounding
    from app.ai_conversation.intent_llm import set_intent_llm_override

    try:
        set_grounding(StudioGrounding.from_dict(json.loads(resolved.get("_grounding_json") or "null")))
    except (TypeError, ValueError):
        pass
    if row.connection_id:
        try:
            from app.odoo_service import get_connection_or_404

            _clar_conn = get_connection_or_404(db, row.connection_id)
            _CONN_WRITE_MODE.set(str(getattr(_clar_conn, "write_mode", "") or ""))
            set_snapshot(snapshot_for_connection(_clar_conn, row.prompt_original or ""))
        except Exception:  # noqa: BLE001 - the snapshot is an enhancement only
            pass        
    if resolved.get("_ai_step") in {"on", "off"}:
        set_intent_llm_override(resolved.get("_ai_step") == "on")

    prompt_resolved, resolved = apply_clarification_answer(
        row.prompt_original,
        merge_key=body.merge_key,
        answer_id=body.answer_id,
        answer_text=body.answer_text,
        resolved_answers=resolved,
        understanding=body.understanding,
    )
    if body.merge_key.startswith(("intent_contract:", "intent_critic:")):
        # The answer changes a material interpretation. Rebuild its source-anchored
        # contract instead of confirming the design built before the answer.
        resolved.pop("understanding_json", None)
    append_turn(
        db,
        row,
        role="user",
        kind="clarify_answer",
        content=body.answer_text or body.answer_id,
        metadata={"merge_key": body.merge_key},
    )

    assessment = assess_intent(prompt_resolved, resolved_answers=resolved)
    if body.merge_key == "diagnosis" and body.answer_id == "reject":
        # Clear previous draft + locked Contract IR when diagnosis changes.
        resolved.pop("understanding_json", None)
        resolved.pop("_intent_contract_json", None)
        resolved.pop("_intent_contract_seal", None)
        resolved.pop("diagnosis", None)
        update_session(
            db,
            row,
            prompt_resolved=row.prompt_original,
            resolved_answers=resolved,
            pending_clarification=None,
            status="rejected",
            artifact={},
            artifact_hash=None,
            job_id=None,
        )
        out = session_to_dict(row)
        out["assessment"] = _assessment_payload(assessment)
        out["rejected"] = True
        out["clarification"] = None
        return out

    if body.merge_key == "diagnosis" and body.answer_id == "confirm":
        # One session IR: wipe stale canvas (Restaurant under Visitor Log Contract)
        # before Generate so Contract title and artifact cannot diverge.
        # Also drop prior job_id so sync cannot resurrect pack IR mid-flight.
        update_session(
            db,
            row,
            artifact={},
            artifact_hash=None,
            job_id=None,
        )

    clarification = (
        build_clarification(assessment, prompt=prompt_resolved)
        if should_block_generation(assessment)
        else None
    )
    if clarification is None:
        clarification = _attach_diagnosis(prompt_resolved, resolved, assessment)
    status = "clarifying" if clarification else "ready"

    update_session(
        db,
        row,
        prompt_resolved=prompt_resolved,
        resolved_answers=resolved,
        pending_clarification=clarification,
        status=status,
    )

    if clarification:
        append_turn(
            db,
            row,
            role="assistant",
            kind="clarify",
            content=str(clarification.get("question") or ""),
            metadata={"clarification": clarification},
        )
        log_session_metrics(db, row.id, clarify_count=1)

    out = session_to_dict(row)
    out["assessment"] = _assessment_payload(
        assessment,
        extra={"clear": status == "ready"},
    )
    out["clarification"] = clarification
    if clarification and clarification.get("understanding"):
        out["understanding"] = clarification.get("understanding")
    return out


@router.post("/{session_id}/generate")
def generate_session_route(
    session_id: str,
    body: GenerateIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if row.status == "generating" and row.job_id:
        out = session_to_dict(row)
        out["job_id"] = row.job_id
        return out

    prompt = row.prompt_resolved or row.prompt_original
    _bind_original_brief(row)
    try:
        resolved = json.loads(row.resolved_answers_json or "{}")
    except json.JSONDecodeError:
        resolved = {}
    if not isinstance(resolved, dict):
        resolved = {}
    assessment = assess_intent(prompt, resolved_answers=resolved)
    if (
        should_block_generation(assessment)
        and not body.force
        and not session_already_admitted(row.status)
    ):
        clarification = build_clarification(assessment, prompt=prompt)
        if clarification:
            update_session(db, row, status="clarifying", pending_clarification=clarification)
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Clarification required before generation",
                    "clarification": clarification,
                },
            )
    if (
        not diagnosis_confirmed(resolved)
        and not body.force
        and row.status not in {"generating", "review", "delivered"}
    ):
        clarification = _attach_diagnosis(prompt, resolved, assessment)
        if clarification:
            update_session(
                db,
                row,
                status="clarifying",
                pending_clarification=clarification,
                resolved_answers=resolved,
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Confirm the diagnosis before generation",
                    "clarification": clarification,
                },
            )

    _install_gate(db, row, resolved)
    understanding = load_understanding(resolved) or parse_locked_diagnosis(prompt)
    host_override = (understanding.host_model if understanding else None) or None
    locked_understanding = understanding.to_dict() if understanding else None

    from app.ai_draft_jobs import build_draft_job_kwargs, enqueue_draft_job
    from app.odoo_service import client_from_connection, get_connection_or_404
    from app.protected_enforcement import manifest_from_json
    from app.routers.ai import _load_reuse_catalog
    from app.schemas import AiDraftModuleBody

    packet_token = None
    try:
        connection_id = row.connection_id

        draft_body = AiDraftModuleBody(prompt=prompt, connection_id=connection_id)
        available, installed, reuse_views, reuse_actions, stock_catalog = _load_reuse_catalog(
            db, draft_body
        )
        protected_manifest = None
        odoo_version = None
        conn = None
        if connection_id:
            try:
                conn = get_connection_or_404(db, connection_id)
                protected_manifest = manifest_from_json(
                    getattr(conn, "protected_manifest_json", None)
                )
                odoo_version = getattr(conn, "server_version", None) or getattr(
                    conn, "protected_manifest_version", None
                )
            except LookupError:
                conn = None

        packet = None
        integration_plan: dict[str, Any] | None = None
        if conn is not None:
            live_client = None
            try:
                live_client = client_from_connection(conn)
            except Exception:  # noqa: BLE001
                live_client = None
            if live_client is not None:
                proposal, integration_plan = _brief_gate(
                    conn, prompt, host_model=host_override, port=live_client
                )
                if proposal is not None:
                    clarification = stock_app_clarification(proposal)
                    update_session(
                        db,
                        row,
                        status="clarifying",
                        pending_clarification=clarification,
                    )
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "message": clarification["question"],
                            "clarification": clarification,
                        },
                    )

            packet = _studio_schema_packet(
                SimpleNamespace(
                    id=getattr(conn, "id", connection_id),
                    server_version=odoo_version or getattr(conn, "server_version", "") or "",
                    odoo_major=getattr(conn, "odoo_major", None),
                    installed_modules=installed,
                    client=live_client,
                ),
                prompt=prompt,
                host=host_override,
                available=available,
            )
        packet_token = set_schema_packet(packet)
        if packet is not None:
            admitted_host = admit_host_from_packet(host_override or "", packet)
            if host_override and admitted_host is None:
                # Discard the unknown host. Do not invent a new residual app.
                host_override = None
                if isinstance(locked_understanding, dict):
                    locked_understanding = dict(locked_understanding)
                    locked_understanding["host_model"] = None
            else:
                host_override = admitted_host or host_override

        job_id = enqueue_draft_job(
            db,
            connection_id=connection_id,
            body_kwargs=build_draft_job_kwargs(
                prompt=prompt,
                connection_id=connection_id,
                available_models=available,
                installed_modules=installed,
                stock_catalog=stock_catalog,
                reuse_views=reuse_views or None,
                reuse_actions=reuse_actions or None,
                protected_manifest=protected_manifest,
                odoo_version=odoo_version,
                expand=draft_body.expand,
                pipeline=draft_body.pipeline,
                grain_override=draft_body.grain,
                gallery_id=draft_body.gallery_id,
                host_model_override=host_override or draft_body.host_model,
                connect_points_override=draft_body.connect_points,
                ai_session_id=session_id,
                locked_understanding=locked_understanding,
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not start the draft job. "
                f"{type(exc).__name__}: {str(exc).strip()[:240] or 'unknown error'}"
            ),
        ) from exc
    finally:
        if packet_token is not None:
            reset_schema_packet(packet_token)

    update_session(
        db,
        row,
        status="generating",
        job_id=job_id,
        pending_clarification=None,
    )
    append_turn(
        db,
        row,
        role="system",
        kind="generate",
        content="Generation started",
        metadata={"job_id": job_id},
    )
    out = session_to_dict(row)
    out["job_id"] = job_id
    _record_integration_plan(db, out, integration_plan)
    return out


def _reread_schema_after_install(
    conn: Any,
    port: Any,
    *,
    prompt: str,
    model: str,
) -> SchemaPacket | None:
    """Rebuild the live packet on the same connection after the install."""
    installed: list[str] = []
    try:
        from app.capabilities import sample_installed_modules

        installed = list(sample_installed_modules(port, limit=300) or [])
    except Exception:  # noqa: BLE001 — module list is context, not a gate
        installed = []
    return _studio_schema_packet(
        SimpleNamespace(
            id=getattr(conn, "id", None),
            server_version=getattr(conn, "server_version", "") or "",
            odoo_major=getattr(conn, "odoo_major", None),
            installed_modules=installed,
            client=port,
        ),
        prompt=prompt,
        host=model,
    )


@router.post("/{session_id}/install-apps")
def install_apps_route(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """S11: install the apps the design is built on, then re-check the database.

    Code authorizes each module: planned by the session's design AND listed as
    installable in a fresh snapshot. Installs go through ``module.install``.
    Returns the session with the remaining ``install_step`` (None when done).
    """
    from app.ai_conversation.install_step import install_planned_module, install_step

    row = get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        resolved = json.loads(row.resolved_answers_json or "{}")
    except json.JSONDecodeError:
        resolved = {}
    resolved = resolved if isinstance(resolved, dict) else {}
    conn, step = _fresh_install_step(db, row, resolved)
    installed: list[str] = []
    failed: list[str] = []
    refresh_error = ""
    if step and step.get("read_only"):
        raise HTTPException(status_code=409, detail={"message": step["blocked_message"], "install_step": step})
    if step and step.get("apps") and conn is not None:
        try:
            port = _open_stock_app_port(conn)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502,
                detail={"message": "The apps were not installed because Odoo could not be reached."},
            ) from exc
        for app_row in step["apps"]:
            if not app_row.get("installable"):
                failed.append(f"{app_row['label']} is still not installed. Ask your Odoo administrator "
                              "to install it, then check again.")
                continue
            ok, msg = install_planned_module(port, app_row["module"], app_row["label"])
            (installed if ok else failed).append(msg)
            append_turn(db, row, role="system",
                        kind="stock_app_installed" if ok else "stock_app_install_failed",
                        content=msg, metadata={"module": app_row["module"]})
        clear_snapshot_cache(str(getattr(conn, "id", "") or "") or None)
        clear_snapshot_cache()
        snap = snapshot_for_connection(conn, row.prompt_original or "")
        step = install_step(_session_design(resolved), snap, _session_plans(resolved, snap))
        if installed:
            resolved[DESIGN_REFRESH_KEY] = "1"
            update_session(db, row, resolved_answers=resolved)
    if not step and conn is not None and resolved.get(DESIGN_REFRESH_KEY):
        snap = snapshot_for_connection(conn, row.prompt_original or "")
        refresh_error = _refresh_design_after_install(db, row, conn, resolved, snap)
        if refresh_error:
            from app.ai_conversation.install_step import refresh_step

            step = mark_read_only(refresh_step(), conn)
            failed.append(refresh_error)
        else:
            append_turn(db, row, role="system", kind="design_refreshed",
                        content="Updated the design to use the installed apps.", metadata={})
        update_session(db, row, resolved_answers=resolved)
        if not refresh_error:
            prompt_now = getattr(row, "prompt_resolved", None) or row.prompt_original or ""
            from app.odoo_snapshot import _SNAPSHOT

            snap_token = set_snapshot(snap)
            mode_token = _CONN_WRITE_MODE.set(str(getattr(conn, "write_mode", "") or ""))
            try:
                fresh = _attach_diagnosis(prompt_now, resolved, assess_intent(prompt_now, resolved_answers=resolved))
            finally:
                _CONN_WRITE_MODE.reset(mode_token)
                _SNAPSHOT.reset(snap_token)
            update_session(db, row, resolved_answers=resolved, pending_clarification=fresh,
                           status="clarifying" if fresh else "ready")
            # The refreshed design can need one more app (e.g. Automation for its reminders).
            step = install_step(_session_design(resolved), snap, _session_plans(resolved, snap))
            if step:
                step = mark_read_only(step, conn)
    pending = session_to_dict(row).get("pending_clarification")
    if isinstance(pending, dict):
        pending = dict(pending)
        if step:
            pending["install_step"] = step
        else:
            pending.pop("install_step", None)
        update_session(db, row, pending_clarification=pending)
    out = session_to_dict(row)
    out["clarification"] = out.get("pending_clarification")
    out["install_step"] = step
    out["installed"] = installed
    out["install_errors"] = failed
    return out


@router.post("/{session_id}/stock-app")
def stock_app_decision_route(
    session_id: str,
    body: StockAppDecisionIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Answer the install confirm step, then continue or stop the same request.

    ``install`` runs the change-set op ``module.install``, re-reads the schema,
    and resumes this session (diagnosis or ready). ``decline`` stops it.
    Errors carry one sentence in ``detail.message``; no traceback.
    """
    row = get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    pending = session_to_dict(row).get("pending_clarification")
    if not isinstance(pending, dict) or pending.get("kind") != STOCK_APP_CLARIFICATION_KIND:
        raise HTTPException(
            status_code=409,
            detail={"message": "No app install is waiting on this request."},
        )
    proposal = pending.get("stock_app") if isinstance(pending.get("stock_app"), dict) else {}
    label = str(proposal.get("app_label") or "The app")

    if body.decision != INSTALL_DECISION or not proposal.get("installable"):
        message = declined_message(proposal)
        append_turn(
            db,
            row,
            role="user",
            kind="stock_app_decline",
            content=message,
            metadata={"module": proposal.get("module")},
        )
        update_session(db, row, status="stopped", pending_clarification=None)
        out = session_to_dict(row)
        out["stopped"] = True
        out["message"] = message
        out["clarification"] = None
        return out

    from app.odoo_service import get_connection_or_404

    try:
        conn = get_connection_or_404(db, row.connection_id) if row.connection_id else None
    except LookupError:
        conn = None
    if conn is None:
        raise HTTPException(
            status_code=409,
            detail={"message": f"{label} was not installed because this request has no connection."},
        )
    try:
        port = _open_stock_app_port(conn)
    except Exception as exc:  # noqa: BLE001 — unreachable Odoo is one sentence
        raise HTTPException(
            status_code=502,
            detail={"message": f"{label} was not installed because Odoo could not be reached."},
        ) from exc

    outcome = install_stock_app(port, proposal)
    if not outcome.ok:
        append_turn(
            db,
            row,
            role="system",
            kind="stock_app_install_failed",
            content=outcome.message,
            metadata={"module": outcome.module},
        )
        raise HTTPException(status_code=502, detail={"message": outcome.message})

    clear_snapshot_cache()
    model = str(proposal.get("model") or "")
    noun = str(proposal.get("noun") or "records")
    try:
        facts = read_install_facts(port, model, outcome.module)
    except Exception:  # noqa: BLE001
        facts = None
    if facts is None or not facts.model_present:
        raise HTTPException(
            status_code=502,
            detail={
                "message": f"{label} was installed, but {noun} are still missing on this database."
            },
        )

    prompt = row.prompt_resolved or row.prompt_original
    packet = _reread_schema_after_install(conn, port, prompt=prompt, model=model)
    append_turn(
        db,
        row,
        role="system",
        kind="stock_app_installed",
        content=outcome.message,
        metadata={"module": outcome.module, "module_id": outcome.module_id},
    )

    try:
        resolved = json.loads(row.resolved_answers_json or "{}")
    except json.JSONDecodeError:
        resolved = {}
    if not isinstance(resolved, dict):
        resolved = {}
    packet_token = set_schema_packet(packet)
    try:
        assessment, clarification = _session_next_step(prompt, resolved)
    finally:
        reset_schema_packet(packet_token)
    status = "clarifying" if clarification else "ready"
    update_session(
        db,
        row,
        status=status,
        resolved_answers=resolved,
        pending_clarification=clarification,
        prompt_resolved=prompt if clarification else _prompt_with_llm(prompt, assessment),
    )
    if clarification:
        append_turn(
            db,
            row,
            role="assistant",
            kind="clarify",
            content=str(clarification.get("question") or ""),
            metadata={"clarification": clarification},
        )
    out = session_to_dict(row)
    out["assessment"] = _assessment_payload(assessment, extra={"clear": status == "ready"})
    out["clarification"] = clarification
    if clarification and clarification.get("understanding"):
        out["understanding"] = clarification.get("understanding")
    out["installed"] = {
        "module": outcome.module,
        "app_label": label,
        "message": outcome.message,
        "warnings": list(outcome.warnings),
    }
    out["schema_reread"] = {
        "models": sorted(packet.models) if packet is not None else [],
        "host_model": model,
    }
    return out


def _grounded_refine_reply(
    reply: str,
    *,
    schema_packet: SchemaPacket | None,
    patch_summary: str,
    highlighted_field_ids: list[str],
) -> str:
    """Keep the display reply only if every technical name is in the packet or the patch.

    Otherwise (or when empty) return the admitted patch summary. Side effects: none.
    """
    fallback = patch_summary or "Updated."
    allowed = set(technical_names(patch_summary))
    for ref in highlighted_field_ids:
        model, _, field = str(ref).rpartition(".")
        allowed.update(name for name in (str(ref), model, field) if name)
    if not reply.strip() or unknown_technical_names(reply, schema_packet, allowed=allowed):
        return fallback
    return reply


@router.post("/{session_id}/refine")
def refine_session_route(
    session_id: str,
    body: RefineIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        artifact = json.loads(row.artifact_json or "{}")
    except json.JSONDecodeError:
        artifact = {}
    if not isinstance(artifact, dict) or not artifact.get("models"):
        raise HTTPException(status_code=409, detail="No draft artifact to refine — finish generation first")

    log_session_metrics(db, row.id, refine_attempts=1)
    append_turn(
        db,
        row,
        role="user",
        kind="refine",
        content=body.instruction.strip(),
    )

    provider = get_llm_provider_for_tier("refine") or get_llm_provider_for_tier("fast")
    packet = None
    packet_token = None
    if row.connection_id:
        try:
            from app.odoo_service import get_connection_or_404

            conn = get_connection_or_404(db, row.connection_id)
            packet = _studio_schema_packet(
                conn,
                prompt=row.prompt_resolved or row.prompt_original or body.instruction,
            )
        except Exception:  # noqa: BLE001
            packet = None
    packet_token = set_schema_packet(packet)
    try:
        result = apply_refinement(
            artifact,
            body.instruction.strip(),
            prompt=row.prompt_resolved or row.prompt_original,
            provider=provider,
            schema_packet=packet,
        )
    finally:
        if packet_token is not None:
            reset_schema_packet(packet_token)
    if not result.get("ok"):
        if result.get("needs_clarification"):
            update_session(
                db,
                row,
                pending_clarification=result["needs_clarification"],
                status="clarifying",
            )
            return {
                "ok": False,
                "session": session_to_dict(row),
                "needs_clarification": result["needs_clarification"],
            }
        err = str(result.get("error") or "Refinement failed")
        append_turn(
            db,
            row,
            role="assistant",
            kind="refine_result",
            content=err,
        )
        return {
            "ok": False,
            "session": session_to_dict(row),
            "error": err,
            "patch_summary": "",
            "highlighted_field_ids": [],
        }

    draft = result["draft"]
    ahash = artifact_hash(draft)
    update_session(
        db,
        row,
        artifact=draft,
        artifact_hash=ahash,
        status="review",
        pending_clarification=None,
    )
    log_session_metrics(db, row.id, refine_landed=1)
    append_turn(
        db,
        row,
        role="assistant",
        kind="refine_result",
        content=str(result.get("patch_summary") or "Updated."),
        metadata={"highlighted_field_ids": result.get("highlighted_field_ids") or []},
    )

    if provider:
        try:
            reply = provider.generate_text(
                prepend_schema_packet(
                    f"User asked: {body.instruction}\nPatch applied: {result.get('patch_summary')}\n"
                    "Reply in one short sentence confirming the change. Name only models and "
                    "fields from the patch or the live schema packet.",
                    packet,
                ),
                system="You are a concise app builder assistant.",
                timeout_s=30.0,
            )
        except Exception:  # noqa: BLE001
            reply = str(result.get("patch_summary") or "Updated.")
        reply = _grounded_refine_reply(
            str(reply or ""),
            schema_packet=packet,
            patch_summary=str(result.get("patch_summary") or ""),
            highlighted_field_ids=list(result.get("highlighted_field_ids") or []),
        )
    else:
        reply = str(result.get("patch_summary") or "Updated.")

    return {
        "ok": True,
        "session": session_to_dict(row),
        "patch_summary": result.get("patch_summary"),
        "highlighted_field_ids": result.get("highlighted_field_ids") or [],
        "validators": result.get("validators") or {},
        "assistant_reply": reply,
    }


@router.post("/{session_id}/reverify-authoring")
def reverify_authoring_route(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Re-check the custom-code authoring gate after installing a stock host app. No LLM."""
    from app.ai_option_a_reverify import run_option_a_reverify

    return run_option_a_reverify(db, session_id=session_id)


@router.post("/{session_id}/option-a-batch")
def start_option_a_batch_route(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """App design Python pieces -> ONE Custom-code module session (author now).

    The child session then follows the existing lane: sandbox prove, then a single
    you publish click (nothing else to configure). Online: refused honestly.
    Idempotent: a second call returns the same child session.
    """
    from app.ai_option_a_author import author_option_a_module

    row = get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        artifact = json.loads(row.artifact_json or "{}")
    except json.JSONDecodeError:
        artifact = {}
    batch = artifact.get("_option_a_batch") if isinstance(artifact, dict) else None
    if not isinstance(batch, dict) or not isinstance(batch.get("draft"), dict):
        raise HTTPException(status_code=409, detail="This app has no Python pieces to batch.")
    if batch.get("online_blocked"):
        raise HTTPException(
            status_code=409,
            detail={"message": batch.get("note") or "Custom Python cannot install on Odoo Online.",
                    "status": "blocked_online"},
        )
    child_id = str(batch.get("session_id") or "")
    if child_id and get_session(db, child_id) is not None:
        return {"session_id": child_id, "pieces": batch.get("pieces") or [], "promote": batch.get("promote")}
    companion = dict(batch["draft"])
    prompt = str(companion.get("_user_prompt") or "")
    author_option_a_module(companion, prompt=prompt)
    child = create_session(
        db, connection_id=row.connection_id, feature=row.feature, prompt=prompt, status="review"
    )
    update_session(db, child, artifact=companion, artifact_hash=artifact_hash(companion))
    batch["session_id"] = child.id
    batch["status"] = "authored"
    artifact["_option_a_batch"] = batch
    update_session(db, row, artifact=artifact, artifact_hash=artifact_hash(artifact))
    return {"session_id": child.id, "pieces": batch.get("pieces") or [], "promote": batch.get("promote")}


@router.post("/{session_id}/stamp-option-a-promote")
def stamp_option_a_promote_route(
    session_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """After Promote: stamp Open-in-Odoo onto the inherit host (Quotations, not Discuss).

    Resolves the stock window action. If the existing form is missing, returns
    ``host_install`` so App Studio can offer Install Sales (etc.). Persist so
    refresh keeps Open Quotation working. Publishing stays a step you confirm.
    """
    from app.ai_generation_engine import is_option_a_authored_draft
    from app.ai_option_a_gate import evaluate_authoring_gate
    from app.ai_option_a_policy import extract_disclosure_ir
    from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
    from app.spec_apply_ui import inherit_host_model_from_spec, resolve_inherit_open_target

    row = get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not row.connection_id:
        raise HTTPException(status_code=422, detail="Session has no connection")

    try:
        artifact = json.loads(row.artifact_json or "{}")
    except json.JSONDecodeError:
        artifact = {}
    if not isinstance(artifact, dict) or not is_option_a_authored_draft(artifact):
        raise HTTPException(
            status_code=409,
            detail="Stamp is only for AI-authored custom-code sessions after you publish.",
        )

    try:
        conn = get_connection_or_404(db, row.connection_id)
        client = client_from_connection(conn)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    major = 19
    try:
        ver = str(getattr(conn, "server_version", None) or "19")
        major = int(ver.split(".", 1)[0]) if ver[0].isdigit() else 19
    except Exception:  # noqa: BLE001
        major = 19

    gate = evaluate_authoring_gate(artifact, client=client, odoo_major=int(major))
    host, action_id = resolve_inherit_open_target(client, artifact)
    if not host:
        host = inherit_host_model_from_spec(artifact)
    inherit_models = list((extract_disclosure_ir(artifact) or {}).get("inherit_models") or [])
    host_install = list(gate.get("host_install") or [])

    apply_meta = {
        "root_menu_id": None,
        "open_action_id": int(action_id) if action_id else None,
        "host_model": host,
        "applied": True,
        "via": "option_a_promote",
    }
    artifact["_studio_apply"] = apply_meta
    _clear_conn_snapshot(conn)
    ahash = artifact_hash(artifact)
    update_session(db, row, artifact=artifact, artifact_hash=ahash, status="review")
    out = session_to_dict(row)
    out["host_model"] = host
    out["open_action_id"] = apply_meta["open_action_id"]
    out["host_install"] = host_install
    out["inherit_models"] = inherit_models
    out["authoring_status"] = gate.get("status")
    if host_install:
        labels = ", ".join(str(o.get("label") or o.get("module")) for o in host_install)
        out["message"] = (
            f"Promoted module is on this connection, but {labels} is still missing. "
            f"Install {labels} so Open Quotation / the host form works — that is not "
            "Live Install of this zip. A complete draft is not the same as certified. Publishing stays a step you confirm."
        )
    elif host and action_id:
        out["message"] = (
            f"Open in Odoo uses the stock {host} action (Sales → Quotations for "
            "sale.order) — not Discuss, not a new Apps tile."
        )
    elif host:
        out["message"] = (
            f"Host {host} is on this connection but no window action was resolved. "
            "Open Sales → Quotations manually; Markup % is on the form."
        )
    else:
        out["message"] = "Promote stamp saved; no inherit host on the draft."
    return out


@router.post("/{session_id}/sync-job")
def sync_job_route(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Pull completed draft job result into session artifact."""
    from app.jobs import get_job

    row = get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not row.job_id:
        return session_to_dict(row)

    job = get_job(db, row.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == "failed":
        update_session(db, row, status="failed")
        out = session_to_dict(row)
        out["job_error"] = job.error
        return out

    if job.status != "succeeded":
        return session_to_dict(row)

    try:
        payload = json.loads(job.result_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    draft = payload.get("draft") if isinstance(payload, dict) else {}
    if not isinstance(draft, dict):
        draft = {}

    if not draft:
        update_session(db, row, status="failed")
        out = session_to_dict(row)
        out["job_error"] = "Draft job succeeded but returned an empty artifact"
        return out

    ahash = artifact_hash(draft)
    update_session(
        db,
        row,
        artifact=draft,
        artifact_hash=ahash,
        status="review",
    )
    return session_to_dict(row)


@router.post("/{session_id}/apply")
def apply_session_route(
    session_id: str,
    body: StudioApplyIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Apply session artifact to the linked Odoo connection (same path as wizard app plan apply)."""
    from app.ai_apply_readiness import prepare_spec_for_live_apply
    from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
    from app.protected_enforcement import manifest_for_connection, scrub_spec_for_protected_apply
    from app.snapshots import ConfirmationRequired, require_advanced_confirmation
    from app.schemas import ModuleSpecApplyOut
    from app.spec_apply_ui import apply_module_spec_ui, inherit_host_model_from_spec

    row = get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not row.connection_id:
        raise HTTPException(status_code=422, detail="Session has no connection — pick a connection first")

    try:
        artifact = json.loads(row.artifact_json or "{}")
    except json.JSONDecodeError:
        artifact = {}
    if not isinstance(artifact, dict) or not artifact.get("models"):
        raise HTTPException(status_code=409, detail="No draft artifact to apply — finish generation first")
    try:
        _resolved_gate = json.loads(row.resolved_answers_json or "{}")
    except json.JSONDecodeError:
        _resolved_gate = {}
    _install_gate(db, row, _resolved_gate if isinstance(_resolved_gate, dict) else {})

    from app.ai_generation_engine import is_gold_option_a_draft, is_option_a_authored_draft

    if is_gold_option_a_draft(artifact):
        raise HTTPException(
            status_code=409,
            detail=(
                "This is custom-code gold (Python + cron). Live Install cannot land CBN rates "
                "or an ir.cron. Download the module zip, sandbox-install, then in Odoo: "
                "Accounting → Settings → Automatic Currency Rates → Central Bank of Nigeria "
                "→ Update now. Check USD/GBP/EUR on res.currency.rate. Publishing stays a step you confirm."
            ),
        )
    if is_option_a_authored_draft(artifact):
        raise HTTPException(
            status_code=409,
            detail=(
                "This is an LLM-authored Custom-code module. Live Install cannot land Python/QWeb. "
                "Wait for the authoring gate, download the zip, sandbox-prove, then publish. "
                "Publishing stays a step you confirm."
            ),
        )

    try:
        conn = get_connection_or_404(db, row.connection_id)
        client = client_from_connection(conn)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning="Apply writes models, fields, views, menus, and smart buttons on this live Odoo.",
            risks=[
                "Creates ir.model / fields / views / menus via RPC",
                "May rewrite primary form arches for custom x_* models",
                "Try a test copy before production",
            ],
        )
    except ConfirmationRequired as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "requires_confirmation": True,
                "confirm_phrase": "I understand the risks",
                "warning": exc.warning,
                "risks": exc.risks,
            },
        ) from exc

    manifest = manifest_for_connection(conn)
    prompt = (row.prompt_resolved or row.prompt_original or "").strip()
    if prompt and not artifact.get("_user_prompt"):
        artifact["_user_prompt"] = prompt
    spec_prepared, prep_notes = prepare_spec_for_live_apply(artifact)
    spec_clean, pcm_skips = scrub_spec_for_protected_apply(spec_prepared, manifest)
    if prompt:
        spec_clean["_user_prompt"] = spec_clean.get("_user_prompt") or prompt
    try:
        result = apply_module_spec_ui(client, spec_clean)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    skipped = list(result.skipped) + pcm_skips
    warnings = list(result.warnings)
    if prep_notes:
        warnings.append(f"Live prep: {len(prep_notes)} readiness adjustment(s)")

    apply_meta = {
        "root_menu_id": result.root_menu_id,
        "open_action_id": result.open_action_id,
        "host_model": getattr(result, "open_model", None)
        or inherit_host_model_from_spec(artifact),
        "applied": True,
        "menus_created": result.menus_created,
        "message": result.message,
    }
    if spec_clean.get("views") is not None:
        artifact["views"] = spec_clean["views"]
    if spec_clean.get("_form_slots") is not None:
        artifact["_form_slots"] = spec_clean["_form_slots"]
    artifact["_studio_apply"] = apply_meta
    _clear_conn_snapshot(conn)
    update_session(db, row, artifact=artifact, status="delivered")
    append_turn(
        db,
        row,
        role="system",
        kind="apply",
        content=result.message,
        metadata={
            "models_created": result.models_created,
            **apply_meta,
        },
    )

    out = ModuleSpecApplyOut(
        ok=True,
        models_created=result.models_created,
        fields_created=result.fields_created,
        views_created=result.views_created,
        views_updated=result.views_updated,
        menus_created=result.menus_created,
        smart_buttons=result.smart_buttons,
        automations_created=result.automations_created,
        root_menu_id=result.root_menu_id,
        open_action_id=result.open_action_id,
        skipped=skipped,
        warnings=warnings,
        message=result.message,
    )
    payload = out.model_dump()
    payload["session"] = session_to_dict(row)
    return payload
