"""AiSession API + refinement orchestrator."""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.ai_conversation.refine import apply_refinement, artifact_hash  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _sample_draft() -> dict:
    return {
        "models": [
            {
                "model": "x_rental",
                "name": "Rental",
                "fields": [
                    {"name": "x_deposit", "string": "Deposit", "type": "float", "required": False},
                    {"name": "x_name", "string": "Name", "type": "char", "required": True},
                ],
            }
        ],
        "_user_prompt": "Car rental with deposit",
    }


def test_refinement_makes_one_field_required() -> None:
    draft = _sample_draft()
    before = json.dumps(draft, sort_keys=True)
    result = apply_refinement(draft, "make the deposit field required")
    assert result["ok"] is True
    patched = result["draft"]
    dep = next(f for f in patched["models"][0]["fields"] if f["name"] == "x_deposit")
    assert dep["required"] is True
    assert result["highlighted_field_ids"] == ["x_rental.x_deposit"]
    assert before != json.dumps(patched, sort_keys=True)


def test_refinement_removes_priority_on_ticket() -> None:
    draft = {
        "models": [
            {
                "model": "x_ticket",
                "fields": [
                    {"name": "x_name", "string": "Subject", "ttype": "char"},
                    {"name": "x_priority", "string": "Priority", "ttype": "selection"},
                ],
            }
        ],
        "_user_prompt": "Helpdesk tickets",
    }
    result = apply_refinement(draft, "remove priority ticket")
    assert result["ok"] is True
    names = {f["name"] for f in result["draft"]["models"][0]["fields"]}
    assert "x_priority" not in names
    assert "x_name" in names
    assert "x_ticket.x_priority" in result["highlighted_field_ids"]


def test_refinement_unmapped_hints_come_from_this_draft() -> None:
    result = apply_refinement(_sample_draft(), "paint it blue")
    assert result["ok"] is False
    err = str(result.get("error") or "")
    assert "deposit field required" not in err.lower()
    assert "Deposit" in err or "Name" in err


def _ticket_draft() -> dict:
    return {
        "models": [
            {
                "model": "x_ticket",
                "is_workflow": True,
                "state_field": {
                    "field": "x_status",
                    "states": ["draft", "in_progress", "done"],
                },
                "fields": [
                    {"name": "x_name", "string": "Subject", "ttype": "char"},
                    {"name": "x_priority", "string": "Priority", "ttype": "selection"},
                    {
                        "name": "x_status",
                        "string": "Status",
                        "ttype": "selection",
                        "required": True,
                    },
                    {"name": "x_category", "string": "Category", "ttype": "selection"},
                ],
            }
        ],
        "_user_prompt": "Helpdesk tickets",
    }


def test_refinement_restores_asset_tag_not_extra() -> None:
    draft = {
        "models": [
            {
                "model": "x_ticket",
                "fields": [
                    {"name": "x_name", "string": "Subject", "ttype": "char"},
                    {"name": "x_asset_tag", "string": "Asset Tag", "ttype": "char"},
                ],
            }
        ],
        "_user_prompt": "Helpdesk tickets with asset tag",
    }
    removed = apply_refinement(draft, "remove the Asset Tag ticket")
    assert removed["ok"] is True
    names = {f["name"] for f in removed["draft"]["models"][0]["fields"]}
    assert "x_asset_tag" not in names
    restored = apply_refinement(removed["draft"], "restore the Asset Tag ticket")
    assert restored["ok"] is True
    ticket = restored["draft"]["models"][0]
    by_name = {f["name"]: f for f in ticket["fields"]}
    assert "x_asset_tag" in by_name
    assert by_name["x_asset_tag"]["string"] == "Asset Tag"
    assert "Extra" not in {f.get("string") for f in ticket["fields"]}
    assert "x_extra" not in by_name


def test_refinement_blank_add_field_is_ignored() -> None:
    from app.ai_conversation.refine import apply_ops

    draft = _ticket_draft()
    summaries, _ = apply_ops(draft, [{"op": "add_field", "model": "x_ticket"}])
    assert summaries == []
    names = {f["name"] for f in draft["models"][0]["fields"]}
    assert "x_extra" not in names
    result = apply_refinement(_ticket_draft(), "Remove Status")
    assert result["ok"] is True
    ticket = result["draft"]["models"][0]
    names = {f["name"] for f in ticket["fields"]}
    assert "x_status" not in names
    assert "x_name" in names
    assert ticket.get("is_workflow") is False
    assert not ticket.get("state_field")


def test_refinement_natural_phrases_hit_catalog_fields() -> None:
    for phrase in (
        "get rid of the status field",
        "we don't need Status",
        "drop Category",
        "make Subject required",
        "hide Priority",
        "rename Priority to Urgency",
    ):
        result = apply_refinement(_ticket_draft(), phrase)
        assert result["ok"] is True, phrase


def test_refinement_production_nl_verbs_typos_undo_and_lists() -> None:
    from app.ai_conversation.refine import classify_intent

    draft = _ticket_draft()
    draft["models"][0]["fields"].extend(
        [
            {"name": "x_partner_id", "string": "Contact", "ttype": "many2one"},
            {"name": "x_reference", "string": "Reference", "ttype": "char"},
        ]
    )
    messy = (
        "can you please remvoe the priorty thanks",
        "yeet Category",
        "without the contact field",
        "pls ditch status",
        "take off Priority",
        "I don't need the reference",
    )
    for phrase in messy:
        intent = classify_intent(phrase)
        assert intent is not None, phrase
        assert intent.verb == "remove", (phrase, intent)
        result = apply_refinement(draft, phrase)
        assert result["ok"] is True, phrase

    both = apply_refinement(draft, "remove priority and category")
    assert both["ok"] is True
    names = {f["name"] for f in both["draft"]["models"][0]["fields"]}
    assert "x_priority" not in names
    assert "x_category" not in names

    gone = apply_refinement(draft, "drop Priority")
    undid = apply_refinement(gone["draft"], "oops")
    assert undid["ok"] is True
    restored_names = {f["name"] for f in undid["draft"]["models"][0]["fields"]}
    assert "x_priority" in restored_names

    tagged = apply_refinement(draft, "remove Status")
    put_back = apply_refinement(tagged["draft"], "put it back")
    assert put_back["ok"] is True
    assert "x_status" in {f["name"] for f in put_back["draft"]["models"][0]["fields"]}

    typo_restore = apply_refinement(gone["draft"], "restroe the priorty")
    assert typo_restore["ok"] is True
    assert "x_priority" in {f["name"] for f in typo_restore["draft"]["models"][0]["fields"]}

    required = apply_refinement(draft, "can you make the subject field mandatory")
    assert required["ok"] is True
    subject = next(f for f in required["draft"]["models"][0]["fields"] if f["name"] == "x_name")
    assert subject.get("required") is True

    added = apply_refinement(draft, "please add a required due date on the ticket")
    assert added["ok"] is True
    assert any(f.get("name") == "x_due_date" for f in added["draft"]["models"][0]["fields"])


def test_refinement_compound_remove_extra_and_restore_asset_tag() -> None:
    draft = {
        "models": [
            {
                "model": "x_ticket",
                "fields": [
                    {"name": "x_name", "string": "Subject", "ttype": "char"},
                    {"name": "x_extra", "string": "Extra", "ttype": "char"},
                ],
            }
        ],
        "_refine_removed_fields": [
            {
                "model": "x_ticket",
                "field": {
                    "name": "x_asset_tag",
                    "string": "Asset Tag",
                    "ttype": "char",
                },
            }
        ],
        "_user_prompt": "Helpdesk tickets with asset tag",
    }
    for phrase in (
        "Remove the Extra and restore the Asset Tag ticket",
        "remove Extra, restore Asset Tag",
        "drop Extra then bring back the Asset Tag",
    ):
        result = apply_refinement(draft, phrase)
        assert result["ok"] is True, phrase
        by_name = {f["name"]: f for f in result["draft"]["models"][0]["fields"]}
        assert "x_extra" not in by_name, phrase
        assert "x_asset_tag" in by_name, phrase
        assert by_name["x_asset_tag"]["string"] == "Asset Tag"
        assert "Removed Extra" in result["patch_summary"]
        assert "Asset Tag" in result["patch_summary"]


def test_refinement_click_undo_uses_same_restore_text() -> None:
    """History Undo for older turns sends inverted restore/remove, not a new op set."""
    draft = _ticket_draft()
    gone = apply_refinement(draft, "remove Priority")
    assert gone["ok"] is True
    restored = apply_refinement(gone["draft"], "restore Priority")
    assert restored["ok"] is True
    assert "x_priority" in {f["name"] for f in restored["draft"]["models"][0]["fields"]}

    added = apply_refinement(draft, "add a due date")
    assert added["ok"] is True
    stripped = apply_refinement(added["draft"], "remove a due date")
    assert stripped["ok"] is True
    assert "x_due_date" not in {f["name"] for f in stripped["draft"]["models"][0]["fields"]}

    compound = apply_refinement(
        {
            "models": [
                {
                    "model": "x_ticket",
                    "fields": [
                        {"name": "x_name", "string": "Subject", "ttype": "char"},
                        {"name": "x_extra", "string": "Extra", "ttype": "char"},
                    ],
                }
            ],
            "_refine_removed_fields": [
                {
                    "model": "x_ticket",
                    "field": {"name": "x_asset_tag", "string": "Asset Tag", "ttype": "char"},
                }
            ],
        },
        "Remove the Extra and restore the Asset Tag ticket",
    )
    undid = apply_refinement(
        compound["draft"],
        "restore the Extra and remove the Asset Tag ticket",
    )
    assert undid["ok"] is True
    by_name = {f["name"]: f for f in undid["draft"]["models"][0]["fields"]}
    assert "x_extra" in by_name
    assert "x_asset_tag" not in by_name


def test_refinement_compound_add_then_require() -> None:
    result = apply_refinement(
        _ticket_draft(), "add a due date and make it required"
    )
    assert result["ok"] is True
    due = next(f for f in result["draft"]["models"][0]["fields"] if f["name"] == "x_due_date")
    assert due.get("required") is True


def test_refinement_llm_fallback_applies_allowlisted_ops() -> None:
    from app.llm_provider import MockLLMProvider

    provider = MockLLMProvider(
        json_response=(
            '{"ops":[{"op":"remove_field","model":"x_ticket","field":"x_category"}],'
            '"summary":"Removed Category."}'
        )
    )
    result = apply_refinement(
        _ticket_draft(),
        "the classification column is noise",
        provider=provider,
    )
    assert result["ok"] is True
    names = {f["name"] for f in result["draft"]["models"][0]["fields"]}
    assert "x_category" not in names


def test_create_session_blocks_low_ir(client: TestClient) -> None:
    res = client.post(
        "/api/ai/sessions",
        json={
            "prompt": "Use stock Odoo apps only for our small business.",
            "connection_id": None,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "clarifying"
    assert body.get("clarification") is not None


def test_markup_session_requires_diagnosis_confirm(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import settings as api_settings

    api_settings.ai_intent_llm = "off"
    prompt = (
        'The Client wants a "Mark-up" line added to every Sale they make. '
        "A Witholding Tax on the markup only, and only for Sales, NOT Purchases. "
        "Choose the percent between 10 and 25 at the time of entry."
    )
    create = client.post("/api/ai/sessions", json={"prompt": prompt, "connection_id": None})
    assert create.status_code == 200
    body = create.json()
    assert body["status"] == "clarifying"
    clarify = body.get("clarification") or {}
    assert clarify.get("kind") == "diagnosis" or clarify.get("merge_key") == "diagnosis"
    assert (clarify.get("understanding") or {}).get("host_model") == "sale.order"
    sid = body["id"]
    confirm = client.post(
        f"/api/ai/sessions/{sid}/clarify",
        json={"merge_key": "diagnosis", "answer_id": "confirm", "answer_text": "Yes — build this"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "ready"
    assert "Diagnosis (locked)" in (confirm.json().get("prompt_resolved") or "")
    res = client.post(
        "/api/ai/sessions",
        json={
            "prompt": "Use stock Odoo apps only for our small business.",
            "connection_id": None,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "clarifying"
    assert body.get("clarification") is not None


def test_session_crud_and_resume_hash(client: TestClient) -> None:
    draft = _sample_draft()
    ahash = artifact_hash(draft)
    create = client.post(
        "/api/ai/sessions",
        json={"prompt": "Car rental with deposit field", "connection_id": None},
    )
    assert create.status_code == 200
    sid = create.json()["id"]

    db = SessionLocal()
    try:
        from app.ai_conversation.session_store import get_session, update_session

        row = get_session(db, sid)
        assert row is not None
        update_session(db, row, artifact=draft, artifact_hash=ahash, status="review")
    finally:
        db.close()

    got = client.get(f"/api/ai/sessions/{sid}")
    assert got.status_code == 200
    assert got.json()["artifact_consistent"] is True

    refine = client.post(
        f"/api/ai/sessions/{sid}/refine",
        json={"instruction": "make the deposit field required"},
    )
    assert refine.status_code == 200
    assert refine.json()["ok"] is True


def test_build_draft_job_kwargs_includes_run_body_fields() -> None:
    from inspect import signature

    from app.ai_draft_jobs import build_draft_job_kwargs, run_draft_job_body

    kwargs = build_draft_job_kwargs(
        prompt="Clinic booking",
        connection_id="conn-1",
        available_models=["res.partner"],
        installed_modules=["base"],
        stock_catalog=[],
    )
    params = signature(run_draft_job_body).parameters
    skip = {"job_id", "db_factory", "client"}
    for name in params:
        if name in skip:
            continue
        assert name in kwargs, f"missing {name}"


def test_sync_job_loads_background_job_into_review(client: TestClient) -> None:
    """Regression: sync-job must use BackgroundJob/get_job — not a missing Job model."""
    from app.db_models import BackgroundJob
    from app.ai_conversation.session_store import get_session, update_session

    create = client.post(
        "/api/ai/sessions",
        json={"prompt": "Helpdesk tickets with requester and status workflow", "connection_id": None},
    )
    assert create.status_code == 200
    sid = create.json()["id"]
    draft = _sample_draft()

    db = SessionLocal()
    try:
        job = BackgroundJob(
            id="job-sync-test-1",
            kind="ai_draft",
            status="succeeded",
            result_json=json.dumps({"ok": True, "draft": draft}),
        )
        db.add(job)
        db.commit()
        row = get_session(db, sid)
        assert row is not None
        update_session(db, row, status="generating", job_id=job.id)
    finally:
        db.close()

    synced = client.post(f"/api/ai/sessions/{sid}/sync-job")
    assert synced.status_code == 200, synced.text
    body = synced.json()
    assert body["status"] == "review"
    assert body["artifact"]["models"][0]["model"] == "x_rental"


def test_mock_llm_provider_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.llm_provider import MockLLMProvider, get_llm_provider_for_tier
    from app.settings import settings

    settings.ai_llm_tier_fast = "mock"
    provider = get_llm_provider_for_tier("fast")
    assert isinstance(provider, MockLLMProvider)
    assert provider.generate_text("hello") == MockLLMProvider().generate_text("hello")
