"""L3 staging autonomy: REVERSIBLE (R0/R1) may apply unsupervised; production pauses."""

from __future__ import annotations

from typing import Any

from app.changeset.setting_ops import may_be_billable

_L3_STAGING_AUTO_RISKS = frozenset({"R0", "R1"})
# Catalog ops that are never unsupervised on staging (aligns with config-as-code destructive set).
_L3_NEVER_UNSUPERVISED = frozenset(
    {
        "data.delete",
        "module.uninstall",
        "data.merge",
    }
)


def l3_staging_may_auto_apply(
    *,
    level: str,
    environment: str,
    max_risk: str,
    changeset: list[dict[str, Any]],
) -> bool:
    """True when WorkerBot may call executor.apply on staging without inbox pause.

    REVERSIBLE here means validated max risk R0 or R1. DESTRUCTIVE (R2+) and
    BILLABLE (paid-edition module or ``module_*`` setting) always pause. Production
    never auto-applies at L3.
    """
    if level != "L3":
        return False
    if environment.lower() != "staging":
        return False
    if max_risk not in _L3_STAGING_AUTO_RISKS:
        return False
    for op in changeset:
        op_type = str(op.get("type", ""))
        if op_type in _L3_NEVER_UNSUPERVISED:
            return False
        params = op.get("params") if isinstance(op.get("params"), dict) else {}
        if may_be_billable(op_type, params, edition="enterprise"):
            return False
        if may_be_billable(op_type, params, edition="odoo_sh"):
            return False
    return True
