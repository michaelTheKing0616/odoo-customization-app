"""Live Demo Co-Pilot: durable sessions, consent audit, webhook hardening."""

from __future__ import annotations

import base64
import os

os.environ.setdefault("ATTENDEE_ALLOW_MOCK", "true")
os.environ["ATTENDEE_ALLOW_MOCK"] = "true"
os.environ["ATTENDEE_API_KEY"] = ""
os.environ["APP_ENVIRONMENT"] = "development"
os.environ["ATTENDEE_WEBHOOK_SECRET"] = base64.b64encode(b"test-webhook-secret-bytes").decode()

from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.db_models import LiveDemoConsentAudit, LiveDemoCopilotSession, LiveDemoWebhookReceipt
from app.live_demo_copilot import DISCLOSURE_VERSION
from app.live_demo_copilot.webhook_crypto import sign_payload
from app.main import app
from app.settings import settings

settings.attendee_allow_mock = True
settings.attendee_api_key = ""
settings.app_environment = "development"
settings.attendee_webhook_secret = os.environ["ATTENDEE_WEBHOOK_SECRET"]


def _client() -> TestClient:
    init_db()
    return TestClient(app)


def test_disclosure_endpoint() -> None:
    client = _client()
    res = client.get("/api/live-demo-copilot/disclosure")
    assert res.status_code == 200
    body = res.json()
    assert body["version"] == DISCLOSURE_VERSION
    assert body["retention_default"] == "do_not_retain"


def test_whatsapp_rejected() -> None:
    client = _client()
    res = client.post(
        "/api/live-demo-copilot/sessions",
        json={"meeting_url": "https://call.whatsapp.com/xyz", "bot_name": "x"},
    )
    assert res.status_code == 422


def test_launch_blocked_without_consent() -> None:
    client = _client()
    create = client.post(
        "/api/live-demo-copilot/sessions",
        json={"meeting_url": "https://zoom.us/j/1234567890", "bot_name": "Co-Pilot"},
    )
    assert create.status_code == 200
    assert create.json()["meeting_url_hash"]
    sid = create.json()["id"]
    # Durable row exists
    db = SessionLocal()
    try:
        assert db.get(LiveDemoCopilotSession, sid) is not None
    finally:
        db.close()
    launch = client.post(f"/api/live-demo-copilot/sessions/{sid}/launch")
    assert launch.status_code == 403


def test_decline_writes_immutable_audit_and_blocks_launch() -> None:
    client = _client()
    create = client.post(
        "/api/live-demo-copilot/sessions",
        json={"meeting_url": "https://meet.google.com/abc-defg-hij"},
    )
    sid = create.json()["id"]
    consent = client.post(
        f"/api/live-demo-copilot/sessions/{sid}/consent",
        json={
            "disclosure_accepted": False,
            "attendees_notified": False,
            "retention_opt_in": False,
            "disclosure_version": DISCLOSURE_VERSION,
        },
    )
    assert consent.status_code == 200
    assert consent.json()["declined"] is True
    audit = client.get(f"/api/live-demo-copilot/sessions/{sid}/consent-audit")
    assert audit.status_code == 200
    events = audit.json()["events"]
    assert len(events) == 1
    assert events[0]["action"] == "declined"
    assert events[0]["meeting_url_hash"] == create.json()["meeting_url_hash"]
    launch = client.post(f"/api/live-demo-copilot/sessions/{sid}/launch")
    assert launch.status_code == 403


def test_consent_then_mock_launch_transcript_and_purge_on_leave() -> None:
    client = _client()
    create = client.post(
        "/api/live-demo-copilot/sessions",
        json={"meeting_url": "https://zoom.us/j/9876543210", "bot_name": "Co-Pilot"},
    )
    sid = create.json()["id"]
    client.post(
        f"/api/live-demo-copilot/sessions/{sid}/consent",
        json={
            "disclosure_accepted": True,
            "attendees_notified": True,
            "retention_opt_in": False,
            "disclosure_version": DISCLOSURE_VERSION,
        },
    )
    launch = client.post(f"/api/live-demo-copilot/sessions/{sid}/launch")
    assert launch.status_code == 200
    assert launch.json()["mock_mode"] is True
    utter = client.post(
        f"/api/live-demo-copilot/sessions/{sid}/mock-utterance",
        json={"speaker_name": "Client", "text": "Can Odoo do multi-company?"},
    )
    assert utter.status_code == 200
    tr = client.get(f"/api/live-demo-copilot/sessions/{sid}/transcript")
    assert len(tr.json()["lines"]) == 1
    leave = client.post(f"/api/live-demo-copilot/sessions/{sid}/leave")
    assert leave.status_code == 200
    assert leave.json()["bot_state"] == "ended"
    tr2 = client.get(f"/api/live-demo-copilot/sessions/{sid}/transcript")
    assert tr2.json()["lines"] == []


def test_webhook_rejects_bad_signature() -> None:
    client = _client()
    payload = {
        "trigger": "transcript.update",
        "data": {"bot_id": "bot_x", "transcription": "hi", "speaker_name": "A"},
    }
    res = client.post(
        "/api/live-demo-copilot/webhooks/attendee",
        json=payload,
        headers={"X-Webhook-Signature": "not-valid"},
    )
    assert res.status_code == 400


def test_webhook_accepts_valid_signature_and_rejects_replay() -> None:
    client = _client()
    create = client.post(
        "/api/live-demo-copilot/sessions",
        json={"meeting_url": "https://zoom.us/j/1112223334"},
    )
    sid = create.json()["id"]
    client.post(
        f"/api/live-demo-copilot/sessions/{sid}/consent",
        json={
            "disclosure_accepted": True,
            "attendees_notified": True,
            "disclosure_version": DISCLOSURE_VERSION,
        },
    )
    launch = client.post(f"/api/live-demo-copilot/sessions/{sid}/launch")
    bot_id = launch.json()["attendee_bot_id"]
    payload = {
        "trigger": "transcript.update",
        "data": {
            "bot_id": bot_id,
            "transcription": "Does it support Approvals?",
            "speaker_name": "Client",
            "timestamp_ms": 1200,
        },
    }
    sig = sign_payload(payload, settings.attendee_webhook_secret)
    res = client.post(
        "/api/live-demo-copilot/webhooks/attendee",
        json=payload,
        headers={"X-Webhook-Signature": sig},
    )
    assert res.status_code == 200
    assert res.json().get("duplicate") is False
    tr = client.get(f"/api/live-demo-copilot/sessions/{sid}/transcript")
    assert any("Approvals" in L["text"] for L in tr.json()["lines"])
    # Replay
    res2 = client.post(
        "/api/live-demo-copilot/webhooks/attendee",
        json=payload,
        headers={"X-Webhook-Signature": sig},
    )
    assert res2.status_code == 200
    assert res2.json().get("duplicate") is True
    tr2 = client.get(f"/api/live-demo-copilot/sessions/{sid}/transcript")
    assert len(tr2.json()["lines"]) == 1
    db = SessionLocal()
    try:
        assert db.query(LiveDemoWebhookReceipt).count() >= 1
        assert db.query(LiveDemoConsentAudit).filter_by(session_id=sid).count() == 1
    finally:
        db.close()


def test_mock_forbidden_in_production() -> None:
    client = _client()
    settings.app_environment = "production"
    settings.attendee_allow_mock = True
    settings.attendee_api_key = ""
    try:
        create = client.post(
            "/api/live-demo-copilot/sessions",
            json={"meeting_url": "https://zoom.us/j/5556667778"},
        )
        sid = create.json()["id"]
        client.post(
            f"/api/live-demo-copilot/sessions/{sid}/consent",
            json={
                "disclosure_accepted": True,
                "attendees_notified": True,
                "disclosure_version": DISCLOSURE_VERSION,
            },
        )
        launch = client.post(f"/api/live-demo-copilot/sessions/{sid}/launch")
        assert launch.status_code == 503
        assert "production" in launch.json()["detail"].lower() or "Attendee" in launch.json()["detail"]
    finally:
        settings.app_environment = "development"
        settings.attendee_allow_mock = True


def test_bot_status_normalizes_waiting_room_and_fatal() -> None:
    from app.live_demo_copilot.bot_status import bot_status_view

    waiting = bot_status_view("Waiting Room")
    assert waiting.phase == "waiting_room"
    assert waiting.needs_host_action is True
    fatal = bot_status_view("Fatal Error")
    assert fatal.phase == "error"
    assert fatal.is_terminal is True


def test_session_includes_bot_status_and_leave_purge_mock() -> None:
    client = _client()
    create = client.post(
        "/api/live-demo-copilot/sessions",
        json={"meeting_url": "https://zoom.us/j/4445556667"},
    )
    body = create.json()
    assert body["bot_status"]["phase"] == "idle"
    sid = body["id"]
    client.post(
        f"/api/live-demo-copilot/sessions/{sid}/consent",
        json={
            "disclosure_accepted": True,
            "attendees_notified": True,
            "disclosure_version": DISCLOSURE_VERSION,
        },
    )
    launch = client.post(f"/api/live-demo-copilot/sessions/{sid}/launch")
    assert launch.json()["bot_status"]["phase"] == "active"
    leave = client.post(f"/api/live-demo-copilot/sessions/{sid}/leave")
    assert leave.status_code == 200
    assert leave.json()["bot_state"] == "ended"
    # Mock path completes purge inline
    assert leave.json()["leave_purge_status"] == "succeeded"


def test_refresh_status_mock_noop() -> None:
    client = _client()
    create = client.post(
        "/api/live-demo-copilot/sessions",
        json={"meeting_url": "https://zoom.us/j/7778889990"},
    )
    sid = create.json()["id"]
    client.post(
        f"/api/live-demo-copilot/sessions/{sid}/consent",
        json={
            "disclosure_accepted": True,
            "attendees_notified": True,
            "disclosure_version": DISCLOSURE_VERSION,
        },
    )
    client.post(f"/api/live-demo-copilot/sessions/{sid}/launch")
    res = client.post(f"/api/live-demo-copilot/sessions/{sid}/refresh-status")
    assert res.status_code == 200
    assert res.json()["mock_mode"] is True


def test_stage1_triggers_on_odoo_question_not_smalltalk() -> None:
    from app.live_demo_copilot.stage1_filter import stage1_filter

    hit = stage1_filter("Can Odoo do multi-company accounting?")
    assert hit.triggered is True
    assert hit.is_question is True
    miss = stage1_filter("Should we grab lunch after this?")
    assert miss.triggered is False


def test_pipeline_sync_creates_answer_when_ai_off() -> None:
    client = _client()
    create = client.post(
        "/api/live-demo-copilot/sessions",
        json={"meeting_url": "https://zoom.us/j/3213213210"},
    )
    sid = create.json()["id"]
    client.post(
        f"/api/live-demo-copilot/sessions/{sid}/consent",
        json={
            "disclosure_accepted": True,
            "attendees_notified": True,
            "disclosure_version": DISCLOSURE_VERSION,
        },
    )
    client.post(f"/api/live-demo-copilot/sessions/{sid}/launch")
    res = client.post(
        f"/api/live-demo-copilot/sessions/{sid}/run-pipeline-sync",
        json={"text": "Does Odoo support Approvals workflows out of the box?", "speaker_name": "Client"},
    )
    assert res.status_code == 200
    answers = res.json()["answers"]
    assert answers, "expected at least one Stage 1/2 answer"
    top = answers[0]
    assert top["status"] in {"ready", "failed"}
    assert top["confidence"] in {"high", "low"}
    assert isinstance(top["bullets"], list) and len(top["bullets"]) >= 1
    # Small talk should not create another answer
    res2 = client.post(
        f"/api/live-demo-copilot/sessions/{sid}/run-pipeline-sync",
        json={"text": "Nice weather today huh", "speaker_name": "Client"},
    )
    assert len(res2.json()["answers"]) == len(answers)


def test_presenter_speaker_helpers() -> None:
    from app.live_demo_copilot.stage1_filter import is_presenter_speaker, parse_presenter_speakers

    names = parse_presenter_speakers("Fabian Umole, Fabian")
    assert names == ["fabian umole", "fabian"]
    assert is_presenter_speaker("Fabian Umole", names)
    assert is_presenter_speaker("Fabian", names)
    assert not is_presenter_speaker("Client Acme", names)


def test_presenter_speakers_skipped_in_pipeline() -> None:
    client = _client()
    created = client.post(
        "/api/live-demo-copilot/sessions",
        json={
            "meeting_url": "https://zoom.us/j/555111222",
            "bot_name": "Odoo Demo Co-Pilot",
            "presenter_speakers": ["Fabian Umole"],
        },
    )
    assert created.status_code == 200
    sid = created.json()["id"]
    assert created.json()["presenter_speakers"] == ["fabian umole"]

    # consent + mock launch
    assert (
        client.post(
            f"/api/live-demo-copilot/sessions/{sid}/consent",
            json={
                "disclosure_accepted": True,
                "attendees_notified": True,
                "retention_opt_in": False,
                "disclosure_version": DISCLOSURE_VERSION,
            },
        ).status_code
        == 200
    )
    assert client.post(f"/api/live-demo-copilot/sessions/{sid}/launch").status_code == 200

    # Presenter rhetorical Odoo question — must NOT create an answer
    sync = client.post(
        f"/api/live-demo-copilot/sessions/{sid}/run-pipeline-sync",
        json={
            "text": "Can Odoo do multi-company accounting?",
            "speaker_name": "Fabian Umole",
        },
    )
    assert sync.status_code == 200
    assert sync.json()["answers"] == []

    # Client question — should create an answer (AI may be off → still a card)
    sync2 = client.post(
        f"/api/live-demo-copilot/sessions/{sid}/run-pipeline-sync",
        json={
            "text": "Can Odoo do multi-company accounting?",
            "speaker_name": "Client",
        },
    )
    assert sync2.status_code == 200
    assert len(sync2.json()["answers"]) >= 1

    # PATCH update names
    patched = client.patch(
        f"/api/live-demo-copilot/sessions/{sid}/presenter-speakers",
        json={"presenter_speakers": ["Host Lead", "Fabian"]},
    )
    assert patched.status_code == 200
    assert patched.json()["presenter_speakers"] == ["host lead", "fabian"]
