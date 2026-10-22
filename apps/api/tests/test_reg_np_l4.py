"""REG-NP-L4: pin GATE-L4-01, 02, 03, 04, 11, and 12. L4 stays off."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.changeset.ops import OP_CATALOG
from app.changeset.protected_registry import protection_level
from app.db_models import AuditChainEntry
from app.worker_bot.l4_policy import (
    L4_ALLOW_LIST_REFUSED,
    L4_NOT_ON_ALLOW_LIST,
    L4_OUTBOUND,
    L4_R2_DDL,
    AllowListRegistry,
    StagingApplyRecord,
    _l4_gate_02_refuses,
    l4_gate_01_refusal,
    l4_gate_03_allows,
    l4_may_apply,
    record_allow_list_change,
    refuse_bot_allow_list_tool_call,
    template_allow_list_change,
)
from app.worker_bot.runtime import WorkerBot
from app.worker_bot.standing_rule import StandingRuleBook

pytestmark = pytest.mark.no_app_db

_TENANT = "tenant-a"
_PLAN_HASH = "abcdef0123456789"
_OTHER_HASH = "0123456789abcdef"
_EVERY_OP = frozenset(OP_CATALOG)
_OWNER = "user-owner"
_ADMIN = "user-admin"
_OTHER = "user-other"


def _verified(plan_hash: str = _PLAN_HASH, *, verified: bool = True) -> StagingApplyRecord:
    return StagingApplyRecord(plan_hash=plan_hash, verified=verified)


def _may(
    op_type: str,
    *,
    risk: str,
    allow_list: frozenset[str] | set[str],
    params: dict | None = None,
    model: str = "",
    method: str = "",
    plan_mode: str = "T",
    plan_hash: str = _PLAN_HASH,
    staging_applies: list[StagingApplyRecord] | None = None,
    mode_t: bool = True,
    staging_verified: bool = True,
) -> bool:
    return l4_may_apply(
        risk=risk,
        op_type=op_type,
        rows=1,
        mode_t=mode_t,
        staging_verified=staging_verified,
        model=model,
        method=method,
        params=params,
        allow_list=allow_list,
        plan_mode=plan_mode,
        plan_hash=plan_hash,
        staging_applies=[_verified()] if staging_applies is None else staging_applies,
    )


@pytest.fixture
def audit_db() -> Session:
    engine = create_engine("sqlite://")
    AuditChainEntry.__table__.create(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_ac1_listed_r1_and_non_ddl_r2_pass_gate_01() -> None:
    listed = frozenset({"mail_template.create"})
    assert l4_gate_01_refusal(op_type="mail_template.create", allow_list=listed) is None
    assert _may("mail_template.create", risk="R1", allow_list=listed) is True

    report = {"model": "sale.order", "name": "Inherit the quotation report"}
    report_listed = frozenset({"report.inherit"})
    assert OP_CATALOG["report.inherit"].ddl is False
    assert protection_level({"type": "report.inherit", "params": report}) is None
    assert l4_gate_01_refusal(op_type="report.inherit", params=report, allow_list=report_listed) is None
    assert _may("report.inherit", risk="R2", params=report, allow_list=report_listed) is True


def test_ac1_off_list_ddl_and_outbound_are_refused() -> None:
    listed = frozenset({"mail_template.create"})
    assert l4_gate_01_refusal(op_type="view.archive", allow_list=listed) == L4_NOT_ON_ALLOW_LIST
    assert _may("view.archive", risk="R1", allow_list=listed) is False

    ddl_params = {"model": "x_m", "name": "x_note", "field_type": "char"}
    for op_type in ("field.create", "model.create", "model.scaffold"):
        assert OP_CATALOG[op_type].ddl is True
        own_list = frozenset({op_type})
        assert (
            l4_gate_01_refusal(op_type=op_type, params=ddl_params, allow_list=own_list) == L4_R2_DDL
        )
        assert _may(op_type, risk="R2", params=ddl_params, allow_list=own_list) is False

    automation_listed = frozenset({"automation.create"})
    for email_params in (
        {"model": "sale.order", "name": "Mail the customer", "actions": [{"state": "email"}]},
        {
            "model": "sale.order",
            "name": "Mail the customer",
            "action_kind": "mail_post",
            "mail_post_method": "email",
        },
    ):
        assert (
            l4_gate_01_refusal(
                op_type="automation.create",
                params=email_params,
                allow_list=automation_listed,
            )
            == L4_OUTBOUND
        )
        assert (
            _may(
                "automation.create",
                risk="R2",
                params=email_params,
                allow_list=automation_listed,
            )
            is False
        )


def test_ac2_listed_r1_is_not_a_gate_02_refusal() -> None:
    listed = frozenset({"mail_template.create"})
    assert (
        _l4_gate_02_refuses(risk="R1", op_type="mail_template.create", params=None) is False
    )
    assert _may("mail_template.create", risk="R1", allow_list=listed) is True


def test_ac2_r3_r4_module_promote_and_elevate_are_refused() -> None:
    benign = frozenset({"mail_template.create"})
    for risk in ("R3", "R4"):
        assert _l4_gate_02_refuses(risk=risk, op_type="mail_template.create", params=None) is True
        assert _may("mail_template.create", risk=risk, allow_list=benign) is False

    module_params = {"module": "sale"}
    modules = frozenset({"module.install", "module.upgrade", "module.uninstall"})
    for op_type in modules:
        assert _l4_gate_02_refuses(risk="R1", op_type=op_type, params=module_params) is True
        assert _may(op_type, risk="R1", params=module_params, allow_list=modules) is False

    promote_listed = frozenset({"promote", "mail_template.create"})
    assert _l4_gate_02_refuses(risk="R1", op_type="promote", params=None) is True
    assert _may("promote", risk="R1", allow_list=promote_listed) is False

    elevated = {"model": "product.category", "name": "x_shelf"}
    assert protection_level({"type": "field.update", "params": elevated}) == "elevate"
    elevate_listed = frozenset({"field.update"})
    assert _l4_gate_02_refuses(risk="R1", op_type="field.update", params=elevated) is True
    assert _may("field.update", risk="R1", params=elevated, allow_list=elevate_listed) is False


def test_ac3_mode_t_same_verified_staging_hash_allows() -> None:
    record = StagingApplyRecord(plan_hash=_PLAN_HASH, verified=True)
    assert (
        l4_gate_03_allows(mode="T", plan_hash=_PLAN_HASH, staging_applies=[record]) is True
    )
    assert (
        _may(
            "mail_template.create",
            risk="R1",
            allow_list=frozenset({"mail_template.create"}),
            staging_applies=[record],
        )
        is True
    )


def test_ac3_mode_c_unverified_other_hash_or_flags_alone_refuse() -> None:
    verified = StagingApplyRecord(plan_hash=_PLAN_HASH, verified=True)
    assert l4_gate_03_allows(mode="C", plan_hash=_PLAN_HASH, staging_applies=[verified]) is False
    assert (
        l4_gate_03_allows(
            mode="T",
            plan_hash=_PLAN_HASH,
            staging_applies=[StagingApplyRecord(plan_hash=_PLAN_HASH, verified=False)],
        )
        is False
    )
    assert (
        l4_gate_03_allows(
            mode="T",
            plan_hash=_PLAN_HASH,
            staging_applies=[StagingApplyRecord(plan_hash=_OTHER_HASH, verified=True)],
        )
        is False
    )
    listed = frozenset({"mail_template.create"})
    assert (
        _may(
            "mail_template.create",
            risk="R1",
            allow_list=listed,
            plan_mode="C",
            staging_applies=[verified],
        )
        is False
    )
    assert (
        l4_may_apply(
            risk="R1",
            op_type="mail_template.create",
            rows=1,
            mode_t=True,
            staging_verified=True,
            allow_list=listed,
        )
        is False
    )


def test_ac4_second_distinct_admin_activates_standing_rule() -> None:
    book = StandingRuleBook()
    assert book.open("rule-1").active is False
    assert book.approve("rule-1", {"user_id": _OWNER, "role": "owner"}).active is False
    active = book.approve("rule-1", {"user_id": _ADMIN, "role": "admin"})
    assert active.active is True
    assert active.admin_user_ids == frozenset({_OWNER, _ADMIN})

    owner_pair = StandingRuleBook()
    owner_pair.approve("rule-1", {"user_id": _ADMIN, "role": "admin"})
    assert owner_pair.approve("rule-1", {"user_id": _OWNER, "role": "owner"}).active is True

    with pytest.raises(ValueError, match="invalid autonomy level"):
        WorkerBot("L4")


def test_ac4_same_admin_missing_user_or_two_non_owners_stay_inactive() -> None:
    same = StandingRuleBook()
    same.approve("rule-1", {"user_id": _ADMIN, "role": "admin"})
    again = same.approve("rule-1", {"user_id": _ADMIN, "role": "admin"})
    assert again.active is False
    assert again.admin_user_ids == frozenset({_ADMIN})

    missing = StandingRuleBook()
    missing.approve("rule-1", {"user_id": _OWNER, "role": "owner"})
    omitted = missing.approve("rule-1", {"role": "admin", "label": _ADMIN})
    assert omitted.active is False
    assert omitted.admin_user_ids == frozenset({_OWNER})

    admins = StandingRuleBook()
    admins.approve("rule-1", {"user_id": _ADMIN, "role": "admin"})
    pair = admins.approve("rule-1", {"user_id": _OTHER, "role": "admin"})
    assert pair.active is False
    assert pair.owner_user_ids == frozenset()


def test_ac5_benign_r1_on_the_full_catalog_allow_list_may_apply() -> None:
    assert "mail_template.create" in _EVERY_OP
    assert (
        _may("mail_template.create", risk="R1", allow_list=_EVERY_OP) is True
    )


def test_ac5_users_unlink_apikeys_and_protected_param_are_refused() -> None:
    assert (
        l4_may_apply(
            risk="R1",
            op_type="data.unlink",
            rows=1,
            mode_t=True,
            staging_verified=True,
            model="res.users",
            method="unlink",
            allow_list=_EVERY_OP,
            plan_mode="T",
            plan_hash=_PLAN_HASH,
            staging_applies=[_verified()],
        )
        is False
    )
    assert (
        l4_may_apply(
            risk="R1",
            op_type="data.unlink",
            rows=1,
            mode_t=True,
            staging_verified=True,
            model="res.users.apikeys",
            method="unlink",
            allow_list=_EVERY_OP,
            plan_mode="T",
            plan_hash=_PLAN_HASH,
            staging_applies=[_verified()],
        )
        is False
    )
    assert (
        _may(
            "config_param.set",
            risk="R1",
            allow_list=_EVERY_OP,
            params={"key": "database.secret", "value": "x"},
        )
        is False
    )


def test_ac6_human_admin_records_allow_list_without_auto_apply() -> None:
    registry = AllowListRegistry()
    result = record_allow_list_change(
        registry,
        role="admin",
        tenant=_TENANT,
        op_type="mail_template.create",
        admin_id="admin-1",
    )
    assert result.recorded is True
    assert result.auto_applied is False
    assert registry.ops(_TENANT) == frozenset({"mail_template.create"})


def test_ac6_bot_and_template_cannot_widen_allow_list(audit_db: Session) -> None:
    registry = AllowListRegistry()
    record_allow_list_change(
        registry,
        role="admin",
        tenant=_TENANT,
        op_type="field.update",
        admin_id="admin-1",
    )
    before = registry.ops(_TENANT)
    refused = refuse_bot_allow_list_tool_call(
        audit_db,
        registry,
        actor="worker_bot",
        tenant=_TENANT,
        op_type="mail_template.create",
        tool_name="l4.allow_list.add",
    )
    assert refused.reason == "bot_cannot_widen_allow_list"
    assert refused.auto_applied is False
    assert refused.recorded is False
    assert registry.ops(_TENANT) == before

    row = audit_db.query(AuditChainEntry).one()
    assert row.kind == "note"
    payload = json.loads(row.payload_json)
    assert payload["event"] == L4_ALLOW_LIST_REFUSED

    template = template_allow_list_change(
        registry,
        [{"type": "l4_allow_list.add", "params": {"op_type": "mail_template.create"}}],
        tenant=_TENANT,
    )
    assert template.auto_applied is False
    assert template.recorded is False
    assert template.reason == "template_not_auto_applied"
    assert registry.ops(_TENANT) == before
    assert "mail_template.create" not in registry.ops(_TENANT)
