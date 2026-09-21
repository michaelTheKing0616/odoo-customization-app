"""Recipe accounting.lock_dates — L3 fiscal lock date write via public RPC."""

from __future__ import annotations

import uuid
from typing import Any

from app.batch_os.types import HONESTY_PREVIEW_NE_POSTED, BatchJobState, RowError
from app.config_packet.fingerprint import read_company_lock_dates


_LOCK_FIELDS = ("period_lock_date", "fiscalyear_lock_date", "tax_lock_date")


class LockDatesRecipe:
    id = "accounting.lock_dates"
    risk = "L3"
    title = "Lock dates"
    blurb = "Set period / FY / tax lock dates on res.company. Confirm required."

    def intake(
        self,
        *,
        connection_id: str,
        filename: str = "",
        headers: list[str] | None = None,
        rows: list[dict[str, str]] | None = None,
        extras: dict[str, Any] | None = None,
    ) -> BatchJobState:
        extras = dict(extras or {})
        return BatchJobState(
            job_id=str(uuid.uuid4()),
            connection_id=connection_id,
            recipe_id=self.id,
            risk="L3",
            phase="intake",
            filename=filename or "lock_dates",
            headers=list(headers or []),
            raw_rows=list(rows or []),
            message="Lock dates recipe ready — supply dates in extras",
            honesty="Lock dates block posting in closed periods. Preview shows current vs proposed.",
            extras={"model": "res.company", **extras},
        )

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState:
        state.phase = "mapped"
        state.message = "Lock dates use extras, not column map"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        current = read_company_lock_dates(client)
        proposed = {
            k: (state.extras.get(k) or None)
            for k in _LOCK_FIELDS
        }
        # normalize empty string → None
        proposed = {k: (str(v)[:10] if v else None) for k, v in proposed.items()}
        if not any(proposed.values()):
            state.errors.append(
                RowError(
                    row_index=0,
                    code="blocking",
                    message="Provide at least one of period_lock_date, fiscalyear_lock_date, tax_lock_date",
                )
            )
            state.phase = "failed"
            return state
        state.extras["current_lock_dates"] = current
        state.extras["proposed_lock_dates"] = proposed
        state.phase = "validated"
        state.message = "Lock date proposal validated"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        state.message = (
            f"Dry-run: would write {state.extras.get('proposed_lock_dates')} "
            f"(current={state.extras.get('current_lock_dates')})"
        )
        return state

    def apply(
        self,
        state: BatchJobState,
        client: Any,
        *,
        post_after_create: bool = False,
    ) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        proposed = state.extras.get("proposed_lock_dates") or {}
        vals = {k: v for k, v in proposed.items() if v}
        if not client.model_exists("res.company"):
            state.errors.append(
                RowError(row_index=0, code="blocking", message="res.company missing")
            )
            state.phase = "failed"
            return state
        ids = client.execute_kw("res.company", "search", [[]], {"limit": 1})
        if not ids:
            state.errors.append(
                RowError(row_index=0, code="blocking", message="No company found")
            )
            state.phase = "failed"
            return state
        client.execute_kw("res.company", "write", [ids, vals])
        state.phase = "applied"
        state.dry_run = False
        state.message = f"Wrote lock dates on company {ids[0]}: {vals}"
        state.honesty = HONESTY_PREVIEW_NE_POSTED
        return state
