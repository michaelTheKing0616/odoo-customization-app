"""Bridge B3 (spec item 7): field-mapping studio core.

Code matches remote fields to Odoo fields with a confidence, checks type compatibility,
applies transforms and previews on real sample records. An AI suggestion may be added on top,
but every pair passes check_pair() before it is accepted (AI proposes, code authorizes).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any

SYN = {
    "email": ["email_address", "mail", "e_mail"],
    "phone": ["telephone", "tel", "mobile", "phone_number"],
    "name": ["title", "full_name", "display_name"],
    "street": ["address1", "address_line1", "line1"],
    "zip": ["postcode", "postal_code", "zipcode"],
    "default_code": ["sku", "code", "item_code"],
    "list_price": ["price", "unit_price", "sale_price"],
    "amount_total": ["total", "grand_total", "total_price"],
    "date_order": ["created_at", "order_date", "placed_at"],
    "partner_id": ["customer", "customer_id", "contact"],
    "product_uom_qty": ["quantity", "qty"],
    "country_id": ["country", "country_code"],
    "vat": ["tax_id", "tin"],
}
COMPAT = {
    "char": {"char", "text", "selection", "html"},
    "integer": {"integer", "float", "monetary", "char"},
    "float": {"float", "monetary", "char"},
    "boolean": {"boolean"},
    "date": {"date", "datetime", "char"},
    "datetime": {"datetime", "date", "char"},
    "many2one": {"many2one"},
    "list": {"one2many", "many2many"},
    "dict": {"char", "text"},
}
TRANSFORMS = (
    "none",
    "trim",
    "lower",
    "upper",
    "to_int",
    "to_float",
    "cents_to_units",
    "to_date",
    "to_datetime",
    "to_bool",
)
READONLY_SKIP = {
    "id",
    "create_uid",
    "write_uid",
    "create_date",
    "write_date",
    "__last_update",
    "display_name",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def score(remote: str, odoo: str, label: str = "") -> float:
    r, o = _norm(remote), _norm(odoo)
    if r == o:
        return 1.0
    if r in SYN.get(o, []) or o in SYN.get(r, []):
        return 0.92
    base = o[:-3] if o.endswith("_id") else o
    if r == base or r == base + "s":
        return 0.9
    return round(
        max(
            SequenceMatcher(None, r, o).ratio(),
            SequenceMatcher(None, r, _norm(label)).ratio() if label else 0,
        )
        * 0.85,
        2,
    )


def check_pair(rtype: str, ofield: dict[str, Any]) -> tuple[bool, str]:
    ot = ofield.get("type", "")
    if ofield.get("readonly") and not ofield.get("store", True):
        return False, "computed field (read-only)"
    if ot not in COMPAT.get(rtype, {rtype}):
        return False, f"{rtype} can't go into {ot}"
    return True, ""


def suggest(
    remote_fields: dict[str, str], odoo_fields: dict[str, dict[str, Any]], floor: float = 0.6
) -> list[dict[str, Any]]:
    out = []
    used: set[str] = set()
    for rname, rtype in remote_fields.items():
        cands = []
        for oname, of in odoo_fields.items():
            if oname in READONLY_SKIP or oname in used:
                continue
            ok, _ = check_pair(rtype, of)
            if not ok:
                continue
            cands.append((score(rname, oname, of.get("string", "")), oname, of))
        cands.sort(key=lambda c: -c[0])
        if cands and cands[0][0] >= floor:
            sc, oname, of = cands[0]
            used.add(oname)
            out.append(
                {
                    "remote": rname,
                    "odoo": oname,
                    "confidence": sc,
                    "transform": default_transform(rtype, of),
                    "money": of.get("type") == "monetary",
                    "needs_review": sc < 0.85 or of.get("type") == "monetary",
                }
            )
        else:
            out.append(
                {
                    "remote": rname,
                    "odoo": None,
                    "confidence": 0.0,
                    "transform": "none",
                    "money": False,
                    "needs_review": True,
                }
            )
    return out


def default_transform(rtype: str, of: dict[str, Any]) -> str:
    ot = of.get("type")
    if rtype == "char" and ot in ("char", "text"):
        return "trim"
    if rtype in ("integer", "char") and ot in ("float", "monetary"):
        return "to_float"
    if rtype == "datetime" and ot == "date":
        return "to_date"
    return "none"


def apply_transform(name: str, v: Any) -> Any:
    if v is None or name == "none":
        return v
    if name == "trim":
        return str(v).strip()
    if name == "lower":
        return str(v).lower()
    if name == "upper":
        return str(v).upper()
    if name == "to_int":
        return int(float(v))
    if name == "to_float":
        return float(v)
    if name == "cents_to_units":
        return round(float(v) / 100, 2)
    if name == "to_date":
        return (
            datetime.fromisoformat(str(v).replace("Z", "+00:00")).date()
            if "T" in str(v)
            else date.fromisoformat(str(v))
        ).isoformat()
    if name == "to_datetime":
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    if name == "to_bool":
        return str(v).strip().lower() in ("1", "true", "yes", "y", "on")
    raise ValueError(f"unknown transform {name}")


def validate_mapping(
    mapping: list[dict[str, Any]],
    remote_fields: dict[str, str],
    odoo_fields: dict[str, dict[str, Any]],
) -> list[str]:
    errs = []
    seen: set[str] = set()
    for m in mapping:
        o = m.get("odoo")
        if not o:
            continue
        if m.get("remote") not in remote_fields:
            errs.append(f"{m.get('remote')}: not in the source")
        elif o not in odoo_fields:
            errs.append(f"{o}: not a field on this Odoo model")
        else:
            ok, why = check_pair(remote_fields[m["remote"]], odoo_fields[o])
            if not ok:
                errs.append(f"{m['remote']} → {o}: {why}")
        if o in seen:
            errs.append(f"{o}: mapped twice")
        seen.add(o)
        if m.get("transform", "none") not in TRANSFORMS:
            errs.append(f"{m.get('transform')}: unknown transform")
    req = [
        n
        for n, f in odoo_fields.items()
        if f.get("required") and n not in READONLY_SKIP and not f.get("default_set")
    ]
    missing = [n for n in req if n not in seen]
    if missing:
        errs.append("Required in Odoo but not mapped: " + ", ".join(missing))
    return errs


def preview(mapping: list[dict[str, Any]], samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for s in samples[:20]:
        out, problems = {}, []
        for m in mapping:
            if not m.get("odoo"):
                continue
            try:
                out[m["odoo"]] = apply_transform(m.get("transform", "none"), s.get(m["remote"]))
            except (ValueError, TypeError) as exc:
                problems.append(f"{m['remote']}: {exc.__class__.__name__}")
        rows.append({"values": out, "problems": problems})
    return rows


def odoo_fields(client: Any, model: str) -> dict[str, dict[str, Any]]:
    """Live, read-only: fields_get + default_get so required-with-default fields don't block."""
    fg = client.execute_kw(
        model,
        "fields_get",
        [],
        {"attributes": ["type", "string", "required", "readonly", "store", "relation"]},
    )
    req = [n for n, f in fg.items() if f.get("required")]
    defaults = client.execute_kw(model, "default_get", [req]) if req else {}
    for n in defaults or {}:
        if n in fg:
            fg[n]["default_set"] = True
    return fg
