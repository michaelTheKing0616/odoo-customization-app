"""Declarative multi-step Power Ops recipes (Online UI workarounds via RPC)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

StepKind = Literal["method", "unlink", "write"]


@dataclass
class RecipeStep:
    kind: StepKind
    method: str | None = None  # for kind=method
    domain_extra: list[Any] | None = None  # AND with current ids' filter
    values: dict[str, Any] | None = None  # for write
    label: str = ""


@dataclass
class PowerRecipe:
    id: str
    name: str
    description: str
    model: str
    steps: list[RecipeStep]
    destructive: bool = True
    risks: list[str] = field(default_factory=list)
    requires_modules: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    min_major: int = 16


@dataclass
class StepLog:
    record_id: int
    step: str
    ok: bool
    error: str | None = None


@dataclass
class PowerOpsResult:
    ok: bool
    dry_run: bool
    processed: int
    succeeded: int
    failed: int
    logs: list[StepLog] = field(default_factory=list)
    message: str = ""
    available: bool = True
    unavailable_reason: str | None = None


def _recipes() -> dict[str, PowerRecipe]:
    return {
        "purge_journal_entries": PowerRecipe(
            id="purge_journal_entries",
            name="Purge journal entries",
            description=(
                "Reset posted account.move rows to draft, then unlink — "
                "the Online one-by-one pain killer."
            ),
            model="account.move",
            destructive=True,
            requires_modules=["account"],
            tags=["accounting", "destructive", "purge"],
            min_major=16,
            risks=[
                "Permanently deletes journal entries matching your domain",
                "Locked fiscal periods / reconciled items may fail per row",
                "Does not bypass accounting locks — failures are reported",
                "Irreversible data loss for successfully deleted rows",
            ],
            steps=[
                RecipeStep(
                    kind="method",
                    method="button_draft",
                    label="Reset to draft",
                ),
                RecipeStep(kind="unlink", label="Delete drafts"),
            ],
        ),
        "mass_archive": PowerRecipe(
            id="mass_archive",
            name="Mass archive records",
            description="Set active=False on matching records (partners, products, custom models).",
            model="*",  # caller overrides model
            destructive=False,
            tags=["generic", "archive"],
            risks=["Hides records from default views; can usually be unarchived"],
            steps=[
                RecipeStep(
                    kind="write",
                    values={"active": False},
                    label="Archive",
                )
            ],
        ),
        "mass_unarchive": PowerRecipe(
            id="mass_unarchive",
            name="Mass unarchive records",
            description="Set active=True on matching records.",
            model="*",
            destructive=False,
            tags=["generic", "archive"],
            risks=["Restores archived records into active lists"],
            steps=[
                RecipeStep(
                    kind="write",
                    values={"active": True},
                    label="Unarchive",
                )
            ],
        ),
        "mass_unlink": PowerRecipe(
            id="mass_unlink",
            name="Mass delete records",
            description="Unlink matching records (draft-safe models). Prefer specific recipes for posted accounting docs.",
            model="*",
            destructive=True,
            tags=["generic", "destructive"],
            risks=[
                "Permanent deletion",
                "May fail on constrained / posted documents — use purge recipes instead",
            ],
            steps=[RecipeStep(kind="unlink", label="Delete")],
        ),
        "cancel_account_moves": PowerRecipe(
            id="cancel_account_moves",
            name="Cancel journal entries / invoices",
            description="Call button_cancel on account.move (where allowed).",
            model="account.move",
            destructive=True,
            requires_modules=["account"],
            tags=["accounting", "destructive"],
            risks=["Cancels posted moves where Odoo allows; locked periods may block"],
            steps=[
                RecipeStep(kind="method", method="button_cancel", label="Cancel"),
            ],
        ),
        "reset_and_cancel_moves": PowerRecipe(
            id="reset_and_cancel_moves",
            name="Reset to draft then cancel",
            description="button_draft then button_cancel on account.move — for stubborn Online UI flows.",
            model="account.move",
            destructive=True,
            requires_modules=["account"],
            tags=["accounting", "destructive"],
            risks=["Mutates accounting documents; fiscal locks may fail per row"],
            steps=[
                RecipeStep(kind="method", method="button_draft", label="Reset to draft"),
                RecipeStep(kind="method", method="button_cancel", label="Cancel"),
            ],
        ),
        "post_account_moves": PowerRecipe(
            id="post_account_moves",
            name="Post draft journal entries",
            description="Call action_post on draft account.move rows.",
            model="account.move",
            destructive=False,
            requires_modules=["account"],
            tags=["accounting"],
            risks=["Posts accounting entries; hard to reverse without cancel/draft"],
            steps=[
                RecipeStep(kind="method", method="action_post", label="Post"),
            ],
        ),
        "unreconcile_and_draft": PowerRecipe(
            id="unreconcile_and_draft",
            name="Button draft (after unlock attempts)",
            description=(
                "Calls button_draft on account.move. Use when Online UI blocks bulk draft reset."
            ),
            model="account.move",
            destructive=True,
            requires_modules=["account"],
            tags=["accounting", "destructive"],
            risks=["May fail on reconciled/locked moves — failures reported per row"],
            steps=[
                RecipeStep(kind="method", method="button_draft", label="Reset to draft"),
            ],
        ),
        "drop_mail_messages": PowerRecipe(
            id="drop_mail_messages",
            name="Delete chatter messages",
            description="Unlink mail.message rows matching a domain (cleanup spam/test chatter).",
            model="mail.message",
            destructive=True,
            requires_modules=["mail"],
            tags=["mail", "destructive"],
            risks=["Permanent chatter deletion", "Can remove audit trail notes"],
            min_major=16,
            steps=[RecipeStep(kind="unlink", label="Delete messages")],
        ),
        "drop_attachments": PowerRecipe(
            id="drop_attachments",
            name="Delete attachments",
            description="Unlink ir.attachment rows (e.g. test uploads).",
            model="ir.attachment",
            destructive=True,
            tags=["generic", "destructive"],
            risks=["Permanent file/attachment deletion"],
            steps=[RecipeStep(kind="unlink", label="Delete attachments")],
        ),
        "deactivate_users": PowerRecipe(
            id="deactivate_users",
            name="Deactivate users",
            description="Set active=False on res.users (never use on admin without care).",
            model="res.users",
            destructive=True,
            tags=["users", "destructive"],
            risks=["Locks users out of Odoo", "Do not deactivate your own admin session user"],
            steps=[
                RecipeStep(
                    kind="write",
                    values={"active": False},
                    label="Deactivate",
                )
            ],
        ),
        # --- mastery M4 packs ---
        "mass_archive_partners": PowerRecipe(
            id="mass_archive_partners",
            name="Mass archive partners",
            description="Set active=False on res.partner (contacts pack).",
            model="res.partner",
            destructive=True,
            tags=["contacts", "pack", "destructive"],
            risks=["Hides partners from default searches", "May affect related documents"],
            min_major=16,
            steps=[
                RecipeStep(
                    kind="write",
                    values={"active": False},
                    label="Archive partners",
                )
            ],
        ),
        "drop_mail_activities_done": PowerRecipe(
            id="drop_mail_activities_done",
            name="Delete done activities",
            description="Unlink mail.activity rows (cleanup pack). Prefer domain active=False or done.",
            model="mail.activity",
            destructive=True,
            tags=["mail", "pack", "destructive"],
            requires_modules=["mail"],
            risks=["Permanent activity history deletion"],
            min_major=16,
            steps=[RecipeStep(kind="unlink", label="Delete activities")],
        ),
        "reset_sequences_next": PowerRecipe(
            id="reset_sequences_next",
            name="Bump sequence number_next",
            description="Write number_next on ir.sequence (admin pack — confirm carefully).",
            model="ir.sequence",
            destructive=True,
            tags=["admin", "pack", "destructive"],
            risks=["Can break document numbering", "Never run blindly on production"],
            min_major=16,
            steps=[
                RecipeStep(
                    kind="write",
                    values={"number_next": 1},
                    label="Reset number_next to 1",
                )
            ],
        ),
        # --- M4-P1: module-gated packs (website / project) ---
        "unpublish_website_pages": PowerRecipe(
            id="unpublish_website_pages",
            name="Unpublish website pages",
            description="Set is_published=False on website.page rows (requires website).",
            model="website.page",
            destructive=True,
            requires_modules=["website"],
            tags=["website", "pack", "destructive"],
            risks=["Hides pages from public visitors", "Does not delete page content"],
            min_major=16,
            steps=[
                RecipeStep(
                    kind="write",
                    values={"is_published": False},
                    label="Unpublish pages",
                )
            ],
        ),
        "mass_archive_project_tasks": PowerRecipe(
            id="mass_archive_project_tasks",
            name="Mass archive project tasks",
            description="Set active=False on project.task (requires project).",
            model="project.task",
            destructive=True,
            requires_modules=["project"],
            tags=["project", "pack", "destructive"],
            risks=["Hides tasks from default project views", "Usually reversible via unarchive"],
            min_major=16,
            steps=[
                RecipeStep(
                    kind="write",
                    values={"active": False},
                    label="Archive tasks",
                )
            ],
        ),
    }


def list_recipes() -> list[dict[str, Any]]:
    out = []
    for r in _recipes().values():
        out.append(
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "model": r.model,
                "destructive": r.destructive,
                "risks": r.risks,
                "requires_modules": r.requires_modules,
                "tags": list(r.tags),
                "min_major": r.min_major,
                "steps": [
                    {
                        "kind": s.kind,
                        "method": s.method,
                        "label": s.label or s.kind,
                        "values": s.values,
                    }
                    for s in r.steps
                ],
            }
        )
    return out


def get_recipe(recipe_id: str) -> PowerRecipe | None:
    return _recipes().get(recipe_id)


def probe_recipe(client: OdooClient, recipe: PowerRecipe, model: str) -> tuple[bool, str]:
    """Return (available, reason). Prefer available when RPC can run."""
    major = getattr(getattr(client, "capabilities", None), "major", None)
    if major is not None and int(major) < int(recipe.min_major):
        return (
            False,
            f"Recipe requires Odoo ≥{recipe.min_major}; connection is major {major}",
        )
    if not client.model_exists(model):
        return False, f"Model {model} not installed on this database"
    for mod in recipe.requires_modules:
        # Module presence inferred via model; also try ir.module.module when listed
        rows = client.execute_kw(
            "ir.module.module",
            "search_read",
            [[("name", "=", mod)]],
            {"fields": ["state"], "limit": 1},
        )
        if not rows:
            return False, f"Module {mod} is not installed (absent)"
        if rows[0].get("state") not in {"installed", "to upgrade", "to remove"}:
            return False, f"Module {mod} is not installed (state={rows[0].get('state')})"
    for step in recipe.steps:
        if step.kind == "method" and step.method:
            # Confirm method is advertised on the model (Odoo fields_get / get doesn't list
            # methods; probe via checking model has records searchable — method errors at run).
            try:
                client.execute_kw(model, "check_access_rights", ["write"], {"raise_exception": False})
            except Exception as exc:  # noqa: BLE001
                return False, f"Write access probe failed: {exc}"
    return True, "RPC available (UI limits do not block this app)"


def run_recipe(
    client: OdooClient,
    *,
    recipe_id: str,
    model: str | None = None,
    domain: list[Any] | None = None,
    ids: list[int] | None = None,
    dry_run: bool = True,
    batch_size: int = 40,
    continue_on_error: bool = True,
) -> PowerOpsResult:
    recipe = get_recipe(recipe_id)
    if recipe is None:
        raise OdooClientError(f"Unknown recipe {recipe_id}")
    target_model = model or (None if recipe.model == "*" else recipe.model)
    if not target_model or target_model == "*":
        raise OdooClientError("model is required for this recipe")

    batch_size = max(1, min(int(batch_size or 40), 200))

    available, reason = probe_recipe(client, recipe, target_model)
    if not available:
        return PowerOpsResult(
            ok=False,
            dry_run=dry_run,
            processed=0,
            succeeded=0,
            failed=0,
            message=reason,
            available=False,
            unavailable_reason=reason,
        )

    if ids:
        record_ids = [int(i) for i in ids]
    else:
        record_ids = [
            int(i)
            for i in client.execute_kw(
                target_model,
                "search",
                [domain or []],
                {"limit": 10000},
            )
        ]

    logs: list[StepLog] = []
    succeeded = 0
    failed = 0

    if dry_run:
        for rid in record_ids:
            for step in recipe.steps:
                logs.append(
                    StepLog(
                        record_id=int(rid),
                        step=step.label or step.kind,
                        ok=True,
                        error=None,
                    )
                )
            succeeded += 1
        return PowerOpsResult(
            ok=True,
            dry_run=True,
            processed=len(record_ids),
            succeeded=succeeded,
            failed=0,
            logs=logs,
            message=(
                f"Dry-run: would process {len(record_ids)} record(s) via {recipe.name} "
                f"(batch_size={batch_size})"
            ),
            available=True,
        )

    # When continue_on_error: per-id for accurate reports.
    # When not: batch write/method/unlink for speed.
    if continue_on_error:
        for rid in record_ids:
            row_ok = True
            for step in recipe.steps:
                label = step.label or step.kind
                try:
                    _exec_step(client, target_model, step, [int(rid)])
                    logs.append(StepLog(record_id=int(rid), step=label, ok=True))
                except Exception as exc:  # noqa: BLE001
                    row_ok = False
                    failed += 1
                    logs.append(
                        StepLog(
                            record_id=int(rid),
                            step=label,
                            ok=False,
                            error=str(exc),
                        )
                    )
                    break
            if row_ok:
                succeeded += 1
    else:
        pending = list(record_ids)
        for step in recipe.steps:
            label = step.label or step.kind
            next_ok: list[int] = []
            for i in range(0, len(pending), batch_size):
                chunk = pending[i : i + batch_size]
                try:
                    _exec_step(client, target_model, step, chunk)
                    for rid in chunk:
                        logs.append(StepLog(record_id=rid, step=label, ok=True))
                        next_ok.append(rid)
                except Exception as exc:  # noqa: BLE001
                    # Fall back to per-id inside the failing chunk
                    for rid in chunk:
                        try:
                            _exec_step(client, target_model, step, [rid])
                            logs.append(StepLog(record_id=rid, step=label, ok=True))
                            next_ok.append(rid)
                        except Exception as row_exc:  # noqa: BLE001
                            failed += 1
                            logs.append(
                                StepLog(
                                    record_id=rid,
                                    step=label,
                                    ok=False,
                                    error=str(row_exc),
                                )
                            )
                            return PowerOpsResult(
                                ok=False,
                                dry_run=False,
                                processed=len(record_ids),
                                succeeded=succeeded,
                                failed=failed,
                                logs=logs,
                                message=f"Stopped on error at id={rid}: {row_exc}",
                                available=True,
                            )
            pending = next_ok
        succeeded = len(pending)

    return PowerOpsResult(
        ok=failed == 0,
        dry_run=False,
        processed=len(record_ids),
        succeeded=succeeded,
        failed=failed,
        logs=logs,
        message=(
            f"{recipe.name}: {succeeded} ok, {failed} failed "
            f"of {len(record_ids)} record(s)"
        ),
        available=True,
    )


def _exec_step(
    client: OdooClient, model: str, step: RecipeStep, ids: list[int]
) -> None:
    if step.kind == "method":
        if not step.method:
            raise OdooClientError("method step missing method name")
        client.execute_kw(model, step.method, [ids])
    elif step.kind == "unlink":
        client.execute_kw(model, "unlink", [ids])
    elif step.kind == "write":
        client.execute_kw(model, "write", [ids, dict(step.values or {})])
    else:
        raise OdooClientError(f"Unknown step kind {step.kind}")


def probe_connection_capabilities(client: OdooClient) -> dict[str, Any]:
    """Prefer RPC-available greens; refuse only true impossibles."""
    version = {}
    try:
        version = client.server_version()
    except Exception:  # noqa: BLE001
        version = {}
    recipe_status = []
    for r in list_recipes():
        model = r["model"] if r["model"] != "*" else "res.partner"
        recipe = get_recipe(r["id"])
        assert recipe
        ok, reason = probe_recipe(client, recipe, model)
        recipe_status.append(
            {
                "id": r["id"],
                "name": r["name"],
                "available": ok,
                "reason": reason,
                "model": model,
            }
        )
    return {
        "server_version": version.get("server_version"),
        "series": str(version.get("server_version", ""))[:2],
        "custom_python_modules": {
            "likely_available_on": ["odoo.sh", "self-hosted"],
            "may_be_blocked_on": ["odoo_online_some_plans"],
            "workaround": "Use Power Ops RPC recipes and data-mode exports instead of live Python",
        },
        "power_ops_recipes": recipe_status,
        "philosophy": (
            "Online UI limits are not API limits. "
            "This app orchestrates the same RPC you would run on Odoo.sh."
        ),
    }
