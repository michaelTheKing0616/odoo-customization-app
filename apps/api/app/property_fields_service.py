"""Properties field setup + definition writes (CMP-7)."""

from __future__ import annotations

from typing import Any

from odoo_client import CreateFieldRequest, FieldType, OdooClient
from odoo_client.client import OdooClientError
from odoo_client.property_fields import normalize_property_definition


def ensure_properties_definition_field(
    client: OdooClient,
    *,
    parent_model: str,
    field_name: str = "x_properties_definition",
    field_description: str = "Properties Definition",
) -> dict[str, Any]:
    if client.field_exists(parent_model, field_name):
        return {"created": False, "field_name": field_name, "model": parent_model}
    created = client.create_field(
        CreateFieldRequest(
            model=parent_model,
            name=field_name,
            field_description=field_description,
            ttype=FieldType.PROPERTIES_DEFINITION,
        )
    )
    return {"created": True, "field_name": created.name, "model": parent_model, "id": created.id}


def ensure_properties_field_on_child(
    client: OdooClient,
    *,
    child_model: str,
    parent_m2o_field: str,
    definition_field: str = "x_properties_definition",
    properties_field: str = "x_properties",
    field_description: str = "Properties",
) -> dict[str, Any]:
    if not client.field_exists(child_model, parent_m2o_field):
        raise OdooClientError(
            f"Parent m2o field {parent_m2o_field!r} missing on {child_model!r}"
        )
    parent_model = client.execute_kw(
        "ir.model.fields",
        "search_read",
        [[("model", "=", child_model), ("name", "=", parent_m2o_field)]],
        {"fields": ["relation"], "limit": 1},
    )
    if not parent_model or not parent_model[0].get("relation"):
        raise OdooClientError(f"Could not resolve relation for {parent_m2o_field}")
    parent = str(parent_model[0]["relation"])

    def_row = ensure_properties_definition_field(
        client, parent_model=parent, field_name=definition_field
    )

    if client.field_exists(child_model, properties_field):
        return {
            "created": False,
            "properties_field": properties_field,
            "definition_field": definition_field,
            "parent_model": parent,
            "definition_field_created": def_row.get("created"),
        }

    created = client.create_field(
        CreateFieldRequest(
            model=child_model,
            name=properties_field,
            field_description=field_description,
            ttype=FieldType.PROPERTIES,
            definition_record=parent_m2o_field,
            definition_record_field=definition_field,
        )
    )
    return {
        "created": True,
        "properties_field": created.name,
        "definition_field": definition_field,
        "parent_model": parent,
        "definition_field_created": def_row.get("created"),
        "id": created.id,
    }


def write_properties_definition(
    client: OdooClient,
    *,
    parent_model: str,
    parent_record_id: int,
    definition_field: str,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    if not client.field_exists(parent_model, definition_field):
        raise OdooClientError(
            f"Definition field {definition_field!r} not found on {parent_model!r}"
        )
    normalized = normalize_property_definition(entries)
    client.execute_kw(
        parent_model,
        "write",
        [[parent_record_id], {definition_field: normalized}],
    )
    return {
        "ok": True,
        "parent_model": parent_model,
        "record_id": parent_record_id,
        "definition_field": definition_field,
        "property_count": len(normalized),
    }
