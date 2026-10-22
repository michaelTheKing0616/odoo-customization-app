import pytest

from app.ai_schema_client import FakeSchemaClient
from app.design_admission import (SUPPORTED_MAJORS, admit_design_for_connection, validate_compiled_views,
                                  validate_design, view_tag_for)


def _schema():
    return FakeSchemaClient(models={"res.partner", "crm.lead", "res.users", "x_legacy"},
                            fields={"crm.lead": {"name": {"type": "char"}, "x_ro": {"type": "char", "readonly": True},
                                                 "probability": {"type": "float"}}})


def _good():
    return {"new_models": [
        {"name": "x_booking", "fields": [
            {"name": "x_name", "ttype": "char"},
            {"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner"},
            {"name": "x_date", "ttype": "date"},
            {"name": "x_state", "ttype": "selection", "selection": [["draft", "Draft"]]},
            {"name": "x_line_ids", "ttype": "one2many", "relation": "x_booking_line", "inverse_name": "x_booking_id"}]},
        {"name": "x_booking_line", "fields": [{"name": "x_name", "ttype": "char"},
                                              {"name": "x_booking_id", "ttype": "many2one", "relation": "x_booking"}]}],
        "security_groups": [{"name": "Rental Manager"}],
        "stock_extensions": [{"model": "crm.lead", "fields": [{"name": "x_source_event", "ttype": "char"}]}],
        "automations": [
            {"label": "remind", "target_model": "x_booking", "automation": {"when": "on_time", "action": "activity", "date_field": "x_date"}},
            {"label": "stale", "target_model": "x_booking", "automation": {"when": "untouched", "action": "notify", "offset_days": 5, "group": "Rental Manager"}},
            {"label": "close", "target_model": "x_booking", "automation": {"when": "on_write", "action": "set_fields", "values": {"x_state": "draft"}}}]}


@pytest.mark.parametrize("major", SUPPORTED_MAJORS)
def test_valid_design_admitted_on_every_supported_version(major):
    res = validate_design(_good(), _schema(), major=major)
    assert res.ok, res.errors
    assert res.checked["automations"] == 3 and res.checked["relations"] == 3


@pytest.mark.parametrize("major", SUPPORTED_MAJORS)
def test_bad_design_fails_closed_with_specific_errors(major):
    d = _good()
    d["new_models"][0]["fields"] += [{"name": "x_bad", "ttype": "many2one", "relation": "x_nowhere"},
                                     {"name": "x_cost", "ttype": "monetary"}, {"name": "price", "ttype": "char"},
                                     {"name": "x_kind", "ttype": "selection"}, {"name": "x_q", "ttype": "decimal"}]
    d["new_models"][1]["fields"].pop()  # no inverse
    d["stock_extensions"] = [{"model": "crm.lead", "fields": [{"name": "probability"}]}, {"model": "helpdesk.ticket", "fields": []}]
    d["automations"] += [{"label": "a", "target_model": "x_booking", "automation": {"when": "on_time", "action": "activity", "date_field": "x_name"}},
                         {"label": "b", "target_model": "x_booking", "automation": {"when": "on_write", "action": "email"}},
                         {"label": "c", "target_model": "x_booking", "automation": {"when": "untouched", "action": "notify", "offset_days": 0, "group": "Ghosts"}},
                         {"label": "d", "target_model": "crm.lead", "automation": {"when": "on_write", "action": "set_fields", "values": {"x_ro": 1}}}]
    d["new_models"] += [{"name": "x_legacy", "fields": []}, {"name": "Bad Name", "fields": []}]
    d["integrations"] = [{"module": "helpdesk", "status": "available"}]
    d["python_needed"] = [{"label": "engine", "delivery_lane": "option_a", "online_blocked": True}]
    codes = {e.code for e in validate_design(d, _schema(), major=major, hosting="sh", edition="community").errors}
    assert {"relation_target_missing", "monetary_without_currency", "field_name_invalid", "selection_empty",
            "field_type_invalid", "one2many_inverse_missing", "extension_field_exists", "extension_model_missing",
            "automation_date_field_missing", "automation_type_unsupported", "automation_days_missing",
            "automation_group_missing", "automation_write_not_writable", "model_name_invalid", "model_exists",
            "app_enterprise_only"} <= codes
    online = validate_design(d, _schema(), major=major, hosting="online")
    assert "online_custom_code_blocked" in {e.code for e in online.errors}


def test_version_gate_and_view_grammar():
    assert validate_design(_good(), _schema(), major=16).errors[0].code == "version_unsupported"
    assert view_tag_for(17) == "tree" and view_tag_for(18) == "list"
    draft = {"views": [{"name": "v", "arch": '<list><field name="x_name"/></list>'},
                       {"name": "k", "arch": '<kanban><templates><t t-name="card"/></templates></kanban>'}]}
    assert {e.code for e in validate_compiled_views(draft, 17)} == {"view_tag_version", "kanban_template_version"}
    assert validate_compiled_views(draft, 18) == [] and validate_compiled_views(draft, 20) == []


def test_flag_off_keeps_existing_behaviour(monkeypatch):
    monkeypatch.delenv("INGENIUM_DESIGN_ADMISSION", raising=False)
    assert admit_design_for_connection(_good()) is None
    monkeypatch.setenv("INGENIUM_DESIGN_ADMISSION", "1")
    res = admit_design_for_connection(_good())  # no snapshot in tests: fail closed, never pass silently
    assert res is not None and not res.ok and res.errors[0].code == "schema_unavailable"


def test_before_apply_uses_fresh_snapshot_and_clears_cache(monkeypatch):
    import app.odoo_snapshot as osnap
    from app.design_admission import admit_before_apply

    monkeypatch.setenv("INGENIUM_DESIGN_ADMISSION", "1")
    calls = []

    class Snap:
        ok, major, series, edition, modules, index, models, caps = True, 19, "19.0", "community", {}, {"res.partner": "Contact"}, {}, {}
        support = "supported"

        def capabilities(self):
            return {"automated_actions": True, "triggers": [], "schedule_todo_action": True}

    monkeypatch.setattr(osnap, "get_snapshot", lambda call, key, brief, models, ttl: calls.append(("get", ttl)) or Snap())
    monkeypatch.setattr(osnap, "clear_snapshot_cache", lambda key=None: calls.append(("clear", key)))
    spec = {"_app_design": _good(), "views": []}
    spec["_app_design"]["stock_extensions"] = []
    res = admit_before_apply(object(), spec)
    assert res.ok, res.errors
    assert calls[0][0] == "clear" and calls[1] == ("get", 0.0) and calls[-1][0] == "clear"
    monkeypatch.setattr(osnap, "get_snapshot", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    res = admit_before_apply(object(), spec)
    assert not res.ok and res.errors[0].code == "schema_unavailable" and "Unchecked" in res.errors[0].message
