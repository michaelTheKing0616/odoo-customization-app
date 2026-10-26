"""Database identity: which Odoo DB is this, and is it the approved one (RF-ANY).

fingerprint = sha256(database.uuid, database.create_date, db name, URL host:port, major).
Identity is read over RPC from ir.config_parameter; a missing or blank value is a refusal,
never a default. Odoo Online "Duplicate" keeps database.uuid, so a copy is told apart from
prod by db name/host and the rehearsal marker (rpc_copy), not by uuid alone.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from app.bots.risk.rules import Refusal

MARKER_KEY = "ingenium.rehearsal_copy"
MAJORS = frozenset({17, 18, 19, 20})

Rpc = Callable[[str, str, Sequence[Any], dict[str, Any] | None], Any]


class IdentityError(Exception):
    def __init__(self, refusal: Refusal) -> None:
        super().__init__(refusal.text())
        self.refusal = refusal


def refuse(missing: str, reason: str) -> IdentityError:
    return IdentityError(Refusal("RF-ANY", missing, reason))


@dataclass(frozen=True)
class Identity:
    uuid: str
    create_date: str
    db_name: str
    host: str  # normalised host:port
    major: int

    @property
    def fingerprint(self) -> str:
        return fingerprint(self)


def norm_host(url: str) -> str:
    """Lower-case, IDNA, no trailing dot, explicit port: 'HTTPS://Prod.Example.' == ':443'."""
    p = urlsplit(str(url or "").strip())
    if p.scheme not in ("http", "https") or not p.hostname:
        raise refuse("db-fingerprint", "bad url")
    try:
        host = p.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        port = p.port or (443 if p.scheme == "https" else 80)
    except (UnicodeError, ValueError) as exc:
        raise refuse("db-fingerprint", "bad url host") from exc
    return f"{host}:{port}"


def fingerprint(i: Identity) -> str:
    blob = [i.uuid, i.create_date, i.db_name, i.host, int(i.major)]
    return hashlib.sha256(json.dumps(blob).encode()).hexdigest()


def get_param(rpc: Rpc, key: str) -> str | None:
    rows = rpc("ir.config_parameter", "search_read", [[("key", "=", key)]], {"fields": ["value"]})
    if not rows:
        return None
    if len(rows) != 1:
        raise refuse("db-fingerprint", f"ambiguous parameter {key}")
    v = rows[0].get("value")
    return str(v) if v not in (None, False, "") else None


def set_param(rpc: Rpc, key: str, value: str | None) -> None:
    from app.bots.clone.rpc_copy import rpc_write  # lazy: rpc_copy imports this module

    ids = rpc("ir.config_parameter", "search", [[("key", "=", key)]], None)
    if value is None:
        if ids:
            rpc_write(rpc, "ir.config_parameter", "unlink", [ids])
    elif ids:
        rpc_write(rpc, "ir.config_parameter", "write", [ids, {"value": value}])
    else:
        rpc_write(rpc, "ir.config_parameter", "create", [{"key": key, "value": value}])


def read_identity(rpc: Rpc, url: str, db_name: str, major: int) -> Identity:
    if int(major) not in MAJORS:
        raise refuse("version", f"Odoo {major} outside 17-20")
    if not db_name:
        raise refuse("db-fingerprint", "no db name")
    try:
        uid, cdate = get_param(rpc, "database.uuid"), get_param(rpc, "database.create_date")
    except IdentityError:
        raise
    except Exception as exc:  # noqa: BLE001 - unreadable identity is a refusal
        raise refuse("db-fingerprint", f"identity unreadable: {type(exc).__name__}") from exc
    if not uid or not cdate:
        raise refuse("db-fingerprint", "database.uuid/create_date missing")
    return Identity(uid, cdate, str(db_name), norm_host(url), int(major))


def check_target(prod: Identity, target: Identity) -> None:
    """A rehearsal target must provably not be prod (raises IdentityError)."""
    if fingerprint(prod) == fingerprint(target):
        raise refuse("rehearsal-target", "rehearsal target is the production database")
    if prod.db_name == target.db_name:
        raise refuse("rehearsal-target", "same db name as production (alias or proxy?)")
    if prod.major != target.major:
        raise refuse("rehearsal-target", f"copy is Odoo {target.major}, prod is {prod.major}")
