"""Bridge B1: connector gallery catalog + connect-time health evaluation (pure, no network).

Spec items 1 (gallery), 3 (guided auth descriptors) and 4 (health check on connect).
AI proposes nothing here; this is the code-side source of truth the UI and AI read.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

AUTH_KINDS = ("oauth2", "api_key", "basic", "webhook_secret")
CATEGORIES = (
    "commerce",
    "payments",
    "accounting",
    "crm",
    "messaging",
    "productivity",
    "banking",
    "shipping",
    "payroll",
)


@dataclass(frozen=True)
class Connector:
    key: str
    name: str
    category: str
    auth: tuple[str, ...]
    entities: tuple[str, ...]
    webhook_signature: str | None = None  # e.g. "hmac-sha256-base64"
    health_probe: str = ""  # read-only endpoint path used by the connect check
    money: bool = False  # flows touch money -> money guard + reconciliation mandatory
    secret_fields: tuple[str, ...] = ()
    status: str = "available"  # available | template (generic; filled per provider)

    def public(self) -> dict[str, Any]:
        d = asdict(self)
        d["secret_fields"] = list(self.secret_fields)  # names only, never values
        return d


_C = Connector
GALLERY: tuple[Connector, ...] = (
    _C(
        "shopify",
        "Shopify",
        "commerce",
        ("oauth2", "webhook_secret"),
        ("products", "customers", "orders", "inventory_levels"),
        "hmac-sha256-base64",
        "/admin/api/shop.json",
        True,
        ("access_token", "webhook_secret"),
    ),
    _C(
        "woocommerce",
        "WooCommerce",
        "commerce",
        ("api_key", "webhook_secret"),
        ("products", "customers", "orders"),
        "hmac-sha256-base64",
        "/wp-json/wc/v3/system_status",
        True,
        ("consumer_key", "consumer_secret", "webhook_secret"),
    ),
    _C(
        "stripe",
        "Stripe",
        "payments",
        ("api_key", "webhook_secret"),
        ("customers", "charges", "payouts", "invoices"),
        "stripe-v1",
        "/v1/balance",
        True,
        ("secret_key", "webhook_secret"),
    ),
    _C(
        "paystack",
        "Paystack",
        "payments",
        ("api_key",),
        ("customers", "transactions", "settlements"),
        "hmac-sha512-hex",
        "/balance",
        True,
        ("secret_key",),
    ),
    _C(
        "flutterwave",
        "Flutterwave",
        "payments",
        ("api_key", "webhook_secret"),
        ("customers", "transactions", "settlements"),
        "verif-hash",
        "/v3/balances",
        True,
        ("secret_key", "webhook_secret"),
    ),
    _C(
        "quickbooks",
        "QuickBooks Online",
        "accounting",
        ("oauth2",),
        ("customers", "vendors", "invoices", "bills", "payments", "accounts"),
        "hmac-sha256-base64",
        "/v3/company/{realm}/companyinfo/{realm}",
        True,
        ("refresh_token",),
    ),
    _C(
        "xero",
        "Xero",
        "accounting",
        ("oauth2", "webhook_secret"),
        ("contacts", "invoices", "payments", "accounts"),
        "hmac-sha256-base64",
        "/connections",
        True,
        ("refresh_token", "webhook_key"),
    ),
    _C(
        "hubspot",
        "HubSpot",
        "crm",
        ("oauth2",),
        ("contacts", "companies", "deals"),
        "hubspot-v3",
        "/account-info/v3/details",
        False,
        ("refresh_token",),
    ),
    _C(
        "salesforce",
        "Salesforce",
        "crm",
        ("oauth2",),
        ("accounts", "contacts", "opportunities", "leads"),
        None,
        "/services/data",
        False,
        ("refresh_token",),
    ),
    _C(
        "slack",
        "Slack",
        "messaging",
        ("oauth2",),
        ("messages", "channels"),
        "slack-v0",
        "/api/auth.test",
        False,
        ("bot_token", "signing_secret"),
    ),
    _C(
        "teams",
        "Microsoft Teams",
        "messaging",
        ("oauth2",),
        ("messages", "channels"),
        None,
        "/v1.0/me",
        False,
        ("refresh_token",),
    ),
    _C(
        "whatsapp",
        "WhatsApp Business",
        "messaging",
        ("api_key", "webhook_secret"),
        ("messages", "contacts"),
        "hmac-sha256-hex",
        "/{phone_number_id}",
        False,
        ("access_token", "app_secret"),
    ),
    _C(
        "google_sheets",
        "Google Sheets",
        "productivity",
        ("oauth2",),
        ("spreadsheets", "rows"),
        None,
        "/v4/spreadsheets/{id}?fields=spreadsheetId",
        False,
        ("refresh_token",),
    ),
    _C(
        "bank",
        "Bank feed",
        "banking",
        ("oauth2", "api_key"),
        ("accounts", "statements", "transactions"),
        None,
        "",
        True,
        ("credentials",),
        "template",
    ),
    _C(
        "shipping",
        "Shipping carrier",
        "shipping",
        ("api_key",),
        ("shipments", "rates", "tracking"),
        None,
        "",
        False,
        ("api_key",),
        "template",
    ),
    _C(
        "payroll",
        "Payroll provider",
        "payroll",
        ("oauth2", "api_key"),
        ("employees", "payslips", "journals"),
        None,
        "",
        True,
        ("credentials",),
        "template",
    ),
)
BY_KEY = {c.key: c for c in GALLERY}


def list_gallery(category: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    out = []
    for c in GALLERY:
        if category and c.category != category:
            continue
        if q and q.lower() not in (c.name + " " + c.key + " " + " ".join(c.entities)).lower():
            continue
        out.append(c.public())
    return out


def auth_plan(key: str) -> dict[str, Any]:
    """Guided-auth steps for the UI. Secret values go to the vault, never into this payload or logs."""
    c = BY_KEY[key]
    steps = []
    for kind in c.auth:
        if kind == "oauth2":
            steps.append({"kind": kind, "step": "Sign in with " + c.name, "refresh": True})
        elif kind == "api_key":
            steps.append(
                {
                    "kind": kind,
                    "step": "Paste API key(s)",
                    "fields": [f for f in c.secret_fields if "webhook" not in f],
                }
            )
        elif kind == "webhook_secret":
            steps.append(
                {
                    "kind": kind,
                    "step": "Register webhook and store its signing secret",
                    "signature": c.webhook_signature,
                }
            )
    return {
        "connector": key,
        "steps": steps,
        "vault_fields": list(c.secret_fields),
        "money_guard": c.money,
    }


# --- Health check on connect (item 4). Probe results are gathered by the caller; this decides. ---
@dataclass
class ProbeResult:
    name: str  # "auth" | "read" | "permissions" | "rate_limit" | "webhook"
    ok: bool
    status: int | None = None
    detail: str = ""
    headers: dict[str, str] = field(default_factory=dict)


def _rate(headers: dict[str, str]) -> dict[str, Any] | None:
    h = {k.lower(): v for k, v in headers.items()}
    for lim_k, rem_k in (
        ("x-ratelimit-limit", "x-ratelimit-remaining"),
        ("x-shopify-shop-api-call-limit", None),
    ):
        if lim_k in h:
            if rem_k is None and "/" in h[lim_k]:
                used, lim = h[lim_k].split("/", 1)
                try:
                    return {"limit": int(lim), "remaining": int(lim) - int(used)}
                except ValueError:
                    return None
            try:
                return {"limit": int(h[lim_k]), "remaining": int(h.get(rem_k, h[lim_k]))}
            except ValueError:
                return None
    return None


def evaluate_health(
    key: str,
    probes: list[ProbeResult],
    granted_scopes: list[str] | None = None,
    needed_entities: list[str] | None = None,
) -> dict[str, Any]:
    c = BY_KEY[key]
    by = {p.name: p for p in probes}
    issues: list[str] = []
    if not by.get("auth") or not by["auth"].ok:
        s = by["auth"].status if by.get("auth") else None
        issues.append("Sign-in failed" + (" (expired or wrong key)" if s in (401, 403) else ""))
    if by.get("read") and not by["read"].ok:
        issues.append("Test read failed")
    need = [e for e in (needed_entities or []) if e not in c.entities]
    if need:
        issues.append("Not supported by this connector: " + ", ".join(need))
    if granted_scopes is not None and needed_entities:
        missing = [
            e for e in needed_entities if not any(e.rstrip("s") in s for s in granted_scopes)
        ]
        if missing:
            issues.append("Missing permission for: " + ", ".join(missing))
    rate = None
    for p in probes:
        rate = rate or _rate(p.headers)
    warn = []
    if rate and rate["limit"] and rate["remaining"] / rate["limit"] < 0.2:
        warn.append("Rate limit nearly used up")
    if c.webhook_signature and not (by.get("webhook") and by["webhook"].ok):
        warn.append("Webhook not verified yet")
    status = "fail" if issues else ("warn" if warn else "ok")
    # details are status codes and plain words only; probe detail text is not echoed (may contain secrets)
    return {
        "connector": key,
        "status": status,
        "issues": issues,
        "warnings": warn,
        "rate_limit": rate,
        "money_guard": c.money,
    }
