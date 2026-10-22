"""App Studio never refuses a whole brief because one optional app is missing."""

from __future__ import annotations

import os
import uuid

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from fastapi.testclient import TestClient  # noqa: E402

from app.brief_integrations import build_brief_plan, split_primary  # noqa: E402
from app.job_autopilot.planner import _stock_app_plan  # noqa: E402
from app.live_schema_context import SchemaPacket  # noqa: E402
from app.stock_app_install import (  # noqa: E402
    InstallFacts,  # noqa: E402
    install_stock_app,
    match_stock_app,
    proposal_for,
)

CUSTOMER_HEALTH = (
    "Customer Health & Retention Intelligence: a B2B customer-success module with a "
    "configurable health score 0-100 with weights and thresholds, a dashboard, a Customer "
    "360 Health tab on res.partner, a no-code rules engine, a Customer Risk model, proactive "
    "actions with explanations, success plans, a renewal workspace, expansion opportunities "
    "into CRM, alerts and config. Integrations with res.partner, CRM, sale, subscriptions, "
    "invoices, payments, helpdesk tickets, project tasks and activities. Security groups CS "
    "User, CS Manager, Sales Manager, Admin. Score history, explainability, full module."
)


class FakeOdoo:
    """Read-only fake: models present and ir.module.module states."""

    def __init__(self, models: set[str], states: dict[str, str]) -> None:
        self.models = models
        self.states = states
        self.installed: list[str] = []

    def execute_kw(self, model, method, args, kwargs=None):
        if model == "ir.model" and method == "search_count":
            return 1 if args[0][0][2] in self.models else 0
        if model == "ir.module.module" and method == "search_read":
            name = args[0][0][2]
            return [{"id": 7, "state": self.states[name]}] if name in self.states else []
        if model == "ir.module.module" and method == "button_immediate_install":
            self.installed.append(args[0][0])
            return {"type": "ir.actions.client", "tag": "reload"}
        raise AssertionError((model, method, args))


_CORE = {"res.partner", "crm.lead", "account.move", "project.task", "mail.activity"}


def _enterprise(helpdesk_state: str = "installed") -> FakeOdoo:
    models = set(_CORE) | ({"helpdesk.ticket"} if helpdesk_state == "installed" else set())
    return FakeOdoo(models, {"helpdesk": helpdesk_state, "crm": "installed"})


def _community() -> FakeOdoo:
    return FakeOdoo(set(_CORE), {"crm": "installed"})  # no helpdesk row on Community


def _items(plan):
    return {i.module: i for i in plan.integrations}


def test_customer_health_has_no_blocking_primary_app():
    primary, others = split_primary(CUSTOMER_HEALTH)
    assert primary is None
    assert "helpdesk" in {m.app.module for m in others}


def test_enterprise_builds_core_and_includes_helpdesk():
    proposal, plan = build_brief_plan(
        CUSTOMER_HEALTH, _enterprise(), edition="enterprise", hosting_hint="self_hosted"
    )
    assert proposal is None
    assert _items(plan)["helpdesk"].status == "available"
    assert plan.left_out == []
    assert plan.as_dict()["core_built"] is True


def test_enterprise_with_helpdesk_uninstalled_defers_not_refuses():
    proposal, plan = build_brief_plan(
        CUSTOMER_HEALTH, _enterprise("uninstalled"), edition="enterprise"
    )
    assert proposal is None
    item = _items(plan)["helpdesk"]
    assert item.status == "deferred" and "Install Helpdesk" in item.note
    assert "helpdesk.ticket" in plan.omitted_models


def test_community_builds_core_with_helpdesk_left_out():
    proposal, plan = build_brief_plan(CUSTOMER_HEALTH, _community(), edition="community")
    assert proposal is None  # no whole-brief refusal
    item = _items(plan)["helpdesk"]
    assert item.status == "left_out"
    assert "Enterprise" in item.note and "refine" in item.note
    out = plan.as_dict()
    assert out["left_out"] == ["helpdesk"]
    assert out["summary"].startswith("Building the core app.")


def test_unknown_edition_does_not_hard_block():
    proposal, plan = build_brief_plan(CUSTOMER_HEALTH, _community(), edition="unknown")
    assert proposal is None
    item = _items(plan)["helpdesk"]
    assert item.status == "left_out" and "Community" not in item.note


def test_online_python_pieces_go_to_option_a_lane():
    _, plan = build_brief_plan(
        CUSTOMER_HEALTH, _enterprise(), edition="enterprise", hosting_hint="online"
    )
    keys = {p["key"] for p in plan.python_pieces}
    assert {"computed_score", "rules_engine", "scheduled_actions"} <= keys
    for piece in plan.python_pieces:
        assert piece["delivery_lane"] == "module_sh_or_self"
        assert piece["artifact_kind"] == "option_a_module"
        assert piece["online_blocked"] == "true"
        assert "Odoo.sh" in piece["lane_note"]
        assert "cannot install on Odoo Online" in piece["lane_note"]


def test_self_hosted_python_pieces_not_labelled_online_blocked():
    _, plan = build_brief_plan(
        CUSTOMER_HEALTH, _enterprise(), edition="enterprise", hosting_hint="self_hosted"
    )
    assert plan.python_pieces and all(p["online_blocked"] == "false" for p in plan.python_pieces)


def test_short_primary_brief_keeps_existing_gate():
    """Prefer-style single-app briefs still get the install / explain step."""
    proposal, plan = build_brief_plan(
        "Add an SLA tier on helpdesk tickets", _community(), edition="community"
    )
    assert plan.primary_module == "helpdesk"
    assert proposal is not None and proposal.installable is False
    assert "cannot be installed on Community" in proposal.question


def test_installer_accepts_helpdesk_on_enterprise():
    match = match_stock_app("Add an SLA tier on helpdesk tickets")
    facts = InstallFacts(model_present=False, module_state="uninstalled", edition="enterprise")
    proposal = proposal_for(match, facts)
    assert proposal is not None and proposal.installable
    port = _enterprise("uninstalled")
    outcome = install_stock_app(port, proposal)
    assert outcome.ok, outcome.message


def test_installer_still_refuses_non_installable_proposal():
    match = match_stock_app("Add an SLA tier on helpdesk tickets")
    proposal = proposal_for(match, InstallFacts(False, None, "community"))
    outcome = install_stock_app(_community(), proposal)
    assert outcome.ok is False


def _packet(version: str, modules: list[tuple[str, str]]) -> SchemaPacket:
    return SchemaPacket(
        server_version=version,
        major=19,
        modules=tuple({"name": n, "state": s} for n, s in modules),
        models={},
    )


def test_planner_keeps_enterprise_app_on_enterprise():
    keep, _, notes = _stock_app_plan(
        "helpdesk tickets", ["helpdesk"], _packet("19.0+e", [("helpdesk", "uninstalled")])
    )
    assert "helpdesk" in keep and notes == []


def test_planner_drops_enterprise_app_on_confirmed_community():
    keep, _, notes = _stock_app_plan("helpdesk tickets", ["helpdesk"], _packet("19.0", []))
    assert "helpdesk" not in keep
    assert any("Community" in n for n in notes)


def test_planner_unknown_edition_does_not_hard_block():
    keep, _, notes = _stock_app_plan("helpdesk tickets", ["helpdesk"], None)
    assert "helpdesk" in keep
    assert any("only if this database is Enterprise" in n for n in notes)


# --- route level -----------------------------------------------------------------


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch):
    from app.db import init_db
    from app.main import app
    from app.settings import settings

    monkeypatch.setattr(settings, "ai_intent_llm", "off", raising=False)
    monkeypatch.setattr("app.llm_provider.get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr("app.llm_provider.get_llm_provider_for_tier", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.ai_studio.get_llm_provider", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.ai_studio.get_llm_provider_for_tier", lambda *a, **k: None)
    monkeypatch.setattr("app.routers.ai_studio._studio_schema_packet", lambda *a, **k: None)
    init_db()
    with TestClient(app) as client:
        yield client


def _connection(version: str, url: str = "http://127.0.0.1:9") -> str:
    from app.crypto import encrypt_secret
    from app.db import SessionLocal
    from app.db_models import OdooConnection

    db = SessionLocal()
    try:
        row = OdooConnection(
            name="brief-integrations",
            url=url,
            db_name=f"brief-{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            write_mode="standard",
            server_version=version,
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


@pytest.mark.parametrize(
    ("version", "port_factory", "status"),
    [("19.0", _community, "left_out"), ("19.0+e", _enterprise, "available")],
)
def test_session_create_never_refuses_customer_health(
    api: TestClient, monkeypatch: pytest.MonkeyPatch, version, port_factory, status
):
    port = port_factory()
    monkeypatch.setattr("app.routers.ai_studio._open_stock_app_port", lambda conn: port)
    res = api.post(
        "/api/ai/sessions",
        json={"prompt": CUSTOMER_HEALTH, "connection_id": _connection(version)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    clar = body.get("clarification") or {}
    assert clar.get("kind") != "stock_app_install"
    assert "cannot be installed on Community" not in res.text or status == "left_out"
    plan = body["integration_plan"]
    helpdesk = next(i for i in plan["integrations"] if i["module"] == "helpdesk")
    assert helpdesk["status"] == status
