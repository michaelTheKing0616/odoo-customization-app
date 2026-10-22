"""Secrets vault (item 28): encrypted at rest, names listable, values only ever reach the run's child.

A script reads one with secret("name"); every log line, result and error is scrubbed of the values.
"""

from __future__ import annotations

import re
import time
from typing import Any

from app.code_runner import store
from app.crypto import decrypt_secret, encrypt_secret

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


def _key(workspace: str | None) -> str:
    return f"vault_{workspace or 'local'}"


def names(workspace: str | None) -> list[dict[str, Any]]:
    data = store.load("vault", _key(workspace), {})
    return [{"name": k, "set_by": v.get("by"), "set_at": v.get("at"), "connections": v.get("connections") or []}
            for k, v in sorted(data.items())]


def put(workspace: str | None, name: str, value: str, by: str | None, connections: list[str] | None = None) -> None:
    if not NAME_RE.match(name):
        raise ValueError("Use letters, digits and _ for secret names, starting with a letter.")
    if not value:
        raise ValueError("A secret needs a value.")
    with store.lock():
        data = store.load("vault", _key(workspace), {})
        data[name] = {"v": encrypt_secret(value), "by": by, "at": time.time(), "connections": connections or []}
        store.save("vault", _key(workspace), data)


def delete(workspace: str | None, name: str) -> bool:
    with store.lock():
        data = store.load("vault", _key(workspace), {})
        hit = data.pop(name, None) is not None
        store.save("vault", _key(workspace), data)
    return hit


def for_run(workspace: str | None, connection_id: str, code: str) -> dict[str, str]:
    """Only the secrets this script names, and only those allowed on this connection."""
    wanted = set(re.findall(r"secret\(\s*[\"']([A-Za-z][A-Za-z0-9_]*)[\"']\s*\)", code or ""))
    data = store.load("vault", _key(workspace), {})
    out = {}
    for n in wanted & set(data):
        allowed = data[n].get("connections") or []
        if allowed and connection_id not in allowed:
            continue
        out[n] = decrypt_secret(data[n]["v"])
    return out


def scrub(text: Any, values: list[str]) -> Any:
    if not isinstance(text, str) or not values:
        return text
    for v in sorted(values, key=len, reverse=True):
        if len(v) >= 3:
            text = text.replace(v, "***")
    return text
