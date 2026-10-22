"""Builders stage 2c: the 19 approved builder ideas (logic and endpoint rules)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import view_engine as ve
from app import view_engine_2c as v2
from app import view_engine_store as vs
from app.routers import view_engine_2c as r2c

FIELDS: dict[str, Any] = {
    "name": {"type": "char", "string": "Name", "required": True},
    "partner_id": {"type": "many2one", "string": "Customer", "relation": "res.partner"},
    "amount": {"type": "float", "string": "Amount"},
    "email": {"type": "char", "string": "Email"},
    "note": {"type": "text", "string": "Note"},
    "state": {"type": "selection", "string": "Status", "selection": [["draft", "Draft"], ["done", "Done"]]},
    "stage_id": {"type": "many2one", "string": "Stage", "relation": "crm.stage"},
    "date": {"type": "date", "string": "Date"},
    "is_vip": {"type": "boolean", "string": "VIP"},
    "line_ids": {"type": "one2many", "string": "Lines", "relation": "x.line"},
    "tag_ids": {"type": "many2many", "string": "Tags", "relation": "x.tag"},
    "message_ids": {"type": "one2many", "string": "Messages", "relation": "mail.message"},
}

FORM = """<form>
  <header><button name="action_done" type="object" string="Mark done"/><button name="action_x" type="object" icon="fa-cog"/>
  <field name="state" widget="statusbar"/></header>
  <sheet>
    <div class="oe_title"><h1><field name="name" placeholder="Name"/></h1></div>
    <group name="main" string="Main">
      <field name="partner_id" required="state == 'done'"/>
      <field name="amount" invisible="not partner_id"/>
      <field name="date" required="stage_id.is_won"/>
    </group>
    <group name="contact"><field name="email" required="is_vip"/></group>
    <notebook name="nb">
      <page name="notes" string="Notes"><group name="notes_g"><field name="note"/></group></page>
      <page name="more" string="More"><group name="more_g"><field name="is_vip"/><field name="tag_ids"/></group></page>
    </notebook>
  </sheet>
</form>"""


def tree() -> dict[str, Any]:
    return ve.normalize(FORM, FIELDS).tree


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    session = sessionmaker(bind=engine)()
    vs._ensure_tables(session)
    yield session
    session.close()


# --- 1. dependency map ---------------------------------------------------------

def test_screen_uses_finds_rules_reading_a_field() -> None:
    uses = v2.uses_in_screen(tree(), "partner_id")
    assert [u["node"] for u in uses] == ["field:amount"]
    assert uses[0]["how"] == "show/hide rule"


def test_arch_mentions_and_domain_mentions() -> None:
    assert v2.arch_mentions('<list><field name="amount"/></list>', "amount")
    assert v2.arch_mentions('<t t-out="o.amount"/>', "amount")
    assert not v2.arch_mentions('<t t-out="o.amount_total"/>', "amount")
    assert v2.domain_mentions("[('partner_id.country_id', '=', 1)]", "partner_id")
    assert not v2.domain_mentions("[('partner_ids', '=', 1)]", "partner_id")


def test_dependency_summary_blocks_removal_but_allows_hiding() -> None:
    items = [{"kind": "automation", "name": "A"}, {"kind": "view", "name": "V"}]
    assert v2.dependency_summary(items, "Amount", removing=True)["level"] == "blocked"
    hide = v2.dependency_summary(items, "Amount", removing=False)
    assert hide["level"] == "caution" and "keeps its value" in hide["verdict"]
    assert v2.dependency_summary([], "Amount", removing=False)["level"] == "safe"


# --- 2. conditional required -----------------------------------------------------

def test_condition_domain_matches_compiled_condition() -> None:
    cond = {"match": "any", "rules": [{"field": "state", "op": "is", "value": "done"}, {"field": "amount", "op": "gt", "value": 100}]}
    assert v2.condition_domain(cond) == ["|", ("state", "=", "done"), ("amount", ">", 100)]
    cond2 = {"match": "all", "rules": [{"field": "is_vip", "op": "is_true"}, {"field": "partner_id", "op": "not_set"}, {"field": "amount", "op": "eq", "value": 5}]}
    assert v2.condition_domain(cond2) == ["&", "&", ("is_vip", "=", True), ("partner_id", "=", False), ("amount", "=", 5)]


def test_required_impact_text() -> None:
    assert "Nobody is blocked" in v2.required_impact_text("Email", "VIP is ticked", 10, 0)
    assert "3 of 10" in v2.required_impact_text("Email", "VIP is ticked", 10, 3)
    assert "nobody is affected" in v2.required_impact_text("Email", "VIP is ticked", 0, 0)


# --- 3. what blocks saving -------------------------------------------------------

def test_eval_expr_is_three_valued() -> None:
    assert v2.eval_expr("state == 'done'", {"state": "done"}) is True
    assert v2.eval_expr("state == 'done'", {"state": "draft"}) is False
    assert v2.eval_expr("state == 'done' and is_vip", {"state": "draft"}) is False
    assert v2.eval_expr("state == 'done' and is_vip", {"state": "done"}) is None
    assert v2.eval_expr("state == 'done' or is_vip", {"state": "done"}) is True
    assert v2.eval_expr("not stage_id.is_won", {"stage_id.is_won": True}) is False
    assert v2.eval_expr("state in ['a', 'done']", {"state": "done"}) is True
    assert v2.eval_expr("", {}) is False and v2.eval_expr("1", {}) is True


def test_save_blockers_per_stage() -> None:
    t = tree()
    assert v2.stage_attr_names(t, "stage_id") == {"is_won"}
    rows = v2.save_blockers(t, FIELDS, "state", [{"value": "draft", "label": "Draft"}, {"value": "done", "label": "Done"}])
    draft, done = rows
    assert [i["field"] for i in draft["always"]] == ["name"]
    assert not any(i["field"] == "partner_id" for i in draft["at_stage"])
    assert [i["field"] for i in done["at_stage"]] == ["partner_id"]
    assert {i["field"] for i in done["depends"]} == {"date", "email"}
    won = v2.save_blockers(t, FIELDS, "stage_id", [{"value": 1, "label": "Won", "attrs": {"is_won": True}}])[0]
    assert "date" in [i["field"] for i in won["at_stage"]]


def test_stage_choices_prefers_stage_id() -> None:
    assert v2.stage_choices(FIELDS) == ("stage_id", "many2one")
    assert v2.stage_choices({"state": FIELDS["state"]}) == ("state", "selection")
    assert v2.stage_choices({"name": FIELDS["name"]}) == (None, None)


# --- 4. heatmap ---------------------------------------------------------------------

def test_heat_levels_mix_fill_and_changes() -> None:
    heat = v2.heat_levels({"name": 100, "note": 2, "amount": 50}, 100, {"amount": 40, "name": 0}, 90)
    assert heat["name"]["level"] >= 3 and heat["note"]["level"] == 0
    assert heat["amount"]["changes"] == 40 and "changed 40 times" in heat["amount"]["label"]
    assert v2.heat_levels({"name": 0}, 0, None, 90)["name"]["level"] == 0


# --- 5. sample data -------------------------------------------------------------------

def test_sample_records_are_labelled_and_typed() -> None:
    recs = v2.sample_records(["name", "amount", "date", "state", "partner_id", "is_vip", "email"], FIELDS, 3)
    assert len(recs) == 3 and all(r["__sample"] and r["id"] < 0 for r in recs)
    assert recs[0]["name"].startswith("Sample") and recs[0]["state"] == "Draft"
    assert recs[0]["email"].endswith("@example.com")
    assert isinstance(recs[1]["amount"], float) and recs[0]["date"].startswith("2026-")


# --- 6. accessibility ---------------------------------------------------------------------

def test_a11y_finds_icon_buttons_and_placeholder_labels() -> None:
    rep = v2.a11y_report(tree(), FIELDS, "form")
    kinds = {i["kind"] for i in rep["issues"]}
    assert "button_no_text" in kinds
    assert "placeholder_label" in kinds
    says = [o["say"] for o in rep["reading_order"]]
    assert any(s.startswith("Customer, pick one") for s in says)
    assert rep["tab_order"][0]["n"] == 1


def test_a11y_flags_colour_only_rows() -> None:
    t = ve.normalize('<list decoration-danger="amount &lt; 0"><field name="name"/><field name="amount"/></list>', FIELDS).tree
    assert any(i["kind"] == "colour_only" for i in v2.a11y_report(t, FIELDS, "list")["issues"])


# --- 7. starters -------------------------------------------------------------------------

def test_starter_uses_only_existing_fields() -> None:
    fields = {"name": {"type": "char", "string": "Name"}, "phone": {"type": "char"}, "email": {"type": "char"}, "vat": {"type": "char"},
              "message_ids": {"type": "one2many"}}
    opts = {o["key"]: o for o in v2.starter_options("res.partner", fields)}
    assert "retail" in opts and opts["retail"]["fields_missing"] > 0
    arch, used, missing = v2.starter_arch("distribution", "res.partner", fields, 18, "Trade partner")
    assert "vat" in used and "credit_limit" in missing
    assert 'name="credit_limit"' not in arch and "<chatter/>" in arch
    ve.normalize(arch, fields)
    arch17, _u, _m = v2.starter_arch("distribution", "res.partner", fields, 17, "Trade partner")
    assert "oe_chatter" in arch17
    with pytest.raises(ve.EngineError):
        v2.starter_arch("retail", "sale.order", fields, 18, "x")


# --- 8. explain -----------------------------------------------------------------------------

def test_explain_steps_are_built_from_the_screen() -> None:
    t = tree()
    t["children"][1]["children"][1]["children"][0]["rules"] = {"required": "Required when Status is Done."}
    steps = v2.explain_steps(t, FIELDS, "Thing", {})
    titles = [s["title"] for s in steps]
    assert titles[0] == "Overview" and "Where the record is" in titles and "Actions" in titles
    assert any("Mark done" in s["text"] for s in steps)
    assert any(s["title"] == "Must be filled in" and "Name" in s["text"] for s in steps)


# --- 9. step-by-step -------------------------------------------------------------------------

def test_steps_layer_moves_sections_into_step_tabs() -> None:
    t = tree()
    cands = v2.step_candidates(t)
    assert [c["kind"] for c in cands] == ["group", "group", "page", "page"]
    arch = v2.steps_layer_arch(cands)
    combined = ve.apply_inherit_local(FORM, arch)
    out = ve.normalize(combined, FIELDS).tree
    pages = [n for n, _p, _h in v2.walk(out) if n.get("tag") == "page" and str(n.get("name") or "").startswith(v2.STEPS_PREFIX)]
    assert len(pages) == 4 and pages[0]["attrs"].get("string") == "Step 1: Main"
    names_in_step1 = {n.get("name") for n, _p, _h in v2.walk(pages[0]) if n.get("tag") == "field"}
    assert {"partner_id", "amount", "date"} <= names_in_step1
    names_in_step3 = {n.get("name") for n, _p, _h in v2.walk(pages[2]) if n.get("tag") == "field"}
    assert names_in_step3 == {"note"}
    assert combined.count('name="partner_id"') == 1  # moved, not copied
    old = next(n for n, _p, _h in v2.walk(out) if n.get("name") == "notes")
    assert old["attrs"].get("invisible") == "1"
    with pytest.raises(ve.EngineError):
        v2.steps_layer_arch(cands[:1])


def test_scoped_layer_name_is_per_role() -> None:
    a = v2.scoped_layer_name(v2.STEPS_PREFIX, "sale.order", "form", 5, "sales_team.group_sale_salesman")
    assert a.startswith(ve.LAYER_PREFIX) and a.endswith("sales_team_group_sale_salesman")


# --- 10. dashboards ----------------------------------------------------------------------------

def test_dashboard_validation_and_arch() -> None:
    fields = {**FIELDS, "amount": {**FIELDS["amount"], "store": True}}
    spec = v2.validate_dashboard({"kind": "graph", "measures": ["amount"], "rows": ["date"], "chart": "line", "interval": "month"}, fields)
    arch = v2.dashboard_arch(spec, fields, "Sales")
    assert arch.startswith('<graph string="Sales" type="line"') and 'interval="month"' in arch and 'type="measure"' in arch
    piv = v2.validate_dashboard({"kind": "pivot", "measures": [], "rows": ["partner_id"], "cols": ["state"]}, fields)
    assert 'type="col"' in v2.dashboard_arch(piv, fields, "P")
    for bad in ({"kind": "graph", "rows": ["note"]}, {"kind": "graph", "rows": ["state"], "measures": ["name"]},
                {"kind": "table", "rows": ["state"]}, {"kind": "graph", "rows": []}):
        with pytest.raises(ve.EngineError):
            v2.validate_dashboard(bad, fields)


# --- 12. email checks ---------------------------------------------------------------------------

def test_email_checks_find_known_problems() -> None:
    html = ('<div style="display:flex;width:800px"><img src="x.png"><a href="http://x">x</a>'
            '<p style="color:#000000">hi</p><script>1</script></div>')
    rep = v2.email_checks(html)
    texts = " ".join(f["text"] for f in rep["findings"])
    assert "Outlook on Windows ignores" in texts and "no description" in texts and "800 px" in texts
    assert "scripts" in texts and "http://" in texts and "dark mode" in texts
    assert rep["score"] < 50
    big = v2.email_checks("<p>" + "x" * (110 * 1024) + "</p>")
    assert any(f["apps"] == "Gmail" for f in big["findings"])
    clean = v2.email_checks('<table width="600"><tr><td style="color:#111;background-color:#fff">Hi</td></tr></table>')
    assert all(f["severity"] == "low" for f in clean["findings"])


# --- 13-16. approvals, schedules, watch, digest ------------------------------------------------

def test_parse_when_limits() -> None:
    now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    with pytest.raises(ve.EngineError):
        v2.parse_when("2026-10-15T13:00:00+01:00", now)  # that's now
    with pytest.raises(ve.EngineError):
        v2.parse_when("2026-10-15T12:00:05+00:00", now)
    with pytest.raises(ve.EngineError):
        v2.parse_when("2026-10-15T14:00:00", now)
    with pytest.raises(ve.EngineError):
        v2.parse_when("2027-01-15T14:00:00+00:00", now)
    assert v2.parse_when("2026-10-16T09:00:00+01:00", now) == datetime(2026, 10, 16, 8, 0, tzinfo=UTC)


class Req:
    def __init__(self, user_id: str | None, email: str | None, mode: str = "accounts") -> None:
        class S:
            pass
        self.state = S()
        a = S()
        a.mode, a.user_id, a.email = mode, user_id, email
        self.state.auth = a


def _approval(db, monkeypatch, requester: Req) -> str:
    monkeypatch.setattr(r2c, "_client", lambda cid, db: object())
    monkeypatch.setattr(r2c, "_check_ops", lambda *a, **k: {"id": 7, "arch": "<form/>"})
    monkeypatch.setattr(r2c, "_layer_hash", lambda *a, **k: "h1")
    out = r2c.approval_request("c1", r2c.ApprovalRequestBody(model="res.partner", view_type="form", ops=[{"op": "hide", "node": "field:email"}],
                                                             summary=["Hide Email"]), requester, db)
    return out["item_id"]


def test_approval_needs_a_different_person_and_publishes_as_approved(db, monkeypatch) -> None:
    item = _approval(db, monkeypatch, Req("u1", "a@x.com"))
    with pytest.raises(HTTPException) as e:
        r2c.approval_decide("c1", r2c.ApprovalDecideBody(item_id=item, approve=True), Req("u1", "a@x.com"), db)
    assert e.value.status_code == 403
    seen: dict[str, Any] = {}

    def fake_publish(cid, body, db):
        seen["approved"] = r2c.APPROVED_PUBLISH.get()
        seen["hash"] = body.base_layer_hash
        return {"ok": True, "version_id": "v1", "layer_view_id": 99, "previous_arch": None, "layer_hash": "h2"}

    monkeypatch.setattr(r2c, "engine_publish", fake_publish)
    out = r2c.approval_decide("c1", r2c.ApprovalDecideBody(item_id=item, approve=True), Req("u2", "b@x.com"), db)
    assert out["status"] == "approved" and seen == {"approved": True, "hash": "h1"}
    assert r2c.APPROVED_PUBLISH.get() is False
    watches = vs.list_items(db, "c1", "watch")
    assert len(watches) == 1 and vs.item_out(watches[0])["payload"]["layer_view_id"] == 99
    with pytest.raises(HTTPException):
        r2c.approval_decide("c1", r2c.ApprovalDecideBody(item_id=item, approve=False), Req("u2", "b@x.com"), db)


def test_stale_approval_is_refused(db, monkeypatch) -> None:
    item = _approval(db, monkeypatch, Req("u1", "a@x.com"))

    def conflict(cid, body, db):
        raise HTTPException(status_code=409, detail={"message": "changed", "conflict": True})

    monkeypatch.setattr(r2c, "engine_publish", conflict)
    with pytest.raises(HTTPException) as e:
        r2c.approval_decide("c1", r2c.ApprovalDecideBody(item_id=item, approve=True), Req("u2", "b@x.com"), db)
    assert e.value.status_code == 409 and "changed after" in e.value.detail
    assert vs.item_out(vs.get_item(db, "c1", item))["payload"]["status"] == "stale"


def test_policy_blocks_plain_publish_and_scheduling(db, monkeypatch) -> None:
    r2c.require_approval_ok(db, "c1")  # off by default
    r2c.set_policy("c1", r2c.PolicyBody(required=True), Req("u1", "a@x.com"), db)
    with pytest.raises(HTTPException) as e:
        r2c.require_approval_ok(db, "c1")
    assert e.value.status_code == 403
    token = r2c.APPROVED_PUBLISH.set(True)
    try:
        r2c.require_approval_ok(db, "c1")
    finally:
        r2c.APPROVED_PUBLISH.reset(token)
    with pytest.raises(HTTPException):
        r2c.schedule_create("c1", r2c.ScheduleBody(model="res.partner", ops=[{"op": "hide"}], run_at="2030-01-01T00:00:00+00:00"),
                            Req("u1", "a@x.com"), db)


def test_scheduled_publish_runs_when_due_and_explains_conflicts(db, monkeypatch) -> None:
    run_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    for key in ("a", "b"):
        vs.save_item(db, connection_id="c1", kind="schedule", key=key, name=key, payload={
            "model": "res.partner", "view_type": "form", "view_id": None, "ops": [{"op": "hide"}], "summary": [key],
            "base_layer_hash": "", "run_at": run_at, "status": "scheduled", "approved": False})
    assert r2c.run_due_schedules(db, "c1") == []  # not yet due

    def publish(cid, body, db):
        if body.summary == ["b"]:
            raise HTTPException(status_code=409, detail={"message": "x", "conflict": True})
        return {"ok": True, "version_id": "v", "layer_view_id": 5, "previous_arch": "<data/>", "layer_hash": "h"}

    monkeypatch.setattr(r2c, "engine_publish", publish)
    ran = r2c.run_due_schedules(db, "c1", now=datetime.now(UTC) + timedelta(minutes=6))
    assert sorted(r["status"] for r in ran) == ["done", "failed"]
    failed = next(r for r in ran if r["status"] == "failed")
    assert "changed after this was scheduled" in failed["failure"]
    assert len(vs.list_items(db, "c1", "watch")) == 1
    assert r2c.run_due_schedules(db, "c1", now=datetime.now(UTC) + timedelta(minutes=7)) == []  # runs once


def test_watch_undo_uses_the_server_copy(db, monkeypatch) -> None:
    wid = r2c._start_watch(db, "c1", "res.partner", "form", None, {"layer_view_id": 5, "version_id": "v", "previous_arch": "<data>OLD</data>", "layer_hash": "h"}, by="t")
    listed = r2c.watch_list("c1", r2c.ModelFilter(model="res.partner"), db)["watches"][0]["payload"]
    assert "previous_arch" not in listed and listed["goes_back_to"] == "the earlier changes"
    seen = {}

    def revert(cid, body, db):
        seen.update(mode=body.mode, arch=body.restore_arch)
        return {"ok": True, "mode": body.mode}

    monkeypatch.setattr(r2c, "engine_revert", revert)
    r2c.watch_undo("c1", r2c.ItemRef(item_id=wid), db)
    assert seen == {"mode": "restore", "arch": "<data>OLD</data>"}
    with pytest.raises(HTTPException):
        r2c.watch_undo("c1", r2c.ItemRef(item_id=wid), db)


def test_watch_due_times_and_digest_text() -> None:
    start = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    due = v2.watch_due_times(start)
    assert due[0].startswith("2026-10-15T12:05") and due[2].startswith("2026-10-16T12:00")
    d = v2.digest_payload([{"model": "res.partner", "view_type": "form", "action": "publish", "summary": ["Hide Email"], "created_at": "x"},
                           {"model": "res.partner", "view_type": "form", "action": "undo", "summary": [], "created_at": "y"}],
                          [{"status": "pending"}], [{"status": "scheduled"}], [{"screen": "s", "problem": "p"}], 7, "Demo")
    assert d["published"] == 1 and d["undone"] == 1 and "1 change is waiting for approval." in d["text"]
    assert "Hide Email" in d["text"] and "had a problem" in d["text"]
    empty = v2.digest_payload([], [], [], [], 7, "Demo")
    assert "No screens were changed." in empty["text"]


class FakeMail:
    def __init__(self, servers: int, state: str = "sent") -> None:
        self.servers, self.state, self.calls = servers, state, []

    def execute_kw(self, model, method, args, kw=None):  # noqa: ANN001, ANN201
        self.calls.append((model, method))
        if model == "ir.mail_server":
            return self.servers
        if method == "create":
            return 7
        if method == "read":
            return [{"state": self.state, "failure_reason": "refused"}]
        return True


def test_digest_sends_weekly_once_through_odoo(db, monkeypatch) -> None:
    fake = FakeMail(1)
    monkeypatch.setattr(r2c, "_client", lambda cid, db: fake)
    monkeypatch.setattr(r2c, "_db_label", lambda db, cid: "Demo")
    vs.save_item(db, connection_id="c1", kind="digest", key="weekly", name="w", payload={"to": "a@x.com", "on": True, "weekday": 0, "last_sent": None})
    monday = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
    assert r2c.run_due_digests(db, monday) == 1
    assert r2c.run_due_digests(db, monday + timedelta(hours=2)) == 0
    assert ("mail.mail", "send") in fake.calls
    row = vs.list_items(db, "c1", "digest", "weekly")[0]
    assert vs.item_out(row)["payload"]["last_delivery"]["status"] == "sent"


def test_send_via_odoo_without_mail_server_is_log_only_and_reports_failures() -> None:
    assert r2c.send_via_odoo(FakeMail(0), "a@x.com", "s", "t")["status"] == "log_only"
    assert r2c.send_via_odoo(FakeMail(1, "exception"), "a@x.com", "s", "t")["status"] == "failed"


ROLE_A = '<form><header><button name="a"/></header><sheet><group name="g"><field name="name"/></group></sheet><div class="oe_chatter"/></form>'


def test_role_variant_puts_groups_inside_the_layer() -> None:
    b = ROLE_A.replace('<field name="name"/>', '<field name="name" string="Your name"/>')
    arch = v2.role_variant_arch(ROLE_A, b, "sales_team.group_sale_salesman")
    assert 'expr="/form/sheet"' in arch and 'groups="sales_team.group_sale_salesman"' in arch and ">!sales_team.group_sale_salesman<" in arch
    combined = ve.apply_inherit_local(ROLE_A, arch)
    assert combined.count("<sheet") == 2
    with pytest.raises(ve.EngineError):
        v2.role_variant_arch(ROLE_A, ROLE_A, "sales_team.group_sale_salesman")
    with pytest.raises(ve.EngineError):
        v2.role_variant_arch(ROLE_A.replace("<sheet>", '<sheet groups="base.group_system">'), b.replace("<sheet>", '<sheet groups="base.group_system">'), "x.y")


def test_ticker_runs_in_one_worker_only(tmp_path) -> None:
    from app.builders_ticker import single_runner

    eng = create_engine(f"sqlite:///{tmp_path}/app.db")
    with single_runner(eng) as first:
        with single_runner(eng) as second:
            assert first is True and second is False
    with single_runner(eng) as again:
        assert again is True


def test_coedit_room_survives_a_new_session(tmp_path, monkeypatch) -> None:
    eng = create_engine(f"sqlite:///{tmp_path}/app.db")
    mk = sessionmaker(bind=eng)
    monkeypatch.setattr(r2c, "_who", lambda req: {"email": None, "verified": False})
    s1 = mk()
    vs._ensure_tables(s1)
    a = r2c.coedit("c1", r2c.CoeditBody(model="res.partner", editor_id="ed-a1", name="Ann", ops=[{"op": "hide", "node": "field:x"}]), None, s1)
    s1.close()
    s2 = mk()  # another worker / after a restart
    b = r2c.coedit("c1", r2c.CoeditBody(model="res.partner", editor_id="ed-b1", name="Ben"), None, s2)
    assert a["seq"] == 1 and [o["op"] for o in b["ops"]] == [{"op": "hide", "node": "field:x"}]
    assert len(vs.list_items(s2, "c1", "coedit")) == 1


def test_guard_fix_and_import_follow_the_approval_rule(db) -> None:
    from app.routers import view_engine_builder as vb

    vs.save_item(db, connection_id="c1", kind="policy", key="approval", name="p", payload={"required": True}, replace_key=True)
    with pytest.raises(HTTPException) as e:
        vb.guard_fix("c1", vb.ScreenRef(model="res.partner"), db)
    assert e.value.status_code == 403 and e.value.detail["needs_approval"]
    with pytest.raises(HTTPException) as e2:
        vb.package_import("c1", vb.PackageBody(package={}), db)
    assert e2.value.status_code == 403


# --- 17. layout tests -------------------------------------------------------------------------------

def test_proportion_test_wording() -> None:
    assert v2.proportion_test(5, 10, 9, 10)["verdict"] == "too_few"
    r = v2.proportion_test(30, 100, 60, 100)
    assert r["verdict"] == "B" and r["p"] < 0.05
    assert v2.proportion_test(50, 100, 52, 100)["verdict"] == "unclear"


def test_role_differences() -> None:
    a = {"field:x": {"visible": True}, "field:y": {"visible": False, "reason": "Only Managers can see it."}}
    b = {"field:x": {"visible": False, "reason": "Only Admin can see it."}, "field:y": {"visible": True}}
    d = v2.role_differences(a, b, {"field:x": "X", "field:y": "Y"})
    assert d["only_a"][0]["label"] == "X" and d["only_b"][0]["why_not"] == "Only Managers can see it."


# --- 18. report from a document -------------------------------------------------------------------

def test_doc_proposal_keeps_only_real_fields() -> None:
    line_fields = {"name": {"type": "char"}, "price_subtotal": {"type": "monetary"}}
    blocks, dropped = v2.validate_doc_proposal({"blocks": [
        {"kind": "heading", "label": "INVOICE"}, {"kind": "label_field", "field": "partner_id", "label": "Bill to"},
        {"kind": "label_field", "field": "made_up", "label": "PO number"},
        {"kind": "o2m_table", "field": "line_ids", "label": "Items", "columns": ["name", "price_subtotal", "nope"]},
        {"kind": "script"}]}, FIELDS, line_fields)
    assert {"type": "heading", "text": "INVOICE", "level": 3} in blocks
    assert {"type": "label_field", "field": "partner_id", "label": "Bill to"} in blocks
    assert {"type": "line_table", "field": "line_ids", "columns": [{"field": "name"}, {"field": "price_subtotal"}]} in blocks
    assert any("PO number" in d for d in dropped) and any("nope" in d for d in dropped)
    assert v2.validate_doc_proposal("junk", FIELDS, None) == ([], ["The document could not be read."])


# --- 19. co-editing -----------------------------------------------------------------------------------

def test_coedit_shares_ops_and_refuses_clashes() -> None:
    room: dict[str, Any] = {}
    a = v2.merge_coedit(room, "ed-a", "Ann", "field:x", 0, [{"op": "hide", "node": "field:x"}], 0, 100.0)
    assert a["seq"] == 1 and a["ops"] == []
    b = v2.merge_coedit(room, "ed-b", "Ben", None, 0, [{"op": "move", "node": "field:x"}, {"op": "hide", "node": "field:y"}], 0, 101.0)
    assert len(b["ops"]) == 1 and b["ops"][0]["name"] == "Ann"
    assert b["refused"][0]["by"] == "Ann" and b["seq"] == 2
    assert b["others"] == [{"editor_id": "ed-a", "name": "Ann", "selected": "field:x"}]
    late = v2.merge_coedit(room, "ed-a", "Ann", None, 1, [], 2, 200.0)
    assert [o["op"]["node"] for o in late["ops"]] == ["field:y"]
    gone = v2.merge_coedit(room, "ed-c", "Cat", None, 0, [], 0, 400.0)
    assert gone["others"] == []  # Ann and Ben timed out


def test_ticker_is_off_in_tests() -> None:
    from app import builders_ticker

    assert builders_ticker.enabled() is False
