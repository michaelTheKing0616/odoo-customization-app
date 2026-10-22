"""Packet-backed inspection tools. No second schema cache.

``describe_model`` / ``describe_field`` read ``SchemaPacket`` only.
``view_get`` / ``view_test_xpath`` use ``SchemaGraph.combined_arch`` from the
same graph that built the packet. Results stay plain data for wrap_untrusted.
"""

from __future__ import annotations

from typing import Any

from odoo_client.schema_graph import SchemaGraph, xpath_matches

from app.live_schema_context import PacketField, SchemaPacket

def _field_payload(field: PacketField) -> dict[str, Any]:
    return {
        "name": field.name,
        "type": field.type,
        "relation": field.relation,
        "required": field.required,
        "readonly": field.readonly,
        "store": field.store,
        "groups": field.groups,
    }


def resolve_schema_packet(
    held: SchemaPacket | None,
) -> SchemaPacket | None:
    """Return the runtime-held packet, else the request-bound packet.

    Inputs: optional packet already on the runtime.
    Outputs: that packet, or ``current_schema_packet()``, or None.
    Side effects: none. Does not build or cache a second schema.
    """

    if held is not None:
        return held
    try:
        from app.ai_conversation.intent_llm import current_schema_packet

        return current_schema_packet()
    except Exception:  # noqa: BLE001
        return None


def describe_model_result(
    args: dict[str, Any],
    packet: SchemaPacket | None,
) -> dict[str, Any]:
    """Return fields that are a subset of the packet for ``model``.

    Inputs: tool args (``model``) and the live/fixture packet.
    Outputs: ``model`` and ``fields`` (packet field dicts only). A miss or
    absent packet yields an empty ``fields`` list — nothing is invented.
    Side effects: none.
    """

    model = str(args.get("model") or "").strip()
    if not model or packet is None:
        return {"model": args.get("model"), "fields": [], "found": False}
    row = packet.models.get(model)
    if row is None:
        return {"model": model, "fields": [], "found": False}
    fields = [_field_payload(field) for field in row.fields.values()]
    return {"model": model, "fields": fields, "found": True}


def describe_field_result(
    args: dict[str, Any],
    packet: SchemaPacket | None,
) -> dict[str, Any]:
    """Return one field meta from the packet, or an honest miss.

    Inputs: tool args (``model``, ``field``) and the packet.
    Outputs: packet field subset when present; ``found`` false otherwise.
    Side effects: none. Does not invent types or relations.
    """

    model = str(args.get("model") or "").strip()
    field_name = str(args.get("field") or args.get("name") or "").strip()
    if not model or not field_name or packet is None:
        return {
            "model": args.get("model"),
            "field": args.get("field") or args.get("name"),
            "found": False,
            "meta": None,
        }
    row = packet.models.get(model)
    field = row.fields.get(field_name) if row is not None else None
    if field is None:
        return {"model": model, "field": field_name, "found": False, "meta": None}
    return {
        "model": model,
        "field": field_name,
        "found": True,
        "meta": _field_payload(field),
    }


def view_get_result(
    args: dict[str, Any],
    *,
    packet: SchemaPacket | None,
    schema_graph: SchemaGraph | None,
) -> dict[str, Any]:
    """Return ``combined_arch`` from the same graph the packet used.

    Inputs: tool args (``model``, optional ``view_type``), packet, graph.
    Outputs: arch string from ``SchemaGraph.combined_arch`` when the graph
    can resolve it; optional ``field_order`` from the packet when present.
    Side effects: read-only graph call. No second view stack.
    """

    model = str(args.get("model") or "").strip()
    view_type = str(args.get("view_type") or args.get("type") or "form").strip() or "form"
    field_order: list[str] = []
    if packet is not None and model in packet.models:
        field_order = list(packet.models[model].views.get(view_type) or ())
    if not model or schema_graph is None:
        return {
            "model": args.get("model"),
            "view_type": view_type,
            "arch": None,
            "field_order": field_order,
            "found": False,
            "arch_source": None,
        }
    if packet is not None and model not in packet.models:
        return {
            "model": model,
            "view_type": view_type,
            "arch": None,
            "field_order": [],
            "found": False,
            "arch_source": None,
        }
    try:
        arch = schema_graph.combined_arch(model, view_type)
    except Exception:  # noqa: BLE001
        return {
            "model": model,
            "view_type": view_type,
            "arch": None,
            "field_order": field_order,
            "found": False,
            "arch_source": "combined_arch",
        }
    return {
        "model": model,
        "view_type": view_type,
        "arch": arch,
        "field_order": field_order,
        "found": True,
        "arch_source": "combined_arch",
    }


def view_test_xpath_result(
    args: dict[str, Any],
    *,
    packet: SchemaPacket | None,
    schema_graph: SchemaGraph | None,
) -> dict[str, Any]:
    """Evaluate xpath against ``combined_arch`` from the packet's graph.

    Inputs: tool args (``model``, ``xpath`` / ``selector``, optional
    ``view_type``), the packet, and the SchemaGraph used to build it.
    Outputs: match count from ``xpath_matches``; miss when the model is
    outside the packet, the graph is absent, or the selector finds nothing.
    Side effects: read-only ``combined_arch`` call. Does not invent nodes.
    """

    model = str(args.get("model") or "").strip()
    view_type = str(args.get("view_type") or args.get("type") or "form").strip() or "form"
    xpath = str(args.get("xpath") or args.get("selector") or "").strip()
    base = {
        "model": args.get("model"),
        "view_type": view_type,
        "xpath": args.get("xpath") or args.get("selector"),
        "matched": False,
        "count": 0,
        "arch_source": None,
    }
    if not model or not xpath or schema_graph is None:
        return base
    if packet is not None and model not in packet.models:
        return {**base, "model": model, "xpath": xpath}
    try:
        arch = schema_graph.combined_arch(model, view_type)
        count = xpath_matches(arch, xpath)
    except Exception:  # noqa: BLE001
        return {
            "model": model,
            "view_type": view_type,
            "xpath": xpath,
            "matched": False,
            "count": 0,
            "arch_source": "combined_arch",
        }
    return {
        "model": model,
        "view_type": view_type,
        "xpath": xpath,
        "matched": count > 0,
        "count": count,
        "arch_source": "combined_arch",
    }


__all__ = [
    "describe_field_result",
    "describe_model_result",
    "resolve_schema_packet",
    "view_get_result",
    "view_test_xpath_result",
]
