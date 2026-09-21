"""Recipe accounting.opening_balances — wraps ingest opening TB path."""

from __future__ import annotations

import uuid
from typing import Any

from app.batch_os.journal_batch import (
    JournalBatchRecipe,
    suggest_journal_column_map,
)
from app.batch_os.types import HONESTY_PREVIEW_NE_POSTED, BatchJobState


class OpeningBalancesRecipe:
    """Opening balances reuse journal-batch shape with Opening journal bias."""

    id = "accounting.opening_balances"
    risk = "L1"
    title = "Opening balances"
    blurb = "Trial balance → draft opening move. Never raw account.move.line invent."

    def __init__(self) -> None:
        self._inner = JournalBatchRecipe()

    def intake(
        self,
        *,
        connection_id: str,
        filename: str,
        headers: list[str],
        rows: list[dict[str, str]],
        extras: dict[str, Any] | None = None,
    ) -> BatchJobState:
        state = self._inner.intake(
            connection_id=connection_id,
            filename=filename,
            headers=headers,
            rows=rows,
            extras={**(extras or {}), "opening": True},
        )
        state.recipe_id = self.id
        state.message = f"Opening balances intake: {len(rows)} rows"
        # Prefer grouping all lines into one opening move
        if "move_group" not in state.column_map.values():
            # leave map; dry_run groups by ref — operator can set move_group=OPEN
            pass
        state.honesty = (
            "Opening balances create DRAFT moves only. Post manually after review. "
            + HONESTY_PREVIEW_NE_POSTED
        )
        return state

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState:
        state.recipe_id = self.id
        if column_map is None and not state.column_map:
            state.column_map = suggest_journal_column_map(state.headers)
        return self._inner.map(state, column_map)

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        state.recipe_id = self.id
        # Force empty journal key → Opening journal via resolve
        for line in state.mapped_lines:
            if not line.journal_key:
                line.journal_key = ""
        return self._inner.validate(state, client)

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state.recipe_id = self.id
        return self._inner.dry_run(state, client)

    def apply(
        self,
        state: BatchJobState,
        client: Any,
        *,
        post_after_create: bool = False,
    ) -> BatchJobState:
        # Opening balances never auto-post
        state.recipe_id = self.id
        return self._inner.apply(state, client, post_after_create=False)
