"""Stub recipes for non-accounting atlas classes (executable no-ops with honesty)."""

from __future__ import annotations

import uuid
from typing import Any

from app.batch_os.types import BatchJobState, RowError


class StubRecipe:
    def __init__(
        self,
        *,
        id: str,
        title: str,
        blurb: str,
        risk: str = "L1",
        atlas_class: str = "master_data",
    ) -> None:
        self.id = id
        self.title = title
        self.blurb = blurb
        self.risk = risk  # type: ignore[assignment]
        self.atlas_class = atlas_class

    def intake(
        self,
        *,
        connection_id: str,
        filename: str = "",
        headers: list[str] | None = None,
        rows: list[dict[str, str]] | None = None,
        extras: dict[str, Any] | None = None,
    ) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()),
            connection_id=connection_id,
            recipe_id=self.id,
            risk=self.risk,  # type: ignore[arg-type]
            phase="intake",
            filename=filename,
            headers=list(headers or []),
            raw_rows=list(rows or []),
            message=f"Stub recipe {self.id} — not implemented yet",
            extras=dict(extras or {}),
        )

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState:
        state.phase = "mapped"
        state.message = f"Stub {self.id}: map is a no-op"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        del client
        state.errors.append(
            RowError(
                row_index=0,
                code="blocking",
                message=f"Recipe {self.id} is a stub — use Bulk Suite / Import / Config recipes",
            )
        )
        state.phase = "failed"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        return self.validate(state, client)

    def apply(
        self,
        state: BatchJobState,
        client: Any,
        *,
        post_after_create: bool = False,
    ) -> BatchJobState:
        del post_after_create
        return self.validate(state, client)


STUB_SPECS = [
    (
        "master_data.partners_batch",
        "Partner batch",
        "Pointer — use Import / Ingest for res.partner CSV; Batch OS intake planned.",
        "master_data",
    ),
    (
        "master_data.products_batch",
        "Product batch",
        "Pointer — use Import / Ingest for product.template; Batch OS intake planned.",
        "master_data",
    ),
    (
        "settings.board_apply",
        "Settings board",
        "Pointer — use Config recipes / settings allowlist board (res.config.settings).",
        "settings",
    ),
    (
        "access_company.users",
        "Users pack",
        "Pointer — use Access / Config recipes for res.users + groups.",
        "access_company",
    ),
    (
        "automation.cron_pack",
        "Cron pack",
        "Pointer — use Cron Manager for ir.cron; no silent cron invent.",
        "automation",
    ),
    (
        "ui_studio.view_pack",
        "View pack",
        "Pointer — use App Studio / View Designer for ir.ui.view.",
        "ui_studio",
    ),
    (
        "housekeeping.attachments",
        "Attachment cleanup",
        "Pointer — use Bulk Suite archive/dedupe for ir.attachment.",
        "housekeeping",
    ),
]


def build_stubs() -> dict[str, StubRecipe]:
    return {
        sid: StubRecipe(id=sid, title=title, blurb=blurb, atlas_class=aclass)
        for sid, title, blurb, aclass in STUB_SPECS
    }
