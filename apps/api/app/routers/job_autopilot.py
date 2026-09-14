"""Job Autopilot API — packet (read-only) and sandbox run (writes)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.crypto import CryptoError
from app.db import get_db
from app.job_autopilot.client_index import retrieve_grounding, upsert_client_docs
from app.job_autopilot.executor import run_autopilot_job
from app.job_autopilot.packet import AutopilotResult, JobPacket, SCORECARD_IS_NOT_GOLIVE
from app.job_autopilot.planner import build_job_packet, file_excerpts_from_bytes
from app.job_autopilot.promote_target import PromoteToResult, promote_to_connection
from app.job_autopilot.report import render_markdown, render_pdf_bytes
from app.config_packet.apply import APPLY_RISKS, APPLY_WARNING, apply_config_packet
from app.config_packet.diff import diff_packet
from app.config_packet.fingerprint import fingerprint_instance
from app.config_packet.schema import ConfigPacket
from app.config_packet.settings import capture_settings, sanitize_settings
from app.job_autopilot.sandbox_gate import (
    AutopilotRefused,
    CONFIRM_PHRASE,
    ConfirmationRequired,
    assert_autopilot_run_allowed,
    classify_connection,
)
from app.job_autopilot.artifacts import persist_autopilot_job_payload
from app.job_runner import create_job, enqueue, find_in_flight_job
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.schemas import ConfirmAdvancedBody

router = APIRouter(
    prefix="/connections/{connection_id}/job-autopilot",
    tags=["job-autopilot"],
)


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


def _row(connection_id: str, db: Session):
    try:
        return get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _ground_packet(connection_id: str, packet: JobPacket, excerpts: list[tuple[str, str]]) -> None:
    if excerpts:
        upsert_client_docs(connection_id, excerpts)
    grounding = retrieve_grounding(connection_id, packet.prompt)
    if grounding:
        packet.grounding = grounding


class FileExcerptIn(BaseModel):
    filename: str
    text: str = ""


class PacketBody(BaseModel):
    prompt: str = Field(..., min_length=1)
    file_excerpts: list[FileExcerptIn] = Field(default_factory=list)
    country_code: str | None = None
    company_name: str | None = None
    use_llm: bool | None = None


class PacketOut(BaseModel):
    packet: JobPacket
    connection_kind: str
    sandbox: bool
    scorecard_note: str = SCORECARD_IS_NOT_GOLIVE
    message: str = (
        "Packet only — nothing installed. Run Autopilot on a sandbox to execute."
    )
    intent_blocked: bool = False
    intent_assessment: dict[str, Any] | None = None
    intent_clarification: dict[str, Any] | None = None


class ContractOut(BaseModel):
    stock_first: bool = True
    sandbox_only: bool = True
    promote_stays_human: bool = True
    scorecard_is_not_golive: bool = True
    refuse_production: bool = True
    implementation_job_scorecard: bool = True
    promote_to_other_connection: bool = True
    no_prod_db_clone: bool = True
    note: str = SCORECARD_IS_NOT_GOLIVE
    confirm_phrase: str = CONFIRM_PHRASE
    smoke_done_bar: str = (
        "quote → confirm → invoice-from-SO via sale.advance.payment.inv "
        "(not private _create_invoices); custom Confirm ir.actions.server, not x_status write"
    )


class RunJsonBody(ConfirmAdvancedBody):
    prompt: str = Field(..., min_length=1)
    packet: dict[str, Any] | None = None
    spec: dict[str, Any] | None = None
    use_llm: bool | None = None
    country_code: str | None = None
    company_name: str | None = None


class PromoteToBody(ConfirmAdvancedBody):
    target_connection_id: str = Field(..., min_length=1)
    zip_base64: str | None = None


class ConfigPacketBody(BaseModel):
    packet: dict[str, Any]


class ConfigPacketApplyBody(ConfirmAdvancedBody):
    packet: dict[str, Any]


@router.get("/contract", response_model=ContractOut)
def get_contract(connection_id: str, db: Session = Depends(get_db)) -> ContractOut:
    row = _row(connection_id, db)
    kind, unattended = classify_connection(row)
    _ = (kind, unattended)
    return ContractOut()


@router.post("/packet", response_model=PacketOut)
def post_packet(
    connection_id: str,
    body: PacketBody,
    db: Session = Depends(get_db),
) -> PacketOut:
    row = _row(connection_id, db)
    kind, unattended = classify_connection(row)
    excerpts = [(f.filename, f.text) for f in body.file_excerpts]
    from app.ai_conversation.feature_hooks import (
        intent_assessment_payload,
        intent_clarification_for_prompt,
    )

    assessment = intent_assessment_payload(body.prompt)
    clarification = intent_clarification_for_prompt(body.prompt)
    try:
        packet = build_job_packet(
            body.prompt,
            file_excerpts=excerpts,
            country_code=body.country_code,
            company_name=body.company_name,
            use_llm=body.use_llm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _ground_packet(connection_id, packet, excerpts)
    return PacketOut(
        packet=packet,
        connection_kind=kind,
        sandbox=unattended,
        intent_blocked=bool(assessment.get("blocked")),
        intent_assessment=assessment,
        intent_clarification=clarification,
    )


class RunQueuedOut(BaseModel):
    job_id: str
    queued: bool = True
    status: str = "queued"
    message: str = (
        "Autopilot is running in the background. Keep this page open — "
        "stages update as stock, connectors, custom, and smoke finish."
    )


def _queue_autopilot(
    *,
    connection_id: str,
    db: Session,
    prompt: str,
    files: list[tuple[str, bytes, str | None]],
    packet: JobPacket | None,
    spec: dict[str, Any] | None,
    confirm_advanced: bool,
    confirm_phrase: str | None,
    use_llm: bool | None,
) -> AutopilotResult | RunQueuedOut:
    row = _row(connection_id, db)
    try:
        assert_autopilot_run_allowed(
            row,
            confirm_advanced=confirm_advanced,
            confirm_phrase=confirm_phrase,
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc
    except AutopilotRefused:
        return run_autopilot_job(
            client=None,
            connection=row,
            prompt=prompt,
            files=files,
            packet=packet,
            spec=spec,
            db=db,
            confirm_advanced=confirm_advanced,
            confirm_phrase=confirm_phrase,
            use_llm=use_llm,
        )

    existing = find_in_flight_job(db, connection_id=connection_id, kind="job_autopilot")
    if existing is not None:
        return RunQueuedOut(
            job_id=existing.id,
            status=existing.status,
            message=(
                "Autopilot already running on this connection — "
                "attaching to that job. Do not click Run again."
            ),
        )

    job = create_job(db, kind="job_autopilot", connection_id=connection_id)
    job_id = job.id
    files_copy = list(files)

    def _work() -> dict[str, Any]:
        from app.db import SessionLocal
        from app.odoo_service import get_connection_or_404 as load_row

        wdb = SessionLocal()
        try:
            live = load_row(wdb, connection_id)
            client = client_from_connection(live)
            out = run_autopilot_job(
                client=client,
                connection=live,
                prompt=prompt,
                files=files_copy,
                packet=packet,
                spec=spec,
                db=wdb,
                confirm_advanced=confirm_advanced,
                confirm_phrase=confirm_phrase,
                use_llm=use_llm,
                progress_job_id=job_id,
            )
            return persist_autopilot_job_payload(job_id, out.model_dump(mode="json"))
        except (OdooClientError, CryptoError) as exc:
            raise RuntimeError(str(exc)) from exc
        finally:
            wdb.close()

    enqueue(job.id, _work)
    return RunQueuedOut(job_id=job.id)


@router.post("/run")
def post_run_json(
    connection_id: str,
    body: RunJsonBody,
    db: Session = Depends(get_db),
) -> AutopilotResult | RunQueuedOut:
    packet = JobPacket.model_validate(body.packet) if body.packet else None
    return _queue_autopilot(
        connection_id=connection_id,
        db=db,
        prompt=body.prompt,
        files=[],
        packet=packet,
        spec=body.spec,
        confirm_advanced=body.confirm_advanced,
        confirm_phrase=body.confirm_phrase,
        use_llm=body.use_llm,
    )


@router.post("/run-files")
async def post_run_files(
    connection_id: str,
    prompt: str = Form(...),
    confirm_advanced: bool = Form(False),
    confirm_phrase: str | None = Form(None),
    use_llm: bool | None = Form(None),
    files: list[UploadFile] | None = File(None),
    db: Session = Depends(get_db),
) -> AutopilotResult | RunQueuedOut:
    uploaded: list[tuple[str, bytes, str | None]] = []
    for f in files or []:
        raw = await f.read()
        uploaded.append((f.filename or "upload.bin", raw, f.content_type))
    excerpts = file_excerpts_from_bytes([(n, b) for n, b, _m in uploaded])
    packet = build_job_packet(prompt, file_excerpts=excerpts, use_llm=use_llm)
    return _queue_autopilot(
        connection_id=connection_id,
        db=db,
        prompt=prompt,
        files=uploaded,
        packet=packet,
        spec=None,
        confirm_advanced=confirm_advanced,
        confirm_phrase=confirm_phrase,
        use_llm=use_llm,
    )


@router.post("/promote-to", response_model=PromoteToResult)
def post_promote_to(
    connection_id: str,
    body: PromoteToBody,
    db: Session = Depends(get_db),
) -> PromoteToResult:
    _row(connection_id, db)
    try:
        return promote_to_connection(
            db,
            source_connection_id=connection_id,
            target_connection_id=body.target_connection_id,
            zip_base64=body.zip_base64,
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc


@router.get("/fingerprint")
def get_fingerprint(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _row(connection_id, db)
    try:
        client = client_from_connection(row)
    except (OdooClientError, CryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    fp = fingerprint_instance(client)
    kind, sandbox = classify_connection(row)
    return {
        "fingerprint": fp.model_dump(mode="json"),
        "connection_kind": kind,
        "sandbox": sandbox,
        "message": (
            "Read-only fingerprint. Use Job Autopilot on a sandbox, then dry-run / apply "
            "the Config Packet here. Autopilot still refuses write_mode=production."
        ),
    }


@router.post("/capture-settings")
def post_capture_settings(connection_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _row(connection_id, db)
    try:
        client = client_from_connection(row)
    except (OdooClientError, CryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    values = sanitize_settings(capture_settings(client))
    return {
        "settings": values,
        "keys": sorted(values),
        "message": (
            f"Captured {len(values)} allowlisted Settings key(s). "
            "SMTP passwords and API keys are never stored."
        ),
    }


@router.post("/config-packet/dry-run")
def post_config_packet_dry_run(
    connection_id: str,
    body: ConfigPacketBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = _row(connection_id, db)
    try:
        packet = ConfigPacket.model_validate(body.packet)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Invalid Config Packet: {exc}") from exc
    try:
        client = client_from_connection(row)
    except (OdooClientError, CryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    fp = fingerprint_instance(client)
    delta = diff_packet(packet, fp)
    kind, sandbox = classify_connection(row)
    return {
        "diff": delta.model_dump(mode="json"),
        "fingerprint": fp.model_dump(mode="json"),
        "connection_kind": kind,
        "sandbox": sandbox,
        "warning": APPLY_WARNING,
        "risks": APPLY_RISKS,
        "message": delta.message,
    }


@router.post("/config-packet/apply")
def post_config_packet_apply(
    connection_id: str,
    body: ConfigPacketApplyBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = _row(connection_id, db)
    try:
        packet = ConfigPacket.model_validate(body.packet)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Invalid Config Packet: {exc}") from exc
    try:
        client = client_from_connection(row)
        report = apply_config_packet(
            client=client,
            connection=row,
            packet=packet,
            db=db,
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc
    except (OdooClientError, CryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return report.model_dump(mode="json")


@router.post("/report.pdf")
def post_report_pdf(
    connection_id: str,
    body: AutopilotResult,
    db: Session = Depends(get_db),
) -> Response:
    _row(connection_id, db)
    markdown = body.report_markdown or render_markdown(body)
    return Response(
        content=render_pdf_bytes(markdown),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="job-autopilot-uat.pdf"'},
    )
