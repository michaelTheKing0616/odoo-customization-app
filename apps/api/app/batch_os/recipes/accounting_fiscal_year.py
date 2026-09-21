"""Recipe accounting.fiscal_year — fiscal year / period awareness via public RPC.

Uses account.fiscal.year when present; otherwise documents company date fields
and lock-date relationship. Complements accounting.lock_dates.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.batch_os.types import HONESTY_PREVIEW_NE_POSTED, BatchJobState, RowError


class FiscalYearRecipe:
    id = "accounting.fiscal_year"
    risk = "L2"
    title = "Fiscal year"
    blurb = "Create/read account.fiscal.year when available; else report company date fields."
    atlas_class = "accounting"

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
            risk="L2",
            phase="intake",
            filename=filename or "fiscal_year",
            headers=list(headers or []),
            raw_rows=list(rows or []),
            message="Fiscal year recipe — supply name/date_from/date_to in extras",
            honesty=(
                "Fiscal year writes are L2. Prefer lock_dates for period close. "
                + HONESTY_PREVIEW_NE_POSTED
            ),
            extras={"model": "account.fiscal.year", **extras},
        )

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState:
        state.phase = "mapped"
        state.message = "Fiscal year uses extras (name, date_from, date_to)"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        name = state.extras.get("name") or ""
        date_from = state.extras.get("date_from") or ""
        date_to = state.extras.get("date_to") or ""
        has_fy_model = client.model_exists("account.fiscal.year")
        state.extras["has_fiscal_year_model"] = has_fy_model

        company_info: dict[str, Any] = {}
        if client.model_exists("res.company"):
            rows = client.execute_kw(
                "res.company",
                "search_read",
                [[]],
                {
                    "fields": [
                        "id",
                        "name",
                        "fiscalyear_last_day",
                        "fiscalyear_last_month",
                        "period_lock_date",
                        "fiscalyear_lock_date",
                        "tax_lock_date",
                    ],
                    "limit": 1,
                },
            )
            if rows:
                company_info = rows[0]
        state.extras["company"] = company_info

        if has_fy_model:
            existing = client.execute_kw(
                "account.fiscal.year",
                "search_read",
                [[]],
                {"fields": ["id", "name", "date_from", "date_to"], "limit": 20},
            )
            state.extras["existing_fiscal_years"] = existing
        else:
            state.extras["existing_fiscal_years"] = []
            state.warnings.append("account.fiscal.year not installed — report company fiscal fields only")

        if not name or not date_from or not date_to:
            # Allow dry-run that only reports current state
            state.extras["mode"] = "report_only"
            state.phase = "validated"
            state.message = "Fiscal year report-only (no name/date_from/date_to supplied)"
            return state

        state.extras["mode"] = "create"
        state.extras["proposed"] = {
            "name": name,
            "date_from": str(date_from)[:10],
            "date_to": str(date_to)[:10],
        }
        if not has_fy_model:
            state.errors.append(
                RowError(
                    row_index=0,
                    code="blocking",
                    message="Cannot create fiscal year: account.fiscal.year model missing",
                )
            )
            state.phase = "failed"
            return state
        state.phase = "validated"
        state.message = f"Fiscal year proposal validated: {name}"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        if state.extras.get("mode") == "report_only":
            state.message = (
                f"Dry-run report: company={state.extras.get('company')}, "
                f"existing_fy={len(state.extras.get('existing_fiscal_years') or [])}"
            )
        else:
            state.message = f"Dry-run: would create fiscal year {state.extras.get('proposed')}"
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
        if state.extras.get("mode") != "create":
            state.phase = "applied"
            state.dry_run = False
            state.message = "No fiscal year create requested (report-only)"
            return state
        proposed = state.extras.get("proposed") or {}
        fy_id = client.execute_kw("account.fiscal.year", "create", [proposed])
        if isinstance(fy_id, list):
            fy_id = fy_id[0]
        state.created_move_ids = [int(fy_id)]
        state.phase = "applied"
        state.dry_run = False
        state.risk = "L2"
        state.message = f"Created account.fiscal.year id={fy_id}"
        state.honesty = HONESTY_PREVIEW_NE_POSTED
        return state
