"""Where to inspect Option A gold on the *connected* Odoo — not the ephemeral sandbox.

Sandbox prove may install ``account`` only on a throwaway container. Opening
``res.config.settings`` on a connection without Invoicing looks like “no Accounting”.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from app.config_packet.rpc import xml_id

GOLD_INSPECT_TARGETS: dict[str, dict[str, Any]] = {
    "currency_rate_cbn": {
        "depends": ("account",),
        "install_module": "account",
        "install_label": "Invoicing (account)",
        "action_xmlids": ("account.action_account_config",),
        "view_model": "res.config.settings",
        "view_type": "form",
        "label": "Open Accounting Settings",
        "after_promote": (
            "Automatic Currency Rates → Central Bank of Nigeria → Update now. "
            "Then Currencies → USD → Rates."
        ),
    },
    "pos_receipt_options": {
        "depends": ("point_of_sale",),
        "install_module": "point_of_sale",
        "install_label": "Point of Sale",
        "action_xmlids": ("point_of_sale.action_pos_config_pos",),
        "view_model": "pos.config",
        "view_type": "list",
        "label": "Open Point of Sale",
        "after_promote": "Open a POS config and check receipt header/footer.",
    },
    "invoice_qweb": {
        "depends": ("account",),
        "install_module": "account",
        "install_label": "Invoicing (account)",
        "action_xmlids": (
            "account.action_move_out_invoice_type",
            "account.action_move_out_invoice",
        ),
        "view_model": "account.move",
        "view_type": "list",
        "label": "Open Invoices",
        "after_promote": "Print a customer invoice PDF.",
    },
}


def _module_installed(client: Any, name: str) -> bool:
    getter = getattr(client, "get_module_state", None)
    if callable(getter):
        row = getter(name) or {}
        return str(row.get("state") or "") == "installed"
    try:
        rows = client.execute_kw(
            "ir.module.module",
            "search_read",
            [[("name", "=", name)]],
            {"fields": ["state"], "limit": 1},
        )
    except Exception:  # noqa: BLE001
        return False
    return bool(rows) and str(rows[0].get("state") or "") == "installed"


def _settings_href(
    base_url: str,
    *,
    model: str,
    view_type: str,
    action_id: int | None,
) -> str:
    root = (base_url or "").rstrip("/")
    if not root:
        return ""
    params: dict[str, str] = {"model": model, "view_type": view_type}
    if action_id and action_id > 0:
        params["action"] = str(action_id)
    return f"{root}/web#{urlencode(params)}"


def probe_gold_inspect(
    client: Any,
    *,
    gold_id: str,
    base_url: str | None,
) -> dict[str, Any]:
    """Return host readiness + Accounting/POS inspect URL for this connection."""
    gid = (gold_id or "").strip()
    target = GOLD_INSPECT_TARGETS.get(gid)
    missing: list[str] = []
    if target:
        for dep in target["depends"]:
            if not _module_installed(client, str(dep)):
                missing.append(str(dep))
    host_ready = not missing if target else True
    action_id: int | None = None
    href: str | None = None
    label = "Open connected Odoo"
    if target and host_ready:
        for xid in target["action_xmlids"]:
            rid = xml_id(client, str(xid))
            if rid:
                action_id = rid
                break
        href = _settings_href(
            str(base_url or ""),
            model=str(target["view_model"]),
            view_type=str(target["view_type"]),
            action_id=action_id,
        ) or None
        label = str(target["label"])
    elif not target and base_url:
        href = f"{str(base_url).rstrip('/')}/web"
        label = "Open connected Odoo"

    if missing:
        install_label = str((target or {}).get("install_label") or missing[0])
        if gid == "currency_rate_cbn":
            message = (
                "This connection has no Invoicing app (account). "
                "Sandbox prove installed Accounting only on a throwaway Odoo that is already gone. "
                "Settings → search Currency → Automatic Currency Rates is Community’s Enterprise "
                "upgrade tease (no ECB Service). Install Invoicing here, Promote the zip, then open "
                "Invoicing → Configuration → Settings — not the Settings app search."
            )
        else:
            message = (
                f"This connection has no {install_label} app. Sandbox prove used a throwaway Odoo. "
                f"Install {install_label} here, then Promote."
            )
    elif target and gid == "currency_rate_cbn":
        message = (
            "Open Invoicing → Configuration → Settings — not Settings → search Currency. "
            "That search is Community’s Enterprise tease (no ECB Service). After Promote: "
            + str(target["after_promote"])
        )
    elif target:
        message = (
            "This is the connected Odoo, not the ephemeral sandbox. "
            + str(target["after_promote"])
        )
    else:
        message = "Sandbox install does not stay up. Promote first, then inspect this connection."

    return {
        "gold_id": gid,
        "host_ready": host_ready,
        "missing_depends": missing,
        "install_module": (target or {}).get("install_module") if missing else None,
        "install_label": (target or {}).get("install_label") if missing else None,
        "action_id": action_id,
        "href": href if host_ready else None,
        "label": label,
        "message": message,
    }
