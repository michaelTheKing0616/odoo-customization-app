"""Bulk Suite — generic bulk workflow transitions (BLK-1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.bulk_suite.activities import (
    ActivityValidationError,
    probe_activity_model,
    run_bulk_activities,
)
from app.bulk_suite.activities import (
    ActivityValidationError,
    probe_activity_model,
    run_bulk_activities,
)
from app.bulk_suite.attachments import (
    AttachmentCleanResult,
    AttachmentValidationError,
    DuplicateScanResult,
    LargeOldScanResult,
    OrphanScanResult,
    clean_attachments,
    scan_duplicate_attachments,
    scan_large_old_attachments,
    scan_orphan_attachments,
)
from app.bulk_suite.attachments import (
    AttachmentCleanResult,
    AttachmentValidationError,
    DuplicateScanResult,
    LargeOldScanResult,
    OrphanScanResult,
    clean_attachments,
    scan_duplicate_attachments,
    scan_large_old_attachments,
    scan_orphan_attachments,
)
from app.bulk_suite.cron_manager import (
    CronManagerError,
    CronRunResult,
    create_cron_for_existing_method,
    list_crons_enriched,
    run_crons_now,
    update_cron_schedule,
)
from app.bulk_suite.cron_manager import (
    CronManagerError,
    CronRunResult,
    create_cron_for_existing_method,
    list_crons_enriched,
    run_crons_now,
    update_cron_schedule,
)
from app.bulk_suite.domain_util import DomainParseError
from app.bulk_suite.dedupe import (
    DedupeMergeResult,
    DedupeScanResult,
    DedupeValidationError,
    build_merge_snapshot_payload,
    discover_inbound_references,
    merge_duplicates,
    scan_duplicates,
)
from app.bulk_suite.dedupe import (
    DedupeMergeResult,
    DedupeScanResult,
    DedupeValidationError,
    build_merge_snapshot_payload,
    discover_inbound_references,
    merge_duplicates,
    scan_duplicates,
)
from app.bulk_suite.mass_edit import (
    MassEditResult,
    MassEditValidationError,
    resolve_and_cap,
    run_mass_edit,
)
from app.bulk_suite.portal_access import PortalApplyResult, PortalValidationError, run_bulk_portal
from app.bulk_suite.recompute import (
    RecomputeRunResult,
    RecomputeValidationError,
    run_recompute,
)
from app.bulk_suite.security import (
    SecurityApplyResult,
    SecurityValidationError,
    apply_security_changes,
    preview_security_changes,
)
from app.bulk_suite.send_message import SendMessageRunResult, SendMessageValidationError, run_bulk_send_message
from app.bulk_suite.mass_edit import (
    MassEditResult,
    MassEditValidationError,
    resolve_and_cap,
    run_mass_edit,
)
from app.bulk_suite.portal_access import PortalApplyResult, PortalValidationError, run_bulk_portal
from app.bulk_suite.recompute import (
    RecomputeRunResult,
    RecomputeValidationError,
    run_recompute,
)
from app.bulk_suite.security import (
    SecurityApplyResult,
    SecurityValidationError,
    apply_security_changes,
    preview_security_changes,
)
from app.bulk_suite.send_message import SendMessageRunResult, SendMessageValidationError, run_bulk_send_message
from app.bulk_suite.storage import load_bulk_run, save_bulk_run
from app.bulk_suite.transitions import (
    DEFAULT_RECORD_CAP,
    BulkRunResult,
    BulkSuiteError,
    discover_transitions,
    resolve_record_ids,
    run_bulk_transition,
)
from app.db import get_db
from app.hosting import hosting_hint_from_url
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.protected_enforcement import manifest_for_connection
from app.schemas import ConfirmAdvancedBody
from app.snapshots import (
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
    save_snapshot,
)

router = APIRouter(
    prefix="/connections/{connection_id}/bulk",
    tags=["bulk-suite"],
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


def _connection_row(connection_id: str, db: Session):
    try:
        return get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _client(connection_id: str, db: Session):
    row = _connection_row(connection_id, db)
    try:
        return row, client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class TransitionButtonOut(BaseModel):
    name: str
    label: str
    bulk_safe: bool
    reason: str
    in_header: bool


class BulkTransitionsOut(BaseModel):
    model: str
    buttons: list[TransitionButtonOut]


class BulkTransitionRunBody(ConfirmAdvancedBody):
    model: str
    method: str
    ids: list[int] | None = None
    domain: list[Any] | str | None = None
    dry_run: bool = True
    cap: int = Field(DEFAULT_RECORD_CAP, ge=1, le=5000)


class MassEditRunBody(ConfirmAdvancedBody):
    model: str
    values: dict[str, Any]
    ids: list[int] | None = None
    domain: list[Any] | str | None = None
    dry_run: bool = True
    cap: int = Field(DEFAULT_RECORD_CAP, ge=1, le=5000)


class DedupeScanBody(BaseModel):
    model: str
    match_fields: list[str] = Field(..., min_length=1)
    mode: str = Field("exact", pattern="^(exact|fuzzy)$")
    limit: int = Field(2000, ge=1, le=5000)
    domain: list[Any] | None = None


class DedupeMergeBody(ConfirmAdvancedBody):
    model: str
    winner_id: int
    loser_ids: list[int] = Field(..., min_length=1)
    dry_run: bool = True
    archive_or_delete: str = Field("archive", pattern="^(archive|unlink)$")


class CronRowOut(BaseModel):
    id: int
    name: str
    model_name: str | None
    interval_number: int | None
    interval_type: str | None
    active: bool
    nextcall: str | None
    lastcall: str | None
    description: str
    state: str | None = None
    code_preview: str | None = None


class CronListOut(BaseModel):
    crons: list[CronRowOut]
    probe: dict[str, Any]


class CronRunNowBody(ConfirmAdvancedBody):
    cron_ids: list[int] = Field(..., min_length=1)
    dry_run: bool = True


class CreateCronBody(ConfirmAdvancedBody):
    name: str = Field(..., min_length=1)
    model: str = Field(..., min_length=3)
    method: str = Field(..., min_length=1)
    interval_number: int = Field(1, ge=1)
    interval_type: str = Field("days", pattern="^(minutes|hours|days|weeks|months)$")
    active: bool = True
    nextcall: str | None = None


class PatchCronScheduleBody(ConfirmAdvancedBody):
    interval_number: int | None = Field(None, ge=1)
    interval_type: str | None = Field(None, pattern="^(minutes|hours|days|weeks|months)$")
    active: bool | None = None
    nextcall: str | None = None


class AttachmentScanBody(BaseModel):
    limit: int = Field(2000, ge=1, le=10000)


class DuplicateScanBody(BaseModel):
    limit: int = Field(5000, ge=1, le=20000)


class LargeOldScanBody(BaseModel):
    min_bytes: int = Field(1_048_576, ge=1)
    older_than_days: int = Field(90, ge=1, le=3650)
    limit: int = Field(500, ge=1, le=5000)


class AttachmentRowOut(BaseModel):
    id: int
    name: str
    res_model: str | None
    res_id: int | None
    res_field: str | None
    checksum: str | None
    file_size: int
    create_date: str | None
    mimetype: str | None
    cleanable: bool
    exclusion_reason: str | None = None


class DuplicateGroupOut(BaseModel):
    checksum: str
    keep_id: int
    duplicate_ids: list[int]
    reclaimable_bytes: int
    members: list[AttachmentRowOut]


class OrphanScanOut(BaseModel):
    orphans: list[AttachmentRowOut]
    standalone: list[AttachmentRowOut]
    excluded: list[AttachmentRowOut]
    total_reclaimable_bytes: int
    binary_field_hint: str
    message: str


class DuplicateScanOut(BaseModel):
    groups: list[DuplicateGroupOut]
    total_reclaimable_bytes: int
    binary_field_hint: str
    message: str


class LargeOldScanOut(BaseModel):
    attachments: list[AttachmentRowOut]
    total_reclaimable_bytes: int
    min_bytes: int
    older_than_days: int
    message: str


class AttachmentCleanBody(ConfirmAdvancedBody):
    attachment_ids: list[int] = Field(..., min_length=1)
    dry_run: bool = True
    kind: str = Field("manual", pattern="^(orphan|duplicate|large_old|manual)$")


class BulkActivitiesBody(ConfirmAdvancedBody):
    model: str
    ids: list[int] | None = None
    domain: list[Any] | str | None = None
    activity_type_id: int
    summary: str = Field(..., min_length=1)
    date_deadline: str = Field(..., min_length=1)
    user_id: int | None = None
    dry_run: bool = True
    cap: int = Field(DEFAULT_RECORD_CAP, ge=1, le=5000)


class ActivityProbeOut(BaseModel):
    major: int | None
    mail_installed: bool
    supports_model: bool
    message: str


class GroupRefOut(BaseModel):
    id: int
    name: str


class UserSecurityDiffOut(BaseModel):
    user_id: int
    user_name: str
    add_groups: list[GroupRefOut]
    remove_groups: list[GroupRefOut]
    implied_warnings: list[str]
    deactivate: bool = False


class SecurityPreviewOut(BaseModel):
    mode: str
    users: list[UserSecurityDiffOut]
    message: str


class SecurityPreviewBody(BaseModel):
    user_ids: list[int] = Field(..., min_length=1)
    group_ids: list[int] = Field(default_factory=list)
    mode: str = Field("add", pattern="^(add|remove|offboard)$")
    deactivate: bool = False


class SecurityApplyBody(ConfirmAdvancedBody):
    user_ids: list[int] = Field(..., min_length=1)
    group_ids: list[int] = Field(default_factory=list)
    mode: str = Field("add", pattern="^(add|remove|offboard)$")
    deactivate: bool = False
    dry_run: bool = True
    preview_acknowledged: bool = False


class BulkPortalBody(ConfirmAdvancedBody):
    partner_ids: list[int] = Field(..., min_length=1)
    action: str = Field("grant", pattern="^(grant|revoke)$")
    dry_run: bool = True


class BulkRecomputeBody(ConfirmAdvancedBody):
    model: str
    field: str
    ids: list[int] | None = None
    domain: list[Any] | str | None = None
    dry_run: bool = True
    cap: int = Field(DEFAULT_RECORD_CAP, ge=1, le=5000)


class RecomputeProbeOut(BaseModel):
    ok: bool
    field: str
    model: str
    dependencies: list[str]
    probe_ids: list[int]
    message: str
    honesty_message: str | None = None


class BulkSendMessageBody(ConfirmAdvancedBody):
    model: str
    ids: list[int] | None = None
    domain: list[Any] | str | None = None
    body: str | None = None
    subject: str | None = None
    mail_template_id: int | None = None
    dry_run: bool = True
    cap: int = Field(DEFAULT_RECORD_CAP, ge=1, le=5000)


class MassEditRunBody(ConfirmAdvancedBody):
    model: str
    values: dict[str, Any]
    ids: list[int] | None = None
    domain: list[Any] | str | None = None
    dry_run: bool = True
    cap: int = Field(DEFAULT_RECORD_CAP, ge=1, le=5000)


class DedupeScanBody(BaseModel):
    model: str
    match_fields: list[str] = Field(..., min_length=1)
    mode: str = Field("exact", pattern="^(exact|fuzzy)$")
    limit: int = Field(2000, ge=1, le=5000)
    domain: list[Any] | None = None


class DedupeMergeBody(ConfirmAdvancedBody):
    model: str
    winner_id: int
    loser_ids: list[int] = Field(..., min_length=1)
    dry_run: bool = True
    archive_or_delete: str = Field("archive", pattern="^(archive|unlink)$")


class CronRowOut(BaseModel):
    id: int
    name: str
    model_name: str | None
    interval_number: int | None
    interval_type: str | None
    active: bool
    nextcall: str | None
    lastcall: str | None
    description: str
    state: str | None = None
    code_preview: str | None = None


class CronListOut(BaseModel):
    crons: list[CronRowOut]
    probe: dict[str, Any]


class CronRunNowBody(ConfirmAdvancedBody):
    cron_ids: list[int] = Field(..., min_length=1)
    dry_run: bool = True


class CreateCronBody(ConfirmAdvancedBody):
    name: str = Field(..., min_length=1)
    model: str = Field(..., min_length=3)
    method: str = Field(..., min_length=1)
    interval_number: int = Field(1, ge=1)
    interval_type: str = Field("days", pattern="^(minutes|hours|days|weeks|months)$")
    active: bool = True
    nextcall: str | None = None


class PatchCronScheduleBody(ConfirmAdvancedBody):
    interval_number: int | None = Field(None, ge=1)
    interval_type: str | None = Field(None, pattern="^(minutes|hours|days|weeks|months)$")
    active: bool | None = None
    nextcall: str | None = None


class AttachmentScanBody(BaseModel):
    limit: int = Field(2000, ge=1, le=10000)


class DuplicateScanBody(BaseModel):
    limit: int = Field(5000, ge=1, le=20000)


class LargeOldScanBody(BaseModel):
    min_bytes: int = Field(1_048_576, ge=1)
    older_than_days: int = Field(90, ge=1, le=3650)
    limit: int = Field(500, ge=1, le=5000)


class AttachmentRowOut(BaseModel):
    id: int
    name: str
    res_model: str | None
    res_id: int | None
    res_field: str | None
    checksum: str | None
    file_size: int
    create_date: str | None
    mimetype: str | None
    cleanable: bool
    exclusion_reason: str | None = None


class DuplicateGroupOut(BaseModel):
    checksum: str
    keep_id: int
    duplicate_ids: list[int]
    reclaimable_bytes: int
    members: list[AttachmentRowOut]


class OrphanScanOut(BaseModel):
    orphans: list[AttachmentRowOut]
    standalone: list[AttachmentRowOut]
    excluded: list[AttachmentRowOut]
    total_reclaimable_bytes: int
    binary_field_hint: str
    message: str


class DuplicateScanOut(BaseModel):
    groups: list[DuplicateGroupOut]
    total_reclaimable_bytes: int
    binary_field_hint: str
    message: str


class LargeOldScanOut(BaseModel):
    attachments: list[AttachmentRowOut]
    total_reclaimable_bytes: int
    min_bytes: int
    older_than_days: int
    message: str


class AttachmentCleanBody(ConfirmAdvancedBody):
    attachment_ids: list[int] = Field(..., min_length=1)
    dry_run: bool = True
    kind: str = Field("manual", pattern="^(orphan|duplicate|large_old|manual)$")


class BulkActivitiesBody(ConfirmAdvancedBody):
    model: str
    ids: list[int] | None = None
    domain: list[Any] | str | None = None
    activity_type_id: int
    summary: str = Field(..., min_length=1)
    date_deadline: str = Field(..., min_length=1)
    user_id: int | None = None
    dry_run: bool = True
    cap: int = Field(DEFAULT_RECORD_CAP, ge=1, le=5000)


class ActivityProbeOut(BaseModel):
    major: int | None
    mail_installed: bool
    supports_model: bool
    message: str


class GroupRefOut(BaseModel):
    id: int
    name: str


class UserSecurityDiffOut(BaseModel):
    user_id: int
    user_name: str
    add_groups: list[GroupRefOut]
    remove_groups: list[GroupRefOut]
    implied_warnings: list[str]
    deactivate: bool = False


class SecurityPreviewOut(BaseModel):
    mode: str
    users: list[UserSecurityDiffOut]
    message: str


class SecurityPreviewBody(BaseModel):
    user_ids: list[int] = Field(..., min_length=1)
    group_ids: list[int] = Field(default_factory=list)
    mode: str = Field("add", pattern="^(add|remove|offboard)$")
    deactivate: bool = False


class SecurityApplyBody(ConfirmAdvancedBody):
    user_ids: list[int] = Field(..., min_length=1)
    group_ids: list[int] = Field(default_factory=list)
    mode: str = Field("add", pattern="^(add|remove|offboard)$")
    deactivate: bool = False
    dry_run: bool = True
    preview_acknowledged: bool = False


class BulkPortalBody(ConfirmAdvancedBody):
    partner_ids: list[int] = Field(..., min_length=1)
    action: str = Field("grant", pattern="^(grant|revoke)$")
    dry_run: bool = True


class BulkRecomputeBody(ConfirmAdvancedBody):
    model: str
    field: str
    ids: list[int] | None = None
    domain: list[Any] | str | None = None
    dry_run: bool = True
    cap: int = Field(DEFAULT_RECORD_CAP, ge=1, le=5000)


class RecomputeProbeOut(BaseModel):
    ok: bool
    field: str
    model: str
    dependencies: list[str]
    probe_ids: list[int]
    message: str
    honesty_message: str | None = None


class BulkSendMessageBody(ConfirmAdvancedBody):
    model: str
    ids: list[int] | None = None
    domain: list[Any] | str | None = None
    body: str | None = None
    subject: str | None = None
    mail_template_id: int | None = None
    dry_run: bool = True
    cap: int = Field(DEFAULT_RECORD_CAP, ge=1, le=5000)


class PerRecordOut(BaseModel):
    id: int
    display_name: str
    ok: bool
    error: str | None = None


class MassEditPreviewOut(BaseModel):
    id: int
    display_name: str
    before: dict[str, Any]
    after: dict[str, Any]


class DedupeCandidateOut(BaseModel):
    id: int
    display_name: str
    preview: dict[str, Any]


class DedupeGroupOut(BaseModel):
    group_key: str
    match_fields: list[str]
    records: list[DedupeCandidateOut]


class DedupeScanOut(BaseModel):
    model: str
    mode: str
    match_fields: list[str]
    total_groups: int
    partner_merge_available: bool
    groups: list[DedupeGroupOut]
    message: str


class RelinkOut(BaseModel):
    model: str
    field: str
    ttype: str
    count: int


class BulkRunOut(BaseModel):
    run_id: str
    operation: str
    model: str
    method: str | None = None
    total: int
    succeeded: int
    failed: int
    per_record: list[PerRecordOut]
    dry_run: bool
    message: str
    values: dict[str, Any] | None = None
    preview: list[MassEditPreviewOut] | None = None
    winner_id: int | None = None
    loser_ids: list[int] | None = None
    relinks: list[RelinkOut] | None = None
    snapshot_id: str | None = None
    reversibility: str | None = None
    cron_ids: list[int] | None = None
    run_via: str | None = None
    attachment_ids: list[int] | None = None
    reclaimable_bytes: int | None = None
    kind: str | None = None
    mode: str | None = None
    preview_message: str | None = None
    action: str | None = None
    field: str | None = None
    dependencies: list[str] | None = None
    probe: dict[str, Any] | None = None
    mode: str | None = None
    preview_message: str | None = None
    action: str | None = None
    field: str | None = None
    dependencies: list[str] | None = None
    probe: dict[str, Any] | None = None


def _attachment_row_out(row: Any) -> AttachmentRowOut:
    data = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    return AttachmentRowOut.model_validate(data)


def _orphan_scan_out(result: OrphanScanResult) -> OrphanScanOut:
    data = result.to_dict()
    return OrphanScanOut(
        orphans=[AttachmentRowOut.model_validate(r) for r in data["orphans"]],
        standalone=[AttachmentRowOut.model_validate(r) for r in data["standalone"]],
        excluded=[AttachmentRowOut.model_validate(r) for r in data["excluded"]],
        total_reclaimable_bytes=result.total_reclaimable_bytes,
        binary_field_hint=str(data["binary_field_hint"]),
        message=result.message,
    )


def _duplicate_scan_out(result: DuplicateScanResult) -> DuplicateScanOut:
    data = result.to_dict()
    return DuplicateScanOut(
        groups=[
            DuplicateGroupOut(
                checksum=g["checksum"],
                keep_id=g["keep_id"],
                duplicate_ids=g["duplicate_ids"],
                reclaimable_bytes=g["reclaimable_bytes"],
                members=[AttachmentRowOut.model_validate(m) for m in g["members"]],
            )
            for g in data["groups"]
        ],
        total_reclaimable_bytes=result.total_reclaimable_bytes,
        binary_field_hint=str(data["binary_field_hint"]),
        message=result.message,
    )


def _large_old_scan_out(result: LargeOldScanResult) -> LargeOldScanOut:
    return LargeOldScanOut(
        attachments=[_attachment_row_out(r) for r in result.attachments],
        total_reclaimable_bytes=result.total_reclaimable_bytes,
        min_bytes=result.min_bytes,
        older_than_days=result.older_than_days,
        message=result.message,
    )


def _scan_out(result: DedupeScanResult) -> DedupeScanOut:
    return DedupeScanOut(
        model=result.model,
        mode=result.mode,
        match_fields=result.match_fields,
        total_groups=len(result.groups),
        partner_merge_available=result.partner_merge_available,
        groups=[
            DedupeGroupOut(
                group_key=g.group_key,
                match_fields=g.match_fields,
                records=[
                    DedupeCandidateOut(
                        id=r.id,
                        display_name=r.display_name,
                        preview=r.preview,
                    )
                    for r in g.records
                ],
            )
            for g in result.groups
        ],
        message=result.message,
    )


def _to_out(
    result: BulkRunResult
    | MassEditResult
    | DedupeMergeResult
    | CronRunResult
    | AttachmentCleanResult
    | SecurityApplyResult
    | PortalApplyResult
    | RecomputeRunResult
    | SendMessageRunResult,
) -> BulkRunOut:
    preview = None
    values = None
    relinks = None
    winner_id = None
    loser_ids = None
    snapshot_id = None
    reversibility = None
    cron_ids = None
    run_via = None
    attachment_ids = None
    reclaimable_bytes = None
    kind = None
    mode = None
    preview_message = None
    action = None
    recompute_field = None
    dependencies = None
    probe = None
    mode = None
    preview_message = None
    action = None
    recompute_field = None
    dependencies = None
    probe = None
    if isinstance(result, MassEditResult):
        values = dict(result.values)
        preview = [
            MassEditPreviewOut(
                id=row.id,
                display_name=row.display_name,
                before=row.before,
                after=row.after,
            )
            for row in result.preview
        ]
    if isinstance(result, DedupeMergeResult):
        winner_id = result.winner_id
        loser_ids = list(result.loser_ids)
        snapshot_id = result.snapshot_id
        reversibility = result.reversibility
        relinks = [
            RelinkOut(model=r.model, field=r.field, ttype=r.ttype, count=r.count)
            for r in result.relinks
        ]
    if isinstance(result, CronRunResult):
        cron_ids = list(result.cron_ids)
        run_via = result.run_via
    if isinstance(result, AttachmentCleanResult):
        attachment_ids = list(result.attachment_ids)
        reclaimable_bytes = result.reclaimable_bytes
        kind = result.kind
    if isinstance(result, SecurityApplyResult):
        mode = result.mode
        preview_message = result.preview_message
    if isinstance(result, PortalApplyResult):
        action = result.action
    if isinstance(result, RecomputeRunResult):
        recompute_field = result.field
        dependencies = list(result.dependencies)
        probe = result.probe.to_dict() if result.probe else None
    return BulkRunOut(
        run_id=result.run_id,
        operation=result.operation,
        model=result.model,
        method=result.method,
        total=result.total,
        succeeded=result.succeeded,
        failed=result.failed,
        per_record=[
            PerRecordOut(
                id=r.id,
                display_name=r.display_name,
                ok=r.ok,
                error=r.error,
            )
            for r in result.per_record
        ],
        dry_run=result.dry_run,
        message=result.message,
        values=values,
        preview=preview or None,
        winner_id=winner_id,
        loser_ids=loser_ids,
        relinks=relinks,
        snapshot_id=snapshot_id,
        reversibility=reversibility,
        cron_ids=cron_ids,
        run_via=run_via,
        attachment_ids=attachment_ids,
        reclaimable_bytes=reclaimable_bytes,
        kind=kind,
        mode=mode,
        preview_message=preview_message,
        action=action,
        field=recompute_field,
        dependencies=dependencies,
        probe=probe,
    )


@router.get("/crons", response_model=CronListOut)
def list_bulk_crons(
    connection_id: str,
    q: str | None = Query(None),
    active: bool | None = Query(None),
    limit: int = Query(300, ge=1, le=500),
    db: Session = Depends(get_db),
) -> CronListOut:
    _, client = _client(connection_id, db)
    try:
        rows, probe = list_crons_enriched(client, q=q, active=active, limit=limit)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CronListOut(
        crons=[CronRowOut.model_validate(r.to_dict()) for r in rows],
        probe=probe,
    )


@router.post("/crons/run-now", response_model=BulkRunOut)
def run_bulk_crons_now(
    connection_id: str,
    body: CronRunNowBody,
    db: Session = Depends(get_db),
) -> BulkRunOut:
    _, client = _client(connection_id, db)
    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Run-now on {len(body.cron_ids)} scheduled action(s) — executes "
                    "their server code immediately."
                ),
                risks=[
                    "May send mail, process payments, or mutate data depending on the cron",
                    "Runs as the connected Odoo user with that user's access rights",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc
    try:
        result = run_crons_now(
            client,
            cron_ids=body.cron_ids,
            dry_run=body.dry_run,
        )
    except CronManagerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    save_bulk_run(db, connection_id=connection_id, result=result)
    return _to_out(result)


@router.post("/crons", response_model=CronRowOut)
def create_bulk_cron(
    connection_id: str,
    body: CreateCronBody,
    db: Session = Depends(get_db),
) -> CronRowOut:
    _, client = _client(connection_id, db)
    try:
        require_advanced_confirmation(
            confirm_advanced=body.confirm_advanced,
            confirm_phrase=body.confirm_phrase,
            warning=(
                f"Create scheduled action {body.name!r} on {body.model}.{body.method}()."
            ),
            risks=[
                "New ir.cron record — will run on the configured interval when active",
                "Only targets an existing model method; no arbitrary Python",
            ],
        )
    except ConfirmationRequired as exc:
        raise _confirm_http(exc) from exc
    try:
        cron_id = create_cron_for_existing_method(
            client,
            name=body.name,
            model=body.model.strip(),
            method=body.method,
            interval_number=body.interval_number,
            interval_type=body.interval_type,
            active=body.active,
            nextcall=body.nextcall,
        )
        rows, _probe = list_crons_enriched(client, limit=500)
    except CronManagerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    row = next((r for r in rows if r.id == cron_id), None)
    if row is None:
        raise HTTPException(status_code=502, detail="Cron created but could not be reloaded")
    return CronRowOut.model_validate(row.to_dict())


@router.patch("/crons/{cron_id}", response_model=CronRowOut)
def patch_bulk_cron_schedule(
    connection_id: str,
    cron_id: int,
    body: PatchCronScheduleBody,
    db: Session = Depends(get_db),
) -> CronRowOut:
    _, client = _client(connection_id, db)
    if body.active is False:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=f"Deactivate scheduled action ir.cron id={cron_id}.",
                risks=["Automated job will stop until re-enabled"],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc
    try:
        row = update_cron_schedule(
            client,
            cron_id,
            interval_number=body.interval_number,
            interval_type=body.interval_type,
            active=body.active,
            nextcall=body.nextcall,
        )
    except CronManagerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CronRowOut.model_validate(row)


@router.get("/transitions", response_model=BulkTransitionsOut)
def list_bulk_transitions(
    connection_id: str,
    model: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
) -> BulkTransitionsOut:
    row, client = _client(connection_id, db)
    try:
        buttons = discover_transitions(
            client,
            connection_id=connection_id,
            model=model.strip(),
            odoo_version=row.server_version,
        )
    except BulkSuiteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return BulkTransitionsOut(
        model=model.strip(),
        buttons=[
            TransitionButtonOut(
                name=b.name,
                label=b.label,
                bulk_safe=b.bulk_safe,
                reason=b.reason,
                in_header=b.in_header,
            )
            for b in buttons
        ],
    )


@router.post("/transitions/run", response_model=BulkRunOut)
def run_bulk_transitions(
    connection_id: str,
    body: BulkTransitionRunBody,
    db: Session = Depends(get_db),
) -> BulkRunOut:
    row, client = _client(connection_id, db)
    model = body.model.strip()
    hint = hosting_hint_from_url(row.url)
    hint = hosting_hint_from_url(row.url)
    method = body.method.strip()
    if not method:
        raise HTTPException(status_code=400, detail="method is required")

    try:
        buttons = discover_transitions(
            client,
            connection_id=connection_id,
            model=model,
            odoo_version=row.server_version,
        )
    except BulkSuiteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    known = {b.name: b for b in buttons}
    btn = known.get(method)
    if btn is None:
        raise HTTPException(
            status_code=400,
            detail=f"Method {method!r} was not discovered on form view for {model!r}",
        )
    if not btn.bulk_safe and not body.dry_run:
        raise HTTPException(
            status_code=400,
            detail=f"Method {method!r} is not bulk-safe: {btn.reason}",
        )

    try:
        record_ids = resolve_record_ids(
            client,
            model=model,
            ids=body.ids,
            domain=body.domain,
            cap=body.cap,
        )
    except DomainParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BulkSuiteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Bulk transition {method!r} on {len(record_ids)} {model!r} record(s) "
                    "via Odoo object button RPC."
                ),
                risks=[
                    "Runs as the connected Odoo user — Odoo enforces access per record",
                    "Partial failures are reported per record; successful rows are not auto-undone",
                    "Workflow methods may have side effects (mail, stock, accounting)",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    try:
        result = run_bulk_transition(
            client,
            model=model,
            method=method,
            record_ids=record_ids,
            dry_run=body.dry_run,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    save_bulk_run(db, connection_id=connection_id, result=result)
    return _to_out(result)


@router.post("/mass-edit", response_model=BulkRunOut)
def run_mass_edit_route(
    connection_id: str,
    body: MassEditRunBody,
    db: Session = Depends(get_db),
) -> BulkRunOut:
    row, client = _client(connection_id, db)
    model = body.model.strip()
    if not body.values:
        raise HTTPException(status_code=400, detail="values must include at least one field")

    try:
        record_ids = resolve_and_cap(
            client,
            model=model,
            ids=body.ids,
            domain=body.domain,
            cap=body.cap,
        )
    except DomainParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BulkSuiteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    manifest = manifest_for_connection(row)

    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Mass edit on {len(record_ids)} {model!r} record(s): "
                    f"{list(body.values.keys())}."
                ),
                risks=[
                    "Single write() batch — same power as list multi-edit in developer mode",
                    "Partial failures are reported per record; successful rows are not auto-undone",
                    "Protected-module policy applies (tier-1 blocked; tier-2 x_* only)",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    try:
        result = run_mass_edit(
            client,
            model=model,
            record_ids=record_ids,
            values=body.values,
            dry_run=body.dry_run,
            manifest=manifest,
        )
    except MassEditValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    save_bulk_run(db, connection_id=connection_id, result=result)
    return _to_out(result)


@router.post("/dedupe/scan", response_model=DedupeScanOut)
def dedupe_scan(
    connection_id: str,
    body: DedupeScanBody,
    db: Session = Depends(get_db),
) -> DedupeScanOut:
    row, client = _client(connection_id, db)
    model = body.model.strip()
    manifest = manifest_for_connection(row)
    try:
        result = scan_duplicates(
            client,
            model=model,
            match_fields=[f.strip() for f in body.match_fields if f.strip()],
            mode=body.mode,  # type: ignore[arg-type]
            limit=body.limit,
            domain=body.domain,
            manifest=manifest,
        )
    except DedupeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _scan_out(result)


@router.get("/dedupe/references")
def dedupe_references(
    connection_id: str,
    model: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _, client = _client(connection_id, db)
    try:
        refs = discover_inbound_references(client, model.strip())
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "model": model.strip(),
        "references": [
            {"model": r.model, "field": r.field, "ttype": r.ttype} for r in refs
        ],
    }


@router.post("/dedupe/merge", response_model=BulkRunOut)
def dedupe_merge(
    connection_id: str,
    body: DedupeMergeBody,
    db: Session = Depends(get_db),
) -> BulkRunOut:
    row, client = _client(connection_id, db)
    model = body.model.strip()
    manifest = manifest_for_connection(row)
    losers = [int(i) for i in body.loser_ids if int(i) != int(body.winner_id)]

    if not losers:
        raise HTTPException(status_code=400, detail="loser_ids must differ from winner_id")

    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Merge {len(losers)} duplicate {model!r} record(s) into winner "
                    f"{body.winner_id} — relinks inbound FKs then "
                    f"{body.archive_or_delete}s losers."
                ),
                risks=[
                    "Partially reversible — snapshot stored but manual recovery may be needed",
                    "Inbound many2one/many2many + chatter rows are rewritten",
                    "Unlink mode permanently deletes loser records",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    snapshot_id: str | None = None
    references = discover_inbound_references(client, model)
    if not body.dry_run:
        try:
            payload = build_merge_snapshot_payload(
                client,
                model=model,
                winner_id=body.winner_id,
                loser_ids=losers,
                references=references,
            )
            snap = save_snapshot(
                db,
                connection_id=connection_id,
                resource_type="dedupe_merge",
                resource_key=f"dedupe:{model}:{body.winner_id}",
                label=f"Dedupe merge {model} → winner {body.winner_id}",
                payload=payload,
                reversible="partial",
            )
            snapshot_id = snap.id
        except OdooClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        result = merge_duplicates(
            client,
            model=model,
            winner_id=body.winner_id,
            loser_ids=losers,
            dry_run=body.dry_run,
            archive_or_delete=body.archive_or_delete,  # type: ignore[arg-type]
            snapshot_id=snapshot_id,
            manifest=manifest,
        )
    except DedupeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    save_bulk_run(db, connection_id=connection_id, result=result)
    return _to_out(result)


@router.post("/attachments/orphans/scan", response_model=OrphanScanOut)
def attachment_orphan_scan(
    connection_id: str,
    body: AttachmentScanBody,
    db: Session = Depends(get_db),
) -> OrphanScanOut:
    _, client = _client(connection_id, db)
    try:
        result = scan_orphan_attachments(client, limit=body.limit)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _orphan_scan_out(result)


@router.post("/attachments/duplicates/scan", response_model=DuplicateScanOut)
def attachment_duplicate_scan(
    connection_id: str,
    body: DuplicateScanBody,
    db: Session = Depends(get_db),
) -> DuplicateScanOut:
    _, client = _client(connection_id, db)
    try:
        result = scan_duplicate_attachments(client, limit=body.limit)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _duplicate_scan_out(result)


@router.post("/attachments/large-old/scan", response_model=LargeOldScanOut)
def attachment_large_old_scan(
    connection_id: str,
    body: LargeOldScanBody,
    db: Session = Depends(get_db),
) -> LargeOldScanOut:
    _, client = _client(connection_id, db)
    try:
        result = scan_large_old_attachments(
            client,
            min_bytes=body.min_bytes,
            older_than_days=body.older_than_days,
            limit=body.limit,
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _large_old_scan_out(result)


@router.post("/attachments/clean", response_model=BulkRunOut)
def attachment_clean(
    connection_id: str,
    body: AttachmentCleanBody,
    db: Session = Depends(get_db),
) -> BulkRunOut:
    row, client = _client(connection_id, db)
    manifest = manifest_for_connection(row)
    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Permanently delete {len(body.attachment_ids)} ir.attachment row(s) "
                    f"({body.kind} clean)."
                ),
                risks=[
                    "Permanent file/attachment deletion — not reversible via this app",
                    "May include documents linked to business records (including tier-1 models)",
                    "Standalone and view/binary-field attachments are blocked by validation",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc
    try:
        result = clean_attachments(
            client,
            attachment_ids=body.attachment_ids,
            dry_run=body.dry_run,
            kind=body.kind,  # type: ignore[arg-type]
            manifest=manifest,
        )
    except AttachmentValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    save_bulk_run(db, connection_id=connection_id, result=result)
    return _to_out(result)


@router.get("/activities/probe", response_model=ActivityProbeOut)
def bulk_activities_probe(
    connection_id: str,
    model: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
) -> ActivityProbeOut:
    _, client = _client(connection_id, db)
    probe = probe_activity_model(client, model.strip())
    return ActivityProbeOut.model_validate(probe.to_dict())


@router.post("/activities", response_model=BulkRunOut)
def bulk_activities_route(
    connection_id: str,
    body: BulkActivitiesBody,
    db: Session = Depends(get_db),
) -> BulkRunOut:
    _, client = _client(connection_id, db)
    model = body.model.strip()
    try:
        record_ids = resolve_record_ids(
            client,
            model=model,
            ids=body.ids,
            domain=body.domain,
            cap=body.cap,
        )
    except DomainParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BulkSuiteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=f"Schedule activities on {len(record_ids)} {model!r} record(s).",
                risks=[
                    "Creates mail.activity rows assigned to users",
                    "May notify assignees depending on Odoo mail settings",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    try:
        result = run_bulk_activities(
            client,
            model=model,
            record_ids=record_ids,
            activity_type_id=body.activity_type_id,
            summary=body.summary,
            date_deadline=body.date_deadline,
            user_id=body.user_id,
            dry_run=body.dry_run,
        )
    except ActivityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    save_bulk_run(db, connection_id=connection_id, result=result)
    return _to_out(result)


@router.post("/security/preview", response_model=SecurityPreviewOut)
def bulk_security_preview(
    connection_id: str,
    body: SecurityPreviewBody,
    db: Session = Depends(get_db),
) -> SecurityPreviewOut:
    _, client = _client(connection_id, db)
    try:
        preview = preview_security_changes(
            client,
            user_ids=body.user_ids,
            group_ids=body.group_ids,
            mode=body.mode,  # type: ignore[arg-type]
            deactivate=body.deactivate,
        )
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SecurityPreviewOut(
        mode=preview.mode,
        users=[UserSecurityDiffOut.model_validate(u.to_dict()) for u in preview.users],
        message=preview.message,
    )


@router.post("/security/apply", response_model=BulkRunOut)
def bulk_security_apply(
    connection_id: str,
    body: SecurityApplyBody,
    db: Session = Depends(get_db),
) -> BulkRunOut:
    _, client = _client(connection_id, db)
    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Apply security change ({body.mode}) on {len(body.user_ids)} user(s)."
                ),
                risks=[
                    "Changes res.users group membership — affects permissions immediately",
                    "Adding groups may imply additional groups (implied_ids) — preview first",
                    "Offboard mode removes non-base groups and may deactivate users",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc
    try:
        result = apply_security_changes(
            client,
            user_ids=body.user_ids,
            group_ids=body.group_ids,
            mode=body.mode,  # type: ignore[arg-type]
            deactivate=body.deactivate,
            dry_run=body.dry_run,
            preview_acknowledged=body.preview_acknowledged or body.dry_run,
        )
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    save_bulk_run(db, connection_id=connection_id, result=result)
    return _to_out(result)


@router.post("/portal", response_model=BulkRunOut)
def bulk_portal_route(
    connection_id: str,
    body: BulkPortalBody,
    db: Session = Depends(get_db),
) -> BulkRunOut:
    _, client = _client(connection_id, db)
    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=(
                    f"Portal {body.action} on {len(body.partner_ids)} partner(s)."
                ),
                risks=[
                    "Grant creates portal users and sends access emails when configured",
                    "Revoke removes portal group membership",
                    "Partners without email fail individually on grant — not batch-aborted",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc
    try:
        result = run_bulk_portal(
            client,
            partner_ids=body.partner_ids,
            action=body.action,  # type: ignore[arg-type]
            dry_run=body.dry_run,
        )
    except PortalValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    save_bulk_run(db, connection_id=connection_id, result=result)
    return _to_out(result)


@router.post("/recompute", response_model=BulkRunOut)
def bulk_recompute_route(
    connection_id: str,
    body: BulkRecomputeBody,
    db: Session = Depends(get_db),
) -> BulkRunOut:
    row, client = _client(connection_id, db)
    model = body.model.strip()
    hint = hosting_hint_from_url(row.url)
    try:
        record_ids = resolve_record_ids(
            client,
            model=model,
            ids=body.ids,
            domain=body.domain,
            cap=body.cap,
        )
    except DomainParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BulkSuiteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=f"Recompute stored field {body.field!r} on {len(record_ids)} {model!r} record(s).",
                risks=[
                    "Touches dependency fields with tracking disabled to refresh stored computes",
                    "Aborts with zero writes when probe cannot confirm the technique on this instance",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    try:
        result = run_recompute(
            client,
            model=model,
            field_name=body.field,
            record_ids=record_ids,
            dry_run=body.dry_run,
            hosting_hint=hint,
        )
    except RecomputeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    save_bulk_run(db, connection_id=connection_id, result=result)
    return _to_out(result)


@router.post("/send-message", response_model=BulkRunOut)
def bulk_send_message_route(
    connection_id: str,
    body: BulkSendMessageBody,
    db: Session = Depends(get_db),
) -> BulkRunOut:
    _, client = _client(connection_id, db)
    model = body.model.strip()
    try:
        record_ids = resolve_record_ids(
            client,
            model=model,
            ids=body.ids,
            domain=body.domain,
            cap=body.cap,
        )
    except DomainParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BulkSuiteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not body.dry_run:
        try:
            require_advanced_confirmation(
                confirm_advanced=body.confirm_advanced,
                confirm_phrase=body.confirm_phrase,
                warning=f"Post threaded messages on {len(record_ids)} {model!r} record(s).",
                risks=[
                    "One message_post per record — not Odoo mass-mail composer",
                    "Template is rendered per record when mail_template_id is set",
                ],
            )
        except ConfirmationRequired as exc:
            raise _confirm_http(exc) from exc

    try:
        result = run_bulk_send_message(
            client,
            model=model,
            record_ids=record_ids,
            body=body.body,
            subject=body.subject,
            mail_template_id=body.mail_template_id,
            dry_run=body.dry_run,
        )
    except SendMessageValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    save_bulk_run(db, connection_id=connection_id, result=result)
    return _to_out(result)


class ScanFindBody(BaseModel):
    model: str
    field: str
    value: str
    limit: int = Field(default=20, ge=1, le=100)


class ScanFindRecordOut(BaseModel):
    id: int
    display_name: str | None = None


class ScanFindOut(BaseModel):
    ok: bool
    model: str
    field: str
    value: str
    count: int
    records: list[ScanFindRecordOut] = Field(default_factory=list)


@router.post("/scan-find", response_model=ScanFindOut)
def bulk_scan_find(
    connection_id: str,
    body: ScanFindBody,
    db: Session = Depends(get_db),
) -> ScanFindOut:
    from app.bulk_suite.scan import find_records_by_field

    _, client = _client(connection_id, db)
    try:
        data = find_records_by_field(
            client,
            model=body.model.strip(),
            field=body.field.strip(),
            value=body.value,
            limit=body.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ScanFindOut(
        ok=True,
        model=str(data["model"]),
        field=str(data["field"]),
        value=str(data["value"]),
        count=int(data["count"]),
        records=[
            ScanFindRecordOut(
                id=int(r["id"]),
                display_name=r.get("display_name"),
            )
            for r in data.get("records") or []
        ],
    )


@router.get("/runs/{run_id}", response_model=BulkRunOut)
def get_bulk_run(
    connection_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> BulkRunOut:
    payload = load_bulk_run(db, run_id)
    if payload is None or payload.get("connection_id") != connection_id:
        raise HTTPException(status_code=404, detail="Bulk run not found")
    return BulkRunOut.model_validate(payload)
