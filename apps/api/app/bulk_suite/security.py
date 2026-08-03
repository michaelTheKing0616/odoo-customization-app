"""Bulk res.groups membership changes with diff preview (BLK-6)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.transitions import BulkRunResult, BulkSuiteError, PerRecordResult

SecurityMode = Literal["add", "remove", "offboard"]


class SecurityValidationError(BulkSuiteError):
    pass


@dataclass
class GroupRef:
    id: int
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name}


@dataclass
class UserSecurityDiff:
    user_id: int
    user_name: str
    add_groups: list[GroupRef] = field(default_factory=list)
    remove_groups: list[GroupRef] = field(default_factory=list)
    implied_warnings: list[str] = field(default_factory=list)
    deactivate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "add_groups": [g.to_dict() for g in self.add_groups],
            "remove_groups": [g.to_dict() for g in self.remove_groups],
            "implied_warnings": list(self.implied_warnings),
            "deactivate": self.deactivate,
        }


@dataclass
class SecurityPreviewResult:
    mode: str
    users: list[UserSecurityDiff]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "users": [u.to_dict() for u in self.users],
            "message": self.message,
        }


@dataclass
class SecurityApplyResult(BulkRunResult):
    mode: str = "add"
    preview_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["mode"] = self.mode
        data["preview_message"] = self.preview_message
        return data


def _group_name_map(client: OdooClient, group_ids: set[int]) -> dict[int, str]:
    if not group_ids:
        return {}
    rows = client.execute_kw(
        "res.groups",
        "read",
        [list(group_ids)],
        {"fields": ["name", "full_name"]},
    )
    out: dict[int, str] = {}
    for row in rows:
        out[int(row["id"])] = str(row.get("full_name") or row.get("name") or row["id"])
    return out


def _base_group_ids(client: OdooClient) -> set[int]:
    try:
        rows = client.execute_kw(
            "ir.model.data",
            "search_read",
            [[("module", "=", "base"), ("model", "=", "res.groups")]],
            {"fields": ["res_id"], "limit": 500},
        )
        return {int(r["res_id"]) for r in rows if r.get("res_id")}
    except OdooClientError:
        return set()


def _implied_warnings(
    client: OdooClient,
    *,
    add_group_ids: set[int],
    current_group_ids: set[int],
) -> list[str]:
    if not add_group_ids:
        return []
    rows = client.execute_kw(
        "res.groups",
        "read",
        [list(add_group_ids)],
        {"fields": ["name", "full_name", "implied_ids"]},
    )
    implied_map = _group_name_map(
        client,
        {
            int(i)
            for row in rows
            for i in (row.get("implied_ids") or [])
            if int(i) not in current_group_ids
        },
    )
    warnings: list[str] = []
    for row in rows:
        label = str(row.get("full_name") or row.get("name") or row["id"])
        implied = [int(i) for i in (row.get("implied_ids") or [])]
        extra = [implied_map[i] for i in implied if i in implied_map]
        if extra:
            warnings.append(
                f"Adding {label!r} also implies: {', '.join(extra)} "
                "(implied_ids are not edited directly)"
            )
    return warnings


def preview_security_changes(
    client: OdooClient,
    *,
    user_ids: list[int],
    group_ids: list[int],
    mode: SecurityMode = "add",
    deactivate: bool = False,
) -> SecurityPreviewResult:
    uids = list(dict.fromkeys(int(u) for u in user_ids))
    gids = list(dict.fromkeys(int(g) for g in group_ids))
    if not uids:
        raise SecurityValidationError("user_ids must not be empty")
    if mode in {"add", "remove"} and not gids:
        raise SecurityValidationError("group_ids must not be empty for add/remove mode")

    user_rows = client.execute_kw(
        "res.users",
        "read",
        [uids],
        {"fields": ["name", "login", "groups_id", "active"]},
    )
    found = {int(r["id"]) for r in user_rows}
    missing = [u for u in uids if u not in found]
    if missing:
        raise SecurityValidationError(f"User id(s) not found: {missing[:5]}")

    all_group_ids: set[int] = set(gids)
    for row in user_rows:
        all_group_ids.update(int(i) for i in (row.get("groups_id") or []))
    group_names = _group_name_map(client, all_group_ids)
    base_ids = _base_group_ids(client)

    diffs: list[UserSecurityDiff] = []
    for row in user_rows:
        uid = int(row["id"])
        label = str(row.get("name") or row.get("login") or uid)
        current = {int(i) for i in (row.get("groups_id") or [])}
        add: list[GroupRef] = []
        remove: list[GroupRef] = []
        implied: list[str] = []

        if mode == "add":
            for gid in gids:
                if gid not in current:
                    add.append(GroupRef(id=gid, name=group_names.get(gid, str(gid))))
            implied = _implied_warnings(client, add_group_ids=set(gids), current_group_ids=current)
        elif mode == "remove":
            for gid in gids:
                if gid in current:
                    remove.append(GroupRef(id=gid, name=group_names.get(gid, str(gid))))
        elif mode == "offboard":
            for gid in sorted(current - base_ids):
                remove.append(GroupRef(id=gid, name=group_names.get(gid, str(gid))))
        else:
            raise SecurityValidationError(f"Unknown mode {mode!r}")

        diffs.append(
            UserSecurityDiff(
                user_id=uid,
                user_name=label,
                add_groups=add,
                remove_groups=remove,
                implied_warnings=implied,
                deactivate=bool(deactivate) if mode == "offboard" else False,
            )
        )

    return SecurityPreviewResult(
        mode=mode,
        users=diffs,
        message=(
            f"Security preview ({mode}): {len(diffs)} user(s); "
            f"{sum(len(u.add_groups) for u in diffs)} group add(s), "
            f"{sum(len(u.remove_groups) for u in diffs)} group remove(s)"
        ),
    )


def apply_security_changes(
    client: OdooClient,
    *,
    user_ids: list[int],
    group_ids: list[int],
    mode: SecurityMode = "add",
    deactivate: bool = False,
    dry_run: bool = True,
    preview_acknowledged: bool = False,
    run_id: str | None = None,
) -> SecurityApplyResult:
    if not preview_acknowledged and not dry_run:
        raise SecurityValidationError(
            "preview_acknowledged=true is required — call /bulk/security/preview first "
            "and review the diff before apply"
        )

    preview = preview_security_changes(
        client,
        user_ids=user_ids,
        group_ids=group_ids,
        mode=mode,
        deactivate=deactivate,
    )
    run_id = run_id or str(uuid.uuid4())
    per_record: list[PerRecordResult] = []
    succeeded = 0
    failed = 0

    for diff in preview.users:
        commands: list[Any] = []
        for g in diff.add_groups:
            commands.append((4, g.id))
        for g in diff.remove_groups:
            commands.append((3, g.id))
        vals: dict[str, Any] = {}
        if commands:
            vals["groups_id"] = commands
        if diff.deactivate:
            vals["active"] = False

        if not vals:
            per_record.append(
                PerRecordResult(
                    id=diff.user_id,
                    display_name=diff.user_name,
                    ok=True,
                    error="no-op",
                )
            )
            succeeded += 1
            continue

        if dry_run:
            per_record.append(
                PerRecordResult(
                    id=diff.user_id,
                    display_name=diff.user_name,
                    ok=True,
                    error="dry-run",
                )
            )
            succeeded += 1
            continue

        try:
            client.execute_kw("res.users", "write", [[diff.user_id], vals])
            per_record.append(
                PerRecordResult(id=diff.user_id, display_name=diff.user_name, ok=True)
            )
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            per_record.append(
                PerRecordResult(
                    id=diff.user_id,
                    display_name=diff.user_name,
                    ok=False,
                    error=str(exc),
                )
            )

    return SecurityApplyResult(
        run_id=run_id,
        operation="bulk_security",
        model="res.users",
        total=len(preview.users),
        succeeded=succeeded,
        failed=failed,
        per_record=per_record,
        dry_run=dry_run,
        message=(
            f"Security apply ({mode}): {succeeded} ok, {failed} failed"
            if not dry_run
            else f"Dry-run security ({mode}) on {len(preview.users)} user(s)"
        ),
        mode=mode,
        preview_message=preview.message,
    )
