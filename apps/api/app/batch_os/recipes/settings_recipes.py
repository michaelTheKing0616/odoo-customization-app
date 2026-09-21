"""Settings recipes — payment terms, pricelists, currency, sequences (public RPC)."""

from __future__ import annotations

import uuid
from typing import Any

from app.batch_os.types import HONESTY_PREVIEW_NE_POSTED, BatchJobState, RowError

_DEFAULT_PAYMENT_TERMS = [
    {"name": "Immediate Payment", "lines": [{"value": "balance", "value_amount": 0, "nb_days": 0}]},
    {"name": "15 Days", "lines": [{"value": "balance", "value_amount": 0, "nb_days": 15}]},
    {"name": "30 Days", "lines": [{"value": "balance", "value_amount": 0, "nb_days": 30}]},
    {"name": "45 Days", "lines": [{"value": "balance", "value_amount": 0, "nb_days": 45}]},
]


class PaymentTermsRecipe:
    id = "settings.payment_terms"
    risk = "L1"
    title = "Payment terms pack"
    blurb = "Create common account.payment.term rows (Immediate / 15 / 30 / 45). Dry-run first."
    atlas_class = "settings"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()),
            connection_id=connection_id,
            recipe_id=self.id,
            risk="L1",
            phase="intake",
            filename=filename or "payment_terms",
            headers=list(headers or []),
            raw_rows=list(rows or []),
            message="Payment terms pack ready. Dry-run proposes; apply creates missing terms.",
            honesty=HONESTY_PREVIEW_NE_POSTED,
            extras={"model": "account.payment.term", **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        state.message = "Payment terms use default pack (optional CSV name/nb_days)"
        return state

    def _proposals(self, state: BatchJobState) -> list[dict[str, Any]]:
        if state.raw_rows:
            out = []
            for row in state.raw_rows:
                name = row.get("name") or row.get("term") or "Term"
                days = int(float(row.get("nb_days") or row.get("days") or 0))
                out.append({"name": name, "lines": [{"value": "balance", "value_amount": 0, "nb_days": days}]})
            return out
        return list(_DEFAULT_PAYMENT_TERMS)

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not client.model_exists("account.payment.term"):
            state.errors.append(RowError(row_index=0, code="blocking", message="account.payment.term missing"))
            state.phase = "failed"
            return state
        props = self._proposals(state)
        existing = set()
        try:
            rows = client.execute_kw(
                "account.payment.term", "search_read",
                [[("name", "in", [p["name"] for p in props])]],
                {"fields": ["id", "name"], "limit": 50},
            )
            existing = {str(r.get("name")) for r in rows}
        except Exception:
            pass
        state.extras["would_create"] = [p for p in props if p["name"] not in existing]
        state.extras["would_skip"] = [p for p in props if p["name"] in existing]
        state.phase = "validated"
        state.message = f"Payment terms: {len(state.extras['would_create'])} create, {len(state.extras['would_skip'])} skip"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        state.message = f"Dry-run: would create {len(state.extras.get('would_create') or [])} payment term(s). Preview ≠ written."
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        created: list[int] = []
        for prop in state.extras.get("would_create") or []:
            vals = {"name": prop["name"]}
            # line_ids when model supports account.payment.term.line
            if client.model_exists("account.payment.term.line"):
                vals["line_ids"] = [(0, 0, line) for line in prop.get("lines") or []]
            try:
                tid = client.execute_kw("account.payment.term", "create", [vals])
                if isinstance(tid, list):
                    tid = tid[0]
                created.append(int(tid))
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=0, code="warn", message=f"Create term {prop['name']!r} failed: {exc}"))
        state.created_move_ids = created
        state.phase = "applied"
        state.dry_run = False
        state.message = f"Created {len(created)} payment term(s)"
        return state


class PricelistRecipe:
    id = "settings.pricelists"
    risk = "L1"
    title = "Pricelist pack"
    blurb = "Create basic product.pricelist rows when model exists. Graceful skip if Sales not installed."
    atlas_class = "settings"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L1",
            phase="intake", filename=filename or "pricelists", headers=list(headers or []), raw_rows=list(rows or []),
            message="Pricelist pack ready.", honesty=HONESTY_PREVIEW_NE_POSTED,
            extras={"model": "product.pricelist", **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not client.model_exists("product.pricelist"):
            state.warnings.append("product.pricelist missing — Sales pricelists not installed; skipping")
            state.extras["would_create"] = []
            state.phase = "validated"
            state.message = "Pricelists unavailable — graceful skip"
            return state
        names = [r.get("name") or "Public Pricelist" for r in state.raw_rows] if state.raw_rows else ["Public Pricelist", "USD Pricelist"]
        existing = set()
        try:
            rows = client.execute_kw(
                "product.pricelist", "search_read", [[("name", "in", names)]], {"fields": ["name"], "limit": 20}
            )
            existing = {str(r.get("name")) for r in rows}
        except Exception:
            pass
        state.extras["would_create"] = [{"name": n} for n in names if n not in existing]
        state.extras["would_skip"] = [{"name": n} for n in names if n in existing]
        state.phase = "validated"
        state.message = f"Pricelists: {len(state.extras['would_create'])} create"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        state.phase = "dry_run"
        state.dry_run = True
        state.message = f"Dry-run: would create {len(state.extras.get('would_create') or [])} pricelist(s)"
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        created: list[int] = []
        for prop in state.extras.get("would_create") or []:
            try:
                pid = client.execute_kw("product.pricelist", "create", [{"name": prop["name"]}])
                if isinstance(pid, list):
                    pid = pid[0]
                created.append(int(pid))
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=0, code="warn", message=str(exc)))
        state.created_move_ids = created
        state.phase = "applied"
        state.dry_run = False
        state.message = f"Created {len(created)} pricelist(s)"
        return state


class CurrencyBasicsRecipe:
    id = "settings.currency"
    risk = "L2"
    title = "Currency basics"
    blurb = "Activate res.currency codes and report company currency. Does not force-change company currency when moves exist."
    atlas_class = "settings"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        extras = dict(extras or {})
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L2",
            phase="intake", filename=filename or "currency", headers=list(headers or []), raw_rows=list(rows or []),
            message="Currency basics ready.", honesty=HONESTY_PREVIEW_NE_POSTED + " Company currency change blocked once journals/moves exist.",
            extras=extras,
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not client.model_exists("res.currency"):
            state.errors.append(RowError(row_index=0, code="blocking", message="res.currency missing"))
            state.phase = "failed"
            return state
        codes = [r.get("code") or r.get("currency") for r in state.raw_rows if (r.get("code") or r.get("currency"))]
        if not codes:
            codes = list(state.extras.get("activate_codes") or ["USD", "EUR", "NGN", "GBP"])
        codes = [c.upper() for c in codes]
        inactive = []
        try:
            rows = client.execute_kw(
                "res.currency", "search_read",
                [[("name", "in", codes)]],
                {"fields": ["id", "name", "active"], "limit": 20},
            )
            for r in rows:
                if not r.get("active"):
                    inactive.append(r)
            state.extras["found"] = rows
        except Exception as exc:  # noqa: BLE001
            state.warnings.append(f"Currency search failed: {exc}")
        company = None
        if client.model_exists("res.company"):
            try:
                companies = client.execute_kw(
                    "res.company", "search_read", [[]], {"fields": ["id", "name", "currency_id"], "limit": 1}
                )
                company = companies[0] if companies else None
            except Exception:
                pass
        state.extras["company"] = company
        state.extras["would_activate"] = inactive
        state.phase = "validated"
        state.message = f"Currency: {len(inactive)} to activate; company={company}"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        state.message = f"Dry-run: would activate {len(state.extras.get('would_activate') or [])} currency(ies). Company currency not force-changed."
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        activated: list[int] = []
        for row in state.extras.get("would_activate") or []:
            try:
                client.execute_kw("res.currency", "write", [[int(row["id"])], {"active": True}])
                activated.append(int(row["id"]))
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=0, code="warn", message=str(exc)))
        state.created_move_ids = activated
        state.phase = "applied"
        state.dry_run = False
        state.risk = "L2"
        state.message = f"Activated {len(activated)} currency(ies)"
        return state


class SequenceDefaultsRecipe:
    id = "settings.sequences"
    risk = "L1"
    title = "Sequence / document defaults"
    blurb = "List ir.sequence defaults via public RPC; optional prefix tweaks when explicitly provided."
    atlas_class = "settings"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L1",
            phase="intake", filename=filename or "sequences", headers=list(headers or []), raw_rows=list(rows or []),
            message="Sequence defaults ready.", honesty=HONESTY_PREVIEW_NE_POSTED,
            extras={"model": "ir.sequence", **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not client.model_exists("ir.sequence"):
            state.errors.append(RowError(row_index=0, code="blocking", message="ir.sequence missing"))
            state.phase = "failed"
            return state
        rows = []
        try:
            rows = client.execute_kw(
                "ir.sequence", "search_read", [[]],
                {"fields": ["id", "name", "code", "prefix", "padding", "number_next"], "limit": 40},
            )
        except Exception as exc:  # noqa: BLE001
            state.warnings.append(str(exc))
        state.extras["sequences"] = rows
        # Optional updates from raw_rows: code,prefix
        updates = []
        for row in state.raw_rows:
            code = row.get("code") or row.get("sequence")
            prefix = row.get("prefix")
            if code and prefix is not None:
                updates.append({"code": code, "prefix": prefix})
        state.extras["would_update"] = updates
        state.phase = "validated"
        state.message = f"Found {len(rows)} sequences; {len(updates)} prefix update(s) proposed"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        state.message = f"Dry-run: list {len(state.extras.get('sequences') or [])} sequences; would update {len(state.extras.get('would_update') or [])}"
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        updated: list[int] = []
        for prop in state.extras.get("would_update") or []:
            try:
                ids = client.execute_kw("ir.sequence", "search", [[("code", "=", prop["code"])]], {"limit": 1})
                if not ids:
                    continue
                client.execute_kw("ir.sequence", "write", [ids, {"prefix": prop["prefix"]}])
                updated.extend(int(i) for i in ids)
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=0, code="warn", message=str(exc)))
        state.created_move_ids = updated
        state.phase = "applied"
        state.dry_run = False
        state.message = f"Updated {len(updated)} sequence(s); catalog listed in extras.sequences"
        return state


class SettingsBoardRecipe:
    """Composite settings pack — runs payment terms + currency dry-run/apply."""

    id = "settings.board_apply"
    risk = "L2"
    title = "Settings board"
    blurb = "Composite: payment terms + currency activate + sequence list. Dry-run first."
    atlas_class = "settings"

    def __init__(self) -> None:
        self._terms = PaymentTermsRecipe()
        self._currency = CurrencyBasicsRecipe()
        self._sequences = SequenceDefaultsRecipe()
        self._pricelists = PricelistRecipe()

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L2",
            phase="intake", filename=filename or "settings_board", headers=list(headers or []), raw_rows=list(rows or []),
            message="Settings board ready (payment terms + currency + sequences + pricelists).",
            honesty=HONESTY_PREVIEW_NE_POSTED,
            extras=dict(extras or {}),
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def _run_children(self, state: BatchJobState, client: Any, *, dry: bool) -> BatchJobState:
        results = {}
        for key, recipe in (
            ("payment_terms", self._terms),
            ("pricelists", self._pricelists),
            ("currency", self._currency),
            ("sequences", self._sequences),
        ):
            child = recipe.intake(connection_id=state.connection_id, extras=state.extras)
            child = recipe.dry_run(child, client) if dry else recipe.apply(child, client)
            results[key] = {"phase": child.phase, "message": child.message, "created": list(child.created_move_ids)}
        state.extras["child_results"] = results
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self._run_children(state, client, dry=True)
        state.phase = "validated"
        state.message = "Settings board validated (child dry-runs)"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self._run_children(state, client, dry=True)
        state.phase = "dry_run"
        state.dry_run = True
        state.message = "Dry-run settings board complete — Preview ≠ written"
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self._run_children(state, client, dry=False)
        state.phase = "applied"
        state.dry_run = False
        state.risk = "L2"
        state.message = "Settings board applied (see extras.child_results)"
        return state
