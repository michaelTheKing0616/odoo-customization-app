"""Allowlisted ``res.config.settings`` keys — never secrets or SMTP passwords."""

from __future__ import annotations

from typing import Any

from app.config_packet import rpc

# Public Settings toggles that Autopilot may capture/replay. Anything resembling
# a password, token, key, smtp, or webhook is refused even if listed by fields_get.
SETTINGS_ALLOWLIST: frozenset[str] = frozenset(
    {
        "group_product_variant",
        "group_uom",
        "group_stock_packaging",
        "group_stock_multi_locations",
        "group_stock_adv_location",
        "group_lot_on_delivery",
        "group_lot_on_incoming",
        "group_stock_production_lot",
        "group_discount_per_so_line",
        "group_sale_delivery_address",
        "group_warning_sale",
        "group_auto_done_setting",
        "default_invoice_policy",
        "quotation_validity_days",
        "use_quotation_validity_days",
        "group_cash_rounding",
        "module_delivery",
        "po_lock",
        "po_double_validation",
    }
)

_SECRET_NEEDLES = (
    "password",
    "secret",
    "token",
    "apikey",
    "api_key",
    "smtp",
    "webhook",
    "private",
    "certificate",
)


def is_secret_key(name: str) -> bool:
    low = (name or "").lower()
    return any(n in low for n in _SECRET_NEEDLES)


def sanitize_settings(values: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in (values or {}).items():
        name = str(key)
        if name not in SETTINGS_ALLOWLIST or is_secret_key(name):
            continue
        if isinstance(val, (bool, int, float, str)) or val is None:
            out[name] = val
    return out


def capture_settings(client: Any) -> dict[str, Any]:
    if not rpc.exists(client, "res.config.settings"):
        return {}
    fields = sorted(SETTINGS_ALLOWLIST)
    try:
        defaults = client.execute_kw("res.config.settings", "default_get", [fields])
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(defaults, dict):
        return {}
    return sanitize_settings({k: defaults.get(k) for k in fields})


def apply_settings(client: Any, values: dict[str, Any]) -> str | None:
    clean = sanitize_settings(values)
    if not clean or not rpc.exists(client, "res.config.settings"):
        return None
    try:
        sid = client.execute_kw("res.config.settings", "create", [clean])
        client.execute_kw("res.config.settings", "execute", [[int(sid)]])
        return f"settings {sorted(clean)}"
    except Exception as exc:  # noqa: BLE001
        return f"settings skipped: {exc}"
