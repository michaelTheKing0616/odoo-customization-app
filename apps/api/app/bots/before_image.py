"""Route A (RPC-only targets): before-image capture, reverse-write undo, batch-1 undo proof.

JSON-RPC only (Odoo 20 has no XML-RPC): every read/write goes through the injected ``Rpc``
callables (``rpc_copy.JsonRpc`` for reads, the gate's writer for writes).

Plug-in for ``guard.WriteGate.run`` (``before_image`` / ``readback`` / ``undo``):

* ``before_image(chunk)`` reads every id x every diff field (+ write_date), at most 50 per
  batch and the plan's N per run, stores it content-addressed (``bi:<sha256 split by ':'>``; the ref
  goes in the audit intent row) and refuses any batch after the first until undo is proven.
* ``readback(chunk)`` compares to the diff. On batch 1 it also runs the proof: undo ->
  read back == before-image -> re-apply -> read back == diff. Any mismatch returns False, so
  the gate trips the kill switch, auto-undoes and refuses the rest of the run.
* ``undo(image)`` loads and re-hashes the stored image (tamper/staleness/other plan =
  refused), skips records already restored (resume after an RPC drop is idempotent), and
  refuses records whose write_date or values changed since our apply (flagged for a human).

Fields whose reverse write cannot restore them (one2many, related, computed, non-stored,
readonly) make the plan irreversible: ``Irreversible`` -> L3 path, never an 'undo' claim.
Irrecoverable classes (posted moves, validated stock, sent mail/EDI/payments, deletes) have
no reverse op in ``REVERSE_OPS`` and are never covered here.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.bots.audit import AuditError
from app.bots.risk.rules import BATCH_CAP

Rpc = Callable[[str, str, Sequence[Any], dict | None], Any]
IMAGE_MAX_AGE_S = 24 * 3600
_KEY = secrets.token_bytes(32)  # proof tokens are minted only in this process
_ATTRS = ["type", "store", "readonly", "related", "relation", "depends"]
BIN_CAP = 25 * 1024 * 1024  # base64 chars per binary value in a before-image
META = frozenset(
    {"id", "write_date", "write_uid", "create_date", "create_uid", "__last_update", "display_name"}
)
# Chatter/audit-trail one2manys: an append-only log (tracking messages are written by our
# own apply AND our undo), not record state, so they are not part of the image.
LOG_RELATIONS = frozenset(
    {"mail.message", "mail.followers", "mail.activity", "mail.tracking.value", "rating.rating"}
)
_TYPE_OP = {"many2many": "m2m", "one2many": "o2m", "many2one": "m2o", "binary": "bin"}


class Irreversible(ValueError):
    """No reverse op: the task is reclassified irreversible (L3 path)."""


class UndoRefused(AuditError):
    """Undo or proof precondition failed; the gate must not write further."""


# ---------------------------------------------------------------- reversibility table (AC2)
def _created(ctx: Mapping[str, Any]) -> str | None:
    if ctx.get("has_dependents") is None:
        return None  # unknown dependents: not provably reversible
    return "archive" if ctx["has_dependents"] else "unlink"


REVERSE_OPS: dict[str, Callable[[Mapping[str, Any]], str | None]] = {
    "write": lambda c: "restore-values",
    "create": _created,
    "archive": lambda c: "unarchive",
    "unarchive": lambda c: "archive",
    "config_param": lambda c: "restore-values" if c.get("existed") else "unlink",
    "metadata": lambda c: "restore-values" if c.get("existed") else "unlink",
    # no reverse by RPC: posted moves, validated stock, sent mail/EDI/payment, delete/merge,
    # company/tax/sequence with transactions, module uninstall, lockout
    "post": lambda c: None,
    "validate_stock": lambda c: None,
    "send": lambda c: None,
    "unlink": lambda c: None,
    "merge": lambda c: None,
    "uninstall": lambda c: None,
    "company_change": lambda c: None if c.get("transactions_exist", True) else "restore-values",
    "lockout": lambda c: None,
}


def reverse_op(kind: str, ctx: Mapping[str, Any] | None = None) -> str:
    fn = REVERSE_OPS.get(kind)
    op = fn(ctx or {}) if fn else None
    if op is None:
        raise Irreversible(f"no reverse op for {kind!r}: reclassified irreversible (L3)")
    return op


def field_ops(rpc: Rpc, model: str, fields: Sequence[str]) -> dict[str, str]:
    """Per-field reverse write kind; raises ``Irreversible`` for any field it cannot restore."""
    meta = rpc(model, "fields_get", [list(fields)], {"attributes": _ATTRS})
    ops, bad = {}, []
    for f in fields:
        m = meta.get(f)
        if not m:
            bad.append(f"{f}: unknown")
            continue
        t = m.get("type")
        if t == "one2many" or m.get("related") or m.get("depends") or m.get("store") is False:
            bad.append(f"{f}: {t} computed/related/non-stored")
        elif m.get("readonly"):
            bad.append(f"{f}: readonly")
        else:
            ops[f] = {"many2many": "m2m", "many2one": "m2o", "binary": "bin"}.get(t, "set")
    if bad:
        raise Irreversible("reverse write cannot restore " + "; ".join(sorted(bad)))
    return ops


def full_fields(rpc: Rpc, model: str) -> tuple[dict[str, str], dict[str, str]]:
    """Every stored field of ``model`` (fields_get per version): (writable, compare-only).
    Compare-only = stored but readonly/computed/related/one2many: captured and verified
    after undo (restored through their inputs), never written directly."""
    meta = rpc(model, "fields_get", [[]], {"attributes": _ATTRS}) or {}  # [] = all fields
    w, c = {}, {}
    for f, m in meta.items():
        if f in META or m.get("store") is False or m.get("relation") in LOG_RELATIONS:
            continue
        t = m.get("type")
        op = _TYPE_OP.get(t, "set")
        ro = t == "one2many" or m.get("readonly") or m.get("related") or m.get("depends")
        (c if ro else w)[f] = op
    return w, c


def _norm(op: str, v: Any) -> Any:
    if op == "o2m":
        return sorted(v or [])
    if op == "m2o":
        return v[0] if isinstance(v, list | tuple) and v else (v or False)
    if op == "m2m":
        if isinstance(v, list | tuple) and v and isinstance(v[0], list | tuple):
            cmd = v[-1]  # plain (6, 0, ids) only; anything else is not comparable
            return sorted(cmd[2]) if cmd[0] == 6 else ("cmd", json.dumps(v))
        return sorted(v or [])
    return v


def _wval(op: str, v: Any) -> Any:
    return [(6, 0, list(v))] if op == "m2m" else v


# ---------------------------------------------------------------- content-addressed images
@dataclass(frozen=True)
class Image:
    ref: str
    plan: str
    model: str
    rows: dict[str, dict[str, Any]]  # str(id) -> {field: value, "write_date": ...}
    taken_at: float


class ImageStore:
    """Images hold real field values, so they live outside bot_audit (which stores only the
    ``bi:<sha256 split by ':'>`` ref + payload hash); a file whose bytes no longer hash
    to the ref is refused."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _save(self, name: str, blob: bytes) -> None:
        """0600 files in a 0700 dir: images hold real record values."""
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        p = self.root / name
        if p.exists():
            return
        tmp = self.root / f".{name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(blob)
        os.replace(tmp, p)

    def put(self, payload: dict[str, Any]) -> str:
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        sha = hashlib.sha256(blob).hexdigest()
        self._save(f"{sha}.json", blob)
        return f"bi:{sha[:32]}:{sha[32:]}"  # split: audit refuses 40+ char blobs

    def put_bin(self, b64: str) -> str:
        """Binary values: the image keeps ``sha:<hex>``; the bytes live in <hex>.bin."""
        if len(b64) > BIN_CAP:
            raise UndoRefused(f"snapshot-proof: binary value over {BIN_CAP} chars")
        sha = hashlib.sha256(b64.encode()).hexdigest()
        self._save(f"{sha}.bin", b64.encode())
        return f"sha:{sha}"

    def get_bin(self, ref: str) -> str:
        sha = ref.removeprefix("sha:")
        try:
            blob = (self.root / f"{sha}.bin").read_bytes()
        except OSError as exc:
            raise UndoRefused("snapshot-proof: binary before-image missing") from exc
        if hashlib.sha256(blob).hexdigest() != sha:
            raise UndoRefused("snapshot-proof: binary before-image tampered")
        return blob.decode()

    def get(self, ref: str) -> dict[str, Any]:
        sha = ref.removeprefix("bi:").replace(":", "")
        try:
            blob = (self.root / f"{sha}.json").read_bytes()
        except OSError as exc:
            raise UndoRefused(f"snapshot-proof: before-image {ref} missing") from exc
        if hashlib.sha256(blob).hexdigest() != sha:
            raise UndoRefused(f"snapshot-proof: before-image {ref} tampered (hash mismatch)")
        return json.loads(blob)


@dataclass(frozen=True)
class UndoProof:
    plan: str
    ref: str
    mac: str


def _proof_mac(plan: str, ref: str) -> str:
    return hmac.new(_KEY, f"{plan}|{ref}".encode(), hashlib.sha256).hexdigest()


def verify_proof(p: UndoProof | None, plan: str) -> bool:
    """True only for a proof minted here by a passing batch-1 proof of this exact plan."""
    return (
        p is not None and p.plan == plan and hmac.compare_digest(p.mac, _proof_mac(p.plan, p.ref))
    )


@dataclass
class UndoResult:
    restored: list[Any] = field(default_factory=list)
    already: list[Any] = field(default_factory=list)
    conflicts: dict[Any, str] = field(default_factory=dict)  # flagged for a human

    @property
    def ok(self) -> bool:
        return not self.conflicts


class RouteA:
    """One approved plan's before-image / proof / undo state for ``WriteGate.run``."""

    def __init__(
        self,
        read: Rpc,
        write: Rpc,
        store: ImageStore,
        *,
        plan: str,
        model: str,
        ids: Sequence[Any],
        values: dict[str, Any],
        switch_check: Callable[[], Any],
        now: Callable[[], float] = time.time,
        max_age_s: float = IMAGE_MAX_AGE_S,
        approval: int = 0,
    ) -> None:
        self.approval = approval  # rule OPR: outside-plan side effects need L2 every batch
        self.read, self.write, self.store = read, write, store
        self.plan, self.model, self.values = plan, model, dict(values)
        self.ids = list(dict.fromkeys(ids))
        self.ops = field_ops(read, model, list(values))  # Irreversible -> L3, before any write
        w, c = full_fields(read, model)
        self.wops = {**w, **self.ops}  # every stored writable field (restored on undo)
        self.allops = {**c, **self.wops}  # + compare-only stored fields (verified on undo)
        self.want = {f: self._bnorm(op, values[f]) for f, op in self.ops.items()}
        self.before_rows: dict[str, dict[str, Any]] = {}
        self.applied: dict[str, dict[str, Any]] = {}  # full image after our own write
        self.side_effects: dict[str, int] = {}  # outside-plan field -> records changed
        self.proven_side: frozenset[str] | None = None
        self.unrestorable: set[str] = set()
        self.switch_check, self.now, self.max_age_s = switch_check, now, max_age_s
        self.proof: UndoProof | None = None
        self.captured: set[Any] = set()
        self.batches = 0
        self.applied_wd: dict[str, Any] = {}  # write_date seen after our own write
        self.conflicts: dict[Any, str] = {}
        self.log: list[str] = []
        self.undone = 0

    # -- reads
    def _bnorm(self, op: str, v: Any) -> Any:
        if op == "bin" and isinstance(v, str) and v and not v.startswith("sha:"):
            return self.store.put_bin(v)
        return _norm(op, v)

    def _read(self, ids: Sequence[Any]) -> dict[str, dict[str, Any]]:
        """Full stored-field image (+ write_date/write_uid, recorded, never compared)."""
        fs = [*self.allops, "write_date", "write_uid"]
        rows = self.read(self.model, "read", [list(ids), fs], {"context": {"bin_size": False}})
        out = {}
        for r in rows:
            row = {f: self._bnorm(op, r.get(f)) for f, op in self.allops.items()}
            row["write_date"], row["write_uid"] = r.get("write_date"), r.get("write_uid")
            out[str(r["id"])] = row
        if len(out) != len(set(ids)):
            raise UndoRefused("snapshot-proof: records missing on read")
        return out

    def _vals(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {f: _norm(op, row.get(f)) for f, op in self.ops.items()}

    def _full(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {f: _norm(op, row.get(f)) for f, op in self.allops.items()}

    def _diff(self, a: Mapping[str, Any], b: Mapping[str, Any]) -> set[str]:
        fa, fb = self._full(a), self._full(b)
        return {f for f in fa if fa[f] != fb[f]}

    @property
    def outside_plan(self) -> frozenset[str]:
        """Fields our apply changed outside the plan (feed diff/blast counts; L2+ review)."""
        return frozenset(self.side_effects)

    @property
    def full_image_ok(self) -> bool:
        return (
            verify_proof(self.proof, self.plan)
            and not self.side_effects
            and not (self.unrestorable)
        )

    def check(self, control: str) -> bool:
        """rules.gate_with_proofs hook: True only once a proof exists for this plan;
        'full-image-proof' also needs no outside-plan changes and nothing unrestorable."""
        if control == "full-image-proof":
            return self.full_image_ok
        return control in ("before-image", "batch1-undo-proof") and verify_proof(
            self.proof, self.plan
        )

    # -- gate hooks
    def before_image(self, chunk: Sequence[Any]) -> tuple[str, Image]:
        chunk = list(chunk)
        if not chunk or len(chunk) > BATCH_CAP:
            raise UndoRefused(f"snapshot-proof: before-image batch {len(chunk)} not 1..50")
        if set(chunk) - set(self.ids) or set(chunk) & self.captured:
            raise UndoRefused("snapshot-proof: chunk outside the plan or captured twice")
        if self.batches >= 1 and not verify_proof(self.proof, self.plan):
            raise UndoRefused("snapshot-proof: undo not proven on batch 1; no further writes")
        rows = self._read(chunk)
        self.before_rows.update(rows)
        payload = {"plan": self.plan, "model": self.model, "rows": rows, "taken_at": self.now()}
        ref = self.store.put(payload)
        self.captured |= set(chunk)
        self.batches += 1
        self._last = Image(ref, self.plan, self.model, rows, payload["taken_at"])
        return ref, self._last

    def readback(self, chunk: Sequence[Any]) -> bool:
        try:
            got = self._read(chunk)
        except Exception as exc:  # noqa: BLE001 - unreadable = mismatch
            self.log.append(f"readback error {type(exc).__name__}")
            return False
        bad = [i for i, r in got.items() if self._vals(r) != self.want]
        if bad:
            self.log.append(f"readback mismatch {bad[:5]}")
            return False
        side = self._note_applied(got)
        if self.proof is None:
            return self._prove(chunk)
        if not side <= (self.proven_side or frozenset()):
            self.log.append(f"unproven outside-plan change {sorted(side)}")
            return False  # later batches: same full-image logic; new side effect = trip
        if side and self.approval < 2:
            self.log.append(f"outside-plan change {sorted(side)[:5]} needs L2 (rule OPR)")
            return False  # OPR re-checked on every batch 2..N, not only pre-run
        return True

    def _note_applied(self, got: Mapping[str, Mapping[str, Any]]) -> set[str]:
        side: set[str] = set()
        for i, r in got.items():
            self.applied_wd[i] = r["write_date"]
            self.applied[i] = dict(r)
            if (b := self.before_rows.get(i)) is not None:
                side |= self._diff(b, r) - set(self.ops)
        for f in side:
            self.side_effects[f] = self.side_effects.get(f, 0) + sum(
                1
                for i in got
                if i in self.before_rows and f in self._diff(self.before_rows[i], got[i])
            )
        return side

    def _prove(self, chunk: Sequence[Any]) -> bool:
        """Batch 1: undo -> == before-image -> re-apply -> == diff. Mints the proof."""
        if self.batches != 1 or self.last_image is None:
            return False
        img = self.last_image
        t0 = time.monotonic()
        prev = {i: dict(self.applied[i]) for i in map(str, chunk) if i in self.applied}
        first_rec = {i: self._diff(self.before_rows[i], prev[i]) - set(self.ops) for i in prev}
        res = self._undo_result(img, allowed=set(self.side_effects))
        if not res.ok or not res.restored:
            self.log.append(f"proof: undo incomplete {res.conflicts or 'nothing restored'}")
            return False
        for rid in chunk:
            if not self._write_one(rid, self._wvals()):
                return False
        got = self._read(chunk)
        if any(self._vals(r) != self.want for r in got.values()):
            self.log.append("proof: re-apply mismatch")
            return False
        # A side effect counts as ours only if the re-apply reproduced it on that record.
        # Anything else was a person's edit: put their value back, flag it, stop.
        foreign = {
            i: f - (self._diff(self.before_rows[i], got[i]) - set(self.ops))
            for i, f in first_rec.items()
            if i in got
        }
        foreign = {i: f for i, f in foreign.items() if f}
        if foreign:
            for i, fs in foreign.items():
                rid = int(i) if i.isdigit() else i
                self._write_one(rid, self._restore_vals(prev[i], fs), reverse=True)
                self.conflicts[i] = f"outside-plan edit {sorted(fs)[:5]} not ours: human review"
            self.side_effects.clear()
            self._note_applied(self._read(chunk))
            self.log.append(f"proof: foreign edits {sorted(foreign)[:5]} (fail closed)")
            return False
        first = set(self.side_effects)
        self.side_effects.clear()
        side = self._note_applied(got)
        if side != first:
            self.log.append("proof: re-apply side effects differ")
            return False
        self.proven_side = frozenset(side)
        self.undone -= len(res.restored)  # proof round-trip, not a run undo
        self.proof = UndoProof(self.plan, img.ref, _proof_mac(self.plan, img.ref))
        self.log.append(f"proof ok {len(chunk)} in {time.monotonic() - t0:.2f}s")
        return True

    @property
    def last_image(self) -> Image | None:
        return getattr(self, "_last", None)

    def _wvals(self) -> dict[str, Any]:
        return {
            f: self.values[f] if op == "bin" else _wval(op, self.want[f])
            for f, op in self.ops.items()
        }

    def _restore_vals(self, before: Mapping[str, Any], fields: set[str]) -> dict[str, Any]:
        out = {}
        for f in fields & set(self.wops):
            op, v = self.wops[f], before.get(f)
            if op == "bin" and isinstance(v, str) and v.startswith("sha:"):
                v = self.store.get_bin(v)
            out[f] = _wval(op, _norm(op, v))
        return out

    def _write_one(self, rid: Any, vals: dict[str, Any], *, reverse: bool = False) -> bool:
        """The only Odoo write in this module (AST-pinned): kill switch first, one record.
        Forward (re-apply) writes need a clear switch. Reverse writes restore the before-image
        and run after the gate itself tripped the switch, so only an unreadable switch
        state stops them."""
        if self._halted(reverse):
            return False
        self.write(self.model, "write", [[rid], vals], None)
        return True

    def _halted(self, reverse: bool = False) -> bool:
        r = self.switch_check()
        if r is not None and reverse and getattr(r, "missing", "") != "kill-switch-state":
            return False
        if r is not None:
            self.log.append("kill switch on during proof")
            return True
        return False

    def undo(self, image: Image | tuple[str, Any]) -> bool:
        try:
            return self._undo_result(image).ok
        except Exception as exc:  # noqa: BLE001 - failed undo is reported, never raised
            self.log.append(f"undo refused: {exc}")
            return False

    def _undo_result(self, image: Image | Any, allowed: set[str] | None = None) -> UndoResult:
        """Reverse-write the stored before-image. Re-loads the stored bytes (the in-memory
        object is never trusted), refuses stale/other-plan images, skips already-restored
        records and refuses records changed by anyone else since our apply. Restores only
        plan fields and side effects proven ours (``allowed`` during the proof); any other
        changed field is left alone and flagged for a human."""
        ours = set(self.ops) | (allowed if allowed is not None else set(self.proven_side or ()))
        ref = image.ref if isinstance(image, Image) else str(image[0])
        data = self.store.get(ref)
        if data.get("plan") != self.plan or data.get("model") != self.model:
            raise UndoRefused("snapshot-proof: before-image belongs to another plan")
        if self.now() - float(data.get("taken_at", 0)) > self.max_age_s:
            raise UndoRefused("snapshot-proof: before-image stale")
        before: dict[str, dict[str, Any]] = data["rows"]
        key = {i: int(i) if i.isdigit() else i for i in before}
        cur = self._read([key[i] for i in before])
        res = UndoResult()
        todo: list[str] = []
        for i, b in before.items():
            if not self._diff(cur[i], b):
                res.already.append(i)
            elif i in self.applied:
                if self._diff(cur[i], self.applied[i]):
                    res.conflicts[i] = "values changed since apply: human review"
                elif cur[i]["write_date"] != self.applied_wd.get(i):
                    res.conflicts[i] = "write_date changed since apply: human review"
                else:
                    todo.append(i)
            elif self._vals(cur[i]) not in (self.want, self._vals(b)):
                res.conflicts[i] = "values changed since apply: human review"
            elif i in self.applied_wd and cur[i]["write_date"] != self.applied_wd[i]:
                res.conflicts[i] = "write_date changed since apply: human review"
            else:
                todo.append(i)
        for _pass in range(2):  # 2nd pass: a write override may re-sync fields in pass 1
            for i in list(todo):
                vals = self._restore_vals(before[i], self._diff(cur[i], before[i]) & ours)
                if not vals:
                    continue
                if not self._write_one(key[i], vals, reverse=True):
                    res.conflicts[i] = "kill switch"
                    todo.remove(i)
            if not todo:
                break
            cur = self._read([key[i] for i in todo])
            if not any(self._diff(cur[i], before[i]) & set(self.wops) & ours for i in todo):
                break
        for i in todo:
            left = self._diff(cur[i], before[i])
            if other := left - ours:
                res.conflicts[i] = f"outside-plan change {sorted(other)[:5]} not ours: human review"
            elif left:
                self.unrestorable |= left
                res.conflicts[i] = f"undo did not restore {sorted(left)[:5]} (fail closed)"
            else:
                res.restored.append(i)
                self.applied_wd.pop(i, None)
                self.applied.pop(i, None)
                self.undone += 1
        self.conflicts.update(res.conflicts)
        return res

    # gate wiring
    def hooks(self) -> dict[str, Callable[..., Any]]:
        return {"before_image": self.before_image, "readback": self.readback, "undo": self.undo}
