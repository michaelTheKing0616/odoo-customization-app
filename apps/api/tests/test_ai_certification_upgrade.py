"""Gates for AI Draft → Engineering Certification upgrade (Phases 0–6)."""

from __future__ import annotations

from app.ai_architecture_plan import build_architecture_plan, stamp_architecture_plan
from app.ai_certification import build_certification, stamp_certification
from app.ai_draft_scorecard import attach_scorecard
from app.ai_failure_ir import failures_from_sandbox_log, make_failure
from app.ai_planner_tools import find_pattern, stamp_planner_grounding
from app.ai_repair_loop import (
    begin_repair_attempt,
    lock_certified_artifacts,
    repair_allowed,
)
from app.ai_static_odoo import analyze_python_ast, stamp_static_odoo


def _field_pack_draft() -> dict:
    return {
        "technical_name": "ext_sla",
        "display_name": "SLA",
        "depends": ["account"],
        "grain": "field_pack",
        "grain_label": "Field pack on account.move",
        "models": [
            {
                "model": "account.move",
                "mode": "inherit",
                "fields": [
                    {"name": "x_sla_due", "ttype": "date", "string": "SLA due"},
                ],
            }
        ],
        "views": [
            {
                "id": "view_move_form_sla",
                "model": "account.move",
                "type": "form",
                "inherit_mode": "extension",
                "arch": '<xpath expr="//field[@name=\'partner_id\']" position="after">'
                '<field name="x_sla_due"/></xpath>',
            }
        ],
        "menus": [],
        "access_rules": [],
        "_user_prompt": "Add SLA due date on invoices",
        "_scorecard": {
            "score_0_10": 9.0,
            "validators": {"all_green": True},
            "findings": [],
            "dimensions": {},
        },
    }


def test_architecture_plan_field_pack_strategy():
    draft = _field_pack_draft()
    plan = build_architecture_plan(draft, prompt=draft["_user_prompt"])
    assert plan["strategy"] == "field_pack"
    assert plan["surface_budget"]["new_models"] == 0
    assert "x_invoice" in plan["forbidden_clones"]


def test_architecture_drift_over_budget():
    draft = _field_pack_draft()
    draft["models"].append(
        {"model": "x_bill", "mode": "new", "fields": [{"name": "x_name", "ttype": "char"}]}
    )
    stamp_architecture_plan(draft, prompt=draft["_user_prompt"], rebuild=True)
    assert any("forbidden_clone" in d or "field_pack" in d for d in draft["_architecture_drift"])


def test_certification_separate_from_completeness():
    draft = _field_pack_draft()
    draft["_capability_primary_option_a"] = True
    draft["_option_a_smoke"] = {"ok": False, "message": "unproven"}
    cert = build_certification(draft)
    assert cert["tier"] in {"Reject", "ReviewRequired"}
    assert "option_a_smoke_failed" in cert["hard_failures"]
    assert cert["completeness_score_0_10"] == 9.0


def test_certification_field_pack_can_be_production():
    draft = _field_pack_draft()
    stamp_architecture_plan(draft, rebuild=True)
    draft["_architecture_drift"] = []
    cert = stamp_certification(draft)
    assert cert["tier"] in {"Production", "ReviewRequired", "Gold"}
    assert draft["_certification"]["tier"] == cert["tier"]


def test_static_sudo_and_raw_sql():
    code = """
class X(models.Model):
    _name = 'x.demo'
    def action(self):
        self.env['res.partner'].sudo().search([])
        self.env.cr.execute('SELECT 1')
"""
    findings = analyze_python_ast(code, source_file="models/demo.py")
    rules = {f["rule"] for f in findings}
    assert "sudo_call" in rules
    assert "raw_sql" in rules


def test_failure_ir_from_log():
    log = 'File "/mnt/extra-addons/ext_x/models/foo.py", line 12, in action\nError'
    fails = failures_from_sandbox_log(log, ok=False, message="install failed")
    assert fails
    assert fails[0]["category"] in {"python", "install", "xml"}
    assert "failure_id" in fails[0]


def test_repair_loop_locks_and_thrash_budget():
    draft = _field_pack_draft()
    draft["custom_code_blocks"] = [
        {"source_file": "models/a.py", "kind": "python", "content": "x=1"}
    ]
    lock_certified_artifacts(draft, run_id="t1")
    ok, why = repair_allowed(draft, target_file="models/a.py")
    assert ok is False
    assert "locked" in why

    draft2 = {"_repair_count": 0, "_failures": []}
    f = [make_failure(category="smoke", message="boom", file="models/b.py")]
    meta = begin_repair_attempt(draft2, f)
    assert meta["ok"] is True
    assert draft2["_repair_count"] == 1

    sandbox = {"_sandbox_repair_count": 0, "_failures": []}
    meta_s = begin_repair_attempt(sandbox, f, bucket="sandbox")
    assert meta_s["ok"] is True
    assert sandbox["_sandbox_repair_count"] == 1
    assert sandbox.get("_repair_count") in (None, 0)

    burned_authoring = {"_repair_count": 3, "_sandbox_repair_count": 0, "_failures": []}
    meta_b = begin_repair_attempt(burned_authoring, f, bucket="sandbox")
    assert meta_b["ok"] is True
    assert burned_authoring["_sandbox_repair_count"] == 1
    assert burned_authoring["_repair_count"] == 3

    exhausted = {"_sandbox_repair_count": 3, "_failures": []}
    meta_x = begin_repair_attempt(exhausted, f, bucket="sandbox")
    assert meta_x["ok"] is False
    assert meta_x["reason"] == "max_repair_exceeded"
    from app.ai_repair_loop import budget_exhausted_message

    msg = budget_exhausted_message("max_repair_exceeded")
    assert "Download module zip still works" in msg
    assert "Zip export failed" not in msg
    assert "passing zip" not in msg


def test_planner_patterns_and_grounding():
    from app.ai_planner_tools import find_views

    pats = find_pattern("invoice qweb pay", limit=3)
    assert pats
    draft = _field_pack_draft()
    g = stamp_planner_grounding(draft)
    assert "patterns" in g
    assert draft["_planner_grounding"]["pattern_library_size"] >= 1
    views = find_views(draft.get("views"), "account.move")
    assert views
    assert "x_sla_due" in (views[0].get("field_names") or [])


def test_security_acl_accepts_model_x_stub() -> None:
    from app.ai_draft_scorecard import draft_scorecard

    draft = {
        "technical_name": "law_firm_management",
        "depends": ["base"],
        "grain": "full_app",
        "models": [
            {
                "model": "x_matter",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "views": [],
        "menus": [],
        "access_rules": [
            {
                "model": "model_x_matter",
                "group": "group_law_firm_management_user",
                "perm_read": 1,
            }
        ],
        "groups": [{"id": "group_law_firm_management_user", "name": "User"}],
        "_user_prompt": "law firm matter",
        "_architecture_plan": {
            "strategy": "residual_app",
            "surface_budget": {"new_models": 8, "new_js": 0, "new_controllers": 0},
            "forbidden_clones": [],
        },
    }
    card = draft_scorecard(draft, user_prompt="law firm")
    elements = {
        f.get("element") for f in (card.get("findings") or []) if isinstance(f, dict)
    }
    assert "security_acl" not in elements


def test_security_minimality_findings_via_scorecard():
    draft = {
        "technical_name": "ext_big",
        "display_name": "Big",
        "depends": ["base"],
        "grain": "field_pack",
        "models": [
            {
                "model": "account.move",
                "mode": "inherit",
                "fields": [{"name": "x_a", "ttype": "char"}],
            },
            {"model": "x_extra", "mode": "new", "fields": [{"name": "x_name", "ttype": "char"}]},
        ],
        "views": [],
        "menus": [],
        "access_rules": [],
        "_user_prompt": "Add one field on invoices",
        "_architecture_plan": {
            "strategy": "field_pack",
            "forbidden_clones": ["x_bill"],
            "surface_budget": {"new_models": 0, "new_js": 0, "new_controllers": 0},
            "stock_hosts": ["account.move"],
            "new_x_models": [],
        },
    }
    stamp_static_odoo(draft)
    card = attach_scorecard(draft, user_prompt=draft["_user_prompt"])
    elements = {
        f.get("element") for f in (card.get("findings") or []) if isinstance(f, dict)
    }
    assert "architecture_fit" in elements or "minimality" in elements or "security_acl" in elements
