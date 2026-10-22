"""Small JSON file store for code-runner data (library, vault, settings), outside the repo.

Writes are atomic (temp file + rename) and serialised by one lock per process.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

_lock = threading.RLock()


def root() -> Path:
    d = Path(os.environ.get("INGENIUM_CODE_RUNNER_DIR") or Path.home() / ".ingenium" / "code_runner")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(kind: str, key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key or "default")[:120]
    d = root() / kind
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe}.json"


def load(kind: str, key: str, default: Any) -> Any:
    p = _path(kind, key)
    with _lock:
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text())
        except ValueError:
            return default


def save(kind: str, key: str, value: Any) -> None:
    p = _path(kind, key)
    with _lock:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, default=str))
        os.chmod(tmp, 0o600)
        tmp.replace(p)


def lock() -> threading.RLock:
    return _lock
