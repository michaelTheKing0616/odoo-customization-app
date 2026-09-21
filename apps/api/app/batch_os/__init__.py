"""Config & Batch Operating System — universal runner + atlas + recipes.

Public Odoo ORM/RPC only. Reuses Bulk Suite persistence (bulk_runs) and the
same confirm gate as config_ops / power_ops. Lifecycle:

    intake → map → validate → dry-run → apply → audit
"""

from app.batch_os.types import (
    RISK_TIERS,
    BatchJobState,
    BatchPhase,
    RiskTier,
    RowError,
)

__all__ = [
    "RISK_TIERS",
    "BatchJobState",
    "BatchPhase",
    "RiskTier",
    "RowError",
]
