"""Inherit field-pack Open-in-Odoo target — stock act_window, no new app tile."""

from __future__ import annotations

from typing import Any

from app.ai_grain import inherit_open_xml_ids
from app.spec_apply_ui import inherit_host_model_from_spec, resolve_inherit_open_target


class _XmlFake:
    def __init__(self, xmlids: dict[str, int], actions: list[dict[str, Any]] | None = None) -> None:
        self.xmlids = xmlids
        self.actions = actions or []

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None):
        if model == "ir.model.data" and method == "search_read":
            domain = args[0] if args else []
            module = name = None
            for term in domain:
                if not isinstance(term, (list, tuple)) or len(term) < 3:
                    continue
                if term[0] == "module":
                    module = term[2]
                elif term[0] == "name":
                    name = term[2]
            rid = self.xmlids.get(f"{module}.{name}")
            return [{"res_id": rid}] if rid else []
        if model == "ir.actions.act_window" and method == "search_read":
            return list(self.actions)
        return []


def test_vendor_bill_prompt_picks_in_invoice_xmlids() -> None:
    ids = inherit_open_xml_ids(
        "account.move",
        "On vendor bills only, add Vendor TIN.",
    )
    assert ids[0] == "account.action_move_in_invoice_type"
    customer = inherit_open_xml_ids("account.move", "add SLA due date on invoices")
    assert customer[0] == "account.action_move_out_invoice_type"
    from_title = inherit_open_xml_ids("account.move", "Vendor bill fields")
    assert from_title[0] == "account.action_move_in_invoice_type"


def test_inherit_host_from_field_pack_spec() -> None:
    spec = {
        "grain": "field_pack",
        "models": [{"model": "account.move", "mode": "inherit", "fields": []}],
    }
    assert inherit_host_model_from_spec(spec) == "account.move"


def test_resolve_inherit_open_target_vendor_bills() -> None:
    client = _XmlFake({"account.action_move_in_invoice_type": 241})
    spec = {
        "_user_prompt": "On vendor bills only, add Vendor TIN.",
        "models": [{"model": "account.move", "mode": "inherit"}],
    }
    host, action_id = resolve_inherit_open_target(client, spec)
    assert host == "account.move"
    assert action_id == 241


def test_resolve_inherit_open_target_falls_back_to_act_window() -> None:
    client = _XmlFake(
        {},
        actions=[
            {
                "id": 9,
                "name": "Bills",
                "domain": "[('move_type','=','in_invoice')]",
                "context": "{}",
            }
        ],
    )
    spec = {
        "_user_prompt": "On vendor bills only, add Vendor TIN.",
        "models": [{"model": "account.move", "mode": "inherit"}],
    }
    host, action_id = resolve_inherit_open_target(client, spec)
    assert host == "account.move"
    assert action_id == 9
