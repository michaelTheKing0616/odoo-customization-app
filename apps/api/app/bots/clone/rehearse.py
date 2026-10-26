"""Rehearsal route selection, Route B clone, rehearsal records, and the prod-apply gate.

Route B (direct DB access): ``ingenium_clone_<hash>`` via pg_dump | pg_restore (online,
never terminates prod sessions) + filestore copy + new database.uuid + Odoo's own
``odoo neutralize`` + the RPC neutralize read-back. Route A (RPC-only: Online, Odoo.sh,
hosted): a user-supplied copy prepared by rpc_copy. Hosted is never a refusal by itself.

A rehearsal record binds (route, prod fingerprint, target fingerprint, task, plan hash, N,
diff hash, prod state hash, taken_at, walkthrough + read-back). ``apply`` refuses a prod
run unless exactly one matching, passed, unconsumed record <24h old exists for the approved
fingerprint and the prod records are unchanged since; the record is consumed (single use)
before WriteGate.run. Records live in an append-only, hash-chained, fsynced JSONL file
(BOT_REHEARSAL_STORE); a broken chain refuses everything.
"""

from __future__ import annotations

import contextlib
import copy
import dataclasses
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from app.bot_verify.targets import is_disposable
from app.bots.clone import neutralize as nz
from app.bots.clone.fingerprint import Identity, IdentityError, Rpc, fingerprint, read_identity
from app.bots.clone.rpc_copy import FORBIDDEN_PORTS, CopyReport, attach_proof, verify_copy
from app.bots.guard import RunReport, RunSpec, WriteGate, diff_hash, plan_hash
from app.bots.risk.rules import Refusal
from app.database_backup import _normalize_hosting, request_database_backup

Route = Literal["A", "B"]
STALE_S = 24 * 3600
CLONE_RX = re.compile(r"^ingenium_clone_[a-z0-9]{12}$")
_IDENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,62}$")


class RehearsalRefused(Exception):
    def __init__(self, refusal: Refusal) -> None:
        super().__init__(refusal.text())
        self.refusal = refusal


def _no(missing: str, reason: str) -> RehearsalRefused:
    return RehearsalRefused(Refusal("RF-ANY", missing, reason))


# ---------------------------------------------------------------- route ---
def detect_route(*, hosting_hint: str | None, db_probe: Callable[[], bool] | None) -> Route:
    """B only when a direct-DB probe succeeds; Online/Odoo.sh never probe; errors -> A."""
    if _normalize_hosting(hosting_hint) in {"online", "odoo_sh"} or db_probe is None:
        return "A"
    try:
        return "B" if db_probe() is True else "A"
    except Exception:  # noqa: BLE001 - no DB access is Route A, not an error
        return "A"


def state_hash(rpc: Rpc, model: str, ids: Sequence[Any]) -> str:
    """Hash of (id, write_date) of the plan's records on prod; source drift => mismatch."""
    rows = rpc(model, "search_read", [[("id", "in", list(ids))]], {"fields": ["write_date"]})
    seen = sorted((r["id"], str(r.get("write_date"))) for r in rows or [])
    blob = json.dumps({"ids": sorted(ids), "rows": seen}, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


# ------------------------------------------------------------- Route B ---
class ClusterOps(Protocol):
    def sql(self, q: str, db: str = "postgres") -> str: ...
    def dump_restore(self, src: str, dst: str) -> None: ...
    def copy_filestore(self, src: str, dst: str) -> None: ...
    def drop_filestore(self, dst: str) -> None: ...
    def neutralize_cli(self, dst: str) -> None: ...


@dataclass
class LocalOps:
    """psql/pg_dump/pg_restore on a reachable cluster (Route B on a self-hosted server)."""

    host: str
    port: int
    user: str
    password: str
    filestore: Path
    odoo_bin: Sequence[str] = ("odoo",)

    def __post_init__(self) -> None:
        if int(self.port) in FORBIDDEN_PORTS:
            raise RehearsalRefused(Refusal("RF-ANY", "port", f"forbidden port {self.port}"))

    def _run(self, argv: list[str], **kw: Any) -> str:
        env = {**os.environ, "PGPASSWORD": self.password}
        cp = subprocess.run(argv, capture_output=True, text=True, env=env, check=False, **kw)
        if cp.returncode != 0:
            raise RuntimeError(f"{argv[0]} failed rc={cp.returncode}")
        return cp.stdout

    def _c(self) -> list[str]:
        return ["-h", self.host, "-p", str(self.port), "-U", self.user]

    def sql(self, q: str, db: str = "postgres") -> str:
        return self._run(["psql", *self._c(), "-d", db, "-v", "ON_ERROR_STOP=1", "-tAc", q])

    def dump_restore(self, src: str, dst: str) -> None:
        dump = Path(os.environ.get("TMPDIR", "/tmp")) / f"{dst}.dump"
        try:
            self._run(["pg_dump", *self._c(), "-Fc", "--no-owner", "-f", str(dump), src])
            self._run(
                ["pg_restore", *self._c(), "--no-owner", "--exit-on-error", "-d", dst, str(dump)]
            )
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.remove(dump)

    def copy_filestore(self, src: str, dst: str) -> None:
        if (self.filestore / src).is_dir():
            shutil.copytree(self.filestore / src, self.filestore / dst)

    def drop_filestore(self, dst: str) -> None:
        if CLONE_RX.match(dst):
            shutil.rmtree(self.filestore / dst, ignore_errors=True)

    def neutralize_cli(self, dst: str) -> None:
        self._run([*self.odoo_bin, "neutralize", "-d", dst])


def clone_name(src: str, plan: str) -> str:
    return "ingenium_clone_" + hashlib.sha256(f"{src}\0{plan}".encode()).hexdigest()[:12]


class Cloner:
    """Route B. A non-disposable source needs a stored owner approval (``approved(src)``)."""

    def __init__(self, ops: ClusterOps, approved: Callable[[str], bool]) -> None:
        self.ops, self.approved = ops, approved

    def drop(self, name: str) -> None:
        if not CLONE_RX.match(name):
            raise _no("clone", f"refusing to drop non-clone {name!r}")
        self.ops.sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        self.ops.drop_filestore(name)

    def make(self, src: str, plan: str) -> str:
        if not _IDENT.match(src or "") or CLONE_RX.match(src):
            raise _no("clone", "bad source db name")
        try:
            ok = is_disposable(src) or self.approved(src) is True
        except Exception:  # noqa: BLE001 - unreadable approval = no approval
            ok = False
        if not ok:
            raise _no("owner-approval", "cloning a non-disposable DB needs an owner approval row")
        name = clone_name(src, plan)
        self.drop(name)  # leftover from a killed run: retry is idempotent
        try:
            self.ops.sql(f'CREATE DATABASE "{name}"')
            self.ops.dump_restore(src, name)
            self.ops.copy_filestore(src, name)
            new = uuid.uuid4()
            self.ops.sql(
                f"UPDATE ir_config_parameter SET value = '{new}' WHERE key = 'database.uuid'",
                db=name,
            )
            self.ops.neutralize_cli(name)
        except Exception as exc:  # noqa: BLE001 - never leave a half-made clone
            self.drop(name)
            raise _no("clone", f"clone failed: {type(exc).__name__}") from exc
        return name


def prove_clone(rpc: Rpc, prod: Identity, url: str, name: str) -> Identity:
    """Route B: bind a write proof to the clone client (ingenium_clone_*, fp != prod)."""
    tid = read_identity(rpc, url, name, prod.major)
    if not CLONE_RX.match(tid.db_name) or tid.fingerprint == prod.fingerprint:
        raise _no("rehearsal-target", "not a proven ingenium_clone_* database")
    if tid.db_name == prod.db_name:
        raise _no("rehearsal-target", "clone has the production db name")
    attach_proof(rpc, prod, tid, verified=True)
    return tid


# ------------------------------------------------------------- records ---
@dataclass
class RehearsalRecord:
    route: Route
    prod_fp: str
    target_fp: str
    task_id: str
    plan_hash: str
    n_records: int
    diff_hash: str
    state_hash: str
    taken_at: float
    walkthrough_ok: bool
    readback_ok: bool
    target_db: str = ""
    copy_age_s: float | None = None
    backup_note: str = ""
    neutralized: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def passed(self) -> bool:
        ok = self.walkthrough_ok is True and self.readback_ok is True
        return (
            ok
            and bool(self.neutralized)
            and all(v in ("ok", "n/a") for v in self.neutralized.values())
        )


class RehearsalStore:
    """Append-only JSONL, each line chained to the previous by sha256; flock + fsync."""

    def __init__(self, path: str | Path | None = None) -> None:
        default = Path.home() / ".ingenium" / "bot_rehearsal" / "rehearsals.jsonl"
        self.path = Path(path or os.environ.get("BOT_REHEARSAL_STORE") or default)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self, fh: Any) -> list[dict]:
        fh.seek(0)
        out, prev = [], "0" * 64
        for line in fh.read().splitlines():
            row = json.loads(line)
            body = {k: v for k, v in row.items() if k != "h"}
            if body.get("prev") != prev or _h(body) != row.get("h"):
                raise _no("rehearsal-store", "rehearsal store chain broken")
            out.append(body)
            prev = row["h"]
        return out

    def _append(self, fh: Any, rows: list[dict], ev: dict) -> None:
        ev["prev"] = _h_of_last(rows)
        line = json.dumps({**ev, "h": _h(ev)}, sort_keys=True, default=str)
        fh.flush()
        os.write(fh.fileno(), (line + "\n").encode())  # O_APPEND: always at the end
        os.fsync(fh.fileno())

    def _locked(self, fn: Callable[[Any, list[dict]], Any]) -> Any:
        with open(self.path, "a+", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                return fn(fh, self._load(fh))
            except (ValueError, KeyError) as exc:
                raise _no("rehearsal-store", "rehearsal store unreadable") from exc
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def add(self, rec: RehearsalRecord) -> None:
        self._locked(lambda fh, rows: self._append(fh, rows, {"ev": "rehearsal", **asdict(rec)}))

    def records(self) -> tuple[list[RehearsalRecord], set[str]]:
        recs, held = self._locked(lambda fh, rows: _fold(rows))
        return recs, set(held)

    def consume(
        self, check: Callable[[list[RehearsalRecord], set[str]], RehearsalRecord], key: str = ""
    ) -> RehearsalRecord:
        """Pick + consume under one lock (no two prod runs share a rehearsal). The run that
        holds it (same idempotency key: duplicate / resume) may present it again."""

        def go(fh: Any, rows: list[dict]) -> RehearsalRecord:
            recs, held = _fold(rows)
            mine = {i for i, k in held.items() if key and k == key}
            rec = check(recs, set(held) - mine)
            if rec.id not in mine:
                ev = {"ev": "consumed", "id": rec.id, "key": key, "at": time.time()}
                self._append(fh, rows, ev)
            return rec

        return self._locked(go)

    def release(self, rec_id: str, key: str = "") -> None:
        """Rule: WriteGate reserves (consumes) the rehearsal before the job opens, so two prod
        runs can never share it, and releases it only when it refused before any write."""

        def go(fh: Any, rows: list[dict]) -> None:
            if _fold(rows)[1].get(rec_id) == key:
                self._append(fh, rows, {"ev": "released", "id": rec_id, "at": time.time()})

        self._locked(go)


def _h(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def _h_of_last(rows: list[dict]) -> str:
    return _h(rows[-1]) if rows else "0" * 64


def _fold(rows: list[dict]) -> tuple[list[RehearsalRecord], dict[str, str]]:
    names = set(RehearsalRecord.__dataclass_fields__)
    recs = [
        RehearsalRecord(**{k: v for k, v in r.items() if k in names})
        for r in rows
        if r["ev"] == "rehearsal"
    ]
    held: dict[str, str] = {}  # rehearsal id -> idempotency key of the run holding it
    for r in rows:
        if r["ev"] == "consumed":
            held[r["id"]] = r.get("key", "")
        elif r["ev"] == "released":
            held.pop(r["id"], None)
    return recs, held


# ---------------------------------------------------------- rehearsal ---
@dataclass
class Target:
    route: Route
    rpc: Rpc
    url: str
    db_name: str
    neutralized: dict[str, str]
    copy: CopyReport | None = None  # Route A
    prod_rpc: Rpc | None = None  # Route A re-verification


def _readback(rpc: Rpc, model: str, ids: list, values: dict) -> bool:
    rows = rpc(model, "search_read", [[("id", "in", ids)]], {"fields": sorted(values)})
    if len(rows or []) != len(ids):
        return False
    for r in rows:
        for k, v in values.items():
            got = r.get(k)
            got = got[0] if isinstance(got, list) and got and isinstance(v, int) else got
            if got != v:
                return False
    return True


def rehearse(
    *,
    store: RehearsalStore,
    prod_rpc: Rpc,
    prod: Identity,
    target: Target,
    task_id: str,
    model: str,
    ids: Sequence[Any],
    values: dict[str, Any],
    walkthrough: Callable[[Rpc], bool],
    hosting_hint: str | None = None,
) -> RehearsalRecord:
    """Run the plan on the target (never prod), walk it, read it back, store the record."""
    ids = list(dict.fromkeys(ids))
    tid = read_identity(target.rpc, target.url, target.db_name, prod.major)
    if fingerprint(tid) == fingerprint(prod) or tid.db_name == prod.db_name:
        raise _no("rehearsal-target", "refusing to rehearse on production")
    if target.route == "B" and not CLONE_RX.match(tid.db_name):
        raise _no("rehearsal-target", "Route B target is not an ingenium_clone_* DB")
    if target.route == "B":
        attach_proof(target.rpc, prod, tid, verified=True)
    if target.route == "A":
        if target.copy is None or target.prod_rpc is None:
            raise _no("rehearsal-marker", "Route A target was not prepared")
        try:
            verify_copy(target.prod_rpc, target.rpc, target.copy)
        except IdentityError as exc:
            raise RehearsalRefused(exc.refusal) from exc
    try:
        nz.assert_neutralized(target.rpc)
    except nz.NeutralizeError as exc:
        raise _no("clone-neutralize", str(exc)[:180]) from exc
    rec = RehearsalRecord(
        route=target.route,
        prod_fp=fingerprint(prod),
        target_fp=fingerprint(tid),
        task_id=task_id,
        plan_hash=plan_hash(prod.db_name, task_id, model, values, ids),
        n_records=len(ids),
        diff_hash=diff_hash(values),
        state_hash=state_hash(prod_rpc, model, ids),
        taken_at=time.time(),
        walkthrough_ok=False,
        readback_ok=False,
        target_db=tid.db_name,
        copy_age_s=target.copy.copy_age_s if target.copy else None,
        backup_note=request_database_backup(odoo_major=prod.major, hosting_hint=hosting_hint)[
            "message"
        ]
        if target.route == "A"
        else "route B: pg_dump + filestore clone",
        neutralized=dict(target.neutralized),
    )
    try:
        target.rpc(model, "write", [ids, values], None)
        rec.readback_ok = _readback(target.rpc, model, ids, values)
        rec.walkthrough_ok = walkthrough(target.rpc) is True
    except Exception:  # noqa: BLE001 - a failed rehearsal is recorded as failed
        rec.walkthrough_ok = rec.readback_ok = False
    store.add(rec)
    return rec


# ------------------------------------------------------------ prod gate ---
def pick(
    recs: list[RehearsalRecord],
    used: set[str],
    *,
    prod_fp: str,
    task_id: str,
    plan: str,
    n: int,
    dhash: str,
    shash: str,
    now: float,
) -> RehearsalRecord:
    mine = [r for r in recs if r.prod_fp == prod_fp and r.task_id == task_id]
    if not mine:
        raise _no("clone-rehearsal", "no rehearsal for this task on this database")
    match = [r for r in mine if r.plan_hash == plan]
    if not match:
        raise _no("clone-rehearsal", "plan changed after rehearsal")
    r = match[-1]
    if r.id in used:
        raise _no("clone-rehearsal", "rehearsal already used by a production run")
    if not r.passed:
        raise _no("clone-rehearsal", "rehearsal did not pass")
    if not 0 <= now - float(r.taken_at) <= STALE_S:
        raise _no("clone-rehearsal", "rehearsal is stale (>24h) or from the future")
    if r.target_fp == prod_fp or r.n_records != n or r.diff_hash != dhash:
        raise _no("clone-rehearsal", "rehearsal does not match the plan")
    if r.state_hash != shash:
        raise _no("clone-rehearsal", "production records changed since the rehearsal")
    return r


class StoreRehearsals:
    """guard.Rehearsals over a RehearsalStore: WriteGate.run reserves the named rehearsal
    (same prod fp, task, plan hash, record set, diff, unchanged prod state, <24h, passed)."""

    def __init__(
        self, store: RehearsalStore, prod_rpc: Rpc, prod_db: str, now: float | None = None
    ):
        self.store, self.prod_rpc, self.prod_db, self.now = store, prod_rpc, prod_db, now

    def reserve(
        self, spec: RunSpec, model: str, ids: Sequence[Any], values: dict[str, Any]
    ) -> Refusal | None:
        ids = list(dict.fromkeys(ids))
        plan = plan_hash(self.prod_db, spec.task_id, model, values, ids)
        sh = state_hash(self.prod_rpc, model, ids)
        t = time.time() if self.now is None else self.now

        def check(recs: list[RehearsalRecord], used: set[str]) -> RehearsalRecord:
            named = [r for r in recs if r.id == spec.rehearsal_id]
            if not named:
                raise _no("clone-rehearsal", "rehearsal id unknown for this production run")
            return pick(
                named,
                used,
                prod_fp=spec.db_fingerprint,
                task_id=spec.task_id,
                plan=plan,
                n=len(ids),
                dhash=diff_hash(values),
                shash=sh,
                now=t,
            )

        try:
            self.store.consume(check, key=spec.idempotency_key)
        except RehearsalRefused as exc:
            return exc.refusal
        return None

    def release(self, spec: RunSpec) -> None:
        self.store.release(spec.rehearsal_id or "", spec.idempotency_key)


def apply(
    gate: WriteGate,
    store: RehearsalStore,
    spec: RunSpec,
    model: str,
    ids: Sequence[Any],
    values: dict[str, Any],
    *,
    prod_rpc: Rpc,
    prod_url: str,
    prod_db: str,
    major: int,
    approved_fp: str,
    now: float | None = None,
    **run_kw: Any,
) -> RunReport:
    """The prod path: identity == approved target, matching rehearsal, then WriteGate.run."""
    ids = list(dict.fromkeys(ids))
    try:
        prod = read_identity(prod_rpc, prod_url, prod_db, major)
        fp = fingerprint(prod)
        if fp != approved_fp or spec.db_fingerprint != approved_fp:
            raise _no("db-fingerprint", "database fingerprint does not match the approved target")
        plan = plan_hash(prod.db_name, spec.task_id, model, values, ids)
        sh = state_hash(prod_rpc, model, ids)
        t = time.time() if now is None else now
        recs, used = store.records()  # read-only pick: the gate reserves it under lock
        rec = pick(
            recs,
            used,
            prod_fp=fp,
            task_id=spec.task_id,
            plan=plan,
            n=len(ids),
            dhash=diff_hash(values),
            shash=sh,
            now=t,
        )
    except IdentityError as exc:
        return gate._refuse(spec, exc.refusal, len(ids))
    except RehearsalRefused as exc:
        return gate._refuse(spec, exc.refusal, len(ids))
    except Exception as exc:  # noqa: BLE001 - anything unexpected refuses
        return gate._refuse(
            spec, Refusal("RF-ANY", "clone-rehearsal", type(exc).__name__), len(ids)
        )
    g = copy.copy(gate)
    g.rehearsals = StoreRehearsals(store, prod_rpc, prod.db_name, now)
    return g.run(dataclasses.replace(spec, rehearsal_id=rec.id), model, ids, values, **run_kw)
