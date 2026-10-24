"""P0-2-CL5 — named behaviours after test_t6_04_inbox_binding is imported.

Each assertion calls the product. Deleting the behaviour it names fails the
assertion. Importing the inbox-binding module must leave the session database
URL and these results unchanged.
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

_STOCK_PROMPT = "Use stock Odoo apps only for our small business."


def _import_inbox_binding():
    """Import the inbox-binding tests without retargeting the session database.

    A second ``import tests.conftest`` execs that file again and assigns a new
    ingenium_ URL. Read the plugin module already in this process instead.
    """
    import sys

    import tests.test_t6_04_inbox_binding as binding

    session_url = ""
    for mod in sys.modules.values():
        url = getattr(mod, "_B0_ISO_DATABASE_URL", None)
        if isinstance(url, str) and "/ingenium_b0_iso_" in url:
            session_url = url
            break
    assert session_url
    assert os.environ["DATABASE_URL"] == session_url
    return binding


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.db import init_db
    from app.main import app
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", "off")
    monkeypatch.setattr(settings, "ai_intent_llm", "off")
    init_db()
    with TestClient(app) as test_client:
        yield test_client


def _clear_request_context():
    """Drop a leaked intent-LLM override and schema packet. Returns the reset tokens."""
    from app.ai_conversation.intent_llm import set_intent_llm_override, set_schema_packet

    return set_intent_llm_override(None), set_schema_packet(None)


def _reset_request_context(intent, packet) -> None:
    from app.ai_conversation.intent_llm import reset_intent_llm_override, reset_schema_packet

    reset_intent_llm_override(intent)
    reset_schema_packet(packet)


def test_order_wrong_fingerprint_or_hash_is_plan_stale(client: TestClient) -> None:
    """Wrong schema fingerprint or plan hash is 409 plan_stale. A match approves."""
    _import_inbox_binding()
    from app.crypto import encrypt_secret
    from app.db import SessionLocal
    from app.db_models import OdooConnection

    session = SessionLocal()
    try:
        row = OdooConnection(
            name="order-plan-stale",
            url="http://127.0.0.1:8069",
            db_name=f"order-stale-{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
        )
        session.add(row)
        session.commit()
        connection_id = row.id
    finally:
        session.close()

    submitted = client.post(
        "/api/inbox/plans",
        json={
            "connection_id": connection_id,
            "requester_id": "requester",
            "goal": "Add a note",
            "assumptions": ["empty"],
            "environment": "staging",
            "known_models": ["x_m"],
            "changeset": [{"type": "field.create", "params": {"model": "x_m", "name": "x_note"}}],
            "schema_slice": {"models": ["x_m"], "revision": 1},
        },
    )
    assert submitted.status_code == 200, submitted.text
    card = submitted.json()["card"]

    def decide(*, plan_hash: str, schema_fp: str) -> object:
        return client.post(
            f"/api/inbox/plans/{card['plan_hash']}/decide",
            json={
                "connection_id": connection_id,
                "approver_id": "approver",
                "decision": "approve",
                "plan_hash": plan_hash,
                "schema_fp": schema_fp,
            },
        )

    wrong_schema = decide(plan_hash=card["plan_hash"], schema_fp="f" * 64)
    assert wrong_schema.status_code == 409
    assert wrong_schema.json()["detail"]["error"] == "plan_stale"

    wrong_hash = decide(plan_hash="a" * 16, schema_fp=card["schema_fp"])
    assert wrong_hash.status_code == 409
    assert wrong_hash.json()["detail"]["error"] == "plan_stale"

    matched = decide(plan_hash=card["plan_hash"], schema_fp=card["schema_fp"])
    assert matched.status_code == 200, matched.text
    assert matched.json()["card"]["status"] == "approved"


def test_order_other_client_list_is_404_and_viewer_decide_is_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Another client's list is 404. A viewer decide is 403."""
    _import_inbox_binding()
    from app.account_models import User
    from app.account_service import grant_connection_access, hash_password, signup_user
    from app.crypto import encrypt_secret
    from app.db import SessionLocal, init_db
    from app.db_models import OdooConnection
    from app.main import app
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", "accounts")
    init_db()
    db = SessionLocal()
    try:
        owner, workspace, _membership = signup_user(
            db,
            email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
            password="owner-pass-99",
            workspace_name="Order agency",
        )
        owner.email_verified = True
        db.add(owner)
        approver = User(
            email=f"approver-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("approver-pass-99"),
            email_verified=True,
        )
        viewer = User(
            email=f"viewer-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("viewer-pass-99"),
            email_verified=True,
        )
        db.add(approver)
        db.add(viewer)
        db.flush()
        granted = OdooConnection(
            name="Granted client",
            url="http://127.0.0.1:8069",
            db_name=f"granted-{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        other = OdooConnection(
            name="Other client",
            url="http://127.0.0.1:8070",
            db_name=f"other-{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        db.add(granted)
        db.add(other)
        db.flush()
        grant_connection_access(
            db,
            workspace_id=workspace.id,
            connection_id=granted.id,
            user_id=approver.id,
            role="client_approver",
        )
        grant_connection_access(
            db,
            workspace_id=workspace.id,
            connection_id=granted.id,
            user_id=viewer.id,
            role="client_viewer",
        )
        owner_email = owner.email
        approver_email = approver.email
        viewer_email = viewer.email
        granted_id = granted.id
        other_id = other.id
    finally:
        db.close()

    def submit(client: TestClient, connection_id: str, field_name: str) -> dict:
        res = client.post(
            "/api/inbox/plans",
            json={
                "connection_id": connection_id,
                "requester_id": "owner",
                "goal": "Add a note",
                "assumptions": [],
                "environment": "staging",
                "known_models": ["x_m"],
                "changeset": [
                    {"type": "field.create", "params": {"model": "x_m", "name": field_name}}
                ],
            },
        )
        assert res.status_code == 200, res.text
        return res.json()["card"]

    with TestClient(app) as client:
        login_owner = client.post(
            "/api/accounts/login",
            json={"email": owner_email, "password": "owner-pass-99"},
        )
        assert login_owner.status_code == 200, login_owner.text
        granted_card = submit(client, granted_id, "x_note_granted")
        other_card = submit(client, other_id, "x_note_other")
        client.post("/api/accounts/logout")

        login_approver = client.post(
            "/api/accounts/login",
            json={"email": approver_email, "password": "approver-pass-99"},
        )
        assert login_approver.status_code == 200, login_approver.text
        listed = client.get("/api/inbox/plans", params={"connection_id": granted_id})
        assert listed.status_code == 200, listed.text
        plans = listed.json()["plans"]
        assert [row["plan_hash"] for row in plans] == [granted_card["plan_hash"]]
        assert other_card["plan_hash"] not in {row["plan_hash"] for row in plans}

        hidden = client.get("/api/inbox/plans", params={"connection_id": other_id})
        assert hidden.status_code == 404
        assert hidden.status_code != 403
        client.post("/api/accounts/logout")

        login_viewer = client.post(
            "/api/accounts/login",
            json={"email": viewer_email, "password": "viewer-pass-99"},
        )
        assert login_viewer.status_code == 200, login_viewer.text
        viewer_decide = client.post(
            f"/api/inbox/plans/{granted_card['plan_hash']}/decide",
            json={
                "connection_id": granted_id,
                "approver_id": "viewer",
                "decision": "approve",
                "plan_hash": granted_card["plan_hash"],
                "schema_fp": granted_card["schema_fp"],
            },
        )
        assert viewer_decide.status_code == 403


def test_order_low_ir_session_after_inbox_binding_import(client: TestClient) -> None:
    """The stock-only prompt still clarifies after the inbox-binding module imports."""
    _import_inbox_binding()
    intent, packet = _clear_request_context()
    try:
        res = client.post(
            "/api/ai/sessions",
            json={"prompt": _STOCK_PROMPT, "connection_id": None},
        )
    finally:
        _reset_request_context(intent, packet)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "clarifying"
    clarification = body.get("clarification")
    assert clarification is not None
    assert clarification.get("merge_key") == "ir_confidence"
    assert {row.get("id") for row in clarification.get("options") or []} >= {
        "residual_app",
        "stock_first",
    }


@pytest.mark.no_app_db
def test_order_diagnosis_title_strips_management_fluff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vehicle Request keeps its noun after the inbox-binding module imports."""
    _import_inbox_binding()
    from app.ai_conversation.understand import build_understanding
    from app.ai_document_shape import naming_from_residual
    from app.ai_residual_identity import scrub_residual_display_name
    from app.settings import settings
    from tests.test_brief_understanding_class import VEHICLE

    monkeypatch.setattr(settings, "ai_intent_llm", "off")
    intent, packet = _clear_request_context()
    try:
        title = build_understanding(VEHICLE).title
        display, slug = naming_from_residual(VEHICLE)
        scrubbed = scrub_residual_display_name("Fleet Vehicle Request Management")
    finally:
        _reset_request_context(intent, packet)
    assert title == "Vehicle Request"
    assert display == "Vehicle Request"
    assert slug == "vehicle_request"
    assert scrubbed == "Vehicle Request"
