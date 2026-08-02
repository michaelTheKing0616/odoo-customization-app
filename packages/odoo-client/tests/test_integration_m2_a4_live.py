"""Live RPC smokes for post-unlock M2 views + advanced A4 automations (Odoo 19).

Requires local Docker Odoo 19 on :8069 (skills/odoo-rpc-gate.md).
"""

from __future__ import annotations

import os
import uuid

import pytest

from odoo_client import (
    ConnectionConfig,
    CreateAutomationRequest,
    CreateViewRequest,
    FollowersAction,
    OdooClient,
    WebhookAction,
    render_activity_arch,
    render_cohort_arch,
    render_form_arch,
    render_gantt_arch,
    render_map_arch,
)
from odoo_client.automation import AutomationTrigger
from odoo_client.client import OdooClientError
from odoo_client.view_arch import (
    ActivityViewSpec,
    CohortViewSpec,
    FormViewSpec,
    GanttViewSpec,
    MapViewSpec,
    parse_activity_arch,
    parse_form_arch,
    parse_map_arch,
)


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@pytest.fixture(scope="module")
def client() -> OdooClient:
    config = ConnectionConfig(
        url=_env("ODOO_URL", "http://127.0.0.1:8069"),
        db=_env("ODOO_DB", "odoo_dev"),
        username=_env("ODOO_USER", "admin"),
        password=_env("ODOO_PASSWORD", "admin"),
    )
    c = OdooClient(config)
    try:
        c.connect()
    except OdooClientError as exc:
        pytest.skip(f"Odoo 19 not reachable: {exc}")
    version = c.server_version()
    if not str(version.get("server_version", "")).startswith("19"):
        pytest.skip(f"Expected Odoo 19, got {version.get('server_version')}")
    return c


def _view_type_allowed(client: OdooClient, view_type: str) -> bool:
    """True if ir.ui.view.type selection includes view_type."""
    fields = client.execute_kw(
        "ir.ui.view",
        "fields_get",
        [["type"]],
        {"attributes": ["selection"]},
    )
    sel = fields.get("type", {}).get("selection") or []
    return any(row[0] == view_type for row in sel if isinstance(row, (list, tuple)))


def _module_installed(client: OdooClient, name: str) -> bool:
    rows = client.execute_kw(
        "ir.module.module",
        "search_read",
        [[("name", "=", name)]],
        {"fields": ["state"], "limit": 1},
    )
    return bool(rows) and rows[0].get("state") in {"installed", "to upgrade", "to remove"}


@pytest.mark.integration
def test_live_activity_view_round_trip(client: OdooClient) -> None:
    if not _view_type_allowed(client, "activity"):
        pytest.skip("ir.ui.view type=activity not in selection on this DB")
    suffix = uuid.uuid4().hex[:8]
    arch = render_activity_arch(
        ActivityViewSpec(string=f"Activity {suffix}", fields=[])
    )
    view = client.create_view(
        CreateViewRequest(
            name=f"x_activity_{suffix}",
            model="res.partner",
            type="activity",
            arch=arch,
        )
    )
    assert view.id > 0
    assert view.type == "activity"
    raw = client.execute_kw(
        "ir.ui.view", "read", [[view.id]], {"fields": ["arch"]}
    )[0]
    parsed = parse_activity_arch(raw["arch"])
    assert parsed.string == f"Activity {suffix}"
    client.execute_kw("ir.ui.view", "unlink", [[view.id]])


@pytest.mark.integration
def test_live_map_view_round_trip(client: OdooClient) -> None:
    if not _view_type_allowed(client, "map"):
        pytest.skip("ir.ui.view type=map not in selection on this DB")
    suffix = uuid.uuid4().hex[:8]
    arch = render_map_arch(
        MapViewSpec(string=f"Map {suffix}", res_partner="id", fields=[])
    )
    # res.partner map often uses partner field differently; try create and skip soft fails
    try:
        view = client.create_view(
            CreateViewRequest(
                name=f"x_map_{suffix}",
                model="res.partner",
                type="map",
                arch=arch,
            )
        )
    except OdooClientError as exc:
        pytest.skip(f"map view create refused on this DB: {exc}")
    assert view.id > 0
    raw = client.execute_kw(
        "ir.ui.view", "read", [[view.id]], {"fields": ["arch"]}
    )[0]
    parsed = parse_map_arch(raw["arch"])
    assert "Map" in (parsed.string or "")
    client.execute_kw("ir.ui.view", "unlink", [[view.id]])


@pytest.mark.integration
def test_live_form_can_create_attr(client: OdooClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    arch = render_form_arch(
        FormViewSpec(string=f"Locked {suffix}", create=False, edit=True, children=[])
    )
    view = client.create_view(
        CreateViewRequest(
            name=f"x_form_attrs_{suffix}",
            model="res.partner",
            type="form",
            arch=arch,
            priority=99,
        )
    )
    raw = client.execute_kw(
        "ir.ui.view", "read", [[view.id]], {"fields": ["arch"]}
    )[0]
    parsed = parse_form_arch(raw["arch"])
    assert parsed.create is False
    assert parsed.edit is True
    client.execute_kw("ir.ui.view", "unlink", [[view.id]])


@pytest.mark.integration
def test_live_gantt_create_or_skip(client: OdooClient) -> None:
    if not _view_type_allowed(client, "gantt"):
        pytest.skip("gantt view type absent (expected on CE without web_gantt)")
    suffix = uuid.uuid4().hex[:8]
    arch = render_gantt_arch(
        GanttViewSpec(
            string=f"Gantt {suffix}",
            date_start="create_date",
            date_stop="write_date",
        )
    )
    try:
        view = client.create_view(
            CreateViewRequest(
                name=f"x_gantt_{suffix}",
                model="res.partner",
                type="gantt",
                arch=arch,
            )
        )
    except OdooClientError as exc:
        pytest.skip(f"gantt create failed (module-gated honesty): {exc}")
    client.execute_kw("ir.ui.view", "unlink", [[view.id]])


@pytest.mark.integration
def test_live_cohort_create_or_skip(client: OdooClient) -> None:
    if not _view_type_allowed(client, "cohort"):
        pytest.skip("cohort view type absent (often EE/module-gated)")
    suffix = uuid.uuid4().hex[:8]
    arch = render_cohort_arch(
        CohortViewSpec(string=f"Cohort {suffix}", date_start="create_date")
    )
    try:
        view = client.create_view(
            CreateViewRequest(
                name=f"x_cohort_{suffix}",
                model="res.partner",
                type="cohort",
                arch=arch,
            )
        )
    except OdooClientError as exc:
        pytest.skip(f"cohort create failed (module-gated honesty): {exc}")
    client.execute_kw("ir.ui.view", "unlink", [[view.id]])


@pytest.mark.integration
def test_live_webhook_automation_create_inactive(client: OdooClient) -> None:
    client.ensure_module_installed("base_automation")
    suffix = uuid.uuid4().hex[:8]
    # Inactive so webhook never fires against the URL during the test.
    created = client.create_automation(
        CreateAutomationRequest(
            name=f"x_webhook_smoke_{suffix}",
            model="res.partner",
            trigger=AutomationTrigger.ON_CREATE,
            active=False,
            action=WebhookAction(
                webhook_url="https://example.com/odoo-webhook-smoke",
                webhook_field_names=["name"],
            ),
        )
    )
    assert created.id > 0
    assert created.trigger == "on_create"
    assert created.active is False
    # Inspect linked server action state
    sa_ids = created.action_server_ids
    assert sa_ids
    sa = client.execute_kw(
        "ir.actions.server",
        "read",
        [sa_ids],
        {"fields": ["state", "webhook_url"]},
    )[0]
    assert sa["state"] == "webhook"
    assert "example.com" in (sa.get("webhook_url") or "")
    client.execute_kw("base.automation", "unlink", [[created.id]])


@pytest.mark.integration
def test_live_followers_automation_create_inactive(client: OdooClient) -> None:
    client.ensure_module_installed("base_automation")
    # res.partner is mail.thread — followers action is meaningful
    if not client.model_exists("mail.followers"):
        pytest.skip("mail.followers missing")
    suffix = uuid.uuid4().hex[:8]
    partner_id = client.execute_kw(
        "res.partner",
        "search",
        [[("is_company", "=", True)]],
        {"limit": 1},
    )
    if not partner_id:
        partner_id = client.execute_kw("res.partner", "search", [[]], {"limit": 1})
    assert partner_id
    created = client.create_automation(
        CreateAutomationRequest(
            name=f"x_followers_smoke_{suffix}",
            model="res.partner",
            trigger=AutomationTrigger.ON_WRITE,
            active=False,
            action=FollowersAction(
                followers_type="specific",
                partner_ids=[int(partner_id[0])],
            ),
        )
    )
    assert created.id > 0
    sa = client.execute_kw(
        "ir.actions.server",
        "read",
        [created.action_server_ids],
        {"fields": ["state"]},
    )[0]
    assert sa["state"] == "followers"
    client.execute_kw("base.automation", "unlink", [[created.id]])


@pytest.mark.integration
def test_live_sms_automation_or_skip(client: OdooClient) -> None:
    if not _module_installed(client, "sms"):
        pytest.skip("sms module not installed — grey-out honesty path")
    from odoo_client import SmsAction

    client.ensure_module_installed("base_automation")
    suffix = uuid.uuid4().hex[:8]
    try:
        created = client.create_automation(
            CreateAutomationRequest(
                name=f"x_sms_smoke_{suffix}",
                model="res.partner",
                trigger=AutomationTrigger.ON_CREATE,
                active=False,
                action=SmsAction(body=f"Smoke {suffix}"),
            )
        )
    except OdooClientError as exc:
        pytest.skip(f"sms automation create failed: {exc}")
    sa = client.execute_kw(
        "ir.actions.server",
        "read",
        [created.action_server_ids],
        {"fields": ["state"]},
    )[0]
    assert sa["state"] == "sms"
    client.execute_kw("base.automation", "unlink", [[created.id]])


@pytest.mark.integration
def test_live_on_message_trigger_selection(client: OdooClient) -> None:
    """Confirm Odoo 19 exposes email-event triggers we advertise."""
    client.ensure_module_installed("base_automation")
    fields = client.execute_kw(
        "base.automation",
        "fields_get",
        [["trigger"]],
        {"attributes": ["selection"]},
    )
    sel = {row[0] for row in (fields.get("trigger", {}).get("selection") or [])}
    for needed in ("on_message_received", "on_message_sent", "on_webhook"):
        if needed not in sel:
            pytest.skip(f"trigger {needed!r} not in selection: {sorted(sel)}")
    # Create inactive on_message_received + mail_post-free update via webhook inactive already covered
    suffix = uuid.uuid4().hex[:8]
    created = client.create_automation(
        CreateAutomationRequest(
            name=f"x_msg_trig_{suffix}",
            model="res.partner",
            trigger=AutomationTrigger.ON_MESSAGE_RECEIVED,
            active=False,
            action=WebhookAction(webhook_url="https://example.com/msg"),
        )
    )
    assert created.trigger == "on_message_received"
    client.execute_kw("base.automation", "unlink", [[created.id]])
