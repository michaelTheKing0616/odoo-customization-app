"""Bot kill switch + write gate for production runs.

A job is one approved plan: (db, task, model, values, exact record ids). Its total N is a
hard ceiling counted from audit rows; 50/batch and 500/checkpoint are pacing, not a ceiling.
Every write goes through ``WriteGate``: kill-switch check (fail closed) before the job, each
batch and each record call; an 'intent' audit row before the write (no row = no write);
read-back per batch and at each checkpoint; failure trips the per-DB switch and undoes.
Approvals are stored single-use grants bound to (db, plan hash, N, level, approver, expiry),
issued only by the owner. Only the owner may clear a switch or set overrides (tighten only).
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.bots.audit import AuditError, AuditLog, AuditRow, CapError, redact
from app.bots.risk.rules import BATCH_CAP, RUN_CAP, Refusal, base_tier

GLOBAL = "global"
CHECKPOINT = RUN_CAP  # records between full read-back checkpoints
GRANT_TTL_S = 3600


def norm(ident: str | None) -> str:
    return unicodedata.normalize("NFKC", ident or "").strip().casefold()


def refusal_kill(scope: str) -> Refusal:
    return Refusal("RF-ANY", "kill-switch-off", f"kill switch on ({scope})")


def plan_hash(db: str, task_id: str, model: str, values: Any, ids: Sequence[Any]) -> str:
    blob = {"db": db, "task": task_id, "model": model, "values": values, "ids": list(ids)}
    return hashlib.sha256(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()


def diff_hash(values: Any) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class Approval:
    level: int  # what the human says; the stored grant decides
    approver: str | None = None
    grant_id: str | None = None


GrantSource = Callable[["KillSwitch", Approval, str, str, int, str], str | None]


class KillSwitch:
    """Switch state, owner-only controls and the grant/job store."""

    def __init__(
        self,
        engine: Engine,
        owner_of: Callable[[str], str | None],
        grant_source: GrantSource | None = None,
    ) -> None:
        self.engine, self.owner_of, self.grant_source = engine, owner_of, grant_source

    # ---- switch
    def check(self, db_fingerprint: str) -> Refusal | None:
        """None = clear to write. Any read failure or missing global row = ON."""
        try:
            with self.engine.connect() as c:
                rows = dict(
                    c.execute(
                        text("SELECT scope, is_on FROM bot_kill_switch WHERE scope IN (:g, :d)"),
                        {"g": GLOBAL, "d": db_fingerprint},
                    ).all()
                )
        except Exception:
            return Refusal("RF-ANY", "kill-switch-state", "kill switch state unreadable (on)")
        if rows.get(GLOBAL, True) is not False:
            return refusal_kill(GLOBAL)
        if rows.get(db_fingerprint) is True:
            return refusal_kill(db_fingerprint)
        return None

    def _set(self, scope: str, on: bool, actor: str, reason: str) -> None:
        with self.engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO bot_kill_switch (scope, is_on, reason, set_by)"
                    " VALUES (:s,:o,:r,:a) ON CONFLICT (scope) DO UPDATE SET is_on=:o,"
                    " reason=:r, set_by=:a, set_at=now()"
                ),
                {"s": scope, "o": on, "r": redact(reason)[:200], "a": actor},
            )

    def _is_owner(self, scope: str, actor: str) -> bool:
        try:
            owner = self.owner_of(scope)
        except Exception:
            return False
        return bool(owner) and norm(owner) == norm(actor)

    def turn_on(self, scope: str, actor: str, reason: str) -> None:
        self._set(scope, True, actor, reason)

    def turn_off(self, scope: str, actor: str, reason: str) -> None:
        if not self._is_owner(scope, actor):
            raise PermissionError("only the owner may clear a kill switch")
        self._set(scope, False, actor, reason)

    # ---- pacing overrides (tighten only)
    def set_caps(self, db_fingerprint: str, actor: str, batch_cap: int, run_cap: int) -> None:
        if not self._is_owner(db_fingerprint, actor):
            raise PermissionError("only the owner may set cap overrides")
        if not (1 <= batch_cap <= BATCH_CAP and 1 <= run_cap <= RUN_CAP):
            raise ValueError("overrides may only tighten the caps")
        with self.engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO bot_cap_override VALUES (:d,:b,:r,:a) ON CONFLICT (db_fingerprint)"
                    " DO UPDATE SET batch_cap=:b, run_cap=:r, set_by=:a"
                ),
                {"d": db_fingerprint, "b": batch_cap, "r": run_cap, "a": actor},
            )

    def caps(self, db_fingerprint: str) -> tuple[int, int]:
        """Effective (batch, checkpoint) pacing: min(default, override). Read failure raises."""
        with self.engine.connect() as c:
            r = c.execute(
                text("SELECT batch_cap, run_cap FROM bot_cap_override WHERE db_fingerprint=:d"),
                {"d": db_fingerprint},
            ).first()
        if r is None:
            return BATCH_CAP, RUN_CAP
        return min(BATCH_CAP, int(r[0])), min(RUN_CAP, int(r[1]))

    # ---- grants (owner path only)
    def create_grant(
        self,
        owner: str,
        db: str,
        plan: str,
        n_records: int,
        level: int,
        approver: str,
        bot_actor: str,
        ttl_s: int = GRANT_TTL_S,
    ) -> str:
        if not self._is_owner(db, owner):
            raise PermissionError("only the owner may issue an approval grant")
        a = norm(approver)
        if not a or a == norm(bot_actor) or a.startswith("bot"):
            raise PermissionError("approver must be a human other than the bot")
        if level not in (1, 2, 3) or n_records < 1:
            raise ValueError("bad grant")
        gid = uuid.uuid4().hex
        with self.engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO bot_grant (id, db_fingerprint, plan_hash, n_records, level,"
                    " approver_norm, created_by, expires_at) VALUES (:i,:d,:p,:n,:l,:a,:o,"
                    " now() + make_interval(secs => :t))"
                ),
                {
                    "i": gid,
                    "d": db,
                    "p": plan,
                    "n": n_records,
                    "l": level,
                    "a": a,
                    "o": owner,
                    "t": ttl_s,
                },
            )
        return gid

    def resolve_grant(self, a: Approval, db: str, plan: str, n: int, actor: str) -> str | None:
        if self.grant_source is not None:
            return self.grant_source(self, a, db, plan, n, actor)
        return a.grant_id

    def open_job(
        self, db: str, plan: str, n: int, need: int, grant_id: str | None, a: Approval, actor: str
    ) -> tuple[str, int, bool] | Refusal:
        """(job id, level, resumed). A live job for the same plan is reused (no new grant, no
        extra records); otherwise a grant is consumed atomically (single use)."""
        with self.engine.begin() as c:
            c.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": db + plan})
            live = c.execute(
                text(
                    "SELECT id, level FROM bot_job WHERE db_fingerprint=:d AND plan_hash=:p"
                    " AND status IN ('open','done')"
                ),
                {"d": db, "p": plan},
            ).first()
            if live:
                return live[0], int(live[1]), True
            level, jid = 1, uuid.uuid4().hex
            if need >= 2 or n > CHECKPOINT:
                if not grant_id or norm(a.approver) == norm(actor):
                    return Refusal("RF-R3", f"human-approve-L{need}", "no valid approval grant")
                got = c.execute(
                    text(
                        "UPDATE bot_grant SET used_at=now(), job_id=:j WHERE id=:g"
                        " AND used_at IS NULL AND expires_at > now() AND db_fingerprint=:d"
                        " AND plan_hash=:p AND n_records=:n AND level >= :need"
                        " AND approver_norm=:an AND approver_norm <> :bot RETURNING level"
                    ),
                    {
                        "j": jid,
                        "g": grant_id,
                        "d": db,
                        "p": plan,
                        "n": n,
                        "need": need,
                        "an": norm(a.approver),
                        "bot": norm(actor),
                    },
                ).scalar()
                if got is None:
                    return Refusal(
                        "RF-R3",
                        f"human-approve-L{need}",
                        "grant not valid for this database/plan/count/level/approver",
                    )
                level = int(got)
            c.execute(
                text(
                    "INSERT INTO bot_job (id, db_fingerprint, plan_hash, n_records, level,"
                    " grant_id, status) VALUES (:j,:d,:p,:n,:l,:g,'open')"
                ),
                {
                    "j": jid,
                    "d": db,
                    "p": plan,
                    "n": n,
                    "l": level,
                    "g": grant_id if level > 1 else None,
                },
            )
        return jid, level, False

    def set_job(self, job_id: str, status: str) -> None:
        with self.engine.begin() as c:
            c.execute(text("UPDATE bot_job SET status=:s WHERE id=:j"), {"s": status, "j": job_id})


@dataclass(frozen=True)
class RunSpec:
    db_fingerprint: str
    task_id: str
    actor: str
    risk_class: str
    rule_ids: str
    approval: Approval
    idempotency_key: str
    snapshot_id: str | None = None


@dataclass
class RunReport:
    status: str  # done | partial | refused | duplicate | tripped
    written: int = 0
    total: int = 0
    batches: int = 0
    checkpoints: int = 0
    job_id: str | None = None
    caps_hit: list[str] = field(default_factory=list)
    refusal: Refusal | None = None


Rpc = Callable[[str, str, Sequence[Any], dict[str, Any] | None], Any]


class WriteGate:
    """The only path from a Bot to an Odoo write."""

    def __init__(self, switch: KillSwitch, audit: AuditLog, rpc: Rpc) -> None:
        self.switch, self.audit, self._rpc = switch, audit, rpc

    def _row(self, spec: RunSpec, **kw: Any) -> AuditRow:
        base = dict(
            db_fingerprint=spec.db_fingerprint,
            task_id=spec.task_id,
            actor=spec.actor,
            approver=spec.approval.approver,
            approval_level=0,
            risk_class=spec.risk_class,
            rule_ids=spec.rule_ids,
            snapshot_id=spec.snapshot_id,
            idempotency_key=spec.idempotency_key,
            diff_hash="0" * 64,
            blast_count=0,
            batch_no=0,
            decision="refused",
            reason="",
        )
        kw["reason"] = redact(kw.get("reason", ""))[:200]
        return AuditRow(**{**base, **kw})

    def _refuse(self, spec: RunSpec, ref: Refusal, blast: int, caps: str = "") -> RunReport:
        try:
            self.audit.append(self._row(spec, blast_count=blast, reason=ref.text(), caps_hit=caps))
        except AuditError:
            pass  # still refused
        return RunReport("refused", total=blast, refusal=ref, caps_hit=[caps] if caps else [])

    def _safe_append(self, spec: RunSpec, decision: str, **kw: Any) -> None:
        try:
            self.audit.append(self._row(spec, decision=decision, **kw))
        except AuditError:
            # post-write row lost: stop everything for this DB rather than continue blind
            self.switch.turn_on(spec.db_fingerprint, "system", "audit write failed")

    def call(
        self, spec: RunSpec, model: str, method: str, args: Sequence[Any], kw: dict | None = None
    ) -> Any:
        """Single guarded write RPC (button, create, ...): a one-record job."""
        out: list[Any] = []

        def one(m: str, _meth: str, a: Sequence[Any], k: dict | None) -> Any:
            out.append(self._rpc(model, method, args, kw))

        gate = WriteGate(self.switch, self.audit, one)
        rep = gate.run(
            spec,
            model,
            [json.dumps([method, args, kw], sort_keys=True, default=str)],
            {},
            before_image=lambda c: ("call", None),
            readback=lambda c: True,
            undo=lambda image: False,
        )
        if rep.status == "refused":
            if rep.refusal and rep.refusal.missing == "audit":
                raise AuditError(rep.refusal.reason)
            raise PermissionError(rep.refusal.text() if rep.refusal else "refused")
        return out[0] if out else None

    def run(
        self,
        spec: RunSpec,
        model: str,
        ids: Sequence[Any],
        values: dict[str, Any],
        *,
        before_image: Callable[[Sequence[Any]], tuple[str, Any]],
        readback: Callable[[Sequence[Any]], bool],
        undo: Callable[[Any], bool],
    ) -> RunReport:
        ids = list(dict.fromkeys(ids))
        n, db = len(ids), spec.db_fingerprint
        if (ref := self.switch.check(db)) is not None:
            return self._refuse(spec, ref, n)
        try:
            batch_cap, ckpt = self.switch.caps(db)
        except Exception:
            return self._refuse(spec, Refusal("RF-ANY", "caps", "cap state unreadable"), n)
        need = 3 if n > ckpt else base_tier(spec.risk_class)
        caps = "run_cap" if n > ckpt else ""
        plan = plan_hash(db, spec.task_id, model, values, ids)
        a = spec.approval
        try:
            gid = self.switch.resolve_grant(a, db, plan, n, spec.actor)
            job = self.switch.open_job(db, plan, n, need, gid, a, spec.actor)
        except Exception as exc:
            return self._refuse(spec, Refusal("RF-ANY", "grant", type(exc).__name__), n, caps)
        if isinstance(job, Refusal):
            return self._refuse(spec, job, n, caps)
        job_id, level, _resumed = job
        dh = diff_hash({"model": model, "values": values})
        rep = RunReport("done", total=n, job_id=job_id, caps_hit=[caps] if caps else [])
        common = dict(
            diff_hash=dh,
            blast_count=n,
            job_id=job_id,
            approval_level=level,
            approver=a.approver if level > 1 else None,
        )
        seg_ids: list[Any] = []
        seg_images: list[Any] = []
        prev_ckpt = plan
        for bn, start in enumerate(range(0, n, batch_cap), 1):
            chunk = ids[start : start + batch_cap]
            if (ref := self.switch.check(db)) is not None:
                return self._stop(spec, rep, ref, bn, common)
            try:
                ref_id, image = before_image(chunk)
                hit = rep.caps_hit + (["batch_cap"] if n > batch_cap else [])
                intent = self._row(
                    spec,
                    batch_no=bn,
                    before_image_ref=ref_id,
                    caps_hit=",".join(hit),
                    decision="intent",
                    reason=f"{model} write {len(chunk)}",
                    n_records=len(chunk),
                    **common,
                )
                if not self.audit.claim(intent, job_cap=n):
                    rep.status = "duplicate" if not rep.written else "partial"
                    return rep
            except CapError as exc:
                return self._stop(
                    spec, rep, Refusal("RF-R3", "approved-count", str(exc)), bn, common
                )
            except AuditError as exc:
                return self._stop(spec, rep, Refusal("RF-ANY", "audit", str(exc)), bn, common)
            for rid in chunk:  # in-flight stop: switch re-checked before every record call
                if (ref := self.switch.check(db)) is not None:
                    self._safe_append(
                        spec,
                        "killed",
                        batch_no=bn,
                        reason=ref.text(),
                        before_image_ref=ref_id,
                        **common,
                    )
                    self._undo(spec, [image], bn, ref_id, common, undo, "kill")
                    self.switch.set_job(job_id, "stopped")
                    rep.status, rep.batches, rep.refusal = "partial", bn, ref
                    return rep
                self._rpc(model, "write", [[rid], values], None)
            seg_ids += chunk
            seg_images.append(image)
            if not readback(chunk):
                return self._trip(spec, rep, bn, ref_id, common, undo, [image], "batch")
            rep.written += len(chunk)
            rep.batches = bn
            self._safe_append(
                spec,
                "applied",
                batch_no=bn,
                reason=f"{len(chunk)} ok",
                before_image_ref=ref_id,
                **common,
            )
            if len(seg_ids) >= ckpt or rep.written == n:
                if self.switch.check(db) is not None or not readback(seg_ids):
                    return self._trip(spec, rep, bn, ref_id, common, undo, seg_images, "checkpoint")
                prev_ckpt = hashlib.sha256(
                    f"{prev_ckpt}:{job_id}:{rep.written}".encode()
                ).hexdigest()
                rep.checkpoints += 1
                self._safe_append(
                    spec, "checkpoint", batch_no=bn, reason=f"ckpt {prev_ckpt}", **common
                )
                seg_ids, seg_images = [], []
        self.switch.set_job(job_id, "done")
        return rep

    def _undo(self, spec, images, bn, ref_id, common, undo, why) -> None:
        ok = all([undo(im) for im in reversed(images)])
        self._safe_append(
            spec,
            "undone" if ok else "undo_failed",
            batch_no=bn,
            reason=why,
            before_image_ref=ref_id,
            **common,
        )

    def _trip(self, spec, rep, bn, ref_id, common, undo, images, where) -> RunReport:
        self.switch.turn_on(spec.db_fingerprint, "system", f"readback mismatch at {where}")
        self._safe_append(
            spec,
            "tripped",
            batch_no=bn,
            reason=f"readback mismatch {where}",
            before_image_ref=ref_id,
            **common,
        )
        self._undo(spec, images, bn, ref_id, common, undo, "auto")
        self.switch.set_job(common["job_id"], "stopped")
        rep.status, rep.batches = "tripped", bn
        rep.refusal = refusal_kill(spec.db_fingerprint)
        return rep

    def _stop(self, spec: RunSpec, rep: RunReport, ref: Refusal, bn: int, common) -> RunReport:
        self._safe_append(spec, "killed", batch_no=bn, reason=ref.text(), **common)
        if ref.missing != "approved-count":
            self.switch.set_job(common["job_id"], "stopped")
        rep.status = "partial" if rep.written else "refused"
        rep.refusal = ref
        return rep
