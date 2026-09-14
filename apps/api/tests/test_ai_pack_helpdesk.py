"""Helpdesk ticket pack — must not route to project_tracker."""

from __future__ import annotations

from app.ai_domain_coherence import (
    helpdesk_ticket_intent,
    pack_conflicts_with_brief,
    should_apply_domain_pack,
)
from app.ai_domain_pack_helpdesk import helpdesk_tickets_pack
from app.ai_domain_pack_project_tracker import project_tracker_pack
from app.ai_domain_packs import match_domain_pack, retrieve_domain_pack_lexical
from app.ai_operator_brief import build_operator_brief, stated_residual_kind

HELPDESK_PROMPT = (
    "Helpdesk is Slack screenshots. I want tickets: requester (employee), asset tag, "
    "category (laptop/network/access), priority, description, status draft → in progress "
    "→ waiting → done. Time spent as lines (hours + note), not a second Timesheet app if "
    "we can keep it simple. Don't clone project.task if you're going to dump a fake Project. "
    "We are not selling this as ITSM. Mail chatter on the ticket is important. "
    "One company, two floors, not two companies."
)


def test_helpdesk_pack_has_ticket_and_time_lines() -> None:
    pack = helpdesk_tickets_pack()
    ids = {m["model"] for m in pack["models"] if isinstance(m, dict)}
    assert ids == {"x_ticket", "x_ticket_time_line"}
    ticket = next(m for m in pack["models"] if m["model"] == "x_ticket")
    names = {f["name"] for f in ticket["fields"]}
    assert {
        "x_requester_id",
        "x_asset_tag",
        "x_category",
        "x_priority",
        "x_description",
        "x_status",
        "x_time_line_ids",
    } <= names
    assert ticket.get("mixins") == ["mail.thread", "mail.activity.mixin"]
    assert "project" not in pack.get("depends", [])


def test_helpdesk_prompt_matches_helpdesk_pack_not_project_tracker() -> None:
    assert helpdesk_ticket_intent(HELPDESK_PROMPT)
    matched = match_domain_pack(HELPDESK_PROMPT)
    assert matched is not None
    assert matched[0] == "helpdesk_tickets"
    hit = retrieve_domain_pack_lexical(HELPDESK_PROMPT)
    assert hit is not None
    assert hit[0] == "helpdesk_tickets"


def test_project_tracker_rejected_for_helpdesk_brief() -> None:
    pack = project_tracker_pack()
    conflicts, notes = pack_conflicts_with_brief(HELPDESK_PROMPT, "project_tracker", pack)
    assert conflicts is True
    assert any("helpdesk" in n or "ticket" in n for n in notes)
    ok, gate_notes = should_apply_domain_pack(
        HELPDESK_PROMPT,
        "project_tracker",
        pack,
        retrieval_score=0.49,
        retrieval_method="embedding",
    )
    assert ok is False
    assert gate_notes


def test_helpdesk_brief_names_tickets_residual() -> None:
    kind, text = stated_residual_kind(HELPDESK_PROMPT)
    assert kind == "named"
    assert text == "tickets"
    brief = build_operator_brief(HELPDESK_PROMPT)
    assert brief.custom_residual == "tickets"
    assert brief.capability_path == "residual_app"
    assert "project" in [x.lower() for x in brief.out_of_scope]
    assert "project" not in brief.stock_reuse
    assert "project" in brief.forbidden_bridges
    assert "hr" in brief.stock_reuse


def test_helpdesk_finish_does_not_reattach_project() -> None:
    from app.ai_draft_jobs import _finish_seed_draft
    from app.ai_pipeline import seed_studio_draft

    seed = seed_studio_draft(HELPDESK_PROMPT)
    closed = _finish_seed_draft(HELPDESK_PROMPT, seed, [])
    ids = {str(m.get("model")) for m in (closed.get("models") or []) if isinstance(m, dict)}
    assert "x_ticket" in ids
    assert "project.task" not in ids
    assert "project.project" not in ids
    assert "purchase.order" not in ids
    depends = {str(d) for d in (closed.get("depends") or [])}
    assert "project" not in depends
    assert "purchase" not in depends
    ticket = next(m for m in closed["models"] if m.get("model") == "x_ticket")
    names = {str(f.get("name")) for f in (ticket.get("fields") or []) if isinstance(f, dict)}
    assert "x_requester_id" in names
    assert "x_employee_id" not in names
    assert "x_project_id" not in names
    assert "x_purchase_order_id" not in names
    line = next(m for m in closed["models"] if m.get("model") == "x_ticket_time_line")
    line_names = {str(f.get("name")) for f in (line.get("fields") or []) if isinstance(f, dict)}
    assert "x_hours" in line_names
    assert "x_note" in line_names
    assert "x_status" not in line_names
    preview = ((closed.get("_generation_engine") or {}).get("form_preview"))
    assert preview


def test_helpdesk_scrub_strips_polluted_project_purchase() -> None:
    from app.ai_domain_pack_helpdesk import scrub_helpdesk_prompt_fit

    draft = {
        "domain_pack": "helpdesk_tickets",
        "depends": ["base", "mail", "hr", "project", "purchase"],
        "_user_prompt": HELPDESK_PROMPT,
        "models": [
            {
                "model": "x_ticket",
                "mode": "new",
                "fields": [
                    {"name": "x_requester_id", "ttype": "many2one", "relation": "hr.employee"},
                    {"name": "x_employee_id", "ttype": "many2one", "relation": "hr.employee"},
                    {"name": "x_project_id", "ttype": "many2one", "relation": "project.project"},
                    {"name": "x_purchase_order_id", "ttype": "many2one", "relation": "purchase.order"},
                ],
            },
            {
                "model": "project.task",
                "mode": "inherit",
                "fields": [{"name": "x_ticket_id", "ttype": "many2one", "relation": "x_ticket"}],
            },
            {
                "model": "x_ticket_time_line",
                "fields": [
                    {"name": "x_hours", "ttype": "float"},
                    {"name": "x_status", "ttype": "selection"},
                ],
            },
        ],
        "smart_buttons": [
            {"on_model": "x_ticket", "related_model": "project.task", "label": "Tasks"},
        ],
    }
    notes = scrub_helpdesk_prompt_fit(draft, prompt=HELPDESK_PROMPT)
    assert notes
    ids = {str(m.get("model")) for m in draft["models"] if isinstance(m, dict)}
    assert "project.task" not in ids
    assert "project" not in {str(d) for d in draft["depends"]}
    ticket = next(m for m in draft["models"] if m["model"] == "x_ticket")
    names = {str(f.get("name")) for f in ticket["fields"] if isinstance(f, dict)}
    assert "x_requester_id" in names
    assert "x_employee_id" not in names
    assert "x_project_id" not in names
    line = next(m for m in draft["models"] if m["model"] == "x_ticket_time_line")
    line_names = {str(f.get("name")) for f in line["fields"] if isinstance(f, dict)}
    assert "x_note" in line_names
    assert "x_status" not in line_names
