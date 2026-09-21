"""Recipe accounting.tax_pack — structure for tax creation via public RPC.

NG/generic stub: dry-run proposes account.tax vals; apply creates only when
explicitly confirmed. Never invents l10n tax packs from whole cloth — honesty
says align to localization when available.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.batch_os.types import HONESTY_PREVIEW_NE_POSTED, BatchJobState, RowError

# Generic / NG-oriented starter rows (dry-run proposals only until apply)
_DEFAULT_PACK: list[dict[str, Any]] = [
    {
        "name": "VAT 7.5%",
        "amount": 7.5,
        "amount_type": "percent",
        "type_tax_use": "sale",
        "country_code": "NG",
    },
    {
        "name": "VAT 7.5% (purchase)",
        "amount": 7.5,
        "amount_type": "percent",
        "type_tax_use": "purchase",
        "country_code": "NG",
    },
]


class TaxPackRecipe:
    id = "accounting.tax_pack"
    risk = "L2"
    title = "Tax pack"
    blurb = (
        "Propose account.tax rows via RPC (NG/generic starter). "
        "Prefer l10n localization — never invent a full fiscal pack."
    )
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
        country = (extras.get("country_code") or "NG").upper()
        return BatchJobState(
            job_id=str(uuid.uuid4()),
            connection_id=connection_id,
            recipe_id=self.id,
            risk="L2",
            phase="intake",
            filename=filename or f"tax_pack_{country}",
            headers=list(headers or []),
            raw_rows=list(rows or []),
            message=f"Tax pack ready (country={country}). Dry-run proposes; apply creates.",
            honesty=(
                "Tax pack proposes account.tax structure only. "
                "Prefer installing l10n_* localization. Preview ≠ posted. "
                + HONESTY_PREVIEW_NE_POSTED
            ),
            extras={"model": "account.tax", "country_code": country, **extras},
        )

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState:
        state.phase = "mapped"
        state.message = "Tax pack uses extras / default pack (column map optional)"
        return state

    def _proposals(self, state: BatchJobState) -> list[dict[str, Any]]:
        country = (state.extras.get("country_code") or "NG").upper()
        if state.raw_rows:
            props = []
            for row in state.raw_rows:
                props.append(
                    {
                        "name": row.get("name") or row.get("tax") or "Tax",
                        "amount": float(row.get("amount") or 0),
                        "amount_type": row.get("amount_type") or "percent",
                        "type_tax_use": row.get("type_tax_use") or row.get("use") or "sale",
                        "country_code": country,
                    }
                )
            return props
        return [{**p, "country_code": country} for p in _DEFAULT_PACK]

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not client.model_exists("account.tax"):
            state.errors.append(
                RowError(
                    row_index=0,
                    code="blocking",
                    message="account.tax missing — install Accounting",
                )
            )
            state.phase = "failed"
            return state
        props = self._proposals(state)
        # Check existing taxes to avoid blind duplicates
        existing_names: set[str] = set()
        try:
            rows = client.execute_kw(
                "account.tax",
                "search_read",
                [[("name", "in", [p["name"] for p in props])]],
                {"fields": ["id", "name"], "limit": 50},
            )
            existing_names = {str(r.get("name")) for r in rows}
        except Exception:
            pass
        state.extras["proposed_taxes"] = props
        state.extras["existing_tax_names"] = sorted(existing_names)
        state.extras["would_create"] = [p for p in props if p["name"] not in existing_names]
        state.extras["would_skip"] = [p for p in props if p["name"] in existing_names]
        if not props:
            state.errors.append(
                RowError(row_index=0, code="blocking", message="No tax proposals")
            )
            state.phase = "failed"
            return state
        state.phase = "validated"
        state.message = (
            f"Tax pack: {len(state.extras['would_create'])} to create, "
            f"{len(state.extras['would_skip'])} already exist"
        )
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        state.message = (
            f"Dry-run: would create {len(state.extras.get('would_create') or [])} account.tax "
            f"(skip {len(state.extras.get('would_skip') or [])}). "
            "Prefer l10n localization when available. Preview ≠ posted."
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
        created: list[int] = []
        for prop in state.extras.get("would_create") or []:
            vals = {
                "name": prop["name"],
                "amount": prop["amount"],
                "amount_type": prop.get("amount_type") or "percent",
                "type_tax_use": prop.get("type_tax_use") or "sale",
            }
            try:
                tid = client.execute_kw("account.tax", "create", [vals])
                if isinstance(tid, list):
                    tid = tid[0]
                created.append(int(tid))
            except Exception as exc:  # noqa: BLE001
                state.errors.append(
                    RowError(
                        row_index=0,
                        code="warn",
                        message=f"Failed to create tax {prop['name']!r}: {exc}",
                    )
                )
        state.created_move_ids = created
        state.phase = "applied"
        state.dry_run = False
        state.risk = "L2"
        state.message = f"Created {len(created)} account.tax record(s)"
        state.honesty = HONESTY_PREVIEW_NE_POSTED
        return state
