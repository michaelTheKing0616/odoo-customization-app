"""Probe Properties / PropertiesDefinition availability per Odoo major (CMP-7 §18)."""

from __future__ import annotations

from typing import Any

from odoo_client.client import OdooClient

# Conservative fallback when live probe unavailable (16 experimental).
PROPERTY_PROBE_FALLBACK: dict[int, dict[str, bool]] = {
    16: {
        "ttype_properties": False,
        "ttype_properties_definition": False,
        "definition_record_column": False,
        "definition_write": False,
        "rpc_create": False,
        "supported": False,
    },
    17: {
        "ttype_properties": True,
        "ttype_properties_definition": True,
        "definition_record_column": True,
        "definition_write": True,
        "rpc_create": True,
        "supported": True,
    },
    18: {
        "ttype_properties": True,
        "ttype_properties_definition": True,
        "definition_record_column": True,
        "definition_write": True,
        "rpc_create": True,
        "supported": True,
    },
    19: {
        "ttype_properties": True,
        "ttype_properties_definition": True,
        "definition_record_column": True,
        "definition_write": True,
        "rpc_create": True,
        "supported": True,
    },
}


def _selection_values(fields_get: dict[str, Any], field: str) -> set[str]:
    meta = fields_get.get(field) or {}
    sel = meta.get("selection")
    if not sel:
        return set()
    out: set[str] = set()
    for item in sel:
        if isinstance(item, (list, tuple)) and item:
            out.add(str(item[0]))
    return out


def probe_table_for_major(major: int) -> list[dict[str, Any]]:
    fb = PROPERTY_PROBE_FALLBACK.get(major, PROPERTY_PROBE_FALLBACK[19])
    return [{"major": major, "source": "fixture", **fb}]


def probe_property_fields(client: OdooClient) -> dict[str, Any]:
    """Return property-field capability truth for this connection."""
    major = int(getattr(client.capabilities, "major", 19) or 19)
    fb = dict(PROPERTY_PROBE_FALLBACK.get(major, PROPERTY_PROBE_FALLBACK[19]))
    source = "fallback"
    row: dict[str, Any] = {"major": major, "source": source, **fb}

    try:
        fg = client.execute_kw(
            "ir.model.fields",
            "fields_get",
            [],
            {"attributes": ["selection", "type"]},
        )
        ttypes = _selection_values(fg, "ttype")
        row["ttype_properties"] = "properties" in ttypes
        row["ttype_properties_definition"] = "properties_definition" in ttypes
        row["definition_record_column"] = "definition_record" in fg
        row["definition_record_field_column"] = "definition_record_field" in fg
        row["supported"] = bool(
            row["ttype_properties"]
            and row["ttype_properties_definition"]
            and row["definition_record_column"]
        )
        source = "live"
        row["source"] = source
    except Exception:  # noqa: BLE001
        pass

    return {
        "major": major,
        "source": source,
        "supported": bool(row.get("supported")),
        "probe_table": [row],
    }
