"""CMP-7 property fields definition normalization."""

from __future__ import annotations

from odoo_client.property_fields import normalize_property_definition


def test_normalize_property_definition_dedupes_and_types() -> None:
    out = normalize_property_definition(
        [
            {"name": "color", "string": "Color", "type": "char", "default": "red"},
            {"name": "color", "type": "integer"},
            {
                "name": "priority",
                "type": "selection",
                "selection": [["low", "Low"], ["high", "High"]],
            },
        ]
    )
    assert len(out) == 2
    assert out[0]["name"] == "color"
    assert out[1]["selection"]
