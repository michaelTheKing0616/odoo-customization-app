"""Stock-first pack rework: duplicates dropped, unique fields carried to the stock model."""
from app.ai_pack_stock_first import stock_first_rework


def _pack():
    return {
        "depends": ["base"],
        "models": [
            {"model": "x_doctor", "mode": "new", "fields": [
                {"name": "x_name", "ttype": "char", "required": True},
                {"name": "x_user_id", "ttype": "many2one", "relation": "res.users"},
                {"name": "x_specialty", "ttype": "char", "required": True},
                {"name": "x_ward_id", "ttype": "many2one", "relation": "x_ward"},
            ]},
            {"model": "x_ward", "mode": "new", "fields": [
                {"name": "x_name", "ttype": "char"},
                {"name": "x_doctor_ids", "ttype": "one2many", "relation": "x_doctor", "relation_field": "x_ward_id"},
            ]},
        ],
        "smart_buttons": [{"on_model": "x_ward", "related_model": "x_doctor", "relation_field": "x_ward_id"}],
        "automations": [{"name": "a", "model": "x_doctor"}],
    }


def test_rework_carries_unique_fields_and_repoints() -> None:
    out = stock_first_rework(_pack(), {"x_doctor": "hr.employee"}, depends=["hr"])
    by = {m["model"]: m for m in out["models"]}
    assert "x_doctor" not in by and by["hr.employee"]["mode"] == "inherit"
    names = {f["name"]: f for f in by["hr.employee"]["fields"]}
    assert "x_specialty" in names and "required" not in names["x_specialty"]
    assert "x_name" not in names and "x_user_id" not in names  # stock has name / user_id
    assert names["x_ward_id"]["relation"] == "x_ward"
    assert by["x_ward"]["fields"][1]["relation"] == "hr.employee"
    assert out["smart_buttons"][0]["related_model"] == "hr.employee"
    assert out["automations"] == [] and "hr" in out["depends"]


def test_rejected_packs_recommend_stock_app() -> None:
    import app.ai_domain_packs as dp

    for fn, mod in [("_restaurant_pack", "pos_restaurant"), ("_project_tracker_pack", "project"), ("_retail_supermarket_pack", "point_of_sale")]:
        rec = getattr(dp, fn)()["stock_app_recommendation"]
        assert mod in rec["modules"] and rec["message"].startswith("Use stock ")
    assert "restaurant" not in dp.CURATED_PACKS


class _FakeFleet:
    class capabilities:
        major = 19

    def __init__(self):
        self.created = []

    def execute_kw(self, model, method, args, kwargs=None):
        if method == "name_search" or method == "search":
            return []
        if method == "create":
            self.created.append((model, args[0]))
            return len(self.created)
        raise AssertionError(method)


def test_fleet_model_created_on_commit_only() -> None:
    from app.data_import import _resolve_m2o

    c = _FakeFleet()
    assert _resolve_m2o(c, "fleet.vehicle.model", "Toyota Corolla", create_missing=False) == 0
    assert c.created == []  # test run writes nothing
    rid = _resolve_m2o(c, "fleet.vehicle.model", "Toyota Corolla", create_missing=True)
    assert c.created[0] == ("fleet.vehicle.model.brand", {"name": "Toyota"})
    assert c.created[1][0] == "fleet.vehicle.model" and c.created[1][1]["name"] == "Corolla" and rid == 2
    import pytest

    with pytest.raises(ValueError):
        _resolve_m2o(_FakeFleet(), "res.partner", "Nobody", create_missing=True)
