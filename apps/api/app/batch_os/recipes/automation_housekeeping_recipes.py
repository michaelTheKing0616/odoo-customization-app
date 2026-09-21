"""Automation (ir.cron) + housekeeping (archive/dedupe partners) recipes."""

from __future__ import annotations

import uuid
from typing import Any

from app.batch_os.partner_match import find_partner_duplicates
from app.batch_os.types import HONESTY_PREVIEW_NE_POSTED, BatchJobState, RowError


class CronPackRecipe:
    id = "automation.cron_pack"
    risk = "L2"
    title = "Cron / scheduled actions"
    blurb = "List ir.cron and enable/disable by id or name via public RPC. No silent cron invent."
    atlas_class = "automation"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L2",
            phase="intake", filename=filename or "cron_pack", headers=list(headers or []), raw_rows=list(rows or []),
            message="Cron pack ready. extras: enable_ids / disable_ids or CSV name,active.",
            honesty=HONESTY_PREVIEW_NE_POSTED,
            extras={"model": "ir.cron", **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not client.model_exists("ir.cron"):
            state.errors.append(RowError(row_index=0, code="blocking", message="ir.cron missing"))
            state.phase = "failed"
            return state
        crons = client.execute_kw(
            "ir.cron", "search_read", [[]],
            {"fields": ["id", "name", "active", "interval_number", "interval_type", "model_id"], "limit": 100},
        )
        state.extras["crons"] = crons
        enable_ids = [int(x) for x in (state.extras.get("enable_ids") or [])]
        disable_ids = [int(x) for x in (state.extras.get("disable_ids") or [])]
        for row in state.raw_rows:
            name = row.get("name") or row.get("cron")
            active_raw = (row.get("active") or "").strip().lower()
            if not name:
                continue
            match = next((c for c in crons if str(c.get("name") or "") == name), None)
            if not match:
                # ilike unique
                hits = [c for c in crons if name.lower() in str(c.get("name") or "").lower()]
                match = hits[0] if len(hits) == 1 else None
            if not match:
                state.errors.append(RowError(row_index=0, code="warn", message=f"Cron not found: {name}"))
                continue
            if active_raw in {"1", "true", "yes", "enable", "on"}:
                enable_ids.append(int(match["id"]))
            elif active_raw in {"0", "false", "no", "disable", "off"}:
                disable_ids.append(int(match["id"]))
        state.extras["would_enable"] = sorted(set(enable_ids))
        state.extras["would_disable"] = sorted(set(disable_ids))
        state.phase = "validated"
        state.message = (
            f"Listed {len(crons)} crons; enable {len(state.extras['would_enable'])}, "
            f"disable {len(state.extras['would_disable'])}"
        )
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        state.message = (
            f"Dry-run: enable {state.extras.get('would_enable')}, disable {state.extras.get('would_disable')}. "
            "Preview ≠ written."
        )
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        touched: list[int] = []
        for cid in state.extras.get("would_enable") or []:
            try:
                client.execute_kw("ir.cron", "write", [[cid], {"active": True}])
                touched.append(cid)
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=0, code="warn", message=str(exc)))
        for cid in state.extras.get("would_disable") or []:
            try:
                client.execute_kw("ir.cron", "write", [[cid], {"active": False}])
                touched.append(cid)
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=0, code="warn", message=str(exc)))
        state.created_move_ids = touched
        state.phase = "applied"
        state.dry_run = False
        state.risk = "L2"
        state.message = f"Toggled {len(touched)} cron(s)"
        return state


class AutomationBasePointerRecipe:
    id = "automation.base"
    risk = "L2"
    title = "Base automations"
    blurb = "Catalog pointer — base.automation packs live in Automation Manager / App Studio. No fake RPC."
    atlas_class = "automation"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L2",
            phase="intake", filename=filename or "base_automation",
            message="Pointer: use Automation Manager for base.automation.",
            honesty=HONESTY_PREVIEW_NE_POSTED,
            extras={"pointer": "/connections/{id}/automations", **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        del client
        state.phase = "validated"
        state.message = "Catalog pointer only — no RPC writes"
        state.extras["pointer_status"] = "complete"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        state.phase = "dry_run"
        state.dry_run = True
        state.message = "Dry-run: pointer to Automation Manager (no writes)"
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create, client
        state.phase = "applied"
        state.dry_run = False
        state.message = "No-op apply — open Automation Manager (pointer)"
        return state


class PartnerDedupeRecipe:
    id = "housekeeping.partner_dedupe"
    risk = "L2"
    title = "Archive / dedupe partners"
    blurb = "Dry-run duplicate clusters by VAT/email; optional archive of inactive extras. Preview ≠ written."
    atlas_class = "housekeeping"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L2",
            phase="intake", filename=filename or "partner_dedupe",
            message="Partner dedupe ready (read-only clusters by default).",
            honesty=HONESTY_PREVIEW_NE_POSTED,
            extras=dict(extras or {}),
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        clusters = find_partner_duplicates(client)
        state.extras["clusters"] = clusters
        archive_ids = [int(x) for x in (state.extras.get("archive_ids") or [])]
        state.extras["would_archive"] = archive_ids
        state.phase = "validated"
        state.message = f"Found {len(clusters)} duplicate cluster(s); archive {len(archive_ids)} id(s) proposed"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        state.phase = "dry_run"
        state.dry_run = True
        state.message = (
            f"Dry-run: {len(state.extras.get('clusters') or [])} clusters; "
            f"would archive {len(state.extras.get('would_archive') or [])}. Preview ≠ written."
        )
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        archived: list[int] = []
        for pid in state.extras.get("would_archive") or []:
            try:
                client.execute_kw("res.partner", "write", [[pid], {"active": False}])
                archived.append(pid)
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=0, code="warn", message=str(exc)))
        state.created_move_ids = archived
        state.phase = "applied"
        state.dry_run = False
        state.risk = "L2"
        state.message = f"Archived {len(archived)} partner(s); clusters remain in extras for review"
        return state


class AttachmentsCleanupRecipe:
    id = "housekeeping.attachments"
    risk = "L2"
    title = "Attachment cleanup"
    blurb = "List orphan-ish ir.attachment candidates; archive/unlink only when extras.attachment_ids provided."
    atlas_class = "housekeeping"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L2",
            phase="intake", filename=filename or "attachments",
            message="Attachment cleanup ready.", honesty=HONESTY_PREVIEW_NE_POSTED,
            extras=dict(extras or {}),
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not client.model_exists("ir.attachment"):
            state.errors.append(RowError(row_index=0, code="blocking", message="ir.attachment missing"))
            state.phase = "failed"
            return state
        rows = client.execute_kw(
            "ir.attachment", "search_read",
            [[("res_model", "=", False)]],
            {"fields": ["id", "name", "file_size", "create_date"], "limit": 50},
        )
        state.extras["candidates"] = rows
        ids = [int(x) for x in (state.extras.get("attachment_ids") or [])]
        state.extras["would_archive"] = ids
        state.phase = "validated"
        state.message = f"{len(rows)} unlinked attachment candidate(s); {len(ids)} explicit id(s) to archive"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        state.message = f"Dry-run: would archive {len(state.extras.get('would_archive') or [])} attachment(s)"
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        archived: list[int] = []
        for aid in state.extras.get("would_archive") or []:
            try:
                # Prefer archive when field exists; else unlink
                client.execute_kw("ir.attachment", "unlink", [[aid]])
                archived.append(aid)
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=0, code="warn", message=str(exc)))
        state.created_move_ids = archived
        state.phase = "applied"
        state.dry_run = False
        state.risk = "L2"
        state.message = f"Removed {len(archived)} attachment(s)"
        return state
