"""UI / Studio atlas pointers — complete catalog entries, no fake RPC."""

from __future__ import annotations

import uuid
from typing import Any

from app.batch_os.types import HONESTY_PREVIEW_NE_POSTED, BatchJobState


class ViewPackPointerRecipe:
    id = "ui_studio.view_pack"
    risk = "L1"
    title = "Views"
    blurb = "Pointer to App Studio / View Designer for ir.ui.view. No Batch OS RPC invent."
    atlas_class = "ui_studio"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L1",
            phase="intake", filename=filename or "view_pack",
            message="Open App Studio for view generation.",
            honesty=HONESTY_PREVIEW_NE_POSTED,
            extras={
                "pointer": "/connections/{id}/studio",
                "models": ["ir.ui.view"],
                "pointer_status": "complete",
                **(extras or {}),
            },
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        del client
        state.phase = "validated"
        state.message = "Catalog pointer — App Studio owns ir.ui.view"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        state.phase = "dry_run"
        state.dry_run = True
        state.message = "Dry-run: pointer to App Studio (no RPC writes)"
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create, client
        state.phase = "applied"
        state.dry_run = False
        state.message = "No-op — use App Studio / View Designer"
        return state


class MenuPackPointerRecipe:
    id = "ui_studio.menus"
    risk = "L1"
    title = "Menus"
    blurb = "Pointer to App Studio for ir.ui.menu packs. Catalog complete."
    atlas_class = "ui_studio"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L1",
            phase="intake", filename=filename or "menu_pack",
            message="Open App Studio for menu generation.",
            honesty=HONESTY_PREVIEW_NE_POSTED,
            extras={"pointer": "/connections/{id}/studio", "models": ["ir.ui.menu"], "pointer_status": "complete", **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        del client
        state.phase = "validated"
        state.message = "Catalog pointer — App Studio owns ir.ui.menu"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        state.phase = "dry_run"
        state.dry_run = True
        state.message = "Dry-run: pointer to App Studio (no RPC writes)"
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create, client
        state.phase = "applied"
        state.dry_run = False
        state.message = "No-op — use App Studio for menus"
        return state
