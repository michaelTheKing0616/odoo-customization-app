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
    ("master_data.partners_batch", "Partner batch", "Stub — use Import / Ingest", "master_data"),
    ("document_batch.invoices", "Invoice batch", "Stub — use Bulk Suite transitions", "document_batch"),
    ("settings.board_apply", "Settings board", "Stub — use Config recipes settings", "settings"),
    ("access_company.users", "Users pack", "Stub — use Access / Config recipes", "access_company"),
    ("automation.cron_pack", "Cron pack", "Stub — use Cron Manager", "automation"),
    ("ui_studio.view_pack", "View pack", "Stub — use App Studio / View Designer", "ui_studio"),
    ("housekeeping.attachments", "Attachment cleanup", "Stub — use Bulk Suite", "housekeeping"),
]


def build_stubs() -> dict[str, StubRecipe]:
    return {
        sid: StubRecipe(id=sid, title=title, blurb=blurb, atlas_class=aclass)
        for sid, title, blurb, aclass in STUB_SPECS
    }
