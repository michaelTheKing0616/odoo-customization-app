"""Conversational App Studio — sessions, clarify, generate, refine."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai_conversation.clarify import apply_clarification_answer, build_clarification
from app.ai_conversation.intent_gate import (
    assess_intent,
    merge_resolved_prompt,
    session_already_admitted,
    should_block_generation,
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
from app.ai_conversation.session_store import (
    append_turn,
    create_session,
    get_session,
    session_to_dict,
    update_session,
)
from app.db import get_db
from app.llm_provider import get_llm_provider, get_llm_provider_for_tier

router = APIRouter(prefix="/ai/sessions", tags=["ai-studio"])


class CreateSessionIn(BaseModel):
    connection_id: str | None = None
    prompt: str = Field(min_length=10)
    feature: str = "studio"

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
        extra.append(f"Custom residual: {blob['residual']}.")
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
    understanding = load_understanding(resolved) or build_understanding(prompt)
    dump_understanding(resolved, understanding)
    return diagnosis_clarification(understanding)


@router.post("")
def create_session_route(body: CreateSessionIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    prompt = body.prompt.strip()
    connection_id = body.connection_id
    if connection_id:
        from app.odoo_service import get_connection_or_404

        try:
            get_connection_or_404(db, connection_id)
        except LookupError as exc:
            raise HTTPException(
                status_code=404,
                detail="Connection not found — open App Studio from a connection page, then Start new app.",
            ) from exc

    resolved: dict[str, str] = {}
    assessment = assess_intent(prompt, resolved_answers=resolved)
    provider, fallback = _provider_meta()
    resolved.update(_resolved_from_llm(assessment))

    clarification = None
    if should_block_generation(assessment):
        clarification = build_clarification(assessment, prompt=prompt)
    if clarification is None:
        clarification = _attach_diagnosis(prompt, resolved, assessment)

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
    row = get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        resolved = json.loads(row.resolved_answers_json or "{}")
    except json.JSONDecodeError:
        resolved = {}
    if not isinstance(resolved, dict):
        resolved = {}

    prompt_resolved, resolved = apply_clarification_answer(
        row.prompt_original,
        merge_key=body.merge_key,
        answer_id=body.answer_id,
        answer_text=body.answer_text,
        resolved_answers=resolved,
        understanding=body.understanding,
    )
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
        )
        out = session_to_dict(row)
        out["assessment"] = _assessment_payload(assessment)
        out["rejected"] = True
        out["clarification"] = None
        return out

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

    understanding = load_understanding(resolved) or parse_locked_diagnosis(prompt)
    host_override = (understanding.host_model if understanding else None) or None

    from app.ai_draft_jobs import build_draft_job_kwargs, enqueue_draft_job
    from app.odoo_service import get_connection_or_404
    from app.protected_enforcement import manifest_from_json
    from app.routers.ai import _load_reuse_catalog
    from app.schemas import AiDraftModuleBody

    try:
        connection_id = row.connection_id
        draft_body = AiDraftModuleBody(prompt=prompt, connection_id=connection_id)
        available, installed, reuse_views, reuse_actions, stock_catalog = _load_reuse_catalog(
            db, draft_body
        )
        protected_manifest = None
        odoo_version = None
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
                pass

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
    return out


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
    result = apply_refinement(
        artifact,
        body.instruction.strip(),
        prompt=row.prompt_resolved or row.prompt_original,
        provider=provider,
    )
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
                f"User asked: {body.instruction}\nPatch applied: {result.get('patch_summary')}\n"
                "Reply in one short sentence confirming the change.",
                system="You are a concise app builder assistant.",
                timeout_s=30.0,
            )
        except Exception:  # noqa: BLE001
            reply = str(result.get("patch_summary") or "Updated.")
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
    """Re-check the Option A authoring gate after installing a stock host app. No LLM."""
    from app.ai_option_a_reverify import run_option_a_reverify

    return run_option_a_reverify(db, session_id=session_id)


@router.post("/{session_id}/stamp-option-a-promote")
def stamp_option_a_promote_route(
    session_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """After Promote: stamp Open-in-Odoo onto the inherit host (Quotations, not Discuss).

    Resolves the stock window action. If the host model is missing, returns
    ``host_install`` so App Studio can offer Install Sales (etc.). Persist so
    refresh keeps Open Quotation working. Promote stays human.
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
            detail="Stamp is only for LLM-authored Option A sessions after Promote.",
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
            "Live Install of this zip. Completeness ≠ Cert. Promote stays human."
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
    """Apply session artifact to the linked Odoo connection (same path as wizard ModuleSpec apply)."""
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

    from app.ai_generation_engine import is_gold_option_a_draft, is_option_a_authored_draft

    if is_gold_option_a_draft(artifact):
        raise HTTPException(
            status_code=409,
            detail=(
                "This is Option A gold (Python + cron). Live Install cannot land CBN rates "
                "or an ir.cron. Download the module zip, sandbox-install, then in Odoo: "
                "Accounting → Settings → Automatic Currency Rates → Central Bank of Nigeria "
                "→ Update now. Check USD/GBP/EUR on res.currency.rate. Promote stays human."
            ),
        )
    if is_option_a_authored_draft(artifact):
        raise HTTPException(
            status_code=409,
            detail=(
                "This is an LLM-authored Option A module. Live Install cannot land Python/QWeb. "
                "Wait for the authoring gate, download the zip, sandbox-prove, then Promote. "
                "Promote stays human."
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
                "Prefer sandbox before production",
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
