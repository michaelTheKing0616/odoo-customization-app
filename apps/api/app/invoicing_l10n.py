"""Fiscal localization detection for Connect-to-Invoicing (CMP-8 §19)."""

from __future__ import annotations

from typing import Any

from odoo_client.client import OdooClient


def detect_l10n(client: OdooClient) -> dict[str, Any]:
    """Return whether account + a country l10n module appear installed."""
    account_ok = client.model_exists("account.move")
    if not account_ok:
        return {
            "ok": False,
            "account_installed": False,
            "l10n_installed": False,
            "company_country": None,
            "l10n_modules": [],
            "message": "Accounting (account) module is not installed on this database.",
        }

    country_code: str | None = None
    try:
        companies = client.execute_kw(
            "res.company",
            "search_read",
            [[]],
            {"fields": ["country_id"], "limit": 1},
        )
        if companies:
            cid = companies[0].get("country_id")
            if isinstance(cid, (list, tuple)) and len(cid) >= 2:
                country_code = str(client.execute_kw(
                    "res.country",
                    "read",
                    [[int(cid[0])]],
                    {"fields": ["code"]},
                )[0].get("code") or "").upper() or None
    except Exception:  # noqa: BLE001
        country_code = None

    installed = client.list_installed_modules(name_prefix="l10n_", limit=400)
    l10n_names = [m.name for m in installed if m.name.startswith("l10n_")]
    matched: list[str] = []
    if country_code:
        prefix = f"l10n_{country_code.lower()}"
        matched = [n for n in l10n_names if n == prefix or n.startswith(f"{prefix}_")]
    l10n_ok = bool(matched) if country_code else bool(l10n_names)

    if not l10n_ok:
        msg = (
            f"No fiscal localization module detected for country {country_code or 'unknown'}. "
            "Install the matching l10n_* module before generating invoices."
            if country_code
            else "No l10n_* modules installed — fiscal localization unknown."
        )
        return {
            "ok": False,
            "account_installed": True,
            "l10n_installed": False,
            "company_country": country_code,
            "l10n_modules": matched or l10n_names[:10],
            "message": msg,
        }

    return {
        "ok": True,
        "account_installed": True,
        "l10n_installed": True,
        "company_country": country_code,
        "l10n_modules": matched or l10n_names[:5],
        "message": "Accounting and fiscal localization detected.",
    }
