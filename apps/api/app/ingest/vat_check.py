"""VAT / VIES validation for partner ingest — reuse Odoo base_vat when present."""

from __future__ import annotations

import re
from typing import Any

from odoo_client import OdooClient

from app.ingest.schema import IngestGap, IngestRow, IngestTable

_VAT_FORMAT = re.compile(r"^[A-Z]{2}[A-Z0-9]{2,12}$", re.I)


def base_vat_available(client: OdooClient) -> bool:
    try:
        mods = client.list_installed_modules(name_prefix="base_vat", limit=5)
        return any(m.name == "base_vat" for m in mods)
    except Exception:  # noqa: BLE001
        return False


def format_ok(vat: str) -> bool:
    cleaned = re.sub(r"[\s.\-]", "", (vat or "").strip())
    return bool(cleaned) and bool(_VAT_FORMAT.match(cleaned))


def check_vat_vies(
    client: OdooClient, vat: str
) -> tuple[bool, str]:
    """Return (ok, note). Uses Odoo partner check_vat when available."""
    cleaned = re.sub(r"[\s.\-]", "", (vat or "").strip()).upper()
    if not cleaned:
        return True, "empty"
    if not format_ok(cleaned):
        return False, f"VAT format invalid: {vat!r}"
    if not base_vat_available(client):
        return True, "format_only (base_vat not installed)"
    # Probe via temporary vals validation — Odoo exposes check_vat on res.partner
    try:
        # Prefer dedicated method if present
        methods = client.execute_kw(
            "ir.model",
            "search_read",
            [[("model", "=", "res.partner")]],
            {"fields": ["id"], "limit": 1},
        )
        _ = methods
        ok = client.execute_kw(
            "res.partner",
            "check_vat",
            [],
            {"context": {"default_vat": cleaned}},
        )
        # Many Odoo versions return True/None or raise ValidationError via create dry path
        if ok is False:
            return False, f"VIES/base_vat rejected {cleaned}"
        return True, "base_vat_ok"
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "vat" in msg or "vies" in msg:
            return False, f"VIES/base_vat: {exc}"
        # Method missing — format-only fallback
        return True, f"format_only ({exc.__class__.__name__})"


def validate_partner_vats(
    client: OdooClient, table: IngestTable
) -> tuple[list[IngestGap], list[str]]:
    if table.model != "res.partner":
        return [], []
    gaps: list[IngestGap] = []
    warnings: list[str] = []
    vat_headers = [h for h, f in table.mapping.items() if f == "vat"]
    if not vat_headers and "vat" not in {
        f for f in table.mapping.values()
    }:
        # also accept raw key
        vat_headers = ["vat"] if any("vat" in r.raw for r in table.rows) else []
    if not vat_headers:
        return [], []
    for row in table.rows:
        vat = ""
        for h in vat_headers:
            vat = str(row.raw.get(h) or row.values.get("vat") or "").strip()
            if vat:
                break
        if not vat:
            continue
        ok, note = check_vat_vies(client, vat)
        row.values["vat"] = re.sub(r"[\s.\-]", "", vat).upper()
        if not ok:
            gaps.append(
                IngestGap(
                    model="res.partner",
                    field="vat",
                    value=vat,
                    message=note,
                )
            )
            row.flags.append("vat_invalid")
        elif "format_only" in note:
            row.flags.append("vat_format_only")
            warnings.append(f"VAT {vat}: {note}")
    return gaps, warnings


def validate_row_vat(client: OdooClient, row: IngestRow) -> tuple[bool, str]:
    vat = str(row.values.get("vat") or row.raw.get("vat") or "")
    if not vat:
        return True, "empty"
    return check_vat_vies(client, vat)


__all__ = [
    "base_vat_available",
    "check_vat_vies",
    "format_ok",
    "validate_partner_vats",
]
