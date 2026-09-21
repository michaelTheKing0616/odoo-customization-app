"""Access & company recipes — users/groups + multi-company basics (public RPC, L2/L3 caution)."""

from __future__ import annotations

import uuid
from typing import Any

from app.batch_os.types import HONESTY_PREVIEW_NE_POSTED, BatchJobState, RowError


class UsersGroupsRecipe:
    id = "access_company.users"
    risk = "L2"
    title = "Users & groups"
    blurb = (
        "Invite/create res.users and assign res.groups via public RPC. "
        "L2 — dry-run first; never invent passwords in logs."
    )
    atlas_class = "access_company"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L2",
            phase="intake", filename=filename or "users", headers=list(headers or []), raw_rows=list(rows or []),
            message="Users pack ready. Provide login,name,groups (comma). Dry-run first.",
            honesty="L2: creating users has access impact. " + HONESTY_PREVIEW_NE_POSTED,
            extras={"model": "res.users", **(extras or {})},
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not client.model_exists("res.users"):
            state.errors.append(RowError(row_index=0, code="blocking", message="res.users missing"))
            state.phase = "failed"
            return state
        proposals = []
        for idx, row in enumerate(state.raw_rows or [], start=1):
            login = (row.get("login") or row.get("email") or "").strip()
            name = (row.get("name") or login).strip()
            groups = [g.strip() for g in (row.get("groups") or row.get("group") or "").split(",") if g.strip()]
            if not login:
                state.errors.append(RowError(row_index=idx, field="login", code="blocking", message="login required"))
                continue
            proposals.append({"row_index": idx, "login": login, "name": name, "groups": groups})
        # Also allow extras.users list
        for u in state.extras.get("users") or []:
            proposals.append(u)
        existing = {}
        if proposals:
            try:
                rows = client.execute_kw(
                    "res.users", "search_read",
                    [[("login", "in", [p["login"] for p in proposals])]],
                    {"fields": ["id", "login"], "limit": 100},
                )
                existing = {str(r["login"]): int(r["id"]) for r in rows}
            except Exception:
                pass
        would_create, would_update = [], []
        for p in proposals:
            if p["login"] in existing:
                p["user_id"] = existing[p["login"]]
                p["action"] = "update_groups"
                would_update.append(p)
            else:
                p["action"] = "create"
                would_create.append(p)
        state.extras["would_create"] = would_create
        state.extras["would_update"] = would_update
        if any(e.code == "blocking" for e in state.errors):
            state.phase = "failed"
            return state
        state.phase = "validated"
        state.message = f"Users: {len(would_create)} create, {len(would_update)} group-update"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        state.message = (
            f"Dry-run: would create {len(state.extras.get('would_create') or [])} users, "
            f"update groups on {len(state.extras.get('would_update') or [])}. Preview ≠ written."
        )
        return state

    def _resolve_group_ids(self, client: Any, names: list[str]) -> list[int]:
        if not names or not client.model_exists("res.groups"):
            return []
        ids: list[int] = []
        for name in names:
            rows = client.execute_kw(
                "res.groups", "search_read",
                [["|", ("full_name", "ilike", name), ("name", "=", name)]],
                {"fields": ["id"], "limit": 1},
            )
            if rows:
                ids.append(int(rows[0]["id"]))
        return ids

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        created: list[int] = []
        for prop in state.extras.get("would_create") or []:
            vals = {
                "name": prop["name"],
                "login": prop["login"],
                # Odoo requires password on create — use placeholder; operator must reset.
                "password": prop.get("password") or f"ChangeMe-{uuid.uuid4().hex[:8]}",
            }
            gids = self._resolve_group_ids(client, prop.get("groups") or [])
            if gids:
                vals["groups_id"] = [(6, 0, gids)]
            try:
                uid = client.execute_kw("res.users", "create", [vals])
                if isinstance(uid, list):
                    uid = uid[0]
                created.append(int(uid))
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=int(prop.get("row_index") or 0), code="warn", message=f"Create user failed: {exc}"))
        for prop in state.extras.get("would_update") or []:
            gids = self._resolve_group_ids(client, prop.get("groups") or [])
            if not gids:
                continue
            try:
                client.execute_kw("res.users", "write", [[int(prop["user_id"])], {"groups_id": [(6, 0, gids)]}])
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=int(prop.get("row_index") or 0), code="warn", message=str(exc)))
        state.created_move_ids = created
        state.phase = "applied"
        state.dry_run = False
        state.risk = "L2"
        state.message = f"Created {len(created)} user(s); group assignments applied where requested"
        state.warnings.append("New user passwords are one-time placeholders — force reset out-of-band.")
        return state


class MultiCompanyLinkRecipe:
    id = "access_company.multi_company"
    risk = "L2"
    title = "Multi-company link"
    blurb = "List companies and optionally link a user to company_ids via public RPC."
    atlas_class = "access_company"

    def intake(self, *, connection_id: str, filename: str = "", headers=None, rows=None, extras=None) -> BatchJobState:
        return BatchJobState(
            job_id=str(uuid.uuid4()), connection_id=connection_id, recipe_id=self.id, risk="L2",
            phase="intake", filename=filename or "multi_company", headers=list(headers or []), raw_rows=list(rows or []),
            message="Multi-company helper ready.", honesty=HONESTY_PREVIEW_NE_POSTED,
            extras=dict(extras or {}),
        )

    def map(self, state: BatchJobState, column_map=None) -> BatchJobState:
        state.phase = "mapped"
        return state

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState:
        if not client.model_exists("res.company"):
            state.errors.append(RowError(row_index=0, code="blocking", message="res.company missing"))
            state.phase = "failed"
            return state
        companies = client.execute_kw(
            "res.company", "search_read", [[]], {"fields": ["id", "name", "currency_id"], "limit": 50}
        )
        state.extras["companies"] = companies
        links = []
        for row in state.raw_rows:
            login = row.get("login") or row.get("user")
            company = row.get("company") or row.get("company_name")
            if login and company:
                links.append({"login": login, "company": company})
        state.extras["would_link"] = links
        state.phase = "validated"
        state.message = f"{len(companies)} companies; {len(links)} user-company link(s) proposed"
        return state

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState:
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        state.phase = "dry_run"
        state.dry_run = True
        state.message = f"Dry-run: {len(state.extras.get('would_link') or [])} link(s). Preview ≠ written."
        return state

    def apply(self, state: BatchJobState, client: Any, *, post_after_create: bool = False) -> BatchJobState:
        del post_after_create
        state = self.validate(state, client)
        if any(e.code == "blocking" for e in state.errors):
            return state
        linked = 0
        for prop in state.extras.get("would_link") or []:
            try:
                users = client.execute_kw(
                    "res.users", "search_read", [[("login", "=", prop["login"])]], {"fields": ["id", "company_ids"], "limit": 1}
                )
                cos = client.execute_kw(
                    "res.company", "search_read", [[("name", "ilike", prop["company"])]], {"fields": ["id"], "limit": 1}
                )
                if not users or not cos:
                    state.errors.append(RowError(row_index=0, code="warn", message=f"Skip link {prop}"))
                    continue
                uid = int(users[0]["id"])
                cid = int(cos[0]["id"])
                existing = users[0].get("company_ids") or []
                if isinstance(existing, list) and existing and isinstance(existing[0], (list, tuple)):
                    existing = [e[0] for e in existing]
                new_ids = sorted(set(int(x) for x in existing) | {cid})
                client.execute_kw("res.users", "write", [[uid], {"company_ids": [(6, 0, new_ids)]}])
                linked += 1
            except Exception as exc:  # noqa: BLE001
                state.errors.append(RowError(row_index=0, code="warn", message=str(exc)))
        state.phase = "applied"
        state.dry_run = False
        state.risk = "L2"
        state.message = f"Linked {linked} user-company membership(s)"
        return state
