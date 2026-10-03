"""L4 stays off unless every gate passes. R3 and module ops never qualify."""

from __future__ import annotations

from app.worker_bot.l4_policy import l4_eligible, l4_may_apply


def test_short_history_is_not_eligible() -> None:
    assert l4_eligible(applies=199, days=60, rollback_rate=0.0, verify_failures=0) is False
    assert l4_eligible(applies=200, days=59, rollback_rate=0.0, verify_failures=0) is False
    assert l4_eligible(applies=200, days=60, rollback_rate=0.02, verify_failures=0) is False
    assert l4_eligible(applies=200, days=60, rollback_rate=0.0, verify_failures=1) is False


def test_full_history_is_eligible() -> None:
    assert l4_eligible(applies=200, days=60, rollback_rate=0.0, verify_failures=0) is True


def test_l4_refuses_r3_modules_and_large_blasts() -> None:
    assert l4_may_apply(risk="R1", op_type="mail_template.create", rows=1, mode_t=True, staging_verified=True)
    assert l4_may_apply(risk="R3", op_type="access.create", rows=1, mode_t=True, staging_verified=True) is False
    assert l4_may_apply(risk="R1", op_type="module.install", rows=1, mode_t=True, staging_verified=True) is False
    assert l4_may_apply(risk="R1", op_type="mail_template.create", rows=51, mode_t=True, staging_verified=True) is False
    assert l4_may_apply(risk="R1", op_type="mail_template.create", rows=1, mode_t=False, staging_verified=True) is False
    assert l4_may_apply(risk="R1", op_type="mail_template.create", rows=1, mode_t=True, staging_verified=False) is False
