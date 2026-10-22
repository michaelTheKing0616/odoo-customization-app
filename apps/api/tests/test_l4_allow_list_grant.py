"""GATE-L4-12: a bot cannot widen its own allow-list. L4 stays off."""

from __future__ import annotations

import json
import re

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.audit_chain import verify_db
from app.db_models import AuditChainEntry
from app.worker_bot.l4_policy import (
    BOT_AUDIT_ACTOR,
    GATE_L4_12,
    L4_ALLOW_LIST_REFUSED,
    AllowListGrantResult,
    AllowListRegistry,
    is_allow_list_edit_tool,
    l4_may_apply,
    record_allow_list_change,
    refuse_bot_allow_list_tool_call,
    template_allow_list_change,
)

pytestmark = pytest.mark.no_app_db

_TENANT = "tenant-a"
_PLAN_HASH = "a" * 16
_VERIFIED_STAGING = {
    "plan_mode": "T",
    "plan_hash": _PLAN_HASH,
    "staging_applies": (
        {"plan_hash": _PLAN_HASH, "verified": True, "environment": "staging"},
    ),
}
_SECRET = "sk-test-L412/do-not-log"
_SECRET_IN_ARGS = "sk-test-l412-do-not-log"
_OPAQUE_HEX_TENANT = "0123456789abcdef0123456789abcdef"
_RUN_ID = "bot-run-l412"


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite://")
    AuditChainEntry.__table__.create(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()


def _record(registry: AllowListRegistry, *, role: str, op_type: str) -> AllowListGrantResult:
    return record_allow_list_change(
        registry,
        role=role,
        tenant=_TENANT,
        op_type=op_type,
        admin_id="admin-1",
    )


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_human_admin_may_record_allow_list_change(role: str) -> None:
    registry = AllowListRegistry()
    result = _record(registry, role=role, op_type="mail_template.create")
    assert result.recorded is True
    assert result.auto_applied is False
    assert result.refused is False
    assert registry.ops(_TENANT) == frozenset({"mail_template.create"})
    again = _record(registry, role=role, op_type="field.update")
    assert again.recorded is True
    assert registry.ops(_TENANT) == frozenset({"mail_template.create", "field.update"})


@pytest.mark.parametrize("role", ["viewer", "builder", "developer", "bot", "L4", ""])
def test_non_admin_cannot_record_allow_list_change(role: str) -> None:
    registry = AllowListRegistry()
    result = _record(registry, role=role, op_type="mail_template.create")
    assert result.recorded is False
    assert result.auto_applied is False
    assert result.refused is True
    assert result.reason == "human_admin_required"
    assert registry.ops(_TENANT) == frozenset()


def test_human_admin_cannot_record_a_non_catalog_token() -> None:
    registry = AllowListRegistry()
    result = _record(registry, role="admin", op_type=_SECRET)
    assert result.recorded is False
    assert result.reason == "op_not_in_catalog"
    assert registry.ops(_TENANT) == frozenset()


def test_recorded_module_op_still_fails_l4_may_apply() -> None:
    registry = AllowListRegistry()
    result = _record(registry, role="admin", op_type="module.install")
    assert result.recorded is True
    assert (
        l4_may_apply(
            risk="R1",
            op_type="module.install",
            rows=1,
            mode_t=True,
            staging_verified=True,
            allow_list=registry.ops(_TENANT),
            **_VERIFIED_STAGING,
        )
        is False
    )


def test_bot_tool_call_is_refused_and_audited(db: Session) -> None:
    registry = AllowListRegistry()
    record_allow_list_change(
        registry,
        role="admin",
        tenant=_TENANT,
        op_type="field.update",
        admin_id="admin-1",
    )
    before = registry.ops(_TENANT)
    tool_args = {
        "op_type": "mail_template.create",
        "role": "admin",
        "api_key": _SECRET,
        "password": _SECRET_IN_ARGS,
    }
    assert is_allow_list_edit_tool("l4.allow_list.add", tool_args) is True
    result = refuse_bot_allow_list_tool_call(
        db,
        registry,
        actor=_SECRET,
        tenant=_TENANT,
        op_type="mail_template.create",
        tool_name="l4.allow_list.add",
        run_id=_RUN_ID,
        tool_args=tool_args,
    )
    assert result.recorded is False
    assert result.auto_applied is False
    assert result.refused is True
    assert result.reason == "bot_cannot_widen_allow_list"
    assert registry.ops(_TENANT) == before
    assert (
        l4_may_apply(
            risk="R1",
            op_type="mail_template.create",
            rows=1,
            mode_t=True,
            staging_verified=True,
            allow_list=registry.ops(_TENANT),
            **_VERIFIED_STAGING,
        )
        is False
    )

    rows = db.query(AuditChainEntry).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "note"
    assert row.actor == BOT_AUDIT_ACTOR
    assert row.run_id == _RUN_ID
    payload = json.loads(row.payload_json)
    assert payload == {
        "actor_kind": "bot",
        "event": L4_ALLOW_LIST_REFUSED,
        "gate": GATE_L4_12,
        "op_type": "mail_template.create",
        "tenant": _TENANT,
        "tool": "l4.allow_list.add",
    }
    assert _SECRET not in row.payload_json
    assert _SECRET_IN_ARGS not in row.payload_json
    assert "api_key" not in payload
    assert "password" not in payload
    ok, bad = verify_db(db)
    assert ok is True
    assert bad is None


def test_bot_tool_call_drops_secrets_and_admin_spoof(db: Session) -> None:
    registry = AllowListRegistry()
    tool_args = {
        "role": "admin",
        "allow_list_add": "module.install",
        "api_key": _SECRET,
        "password": _SECRET_IN_ARGS,
        "nested": {"token": _SECRET, "op_type": "access.create"},
    }
    assert is_allow_list_edit_tool(_SECRET, tool_args) is True
    result = refuse_bot_allow_list_tool_call(
        db,
        registry,
        actor=_SECRET,
        tenant=_SECRET,
        op_type=_SECRET,
        tool_name=_SECRET,
        run_id=_SECRET,
        tool_args=tool_args,
    )
    assert result.refused is True
    assert result.recorded is False
    assert result.auto_applied is False
    assert registry.ops(_TENANT) == frozenset()
    assert registry.ops(_SECRET) == frozenset()

    row = db.query(AuditChainEntry).one()
    assert row.actor == BOT_AUDIT_ACTOR
    assert row.run_id is None
    payload = json.loads(row.payload_json)
    assert payload == {
        "actor_kind": "bot",
        "event": L4_ALLOW_LIST_REFUSED,
        "gate": GATE_L4_12,
        "op_type": "unlisted",
        "tenant": "unlisted",
        "tool": "unlisted",
    }
    blob = f"{row.actor}\n{row.run_id}\n{row.payload_json}"
    assert _SECRET not in blob
    assert _SECRET_IN_ARGS not in blob
    assert "module.install" not in row.payload_json
    assert "access.create" not in row.payload_json


def test_secret_shaped_tenant_is_absent_from_audit_note(db: Session) -> None:
    """A lowercase key that matches the tenant id pattern is not stored."""
    assert re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", _SECRET_IN_ARGS)
    registry = AllowListRegistry()
    result = refuse_bot_allow_list_tool_call(
        db,
        registry,
        actor="worker_bot",
        tenant=_SECRET_IN_ARGS,
        op_type="mail_template.create",
        tool_name="l4.allow_list.add",
        run_id=_RUN_ID,
    )
    assert result.refused is True
    assert result.recorded is False
    assert result.auto_applied is False
    assert registry.ops(_SECRET_IN_ARGS) == frozenset()

    row = db.query(AuditChainEntry).one()
    assert row.kind == "note"
    assert row.actor == BOT_AUDIT_ACTOR
    payload = json.loads(row.payload_json)
    assert payload["tenant"] == "unlisted"
    assert _SECRET_IN_ARGS not in row.payload_json
    assert _SECRET_IN_ARGS not in json.dumps(payload)


def test_opaque_hex_tenant_is_absent_from_audit_note(db: Session) -> None:
    """A 32-character hex tenant matches the slug pattern and is still not stored."""
    assert len(_OPAQUE_HEX_TENANT) == 32
    assert re.fullmatch(r"[0-9a-f]{32,}", _OPAQUE_HEX_TENANT)
    assert re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", _OPAQUE_HEX_TENANT)
    assert re.search(r"sk-[A-Za-z0-9_\-]{8,}", _OPAQUE_HEX_TENANT) is None
    registry = AllowListRegistry()
    result = refuse_bot_allow_list_tool_call(
        db,
        registry,
        actor="worker_bot",
        tenant=_OPAQUE_HEX_TENANT,
        op_type="mail_template.create",
        tool_name="l4.allow_list.add",
        run_id=_RUN_ID,
    )
    assert result.refused is True
    assert result.recorded is False
    assert result.auto_applied is False
    assert registry.ops(_OPAQUE_HEX_TENANT) == frozenset()

    row = db.query(AuditChainEntry).one()
    assert row.kind == "note"
    assert row.actor == BOT_AUDIT_ACTOR
    payload = json.loads(row.payload_json)
    assert payload["tenant"] == "unlisted"
    assert _OPAQUE_HEX_TENANT not in row.payload_json


def test_template_that_adds_an_op_is_not_auto_applied() -> None:
    registry = AllowListRegistry()
    record_allow_list_change(
        registry,
        role="owner",
        tenant=_TENANT,
        op_type="field.update",
        admin_id="owner-1",
    )
    before = registry.ops(_TENANT)
    changeset = [
        {
            "type": "l4_allow_list.add",
            "params": {
                "op_type": "mail_template.create",
                "api_key": _SECRET,
            },
        },
        {
            "type": "mail_template.create",
            "params": {
                "allow_list_add": "access.create",
                "password": _SECRET_IN_ARGS,
            },
        },
    ]
    result = template_allow_list_change(registry, changeset, tenant=_TENANT)
    assert result.recorded is False
    assert result.auto_applied is False
    assert result.refused is True
    assert result.reason == "template_not_auto_applied"
    assert registry.ops(_TENANT) == before
    assert "mail_template.create" not in registry.ops(_TENANT)
    assert "access.create" not in registry.ops(_TENANT)
    assert (
        l4_may_apply(
            risk="R1",
            op_type="mail_template.create",
            rows=1,
            mode_t=True,
            staging_verified=True,
            allow_list=registry.ops(_TENANT),
            **_VERIFIED_STAGING,
        )
        is False
    )


def test_template_without_allow_list_edit_does_not_record() -> None:
    registry = AllowListRegistry()
    result = template_allow_list_change(
        registry,
        [{"type": "mail_template.create", "params": {"name": "Hello"}}],
        tenant=_TENANT,
    )
    assert result.recorded is False
    assert result.auto_applied is False
    assert result.refused is False
    assert result.reason == "no_allow_list_edit"
    assert registry.ops(_TENANT) == frozenset()


def test_unrelated_tool_is_not_an_allow_list_edit() -> None:
    assert is_allow_list_edit_tool("describe_model", {"model": "sale.order"}) is False
