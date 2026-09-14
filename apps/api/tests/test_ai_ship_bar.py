"""Ship-bar upgrades: inherit junk strip, Cert honesty, Option A gaps, journals."""

from __future__ import annotations

from app.ai_capability_gaps import assess_capability_gaps
from app.ai_certification import build_certification, stamp_certification
from app.ai_stock_first import strip_stock_inherit_junk_fields
from app.job_autopilot.packet import SCORECARD_IS_NOT_GOLIVE


def test_strip_stock_inherit_junk_x_name():
    draft = {
        "models": [
            {
                "model": "sale.order",
                "mode": "inherit",
                "is_workflow": True,
                "state_field": {"field": "x_status", "transitions": [["draft", "open"]]},
                "fields": [
                    {"name": "x_name", "ttype": "char", "required": True},
                    {"name": "x_matter_id", "ttype": "many2one", "relation": "x_matter"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('open','Open')]",
                    },
                ],
            },
            {
                "model": "x_matter",
                "mode": "new",
                "fields": [{"name": "x_name", "ttype": "char", "required": True}],
            },
        ],
        "sequences": [
            {"model": "sale.order", "field": "x_code", "prefix": "SO/"},
            {"model": "x_matter", "field": "x_code", "prefix": "MATTER/"},
        ],
    }
    notes = strip_stock_inherit_junk_fields(draft)
    so = draft["models"][0]
    names = {f["name"] for f in so["fields"]}
    assert "x_name" not in names
    assert "x_matter_id" in names
    assert "x_status" not in names
    assert not so.get("is_workflow")
    assert any("junk inherit" in n for n in notes)
    assert draft["models"][1]["fields"][0]["name"] == "x_name"  # custom keeps x_name
    assert all(s.get("model") != "sale.order" for s in draft["sequences"])


def test_cert_review_when_option_a_pending():
    draft = {
        "grain": "full_app",
        "models": [{"model": "x_matter", "mode": "new", "fields": []}],
        "custom_code_blocks": [
            {
                "source_file": "data/payment_provider_stub.xml",
                "kind": "xml",
                "option_a": True,
                "content": "<odoo/>",
            }
        ],
        "_capability_gaps": [{"id": "payment_provider"}, {"id": "qr_on_document"}],
        "_scorecard": {
            "score_0_10": 9.7,
            "validators": {"all_green": True},
            "findings": [],
        },
        "_architecture_plan": {"strategy": "residual_app", "forbidden_clones": []},
        "_architecture_drift": [],
        "_static_odoo": {"findings": [], "critical_count": 0, "ok": True},
        "_done_bar": {"option_a": "scaffold_pending_smoke", "mode": "mixed"},
    }
    cert = build_certification(draft)
    assert cert["tier"] in {"Reject", "ReviewRequired"}
    assert cert["option_a_pending"] is True
    assert "option_a_smoke_failed" in cert["hard_failures"] or cert["tier"] == "ReviewRequired"
    assert any(
        e.get("check") == "autopilot_process_smoke" and e.get("status") == "SKIP"
        for e in cert["evidence_ledger"]
    )


def test_cert_review_for_line_compute_python_block():
    """AOP-style draft: line subtotal Option A without smoke must not be Production."""
    draft = {
        "grain": "full_app",
        "models": [{"model": "x_matter_line", "mode": "new", "fields": []}],
        "custom_code_blocks": [
            {
                "source_file": "models/x_matter_line.py",
                "kind": "python",
                "reason": "apply_readiness: line subtotal compute",
                "content": "from odoo import models\n",
            }
        ],
        "_capability_gaps": [{"id": "qr_on_document"}, {"id": "payment_provider"}],
        "_scorecard": {
            "score_0_10": 9.7,
            "validators": {"all_green": True},
            "findings": [],
        },
        "_architecture_plan": {"strategy": "residual_app", "forbidden_clones": []},
        "_architecture_drift": [],
        "_static_odoo": {"findings": [], "critical_count": 0, "ok": True},
        "_done_bar": {"option_a": "scaffold_pending_smoke", "mode": "mixed"},
    }
    cert = build_certification(draft)
    assert cert["tier"] != "Production"
    assert cert["option_a_pending"] is True


def test_acl_accepts_model_x_stubs():
    from app.ai_draft_scorecard import draft_scorecard

    draft = {
        "technical_name": "law_firm_management",
        "models": [
            {"model": "x_matter", "mode": "new", "fields": [{"name": "x_name", "ttype": "char"}]},
            {
                "model": "sale.order",
                "mode": "inherit",
                "fields": [{"name": "x_matter_id", "ttype": "many2one", "relation": "x_matter"}],
            },
        ],
        "access_rules": [
            {
                "id": "access_x_matter_user",
                "model": "model_x_matter",
                "group": "group_law_firm_management_user",
                "perm_read": 1,
                "perm_write": 1,
                "perm_create": 1,
                "perm_unlink": 0,
            }
        ],
        "views": [],
        "menus": [],
        "actions": [],
    }
    card = draft_scorecard(draft, user_prompt="law firm matter")
    acl = [f for f in card["findings"] if f.get("element") == "security_acl"]
    assert not acl, acl


def test_paystack_brief_detects_payment_and_qr_gaps():
    prompt = (
        "Paystack: dynamic QR and card checkout on retainer invoices. "
        "Provider stays disabled until keys pasted."
    )
    assessment = assess_capability_gaps(prompt)
    ids = {g.id for g in assessment.gaps}
    assert "payment_provider" in ids
    assert "qr_on_document" in ids or "click_to_pay" in ids or "payment_provider" in ids


def test_autopilot_scorecard_note_separates_cert():
    assert "Certification" in SCORECARD_IS_NOT_GOLIVE
    assert "Autopilot" in SCORECARD_IS_NOT_GOLIVE


def test_stamp_cert_sets_option_a_pending_meta():
    draft = {
        "grain": "field_pack",
        "models": [
            {
                "model": "account.move",
                "mode": "inherit",
                "fields": [{"name": "x_sla_due", "ttype": "date"}],
            }
        ],
        "_scorecard": {
            "score_0_10": 9.0,
            "validators": {"all_green": True},
            "findings": [],
        },
        "_architecture_plan": {"strategy": "field_pack", "forbidden_clones": []},
        "_architecture_drift": [],
    }
    cert = stamp_certification(draft)
    assert draft["_meta"]["certification_tier"] == cert["tier"]
