"""BV-AUDIT-WIRE: lazy audit-store wiring (no main.py hook) + audited approval-read failure."""

from __future__ import annotations

import threading
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import app.db as appdb
from app.bot_verify import targets as tg
from tests.test_nf_bot_verify_audit import CONN_A, CONN_B, engine  # noqa: F401 - shared fixture

URL = "http://127.0.0.1:18117"


@pytest.fixture()
def lazy(engine, monkeypatch):  # noqa: F811
    with engine.begin() as c:
        c.execute(text("DELETE FROM verify_audit"))
        c.execute(text("DELETE FROM verify_walk_approvals"))
    monkeypatch.setattr(appdb, "engine", engine)
    monkeypatch.setattr(tg, "_STORE", tg._UNSET)
    yield engine


def _rows(eng) -> list[tuple[str, str]]:
    with eng.connect() as c:
        return [tuple(r) for r in c.execute(text("SELECT decision, reason FROM verify_audit"))]


def test_walk_path_lazily_wires_store_when_db_up(lazy) -> None:
    t = tg.resolve_target(url=URL, db_name="ingenium_wire_a", major=17)
    assert t.kind == "disposable_clone"
    assert isinstance(tg.audit_store(), tg.AuditStore)
    assert _rows(lazy) == [("allowed", "disposable_clone")]


def test_ensure_is_idempotent_and_thread_safe(lazy) -> None:
    got: list[Any] = []
    ts = [threading.Thread(target=lambda: got.append(tg.ensure_audit_store())) for _ in range(16)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len({id(s) for s in got}) == 1 and got[0] is tg.audit_store()
    assert _rows(lazy) == []


def test_db_down_refuses(monkeypatch) -> None:
    dead = create_engine("postgresql+psycopg://x:x@127.0.0.1:1/ingenium_none", poolclass=NullPool)
    monkeypatch.setattr(appdb, "engine", dead)
    monkeypatch.setattr(tg, "_STORE", tg._UNSET)
    with pytest.raises(tg.TargetNotAllowed, match="audit write failed"):
        tg.resolve_target(url=URL, db_name="ingenium_wire_b", major=20)


def test_explicit_none_is_not_overridden(monkeypatch) -> None:
    monkeypatch.setattr(tg, "_STORE", tg._UNSET)
    tg.configure_audit_store(None)
    with pytest.raises(tg.TargetNotAllowed, match="not configured"):
        tg.resolve_target(url=URL, db_name="ingenium_wire_c", major=17)


def test_approval_read_failure_is_an_audited_refusal(monkeypatch) -> None:
    rows: list[tuple[Any, ...]] = []

    class Raising:
        def record(self, *a: Any) -> None:
            rows.append(a)

        def approval(self, cid: Any) -> tg.WalkApproval:
            raise RuntimeError("secret-dsn postgresql://u:pw@h/db")

    monkeypatch.setattr(tg, "_STORE", Raising())
    with pytest.raises(tg.TargetNotAllowed, match="approval read failed"):
        tg.resolve_target(url=URL, db_name="prod_db", major=18, connection_id=CONN_A)
    assert rows == [(CONN_A, "prod_db", "refused", "approval read failed")]


def test_caller_supplied_approval_ignored_on_lazy_store(lazy) -> None:
    with pytest.raises(tg.TargetNotAllowed, match="no stored owner"):
        tg.resolve_target(
            url=URL,
            db_name="prod_db",
            major=19,
            connection_id=CONN_A,
            walkthrough_allowed=True,
            approved_by="u1",
            owner_id="u1",
        )
    assert _rows(lazy)[0][0] == "refused"
    tg.audit_store().set_approval(CONN_A, allowed=True, approved_by="u1", owner_id="u1")
    assert tg.resolve_target(url=URL, db_name="prod_db", major=19, connection_id=CONN_A).kind == (
        "approved_connection"
    )


# ------------------------------------------------------------ AC4-AC6 approval endpoint


@pytest.fixture()
def api(lazy, monkeypatch):
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app
    from app.routers import bot_verify as r
    from app.safety_dependency import enforce_safety_gate
    from app.workspace_auth import WorkspaceAuth, require_app_auth

    with lazy.begin() as c:
        c.execute(
            text(
                "INSERT INTO workspaces (id, name, slug) VALUES ('ws-ot','ws-ot','ws-ot')"
                " ON CONFLICT DO NOTHING"
            )
        )
        c.execute(
            text(
                "INSERT INTO odoo_connections (id, workspace_id, name, url, db_name, username,"
                " secret_encrypted, upgrade_detected) VALUES ('conn-ot', 'ws-ot', 'o',"
                " 'http://x', 'd', 'u', 'enc', false) ON CONFLICT DO NOTHING"
            )
        )
        for u, role in (("u-own", "owner"), ("u-adm", "admin"), ("u-own2", "owner")):
            c.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, password_login_enabled,"
                    " email_verified, totp_enabled, is_superadmin) VALUES"
                    " (:u, :e, 'x', true, true, false, false) ON CONFLICT DO NOTHING"
                ),
                {"u": u, "e": f"{u}@t.test"},
            )
            c.execute(
                text(
                    "INSERT INTO workspace_memberships (id, workspace_id, user_id, role)"
                    " VALUES (:i, 'ws-au', :u, :r) ON CONFLICT DO NOTHING"
                ),
                {"i": f"m-{u}", "u": u, "r": role},
            )
    Session = sessionmaker(bind=lazy)

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    def _auth(request):
        h = request.headers
        return WorkspaceAuth(
            mode=h.get("x-mode", "accounts"),
            user_id=h.get("x-user"),
            workspace_id="ws-au",
            role="admin" if h.get("x-user") == "u-adm" else "owner",
            api_key_authenticated=h.get("x-apikey") == "1",
        )

    monkeypatch.setattr(r, "get_workspace_auth", _auth)
    o = app.dependency_overrides
    saved = dict(o)
    o[require_app_auth] = lambda: None
    o[enforce_safety_gate] = lambda: None
    o[get_db] = _db
    yield TestClient(app)
    o.clear()
    o.update(saved)


def _put(api, cid: str, user: str, hdr: dict[str, str] | None = None, **body: Any):
    return api.put(
        f"/api/connections/{cid}/verify-runs/walk-approval",
        json=body,
        headers={"x-user": user, **(hdr or {})},
    )


def _appr(eng, cid: str):
    with eng.connect() as c:
        return c.execute(
            text(
                "SELECT walkthrough_allowed, approved_by, owner_id FROM verify_walk_approvals"
                " WHERE connection_id = :c"
            ),
            {"c": cid},
        ).first()


def test_ac4_owner_grants_server_side_ids_and_audits(api, lazy) -> None:
    res = _put(api, CONN_A, "u-own", allowed=True, owner_id="evil", approved_by="evil")
    assert res.status_code == 200 and res.json()["walkthrough_allowed"] is True
    assert tuple(_appr(lazy, CONN_A)) == (True, "u-own", "u-own")
    assert _rows(lazy) == [("approval_granted", "owner walkthrough approval")]
    assert tg.resolve_target(url=URL, db_name="d", major=17, connection_id=CONN_A).kind == (
        "approved_connection"
    )


def test_ac4_non_owner_403_and_nothing_written(api, lazy) -> None:
    res = _put(api, CONN_A, "u-adm", allowed=True)
    assert res.status_code == 403
    assert _appr(lazy, CONN_A) is None and _rows(lazy) == []


def test_ac4_ac5_revoke_audited_and_refuses(api, lazy) -> None:
    assert _put(api, CONN_A, "u-own", allowed=True).status_code == 200
    assert _put(api, CONN_A, "u-own", allowed=False).status_code == 200
    assert _appr(lazy, CONN_A)[0] is False
    assert [d for d, _ in _rows(lazy)] == ["approval_granted", "approval_revoked"]
    with pytest.raises(tg.TargetNotAllowed):
        tg.resolve_target(url=URL, db_name="d", major=20, connection_id=CONN_A)


def test_ac6_delete_connection_keeps_audit_cascades_approval(api, lazy) -> None:
    assert _put(api, CONN_B, "u-own", allowed=True).status_code == 200
    with lazy.begin() as c:
        c.execute(text("DELETE FROM odoo_connections WHERE id = :c"), {"c": CONN_B})
    assert _appr(lazy, CONN_B) is None
    with lazy.connect() as c:
        n = c.execute(
            text("SELECT count(*) FROM verify_audit WHERE connection_id = :c"), {"c": CONN_B}
        ).scalar()
    assert n == 1


def _nothing(eng, cid: str) -> bool:
    return _appr(eng, cid) is None and _rows(eng) == []


def test_ac4_cross_workspace_connection_404(api, lazy) -> None:
    assert _put(api, "conn-ot", "u-own", allowed=True).status_code == 404
    assert _nothing(lazy, "conn-ot")


@pytest.mark.parametrize("hdr", [{"x-apikey": "1"}, {"x-mode": "off"}], ids=["api_key", "auth_off"])
def test_ac4_api_key_and_auth_off_denied(api, lazy, hdr) -> None:
    res = _put(api, CONN_A, "u-own", hdr, allowed=True)
    assert res.status_code in (403, 404) and res.status_code != 200
    assert _nothing(lazy, CONN_A)


def test_ac4_deleted_connection_404(api, lazy) -> None:
    assert _put(api, "conn-gone", "u-own", allowed=True).status_code == 404
    assert _nothing(lazy, "conn-gone")


def test_ac4_second_owner_can_approve(api, lazy) -> None:
    assert _put(api, CONN_A, "u-own2", allowed=True).status_code == 200
    assert tuple(_appr(lazy, CONN_A)) == (True, "u-own2", "u-own2")


def test_ac5_audit_failure_rolls_back_approval(api, lazy, monkeypatch) -> None:
    real = tg.verify_audit.insert

    class Boom:
        def values(self, **_k: Any) -> Any:
            return text("SELECT 1/0")

    monkeypatch.setattr(tg.verify_audit, "insert", lambda: Boom())
    res = _put(api, CONN_A, "u-own", allowed=True)
    monkeypatch.setattr(tg.verify_audit, "insert", real)
    assert res.status_code == 409 and res.json()["error"]["code"] == "TARGET_NOT_ALLOWED"
    assert _nothing(lazy, CONN_A)
