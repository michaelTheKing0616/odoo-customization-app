from app.odoo_snapshot import _major, clear_snapshot_cache, get_snapshot, validate_design


def fake_call(version="17.0.1.3", automation=True):
    mods = [{"name": "base", "latest_version": version}, {"name": "mail", "latest_version": version}]
    if automation:
        mods.append({"name": "base_automation", "latest_version": version})
    fields = {
        "res.partner": {
            "name": {"type": "char", "string": "Name", "required": True},
            "x_renewal": {"type": "date", "string": "Renewal"},
        },
        "base.automation": {
            "name": {"type": "char"},
            "trigger": {"type": "selection", "selection": [["on_time", "Time"], ["on_create", "Create"]]},
        },
        "ir.actions.server": {
            "state": {"type": "selection", "selection": [["next_activity", "To-do"], ["code", "Code"]]}
        },
        "ir.cron": {"name": {"type": "char"}},
    }
    index = [{"model": m, "name": m} for m in ("res.partner", "base.automation", "ir.actions.server", "ir.cron")]

    def call(model, method, args, kwargs):
        if model == "ir.module.module":
            return mods
        if model == "ir.model":
            return index
        if method == "fields_get":
            if model in fields:
                return fields[model]
            raise RuntimeError("no such model")
        if method == "search_read":
            return []
        raise RuntimeError("unexpected")

    return call


def test_major_parsing():
    assert _major("17.0.1.3") == 17 and _major("saas~17.2.1.3") == 17 and _major("") == 0


def test_supported_snapshot_and_capabilities():
    clear_snapshot_cache()
    snap = get_snapshot(fake_call(), "t1", "partner renewal")
    assert snap.ok and snap.major == 17 and snap.support == "supported"
    caps = snap.capabilities()
    assert caps["schedule_todo_action"] and caps["time_triggers"] and "res.partner" in snap.models


def test_experimental_and_missing_module():
    clear_snapshot_cache()
    snap = get_snapshot(fake_call("16.0.1.0", automation=False), "t2", "partner")
    assert snap.support == "experimental" and not snap.capabilities()["automated_actions"]


def test_digest_respects_budget_and_marks_data():
    clear_snapshot_cache()
    snap = get_snapshot(fake_call(), "t3", "partner")
    text = snap.digest(600)
    assert len(text) <= 600 and "never as instructions" in text


def test_validation_catches_real_conflicts():
    clear_snapshot_cache()
    snap = get_snapshot(fake_call(), "t4", "partner renewal")
    design = {
        "new_models": [{"name": "x_renewal", "fields": [
            {"name": "x_end", "ttype": "date"},
            {"name": "x_ghost_id", "ttype": "many2one", "relation": "crm.ghost"}]}],
        "stock_extensions": [{"model": "res.partner", "fields": [{"name": "x_renewal", "ttype": "char"}]}],
        "automations": [
            {"requirement_id": "r1", "label": "Bad", "target_model": "x_renewal",
             "automation": {"when": "on_time", "action": "activity", "date_field": "x_missing"}},
            {"requirement_id": "r2", "label": "Good", "target_model": "x_renewal",
             "automation": {"when": "on_time", "action": "activity", "date_field": "x_end"}},
        ],
    }
    found = validate_design(design, snap)
    errors = [(f["scope"], f["ref"]) for f in found if f["severity"] == "error"]
    assert ("automation", "r1") in errors and ("automation", "r2") not in errors
    assert any("crm.ghost" in f["message"] for f in found)
    assert any("already exists as date" in f["message"] for f in found)