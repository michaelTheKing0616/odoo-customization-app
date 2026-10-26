"""Route A: rehearse on a user-supplied copy (Online "Duplicate", Odoo.sh staging) over RPC.

Order (each step fail-closed, nothing is written to prod):
1. read both identities; copy must differ from prod (fingerprint, db name, same major);
2. prod must carry no ``ingenium.rehearsal_copy`` marker (a marker on prod = confusion);
3. write a fresh nonce marker to the copy, read it back on the copy, and verify it is still
   absent on prod (an alias of prod would show it; it is then removed and we refuse);
4. neutralize the copy over RPC and read every item back (neutralize.py).
Transport is JSON-RPC (``/jsonrpc``) only: no XML-RPC on any major, so Odoo 20 is served.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from app.bots.clone import neutralize as nz
from app.bots.clone.fingerprint import (
    MARKER_KEY,
    Identity,
    IdentityError,
    Rpc,
    check_target,
    get_param,
    norm_host,
    read_identity,
    refuse,
    set_param,
)

FORBIDDEN_PORTS = frozenset({3002, 8001, 8002, 8012, 5433, 5436, 11434, 54329}) | frozenset(
    range(8069, 8074)
)


class RpcError(Exception):
    pass


class JsonRpc:
    """Minimal JSON-RPC client (stdlib). ``call`` matches guard.Rpc."""

    def __init__(self, url: str, db: str, login: str, password: str, timeout: float = 60) -> None:
        p = urlsplit(url)
        port = p.port or (443 if p.scheme == "https" else 80)
        if p.scheme not in ("http", "https") or port in FORBIDDEN_PORTS:
            raise RpcError(f"refused endpoint port {port}")
        self.url, self.db, self.timeout = url.rstrip("/"), db, timeout
        self._pw, self.login = password, login
        self.uid = self._rpc("common", "authenticate", [db, login, password, {}])
        if not self.uid:
            raise RpcError("authentication failed")

    def _rpc(self, service: str, method: str, args: list) -> Any:
        body = {"jsonrpc": "2.0", "method": "call", "id": secrets.randbelow(10**9)}
        body["params"] = {"service": service, "method": method, "args": args}
        req = urllib.request.Request(
            f"{self.url}/jsonrpc",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310 - checked scheme
            out = json.loads(r.read())
        if out.get("error"):
            data = out["error"].get("data") or {}
            raise RpcError(str(data.get("name") or out["error"].get("message"))[:200])
        return out.get("result")

    def __call__(self, model: str, method: str, args: Sequence[Any], kw: dict | None = None) -> Any:
        return self._guarded_execute_kw(model, method, args, kw)

    def attach_proof(self, proof: CopyProof) -> None:
        self.proof = proof

    def _require_proof(self, model: str, method: str, args: Sequence[Any]) -> None:
        """Reads always pass. Writes need a proof that THIS client is a non-prod copy/clone:
        pending = identity checked, only the marker nonce may be written; verified = any."""
        if method in READ_METHODS:
            return
        pr: CopyProof | None = getattr(self, "proof", None)
        if pr is None or not hmac.compare_digest(pr.mac, _mac(pr)):
            raise RpcError(
                "write refused: no verified copy proof (missing or not minted by attach_proof)"
            )
        if not pr.copy_fp or pr.copy_fp == pr.prod_fp:
            raise RpcError("write refused: no verified copy fingerprint")
        if (pr.db_name, pr.host) != (self.db, norm_host(self.url)) or pr.db_name == pr.prod_db:
            raise RpcError("write refused: client is not the proven copy")
        if pr.verified:
            return
        a = list(args)
        ok = model == "ir.config_parameter" and (
            (method == "create" and a[:1] == [{"key": MARKER_KEY, "value": pr.nonce}])
            or (
                method == "write"
                and len(a) == 2
                and a[1] == {"value": pr.nonce}
                and a[0] == self._marker_ids()
            )
            or (method == "unlink" and len(a) == 1 and a[0] == self._marker_ids())
        )
        if not ok:
            raise RpcError("write refused: copy marker not verified yet")

    def _marker_ids(self) -> list:
        return list(
            self._guarded_execute_kw(
                "ir.config_parameter", "search", [[("key", "=", MARKER_KEY)]], None
            )
        )

    def _guarded_execute_kw(
        self, model: str, method: str, args: Sequence[Any], kw: dict | None
    ) -> Any:
        """The only execute_kw call site (pinned by test_nf_bot_kill_audit)."""
        self._require_proof(model, method, args)
        return self._rpc(
            "object",
            "execute_kw",
            [self.db, self.uid, self._pw, model, method, list(args), kw or {}],
        )


WRITE_METHODS = frozenset({"write", "create", "unlink"})


def rpc_write(
    rpc: Rpc, model: str, method: str, args: Sequence[Any], kw: dict | None = None
) -> Any:
    """The single entry point for clone/copy writes under app/bots/clone. A JsonRpc target
    routes through _guarded_execute_kw, so the verified copy proof is required."""
    if method not in WRITE_METHODS:
        raise RpcError(f"rpc_write: {method!r} is not a write method")
    return rpc(model, method, list(args), kw)


READ_METHODS = frozenset({"search", "search_read", "search_count", "read", "fields_get"})
# Process-held key: only attach_proof() below can mint a proof the wrapper accepts.
_PROOF_KEY = secrets.token_bytes(32)


def _mac(p: CopyProof) -> str:
    body = json.dumps([p.prod_fp, p.prod_db, p.copy_fp, p.db_name, p.host, p.nonce, p.verified])
    return hmac.new(_PROOF_KEY, body.encode(), hashlib.sha256).hexdigest()


@dataclass
class CopyProof:
    prod_fp: str
    prod_db: str
    copy_fp: str
    db_name: str
    host: str
    nonce: str = ""
    verified: bool = False
    mac: str = ""


def attach_proof(
    rpc: Rpc, prod: Identity, target: Identity, nonce: str = "", verified: bool = False
) -> None:
    """Bind a write proof to a JsonRpc target (no-op for other callables, e.g. test fakes)."""
    if isinstance(rpc, JsonRpc):
        p = CopyProof(
            prod.fingerprint,
            prod.db_name,
            target.fingerprint,
            target.db_name,
            target.host,
            nonce,
            verified,
        )
        p.mac = _mac(p)
        rpc.attach_proof(p)


@dataclass
class CopyReport:
    prod: Identity
    copy: Identity
    nonce: str
    neutralized: dict[str, str] = field(default_factory=dict)
    copy_age_s: float | None = None


def _age_s(create_date: str) -> float | None:
    try:
        return max(
            0.0, time.time() - time.mktime(time.strptime(create_date[:19], "%Y-%m-%d %H:%M:%S"))
        )
    except ValueError:
        return None


def prepare_copy(
    prod_rpc: Rpc,
    prod_url: str,
    prod_db: str,
    copy_rpc: Rpc,
    copy_url: str,
    copy_db: str,
    major: int,
) -> CopyReport:
    """Prove the copy is not prod, mark it, neutralize it (IdentityError / NeutralizeError)."""
    prod = read_identity(prod_rpc, prod_url, prod_db, major)
    copy = read_identity(copy_rpc, copy_url, copy_db, major)
    check_target(prod, copy)
    if get_param(prod_rpc, MARKER_KEY) is not None:
        raise refuse("rehearsal-marker", "rehearsal marker found on production: refusing")
    nonce = secrets.token_hex(16)
    attach_proof(copy_rpc, prod, copy, nonce)  # pending: only the marker may be written
    set_param(copy_rpc, MARKER_KEY, nonce)
    on_prod = get_param(prod_rpc, MARKER_KEY)
    if on_prod is not None:
        if on_prod == nonce:  # the "copy" is prod under another name: undo our one param
            set_param(copy_rpc, MARKER_KEY, None)  # same storage; prod client never writes
        raise refuse("rehearsal-marker", "marker written to copy appeared on production")
    if get_param(copy_rpc, MARKER_KEY) != nonce:
        raise refuse("rehearsal-marker", "marker read-back on copy failed")
    attach_proof(copy_rpc, prod, copy, nonce, verified=True)
    rep = CopyReport(prod, copy, nonce, copy_age_s=_age_s(copy.create_date))
    rep.neutralized = nz.neutralize_and_check(copy_rpc)
    verify_copy(prod_rpc, copy_rpc, rep)
    return rep


def verify_copy(prod_rpc: Rpc, copy_rpc: Rpc, rep: CopyReport) -> None:
    """Re-check right before every rehearsal write (identity can change under us)."""
    try:
        if get_param(prod_rpc, MARKER_KEY) is not None:
            raise refuse("rehearsal-marker", "marker present on production")
        if get_param(copy_rpc, MARKER_KEY) != rep.nonce:
            raise refuse("rehearsal-marker", "copy marker missing or changed")
        now = read_identity(copy_rpc, f"http://{rep.copy.host}", rep.copy.db_name, rep.copy.major)
    except IdentityError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise refuse("rehearsal-marker", f"marker unreadable: {type(exc).__name__}") from exc
    if (now.uuid, now.create_date) != (rep.copy.uuid, rep.copy.create_date):
        raise refuse("rehearsal-target", "copy identity changed since preparation")


def remove_marker(copy_rpc: Rpc) -> None:
    """Rollback step: drop the marker from a copy."""
    set_param(copy_rpc, MARKER_KEY, None)
