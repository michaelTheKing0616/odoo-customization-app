"""Bulk portal grant/revoke via portal.wizard (BLK-6)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from dataclasses import dataclass
from typing import Any, Literal

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.bulk_suite.transitions import BulkRunResult, BulkSuiteError, PerRecordResult

PortalAction = Literal["grant", "revoke"]


class PortalValidationError(BulkSuiteError):
    pass


@dataclass
class PortalApplyResult(BulkRunResult):
    action: str = "grant"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["action"] = self.action
        return data


def _portal_group_id(client: OdooClient) -> int | None:
    try:
        rows = client.execute_kw(
            "ir.model.data",
            "search_read",
            [[("module", "=", "base"), ("name", "=", "group_portal")]],
            {"fields": ["res_id"], "limit": 1},
        )
        if rows and rows[0].get("res_id"):
            return int(rows[0]["res_id"])
    except OdooClientError:
        return None
    return None


def _grant_one(client: OdooClient, partner_id: int) -> None:
    wizard_id = int(
        client.execute_kw(
            "portal.wizard",
            "create",
            [{"partner_ids": [(6, 0, [partner_id])]}],
        )
    )
    line_ids = client.execute_kw(
        "portal.wizard.user",
        "search",
        [[("wizard_id", "=", wizard_id), ("partner_id", "=", partner_id)]],
    )
    if not line_ids:
        line_ids = client.execute_kw(
            "portal.wizard.user",
            "search",
            [[("wizard_id", "=", wizard_id)]],
        )
    if not line_ids:
        raise PortalValidationError("portal.wizard did not create user lines for partner")
    for line_id in line_ids:
        client.execute_kw("portal.wizard.user", "action_grant_access", [[int(line_id)]])


def run_bulk_portal(
    client: OdooClient,
    *,
    partner_ids: list[int],
    action: PortalAction = "grant",
    dry_run: bool = True,
    run_id: str | None = None,
) -> PortalApplyResult:
    run_id = run_id or str(uuid.uuid4())
    pids = list(dict.fromkeys(int(p) for p in partner_ids))
    if not pids:
        raise PortalValidationError("partner_ids must not be empty")

    if action == "grant" and not client.model_exists("portal.wizard"):
        raise PortalValidationError(
            "portal module is not installed — portal.wizard unavailable"
        )

    rows = client.execute_kw(
        "res.partner",
        "read",
        [pids],
        {"fields": ["name", "email", "user_ids"]},
    )
    found = {int(r["id"]) for r in rows}
    missing = [p for p in pids if p not in found]
    if missing:
        raise PortalValidationError(f"Partner id(s) not found: {missing[:5]}")

    portal_gid: int | None = None
    if action == "revoke":
        portal_gid: int | None = None
    if action == "revoke":
        portal_gid = _portal_group_id(client)
    per_record: list[PerRecordResult] = []
    succeeded = 0
    failed = 0

    for row in rows:
        pid = int(row["id"])
        label = str(row.get("name") or pid)

        if action == "grant":
            email = (row.get("email") or "").strip()
            if not email:
                failed += 1
                per_record.append(
                    PerRecordResult(
                        id=pid,
                        display_name=label,
                        ok=False,
                        error="Partner has no email — portal grant skipped",
                    )
                )
                continue
            if dry_run:
                succeeded += 1
                per_record.append(
                    PerRecordResult(id=pid, display_name=label, ok=True, error="dry-run")
                )
                continue
            try:
                _grant_one(client, pid)
                succeeded += 1
                per_record.append(PerRecordResult(id=pid, display_name=label, ok=True))
            except Exception as exc:  # noqa: BLE001
                failed += 1
                per_record.append(
                    PerRecordResult(id=pid, display_name=label, ok=False, error=str(exc))
                )
            continue

        user_ids = [int(u) for u in (row.get("user_ids") or [])]
        if not user_ids or portal_gid is None:
            succeeded += 1
            per_record.append(
                PerRecordResult(
                    id=pid,
                    display_name=label,
                    ok=True,
                    error="no portal user linked" if not user_ids else "portal group missing",
                )
            )
            continue
        if dry_run:
            succeeded += 1
            per_record.append(
                PerRecordResult(id=pid, display_name=label, ok=True, error="dry-run")
            )
            continue
        try:
            for uid in user_ids:
                client.execute_kw(
                    "res.users",
                    "write",
                    [[uid], {"groups_id": [(3, portal_gid)]}],
                )
            succeeded += 1
            per_record.append(PerRecordResult(id=pid, display_name=label, ok=True))
        except Exception as exc:  # noqa: BLE001
            failed += 1
            per_record.append(
                PerRecordResult(id=pid, display_name=label, ok=False, error=str(exc))
            )

    return PortalApplyResult(
        run_id=run_id,
        operation="bulk_portal",
        model="res.partner",
        total=len(pids),
        succeeded=succeeded,
        failed=failed,
        per_record=per_record,
        dry_run=dry_run,
        message=(
            f"Portal {action}: {succeeded} ok, {failed} failed of {len(pids)} partner(s)"
            if not dry_run
            else f"Dry-run portal {action} on {len(pids)} partner(s)"
        ),
        action=action,
    )
