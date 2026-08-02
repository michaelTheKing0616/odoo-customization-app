"""Unit tests for automation request validation (no live Odoo)."""

import pytest
from pydantic import ValidationError

from odoo_client.automation import (
    ADVANCED_SERVER_STATES,
    AutomationTrigger,
    CreateAutomationRequest,
    FollowersAction,
    SAFE_TRIGGERS,
    SmsAction,
    UpdateFieldAction,
    WebhookAction,
)


def test_create_automation_update_field() -> None:
    req = CreateAutomationRequest(
        name="Set note",
        model="res.partner",
        trigger=AutomationTrigger.ON_CREATE,
        action=UpdateFieldAction(field_name="x_auto_note", value="hi"),
    )
    assert req.trigger == AutomationTrigger.ON_CREATE


def test_on_time_requires_date_field() -> None:
    with pytest.raises(ValidationError):
        CreateAutomationRequest(
            name="Timed",
            model="res.partner",
            trigger=AutomationTrigger.ON_TIME,
            action=UpdateFieldAction(field_name="x_auto_note", value="hi"),
        )


def test_create_record_action() -> None:
    from odoo_client.automation import CreateRecordAction

    req = CreateAutomationRequest(
        name="Spawn note",
        model="res.partner",
        trigger=AutomationTrigger.ON_CREATE,
        action=CreateRecordAction(
            target_model="res.partner",
            field_values={"name": "Child"},
        ),
    )
    assert req.action.kind == "create_record"


def test_related_write_action() -> None:
    from odoo_client.automation import RelatedWriteAction

    req = CreateAutomationRequest(
        name="Vehicle rented",
        model="x_rental_contract",
        trigger=AutomationTrigger.ON_WRITE,
        filter_domain="[('x_status','=','confirmed')]",
        action=RelatedWriteAction(
            relation_field="x_vehicle_id",
            field_name="x_status",
            value="rented",
        ),
    )
    assert req.action.kind == "related_write"
    assert req.action.relation_field == "x_vehicle_id"


def test_message_and_webhook_triggers_allowed() -> None:
    for trigger in (
        AutomationTrigger.ON_MESSAGE_RECEIVED,
        AutomationTrigger.ON_MESSAGE_SENT,
        AutomationTrigger.ON_WEBHOOK,
    ):
        assert trigger.value in SAFE_TRIGGERS
        req = CreateAutomationRequest(
            name=f"T {trigger.value}",
            model="res.partner",
            trigger=trigger,
            action=UpdateFieldAction(field_name="x_auto_note", value="hi"),
        )
        assert req.trigger == trigger


def test_webhook_sms_followers_actions() -> None:
    wh = CreateAutomationRequest(
        name="Hook",
        model="res.partner",
        trigger=AutomationTrigger.ON_CREATE,
        action=WebhookAction(webhook_url="https://example.com/hook"),
    )
    assert wh.action.kind == "webhook"

    sms = CreateAutomationRequest(
        name="Text",
        model="res.partner",
        trigger=AutomationTrigger.ON_CREATE,
        action=SmsAction(body="Hello"),
    )
    assert sms.action.kind == "sms"

    with pytest.raises(ValidationError):
        SmsAction()

    fol = CreateAutomationRequest(
        name="Follow",
        model="res.partner",
        trigger=AutomationTrigger.ON_CREATE,
        action=FollowersAction(partner_ids=[1, 2], followers_type="specific"),
    )
    assert fol.action.kind == "followers"
    assert ADVANCED_SERVER_STATES == frozenset(
        {"webhook", "sms", "followers", "remove_followers"}
    )
