"""Plan fingerprint and structural dry-run hashing (Track 5A)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def structural_dry_run_hash(tool: str, args: dict[str, Any]) -> str:
    """SHA-256 hex of canonical JSON for ``{tool, args}`` with ``dry_run`` stripped from args."""
    payload_args = {k: v for k, v in args.items() if k != "dry_run"}
    canonical = json.dumps(
        {"tool": tool, "args": payload_args},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def plan_fingerprint(changes: list[dict[str, Any]]) -> str:
    """SHA-256 of actionable changes (``res_id`` excluded), first 16 hex chars."""
    scrubbed = [{k: v for k, v in change.items() if k != "res_id"} for change in changes]
    canonical = json.dumps(scrubbed, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def fingerprints_match(expected: str, changes: list[dict[str, Any]]) -> bool:
    return plan_fingerprint(changes) == expected
