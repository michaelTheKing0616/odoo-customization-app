"""L4 is a checked policy, not an enabled default. Thresholds match the locks file."""

from __future__ import annotations

L4_MIN_APPLIES = 200
L4_MIN_DAYS = 60
L4_MAX_ROLLBACK = 0.01
L4_MAX_BLAST = 50
L4_ALLOWED_RISKS = frozenset({"R0", "R1"})


def l4_eligible(*, applies: int, days: int, rollback_rate: float, verify_failures: int) -> bool:
    return (
        applies >= L4_MIN_APPLIES
        and days >= L4_MIN_DAYS
        and rollback_rate <= L4_MAX_ROLLBACK
        and verify_failures == 0
    )


def l4_may_apply(*, risk: str, op_type: str, rows: int, mode_t: bool, staging_verified: bool) -> bool:
    if not mode_t or not staging_verified:
        return False
    if risk not in L4_ALLOWED_RISKS:
        return False
    if op_type.startswith("module.") or op_type in {"data.delete", "module.uninstall"}:
        return False
    if rows > L4_MAX_BLAST:
        return False
    return True
