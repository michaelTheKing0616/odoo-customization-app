"""GATE-L4-03: production L4 needs Mode T and a verified staging apply of the same plan hash.

L4 stays off. This file does not enable a runtime level.
"""

from __future__ import annotations

import pytest

from app.worker_bot.l4_policy import (
    GATE_L4_03,
    StagingApplyRecord,
    l4_gate_03_allows,
    l4_may_apply,
)

pytestmark = pytest.mark.no_app_db

_HASH = "a" * 16
_OTHER = "b" * 16

_OP = {
    "risk": "R1",
    "op_type": "mail_template.create",
    "rows": 1,
    "mode_t": True,
    "staging_verified": True,
}


def _record(
    plan_hash: str = _HASH,
    *,
    verified: bool = True,
    environment: str = "staging",
) -> dict[str, object]:
    return {"plan_hash": plan_hash, "verified": verified, "environment": environment}


def test_gate_id_is_gate_l4_03() -> None:
    assert GATE_L4_03 == "GATE-L4-03"


def test_production_l4_allows_mode_t_when_the_same_hash_was_verified_on_staging() -> None:
    record = _record()
    assert l4_gate_03_allows(mode="T", plan_hash=_HASH, staging_applies=[record]) is True
    assert (
        l4_may_apply(
            **_OP,
            plan_mode="T",
            plan_hash=_HASH,
            staging_applies=[record],
            environment="production",
        )
        is True
    )
    assert (
        l4_may_apply(
            **_OP,
            plan_mode="T",
            plan_hash=_HASH,
            staging_applies=[StagingApplyRecord(plan_hash=_HASH, verified=True)],
            environment="production",
        )
        is True
    )


def test_mode_c_is_refused_on_a_production_l4_decision() -> None:
    record = _record()
    assert l4_gate_03_allows(mode="C", plan_hash=_HASH, staging_applies=[record]) is False
    assert (
        l4_may_apply(
            **_OP,
            plan_mode="C",
            plan_hash=_HASH,
            staging_applies=[record],
            environment="production",
        )
        is False
    )


def test_staging_hash_with_failed_verification_is_refused() -> None:
    failed = _record(verified=False)
    assert l4_gate_03_allows(mode="T", plan_hash=_HASH, staging_applies=[failed]) is False
    assert (
        l4_may_apply(
            **_OP,
            plan_mode="T",
            plan_hash=_HASH,
            staging_applies=[failed],
            environment="production",
        )
        is False
    )


def test_verified_record_for_a_different_hash_is_refused() -> None:
    assert (
        l4_may_apply(
            **_OP,
            plan_mode="T",
            plan_hash=_HASH,
            staging_applies=[_record(_OTHER)],
            environment="production",
        )
        is False
    )


def test_mode_t_and_staging_verified_flags_without_a_staging_record_are_refused() -> None:
    assert (
        l4_may_apply(
            risk="R1",
            op_type="mail_template.create",
            rows=1,
            mode_t=True,
            staging_verified=True,
        )
        is False
    )


def test_production_without_a_staging_record_is_refused() -> None:
    assert (
        l4_may_apply(
            **_OP,
            plan_mode="T",
            plan_hash=_HASH,
            staging_applies=[],
            environment="production",
        )
        is False
    )


def test_a_production_verify_does_not_stand_in_for_staging() -> None:
    assert (
        l4_may_apply(
            **_OP,
            plan_mode="T",
            plan_hash=_HASH,
            staging_applies=[_record(environment="production")],
            environment="production",
        )
        is False
    )
