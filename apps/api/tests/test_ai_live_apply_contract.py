"""Live-apply contract: generation must stamp fields UI apply needs on first try."""

from __future__ import annotations

from app.ai_live_apply_contract import (
    attach_live_apply_contract,
    live_apply_contract_findings,
    stamp_live_apply_contract,
)


def _broken_apply_draft() -> dict:
    return {
        "technical_name": "clinic_ops",
        "display_name": "Clinic",
        "depends": ["base"],
        "models": [
            {
                "model": "x_appointment",
                "description": "Appointment",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "selection": "[('draft','Draft'),('done','Done')]",
                    },
                    {"name": "x_date_end", "ttype": "datetime"},
                ],
            }
        ],
        "automations": [
            {
                "name": "Follow up deadline Appointment",
                "model": "x_appointment",
                "trigger": "on_time",
                "filter_domain": "[('x_date_end', '!=', False), ('x_date_end', '<', 'now')]",
                "safe_actions": [{"kind": "next_activity", "summary": "deadline"}],
            },
            {
                "name": "Notify on Appointment done",
                "model": "x_appointment",
                "trigger": "write",
                "filter_domain": "[('x_status','=','done')]",
                "safe_actions": [{"kind": "next_activity", "summary": "Review done"}],
            },
        ],
        "_user_prompt": "A neighborhood clinic with walk-in appointments",
    }


def test_unstamped_draft_fails_live_apply_contract() -> None:
    findings = live_apply_contract_findings(_broken_apply_draft())
    details = [str(f.get("detail") or "") for f in findings]
    assert any("trg_date_field_name" in d for d in details)
    assert any("mail.activity.mixin" in d for d in details)


def test_stamp_makes_live_apply_contract_ready() -> None:
    draft = _broken_apply_draft()
    notes = attach_live_apply_contract(draft)
    autos = {a["name"]: a for a in draft["automations"]}
    timed = autos["Follow up deadline Appointment"]
    assert timed["trg_date_field_name"] == "x_date_end"
    notify = autos["Notify on Appointment done"]
    assert notify["trigger"] == "on_write"
    model = draft["models"][0]
    assert "mail.activity.mixin" in model["mixins"]
    assert model.get("is_mail_activity") is True
    assert "mail" in draft["depends"]
    action = notify["safe_actions"][0]
    assert action.get("activity_type_xml_id") == "mail.mail_activity_data_todo"
    assert draft["_live_apply"]["ready"] is True
    assert not live_apply_contract_findings(draft)
    assert any("contract ready" in n for n in notes)


def test_scorecard_hygiene_flags_unstamped_on_time() -> None:
    from app.ai_draft_scorecard import draft_scorecard

    sc = draft_scorecard(_broken_apply_draft(), user_prompt="clinic appointments")
    details = [str(f.get("detail") or "") for f in sc.get("findings") or []]
    assert any("live apply" in d for d in details)


def test_close_stamps_live_apply_contract() -> None:
    from app.ai_odoo_app_bar import close_odoo_architecture

    draft = _broken_apply_draft()
    close_odoo_architecture(
        draft, user_prompt="A neighborhood clinic with walk-in appointments"
    )
    assert draft.get("_live_apply", {}).get("ready") is True
    timed = next(
        a
        for a in (draft.get("automations") or [])
        if "deadline" in str(a.get("name") or "").lower()
        and str(a.get("trigger") or "").startswith("on_time")
    )
    assert timed.get("trg_date_field_name")
    model = next(m for m in draft["models"] if m["model"] == "x_appointment")
    mixins = {str(x) for x in (model.get("mixins") or [])}
    assert "mail.activity.mixin" in mixins or model.get("is_mail_activity")


def test_prepare_spec_attaches_live_apply_contract() -> None:
    from app.ai_apply_readiness import prepare_spec_for_live_apply

    prepared, notes = prepare_spec_for_live_apply(_broken_apply_draft())
    assert prepared["_live_apply"]["ready"] is True
    assert any("live_apply" in n for n in notes)


def test_stamp_drops_unknown_trigger() -> None:
    draft = _broken_apply_draft()
    draft["automations"].append(
        {
            "name": "Bogus",
            "model": "x_appointment",
            "trigger": "whenever",
            "safe_actions": [
                {"kind": "update_field", "field": "x_status", "value": "done"}
            ],
        }
    )
    stamp_live_apply_contract(draft)
    names = {a.get("name") for a in draft["automations"]}
    assert "Bogus" not in names


def _apply_fault_draft() -> dict:
    return {
        "technical_name": "studio_ops",
        "display_name": "Studio",
        "depends": ["base"],
        "models": [
            {
                "model": "x_rate_unit",
                "description": "Rate Unit",
                "fields": [
                    {
                        "name": "x_rate",
                        "ttype": "monetary",
                        "currency_field": "x_currency_id",
                    },
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "relation": "res.currency",
                    },
                    {
                        "name": "x_crew_ids",
                        "ttype": "one2many",
                        "relation": "hr.employee",
                        "relation_field": "x_rate_unit_id",
                    },
                ],
            }
        ],
        "automations": [
            {
                "name": "Auto-Assign Studio",
                "model": "x_rate_unit",
                "trigger": "on_create",
                "filter_domain": "[]",
                "safe_actions": [
                    {
                        "kind": "object_write",
                        "field": "x_name",
                        "value": "x_name",
                    }
                ],
            }
        ],
    }


def test_unstamped_stock_o2m_and_currency_order_fail_contract() -> None:
    findings = live_apply_contract_findings(_apply_fault_draft())
    details = [str(f.get("detail") or "") for f in findings]
    assert any("stock hr.employee" in d for d in details)
    assert any("must precede monetary" in d for d in details)
    assert any("identity or Python-shaped" in d for d in details)


def test_stamp_drops_stock_o2m_and_orders_currency() -> None:
    draft = _apply_fault_draft()
    attach_live_apply_contract(draft)
    rate = draft["models"][0]
    names = [str(f.get("name")) for f in rate["fields"]]
    assert "x_crew_ids" not in names
    assert names.index("x_currency_id") < names.index("x_rate")
    auto_names = {a.get("name") for a in draft["automations"]}
    assert "Auto-Assign Studio" not in auto_names
    assert draft["_live_apply"]["ready"] is True
    assert not live_apply_contract_findings(draft)


def test_stamp_drops_mail_post_and_orders_related_after_hop() -> None:
    draft = {
        "technical_name": "studio_ops",
        "models": [
            {
                "model": "x_crew_line",
                "fields": [
                    {
                        "name": "x_currency_id",
                        "ttype": "many2one",
                        "relation": "res.currency",
                        "related": "x_rate_unit_id.x_currency_id",
                    },
                    {
                        "name": "x_rate_unit_id",
                        "ttype": "many2one",
                        "relation": "x_rate_unit",
                    },
                ],
            }
        ],
        "automations": [
            {
                "name": "Notify Booking Confirmation",
                "model": "x_crew_line",
                "trigger": "on_write",
                "filter_domain": "[]",
                "safe_actions": [{"kind": "mail_post", "body": "<p>ok</p>"}],
            }
        ],
        "smart_buttons": [
            {
                "on_model": "x_crew_line",
                "related_model": "x_booking",
                "relation_field": "x_crew_line_id",
                "label": "Crew",
            }
        ],
        "_meta": {"smart_button_count": 9},
    }
    findings = live_apply_contract_findings(draft)
    details = [str(f.get("detail") or "") for f in findings]
    assert any("identity or Python-shaped" in d for d in details)
    attach_live_apply_contract(draft)
    names = [str(f.get("name")) for f in draft["models"][0]["fields"]]
    assert names.index("x_rate_unit_id") < names.index("x_currency_id")
    assert not any(
        a.get("name") == "Notify Booking Confirmation" for a in draft["automations"]
    )
    assert draft["_meta"]["smart_button_count"] == 1
    assert not live_apply_contract_findings(draft)


def test_search_domain_on_missing_status_fails_contract() -> None:
    draft = {
        "models": [
            {
                "model": "x_rate_unit",
                "fields": [{"name": "x_name", "ttype": "char"}],
            }
        ],
        "views": [
            {
                "model": "x_rate_unit",
                "type": "search",
                "arch": (
                    '<search><filter string="Active" name="status_active" '
                    "domain=\"[('x_status','=','active')]\"/></search>"
                ),
            }
        ],
        "automations": [],
    }
    details = [str(f.get("detail") or "") for f in live_apply_contract_findings(draft)]
    assert any("search filter names missing field(s) x_status" in d for d in details)
