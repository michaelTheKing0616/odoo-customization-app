"""LLM column mapping fallback when header aliases miss (ING-3, GND-G-MAP)."""

from __future__ import annotations
from app.ai_client.guards import fence_untrusted as _fence

import json
from types import SimpleNamespace
from typing import Any

from odoo_client import OdooClient

from app.ai_schema_client import LiveSchemaClient
from app.data_import import suggest_mapping
from app.live_schema_context import SchemaPacket, build_schema_packet, prepend_schema_packet
from app.llm_provider import LLMError, get_llm_provider


def _alias_coverage(model: str, headers: list[str], mapping: dict[str, str]) -> float:
    if not headers:
        return 0.0
    aliases = set(suggest_mapping(model, headers).values())
    hits = sum(1 for h in headers if mapping.get(h) and mapping[h] in aliases)
    return hits / len(headers)


def _column_schema_packet(
    client: OdooClient | None,
    model: str,
    schema_packet: SchemaPacket | None,
) -> SchemaPacket | None:
    """Packet for the import target model. No client and no packet → ``None``.

    Side effects: read-only ``model_exists`` / field reads on ``client``.
    """
    if schema_packet is not None:
        return schema_packet
    if client is None:
        return None
    try:
        return build_schema_packet(
            SimpleNamespace(id="ingest"),
            models=[model],
            schema_client=LiveSchemaClient(client),
        )
    except Exception:  # noqa: BLE001
        return None


def _llm_map_columns(
    *,
    model: str,
    headers: list[str],
    sample_rows: list[dict[str, str]],
    schema_packet: SchemaPacket | None,
) -> tuple[dict[str, str], list[str]]:
    """Return (header → field pairs on ``model`` in the packet, reasons for dropped pairs).

    No live field list for ``model`` → the LLM is not called.
    """
    packet_model = schema_packet.models.get(model) if schema_packet is not None else None
    if packet_model is None or not packet_model.fields:
        return {}, []
    provider = get_llm_provider()
    if provider is None:
        return {}, []
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "mapping": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            }
        },
        "required": ["mapping"],
    }
    prompt = prepend_schema_packet(
        (
            f"Map CSV headers to Odoo model {model} fields.\n"
            f"Allowed target fields: only the fields of MODEL {model} in the packet above.\n"
            + _fence(f"Headers: {headers}\nSample rows: {json.dumps(sample_rows[:2], ensure_ascii=False)[:800]}", "upload")
            + "\n"
            "Only map when confident; omit unknown headers."
        ),
        schema_packet,
    )
    try:
        raw = provider.generate_json(
            prompt,
            system="You map migration CSV columns to Odoo fields. Closed field list only.",
            temperature=0.1,
            format_schema=schema,
        )
        data = json.loads(raw) if isinstance(raw, str) else raw
        out = data.get("mapping") or {}
        pairs = {str(k): str(v).strip() for k, v in out.items() if v}
    except (LLMError, json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return {}, []
    kept: dict[str, str] = {}
    dropped: list[str] = []
    for header, target in pairs.items():
        if target in packet_model.fields:
            kept[header] = target
        else:
            dropped.append(
                f"column {header!r} left unmapped: LLM proposed {target!r}, "
                f"which is not a field on {model}"
            )
    return kept, dropped


def enhance_mapping_with_llm(
    client: OdooClient | None,
    *,
    model: str,
    headers: list[str],
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    min_coverage: float = 0.45,
    schema_packet: SchemaPacket | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Return (mapping, warnings). LLM used only when alias coverage is low.

    The LLM sees the live packet for ``model`` and may only map to its fields.
    No client (and no packet) or an empty field list → no LLM call.
    """
    warnings: list[str] = []
    coverage = _alias_coverage(model, headers, mapping)
    if coverage >= min_coverage:
        return mapping, warnings
    packet = _column_schema_packet(client, model, schema_packet)
    llm_map, dropped = _llm_map_columns(
        model=model,
        headers=headers,
        sample_rows=rows[:3],
        schema_packet=packet,
    )
    warnings.extend(dropped)
    if not llm_map:
        warnings.append("low alias coverage; LLM column map unavailable")
        return mapping, warnings
    merged = dict(mapping)
    for h, f in llm_map.items():
        if h in headers and f:
            merged[h] = f
    warnings.append(f"LLM column map applied (alias coverage was {coverage:.0%})")
    return merged, warnings
