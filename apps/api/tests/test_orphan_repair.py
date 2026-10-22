import json

from app.ai_conversation import orphan_repair as orph
from app.ai_conversation.app_design import AppDesign, DesignField, DesignModel


class FakeProvider:
    model = "fake"

    def __init__(self, out):
        self.out, self.calls = out, 0

    def generate_json(self, *a, **kw):
        self.calls += 1
        return self.out


def _design():
    m = DesignModel(name="x_job", label="Job", requirement_ids=["R1"], fields=[DesignField(name="x_name", string="Name")])
    return AppDesign(new_models=[m], intent_contract=[{"id": "R1", "decision": "metadata", "kind": "model"},
                                                       {"id": "R2", "decision": "metadata", "kind": "field", "subject": "plate",
                                                        "evidence": {"quote": "the car plate"}}])


PROPOSED = {"app_name": "x", "new_models": [
    {"name": "x_job", "label": "Job", "fields": [{"name": "x_plate", "type": "char", "string": "Plate", "requirement_ids": ["R2"]},
                                                 {"name": "x_extra", "type": "char", "string": "Extra"}]},
    {"name": "x_new", "label": "New thing", "requirement_ids": ["R2"], "fields": []}]}


def test_off_makes_no_call(monkeypatch):
    monkeypatch.delenv("INGENIUM_ORPHAN_REPAIR", raising=False)
    p = FakeProvider(PROPOSED)
    assert orph.repair_step(_design(), "job card with the car plate", provider=p)["called"] is False and p.calls == 0


def test_no_orphans_no_call(monkeypatch):
    monkeypatch.setenv("INGENIUM_ORPHAN_REPAIR", "on")
    d = _design()
    d.new_models[0].fields.append(DesignField(name="x_plate", string="Plate", requirement_ids=["R2"]))
    p = FakeProvider(PROPOSED)
    assert orph.repair_step(d, "brief", provider=p)["called"] is False and p.calls == 0


def test_shadow_logs_and_changes_nothing(monkeypatch, tmp_path):
    log = tmp_path / "s.jsonl"
    monkeypatch.setenv("INGENIUM_ORPHAN_REPAIR", "shadow")
    monkeypatch.setenv("INGENIUM_SHADOW_LOG", str(log))
    d = _design()
    rec = orph.repair_step(d, "job card with the car plate", provider=FakeProvider(PROPOSED))
    assert rec["called"] and rec["added"]["fields"] == ["x_job.x_plate"] and rec["added"]["unmet_models"] == ["New thing"]
    assert [f.name for f in d.new_models[0].fields] == ["x_name"] and len(d.new_models) == 1
    assert json.loads(log.read_text().splitlines()[-1])["orphan_repair"]["orphans_after"] == []


def test_on_merges_only_citing_elements_never_models(monkeypatch):
    monkeypatch.setenv("INGENIUM_ORPHAN_REPAIR", "on")
    monkeypatch.delenv("INGENIUM_SHADOW_LOG", raising=False)
    d = _design()
    p = FakeProvider(PROPOSED)
    orph.repair_step(d, "job card with the car plate", provider=p)
    assert p.calls == 1 and [f.name for f in d.new_models[0].fields] == ["x_name", "x_plate"] and len(d.new_models) == 1
