"""Q6: stock-first mapping of sketches, guards on extracted text, metadata-only reads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.wireframe.reader import read_sketch
from app.wireframe.stock_map import guard_sketch, map_regions

pytestmark = pytest.mark.no_app_db
FIX = Path(__file__).parent / "fixtures" / "wireframe"

MODELS = [{"model": "crm.lead", "name": "Lead"}, {"model": "res.partner", "name": "Contact"},
          {"model": "fleet.vehicle", "name": "Vehicle"}, {"model": "ir.ui.view", "name": "View"}]
LEAD_FIELDS = {
    "partner_id": {"string": "Customer", "type": "many2one", "relation": "res.partner"},
    "email_from": {"string": "Email", "type": "char"},
    "expected_revenue": {"string": "Expected Revenue", "type": "monetary"},
    "date_deadline": {"string": "Expected Closing", "type": "date"},
    "message_ids": {"string": "Messages", "type": "one2many"},
}


def fake(log):
    def call(model, method, args, kwargs):
        log.append((model, method))
        assert method in {"search_read", "fields_get"} and model in {"ir.model", "crm.lead"}, (model, method)
        return MODELS if model == "ir.model" else LEAD_FIELDS
    return call


def test_handdrawn_lead_reuses_stock_fields():
    log: list = []
    sketch = read_sketch(json.loads((FIX / "handdrawn_lead.json").read_text()))
    out = map_regions(sketch, fake(log))
    assert out["target"] == {"action": "extend", "model": "crm.lead", "name": "Lead", "score": 1.0}
    by = {r["region"]: r for r in out["rows"]}
    assert by["r1"]["field"] == "partner_id"  # "Client" is a synonym of Customer
    assert by["r2"]["field"] == "email_from" and by["r3"]["field"] == "expected_revenue"
    assert by["r4"]["action"] == "new"
    assert out["summary"].startswith("3 of 4")
    assert len(out["questions"]) <= 3


def test_figma_vehicle_guards_and_new_model():
    log: list = []
    sketch = read_sketch(json.loads((FIX / "figma_vehicle.json").read_text()))
    g = guard_sketch(sketch)
    assert "r3" in g["flagged_regions"]
    labels = {r.id: r.label for r in sketch.regions}
    assert "ada@example.com" not in labels["r2"] and g["redacted"]
    out = map_regions(sketch, fake(log))
    assert out["target"]["action"] == "new" and out["target"]["model"].startswith("x_")
    assert out["target"]["maybe"]["model"] == "fleet.vehicle"
    assert out["questions"][0]["id"] == "model"
    assert any(q["id"].startswith("label:") for q in out["questions"])
    assert len(out["questions"]) <= 3
    assert all(m in {"ir.model"} for m, _ in log)  # never reads business records


def test_region_box_is_kept_only_when_valid() -> None:
    from app.wireframe.reader import read_sketch

    sk = read_sketch(
        {
            "title": "Visitor log",
            "regions": [
                {"id": "r1", "label": "Name", "hint": "char", "box": [0.1, 0.2, 0.5, 0.1]},
                {"id": "r2", "label": "Host", "hint": "char", "box": [0.8, 0.2, 0.5, 0.1]},
                {"id": "r3", "label": "Date", "hint": "date", "box": "top"},
            ],
        }
    )
    boxes = {r.id: r.box for r in sk.regions}
    assert boxes == {"r1": (0.1, 0.2, 0.5, 0.1), "r2": None, "r3": None}
