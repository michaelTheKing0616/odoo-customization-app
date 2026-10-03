"""RPC risk classification for Odoo ORM calls (Track 5A).

Bucket map (approval policy, not a separate taxonomy):
  A — READ: no approval required.
  B — REVERSIBLE: auto-allowed on staging; needs approval on production.
  C — DESTRUCTIVE, BILLABLE, or forbidden: always needs a human; forbidden never proceeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Bucket = Literal["A", "B", "C"]

READ_METHODS: frozenset[str] = frozenset(
    {
        "search",
        "search_read",
        "read",
        "search_count",
        "fields_get",
        "name_search",
        "default_get",
        "read_group",
        "formatted_read_group",
        "context_get",
        "exists",
        "get_views",
    }
)

SENSITIVE_MODELS: frozenset[str] = frozenset(
    {
        "ir.model.access",
        "ir.rule",
        "ir.access",
        "res.groups",
        "res.groups.privilege",
        "ir.config_parameter",
        "ir.mail_server",
        "fetchmail.server",
        "auth.oauth.provider",
        "res.users.apikeys",
        "ir.module.module",
        "account.move",
        "account.payment",
        "account.bank.statement",
        "account.bank.statement.line",
        "hr.payslip",
        "ir.cron",
        "ir.actions.server",
        "base.automation",
        "ir.ui.view",
        "ir.model",
        "ir.model.fields",
        "payment.provider",
    }
)

DESTRUCTIVE_METHODS: frozenset[str] = frozenset(
    {
        "unlink",
        "button_immediate_uninstall",
        "button_uninstall",
        "action_post",
        "button_cancel",
        "action_cancel",
        "action_reverse",
        "button_draft",
        "action_send_mail",
        "message_post",
        "send_mail",
        "action_invoice_sent",
        "action_register_payment",
        "action_create_payments",
        "action_validate",
        "button_validate",
        "button_mark_done",
        "action_done",
        "unlink_all",
        "toggle_active",
        "action_archive",
        "action_unarchive",
        "reconcile",
        "remove_move_reconcile",
    }
)

BILLABLE_METHODS: frozenset[str] = frozenset(
    {
        "button_immediate_install",
        "button_install",
        "button_upgrade",
        "button_immediate_upgrade",
    }
)

from odoo_client.rpc_policy import NEVER_ALLOWED, PROTECTED_PARAMS

_ENTERPRISE_EDITIONS = frozenset({"enterprise", "online", "odoo_sh"})
_MASS_WRITE_THRESHOLD = 50


@dataclass(frozen=True)
class Classification:
    risk: Literal["READ", "REVERSIBLE", "DESTRUCTIVE", "BILLABLE"]
    forbidden: bool
    reason: str
    bucket: Bucket


def _nested_strings_touch_protected(obj: object) -> bool:
    if isinstance(obj, str):
        return obj in PROTECTED_PARAMS
    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(key, str) and key in PROTECTED_PARAMS:
                return True
            if _nested_strings_touch_protected(val):
                return True
        return False
    if isinstance(obj, (list, tuple)):
        return any(_nested_strings_touch_protected(item) for item in obj)
    return False


def _values_touch_protected(values: dict) -> bool:
    if PROTECTED_PARAMS.intersection(values.keys()):
        return True
    key_field = values.get("key")
    if isinstance(key_field, str) and key_field in PROTECTED_PARAMS:
        return True
    return False


def _never_allowed(model: str, method: str) -> bool:
    for blocked_model, blocked_method in NEVER_ALLOWED:
        if model == blocked_model and (
            blocked_method == "*" or blocked_method == method
        ):
            return True
    return False


def _is_read_method(method: str) -> bool:
    return method in READ_METHODS and method not in DESTRUCTIVE_METHODS


def _is_billable_method(method: str) -> bool:
    if method in BILLABLE_METHODS:
        return True
    if method.startswith("iap_") or method.startswith("action_buy_"):
        return True
    return "_iap_" in method


def _finish(
    risk: Literal["READ", "REVERSIBLE", "DESTRUCTIVE", "BILLABLE"],
    *,
    forbidden: bool,
    reason: str,
) -> Classification:
    if risk == "READ" and not forbidden:
        bucket: Bucket = "A"
    elif risk == "REVERSIBLE":
        bucket = "B"
    else:
        bucket = "C"
    return Classification(risk=risk, forbidden=forbidden, reason=reason, bucket=bucket)


def classify_rpc(
    model: str,
    method: str,
    *,
    ids: list | None = None,
    values: dict | None = None,
    args: tuple | list | None = None,
    edition: str = "community",
    approved: bool = False,
) -> Classification:
    """Classify an Odoo RPC call. ``approved`` does not override forbidden actions."""
    del approved  # reserved for callers; forbidden is never cleared by approval

    if _never_allowed(model, method):
        return _finish("DESTRUCTIVE", forbidden=True, reason="never_allowed")

    if values and _values_touch_protected(values):
        return _finish(
            "DESTRUCTIVE",
            forbidden=True,
            reason="protected_param",
        )

    if args is not None and _nested_strings_touch_protected(args):
        return _finish(
            "DESTRUCTIVE",
            forbidden=True,
            reason="protected_param",
        )

    if _is_read_method(method):
        return _finish("READ", forbidden=False, reason="read_method")

    if _is_billable_method(method):
        if edition in _ENTERPRISE_EDITIONS:
            return _finish("BILLABLE", forbidden=False, reason="billable_method")
        return _finish("DESTRUCTIVE", forbidden=False, reason="billable_on_community")

    if method in DESTRUCTIVE_METHODS:
        return _finish("DESTRUCTIVE", forbidden=False, reason="destructive_method")

    if model in SENSITIVE_MODELS and not _is_read_method(method):
        return _finish("DESTRUCTIVE", forbidden=False, reason="sensitive_model")

    if method in {"write", "create", "copy"}:
        if method == "write" and ids is not None and len(ids) > _MASS_WRITE_THRESHOLD:
            return _finish("DESTRUCTIVE", forbidden=False, reason="mass_write")
        return _finish("REVERSIBLE", forbidden=False, reason="reversible_mutation")

    return _finish("DESTRUCTIVE", forbidden=False, reason="unknown_method")


def policy_allows(classification: Classification, *, environment: str) -> bool:
    """Auto-approve gate: staging allows READ/REVERSIBLE; production allows READ only."""
    if classification.forbidden:
        return False
    if environment == "staging":
        return classification.risk in {"READ", "REVERSIBLE"}
    if environment == "production":
        return classification.risk == "READ"
    raise ValueError(f"unknown environment: {environment!r}")
