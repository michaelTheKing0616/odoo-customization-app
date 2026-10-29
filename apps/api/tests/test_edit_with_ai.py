"""SPEC 20.1 Edit with AI: AI proposes typed ops, code authorizes (views, reports, emails)."""
import pytest

from app import ai_edit_blocks as aeb
from app import view_engine_ai as vai
from app import view_engine_report_blocks as rb
from app.routers.view_engine_logic import check_ai_groups
from app.view_engine import EngineError

SLOTS = [{"id": "s1", "label": "Under the address"}, {"id": "s2", "label": "Above the totals"}]
FIELDS = {"name": {"type": "char", "string": "Number"}, "partner_id": {"type": "many2one", "string": "Customer"},
          "client_order_ref": {"type": "char", "string": "Customer reference"}}


def _fake(monkeypatch, answer):
    monkeypatch.setattr(vai, "designer_json", lambda *a, **k: answer)


def test_report_add_and_move_then_validator_authorizes(monkeypatch):
    _fake(monkeypatch, {"ops": [{"op": "add", "slot": "s1", "block": {"type": "label_field", "field": "client_order_ref"}},
                                {"op": "move", "slot": "s1", "index": 0, "to_slot": "s2"}], "unclear": None})
    base = [{"slot": "s1", "blocks": [{"type": "text", "text": "Thanks"}]}]
    prop = aeb.propose("put customer reference under the address, move thanks above totals", base, SLOTS, FIELDS, email=False)
    assert prop["descriptions"][0] == "Add Customer reference to Under the address"
    out = rb.validate_placements(aeb.apply_ops(base, prop["ops"]), SLOTS, FIELDS)
    assert out == [{"slot": "s1", "blocks": [{"type": "label_field", "field": "client_order_ref", "label": "Customer reference"}]},
                   {"slot": "s2", "blocks": [{"type": "text", "text": "Thanks"}]}]
    assert base[0]["blocks"] == [{"type": "text", "text": "Thanks"}]  # the draft is a copy


def test_invented_field_is_refused_by_code(monkeypatch):
    _fake(monkeypatch, {"ops": [{"op": "add", "slot": "s1", "block": {"type": "field", "field": "x_secret"}}], "unclear": None})
    prop = aeb.propose("add secret", [], SLOTS, FIELDS, email=False)
    with pytest.raises(EngineError):
        rb.validate_placements(aeb.apply_ops([], prop["ops"]), SLOTS, FIELDS)


def test_unknown_slot_and_email_only_types_refused(monkeypatch):
    _fake(monkeypatch, {"ops": [{"op": "add", "slot": "nowhere", "block": {"type": "text", "text": "x"}}], "unclear": None})
    with pytest.raises(EngineError):
        aeb.propose("x", [], SLOTS, FIELDS, email=False)
    _fake(monkeypatch, {"ops": [{"op": "add", "slot": "top", "block": {"type": "qr", "field": "name"}}], "unclear": None})
    with pytest.raises(EngineError):
        aeb.propose("add a qr", [], rb.EMAIL_SLOTS, FIELDS, email=True)


def test_ambiguous_request_gets_one_clarifying_choice(monkeypatch):
    _fake(monkeypatch, {"ops": [], "unclear": "Which reference?", "choices": ["Customer reference", "Order number", "Customer reference"]})
    prop = aeb.propose("add the reference", [], SLOTS, FIELDS, email=False)
    assert prop["ops"] == [] and prop["unclear"] == "Which reference?" and prop["choices"] == ["Customer reference", "Order number"]


def test_view_attr_allowlist_and_choices(monkeypatch):
    tree = {"id": "r", "tag": "form", "anchor": True, "children": [{"id": "f1", "tag": "field", "name": "name", "anchor": True}]}
    _fake(monkeypatch, {"ops": [{"op": "set_attr", "node": "f1", "attr": "t-att-onclick", "value": "x"}], "unclear": None})
    with pytest.raises(EngineError):
        vai.propose_edit("do it", tree, FIELDS)
    _fake(monkeypatch, {"ops": [], "unclear": "Which phone?", "choices": ["Work phone", "Mobile"]})
    ch: list[str] = []
    assert vai.propose_edit("make phone required", tree, FIELDS, None, ch) == ([], "Which phone?") and ch == ["Work phone", "Mobile"]


def test_view_groups_only_inner_and_existing():
    cat = type("C", (), {"id_of": {"sales_team.group_sale_salesman": 3}})()
    by_id = {"r": {"tag": "form"}, "f1": {"tag": "field"}}
    check_ai_groups([{"op": "set_attr", "node": "f1", "attr": "groups", "value": "sales_team.group_sale_salesman"}], by_id, cat)
    with pytest.raises(EngineError):
        check_ai_groups([{"op": "set_attr", "node": "r", "attr": "groups", "value": "sales_team.group_sale_salesman"}], by_id, cat)
    with pytest.raises(EngineError):
        check_ai_groups([{"op": "set_attr", "node": "f1", "attr": "groups", "value": "made.up_group"}], by_id, cat)


def test_email_preview_outlines_only_the_ai_change():
    pl = [{"slot": "top", "blocks": [{"type": "text", "text": "Hi"}, {"type": "heading", "text": "Your order", "level": 2}]}]
    html = rb.email_body("<div><p>Body</p></div>", pl, FIELDS, {("top", 1)})
    assert html.count('data-ingenium-ai="1"') == 1 and html.index("Your order") > html.index('data-ingenium-ai')
    assert "data-ingenium-ai" not in rb.email_body("<div><p>Body</p></div>", pl, FIELDS)
