from app.ai_conversation import brief_checklist as bc
from app.ai_conversation.app_design import AppDesign, _contract_for_designer


def test_addendum_asks_stock_and_service():
    assert "stock_options" in bc.CONTRACT_ADDENDUM and "service" in bc.CONTRACT_ADDENDUM


def test_parse_keeps_stock_fields():
    raw = {"checklist": [{"id": "a", "item": "Quotes", "status": "build", "quote": "quotes", "plan": "stock",
                          "stock_options": [{"module": "sale"}], "service": "Paystack", "type": "money"}]}
    items = bc.parse_checklist(raw, "We send quotes to clients")
    assert items[0]["plan"] == "stock" and items[0]["service"] == "Paystack" and items[0]["type"] == "money"


def test_design_roundtrip_and_designer_rows():
    d = AppDesign.from_dict({"stock_checks": [{"item": "Q", "label": "Using Odoo's Sales", "choice": "stock"}],
                             "integration_routes": [{"service": "GIG", "route": "decline", "reason": "x"}]})
    assert d.stock_checks and d.integration_routes
    rows = _contract_for_designer([{"id": "r", "decision": "metadata", "stock_plan": {"use": "sale.order"}}])
    assert any(r.get("stock_plan") for r in rows)
