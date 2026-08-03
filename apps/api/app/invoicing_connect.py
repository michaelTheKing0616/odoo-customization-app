"""Connect-to-Invoicing — link-only billing pattern (CMP-8 §19)."""

from __future__ import annotations

from typing import Any

from odoo_client import CreateFieldRequest, FieldType, OdooClient
from odoo_client.actions import CreateRelatedCountField
from odoo_client.client import OdooClientError
from odoo_client.view_arch import ButtonNode

DEFAULT_INVOICE_M2M = "x_invoice_ids"
DEFAULT_PARTNER_FIELD = "x_partner_id"
DEFAULT_AMOUNT_FIELD = "x_amount"
DEFAULT_DESC_FIELD = "x_name"


def module_spec_fragment(
    *,
    model: str,
    invoice_field: str = DEFAULT_INVOICE_M2M,
    origin_field_on_move: str = "x_origin_id",
    partner_field: str = DEFAULT_PARTNER_FIELD,
) -> dict[str, Any]:
    """Module-export path: o2m on custom model + inverse m2o on account.move (review note)."""
    return {
        "depends_add": ["account"],
        "review_note": (
            "Module path adds inverse m2o on account.move — standard Odoo module practice; "
            "live-metadata path uses many2many on the custom model only."
        ),
        "models": [
            {
                "model": model,
                "fields": [
                    {
                        "name": invoice_field,
                        "ttype": "one2many",
                        "string": "Invoices",
                        "relation": "account.move",
                        "relation_field": origin_field_on_move,
                    },
                    {
                        "name": partner_field,
                        "ttype": "many2one",
                        "string": "Customer",
                        "relation": "res.partner",
                    },
                ],
            },
            {
                "model": "account.move",
                "mode": "inherit",
                "inherit": "account.move",
                "fields": [
                    {
                        "name": origin_field_on_move,
                        "ttype": "many2one",
                        "string": "Origin",
                        "relation": model,
                    },
                ],
            },
        ],
        "smart_button": {
            "name": "Invoices",
            "source_model": model,
            "target_model": "account.move",
            "relation_field": origin_field_on_move,
            "one2many_field": invoice_field,
        },
        "server_action": {
            "name": "Create draft invoice",
            "model": model,
            "target_model": "account.move",
            "partner_field": partner_field,
        },
    }


def connect_live_metadata(
    client: OdooClient,
    *,
    model: str,
    invoice_field: str = DEFAULT_INVOICE_M2M,
    smart_button_name: str = "Invoices",
    inject_form: bool = True,
) -> dict[str, Any]:
    """Live path: m2m on custom model + smart button (no account.move field writes)."""
    if not model.startswith("x_"):
        raise OdooClientError("Connect-to-Invoicing requires a custom x_* model")
    if not client.model_exists("account.move"):
        raise OdooClientError("account.move not available — install account module")

    created_field = False
    if not client.field_exists(model, invoice_field):
        client.create_field(
            CreateFieldRequest(
                model=model,
                name=invoice_field,
                field_description="Invoices",
                ttype=FieldType.MANY2MANY,
                relation="account.move",
            )
        )
        created_field = True

    count_name = invoice_field.replace("_ids", "_count")
    if not count_name.startswith("x_"):
        count_name = f"x_{count_name}"
    count_created = False
    if not client.field_exists(model, count_name):
        client.create_related_count_field(
            CreateRelatedCountField(
                model=model,
                name=count_name,
                field_description=smart_button_name,
                one2many_field=invoice_field,
            )
        )
        count_created = True

    domain = f"[('id', 'in', {invoice_field})]"
    context = "{'default_move_type': 'out_invoice'}"
    action_id = client.create_window_action(
        name=smart_button_name,
        model="account.move",
        view_mode="list,form",
        domain=domain,
        context=context,
    )
    button_spec = {
        "kind": "button",
        "string": smart_button_name,
        "name": str(action_id),
        "type": "action",
        "class": "oe_stat_button",
        "icon": "fa-pencil-square-o",
        "count_field": count_name,
    }
    view_info = None
    if inject_form:
        view_info = client.inject_smart_buttons_into_form(
            model,
            [
                ButtonNode(
                    string=smart_button_name,
                    name=str(action_id),
                    type="action",
                    class_name="oe_stat_button",
                    icon="fa-pencil-square-o",
                    count_field=count_name,
                )
            ],
        )
    return {
        "ok": True,
        "path": "live_metadata_m2m",
        "invoice_field": invoice_field,
        "field_created": created_field,
        "count_field": count_name,
        "count_field_created": count_created,
        "window_action_id": action_id,
        "button_spec": button_spec,
        "form_view_id": getattr(view_info, "id", None),
        "form_view_name": getattr(view_info, "name", None),
    }


def create_draft_invoice_linked(
    client: OdooClient,
    *,
    source_model: str,
    record_id: int,
    invoice_field: str = DEFAULT_INVOICE_M2M,
    partner_field: str = DEFAULT_PARTNER_FIELD,
    amount_field: str = DEFAULT_AMOUNT_FIELD,
    description_field: str = DEFAULT_DESC_FIELD,
) -> dict[str, Any]:
    """Create draft out_invoice and link via m2m — never posts."""
    if not source_model.startswith("x_"):
        raise OdooClientError("Draft invoice link requires custom source model")
    if not client.model_exists("account.move"):
        raise OdooClientError("account.move not available")

    rec = client.execute_kw(
        source_model,
        "read",
        [[record_id]],
        {"fields": [partner_field, amount_field, description_field, invoice_field]},
    )
    if not rec:
        raise OdooClientError(f"Record {record_id} not found on {source_model}")
    row = rec[0]
    partner_id = row.get(partner_field)
    if isinstance(partner_id, (list, tuple)):
        partner_id = partner_id[0] if partner_id else None
    if not partner_id:
        raise OdooClientError(f"Partner field {partner_field!r} is empty on record")

    amount = float(row.get(amount_field) or 0.0)
    desc = str(row.get(description_field) or source_model)
    move_vals: dict[str, Any] = {
        "move_type": "out_invoice",
        "partner_id": int(partner_id),
        "invoice_line_ids": [
            (
                0,
                0,
                {
                    "name": desc,
                    "quantity": 1,
                    "price_unit": amount,
                },
            )
        ],
    }
    move_id = int(client.execute_kw("account.move", "create", [move_vals]))
    move = client.execute_kw(
        "account.move",
        "read",
        [[move_id]],
        {"fields": ["state", "name"]},
    )[0]
    if str(move.get("state")) not in {"draft", "cancel"}:
        raise OdooClientError("Invoice was not left in draft state")

    client.execute_kw(
        source_model,
        "write",
        [[record_id], {invoice_field: [(4, move_id)]}],
    )
    return {
        "ok": True,
        "move_id": move_id,
        "move_name": move.get("name"),
        "state": move.get("state"),
        "source_model": source_model,
        "record_id": record_id,
    }
