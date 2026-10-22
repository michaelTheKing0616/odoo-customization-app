"""Stage 2d helpers and endpoints (no Odoo needed)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import view_engine as ve
from app import view_engine_2c as v2
from app import view_engine_2d as v2d
from app import view_engine_pdf as vpdf
from app import view_engine_store as vs
from app.routers import view_engine_2c as r2c
from tests.test_view_engine_2c import FIELDS, FORM, Req, _approval, tree


@pytest.fixture()
def db():
    session = sessionmaker(bind=create_engine("sqlite://"))()
    vs._ensure_tables(session)
    yield session
    session.close()


def test_tree_diff_lists_added_removed_and_changed() -> None:
    after = ve.normalize(FORM.replace('<field name="note"/>', '<field name="note" string="Remarks"/>').replace('<field name="email" required="is_vip"/>', ""), FIELDS).tree
    kinds = {(d["kind"], d["node"]) for d in v2d.tree_diff(tree(), after)}
    assert ("removed", "field:email") in kinds and ("changed", "field:note") in kinds


def test_approvers_are_checked_per_record_type() -> None:
    m = v2d.clean_approvers({"sale.order": ["Boss@X.com"], "*": ["ops@x.com"]})
    assert m["sale.order"] == ["boss@x.com"]
    assert v2d.approver_check(m, "sale.order", "boss@x.com", True) is None
    assert "Only boss@x.com" in v2d.approver_check(m, "sale.order", "ann@x.com", True)
    assert "sign-in is off" in v2d.approver_check(m, "res.partner", None, False)
    with pytest.raises(ve.EngineError):
        v2d.clean_approvers({"sale.order": ["not-an-email"]})


def test_named_approver_rule_blocks_others(db, monkeypatch) -> None:
    item = _approval(db, monkeypatch, Req("u1", "a@x.com"))
    vs.save_item(db, connection_id="c1", kind="policy", key="approvers", name="a", payload={"approvers": {"res.partner": ["boss@x.com"]}}, replace_key=True)
    with pytest.raises(HTTPException) as e:
        r2c.approval_decide("c1", r2c.ApprovalDecideBody(item_id=item, approve=True), Req("u2", "b@x.com"), db)
    assert e.value.status_code == 403 and "boss@x.com" in e.value.detail


def test_pause_holds_scheduled_changes(db, monkeypatch) -> None:
    now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    vs.save_item(db, connection_id="c1", kind="pause", key="schedules", name="upgrade",
                 payload={"start": (now - timedelta(hours=1)).isoformat(), "end": (now + timedelta(hours=1)).isoformat()})
    vs.save_item(db, connection_id="c1", kind="schedule", key="k", name="s", payload={"model": "res.partner", "view_type": "form", "ops": [], "run_at": (now - timedelta(minutes=1)).isoformat(), "status": "scheduled"})
    monkeypatch.setattr(r2c, "_publish_stored", lambda *a, **k: pytest.fail("published during a pause"))
    out = r2c.run_due_schedules(db, now=now)
    assert out[0]["status"] == "paused"
    with pytest.raises(ve.EngineError):
        v2d.check_pause(now, now - timedelta(hours=1), now)


def test_periods_and_change_text() -> None:
    cs, ce, ps, pe = v2d.period_bounds("month", date(2026, 1, 15))
    assert (cs, ce, ps, pe) == (date(2026, 1, 1), date(2026, 2, 1), date(2025, 12, 1), date(2026, 1, 1))
    q = v2d.period_bounds("quarter", date(2026, 11, 2))
    assert q[0] == date(2026, 10, 1) and q[1] == date(2027, 1, 1) and q[2] == date(2026, 7, 1)
    assert v2d.change_text(120, 100, "month") == "Up 20% on last month."
    assert v2d.change_text(0, 0, "week") == "Nothing to compare with last week."


def test_unused_fields_skip_required_and_rule_fields() -> None:
    counts = {"note": 0, "email": 0, "amount": 0, "partner_id": 5, "is_vip": 3}
    ops = v2d.unused_field_ops(tree(), FIELDS, counts, 40)
    names = {o["node"] for o in ops}
    assert "field:note" in names and "field:email" not in names  # email is required when VIP
    assert not v2d.unused_field_ops(tree(), FIELDS, counts, 5)


def test_checklist_lists_fields_per_stage() -> None:
    stages = [{"value": "done", "label": "Done", "always": [], "at_stage": [{"field": "partner_id", "label": "Customer"}], "depends": []}]
    arch = v2d.checklist_arch("state", stages, FIELDS)
    assert "partner_id or state != 'done'" in arch and "fill in Customer" in arch
    with pytest.raises(ve.EngineError):
        v2d.checklist_arch("state", [{"value": "draft", "label": "Draft", "always": [], "at_stage": []}], FIELDS)


def test_step_progress_badges_come_from_record_fields() -> None:
    steps = v2.step_candidates(tree())[:2]
    arch = v2d.steps_progress_arch(v2.steps_layer_arch(steps), steps, FIELDS)
    assert "Step 1 done" in arch and "invisible=\"not partner_id" in arch


def test_a11y_fixes_use_existing_words() -> None:
    arch = FORM.replace('icon="fa-cog"', 'icon="fa-cog" title="Settings"')
    ops = v2d.a11y_fix_ops(ve.normalize(arch, FIELDS).tree, FIELDS, v2d.button_words(arch))
    assert any(o["attr"] == "string" and o["value"] == "Settings" for o in ops)


def test_industry_samples_are_labelled() -> None:
    recs = v2d.industry_sample_records(["name", "partner_id"], FIELDS, "hospitality", 2)
    assert all(r["__sample"] and r["id"] < 0 and r["partner_id"].startswith("Sample:") for r in recs)
    v2d.register_extra_starters()
    assert {"hospitality", "healthcare", "nonprofit"} <= set(v2.STARTERS)


def test_webhooks_only_slack_or_teams() -> None:
    assert v2d.check_webhook("https://hooks.slack.com/services/T/B/x") == "slack"
    assert v2d.check_webhook("https://acme.webhook.office.com/webhookb2/x") == "teams"
    for bad in ("http://hooks.slack.com/x", "https://evil.example.com/hook"):
        with pytest.raises(ve.EngineError):
            v2d.check_webhook(bad)
    assert "…" in v2d.mask_url("https://hooks.slack.com/services/T/B/secret")


def test_layout_test_ends_on_clear_result_or_after_60_days() -> None:
    now = datetime(2026, 12, 1, tzinfo=UTC)
    assert v2d.test_should_end({"verdict": "B", "text": "B wins."}, now, now)[0]
    assert not v2d.test_should_end({"verdict": "too_few"}, now - timedelta(days=5), now)[0]
    assert v2d.test_should_end({"verdict": "unclear"}, now - timedelta(days=61), now)[0]


def test_translation_must_keep_numbers() -> None:
    src = [{"node": "root", "title": "Overview", "text": "It shows 40 fields on 3 tabs."}]
    assert v2d.check_translation(src, {"steps": [{"title": "Aperçu", "text": "Il montre 40 champs sur 3 onglets."}]})[0]["title"] == "Aperçu"
    assert v2d.check_translation(src, {"steps": [{"title": "Aperçu", "text": "Il montre 4 champs."}]}) is None


def test_text_pdf() -> None:
    pdf = vpdf.text_pdf("Guide", [("Overview", "Hello (world) " * 50)] * 40, "note")
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF") and b"/Type /Pages" in pdf
    assert vpdf.text_pdf("x", [("a", "Ẹ")]) is None


def test_progress_skips_group_limited_fields():
    arch = ('<data><xpath expr="//sheet" position="inside"><notebook>'
            '<page string="A"><field name="a"/><field name="t" groups="g.x"/></page></notebook></xpath></data>')
    out = v2d.steps_progress_arch(arch, [{"field_names": ["a", "t"]}], {"a": {"type": "char"}, "t": {"type": "many2one"}})
    assert "not a" in out and "not t" not in out and " t" not in out.split("Step 1 done")[0].split("invisible=")[-1]
