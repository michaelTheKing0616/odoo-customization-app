"""GND-MOD: Job Autopilot plans stock-app installs from the shared map.

Approving the Autopilot plan is the confirm, so the plan states the shared
'why' sentence for each install and never plans an Enterprise-only app.
"""

from __future__ import annotations

import pytest

from app.job_autopilot import planner
from app.job_autopilot.planner import build_job_packet
from app.stock_app_install import (
    InstallFacts,
    StockAppMatch,
    match_stock_apps,
    proposal_for,
    stock_app_for_model,
)

pytestmark = pytest.mark.no_app_db


def _community_packet():
    from app.live_schema_context import SchemaPacket

    return SchemaPacket(server_version="19.0", major=19, modules=(), models={})


def _shared_reason(model: str, noun: str) -> str:
    app = stock_app_for_model(model)
    assert app is not None
    proposal = proposal_for(
        StockAppMatch(app=app, model=model, noun=noun),
        InstallFacts(model_present=False, module_state="uninstalled"),
    )
    assert proposal is not None
    return proposal.reason


def test_planner_vocabulary_resolves_modules_through_shared_map() -> None:
    assert not hasattr(planner, "_PLANNER_MODULE_SIGNALS")
    for _, model in planner._PLANNER_MODEL_SIGNALS:
        assert stock_app_for_model(model) is not None, model


def test_quotation_request_plans_sale_with_shared_why_sentence() -> None:
    packet = build_job_packet("We send quotations to customers.", use_llm=False)

    assert "sale" in packet.stock_apps
    reason = _shared_reason("sale.order", "quotations")
    assert reason == "Sales is not installed, so there is no quotation to put this on yet."
    assert f"Install Sales (sale): {reason}" in packet.decision_record


def test_helpdesk_request_plans_no_install_and_explains(monkeypatch: pytest.MonkeyPatch) -> None:
    # Confirmed Community: Enterprise apps are still dropped and explained.
    monkeypatch.setattr(planner, "_packet_edition", lambda _packet: ("community", {}))
    packet = build_job_packet("Our team answers helpdesk tickets.", use_llm=False)

    assert "helpdesk" not in packet.stock_apps
    explanation = (
        "Your request edits helpdesk tickets, which come from Helpdesk. "
        "Helpdesk is an Odoo Enterprise app, so it cannot be installed on Community. "
        "Helpdesk is not in Odoo Community, so there is no helpdesk ticket to change here."
    )
    assert explanation in packet.warnings
    assert f"No install planned. {explanation}" in packet.decision_record
    assert not any(line.startswith("Install Helpdesk") for line in packet.decision_record)


def test_enterprise_module_from_another_source_is_dropped_with_explanation() -> None:
    keep, why, notes = planner._stock_app_plan(
        "run the shop", ["mail", "helpdesk", "sale"], _community_packet()
    )

    assert keep == ["mail", "sale"]
    assert why == [f"Install Sales (sale): {_shared_reason('sale.order', 'quotations')}"]
    assert len(notes) == 1 and "Helpdesk is an Odoo Enterprise app" in notes[0]


def test_longer_phrase_wins_across_apps() -> None:
    modules = [m.app.module for m in match_stock_apps("Customize POS orders and invoices")]

    assert modules == ["point_of_sale", "account"]


def test_generic_shared_map_words_do_not_widen_inferred_apps() -> None:
    packet = build_job_packet(
        "We log each transfer of crew between rigs.",
        use_llm=False,
    )

    assert "stock" not in packet.stock_apps
