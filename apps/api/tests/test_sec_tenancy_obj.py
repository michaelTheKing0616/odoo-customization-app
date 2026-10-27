"""SEC-TENANCY-OBJ oracle. Foreign objects are denied with 404 or 403.

AC1: workspace A must not read or change workspace B's connections, plans,
approvals, History entries, bots, flows, or files. Denial is 404 or 403.
Workspace A reading its own object of that kind must not be denied.

Foreign probes use A's connection id together with B's object id, except for
the connection itself. A request that only carries B's connection id is already
denied by WorkspaceTenancyMiddleware, so it would stay green after the object
check was removed.

Product lines whose deletion fails the matching hard case:
- connection: the 404 before the handler when the path carries another workspace's connection id
- plan: suite get_item / get_suite_item filtered by connection id
- History entry: snapshot artifact and rollback refuse another connection's snapshot
- bot: assert_session_tenant on the live-demo session
- flow read: get_flow loads only the caller's workspace
- file: ingest job read and override refuse another connection's job

The hard test covers connections, plans, history, bots, flow read, and files.
Approval read and change are pinned on
test_ac1_positive_foreign_approvals_are_denied: approve_entry opens the Odoo
client before it compares the entry connection id, so a foreign entry returns
502. Flow change is pinned on test_ac1_positive_foreign_flow_change_is_denied:
flow rollback returns 409 when the flow is outside the caller workspace. A
pinned test XPASSes only when its probes return 404 or 403 and the foreign
marker is absent from the body.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlparse

import pytest

_PASSWORD = "workspace-a-pass"
_DENIAL = frozenset({403, 404})
_APP = None
_KINDS = (
    "connections",
    "plans",
    "approvals",
    "history",
    "bots",
    "flows",
    "files",
)
# Hard denials. Approval probes and flow rollback stay in their own strict xfails.
_HARD_FOREIGN = frozenset(
    {
        ("connections", "read"),
        ("connections", "change"),
        ("plans", "read"),
        ("plans", "change"),
        ("history", "read"),
        ("history", "change"),
        ("bots", "read"),
        ("bots", "change"),
        ("flows", "read"),
        ("files", "read"),
        ("files", "change"),
    }
)
_APPROVAL_FOREIGN = frozenset({("approvals", "read"), ("approvals", "change")})
_FLOW_CHANGE_FOREIGN = frozenset({("flows", "change")})


def _allow_boot() -> None:
    """Loopback ``--host`` as its own argv token so auth-off boot is not the failure."""
    if "--host" in sys.argv:
        return
    sys.argv.extend(["--host", "127.0.0.1"])


def _load_app():
    global _APP
    if _APP is None:
        _allow_boot()
        from app.main import app as fastapi_app

        _APP = fastapi_app
    return _APP


def _accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", "accounts")
    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(settings, "ai_assist", "off")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 0)


def _isolate_flow_store(monkeypatch: pytest.MonkeyPatch) -> str:
    """Point bridge flow files at an empty directory for this test only."""
    home = tempfile.mkdtemp(prefix="ingenium_tenancy_obj_")
    monkeypatch.setenv("INGENIUM_CODE_RUNNER_DIR", home)
    return home


def _db_port() -> int:
    from app.settings import settings

    raw = settings.database_url.replace("postgresql+psycopg", "postgresql", 1)
    return urlparse(raw).port or 5432


@contextmanager
def _block_outbound_except_app_db() -> Iterator[None]:
    """Fail closed on non-database sockets so a route cannot wait on Odoo."""
    import socket

    allowed = _db_port()
    real = socket.create_connection

    def guarded(address, *args, **kwargs):
        port = address[1] if isinstance(address, tuple) and len(address) >= 2 else None
        if port != allowed:
            raise OSError(f"tenancy object probe blocked outbound port {port}")
        return real(address, *args, **kwargs)

    socket.create_connection = guarded
    try:
        yield
    finally:
        socket.create_connection = real


def _connection(name: str, db_name: str, secret: str, workspace_id: str):
    from app.db_models import OdooConnection

    return OdooConnection(
        name=name,
        url="http://127.0.0.1:9",
        db_name=db_name,
        username="tenancy",
        secret_encrypted=secret,
        workspace_id=workspace_id,
    )


def _snapshot(connection_id: str, label: str):
    from app.db_models import MetadataSnapshot

    return MetadataSnapshot(
        connection_id=connection_id,
        resource_type="view",
        resource_key="view:tenancy-obj",
        label=label,
        payload_json='{"marker": "%s"}' % label,
        reversible="yes",
    )


def _bot(workspace_id: str, connection_id: str, name: str):
    from app.db_models import LiveDemoCopilotSession

    bot_id = str(uuid.uuid4())
    url = f"https://example.com/meet/{bot_id}"
    return LiveDemoCopilotSession(
        id=bot_id,
        workspace_id=workspace_id,
        connection_id=connection_id,
        meeting_url=url,
        meeting_url_hash=hashlib.sha256(url.encode()).hexdigest(),
        bot_name=name,
        attendee_bot_id=f"bot-{bot_id}",
    )


def _flow(workspace_id: str, marker: str) -> str:
    from app.code_runner import store

    flow_id = str(uuid.uuid4())
    store.save(
        "bridge_flows",
        f"flows_{workspace_id}",
        {
            flow_id: {
                "versions": [],
                "live": None,
                "rollout": 0,
                "marker": marker,
            }
        },
    )
    return flow_id


def _seed() -> dict[str, str]:
    from app.account_service import signup_user
    from app.crypto import encrypt_secret
    from app.db import SessionLocal
    from app.db_models import ApprovalEntry, ApprovalRule
    from app.ingest.store import create_job, load_payload
    from app.suite_store import save_item

    email_a = f"tenancy-obj-a-{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"tenancy-obj-b-{uuid.uuid4().hex[:8]}@example.com"
    secret = encrypt_secret("not-a-credential")
    db = SessionLocal()
    try:
        user_a, ws_a, _token_a = signup_user(
            db, email=email_a, password=_PASSWORD, workspace_name="Workspace A"
        )
        user_b, ws_b, _token_b = signup_user(
            db, email=email_b, password=_PASSWORD, workspace_name="Workspace B"
        )
        user_a.email_verified = True
        user_b.email_verified = True
        db.add(user_a)
        db.add(user_b)
        owned = _connection("a-connection-secret", "ingenium_tenancy_obj_a", secret, ws_a.id)
        victim = _connection("b-connection-secret", "ingenium_tenancy_obj_b", secret, ws_b.id)
        db.add(owned)
        db.add(victim)
        db.flush()
        rule_a = ApprovalRule(
            connection_id=owned.id,
            name="a-approval-rule",
            target_model="sale.order",
            button_method="action_confirm",
        )
        rule_b = ApprovalRule(
            connection_id=victim.id,
            name="b-approval-rule",
            target_model="sale.order",
            button_method="action_confirm",
        )
        db.add(rule_a)
        db.add(rule_b)
        db.flush()
        entry_a = ApprovalEntry(
            connection_id=owned.id,
            rule_id=rule_a.id,
            record_model="sale.order",
            record_id=1,
            message="a-approval-secret",
        )
        entry_b = ApprovalEntry(
            connection_id=victim.id,
            rule_id=rule_b.id,
            record_model="sale.order",
            record_id=2,
            message="b-approval-secret",
        )
        snap_a = _snapshot(owned.id, "a-history-secret")
        snap_b = _snapshot(victim.id, "b-history-secret")
        bot_a = _bot(ws_a.id, owned.id, "a-bot-secret")
        bot_b = _bot(ws_b.id, victim.id, "b-bot-secret")
        db.add_all([entry_a, entry_b, snap_a, snap_b, bot_a, bot_b])
        db.commit()
        plan_a = save_item(
            db,
            connection_id=owned.id,
            kind="suite_plan",
            key="plan:setup",
            name="a-plan-secret",
            payload={"kind": "setup", "steps": []},
        )
        plan_b = save_item(
            db,
            connection_id=victim.id,
            kind="suite_plan",
            key="plan:setup",
            name="b-plan-secret",
            payload={"kind": "setup", "steps": []},
        )
        job_a, _blobs_a = create_job(
            db,
            connection_id=owned.id,
            files=[("a-file-secret.csv", b"a,b\n", "text/csv")],
        )
        job_b, _blobs_b = create_job(
            db,
            connection_id=victim.id,
            files=[("b-file-secret.csv", b"a,b\n", "text/csv")],
        )
        file_a = load_payload(job_a)[0].files[0].id
        file_b = load_payload(job_b)[0].files[0].id
        flow_a = _flow(ws_a.id, "a-flow-secret")
        flow_b = _flow(ws_b.id, "b-flow-secret")
        return {
            "email_a": email_a,
            "a_connection_id": owned.id,
            "b_connection_id": victim.id,
            "a_plan_id": plan_a.id,
            "b_plan_id": plan_b.id,
            "a_entry_id": entry_a.id,
            "b_entry_id": entry_b.id,
            "a_snapshot_id": snap_a.id,
            "b_snapshot_id": snap_b.id,
            "a_bot_id": bot_a.id,
            "b_bot_id": bot_b.id,
            "a_flow_id": flow_a,
            "b_flow_id": flow_b,
            "a_job_id": job_a.id,
            "b_job_id": job_b.id,
            "a_file_id": file_a,
            "b_file_id": file_b,
        }
    finally:
        db.close()


def _login(client, email: str) -> None:
    response = client.post(
        "/api/accounts/login",
        json={"email": email, "password": _PASSWORD},
    )
    assert response.status_code == 200, response.text[:200]


def _probe(client, method: str, url: str, body: dict | None) -> tuple[int | str, str]:
    kwargs: dict = {}
    if body is not None:
        kwargs["json"] = body
    try:
        response = client.request(method, url, **kwargs)
    except Exception as exc:  # noqa: BLE001 — one probe must not hide the other kinds
        return type(exc).__name__, str(exc)[:180]
    return response.status_code, response.text[:500]


def _denied(status: int | str) -> bool:
    return isinstance(status, int) and status in _DENIAL


def _foreign_calls(rows: dict[str, str]) -> list[tuple[str, str, str, str, dict | None, str]]:
    """Read and change each of B's objects without sending B's connection id.

    The connection probe is the exception: the connection id is the object id.
    """
    a_conn = rows["a_connection_id"]
    b_conn = rows["b_connection_id"]
    b_plan = rows["b_plan_id"]
    b_entry = rows["b_entry_id"]
    b_snap = rows["b_snapshot_id"]
    b_bot = rows["b_bot_id"]
    b_flow = rows["b_flow_id"]
    b_job = rows["b_job_id"]
    return [
        ("connections", "read", "GET", f"/api/connections/{b_conn}", None, "b-connection-secret"),
        (
            "connections",
            "change",
            "PATCH",
            f"/api/connections/{b_conn}",
            {"name": "stolen", "verify": False},
            "b-connection-secret",
        ),
        (
            "plans",
            "read",
            "GET",
            f"/api/connections/{a_conn}/suite/setup/plans/{b_plan}",
            None,
            "b-plan-secret",
        ),
        (
            "plans",
            "change",
            "PUT",
            f"/api/connections/{a_conn}/suite/setup/plans/{b_plan}",
            {"name": "stolen", "steps": []},
            "b-plan-secret",
        ),
        # SEC-6.2-OBJ-APPROVAL: excluded from the hard denial test.
        (
            "approvals",
            "read",
            "POST",
            f"/api/connections/{a_conn}/approvals/entries/{b_entry}/approve",
            {"approve": False},
            "b-approval-secret",
        ),
        (
            "approvals",
            "change",
            "POST",
            f"/api/connections/{a_conn}/approvals/entries/{b_entry}/approve",
            {"approve": True},
            "b-approval-secret",
        ),
        (
            "history",
            "read",
            "GET",
            f"/api/connections/{a_conn}/snapshots/{b_snap}/artifact.json",
            None,
            "b-history-secret",
        ),
        (
            "history",
            "change",
            "POST",
            f"/api/connections/{a_conn}/snapshots/{b_snap}/rollback",
            None,
            "b-history-secret",
        ),
        (
            "bots",
            "read",
            "GET",
            f"/api/live-demo-copilot/sessions/{b_bot}",
            None,
            "b-bot-secret",
        ),
        (
            "bots",
            "change",
            "PATCH",
            f"/api/live-demo-copilot/sessions/{b_bot}/presenter-speakers",
            {"presenter_speakers": ["Other"]},
            "b-bot-secret",
        ),
        ("flows", "read", "GET", f"/api/bridge/flows/{b_flow}", None, "b-flow-secret"),
        # SEC-6.2-OBJ-FLOW: excluded from the hard denial test.
        ("flows", "change", "POST", f"/api/bridge/flows/{b_flow}/rollback", None, "b-flow-secret"),
        (
            "files",
            "read",
            "GET",
            f"/api/connections/{a_conn}/ingest/jobs/{b_job}",
            None,
            "b-file-secret.csv",
        ),
        (
            "files",
            "change",
            "POST",
            f"/api/connections/{a_conn}/ingest/jobs/{b_job}/override",
            {"force_doc_types": {}},
            "b-file-secret.csv",
        ),
    ]


def _own_reads(rows: dict[str, str]) -> list[tuple[str, str, str, str]]:
    a_conn = rows["a_connection_id"]
    return [
        ("connections", "GET", f"/api/connections/{a_conn}", rows["a_connection_id"]),
        (
            "plans",
            "GET",
            f"/api/connections/{a_conn}/suite/setup/plans/{rows['a_plan_id']}",
            rows["a_plan_id"],
        ),
        (
            "approvals",
            "GET",
            f"/api/connections/{a_conn}/approvals/entries",
            rows["a_entry_id"],
        ),
        (
            "history",
            "GET",
            f"/api/connections/{a_conn}/history",
            f"snap:{rows['a_snapshot_id']}",
        ),
        (
            "bots",
            "GET",
            f"/api/live-demo-copilot/sessions/{rows['a_bot_id']}",
            rows["a_bot_id"],
        ),
        ("flows", "GET", f"/api/bridge/flows/{rows['a_flow_id']}", "a-flow-secret"),
        (
            "files",
            "GET",
            f"/api/connections/{a_conn}/ingest/jobs/{rows['a_job_id']}",
            rows["a_file_id"],
        ),
    ]


def _open_cases(
    client,
    rows: dict[str, str],
    selected: frozenset[tuple[str, str]],
) -> list[str]:
    calls = [item for item in _foreign_calls(rows) if (item[0], item[1]) in selected]
    assert {(item[0], item[1]) for item in calls} == selected
    assert len(calls) == len(selected)
    open_cases: list[str] = []
    for kind, verb, method, url, body, marker in calls:
        status, text = _probe(client, method, url, body)
        if not _denied(status) or marker in text:
            open_cases.append(f"{kind} {verb} {status}")
    return open_cases


def _open_foreign_cases(
    monkeypatch: pytest.MonkeyPatch,
    selected: frozenset[tuple[str, str]],
) -> list[str]:
    """Log in as workspace A and return selected foreign probes that are not denied."""
    from fastapi.testclient import TestClient

    app = _load_app()
    _accounts(monkeypatch)
    home = _isolate_flow_store(monkeypatch)
    try:
        rows = _seed()
        with (
            TestClient(app, raise_server_exceptions=False) as client,
            _block_outbound_except_app_db(),
        ):
            _login(client, rows["email_a"])
            return _open_cases(client, rows, selected)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _own_failures(client, rows: dict[str, str]) -> list[str]:
    reads = _own_reads(rows)
    assert {item[0] for item in reads} == set(_KINDS)
    failed: list[str] = []
    for kind, method, url, needle in reads:
        status, text = _probe(client, method, url, None)
        if _denied(status) or status != 200 or needle not in text:
            failed.append(f"{kind} {status}")
    return failed


def test_ac1_positive_foreign_objects_are_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Connections, plans, history, bots, flow read, and files are denied with 404 or 403."""
    open_cases = _open_foreign_cases(monkeypatch, _HARD_FOREIGN)
    assert not open_cases, "object checks still open: " + "; ".join(open_cases)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.2-OBJ-APPROVAL: approve_entry opens the Odoo client before the "
        "entry connection check, so a foreign entry returns 502"
    ),
)
def test_ac1_positive_foreign_approvals_are_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Foreign approval probes are denied only when both return 404 or 403 without the marker."""
    open_cases = _open_foreign_cases(monkeypatch, _APPROVAL_FOREIGN)
    assert not open_cases, "object checks still open: " + "; ".join(open_cases)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.2-OBJ-FLOW: flow rollback returns 409 when the flow is outside the "
        "caller workspace, not 404 or 403"
    ),
)
def test_ac1_positive_foreign_flow_change_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """A foreign flow rollback is denied only when it returns 404 or 403 without the marker."""
    open_cases = _open_foreign_cases(monkeypatch, _FLOW_CHANGE_FOREIGN)
    assert not open_cases, "object checks still open: " + "; ".join(open_cases)


def test_ac1_negative_own_objects_are_not_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Workspace A reading its own object is not a 404 or 403 from that check."""
    from fastapi.testclient import TestClient

    app = _load_app()
    _accounts(monkeypatch)
    home = _isolate_flow_store(monkeypatch)
    try:
        rows = _seed()
        with TestClient(app, raise_server_exceptions=False) as client, _block_outbound_except_app_db():
            _login(client, rows["email_a"])
            failed = _own_failures(client, rows)
        assert not failed, "own objects denied or not readable: " + "; ".join(failed)
    finally:
        shutil.rmtree(home, ignore_errors=True)
