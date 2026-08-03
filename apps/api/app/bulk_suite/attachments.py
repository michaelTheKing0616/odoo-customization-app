"""Attachment housekeeping — orphan/duplicate scans + confirmed clean (BLK-5)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.transitions import BulkRunResult, BulkSuiteError, PerRecordResult
from app.protected_enforcement import is_custom_model, protected_models_for

CleanKind = Literal["orphan", "duplicate", "large_old", "manual"]

# View assets and other non-user uploads we never auto-target.
_EXCLUDED_CLEAN_MODELS = frozenset({"ir.ui.view"})

# Attachments bound to a binary field on a live record — documented heuristic, not deleted.
_BINARY_FIELD_HINT = (
    "Attachments with res_field set are treated as binary-field storage on their parent "
    "record and are excluded from orphan/duplicate clean suggestions."
)

_PREFERRED_FIELDS = [
    "name",
    "res_model",
    "res_id",
    "res_field",
    "checksum",
    "file_size",
    "create_date",
    "mimetype",
    "type",
]


class AttachmentValidationError(BulkSuiteError):
    pass


@dataclass(frozen=True)
class AttachmentRow:
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "res_model": self.res_model,
            "res_id": self.res_id,
            "res_field": self.res_field,
            "checksum": self.checksum,
            "file_size": self.file_size,
            "create_date": self.create_date,
            "mimetype": self.mimetype,
            "cleanable": self.cleanable,
            "exclusion_reason": self.exclusion_reason,
        }


@dataclass
class DuplicateGroup:
    checksum: str
    keep_id: int
    duplicate_ids: list[int]
    reclaimable_bytes: int
    members: list[AttachmentRow]

    def to_dict(self) -> dict[str, Any]:
        return {
            "checksum": self.checksum,
            "keep_id": self.keep_id,
            "duplicate_ids": list(self.duplicate_ids),
            "reclaimable_bytes": self.reclaimable_bytes,
            "members": [m.to_dict() for m in self.members],
        }


@dataclass
class OrphanScanResult:
    orphans: list[AttachmentRow]
    standalone: list[AttachmentRow]
    excluded: list[AttachmentRow]
    total_reclaimable_bytes: int
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "orphans": [r.to_dict() for r in self.orphans],
            "standalone": [r.to_dict() for r in self.standalone],
            "excluded": [r.to_dict() for r in self.excluded],
            "total_reclaimable_bytes": self.total_reclaimable_bytes,
            "binary_field_hint": _BINARY_FIELD_HINT,
            "message": self.message,
        }


@dataclass
class DuplicateScanResult:
    groups: list[DuplicateGroup]
    total_reclaimable_bytes: int
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "groups": [g.to_dict() for g in self.groups],
            "total_reclaimable_bytes": self.total_reclaimable_bytes,
            "binary_field_hint": _BINARY_FIELD_HINT,
            "message": self.message,
        }


@dataclass
class LargeOldScanResult:
    attachments: list[AttachmentRow]
    total_reclaimable_bytes: int
    min_bytes: int
    older_than_days: int
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "attachments": [r.to_dict() for r in self.attachments],
            "total_reclaimable_bytes": self.total_reclaimable_bytes,
            "min_bytes": self.min_bytes,
            "older_than_days": self.older_than_days,
            "message": self.message,
        }


@dataclass
class AttachmentCleanResult(BulkRunResult):
    attachment_ids: list[int] = field(default_factory=list)
    reclaimable_bytes: int = 0
    kind: str = "manual"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["attachment_ids"] = list(self.attachment_ids)
        data["reclaimable_bytes"] = self.reclaimable_bytes
        data["kind"] = self.kind
        return data


def _attachment_fields(client: OdooClient) -> list[str]:
    available = set(
        client.execute_kw("ir.attachment", "fields_get", [], {"attributes": []}).keys()
    )
    return [f for f in _PREFERRED_FIELDS if f in available]


def _int_size(value: Any) -> int:
    if value in (None, False):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _row_from_dict(raw: dict[str, Any], *, cleanable: bool, reason: str | None = None) -> AttachmentRow:
    res_model = raw.get("res_model")
    res_id = raw.get("res_id")
    return AttachmentRow(
        id=int(raw["id"]),
        name=str(raw.get("name") or ""),
        res_model=str(res_model) if res_model else None,
        res_id=int(res_id) if res_id not in (None, False, 0) else None,
        res_field=str(raw["res_field"]) if raw.get("res_field") else None,
        checksum=str(raw["checksum"]) if raw.get("checksum") else None,
        file_size=_int_size(raw.get("file_size")),
        create_date=str(raw["create_date"]) if raw.get("create_date") else None,
        mimetype=str(raw["mimetype"]) if raw.get("mimetype") else None,
        cleanable=cleanable,
        exclusion_reason=reason,
    )


def _classify_exclusion(raw: dict[str, Any]) -> tuple[bool, str | None]:
    model = raw.get("res_model")
    if model in _EXCLUDED_CLEAN_MODELS:
        return False, f"Excluded model {model!r} (view/asset attachment)"
    if raw.get("res_field"):
        return False, _BINARY_FIELD_HINT
    return True, None


def _is_standalone(raw: dict[str, Any]) -> bool:
    model = raw.get("res_model")
    rid = raw.get("res_id")
    if not model or model is False:
        return True
    if rid in (None, False, 0):
        return True
    return False


def _search_attachments(
    client: OdooClient,
    *,
    domain: list[Any],
    limit: int,
) -> list[dict[str, Any]]:
    fields = _attachment_fields(client)
    return client.execute_kw(
        "ir.attachment",
        "search_read",
        [domain],
        {"fields": fields, "limit": limit, "order": "id desc"},
    )


def scan_orphan_attachments(
    client: OdooClient,
    *,
    limit: int = 2000,
) -> OrphanScanResult:
    rows = _search_attachments(
        client,
        domain=[("res_model", "!=", False), ("res_id", "!=", 0)],
        limit=limit,
    )
    orphans: list[AttachmentRow] = []
    standalone: list[AttachmentRow] = []
    excluded: list[AttachmentRow] = []
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for raw in rows:
        if _is_standalone(raw):
            standalone.append(
                _row_from_dict(
                    raw,
                    cleanable=False,
                    reason="Standalone upload (no res_model/res_id) — report only",
                )
            )
            continue
        cleanable, reason = _classify_exclusion(raw)
        if not cleanable:
            excluded.append(_row_from_dict(raw, cleanable=False, reason=reason))
            continue
        model = str(raw["res_model"])
        by_model[model].append(raw)

    for model, group in by_model.items():
        if not client.model_exists(model):
            for raw in group:
                row = _row_from_dict(raw, cleanable=True)
                orphans.append(row)
            continue
        ids = [int(r["res_id"]) for r in group]
        try:
            existing = set(
                client.execute_kw(model, "search", [[("id", "in", ids)]])
            )
        except OdooClientError:
            for raw in group:
                excluded.append(
                    _row_from_dict(
                        raw,
                        cleanable=False,
                        reason=f"Could not verify parent records on {model!r}",
                    )
                )
            continue
        for raw in group:
            if int(raw["res_id"]) not in existing:
                orphans.append(_row_from_dict(raw, cleanable=True))

    # Also sample standalone uploads (not linked) for visibility — separate query cap.
    standalone_rows = _search_attachments(
        client,
        domain=["|", ("res_model", "=", False), ("res_id", "=", 0)],
        limit=min(200, limit),
    )
    for raw in standalone_rows:
        if any(s.id == int(raw["id"]) for s in standalone):
            continue
        standalone.append(
            _row_from_dict(
                raw,
                cleanable=False,
                reason="Standalone upload (no res_model/res_id) — report only",
            )
        )

    total_bytes = sum(r.file_size for r in orphans)
    return OrphanScanResult(
        orphans=orphans,
        standalone=standalone,
        excluded=excluded,
        total_reclaimable_bytes=total_bytes,
        message=(
            f"Orphan scan: {len(orphans)} cleanable orphan(s), "
            f"{len(standalone)} standalone, {len(excluded)} excluded "
            f"({total_bytes} bytes reclaimable from orphans)"
        ),
    )


def scan_duplicate_attachments(
    client: OdooClient,
    *,
    limit: int = 5000,
) -> DuplicateScanResult:
    rows = _search_attachments(
        client,
        domain=[("checksum", "!=", False)],
        limit=limit,
    )
    by_checksum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        cleanable, _reason = _classify_exclusion(raw)
        if not cleanable:
            continue
        cs = str(raw.get("checksum") or "")
        if not cs:
            continue
        by_checksum[cs].append(raw)

    groups: list[DuplicateGroup] = []
    total_bytes = 0
    for cs, members in by_checksum.items():
        if len(members) < 2:
            continue
        members.sort(
            key=lambda r: (str(r.get("create_date") or ""), int(r["id"])),
            reverse=True,
        )
        attachment_rows = [_row_from_dict(m, cleanable=True) for m in members]
        keep = attachment_rows[0]
        losers = attachment_rows[1:]
        reclaim = sum(r.file_size for r in losers)
        total_bytes += reclaim
        groups.append(
            DuplicateGroup(
                checksum=cs,
                keep_id=keep.id,
                duplicate_ids=[r.id for r in losers],
                reclaimable_bytes=reclaim,
                members=attachment_rows,
            )
        )

    groups.sort(key=lambda g: (g.reclaimable_bytes, len(g.duplicate_ids)), reverse=True)
    return DuplicateScanResult(
        groups=groups,
        total_reclaimable_bytes=total_bytes,
        message=(
            f"Duplicate scan: {len(groups)} checksum group(s), "
            f"{sum(len(g.duplicate_ids) for g in groups)} duplicate file(s), "
            f"{total_bytes} bytes reclaimable (keep-newest default)"
        ),
    )


def scan_large_old_attachments(
    client: OdooClient,
    *,
    min_bytes: int = 1_048_576,
    older_than_days: int = 90,
    limit: int = 500,
) -> LargeOldScanResult:
    cutoff = datetime.now(UTC) - timedelta(days=max(1, older_than_days))
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    domain: list[Any] = [
        ("file_size", ">=", max(1, min_bytes)),
        ("create_date", "<", cutoff_str),
    ]
    rows = _search_attachments(client, domain=domain, limit=limit)
    attachments: list[AttachmentRow] = []
    for raw in rows:
        if _is_standalone(raw):
            attachments.append(
                _row_from_dict(
                    raw,
                    cleanable=False,
                    reason="Standalone upload — report only",
                )
            )
            continue
        cleanable, reason = _classify_exclusion(raw)
        attachments.append(_row_from_dict(raw, cleanable=cleanable, reason=reason))
    reclaimable = sum(r.file_size for r in attachments if r.cleanable)
    return LargeOldScanResult(
        attachments=attachments,
        total_reclaimable_bytes=reclaimable,
        min_bytes=min_bytes,
        older_than_days=older_than_days,
        message=(
            f"Large/old scan: {sum(1 for r in attachments if r.cleanable)} cleanable of "
            f"{len(attachments)} row(s) ≥{min_bytes} bytes older than {older_than_days}d "
            f"({reclaimable} bytes reclaimable)"
        ),
    )


def _tier1_attachment_models(
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
) -> set[str]:
    models: set[str] = set()
    for raw in rows:
        model = raw.get("res_model")
        if not model:
            continue
        model_s = str(model)
        tier = protected_models_for(manifest, model_s)
        if tier == "tier_1" and not is_custom_model(model_s):
            models.add(model_s)
    return models


def validate_clean_targets(
    rows: list[dict[str, Any]],
    *,
    manifest: dict[str, Any] | None = None,
) -> None:
    if not rows:
        raise AttachmentValidationError("No attachment ids provided")
    for raw in rows:
        if _is_standalone(raw):
            raise AttachmentValidationError(
                "Standalone attachments (no res_model/res_id) cannot be auto-cleaned"
            )
        cleanable, reason = _classify_exclusion(raw)
        if not cleanable:
            raise AttachmentValidationError(reason or "Attachment is excluded from cleaning")


def clean_attachments(
    client: OdooClient,
    *,
    attachment_ids: list[int],
    dry_run: bool = True,
    kind: CleanKind = "manual",
    manifest: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> AttachmentCleanResult:
    run_id = run_id or str(uuid.uuid4())
    ids = list(dict.fromkeys(int(i) for i in attachment_ids))
    if not ids:
        raise AttachmentValidationError("attachment_ids must not be empty")

    fields = _attachment_fields(client)
    rows = client.execute_kw(
        "ir.attachment",
        "read",
        [ids],
        {"fields": fields},
    )
    found = {int(r["id"]) for r in rows}
    missing = [i for i in ids if i not in found]
    if missing:
        raise AttachmentValidationError(f"Attachment id(s) not found: {missing[:5]}")

    validate_clean_targets(rows, manifest=manifest)
    reclaimable = sum(_int_size(r.get("file_size")) for r in rows)
    tier1_models = _tier1_attachment_models(manifest or {}, rows)

    per_record: list[PerRecordResult] = []
    succeeded = 0
    failed = 0

    for raw in rows:
        aid = int(raw["id"])
        label = str(raw.get("name") or aid)
        if dry_run:
            per_record.append(
                PerRecordResult(id=aid, display_name=label, ok=True, error="dry-run")
            )
            succeeded += 1
            continue
        try:
            client.execute_kw("ir.attachment", "unlink", [[aid]])
            per_record.append(PerRecordResult(id=aid, display_name=label, ok=True))
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            per_record.append(
                PerRecordResult(id=aid, display_name=label, ok=False, error=str(exc))
            )

    msg = (
        f"Attachment clean ({kind}): {succeeded} ok, {failed} failed of {len(ids)}"
        if not dry_run
        else f"Dry-run: would delete {len(ids)} attachment(s) ({reclaimable} bytes)"
    )
    if tier1_models and not dry_run:
        msg += f"; includes tier-1 parent model(s): {', '.join(sorted(tier1_models))}"

    return AttachmentCleanResult(
        run_id=run_id,
        operation="attachment_clean",
        model="ir.attachment",
        total=len(ids),
        succeeded=succeeded,
        failed=failed,
        per_record=per_record,
        dry_run=dry_run,
        message=msg,
        attachment_ids=ids,
        reclaimable_bytes=reclaimable,
        kind=kind,
    )
