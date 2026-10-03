"""Remember a dry-run and refuse the matching live write until one has been seen.

The hash ignores approval fields so a confirm step does not look like a different plan.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from app.plan_fingerprint import structural_dry_run_hash

_IGNORE = frozenset(
    {
        "dry_run",
        "receipt_token",
        "confirm_advanced",
        "confirm_phrase",
        "continue_after_sample",
    }
)
_TTL_S = 15 * 60
_lock = threading.Lock()
_seen: dict[str, float] = {}


class DryRunRequired(Exception):
    """A live write arrived without a matching dry-run in this process."""


def _payload(args: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in args.items() if key not in _IGNORE}


def _key(tool: str, args: dict[str, Any]) -> str:
    return structural_dry_run_hash(tool, _payload(args))


def remember_dry_run(tool: str, args: dict[str, Any]) -> str:
    digest = _key(tool, args)
    now = time.monotonic()
    with _lock:
        _seen[digest] = now + _TTL_S
        stale = [item for item, expiry in _seen.items() if expiry < now]
        for item in stale:
            _seen.pop(item, None)
    return digest


def dry_run_was_seen(tool: str, args: dict[str, Any]) -> bool:
    digest = _key(tool, args)
    now = time.monotonic()
    with _lock:
        expiry = _seen.get(digest)
        if expiry is None:
            return False
        if expiry < now:
            _seen.pop(digest, None)
            return False
        return True


def enforce_dry_run(tool: str, args: dict[str, Any], *, dry_run: bool) -> str:
    """Record a dry-run, or raise DryRunRequired when the live write was not previewed."""
    if dry_run:
        return remember_dry_run(tool, args)
    if not dry_run_was_seen(tool, args):
        raise DryRunRequired(
            f"Run {tool} with dry_run true before the live write. The parameters must match."
        )
    return _key(tool, args)
