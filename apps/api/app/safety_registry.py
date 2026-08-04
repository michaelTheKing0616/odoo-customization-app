"""Route → SafetySpec registry for TRUST-2 meta-test and gate lookup."""

from __future__ import annotations

import re
from typing import Any

from app.safety_gate import SafetySpec

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

EXEMPT_ROUTE_KEYS: frozenset[str] = frozenset(
    {
        "POST:/api/accounts/signup",
        "POST:/api/accounts/login",
        "POST:/api/accounts/logout",
        "POST:/api/accounts/verify-email",
        "POST:/api/accounts/request-password-reset",
        "POST:/api/accounts/reset-password",
        "POST:/api/accounts/accept-invite",
        "POST:/api/accounts/invitations",
        "POST:/api/accounts/totp/enroll",
        "POST:/api/accounts/totp/verify",
        "GET:/api/accounts/oauth/{provider}/start",
        "GET:/api/accounts/oauth/{provider}/callback",
        "POST:/api/accounts/oauth/complete-2fa",
        "DELETE:/api/accounts/oauth/{provider}",
        "POST:/api/auth/bootstrap",
        "POST:/api/auth/keys",
        "DELETE:/api/auth/keys/{key_id}",
        "POST:/api/billing/stripe/webhook",
        "POST:/api/billing/paystack/webhook",
        "POST:/api/billing/checkout/stripe",
        "POST:/api/billing/checkout/paystack",
        "POST:/api/billing/checkout/stripe/extra-slots",
        "POST:/api/billing/checkout/paystack/extra-slots",
        "POST:/api/admin/grant-slots",
        "POST:/api/audit/purge",
    }
)

ROUTE_OVERRIDES: dict[str, SafetySpec] = {
    "POST:/api/connections": SafetySpec(risk="read", odoo_mutation=False, confirm="none"),
    "PATCH:/api/connections/{connection_id}": SafetySpec(
        risk="read", odoo_mutation=False, confirm="none"
    ),
    "DELETE:/api/connections/{connection_id}": SafetySpec(
        risk="reversible", odoo_mutation=False, confirm="simple"
    ),
    "PATCH:/api/connections/{connection_id}/write-mode": SafetySpec(
        risk="read", odoo_mutation=False, confirm="simple"
    ),
    "PATCH:/api/connections/{connection_id}/writes-paused": SafetySpec(
        risk="read", odoo_mutation=False, confirm="none", bypass_writes_paused=True
    ),
    "PATCH:/api/workspaces/writes-paused": SafetySpec(
        risk="read", odoo_mutation=False, confirm="none", bypass_writes_paused=True
    ),
    "POST:/api/connections/{connection_id}/bulk/transitions/run": SafetySpec(
        risk="reversible", snapshot=True, confirm="phrase", dry_run_first=True
    ),
    "POST:/api/connections/{connection_id}/bulk/mass-edit": SafetySpec(
        risk="reversible", snapshot=True, confirm="phrase", dry_run_first=True
    ),
    "POST:/api/connections/{connection_id}/bulk/dedupe/merge": SafetySpec(
        risk="destructive", snapshot=True, confirm="phrase", dry_run_first=True
    ),
    "POST:/api/connections/{connection_id}/bulk/attachments/clean": SafetySpec(
        risk="destructive", snapshot=True, confirm="phrase", dry_run_first=True
    ),
    "POST:/api/connections/{connection_id}/bulk/activities": SafetySpec(
        risk="reversible", snapshot=True, confirm="phrase", dry_run_first=True
    ),
    "POST:/api/connections/{connection_id}/bulk/security/apply": SafetySpec(
        risk="destructive", snapshot=True, confirm="phrase", dry_run_first=True
    ),
    "POST:/api/connections/{connection_id}/bulk/portal": SafetySpec(
        risk="reversible", snapshot=True, confirm="phrase", dry_run_first=True
    ),
    "POST:/api/connections/{connection_id}/bulk/recompute": SafetySpec(
        risk="reversible", snapshot=True, confirm="phrase", dry_run_first=True
    ),
    "POST:/api/connections/{connection_id}/bulk/send-message": SafetySpec(
        risk="reversible", snapshot=True, confirm="phrase", dry_run_first=True
    ),
    "POST:/api/connections/{connection_id}/bulk/crons/run-now": SafetySpec(
        risk="destructive", snapshot=True, confirm="phrase", dry_run_first=True
    ),
    "POST:/api/connections/{connection_id}/bulk/runs/{run_id}/continue": SafetySpec(
        risk="reversible", snapshot=True, confirm="none", odoo_mutation=True
    ),
    "POST:/api/connections/{connection_id}/bulk/runs/{run_id}/abort": SafetySpec(
        risk="read", odoo_mutation=False, confirm="none", bypass_writes_paused=True
    ),
    "DELETE:/api/connections/{connection_id}/fields/{field_id}": SafetySpec(
        risk="destructive", snapshot=True, confirm="phrase", odoo_mutation=True
    ),
    "POST:/api/connections/{connection_id}/code-studio/bind": SafetySpec(
        risk="code", snapshot=True, confirm="phrase", odoo_mutation=True
    ),
    "POST:/api/connections/{connection_id}/code-studio/test-run": SafetySpec(
        risk="code", snapshot=False, confirm="none", odoo_mutation=True
    ),
    "POST:/api/connections/{connection_id}/code-studio/validate": SafetySpec(
        risk="read", odoo_mutation=False, confirm="none"
    ),
    "POST:/api/connections/{connection_id}/code-studio/probe": SafetySpec(
        risk="read", odoo_mutation=True, confirm="none"
    ),
    "POST:/api/connections/{connection_id}/script-runner/run": SafetySpec(
        risk="code", snapshot=False, confirm="phrase", odoo_mutation=True
    ),
    "POST:/api/connections/{connection_id}/script-runner/library": SafetySpec(
        risk="read", odoo_mutation=False, confirm="none"
    ),
    "POST:/api/connections/{connection_id}/module-spec/export-sandbox": SafetySpec(
        risk="read", odoo_mutation=False, confirm="none"
    ),
    "POST:/api/connections/{connection_id}/module-spec/lint-blocks": SafetySpec(
        risk="read", odoo_mutation=False, confirm="none"
    ),
}


def route_key(method: str, path: str) -> str:
    return f"{method.upper()}:{path}"


def _default_spec(path: str) -> SafetySpec:
    lower = path.lower()
    if any(x in lower for x in ("/purge", "/uninstall", "/delete", "hard-delete", "/merge")):
        return SafetySpec(risk="destructive", snapshot=True, confirm="phrase", dry_run_first=True)
    if "dry-run" in lower or lower.endswith("/preview"):
        return SafetySpec(risk="read", odoo_mutation=False, confirm="none")
    if "/apply" in lower or "/execute" in lower or "/promote" in lower:
        return SafetySpec(risk="reversible", snapshot=True, confirm="phrase", dry_run_first=True)
    return SafetySpec(risk="reversible", confirm="phrase")


def build_route_registry(openapi_paths: dict[str, Any]) -> dict[str, SafetySpec]:
    registry: dict[str, SafetySpec] = {}
    for path, ops in openapi_paths.items():
        if not path.startswith("/api/"):
            continue
        for method in ops:
            if method.upper() not in MUTATING_METHODS:
                continue
            key = route_key(method, path)
            registry[key] = ROUTE_OVERRIDES.get(key, _default_spec(path))
    return registry


def is_exempt(key: str) -> bool:
    return key in EXEMPT_ROUTE_KEYS


def lookup_route_spec(method: str, path: str, registry: dict[str, SafetySpec]) -> SafetySpec | None:
    key = route_key(method, path)
    return registry.get(key)


def connection_id_from_path(path: str, path_params: dict[str, str]) -> str | None:
    if "connection_id" in path_params:
        return path_params["connection_id"]
    m = re.search(r"/connections/([^/]+)", path)
    if m:
        return m.group(1)
    return None
