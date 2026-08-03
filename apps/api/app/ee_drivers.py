"""Enterprise capability drivers via public RPC only (TIER-5).

Field names for ``studio.approval.rule`` are sourced from Odoo Studio public docs
and probed live via ``fields_get`` when the model exists. RPC calls marked
``verified: pending-live`` until confirmed on an Enterprise instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from odoo_client import OdooClient
from odoo_client.client import OdooClientError

VerifyState = Literal["live", "pending-live", "unavailable"]

APPROVAL_RULE_MODEL = "studio.approval.rule"
APPROVAL_ENTRY_MODEL = "studio.approval.entry"
ENTERPRISE_APPROVAL_REQUEST_MODEL = "approval.request"
ENTERPRISE_APPROVAL_CATEGORY_MODEL = "approval.category"

# Public EE Approvals app — field names verified: pending-live until EE instance available.
ENTERPRISE_APPROVAL_REQUEST_FIELDS_DOC: dict[str, str] = {
    "name": "Approval title",
    "category_id": "Approval category (approval.category)",
    "request_status": "Request status",
    "request_owner_id": "Request owner (res.users)",
    "date": "Request date",
    "amount": "Amount",
    "reason": "Description",
}
ENTERPRISE_APPROVAL_REQUEST_MODEL = "approval.request"
ENTERPRISE_APPROVAL_CATEGORY_MODEL = "approval.category"

# Public EE Approvals app — field names verified: pending-live until EE instance available.
ENTERPRISE_APPROVAL_REQUEST_FIELDS_DOC: dict[str, str] = {
    "name": "Approval title",
    "category_id": "Approval category (approval.category)",
    "request_status": "Request status",
    "request_owner_id": "Request owner (res.users)",
    "date": "Request date",
    "amount": "Amount",
    "reason": "Description",
}

# Public Studio docs — Approvers, Approver Group, domain filter, order, exclusive.
# verified: pending-live — confirm field names on Enterprise via fields_get probe.
APPROVAL_RULE_FIELDS_DOC: dict[str, str] = {
    "name": "Rule label",
    "model_id": "Target model (ir.model)",
    "method": "Button method name on the model",
    "action_id": "Bound ir.actions.server / button action",
    "domain": "Conditional domain for when the step applies",
    "user_ids": "Approver users (res.users)",
    "group_id": "Approver group (res.groups)",
    "exclusive_user": "Exclusive approval — approver cannot approve other steps",
    "notification_order": "Approval order (1 = first step)",
    "active": "Active flag",
}

EE_VIEW_TYPES = frozenset({"map", "gantt", "cohort", "grid"})


class EeDriverError(Exception):
    pass


class EeDriverUnavailable(EeDriverError):
    pass


@dataclass
class DriverCapabilityStatus:
    driver_id: str
    label: str
    model: str | None
    available: bool
    verify_state: VerifyState
    reason: str
    verified_fields: list[str] = field(default_factory=list)
    pending_fields: list[str] = field(default_factory=list)
    requires_modules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "driver_id": self.driver_id,
            "label": self.label,
            "model": self.model,
            "available": self.available,
            "verify_state": self.verify_state,
            "reason": self.reason,
            "verified_fields": list(self.verified_fields),
            "pending_fields": list(self.pending_fields),
            "requires_modules": list(self.requires_modules),
        }
        if self.verify_state == "pending-live":
            out["note"] = "[SKIPPED-LIVE-VERIFY] Field names not confirmed on a live Enterprise instance."
        return out


def _module_installed(client: OdooClient, name: str) -> bool:
    rows = client.execute_kw(
        "ir.module.module",
        "search_read",
        [[("name", "=", name)]],
        {"fields": ["state"], "limit": 1},
    )
    if not rows:
        return False
    return str(rows[0].get("state") or "") in {"installed", "to upgrade", "to remove"}


def _fields_get(client: OdooClient, model: str) -> dict[str, Any]:
    return client.execute_kw(model, "fields_get", [], {"attributes": ["string", "type"]})


def probe_approval_rules_driver(client: OdooClient) -> DriverCapabilityStatus:
    requires = ["web_studio", "studio_customization"]
    has_studio = any(_module_installed(client, m) for m in requires)
    if not client.model_exists(APPROVAL_RULE_MODEL):
        return DriverCapabilityStatus(
            driver_id="studio_approval_rules",
            label="Studio approval rules",
            model=APPROVAL_RULE_MODEL,
            available=False,
            verify_state="unavailable",
            reason=(
                f"Model {APPROVAL_RULE_MODEL} not found"
                + (" — Studio modules not installed." if not has_studio else ".")
            ),
            requires_modules=requires,
        )
    try:
        live_fields = set(_fields_get(client, APPROVAL_RULE_MODEL).keys())
    except OdooClientError as exc:
        return DriverCapabilityStatus(
            driver_id="studio_approval_rules",
            label="Studio approval rules",
            model=APPROVAL_RULE_MODEL,
            available=False,
            verify_state="pending-live",
            reason=f"fields_get failed: {exc}",
            requires_modules=requires,
        )

    verified = sorted(k for k in APPROVAL_RULE_FIELDS_DOC if k in live_fields)
    pending = sorted(k for k in APPROVAL_RULE_FIELDS_DOC if k not in live_fields)
    verify_state: VerifyState = "live" if len(verified) >= 4 else "pending-live"
    return DriverCapabilityStatus(
        driver_id="studio_approval_rules",
        label="Studio approval rules",
        model=APPROVAL_RULE_MODEL,
        available=True,
        verify_state=verify_state,
        reason=(
            "Approval rule RPC available — fields probed live."
            if verify_state == "live"
            else "Model exists — some doc fields absent; RPC uses probed subset only."
        ),
        verified_fields=verified,
        pending_fields=pending,
        requires_modules=requires,
    )


def probe_ee_playbook_driver(
    client: OdooClient,
    *,
    driver_id: str,
    label: str,
    modules: list[str],
    model: str | None,
) -> DriverCapabilityStatus:
    installed = any(_module_installed(client, m) for m in modules)
    if not installed:
        return DriverCapabilityStatus(
            driver_id=driver_id,
            label=label,
            model=model,
            available=False,
            verify_state="unavailable",
            reason=f"Required module(s) not installed: {', '.join(modules)}",
            requires_modules=modules,
        )
    if model and not client.model_exists(model):
        return DriverCapabilityStatus(
            driver_id=driver_id,
            label=label,
            model=model,
            available=False,
            verify_state="pending-live",
            reason=f"Module present but model {model} not found on this major.",
            requires_modules=modules,
        )
    return DriverCapabilityStatus(
        driver_id=driver_id,
        label=label,
        model=model,
        available=True,
        verify_state="live" if model and client.model_exists(model) else "pending-live",
        reason="RPC model available on this database.",
        requires_modules=modules,
    )


def probe_enterprise_approvals_driver(client: OdooClient) -> DriverCapabilityStatus:
    """Enterprise Approvals app (approval.request) — distinct from Studio button rules."""
    requires = ["approvals"]
    if not any(_module_installed(client, m) for m in requires):
        return DriverCapabilityStatus(
            driver_id="enterprise_approval_requests",
            label="Enterprise approval requests",
            model=ENTERPRISE_APPROVAL_REQUEST_MODEL,
            available=False,
            verify_state="unavailable",
            reason="Enterprise approvals module not installed.",
            requires_modules=requires,
        )
    if not client.model_exists(ENTERPRISE_APPROVAL_REQUEST_MODEL):
        return DriverCapabilityStatus(
            driver_id="enterprise_approval_requests",
            label="Enterprise approval requests",
            model=ENTERPRISE_APPROVAL_REQUEST_MODEL,
            available=False,
            verify_state="unavailable",
            reason=f"Model {ENTERPRISE_APPROVAL_REQUEST_MODEL!r} not found.",
            requires_modules=requires,
        )
    try:
        fields = _fields_get(client, ENTERPRISE_APPROVAL_REQUEST_MODEL)
    except OdooClientError as exc:
        return DriverCapabilityStatus(
            driver_id="enterprise_approval_requests",
            label="Enterprise approval requests",
            model=ENTERPRISE_APPROVAL_REQUEST_MODEL,
            available=False,
            verify_state="unavailable",
            reason=str(exc),
            requires_modules=requires,
        )
    verified = [k for k in ENTERPRISE_APPROVAL_REQUEST_FIELDS_DOC if k in fields]
    pending = [k for k in ENTERPRISE_APPROVAL_REQUEST_FIELDS_DOC if k not in fields]
    return DriverCapabilityStatus(
        driver_id="enterprise_approval_requests",
        label="Enterprise approval requests",
        model=ENTERPRISE_APPROVAL_REQUEST_MODEL,
        available=True,
        verify_state="live" if len(verified) >= 3 else "pending-live",
        reason="Enterprise approval.request RPC available.",
        verified_fields=verified,
        pending_fields=pending,
        requires_modules=requires,
    )


def probe_enterprise_approvals_driver(client: OdooClient) -> DriverCapabilityStatus:
    """Enterprise Approvals app (approval.request) — distinct from Studio button rules."""
    requires = ["approvals"]
    if not any(_module_installed(client, m) for m in requires):
        return DriverCapabilityStatus(
            driver_id="enterprise_approval_requests",
            label="Enterprise approval requests",
            model=ENTERPRISE_APPROVAL_REQUEST_MODEL,
            available=False,
            verify_state="unavailable",
            reason="Enterprise approvals module not installed.",
            requires_modules=requires,
        )
    if not client.model_exists(ENTERPRISE_APPROVAL_REQUEST_MODEL):
        return DriverCapabilityStatus(
            driver_id="enterprise_approval_requests",
            label="Enterprise approval requests",
            model=ENTERPRISE_APPROVAL_REQUEST_MODEL,
            available=False,
            verify_state="unavailable",
            reason=f"Model {ENTERPRISE_APPROVAL_REQUEST_MODEL!r} not found.",
            requires_modules=requires,
        )
    try:
        fields = _fields_get(client, ENTERPRISE_APPROVAL_REQUEST_MODEL)
    except OdooClientError as exc:
        return DriverCapabilityStatus(
            driver_id="enterprise_approval_requests",
            label="Enterprise approval requests",
            model=ENTERPRISE_APPROVAL_REQUEST_MODEL,
            available=False,
            verify_state="unavailable",
            reason=str(exc),
            requires_modules=requires,
        )
    verified = [k for k in ENTERPRISE_APPROVAL_REQUEST_FIELDS_DOC if k in fields]
    pending = [k for k in ENTERPRISE_APPROVAL_REQUEST_FIELDS_DOC if k not in fields]
    return DriverCapabilityStatus(
        driver_id="enterprise_approval_requests",
        label="Enterprise approval requests",
        model=ENTERPRISE_APPROVAL_REQUEST_MODEL,
        available=True,
        verify_state="live" if len(verified) >= 3 else "pending-live",
        reason="Enterprise approval.request RPC available.",
        verified_fields=verified,
        pending_fields=pending,
        requires_modules=requires,
    )


def probe_all_drivers(client: OdooClient) -> list[DriverCapabilityStatus]:
    return [
        probe_approval_rules_driver(client),
        probe_enterprise_approvals_driver(client),
        probe_ee_playbook_driver(
            client,
            driver_id="ee_playbook_sign",
            label="Sign — create request",
            modules=["sign"],
            model="sign.request",
        ),
        probe_ee_playbook_driver(
            client,
            driver_id="ee_playbook_documents",
            label="Documents — attach to folder",
            modules=["documents"],
            model="documents.document",
        ),
        probe_ee_playbook_driver(
            client,
            driver_id="ee_playbook_spreadsheet",
            label="Spreadsheet dashboards (read)",
            modules=["spreadsheet_dashboard", "spreadsheet"],
            model="spreadsheet.dashboard",
        ),
    ]


def require_approval_driver(client: OdooClient) -> DriverCapabilityStatus:
    status = probe_approval_rules_driver(client)
    if not status.available:
        raise EeDriverUnavailable(status.reason)
    return status


def _pick_write_fields(payload: dict[str, Any], verified: list[str]) -> dict[str, Any]:
    allowed = set(verified) | {"name", "active"}
    return {k: v for k, v in payload.items() if k in allowed and v is not None}


def list_approval_rules(
    client: OdooClient,
    *,
    domain: list[Any] | None = None,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], DriverCapabilityStatus]:
    status = require_approval_driver(client)
    read_fields = status.verified_fields or ["id", "name"]
    if "id" not in read_fields:
        read_fields = ["id", *read_fields]
    rows = client.execute_kw(
        APPROVAL_RULE_MODEL,
        "search_read",
        [domain or []],
        {"fields": read_fields, "limit": limit, "order": "id desc"},
    )
    return rows, status


def read_approval_rule(client: OdooClient, rule_id: int) -> tuple[dict[str, Any], DriverCapabilityStatus]:
    status = require_approval_driver(client)
    read_fields = status.verified_fields or ["id", "name"]
    rows = client.execute_kw(
        APPROVAL_RULE_MODEL,
        "read",
        [[rule_id]],
        {"fields": read_fields},
    )
    if not rows:
        raise EeDriverError(f"Approval rule #{rule_id} not found")
    return rows[0], status


def create_approval_rule(client: OdooClient, payload: dict[str, Any]) -> tuple[int, DriverCapabilityStatus]:
    # verified: pending-live — create uses probed field subset only.
    status = require_approval_driver(client)
    vals = _pick_write_fields(payload, status.verified_fields)
    if not vals:
        raise EeDriverError(
            "No writable approval-rule fields matched live probe — "
            f"verified={status.verified_fields}, pending={status.pending_fields}"
        )
    rule_id = client.execute_kw(APPROVAL_RULE_MODEL, "create", [vals])
    return int(rule_id), status


def update_approval_rule(
    client: OdooClient, rule_id: int, payload: dict[str, Any]
) -> tuple[bool, DriverCapabilityStatus]:
    status = require_approval_driver(client)
    vals = _pick_write_fields(payload, status.verified_fields)
    if not vals:
        raise EeDriverError("No writable fields in update payload")
    ok = client.execute_kw(APPROVAL_RULE_MODEL, "write", [[rule_id], vals])
    return bool(ok), status


def delete_approval_rule(client: OdooClient, rule_id: int) -> tuple[bool, DriverCapabilityStatus]:
    status = require_approval_driver(client)
    ok = client.execute_kw(APPROVAL_RULE_MODEL, "unlink", [[rule_id]])
    return bool(ok), status


def driver_response_note(status: DriverCapabilityStatus) -> str | None:
    if status.verify_state == "pending-live":
        return "[SKIPPED-LIVE-VERIFY] Some RPC field names are doc-sourced; live Enterprise probe incomplete."
    return None


__all__ = [
    "APPROVAL_RULE_MODEL",
    "EE_VIEW_TYPES",
    "DriverCapabilityStatus",
    "EeDriverError",
    "EeDriverUnavailable",
    "create_approval_rule",
    "delete_approval_rule",
    "driver_response_note",
    "list_approval_rules",
    "probe_all_drivers",
    "probe_approval_rules_driver",
    "probe_enterprise_approvals_driver",
    "read_approval_rule",
    "update_approval_rule",
]
