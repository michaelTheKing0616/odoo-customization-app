from types import SimpleNamespace as NS

from app.ai_conversation import stock_routing as sr


def snap(modules=("sale",), installable=("sms_twilio",), models=("sale.order",), states=("code", "webhook"), triggers=("on_create", "on_webhook")):
    sel = {("ir.actions.server", "state"): list(states), ("base.automation", "trigger"): list(triggers)}
    return NS(modules=set(modules), installable={m: "uninstalled" for m in installable},
              index={m: {} for m in models}, selection_of=lambda m, f: sel.get((m, f), []), major=18, edition="community")


def test_stock_used_when_installed():
    c = sr.stock_check({"item": "Quotes", "stock_options": [{"module": "sale", "model": "sale.order", "name": "Sales"}], "plan": "stock"}, snap())
    assert c["choice"] == "stock" and "Using Odoo" in c["label"]


def test_custom_without_reason_overridden_when_stock_fits():
    c = sr.stock_check({"item": "Quotes", "stock_options": [{"module": "sale", "model": "sale.order"}], "plan": "custom"}, snap())
    assert c["choice"] == "stock" and c.get("overrode_custom")


def test_ai_custom_reason_is_display_only():
    c = sr.stock_check({"item": "Quotes", "stock_options": [{"module": "sale"}], "plan": "custom", "custom_reason": "sale is not installed"}, snap())
    assert c["choice"] == "stock" and c["ai_reason"] == "sale is not installed"


def test_no_absent_claim_without_snapshot():
    c = sr.stock_check({"item": "Quotes", "stock_options": [{"module": "sale"}]}, None)
    assert c["choice"] == "custom" and not c["verified_reason"]


def test_installable_offers_install():
    c = sr.stock_check({"item": "SMS", "stock_options": [{"module": "sms_twilio"}], "plan": "stock"}, snap())
    assert c["choice"] == "stock" and c.get("install") == "sms_twilio"


def test_absent_stock_goes_custom():
    c = sr.stock_check({"item": "X", "stock_options": [{"module": "nope"}], "plan": "stock"}, snap())
    assert c["choice"] == "custom" and "not available on this database" in c["verified_reason"]


def test_route_ladder():
    s = snap()
    assert sr.route_service({"service": "Twilio SMS", "service_modules": ["sms_twilio"]}, s)["route"] == "stock"
    assert sr.route_service({"service": "Zapier", "service_direction": "send", "service_needs_api": False}, s)["route"] == "webhook"
    assert sr.route_service({"service": "Shopify", "service_needs_api": True}, s)["route"] == "bridge"
    d = sr.route_service({"service": "GIG Logistics", "service_needs_api": True, "service_modules": ["delivery_gig"]}, s)
    assert d["route"] == "decline" and d["reason"]
    assert sr.route_service({"item": "plain"}, s) is None


def test_webhook_gated_by_version():
    s = snap(states=("code",), triggers=("on_create",))
    assert sr.route_service({"service": "Zapier", "service_direction": "send", "service_needs_api": False}, s)["route"] == "decline"


def test_register_caps_and_quotes():
    items = [{"id": f"i{n}", "item": f"Item {n}", "type": "money", "decision": {"source": "ask", "question": "Which currency?", "options": ["NGN"]}} for n in range(5)]
    items.append({"id": "q", "item": "Price", "type": "money", "decision": {"source": "quoted", "quote": "in naira", "value": "NGN"}})
    items.append({"id": "s", "item": "Status", "type": "status", "decision": {"source": "ask", "question": "Stages?", "value": "New, Done"}})
    r = sr.register(items, lambda q: q == "in naira")
    assert len(r["questions"]) == sr.MAX_BLOCKING
    assert [q["id"] for q in r["quoted"]] == ["q"]
    assert all(q["type"] in sr.RISKY_TYPES or q.get("effects") for q in r["questions"])
    assert any(d["id"] == "s" for d in r["defaults"])


def _design():
    from app.ai_conversation.app_design import AppDesign
    return AppDesign.from_dict({"app_name": "Bakery", "new_models": [
        {"name": "x_bakery_order", "label": "Bakery Order", "fields": [
            {"name": "x_pickup", "ttype": "date"}, {"name": "x_currency_id", "ttype": "many2one", "relation": "res.currency"},
            {"name": "x_line_ids", "ttype": "one2many", "relation": "x_order_line", "inverse_name": "x_order_id"}]},
        {"name": "x_order_line", "label": "Order Line", "fields": [{"name": "x_order_id", "ttype": "many2one", "relation": "x_bakery_order"}]}],
        "automations": [{"label": "Remind", "target_model": "x_bakery_order", "automation": {"when": "on_create", "action": "notify"}}]})


class FakeSnap:
    index = {"sale.order": {}}
    modules = {"sale"}
    installable = {}
    def fields_of(self, m):
        return {"name", "partner_id"}


def test_enforce_converts_custom_onto_stock_host():
    d = _design()
    checks = [{"item": "Customer orders", "choice": "stock", "use": {"model": "sale.order", "module": "sale", "name": "Sales"}}]
    notes = sr.enforce_stock_first(d, checks, FakeSnap())
    assert notes and checks[0]["converted"] == "Bakery Order"
    assert [m.name for m in d.new_models] == ["x_order_line"]
    assert d.new_models[0].fields[0].relation == "sale.order"
    ext = d.stock_extensions[0]
    assert ext.model == "sale.order" and {f.name for f in ext.fields} == {"x_pickup", "x_line_ids"}
    assert d.automations[0]["target_model"] == "sale.order"


def test_enforce_keeps_custom_with_verified_reason_only():
    d = _design()
    checks = [{"item": "Customer orders", "choice": "stock", "install": "sale", "use": {"model": "sale.order", "module": "sale", "name": "Sales"}}]
    sr.enforce_stock_first(d, checks, FakeSnap())
    # S7: an installable domain host converts with an install suggestion (not a custom copy)
    assert checks[0]["install_suggested"] == "sale" and any(i.module == "sale" and i.installed is False for i in d.integrations)
    d = _design()
    checks = [{"item": "Customer orders", "choice": "stock", "use": {"model": "account.move", "module": "account", "name": "Invoicing"}}]
    snap_ = FakeSnap(); snap_.index = {"account.move": {}}
    sr.enforce_stock_first(d, checks, snap_)
    assert len(d.new_models) == 2 and "protected" in checks[0]["verified_reason"]
