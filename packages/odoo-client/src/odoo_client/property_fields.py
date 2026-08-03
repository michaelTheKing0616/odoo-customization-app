"""Compendium §18 — Properties / PropertiesDefinition field helpers."""

from __future__ import annotations

from typing import Any, Literal

PropertyDefType = Literal[
    "char",
    "boolean",
    "integer",
    "float",
    "date",
    "datetime",
    "selection",
    "tags",
    "many2one",
    "many2many",
]

PROPERTY_DEF_TYPES: tuple[str, ...] = (
    "char",
    "boolean",
    "integer",
    "float",
    "date",
    "datetime",
    "selection",
    "tags",
    "many2one",
    "many2many",
)


def normalize_property_definition(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and normalize a properties definition list for Odoo write."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name or name in seen:
            continue
        ptype = str(raw.get("type") or "char")
        if ptype not in PROPERTY_DEF_TYPES:
            ptype = "char"
        entry: dict[str, Any] = {
            "name": name,
            "string": str(raw.get("string") or name.replace("_", " ").title()),
            "type": ptype,
        }
        if raw.get("default") not in (None, ""):
            entry["default"] = raw["default"]
        if ptype == "selection" and raw.get("selection"):
            entry["selection"] = raw["selection"]
        if ptype in {"many2one", "many2many"} and raw.get("comodel"):
            entry["comodel"] = raw["comodel"]
        seen.add(name)
        out.append(entry)
    return out
