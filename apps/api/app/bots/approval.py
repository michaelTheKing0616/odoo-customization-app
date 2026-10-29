"""BOT-APPROVAL-TIERS: plan -> L1/L2/L3 with plain reasons; server-side, plan-bound grants.

The tier, N and card are computed here, never taken from a client. Tiers only go up.
Anything we cannot prove is refused (no tier), never run at a lower tier. Approvals become
single-use grants through ``KillSwitch.create_grant`` (level = stored tier, n = stored N,
bound to the plan hash and rehearsal). Runs use ``TierRehearsals`` + ``grant_source`` +
``route_approval`` so a rejected, pending or altered plan never writes. guard.py is unchanged.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.bots.audit import AuditLog, AuditRow, redact
from app.bots.guard import Approval, KillSwitch, Rehearsals, RunSpec, norm, plan_hash
from app.bots.risk.rules import CLASSES, RUN_CAP, Refusal, a_kind, base_tier

LIMITS = (
    "Undo only covers this record type. Changes Odoo makes to other kinds of records"
    " are not rolled back.",
    "Text translated into other languages is not restored by undo.",
    "Values that differ per company are restored for the current company only.",
)
TIER_LABEL = {
    1: "Low risk: runs on its own",
    2: "Needs your approval",
    3: "High impact: needs a workspace owner or admin to approve",
}


class ApprovalError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class Plan:
    connection_id: str
    db_fingerprint: str
    task_id: str
    model: str
    ids: Sequence[Any]
    values: Mapping[str, Any]
    risk_class: str
    requested_by: str
    summary: str
    subkind: str | None = None
    irreversible: bool = False
    rehearsal_id: str | None = None
    rehearsal_passed: bool = False
    undo_route: str | None = None  # "before_image" (reversible) | "snapshot" (irreversible)
    snapshot_verified: bool = False
    outside_plan: frozenset[str] = field(default_factory=frozenset)
    # BOT-SPINE-WIRE: a floor from checks outside this module (walker class, outgoing messages,
    # lockout); tiers only go up. ``call``: a gate.call job (button/create): no field values.
    min_tier: int = 1
    call: bool = False

    def unique_ids(self) -> list[Any]:
        return list(dict.fromkeys(self.ids))

    def hash(self) -> str:
        return plan_hash(
            self.db_fingerprint, self.task_id, self.model, dict(self.values), self.unique_ids()
        )


def facts_hash(plan: Plan) -> str:
    """Every fact the tier depends on. A run is only allowed while these match what a person
    approved (or, for L1, what was last classified)."""
    facts = {
        "risk": plan.risk_class,
        "irr": bool(plan.irreversible or a_kind(plan.risk_class, plan.subkind) == "irr")
        if plan.risk_class in CLASSES
        else True,
        "sub": plan.subkind,
        "undo": plan.undo_route,
        "backup": bool(plan.snapshot_verified),
        "side": sorted(plan.outside_plan),
        "n": len(plan.unique_ids()),
        "rh": plan.rehearsal_id,
        "rh_ok": bool(plan.rehearsal_passed),
    }
    if plan.min_tier != 1 or plan.call:  # absent keys keep earlier facts hashes unchanged
        facts |= {"min": plan.min_tier, "call": bool(plan.call)}
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class Tiering:
    tier: int | None
    reasons: tuple[str, ...]
    refusal: str | None = None


def classify(plan: Plan, checkpoint: int = RUN_CAP) -> Tiering:
    """Pure: tier + plain reasons, or a refusal. Fails closed on anything unproven."""
    n = len(plan.unique_ids())
    if plan.risk_class not in CLASSES:
        return Tiering(None, (), "We couldn't tell how risky this change is, so it can't run.")
    if plan.min_tier not in (1, 2, 3):
        return Tiering(None, (), "We couldn't tell how risky this change is, so it can't run.")
    if n < 1 or not isinstance(plan.values, Mapping) or not (plan.values or plan.call):
        return Tiering(None, (), "This plan doesn't say which records or values to change.")
    if not plan.rehearsal_id or not plan.rehearsal_passed:
        return Tiering(None, (), "It hasn't passed a practice run on a copy of your database yet.")
    irr = plan.irreversible or a_kind(plan.risk_class, plan.subkind) == "irr"
    if irr and not (plan.undo_route == "snapshot" and plan.snapshot_verified):
        return Tiering(
            None,
            (),
            "This can't be undone, and no checked backup was taken first, so it won't run.",
        )
    if not irr and plan.undo_route != "before_image":
        return Tiering(None, (), "There's no way to undo this change yet, so it won't run.")
    tier = base_tier(plan.risk_class)
    reasons = [f"This kind of change is rated level {tier}."]
    if plan.outside_plan:
        tier = max(tier, 2)
        names = ", ".join(sorted(plan.outside_plan)[:5])
        reasons.append(f"Odoo also changes other fields on these records ({names}).")
    if plan.min_tier > tier:
        tier = plan.min_tier
        reasons.append(f"Other safety checks on this change rate it level {tier}.")
    if irr:
        tier = 3
        reasons.append("It can't be undone in place; undo means restoring the backup.")
    if n > checkpoint:
        tier = 3
        reasons.append(f"It touches {n} records, more than {checkpoint} in one run.")
    reasons.append(f"It will change exactly {n} record{'s' if n != 1 else ''}, never more.")
    return Tiering(tier, tuple(reasons))


def _card(plan: Plan, t: Tiering, n: int) -> dict[str, Any]:
    irr = plan.irreversible or a_kind(plan.risk_class, plan.subkind) == "irr"
    if t.tier is None:
        undo = {"available": False, "how": "Not available."}
    elif irr:
        undo = {"available": True, "how": "Restore the backup taken just before the change."}
    else:
        undo = {"available": True, "how": "One-click undo puts back the earlier values."}
    return {
        "summary": redact(plan.summary)[:300],
        "model": plan.model,
        "changes": [
            {"field": f, "to": redact(str(v))[:80]} for f, v in sorted(plan.values.items())
        ][:20],
        "records": n,
        "risk": plan.risk_class,
        "tier": t.tier,
        "tier_label": TIER_LABEL.get(t.tier or 0, "Can't run"),
        "reasons": list(t.reasons),
        "refusal": t.refusal,
        "undo": undo,
        "rehearsal": {"passed": bool(plan.rehearsal_passed and plan.rehearsal_id)},
        "limits": list(LIMITS),
    }


_COLS = (
    "id, connection_id, db_fingerprint, plan_hash, task_id, risk_class, n_records, tier,"
    " status, rehearsal_id, requested_by, decided_by, grant_id, card, created_at, decided_at,"
    " facts_hash"
)


def _row(r: Any) -> dict[str, Any]:
    d = dict(r._mapping)
    d["card"] = json.loads(d["card"])
    d.pop("grant_id", None)  # never leaves the server
    d.pop("facts_hash", None)
    for k in ("created_at", "decided_at"):
        d[k] = d[k].isoformat() if d[k] else None
    return d


class ApprovalStore:
    def __init__(self, engine: Engine, switch: KillSwitch, audit: AuditLog) -> None:
        self.engine, self.switch, self.audit = engine, switch, audit

    # ---- submit (bot side)
    def submit(self, plan: Plan) -> dict[str, Any]:
        """Idempotent per plan: an existing row (incl. rejected) is returned unchanged."""
        try:
            checkpoint = self.switch.caps(plan.db_fingerprint)[1]
        except Exception:
            checkpoint = None
        ids = plan.unique_ids()
        t = (
            classify(plan, checkpoint)
            if checkpoint
            else Tiering(None, (), "Safety limits couldn't be read, so it won't run.")
        )
        status = "refused" if t.tier is None else "auto" if t.tier == 1 else "pending"
        h, fh = plan.hash(), facts_hash(plan)
        with self.engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO bot_approval (id, connection_id, db_fingerprint, plan_hash,"
                    " task_id, risk_class, n_records, tier, status, rehearsal_id, requested_by,"
                    " card, facts_hash) VALUES (:i,:c,:d,:p,:t,:r,:n,:tier,:s,:rh,:rq,:card,:fh)"
                    " ON CONFLICT (db_fingerprint, plan_hash) DO NOTHING"
                ),
                {
                    "i": uuid.uuid4().hex,
                    "c": plan.connection_id,
                    "d": plan.db_fingerprint,
                    "p": h,
                    "t": plan.task_id,
                    "r": plan.risk_class if plan.risk_class in CLASSES else "R9",
                    "n": max(len(ids), 1),
                    "tier": t.tier,
                    "s": status,
                    "rh": plan.rehearsal_id,
                    "rq": plan.requested_by,
                    "card": json.dumps(_card(plan, t, len(ids))),
                    "fh": fh,
                },
            )
            sel = text(
                f"SELECT {_COLS} FROM bot_approval WHERE db_fingerprint=:d AND plan_hash=:p"
                " FOR UPDATE"
            )
            r = c.execute(sel, {"d": plan.db_fingerprint, "p": h}).one()
            m = r._mapping
            if m["facts_hash"] != fh:
                self._reclassify(c, m, plan, t, fh, len(ids))
                r = c.execute(sel, {"d": plan.db_fingerprint, "p": h}).one()
        return _row(r)

    def _reclassify(self, c: Any, m: Any, plan: Plan, t: Tiering, fh: str, n: int) -> None:
        """Same plan, new facts. Tiers only go up; rejected stays rejected; an approved plan
        goes back to pending (or refused) and its unused grant is voided; a refused plan is
        re-evaluated and may now get a tier."""
        old, status = m["tier"], m["status"]
        if status == "rejected":
            return
        if status == "refused" or t.tier is None:
            tier = t.tier
        else:
            tier = max(int(old), t.tier) if old is not None else t.tier
        new = (
            "refused"
            if tier is None
            else "auto"
            if tier == 1 and status != "approved"
            else "pending"
        )
        card = _card(plan, t, n)
        if tier is not None and tier != t.tier:
            card["tier"], card["tier_label"] = tier, TIER_LABEL[tier]
            card["reasons"].append(f"Kept at level {tier} from an earlier check.")
        if status == "approved" and m["grant_id"]:
            c.execute(  # void: an unused grant can never open a job
                text("UPDATE bot_grant SET used_at=now() WHERE id=:g AND used_at IS NULL"),
                {"g": m["grant_id"]},
            )
            self.audit.append(  # the void is a decision: no audit row, no void
                AuditRow(
                    db_fingerprint=m["db_fingerprint"],
                    task_id=m["task_id"],
                    actor=m["requested_by"],
                    approval_level=int(old or 0),
                    risk_class=m["risk_class"],
                    rule_ids="APPROVAL-TIER",
                    diff_hash=m["plan_hash"],
                    blast_count=n,
                    batch_no=0,
                    idempotency_key=f"approval:{m['id']}:void:{m['grant_id']}",
                    decision="refused",
                    reason="approval voided: plan facts changed",
                )
            )
        c.execute(
            text(
                "UPDATE bot_approval SET tier=:tier, status=:s, risk_class=:r, card=:card,"
                " rehearsal_id=:rh, facts_hash=:fh, grant_id=NULL, decided_by=NULL,"
                " decided_at=NULL, decided_facts_hash=NULL WHERE id=:i"
            ),
            {
                "tier": tier,
                "s": new,
                "r": plan.risk_class if plan.risk_class in CLASSES else "R9",
                "card": json.dumps(card),
                "rh": plan.rehearsal_id,
                "fh": fh,
                "i": m["id"],
            },
        )

    # ---- reads
    def list(self, connection_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            rows = c.execute(
                text(
                    f"SELECT {_COLS} FROM bot_approval WHERE connection_id=:c ORDER BY"
                    " (status='pending') DESC, created_at DESC LIMIT 200"
                ),
                {"c": connection_id},
            ).all()
        return [_row(r) for r in rows]

    def get(self, connection_id: str, aid: str) -> dict[str, Any]:
        with self.engine.connect() as c:
            r = c.execute(
                text(f"SELECT {_COLS} FROM bot_approval WHERE id=:i AND connection_id=:c"),
                {"i": aid, "c": connection_id},
            ).first()
        if r is None:
            raise ApprovalError("not_found", "This approval doesn't exist.")
        return _row(r)

    # ---- decide (human side)
    def _decide(self, connection_id: str, aid: str, actor: str, approve: bool) -> dict[str, Any]:
        who = norm(actor)
        if not who or who.startswith("bot"):
            raise ApprovalError("forbidden", "Only a signed-in person can approve or reject.")
        with self.engine.begin() as c:
            r = c.execute(
                text(
                    f"SELECT {_COLS} FROM bot_approval WHERE id=:i AND connection_id=:c FOR UPDATE"
                ),
                {"i": aid, "c": connection_id},
            ).first()
            if r is None:
                raise ApprovalError("not_found", "This approval doesn't exist.")
            row = r._mapping
            if row["status"] != "pending":
                raise ApprovalError("conflict", f"This plan is already {row['status']}.")
            if who == norm(row["requested_by"]):
                raise ApprovalError("forbidden", "Someone other than the requester must decide.")
            tier, n = int(row["tier"]), int(row["n_records"])
            gid = None
            if approve:
                try:
                    gid = self.switch.create_grant(
                        actor,
                        row["db_fingerprint"],
                        row["plan_hash"],
                        n,
                        tier,
                        actor,
                        row["requested_by"],
                        rehearsal_id=row["rehearsal_id"] or "",
                    )
                except (PermissionError, ValueError) as exc:
                    raise ApprovalError("forbidden", "You can't approve this plan.") from exc
            decision = "approved" if approve else "rejected"
            self.audit.append(  # no audit row = no decision (raises, rolls back)
                AuditRow(
                    db_fingerprint=row["db_fingerprint"],
                    task_id=row["task_id"],
                    actor=actor,
                    approval_level=tier,
                    risk_class=row["risk_class"],
                    rule_ids="APPROVAL-TIER",
                    diff_hash=row["plan_hash"],
                    blast_count=n,
                    batch_no=0,
                    idempotency_key=f"approval:{aid}:{decision}",
                    decision=decision,
                    reason=f"L{tier} plan {decision} by a person",
                    approver=actor,
                    n_records=n,
                )
            )
            c.execute(
                text(
                    "UPDATE bot_approval SET status=:s, decided_by=:a, grant_id=:g,"
                    " decided_at=now(), decided_facts_hash=CASE WHEN CAST(:ap AS boolean)"
                    " THEN facts_hash END WHERE id=:i AND status='pending'"
                ),
                {"s": decision, "a": actor, "g": gid, "i": aid, "ap": approve},
            )
            r2 = c.execute(text(f"SELECT {_COLS} FROM bot_approval WHERE id=:i"), {"i": aid}).one()
        return _row(r2)

    def approve(self, connection_id: str, aid: str, actor: str) -> dict[str, Any]:
        return self._decide(connection_id, aid, actor, True)

    def reject(self, connection_id: str, aid: str, actor: str) -> dict[str, Any]:
        return self._decide(connection_id, aid, actor, False)

    # ---- run wiring
    def _live(self, db: str, plan: str) -> Any:
        with self.engine.connect() as c:
            return c.execute(
                text(
                    "SELECT status, tier, n_records, risk_class, rehearsal_id, decided_by,"
                    " grant_id, facts_hash, decided_facts_hash FROM bot_approval"
                    " WHERE db_fingerprint=:d AND plan_hash=:p"
                ),
                {"d": db, "p": plan},
            ).first()

    def grant_source(
        self, _sw: KillSwitch, _a: Approval, db: str, plan: str, n: int, _actor: str, rid: str
    ) -> str | None:
        """Only the stored grant of an approved plan; a client-supplied grant id is ignored."""
        try:
            r = self._live(db, plan)
        except Exception:
            return None
        if r is None or r[0] != "approved" or not _runnable(r):
            return None
        if int(r[2]) != n or (r[4] or "") != rid:
            return None
        return r[6]

    def approval_for(self, db: str, plan: str) -> Approval:
        """The Approval a bot run presents: stored tier and decider (level is advisory)."""
        r = self._live(db, plan)
        if r is None or not _runnable(r):
            return Approval(0)
        return Approval(int(r[1]), r[5])

    def route_approval(self, db: str, plan: str) -> int:
        """RouteA(approval=...): the stored tier of an auto/approved plan, else 0."""
        try:
            r = self._live(db, plan)
        except Exception:
            return 0
        return int(r[1]) if r is not None and _runnable(r) else 0


def _runnable(r: Any) -> bool:
    """auto (L1) rows, or approved rows whose facts still match what the person approved."""
    if r[0] == "auto":
        return True
    return r[0] == "approved" and bool(r[7]) and r[7] == r[8] and bool(r[6])


class TierRehearsals:
    """Wraps the rehearsal store: no auto/approved row for the exact plan = no run."""

    def __init__(self, inner: Rehearsals, store: ApprovalStore) -> None:
        self.inner, self.store = inner, store

    def reserve(
        self, spec: RunSpec, model: str, ids: Sequence[Any], values: dict[str, Any]
    ) -> Refusal | None:
        ids = list(dict.fromkeys(ids))
        h = plan_hash(spec.db_fingerprint, spec.task_id, model, values, ids)
        r = self.store._live(spec.db_fingerprint, h)
        if r is None:
            return Refusal("RF-ANY", "approval", "no approval record for this exact plan")
        status, tier, n, cls, rid = r[0], r[1], int(r[2]), r[3], r[4] or ""
        if not _runnable(r):
            return Refusal("RF-ANY", "approval", f"plan is {status} or its facts changed")
        if n != len(ids):
            return Refusal("RF-ANY", "approval", "record count differs from the approved N")
        if spec.risk_class != cls or base_tier(spec.risk_class) > int(tier):
            return Refusal("RF-ANY", "approval", "risk class differs from the approved plan")
        if (spec.rehearsal_id or "") != rid:
            return Refusal("RF-ANY", "approval", "rehearsal differs from the approved plan")
        return self.inner.reserve(spec, model, ids, values)

    def release(self, spec: RunSpec) -> None:
        self.inner.release(spec)
