"""i18n capability probe per Odoo major (CMP-11)."""

from __future__ import annotations

from typing import Any

from odoo_client.client import OdooClient, OdooClientError


def probe_i18n(client: OdooClient, *, major: int | None = None) -> dict[str, Any]:
    """Probe translation paths: context lang reads vs ir.translation."""
    resolved_major = major
    if resolved_major is None:
        try:
            from odoo_client.compat import parse_major

            resolved_major = parse_major(str(client.server_version().get("server_version") or ""))
        except Exception:  # noqa: BLE001
            resolved_major = None

    has_ir_translation = client.model_exists("ir.translation")
    context_lang = False
    try:
        rows = client.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "=", "res.partner"), ("name", "=", "name")]],
            {
                "fields": ["field_description"],
                "limit": 1,
                "context": {"lang": "fr_FR"},
            },
        )
        context_lang = bool(rows)
    except OdooClientError:
        context_lang = False

    method = "context_lang" if context_lang else ("ir_translation" if has_ir_translation else "none")
    supported = context_lang or has_ir_translation

    return {
        "ok": supported,
        "major": resolved_major,
        "method": method,
        "context_lang_reads": context_lang,
        "ir_translation_model": has_ir_translation,
        "message": (
            "Field/menu translations via context lang reads (Odoo 17–19 GA path)."
            if context_lang
            else (
                "ir.translation model available — verify write API on this major."
                if has_ir_translation
                else "No supported translation RPC path detected."
            )
        ),
    }
