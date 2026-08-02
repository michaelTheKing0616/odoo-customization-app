"""Tests for ModuleSpec draft repair rules (AI slip normalization)."""

from __future__ import annotations

from app.ai_rules import repair_smart_buttons_and_automations


def test_repair_smart_button_relation_field_prefix() -> None:
    draft = {
        "models": [
            {
                "model": "x_patient",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_appointment",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_patient_id",
                        "ttype": "many2one",
                        "relation": "x_patient",
                    },
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_patient",
                "related_model": "x_appointment",
                "relation_field": "patient_id",
                "label": "Appointments",
            }
        ],
        "automations": [
            {
                "name": "On create",
                "model": "x_appointment",
                "trigger": "create",
                "filter_domain": "[('status', '=', 'confirmed')]",
                "safe_actions": [{"kind": "object_write", "field": "x_name", "value": "x"}],
            }
        ],
    }
    # Add x_status so filter repair can run
    draft["models"][1]["fields"].append(
        {
            "name": "x_status",
            "ttype": "selection",
            "selection": "[('confirmed','Confirmed')]",
        }
    )
    notes = repair_smart_buttons_and_automations(draft)
    assert draft["smart_buttons"][0]["relation_field"] == "x_patient_id"
    assert draft["automations"][0]["trigger"] == "on_create"
    assert "x_status" in draft["automations"][0]["filter_domain"]
    assert notes
