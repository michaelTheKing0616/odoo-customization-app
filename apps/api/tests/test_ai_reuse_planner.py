"""Reuse planner — offline CE-19 allowlist + connection-aware filtering."""

from __future__ import annotations

from app.ai_reuse_planner import apply_reuse_plan, plan_reuse


def test_offline_always_includes_partner_stack() -> None:
    plan = plan_reuse("Build a simple CRM for local shops")
    assert plan.source == "offline_ce19"
    assert "res.partner" in plan.models
    assert "res.users" in plan.models
    assert "res.company" in plan.models
    assert "res.currency" in plan.models
    assert "x_client" in plan.forbid_new_models
    assert any(not d.confirmed for d in plan.decisions)


def test_offline_intent_adds_account_and_calendar() -> None:
    plan = plan_reuse(
        "Law firm with hearings, calendar scheduling, and customer invoicing"
    )
    assert plan.source == "offline_ce19"
    assert "account.move" in plan.models
    assert "calendar.event" in plan.models
    assert "x_invoice" in plan.forbid_new_models
    assert "contacts" in plan.depends
    assert "account" in plan.depends
    assert "calendar" in plan.depends


def test_connection_skips_missing_optional_apps() -> None:
    plan = plan_reuse(
        "Hospital with appointments and invoicing",
        available_models=["res.partner", "res.users", "res.company", "res.currency"],
        installed_modules=["base", "contacts", "mail"],
    )
    assert plan.source == "connection"
    assert "res.partner" in plan.models
    assert "account.move" not in plan.models
    assert "calendar.event" not in plan.models
    assert any("skipped account.move" in n for n in plan.notes)


def test_connection_confirms_via_installed_module() -> None:
    plan = plan_reuse(
        "Fleet billing and invoices",
        available_models=["res.partner"],  # truncated catalog
        installed_modules=["base", "account", "mail"],
    )
    assert plan.source == "connection"
    assert "account.move" in plan.models
    assert all(
        d.confirmed for d in plan.decisions if d.model == "account.move"
    )


def test_operator_reuse_merged() -> None:
    plan = plan_reuse(
        "Simple todo list",
        operator_reuse=["product.product"],
    )
    assert "product.product" in plan.models
    assert any(d.source == "operator" for d in plan.decisions)


def test_apply_collapses_x_client_and_x_invoice() -> None:
    plan = plan_reuse(
        "Law firm management with invoicing and clients",
    )
    draft = {
        "models": [
            {
                "model": "x_matter",
                "is_workflow": True,
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_client_id",
                        "ttype": "many2one",
                        "relation": "x_client",
                    },
                ],
            },
            {
                "model": "x_client",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_invoice",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_payment",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_invoice_id",
                        "ttype": "many2one",
                        "relation": "x_invoice",
                    },
                ],
            },
        ],
        "depends": ["base"],
    }
    notes = apply_reuse_plan(draft, plan)
    ids = {m["model"] for m in draft["models"]}
    assert "x_client" not in ids
    assert "x_invoice" not in ids
    assert "x_matter" in ids
    matter = next(m for m in draft["models"] if m["model"] == "x_matter")
    rels = {f.get("relation") for f in matter["fields"]}
    assert "res.partner" in rels
    payment = next(m for m in draft["models"] if m["model"] == "x_payment")
    inv = next(f for f in payment["fields"] if f["name"] == "x_invoice_id")
    assert inv["relation"] == "account.move"
    assert draft["reuse"]["plan"]["source"] == "offline_ce19"
    assert "contacts" in draft["depends"]
    assert any("collapsed" in n for n in notes)
    # Second apply must not re-emit the connection/offline banner
    notes2 = apply_reuse_plan(draft, plan)
    assert not any(n == "reuse: offline CE-19 allowlist (no connection)" for n in notes2)


def test_apply_collapses_invoice_when_bill_exists_without_accounting() -> None:
    plan = plan_reuse("Simple matter tracker")  # no invoicing intent
    draft = {
        "models": [
            {
                "model": "x_bill",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
            {
                "model": "x_invoice",
                "fields": [{"name": "x_name", "ttype": "char"}],
            },
        ],
        "depends": ["base"],
    }
    apply_reuse_plan(draft, plan)
    ids = {m["model"] for m in draft["models"]}
    assert "x_bill" in ids
    assert "x_invoice" not in ids
