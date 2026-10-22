"""The ONE staleness rule for Odoo schema reads (odoo_snapshot cache and ai_schema_client catalogs).

A schema read older than SCHEMA_TTL_S is stale: callers re-read (snapshot) or deny the
schema-verified path (catalog). Apply always re-reads with ttl=0 regardless (design_admission).
"""

from __future__ import annotations

import time

SCHEMA_TTL_S = 300.0


def is_fresh(captured_at: float | None, *, now: float | None = None, ttl_s: float = SCHEMA_TTL_S) -> bool:
    if captured_at is None:
        return False
    return ((time.time() if now is None else now) - float(captured_at)) <= ttl_s
