"""Canonical hash of a schema slice. Volatile ids are not part of the hash."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def schema_fingerprint(slice_data: dict[str, Any]) -> str:
    cleaned = {key: value for key, value in slice_data.items() if key not in {"id", "write_date", "create_date"}}
    canonical = json.dumps(cleaned, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
