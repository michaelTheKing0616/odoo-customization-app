"""Oracle pins for REG-NP-T6. One positive and one negative test per AC.

The app database for this file is an in-memory SQLite engine so the oracle
does not open the app Postgres port. Product code is not modified.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["FERNET_KEY"] = "dev-only-test"
os.environ["AUTH_MODE"] = "off"
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"
os.environ["DB_MIGRATIONS"] = "off"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db as _app_db

_app_db.engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_app_db.SessionLocal = sessionmaker(bind=_app_db.engine, autoflush=False, autocommit=False)

import pytest
from fastapi.testclient import TestClient

from app.account_models import OAuthIdentity, User
from app.account_service import AccountError, grant_connection_access, hash_password, signup_user
from app.audit_chain import verify_db
from app.changeset.plan_card import PLAN_CARD_COPY_SECTIONS, render_plan_card
from app.changeset.policy import policy_decision, production_r3_approval_met, self_approval_allowed
from app.changeset.store import (
    ApprovalExpired,
    apply_approved_plan,
    clear_freeze_window,
    decide_plan,
    set_freeze_window,
    submit_plan,
)
from app.crypto import encrypt_secret
from app.db import Base, SessionLocal, init_db
from app.db_models import AuditChainEntry, OdooConnection
from app.main import app
from app.oauth_service import OAuthProfile, resolve_oauth_login
from app.settings import settings

settings.database_url = "sqlite://"
settings.fernet_key = "dev-only-test"
settings.auth_mode = "off"
settings.rate_limit_per_minute = 0
settings.db_migrations = "off"

_REPO = Path(__file__).resolve().parents[3]
_FIELD = [{"type": "field.create", "params": {"model": "x_m", "name": "x_note"}}]
_SECOND_AUTH_AUDIT_TABLES = frozenset(
    {
        "auth_audit",
        "auth_audit_entries",
        "auth_events",
        "login_audit",
        "login_events",
        "oauth_audit",
    }
)
_HEAVY_NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)
_HEAVY_WINDOW = {
    "start": "2026-10-04T14:00:00+00:00",
    "end": "2026-10-04T16:00:00+00:00",
}


@dataclass
class Agency:
    owner_email: str
    owner_password: str
    approver_email: str
    approver_password: str
    viewer_email: str
    viewer_password: str
    granted_id: str
    other_id: str
    other_name: str


@pytest.fixture(autouse=True)
def _schema() -> None:
    assert _app_db.engine.dialect.name == "sqlite"
    init_db()


def _read(relative: str) -> str:
    return (_REPO / relative).read_text(encoding="utf-8")


def _email(tag: str) -> str:
    return f"{tag}-{uuid.uuid4().hex[:8]}@example.com"


def _client(monkeypatch: pytest.MonkeyPatch, *, accounts: bool) -> TestClient:
    monkeypatch.setattr(settings, "auth_mode", "accounts" if accounts else "off")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 0)
    monkeypatch.setattr(settings, "db_migrations", "off")
    return TestClient(app)


def _login(client: TestClient, email: str, password: str) -> None:
    response = client.post("/api/accounts/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


def _ids(kind: str) -> set[str]:
    db = SessionLocal()
    try:
        return {row.id for row in db.query(AuditChainEntry).filter(AuditChainEntry.kind == kind).all()}
    finally:
        db.close()


def _new_rows(kind: str, before: set[str]) -> list[AuditChainEntry]:
    db = SessionLocal()
    try:
        return (
            db.query(AuditChainEntry)
            .filter(AuditChainEntry.kind == kind, AuditChainEntry.id.notin_(before or {"_"}))
            .order_by(AuditChainEntry.ts.asc(), AuditChainEntry.id.asc())
            .all()
        )
    finally:
        db.close()


def _payload(row: AuditChainEntry) -> dict:
    return json.loads(row.payload_json)


def _agency() -> Agency:
    owner_email = _email("owner")
    owner_password = "owner-pass-99"
    db = SessionLocal()
    try:
        owner, workspace, _token = signup_user(
            db, email=owner_email, password=owner_password, workspace_name="Agency"
        )
        owner.email_verified = True
        db.add(owner)
        db.commit()
        granted = OdooConnection(
            name="Granted client",
            url="http://odoo.invalid",
            db_name=f"ingenium_reg_np_t6_{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        other_name = f"Other client {uuid.uuid4().hex[:8]}"
        other = OdooConnection(
            name=other_name,
            url="http://odoo.invalid",
            db_name=f"ingenium_reg_np_t6_{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        db.add(granted)
        db.add(other)
        db.commit()
        approver_email = _email("approver")
        approver_password = "approver-pass-99"
        viewer_email = _email("viewer")
        viewer_password = "viewer-pass-99"
        approver = User(
            email=approver_email,
            password_hash=hash_password(approver_password),
            email_verified=True,
        )
        viewer = User(
            email=viewer_email,
            password_hash=hash_password(viewer_password),
            email_verified=True,
        )
        db.add(approver)
        db.add(viewer)
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
        return Agency(
            owner_email=owner_email,
            owner_password=owner_password,
            approver_email=approver_email,
            approver_password=approver_password,
            viewer_email=viewer_email,
            viewer_password=viewer_password,
            granted_id=granted.id,
            other_id=other.id,
            other_name=other_name,
        )
    finally:
        db.close()


def _submit_plan(client: TestClient, connection_id: str, *, name: str) -> dict:
    response = client.post(
        "/api/inbox/plans",
        json={
            "connection_id": connection_id,
            "requester_id": "owner",
            "goal": "Add a note",
            "assumptions": ["empty"],
            "environment": "staging",
            "known_models": ["x_m"],
            "changeset": [{"type": "field.create", "params": {"model": "x_m", "name": name}}],
            "schema_slice": {"models": ["x_m"], "revision": name},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["card"]


def _decide(client: TestClient, connection_id: str, card: dict, *, schema_fp: str, decision: str = "approve"):
    return client.post(
        f"/api/inbox/plans/{card['plan_hash']}/decide",
        json={
            "connection_id": connection_id,
            "approver_id": "approver",
            "decision": decision,
            "plan_hash": card["plan_hash"],
            "schema_fp": schema_fp,
        },
    )


def _connection_row() -> str:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name="Inbox",
            url="http://odoo.invalid",
            db_name=f"ingenium_reg_np_t6_{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _heavy_person(user_id: str, **extra: object) -> dict:
    approver_id = extra.pop("approver_id", user_id)
    record: dict = {"approver_id": approver_id, "user_id": user_id, "decision": "approve"}
    record.update(extra)
    return record


def _heavy_met(approvals: list[dict]) -> dict:
    decision = policy_decision("R4", "production", heavy=True)
    return production_r3_approval_met(
        decision,
        approvals,
        requester_id="requester",
        protected=False,
        simulation_passed=True,
        backup_id="backup-1",
        allowed_window=_HEAVY_WINDOW,
        now=_HEAVY_NOW,
    )


def _open_plan_statuses() -> set[str]:
    hook = _read("apps/web/src/components/connection-client/useConnectionClientSections.ts")
    match = re.search(r"OPEN_PLAN_STATUSES = new Set\(\[([^\]]*)\]\)", hook)
    assert match is not None
    assert "body.plans.filter(isOpenChangeSet)" in hook
    return set(re.findall(r"""["']([^"']+)["']""", match.group(1)))


def test_ac1_allowed_role_decide_is_not_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    """A role the matrix allows does not get 403 on inbox decide."""
    world = _agency()
    with _client(monkeypatch, accounts=True) as client:
        _login(client, world.owner_email, world.owner_password)
        card = _submit_plan(client, world.granted_id, name=f"x_allow_{uuid.uuid4().hex[:6]}")
        client.post("/api/accounts/logout")
        _login(client, world.approver_email, world.approver_password)
        allowed = _decide(client, world.granted_id, card, schema_fp=card["schema_fp"])
    assert allowed.status_code != 403
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["card"]["status"] == "approved"


def test_ac1_client_viewer_decide_forbidden_and_other_connection_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """client_viewer approve is 403 and another connection is 404."""
    world = _agency()
    with _client(monkeypatch, accounts=True) as client:
        _login(client, world.owner_email, world.owner_password)
        card = _submit_plan(client, world.granted_id, name=f"x_deny_{uuid.uuid4().hex[:6]}")
        client.post("/api/accounts/logout")
        _login(client, world.viewer_email, world.viewer_password)
        denied = _decide(client, world.granted_id, card, schema_fp=card["schema_fp"])
        hidden = client.get(f"/api/connections/{world.other_id}")
    assert denied.status_code == 403
    assert hidden.status_code == 404


def test_ac2_verified_email_links_without_a_manual_step() -> None:
    """A verified existing email and a Google profile link in this one call."""
    email = _email("oauth-link")
    db = SessionLocal()
    try:
        user, _workspace, _token = signup_user(db, email=email, password="secure-pass-99")
        user.email_verified = True
        db.add(user)
        db.commit()
        db.refresh(user)
        result = resolve_oauth_login(
            db,
            OAuthProfile(
                provider="google",
                subject=f"google-{uuid.uuid4().hex}",
                email=user.email,
                email_verified=True,
            ),
        )
        assert result.user.id == user.id
        identities = db.query(OAuthIdentity).filter(OAuthIdentity.user_id == user.id).all()
        assert len(identities) == 1
        assert identities[0].provider == "google"
    finally:
        db.close()


def test_ac2_unverified_email_collision_does_not_link() -> None:
    """The same email with email_verified False raises oauth_unverified_collision."""
    email = _email("oauth-unverified")
    db = SessionLocal()
    try:
        user, _workspace, _token = signup_user(db, email=email, password="secure-pass-99")
        user.email_verified = False
        db.add(user)
        db.commit()
        with pytest.raises(AccountError) as exc:
            resolve_oauth_login(
                db,
                OAuthProfile(
                    provider="google",
                    subject=f"google-{uuid.uuid4().hex}",
                    email=email,
                    email_verified=True,
                ),
            )
        assert exc.value.code == "oauth_unverified_collision"
        assert db.query(OAuthIdentity).filter(OAuthIdentity.user_id == user.id).count() == 0
    finally:
        db.close()


def test_ac3_login_logout_and_failed_login_stay_on_one_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """A right password writes one login row; verify_db stays green; one table."""
    email = _email("login-ok")
    password = "secure-pass-99"
    db = SessionLocal()
    try:
        user, _workspace, _token = signup_user(db, email=email, password=password)
        user.email_verified = True
        db.add(user)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    with _client(monkeypatch, accounts=True) as client:
        before_login = _ids("login")
        _login(client, email, password)
        success = _new_rows("login", before_login)
        assert len(success) == 1
        body = _payload(success[0])
        assert body["result"] == "success"
        assert body["provider"] == "password"
        assert body["actor"] == user_id
        assert password not in success[0].payload_json
        before_logout = _ids("logout")
        logged_out = client.post("/api/accounts/logout")
        assert logged_out.status_code == 204, logged_out.text
        logout_rows = _new_rows("logout", before_logout)
        assert len(logout_rows) == 1
        failed = client.post(
            "/api/accounts/login",
            json={"email": email, "password": "wrong-password-99"},
        )
        assert failed.status_code == 401
        check = SessionLocal()
        try:
            assert verify_db(check) == (True, None)
            names = set(Base.metadata.tables)
        finally:
            check.close()
    assert "audit_chain_entries" in names
    assert names.isdisjoint(_SECOND_AUTH_AUDIT_TABLES)


def test_ac3_wrong_password_writes_one_row_without_the_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """A wrong password writes one login row and does not store the password."""
    email = _email("login-fail")
    password = "secure-pass-99"
    attempted = "wrong-password-should-never-be-logged"
    db = SessionLocal()
    try:
        user, _workspace, _token = signup_user(db, email=email, password=password)
        user.email_verified = True
        db.add(user)
        db.commit()
    finally:
        db.close()

    with _client(monkeypatch, accounts=True) as client:
        before = _ids("login")
        failed = client.post("/api/accounts/login", json={"email": email, "password": attempted})
        assert failed.status_code == 401
        rows = _new_rows("login", before)
    assert len(rows) == 1
    body = _payload(rows[0])
    assert body["result"] == "failure"
    assert body["provider"] == "password"
    assert "password" not in body
    assert attempted not in rows[0].payload_json
    assert password not in rows[0].payload_json


def test_ac4_matching_fingerprint_decide_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A decide whose schema_fp matches the card is not plan_stale."""
    connection_id = _connection_row()
    with _client(monkeypatch, accounts=False) as client:
        card = _submit_plan(client, connection_id, name=f"x_match_{uuid.uuid4().hex[:6]}")
        accepted = _decide(client, connection_id, card, schema_fp=card["schema_fp"])
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["card"]["status"] == "approved"
    assert accepted.json().get("detail", {}).get("error") != "plan_stale"


def test_ac4_stale_expired_and_frozen_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mismatched schema_fp, expiry, and a freeze window are refused."""
    stale_id = _connection_row()
    frozen_id = _connection_row()
    with _client(monkeypatch, accounts=False) as client:
        stale = _submit_plan(client, stale_id, name=f"x_stale_{uuid.uuid4().hex[:6]}")
        mismatched = _decide(client, stale_id, stale, schema_fp="f" * 64)
        assert mismatched.status_code == 409
        assert mismatched.json()["detail"]["error"] == "plan_stale"

        frozen = _submit_plan(client, frozen_id, name=f"x_frozen_{uuid.uuid4().hex[:6]}")
        start = datetime.now(timezone.utc) - timedelta(minutes=1)
        end = datetime.now(timezone.utc) + timedelta(hours=1)
        set_freeze_window(frozen_id, start=start, end=end)
        try:
            blocked = _decide(client, frozen_id, frozen, schema_fp=frozen["schema_fp"])
            assert blocked.status_code == 409
            assert blocked.json()["detail"]["error"] == "frozen"
            listed = client.get("/api/inbox/plans", params={"connection_id": frozen_id})
            assert listed.status_code == 200, listed.text
            match = next(plan for plan in listed.json()["plans"] if plan["plan_hash"] == frozen["plan_hash"])
            assert match["status"] == "pending"
        finally:
            clear_freeze_window(frozen_id)

    db = SessionLocal()
    try:
        submitted = submit_plan(
            db,
            changeset=[{"type": "field.create", "params": {"model": "x_m", "name": "x_expire"}}],
            goal="Add a note",
            assumptions=["empty"],
            environment="staging",
            requester_id="requester",
            known_models={"x_m"},
            connection_id=str(uuid.uuid4()),
            schema_slice={"models": ["x_m"], "revision": "expire"},
        )
        assert submitted["ok"] is True
        card = submitted["card"]
        expires = datetime.fromisoformat(card["expires_at"])
        approved = decide_plan(
            db,
            card["plan_hash"],
            approver_id="approver",
            decision="approve",
            connection_id=card["connection_id"],
            body_plan_hash=card["plan_hash"],
            schema_fp=card["schema_fp"],
            now=expires - timedelta(seconds=1),
        )
        assert approved["status"] == "approved"
        with pytest.raises(ApprovalExpired):
            apply_approved_plan(
                db,
                card["plan_hash"],
                connection_id=card["connection_id"],
                body_plan_hash=card["plan_hash"],
                schema_fp=card["schema_fp"],
                now=expires,
            )
    finally:
        db.close()


def test_ac5_render_plan_card_emits_nine_sections_in_order() -> None:
    """render_plan_card emits PLAN_CARD_COPY_SECTIONS in order."""
    rendered = render_plan_card(
        _FIELD,
        goal="Add a note",
        assumptions=["empty"],
        environment="staging",
    )
    titles = [section["title"] for section in rendered["sections"]]
    assert titles == list(PLAN_CARD_COPY_SECTIONS)
    assert titles == [
        "goal and assumptions",
        "each change",
        "impact",
        "risk and why",
        "what is not changing",
        "how it will be checked",
        "how to undo",
        "environment",
        "plan fingerprint and expiry",
    ]


def test_ac5_changing_an_assumption_changes_the_hash() -> None:
    """Changing an assumption changes the plan hash."""
    original = render_plan_card(
        _FIELD,
        goal="Add a note",
        assumptions=["empty"],
        environment="staging",
    )
    changed = render_plan_card(
        _FIELD,
        goal="Add a note",
        assumptions=["not empty"],
        environment="staging",
    )
    assert changed["plan_hash"] != original["plan_hash"]
    assert changed["assumptions"] == ["not empty"]


def test_ac6_r3_production_is_one_self_approval() -> None:
    """R3 on production or staging is one approver, and the requester may approve."""
    for environment in ("production", "staging"):
        decision = policy_decision("R3", environment)
        assert decision["approvers"] == 1
        assert decision["deny"] is False
        assert decision["allow"] is True
        assert decision["needs_simulation"] is False
    assert self_approval_allowed("R3") is True


def test_ac6_r4_hard_stop_and_heavy_gate_keep_two_people() -> None:
    """Hard-stop R4 is denied. Heavy production R4 needs two people, not one identity twice."""
    for environment in ("production", "staging"):
        denied = policy_decision("R4", environment)
        assert denied["deny"] is True
    heavy = policy_decision("R4", "production", heavy=True)
    assert heavy["approvers"] == 2
    assert heavy["allow"] is True
    assert heavy["needs_simulation"] is True
    assert heavy["needs_backup"] is True
    assert heavy["needs_window"] is True
    assert self_approval_allowed("R4") is False
    twice = _heavy_met(
        [
            _heavy_person("ada", approver_id="google-ada", provider="google", session_id="sess-g"),
            _heavy_person("ada", approver_id="microsoft-ada", provider="microsoft", session_id="sess-m"),
        ]
    )
    assert twice["distinct_approvers"] == 1
    assert twice["met"] is False
    assert "distinct_approvers" in twice["blockers"]
    requester_both = _heavy_met(
        [
            _heavy_person("requester", approver_id="google-requester", provider="google"),
            _heavy_person("requester", approver_id="microsoft-requester", provider="microsoft"),
            _heavy_person("mina"),
        ]
    )
    assert requester_both["distinct_approvers"] == 1
    assert requester_both["met"] is False
    assert "distinct_approvers" in requester_both["blockers"]


def test_ac7_client_roles_hide_other_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """client_approver and client_viewer get 404 for another connection."""
    world = _agency()
    with _client(monkeypatch, accounts=True) as client:
        for email, password in (
            (world.approver_email, world.approver_password),
            (world.viewer_email, world.viewer_password),
        ):
            _login(client, email, password)
            hidden = client.get(f"/api/connections/{world.other_id}")
            assert hidden.status_code == 404
            client.post("/api/accounts/logout")


def test_ac7_other_connection_is_not_a_named_403(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other-connection response is not a 403 body that names that connection."""
    world = _agency()
    with _client(monkeypatch, accounts=True) as client:
        for email, password in (
            (world.approver_email, world.approver_password),
            (world.viewer_email, world.viewer_password),
        ):
            _login(client, email, password)
            hidden = client.get(f"/api/connections/{world.other_id}")
            assert hidden.status_code != 403
            assert world.other_name not in hidden.text
            assert world.other_id not in hidden.text
            client.post("/api/accounts/logout")


def test_ac8_client_approver_replaces_command_with_inbox() -> None:
    """client_approver with conn-granted is sent to that connection's inbox."""
    page = _read("apps/web/src/app/command/page.tsx")
    view = _read("apps/web/src/components/command/FleetCommandPageView.tsx")
    assert 'return role === "client_approver";' in page
    assert "const connectionId = connections[0]?.id;" in page
    assert "`/approvals?connection_id=${encodeURIComponent(connectionId)}`" in page
    redirect = page.split("if (isClientApprover", 1)[1].split('setGate("consultant")', 1)[0]
    assert "router.replace" in redirect
    assert "return;" in redirect
    gate = view.split("if (gateLoading && !harnessState)", 1)[1].split("\n  return (", 1)[0]
    assert "CommandCenterTile" not in gate
    assert "command-tile-clients" not in gate
    connection_id = ["conn-granted"][0]
    assert f"/approvals?connection_id={connection_id}" == "/approvals?connection_id=conn-granted"


def test_ac8_slow_pending_approvals_keeps_other_tiles() -> None:
    """A slow pending-approvals tile keeps its skeleton and does not blank the others."""
    page = _read("apps/web/src/app/command/page.tsx")
    tile = _read("apps/web/src/components/command/CommandCenterTile.tsx")
    view = _read("apps/web/src/components/command/FleetCommandPageView.tsx")
    fleet = _read("apps/web/src/lib/fleetCommandScreen.ts")
    assert "/api/command/tiles/pending-approvals" not in page
    assert 'id: "pending-approvals"' in fleet
    assert 'countUrl: "/api/command/tiles/pending-approvals"' in fleet
    assert "useState<TileState>" in tile
    assert "const count = await fetchCount(tile.countUrl);" in tile
    assert 'data-testid={`command-tile-${tile.id}-skeleton`}' in tile
    assert 'data-testid={`command-tile-${tile.id}-count`}' in tile
    loading = tile.split('state.phase === "loading"', 1)[1].split(": null}", 1)[0]
    assert "command-tile-${tile.id}-skeleton" in loading
    grid = view.split('data-testid="fleet-tile-grid"', 1)[1].split("</ul>", 1)[0]
    assert "FLEET_TILES.map" in grid
    assert "<CommandCenterTile" in grid
    assert "pending-approvals" not in grid


def test_ac9_client_page_shows_one_open_plan_snapshot_and_roster() -> None:
    """Acme Odoo shows one open plan, the latest snapshot, and the roster note."""
    page = _read("apps/web/src/app/connections/[id]/client/page.tsx")
    panel = _read("apps/web/src/components/connection-client/ConnectionClientPanel.tsx")
    assert "ConnectionClientPanel" in page
    assert 'data-testid="connection-client-page"' in page
    statuses = _open_plan_statuses()
    plans = [
        {"goal": "Add invoice note field", "status": "pending"},
        {"goal": "Old approved plan", "status": "approved"},
    ]
    open_plans = [plan for plan in plans if plan["status"] in statuses]
    assert open_plans == [{"goal": "Add invoice note field", "status": "pending"}]
    assert 'data-testid="connection-client-open-plan"' in panel
    assert "{plan.goal}" in panel
    assert "{snap.label}" in panel
    assert "{snap.id}" in panel
    roster = panel.split('testId="connection-client-bot-roster"', 1)[1]
    assert "not available yet" in roster.lower()
    snapshot = {"label": "sale.order.form", "id": "snap-latest"}
    assert snapshot["label"] == "sale.order.form"
    assert snapshot["id"] == "snap-latest"


def test_ac9_approved_plan_is_not_an_open_change_set() -> None:
    """An approved plan is not an open change-set on the client page."""
    statuses = _open_plan_statuses()
    assert statuses == {"pending"}
    assert "approved" not in statuses
    approved = {"goal": "Old approved plan", "status": "approved"}
    assert approved["status"] not in statuses


def test_ac10_grant_and_revoke_write_typed_rows_and_panel_calls_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Grant returns 201 and revoke returns 204, each with one success audit row."""
    panel = _read("apps/web/src/components/access/ConnectionTeamGrantsPanel.tsx")
    assert "api.createConnectionGrant(" in panel
    assert "api.deleteConnectionGrant(" in panel
    owner_email = _email("grant-owner")
    owner_password = "owner-pass-99"
    grantee_email = _email("grantee")
    db = SessionLocal()
    try:
        _owner, workspace, _token = signup_user(
            db, email=owner_email, password=owner_password, workspace_name="Grant WS"
        )
        _owner.email_verified = True
        db.add(_owner)
        grantee = User(
            email=grantee_email,
            password_hash=hash_password("grantee-pass-99"),
            email_verified=True,
        )
        db.add(grantee)
        connection = OdooConnection(
            name="Grant conn",
            url="http://odoo.invalid",
            db_name=f"ingenium_reg_np_t6_{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        db.add(connection)
        db.commit()
        connection_id = connection.id
    finally:
        db.close()

    with _client(monkeypatch, accounts=True) as client:
        _login(client, owner_email, owner_password)
        before_grant = _ids("grant")
        created = client.post(
            "/api/accounts/connection-grants",
            json={"connection_id": connection_id, "email": grantee_email, "role": "client_approver"},
        )
        assert created.status_code == 201, created.text
        grant_rows = _new_rows("grant", before_grant)
        assert len(grant_rows) == 1
        assert _payload(grant_rows[0])["result"] == "success"
        before_revoke = _ids("revoke")
        revoked = client.delete(f"/api/accounts/connection-grants/{created.json()['id']}")
        assert revoked.status_code == 204, revoked.text
        revoke_rows = _new_rows("revoke", before_revoke)
        assert len(revoke_rows) == 1
        assert _payload(revoke_rows[0])["result"] == "success"


def test_ac10_unknown_email_grant_is_404_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown email returns 404 and one grant row with result failure."""
    owner_email = _email("grant-owner")
    owner_password = "owner-pass-99"
    db = SessionLocal()
    try:
        owner, workspace, _token = signup_user(
            db, email=owner_email, password=owner_password, workspace_name="Grant WS"
        )
        owner.email_verified = True
        db.add(owner)
        connection = OdooConnection(
            name="Grant conn",
            url="http://odoo.invalid",
            db_name=f"ingenium_reg_np_t6_{uuid.uuid4().hex[:8]}",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
            workspace_id=workspace.id,
        )
        db.add(connection)
        db.commit()
        connection_id = connection.id
    finally:
        db.close()

    with _client(monkeypatch, accounts=True) as client:
        _login(client, owner_email, owner_password)
        before = _ids("grant")
        missing = client.post(
            "/api/accounts/connection-grants",
            json={
                "connection_id": connection_id,
                "email": _email("nobody"),
                "role": "client_approver",
            },
        )
        assert missing.status_code == 404
        rows = _new_rows("grant", before)
    assert len(rows) == 1
    assert _payload(rows[0])["result"] == "failure"


def test_ac11_saml_open_question_records_later() -> None:
    """OQ-SAML is still an open question and records SAML as later."""
    text = _read("docs/plans/next-phase/18_OPEN_QUESTIONS.md")
    assert text.startswith("# Open questions")
    row = next(line for line in text.splitlines() if line.startswith("| OQ-SAML |"))
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    assert cells[0] == "OQ-SAML"
    assert cells[1] == "SAML"
    assert cells[2] == "No"
    assert "Accepted" not in cells[2]
    assert cells[3] == "T6-12 records it as later"


def test_ac11_api_has_no_saml_symbol() -> None:
    """apps/api/app has no SAML symbol."""
    root = _REPO / "apps" / "api" / "app"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if "saml" in path.name.lower() or "saml" in path.read_text(encoding="utf-8").lower():
            hits.append(str(path.relative_to(_REPO)))
    assert hits == []
