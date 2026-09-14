"""Apply ModuleSpec JSON + Code→ModuleSpec import."""

from __future__ import annotations

import copy
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.module_import import import_module_archive
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import (
    ModuleSpecApplyBody,
    ModuleSpecApplyOut,
    ModuleSpecImportJsonBody,
    ModuleSpecImportOut,
    ModuleSpecValidateLiveBody,
    ModuleSpecWalkthroughBody,
    ModuleSpecWalkthroughOut,
    ValidateLiveItemOut,
    ValidateLiveOut,
)
from app.spec_validate_live import validate_module_spec_live
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)
from app.protected_enforcement import manifest_for_connection, scrub_spec_for_protected_apply
from app.ai_apply_readiness import prepare_spec_for_live_apply
from app.spec_apply_ui import apply_module_spec_ui
from app.mutation_lock_dep import require_connection_mutation_lock
from app.custom_code_authoring import lint_custom_code_blocks, model_class_skeleton
from app.module_spec_codec import export_draft_module_zip
from app.workspace_auth import WorkspaceAuth, require_app_auth
from app.code_studio_gating import assert_code_studio_entitlement, assert_developer_role
from app.mutation_lock_dep import require_connection_mutation_lock

router = APIRouter(
    prefix="/connections/{connection_id}/module-spec",
    tags=["module-spec"],
)

# Parse-only import (no live Odoo writes)
import_router = APIRouter(prefix="/module-spec", tags=["module-spec"])


def _confirm_http(exc: ConfirmationRequired) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "requires_confirmation": True,
            "confirm_phrase": CONFIRM_PHRASE,
            "warning": exc.warning,
            "risks": exc.risks,
        },
    )


@import_router.post("/import", response_model=ModuleSpecImportOut)
async def import_module_spec_file(
    file: UploadFile = File(..., description="Odoo module zip, .meta.json, .py, or .xml"),
) -> ModuleSpecImportOut:
    """Parse third-party / own module code into ModuleSpec (no Odoo writes)."""
    if not file.filename:
        raise HTTPException(status_code=422, detail="filename required")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="empty file")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large (max 25MB)")
    try:
        result = import_module_archive(raw, filename=file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}") from exc

    payload = result.as_dict()
    return ModuleSpecImportOut(
        ok=True,
        spec=payload,
        warnings=result.warnings,
        unmapped=result.unmapped,
        custom_code_blocks=list(payload.get("custom_code_blocks") or []),
        source=result.source,
    )


@import_router.post("/import-json", response_model=ModuleSpecImportOut)
def import_module_spec_json(body: ModuleSpecImportJsonBody) -> ModuleSpecImportOut:
    """Accept pasted ModuleSpec JSON — optional apply-readiness prep, no Odoo writes."""
    if not isinstance(body.spec, dict) or not body.spec.get("models"):
        raise HTTPException(
            status_code=422,
            detail="spec.models must be a non-empty list",
        )
    spec = copy.deepcopy(body.spec)
    warnings: list[str] = []
    if body.prepare:
        spec, prep_notes = prepare_spec_for_live_apply(spec)
        warnings.extend(prep_notes)
    blocks = list(spec.get("custom_code_blocks") or [])
    return ModuleSpecImportOut(
        ok=True,
        spec=spec,
        warnings=warnings,
        unmapped=[],
        custom_code_blocks=blocks,
        source="json_paste",
        note=(
            "JSON loaded into ModuleSpec — click Apply to Odoo on a connection "
            "or open the visual editor."
        ),
    )


@router.post("/validate-live", response_model=ValidateLiveOut)
def validate_live_module_spec(
    connection_id: str,
    body: ModuleSpecValidateLiveBody,
    db: Session = Depends(get_db),
) -> ValidateLiveOut:
    """Read-only pre-apply checks against the live Odoo instance."""
    if not isinstance(body.spec, dict) or not body.spec.get("models"):
        raise HTTPException(status_code=422, detail="spec.models must be a non-empty list")
    try:
        conn = get_connection_or_404(db, connection_id)
        client = client_from_connection(conn)
        result = validate_module_spec_live(client, body.spec)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ValidateLiveOut(
        ok=result.ok,
        items=[
            ValidateLiveItemOut(
                item_id=i.item_id,
                category=i.category,
                status=i.status,
                message=i.message,
            )
            for i in result.items
        ],
        fail_count=result.fail_count,
        warn_count=result.warn_count,
        message=result.message,
    )


class LintBlocksBody(BaseModel):
    spec: dict


class ExportSandboxBody(BaseModel):
    spec: dict
    async_job: bool = True
    odoo_major: int | None = None


class EliteAutopilotBody(BaseModel):
    spec: dict
    odoo_major: int | None = None
    skip_gate: bool = False


class EliteGateBody(BaseModel):
    spec: dict


class OptionAProveBody(BaseModel):
    spec: dict
    odoo_major: int | None = None
    structural_only: bool = False
    auto_repair: bool = True


class OptionARepairFeedbackBody(BaseModel):
    spec: dict
    error_text: str = ""
    operator_notes: str = ""
    retry_sandbox: bool = False
    odoo_major: int | None = None


class ConstrainedRepairBody(BaseModel):
    spec: dict
    patches: list[dict] = []  # [{source_file, content}]
    begin_only: bool = False


class SkeletonBody(BaseModel):
    spec: dict
    model: str


@router.post("/lint-blocks")
def lint_blocks_route(
    connection_id: str,
    body: LintBlocksBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    get_connection_or_404(db, connection_id)
    return lint_custom_code_blocks(body.spec)


@router.post("/export-zip")
def export_zip_from_draft(
    connection_id: str,
    body: ExportSandboxBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    """Downloadable module zip after the structural gate — no Docker."""
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    conn = get_connection_or_404(db, connection_id)
    import base64

    from app.ai_option_a_gate import raise_if_authoring_blocked
    from app.ai_structural_zip_gate import structural_zip_gate
    from app.sandbox import sandbox_major_for_connection

    raise_if_authoring_blocked(body.spec if isinstance(body.spec, dict) else {})
    major = sandbox_major_for_connection(
        body.odoo_major if body.odoo_major is not None else conn.server_version
    )
    try:
        zip_bytes = export_draft_module_zip(body.spec, odoo_major=major)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "export_failed": True,
                "message": f"Module zip could not be built: {exc}",
            },
        ) from exc
    gate = structural_zip_gate(zip_bytes)
    if not gate.get("ok"):
        raise HTTPException(
            status_code=422,
            detail={
                "structural_zip_failed": True,
                "findings": gate.get("findings") or [],
            },
        )
    tech = str(body.spec.get("technical_name") or "custom_module")
    return {
        "ok": True,
        "module": tech,
        "zip_base64": base64.b64encode(zip_bytes).decode("ascii"),
        "structural_zip": gate,
        "odoo_major": major,
    }


@router.post("/skeleton")
def model_skeleton_route(
    connection_id: str,
    body: SkeletonBody,
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    assert_developer_role(auth)
    return {"model": body.model, "code": model_class_skeleton(body.spec, body.model)}


@router.post("/export-sandbox")
def export_sandbox_from_draft(
    connection_id: str,
    body: ExportSandboxBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    """DEV-2 — export draft ModuleSpec zip and run sandbox gate."""
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    conn = get_connection_or_404(db, connection_id)
    from app.ai_option_a_gate import raise_if_authoring_blocked

    raise_if_authoring_blocked(body.spec if isinstance(body.spec, dict) else {})
    lint = lint_custom_code_blocks(body.spec)
    if not lint.get("ok"):
        raise HTTPException(status_code=422, detail={"lint_failed": True, **lint})
    import base64

    from app.jobs import create_job, enqueue
    from app.sandbox import sandbox_major_for_connection, run_sandbox_install
    from app.promote import record_sandbox_validation, sha256_bytes

    major = sandbox_major_for_connection(
        body.odoo_major if body.odoo_major is not None else conn.server_version
    )
    try:
        zip_bytes = export_draft_module_zip(body.spec, odoo_major=major)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "export_failed": True,
                "message": f"Module zip could not be built: {exc}",
            },
        ) from exc
    zip_b64 = base64.b64encode(zip_bytes).decode("ascii")
    tech = str(body.spec.get("technical_name") or "custom_module")

    if not body.async_job:
        result = run_sandbox_install(
            zip_bytes=zip_bytes,
            module_name=tech,
            odoo_major=major,
            extra_modules=list(body.spec.get("depends") or []),
        )
        spec = copy.deepcopy(body.spec) if isinstance(body.spec, dict) else {}
        from app.ai_failure_ir import failures_from_sandbox_log, stamp_failures
        from app.ai_repair_loop import begin_repair_attempt, lock_certified_artifacts, repair_guidance
        from app.ai_static_odoo import stamp_static_odoo
        from app.ai_draft_scorecard import attach_scorecard

        stamp_static_odoo(spec)
        if not result.ok:
            fails = failures_from_sandbox_log(
                result.log_tail or "", ok=False, message=result.message or ""
            )
            stamp_failures(spec, fails)
            repair_meta = begin_repair_attempt(spec, fails)
            spec["_sandbox_install"] = {"ok": False, "message": result.message}
            attach_scorecard(spec, user_prompt=str(spec.get("_user_prompt") or ""))
            return {
                "ok": False,
                "lint": lint,
                "draft": spec,
                "failures": spec.get("_failures"),
                "repair": repair_meta,
                "repair_hints": repair_guidance(fails),
                "certification": spec.get("_certification"),
                "sandbox": {
                    "ok": result.ok,
                    "module": result.module,
                    "message": result.message,
                    "log_tail": result.log_tail,
                },
            }
        lock_certified_artifacts(spec, run_id=str(result.module or tech))
        spec["_sandbox_install"] = {
            "ok": True,
            "message": result.message,
            "module": result.module,
        }
        attach_scorecard(spec, user_prompt=str(spec.get("_user_prompt") or ""))
        validation_row = record_sandbox_validation(
            db,
            connection_id=connection_id,
            module_name=tech,
            zip_bytes=zip_bytes,
        )
        return {
            "ok": True,
            "lint": lint,
            "validation_id": validation_row.id,
            "zip_sha256": validation_row.zip_sha256,
            "zip_base64": zip_b64,
            "draft": spec,
            "certification": spec.get("_certification"),
            "certified_artifacts": spec.get("_certified_artifacts"),
            "sandbox": {
                "ok": result.ok,
                "module": result.module,
                "message": result.message,
                "log_tail": result.log_tail,
            },
        }

    job = create_job(db, kind="sandbox", connection_id=connection_id)

    def _work() -> dict:
        result = run_sandbox_install(
            zip_bytes=zip_bytes,
            module_name=tech,
            odoo_major=major,
            job_id=job.id,
            extra_modules=list(body.spec.get("depends") or []),
        )
        from app.db import SessionLocal

        wdb = SessionLocal()
        try:
            validation_id = None
            if result.ok:
                validation_row = record_sandbox_validation(
                    wdb,
                    connection_id=connection_id,
                    module_name=tech,
                    zip_bytes=zip_bytes,
                )
                validation_id = validation_row.id
        finally:
            wdb.close()
        return {
            "ok": result.ok,
            "validation_id": validation_id,
            "zip_base64": zip_b64,
            "sandbox": {
                "ok": result.ok,
                "module": result.module,
                "message": result.message,
                "log_tail": result.log_tail,
            },
            "lint": lint,
        }

    enqueue(job.id, _work)
    return {"ok": True, "job_id": job.id, "lint": lint, "message": "Sandbox job queued"}


@router.get("/gold-inspect")
def gold_inspect(
    connection_id: str,
    gold_id: str = Query(..., min_length=1, max_length=64),
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    """Whether this connection can show CBN/Accounting (or POS) after gold Promote."""
    conn = get_connection_or_404(db, connection_id)
    try:
        client = client_from_connection(conn)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    from app.ai_gold_inspect import probe_gold_inspect

    return probe_gold_inspect(client, gold_id=gold_id, base_url=conn.url)


@router.post("/option-a-prove")
def option_a_prove(
    connection_id: str,
    body: OptionAProveBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    """Sandbox-install Option A scaffolds and run surface smoke; restamp scorecard.

    ``structural_only`` skips Docker (CI / offline) — never lifts score to 10.0.
    Promote to another connection stays human even when ``go_live_ready``.
    """
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    conn = get_connection_or_404(db, connection_id)
    from app.ai_option_a_quality import (
        prove_option_a_in_sandbox,
        stamp_option_a_smoke,
        structural_option_a_smoke,
    )
    from app.sandbox import sandbox_major_for_connection

    spec = copy.deepcopy(body.spec) if isinstance(body.spec, dict) else {}
    from app.ai_option_a_gate import raise_if_authoring_blocked

    raise_if_authoring_blocked(spec)
    if body.structural_only:
        smoke = structural_option_a_smoke(spec)
        stamp_option_a_smoke(spec, {**smoke, "ok": False, "message": "structural_only"})
        return {
            "ok": False,
            "structural_only": True,
            "draft": spec,
            "smoke": spec.get("_option_a_smoke"),
            "score_0_10": (spec.get("_scorecard") or {}).get("score_0_10"),
            "go_live_ready": spec.get("_go_live_ready"),
            "grain_label": spec.get("grain_label"),
            "done_bar": spec.get("_done_bar"),
        }

    major = sandbox_major_for_connection(
        body.odoo_major if body.odoo_major is not None else conn.server_version
    )
    result = prove_option_a_in_sandbox(
        spec, odoo_major=major, auto_repair=body.auto_repair
    )
    from app.promote import stamp_option_a_promote_token

    result = stamp_option_a_promote_token(
        db, connection_id=connection_id, result=result
    )
    draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
    return {
        **result,
        "grain_label": draft.get("grain_label"),
        "done_bar": draft.get("_done_bar"),
        "certification": draft.get("_certification") or result.get("certification"),
        "failures": draft.get("_failures") or result.get("failures") or [],
        "feedback_repair": result.get("feedback_repair")
        or draft.get("_option_a_feedback_repair"),
    }


@router.post("/option-a-repair-feedback")
def option_a_repair_feedback(
    connection_id: str,
    body: OptionARepairFeedbackBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    """Patch LLM-authored Option A files from a sandbox Fault or operator notes.

    Optional ``retry_sandbox`` re-runs ephemeral install after a passing gate.
    Never Live Apply. Promote stays human.
    """
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    conn = get_connection_or_404(db, connection_id)
    spec = copy.deepcopy(body.spec) if isinstance(body.spec, dict) else {}
    from app.ai_option_a_feedback import repair_option_a_from_feedback
    from app.sandbox import sandbox_major_for_connection

    major = sandbox_major_for_connection(
        body.odoo_major if body.odoo_major is not None else conn.server_version
    )
    repair = repair_option_a_from_feedback(
        spec,
        error_text=body.error_text or "",
        operator_notes=body.operator_notes or "",
        odoo_major=int(major or 19),
    )
    out: dict = {
        "ok": bool(repair.get("ok")),
        "draft": spec,
        "feedback_repair": repair,
        "message": repair.get("message"),
        "certification": spec.get("_certification"),
        "failures": spec.get("_failures") or [],
    }
    if body.retry_sandbox and repair.get("applied") and repair.get("gate_status") == "pass":
        from app.ai_option_a_quality import prove_option_a_in_sandbox
        from app.promote import stamp_option_a_promote_token

        proved = prove_option_a_in_sandbox(
            spec, odoo_major=major, auto_repair=False
        )
        proved = stamp_option_a_promote_token(
            db, connection_id=connection_id, result=proved
        )
        draft = proved.get("draft") if isinstance(proved.get("draft"), dict) else spec
        return {
            **proved,
            "feedback_repair": draft.get("_option_a_feedback_repair") or repair,
            "grain_label": draft.get("grain_label"),
            "done_bar": draft.get("_done_bar"),
            "certification": draft.get("_certification") or proved.get("certification"),
            "failures": draft.get("_failures") or proved.get("failures") or [],
        }
    return out


@router.post("/constrained-repair")
def constrained_repair_route(
    connection_id: str,
    body: ConstrainedRepairBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    """Apply Failure-IR–scoped patches to custom_code_blocks only (no full regenerate)."""
    assert_developer_role(auth)
    assert_code_studio_entitlement(db, auth)
    get_connection_or_404(db, connection_id)
    from app.ai_draft_scorecard import attach_scorecard
    from app.ai_repair_loop import (
        apply_constrained_block_patch,
        begin_repair_attempt,
        repair_guidance,
    )

    spec = copy.deepcopy(body.spec) if isinstance(body.spec, dict) else {}
    failures = [f for f in (spec.get("_failures") or []) if isinstance(f, dict)]
    meta = begin_repair_attempt(spec, failures)
    if body.begin_only:
        return {
            "ok": bool(meta.get("ok")),
            "repair": meta,
            "repair_hints": repair_guidance(failures),
            "draft": spec,
        }
    if not meta.get("ok"):
        return {"ok": False, "repair": meta, "draft": spec}

    applied: list[dict] = []
    for patch in body.patches[:2]:
        if not isinstance(patch, dict):
            continue
        path = str(patch.get("source_file") or patch.get("file") or "")
        content = str(patch.get("content") or "")
        if not path:
            continue
        res = apply_constrained_block_patch(spec, source_file=path, new_content=content)
        applied.append(res)
    attach_scorecard(spec, user_prompt=str(spec.get("_user_prompt") or ""))
    return {
        "ok": all(a.get("ok") for a in applied) if applied else False,
        "repair": meta,
        "applied": applied,
        "draft": spec,
        "certification": spec.get("_certification"),
        "score_0_10": (spec.get("_scorecard") or {}).get("score_0_10"),
    }


@router.post("/elite-gate")
def elite_gate_check(
    connection_id: str,
    body: EliteGateBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
) -> dict:
    """Read-only ELITE scorecard + lint gate (no sandbox)."""
    get_connection_or_404(db, connection_id)
    from app.ai_elite import elite_promote_gate

    passed, reasons = elite_promote_gate(body.spec)
    sc = body.spec.get("_scorecard") if isinstance(body.spec.get("_scorecard"), dict) else {}
    return {
        "gate_passed": passed,
        "gate_reasons": reasons,
        "score_0_10": sc.get("score_0_10"),
        "dimensions": sc.get("dimensions"),
    }


@router.post("/elite-autopilot")
def elite_autopilot_route(
    connection_id: str,
    body: EliteAutopilotBody,
    db: Session = Depends(get_db),
    auth: WorkspaceAuth = Depends(require_app_auth),
    _lock: Annotated[None, Depends(require_connection_mutation_lock)] = None,
) -> dict:
    """ELITE-4 — scorecard-gated export → sandbox → validation_id for promote."""
    get_connection_or_404(db, connection_id)
    from app.ai_elite_promote import run_elite_autopilot

    try:
        return run_elite_autopilot(
            db,
            connection_id=connection_id,
            spec=body.spec,
            odoo_major=body.odoo_major,
            skip_gate=body.skip_gate,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/apply", response_model=ModuleSpecApplyOut)
def apply_module_spec(
    connection_id: str,
    body: ModuleSpecApplyBody,
    db: Session = Depends(get_db),
    _: Annotated[None, Depends(require_connection_mutation_lock)] = None,
) -> ModuleSpecApplyOut:
    """Generate UI from ModuleSpec JSON (models, fields, views, menus, smart buttons)."""
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                "Generate UI from JSON creates models, fields, views, menus, and "
                "safe automations on the live Odoo database. Prefer a sandbox connection first."
            ),
            risks=[
                "Creates ir.model / ir.model.fields / ir.ui.view / ir.ui.menu",
                "May rewrite primary form arches for custom x_* models (statusbars)",
                "Smart buttons use inherit views (stock forms like Contacts stay intact)",
                "Safe automations (update_field / related_write / activity) are created live",
                "Does not fully roll back if a later step fails",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc

    if not isinstance(body.spec, dict) or not body.spec.get("models"):
        raise HTTPException(
            status_code=422, detail="spec.models must be a non-empty list"
        )

    try:
        conn = get_connection_or_404(db, connection_id)
        client = client_from_connection(conn)
        validation = validate_module_spec_live(client, body.spec)
        if not validation.ok and not body.skip_validate_live:
            raise HTTPException(
                status_code=422,
                detail={
                    "validate_live_failed": True,
                    "fail_count": validation.fail_count,
                    "warn_count": validation.warn_count,
                    "message": validation.message,
                    "items": [
                        {
                            "item_id": i.item_id,
                            "category": i.category,
                            "status": i.status,
                            "message": i.message,
                        }
                        for i in validation.items
                        if i.status == "fail"
                    ],
                },
            )
        if not validation.ok and body.skip_validate_live:
            try:
                require_advanced_confirmation(
                    confirm_advanced=body.confirm_advanced,
                    confirm_phrase=body.confirm_phrase,
                    warning=(
                        "Apply despite validate-live failures — live Odoo may reject writes "
                        "or produce broken views."
                    ),
                    risks=[
                        f"{validation.fail_count} validate-live check(s) failed",
                        "Partial apply may leave inconsistent metadata",
                        "Prefer fixing the draft or re-running validate-live",
                    ],
                )
            except ConfirmationRequired as exc:
                raise _confirm_http(exc) from exc
        manifest = manifest_for_connection(conn)
        spec_prepared, prep_notes = prepare_spec_for_live_apply(body.spec)
        spec_clean, pcm_skips = scrub_spec_for_protected_apply(spec_prepared, manifest)
        result = apply_module_spec_ui(
            client,
            spec_clean,
            apply_views=body.apply_views,
            apply_menus=body.apply_menus,
            apply_smart_buttons=body.apply_smart_buttons,
            apply_automations=body.apply_automations,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    skipped = list(result.skipped) + pcm_skips
    warnings = list(result.warnings)
    if prep_notes:
        warnings.append(f"Live prep: {len(prep_notes)} readiness adjustment(s)")
    if pcm_skips:
        warnings.append(f"PCM: skipped {len(pcm_skips)} protected item(s)")

    return ModuleSpecApplyOut(
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


@router.post("/seed-walkthrough", response_model=ModuleSpecWalkthroughOut)
def seed_module_spec_walkthrough(
    connection_id: str,
    body: ModuleSpecWalkthroughBody,
    db: Session = Depends(get_db),
    _: Annotated[None, Depends(require_connection_mutation_lock)] = None,
) -> ModuleSpecWalkthroughOut:
    """Create a linked demo spine on this Odoo so Open app is not empty lists."""
    try:
        get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                "Creates sample records on this live Odoo (site, party, job, "
                "booking, equipment lines, …). Prefer a sandbox connection."
            ),
            risks=[
                "Writes data rows on custom x_* models",
                "Reuses the first res.partner / hr.employee / res.currency if those FKs exist",
                "Idempotent by Walkthrough name — re-run updates links, does not delete",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc
    if not isinstance(body.spec, dict) or not body.spec.get("models"):
        raise HTTPException(
            status_code=422, detail="spec.models must be a non-empty list"
        )
    try:
        conn = get_connection_or_404(db, connection_id)
        client = client_from_connection(conn)
        from app.ai_walkthrough_seed import seed_walkthrough

        result = seed_walkthrough(client, body.spec)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ModuleSpecWalkthroughOut(
        ok=True,
        created=result.get("created") or {},
        open_model=result.get("open_model"),
        open_record_id=result.get("open_record_id"),
        warnings=list(result.get("warnings") or []),
        message=str(result.get("message") or ""),
    )
