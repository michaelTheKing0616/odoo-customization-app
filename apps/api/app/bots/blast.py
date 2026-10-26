"""Cascade-aware blast count, tier choice and stale-approval guard (BOT-DIFF-BLAST).

The graph comes from live ``ir.model.fields`` (stored many2one/many2many whose relation is
a touched model), never a hand list. many2one on_delete: cascade -> those rows go too
(walked); set null -> those rows are modified (counted, not walked); restrict -> refusal
preview naming the blockers. many2many -> link rows removed (counted). Anything not countable
(access error, unknown on_delete, node/depth cap) -> RF-R6 refusal. Python-level cascades
(overridden unlink, res_model/res_id pointers) are invisible to metadata: such models are
flagged "count may be low" (reasons derived from the reviewed catalogue) and require L3.

``Preview`` = diff + blast + tier; its ``payload_hash`` is what the owner approves.
``StaleGuard`` wraps the gate's Rehearsals: before the job opens it recomputes the preview
from live and refuses if the hash differs (records changed since approval).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.bots import diff as df
from app.bots.risk import rules
from app.bots.risk.rules import Refusal, TierPlan
from app.bots.snapshot import Verified

Rpc = df.Rpc
MAX_NODES = 20000  # records walked before the graph is declared uncountable
MAX_DEPTH = 12
CHUNK = 1000
ON_DELETE = ("cascade", "set null", "restrict")
USER_MODEL, COMPANY_MODEL, PARTNER_MODEL = "res.users", "res.company", "res.partner"


def low_count_reasons(model: str, op: str) -> list[str]:
    """Why metadata may under-count (derived from catalogue inventory, not a hand list)."""
    out: list[str] = []
    if op != "unlink":
        return out
    if model in rules.MAIL_THREAD:
        out.append(f"{model} is mail.thread: messages/followers/attachments go via Python unlink")
    if model not in rules.LOW_RISK_MODELS:
        out.append(f"{model} not reviewed low-risk: an overridden unlink may cascade further")
    return out


@dataclass
class Blast:
    op: str
    root: str
    deleted: dict[str, set[int]] = field(default_factory=dict)  # model -> ids removed
    nulled: dict[str, int] = field(default_factory=dict)  # "model.field" -> rows set to null
    nulled_ids: dict[str, set[int]] = field(default_factory=dict)  # model -> ids modified
    versions: dict[str, list] = field(default_factory=dict)  # model -> [[id, write_date]]
    links: dict[str, int] = field(default_factory=dict)  # "model.field" m2m links removed
    restrict: dict[str, int] = field(default_factory=dict)  # "model.field" -> blocking rows
    companies: set[int] = field(default_factory=set)
    users: set[int] = field(default_factory=set)
    low_count: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(len(v) for v in self.deleted.values()) + sum(self.nulled.values())

    def payload(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "per_model": {m: len(v) for m, v in sorted(self.deleted.items())},
            "ids": {m: sorted(v) for m, v in sorted(self.deleted.items())},
            "nulled": dict(sorted(self.nulled.items())),
            "links": dict(sorted(self.links.items())),
            "restrict": dict(sorted(self.restrict.items())),
            "companies": sorted(self.companies),
            "users": sorted(self.users),
            "total": self.total,
            "low_count": sorted(self.low_count),
            "nulled_ids": {m: sorted(v) for m, v in sorted(self.nulled_ids.items())},
            "versions": dict(sorted(self.versions.items())),
        }


def _r6(missing: str, reason: str) -> Refusal:
    return Refusal("RF-R6", missing, reason[:180])


def _incoming(read: Rpc, model: str, cache: dict[str, list[dict]]) -> list[dict]:
    if model not in cache:
        cache[model] = (
            read(
                "ir.model.fields",
                "search_read",
                [
                    [
                        ("relation", "=", model),
                        ("ttype", "in", ["many2one", "many2many"]),
                        ("store", "=", True),
                    ]
                ],
                {"fields": ["model", "name", "ttype", "on_delete"], "order": "model,name"},
            )
            or []
        )
    return cache[model]


def _search(read: Rpc, model: str, fname: str, ids: Sequence[int]) -> list[int]:
    out: list[int] = []
    s = sorted(ids)
    for i in range(0, len(s), CHUNK):
        out += (
            read(
                model, "search", [[(fname, "in", s[i : i + CHUNK])]], {"context": df.NO_ACTIVE_TEST}
            )
            or []
        )
    return out


def _count(read: Rpc, model: str, fname: str, ids: Sequence[int]) -> int:
    s, n = sorted(ids), 0
    for i in range(0, len(s), CHUNK):
        n += int(
            read(
                model,
                "search_count",
                [[(fname, "in", s[i : i + CHUNK])]],
                {"context": df.NO_ACTIVE_TEST},
            )
            or 0
        )
    return n


def _owners(read: Rpc, b: Blast, touched: dict[str, set[int]]) -> None:
    """Companies and users the touched records belong to / are."""
    for model, ids in touched.items():
        if model == USER_MODEL:
            b.users |= ids
        if model == COMPANY_MODEL:
            b.companies |= ids
        meta = (
            read(
                model,
                "fields_get",
                [["company_id", "company_ids"]],
                {"attributes": ["type", "relation"]},
            )
            or {}
        )
        fl = [
            f
            for f in ("company_id", "company_ids")
            if meta.get(f, {}).get("relation") == COMPANY_MODEL
        ]
        s = sorted(ids)
        for i in range(0, len(s), CHUNK) if fl else ():
            rows = read(model, "read", [s[i : i + CHUNK], fl], {"context": df.NO_ACTIVE_TEST}) or []
            for r in rows:
                for f in fl:
                    v = r.get(f)
                    b.companies |= set(v if f == "company_ids" else [df.norm_read("many2one", v)])
        if model == PARTNER_MODEL:
            b.users |= set(_search(read, USER_MODEL, "partner_id", s))
    b.companies.discard(False)


RULE_HIDE = "count may be low: record rules may hide rows"


def visibility_reasons(read: Rpc, b: Blast) -> list[str]:
    """Postgres cascades rows the Bot's RPC user cannot see. Searches run as that user, so
    any active ir.rule on a graph model, or more than one company, means the count is only a
    lower bound. Unreadable rule/company state counts as hidden (fail closed)."""
    models = set(b.deleted) | set(b.nulled_ids)
    models |= {k.rsplit(".", 1)[0] for k in (*b.links, *b.restrict)}
    out: list[str] = []
    try:
        n = read(
            "ir.rule",
            "search_count",
            [[("model_id.model", "in", sorted(models))]],
            {"context": df.NO_ACTIVE_TEST},
        )
        if n:
            out.append(f"{RULE_HIDE} ({n} ir.rule on graph models)")
    except Exception as exc:  # noqa: BLE001
        out.append(f"{RULE_HIDE} (ir.rule unreadable: {type(exc).__name__})")
    try:
        if read(COMPANY_MODEL, "search_count", [[]], {"context": df.NO_ACTIVE_TEST}) != 1:
            out.append("count may be low: more than one company (allowed-company filters)")
    except Exception as exc:  # noqa: BLE001
        out.append(f"count may be low: companies unreadable ({type(exc).__name__})")
    return out


def build_blast(rpc: Rpc, model: str, ids: Sequence[Any], op: str) -> Blast | Refusal:
    """op 'write': the planned records; op 'unlink': plus the cascade graph."""
    read = rpc if isinstance(rpc, df.ReadOnly) else df.ReadOnly(rpc)
    try:
        rids = set(df._ids(ids))
    except df.DiffRefused as e:
        return e.refusal
    if op not in ("write", "unlink"):
        return _r6("cascade-graph-count", f"unknown op {op!r}")
    b = Blast(op, model, {model: set(rids)})
    try:
        if op == "unlink":
            ref = _walk(read, b)
            if ref is not None:
                return ref
        _owners(read, b, b.deleted)
        _owners(read, b, b.nulled_ids)
        if op == "unlink":
            b.low_count += visibility_reasons(read, b)
            for m, mids in sorted(b.deleted.items()):
                rows = read(
                    m, "read", [sorted(mids), ["write_date"]], {"context": df.NO_ACTIVE_TEST}
                )
                b.versions[m] = sorted(
                    [r["id"], str(r.get("write_date") or "")] for r in rows or []
                )
    except Exception as exc:  # noqa: BLE001 - access error / transport: uncountable
        return _r6("cascade-graph-count", f"blast uncountable: {type(exc).__name__}")
    for m in sorted(b.deleted):
        b.low_count += low_count_reasons(m, op)
    return b


def _walk(read: Rpc, b: Blast) -> Refusal | None:
    cache: dict[str, list[dict]] = {}
    frontier = {b.root: set(b.deleted[b.root])}
    for depth in range(MAX_DEPTH + 1):
        if not frontier:
            break
        if depth == MAX_DEPTH:
            return _r6("cascade-graph-count", f"cascade deeper than {MAX_DEPTH}: uncountable")
        nxt: dict[str, set[int]] = {}
        for model, ids in sorted(frontier.items()):
            for f in _incoming(read, model, cache):
                key = f"{f['model']}.{f['name']}"
                if f["ttype"] == "many2many":
                    if n := _count(read, f["model"], f["name"], ids):
                        b.links[key] = b.links.get(key, 0) + n
                    continue
                hit = set(_search(read, f["model"], f["name"], ids))
                hit -= b.deleted.get(f["model"], set())  # already going (cycle / self-ref)
                if not hit:
                    continue  # unreferenced: its on_delete cannot matter
                od = f.get("on_delete")
                if od not in ON_DELETE:  # e.g. False on some Odoo 20 fields: never guess
                    return _r6("cascade-graph-count", f"{key} on_delete {od!r} unknown")
                if od == "restrict":
                    b.restrict[key] = b.restrict.get(key, 0) + len(hit)
                elif od == "set null":
                    b.nulled[key] = b.nulled.get(key, 0) + len(hit)
                    b.nulled_ids.setdefault(f["model"], set()).update(hit)
                else:
                    b.deleted.setdefault(f["model"], set()).update(hit)
                    nxt.setdefault(f["model"], set()).update(hit)
                if sum(len(v) for v in b.deleted.values()) > MAX_NODES:
                    return _r6("cascade-graph-count", f"cascade over {MAX_NODES} records")
        frontier = nxt
    for model, ids in sorted(b.deleted.items()):  # own many2many link rows go too
        meta = read(model, "fields_get", [[]], {"attributes": ["type", "store"]}) or {}
        m2m = sorted(f for f, m in meta.items() if m.get("type") == "many2many" and m.get("store"))
        if m2m:
            for r in read(model, "read", [sorted(ids), m2m], {"context": df.NO_ACTIVE_TEST}) or []:
                for f in m2m:
                    if n := len(r.get(f) or []):
                        b.links[f"{model}.{f}"] = b.links.get(f"{model}.{f}", 0) + n
    return None


@dataclass(frozen=True)
class Preview:
    diff: dict[str, Any] | None
    blast: dict[str, Any]
    tier: TierPlan
    payload_hash: str


def preview(
    rpc: Rpc,
    model: str,
    ids: Sequence[Any],
    values: dict[str, Any] | None,
    *,
    op: str,
    cls: str,
    subkind: str | None,
    route: rules.Route,
    policy: rules.Policy = rules.DEFAULT_POLICY,
) -> Preview | Refusal:
    """What the owner sees before approval. Restrict -> refusal preview (RF-R6)."""
    d = None
    if op == "write":
        try:
            d = df.build_diff(rpc, model, ids, values or {}).payload()
        except df.DiffRefused as e:
            return e.refusal
    elif values:
        return _r6("cascade-graph-count", "unlink plans carry no values")
    b = build_blast(rpc, model, ids, op)
    if isinstance(b, Refusal):
        return b
    if b.restrict:
        return _r6(
            "cascade-graph-count", f"restrict blocks unlink: {dict(sorted(b.restrict.items()))}"
        )
    if op == "unlink" and (b.nulled or len(b.deleted) > 1 or b.links):
        b.low_count.append("unlink touches dependent rows")
    t = rules.plan_tier(cls, subkind, route, policy, b.total, b.low_count)
    if isinstance(t, Refusal):
        return t
    body = {
        "model": model,
        "op": op,
        "values": values or {},
        "diff": d,
        "blast": b.payload(),
        "tier": t.tier,
        "batches": t.batches,
    }
    return Preview(d, b.payload(), t, df.canonical_hash(body))


def confirm(
    p: Preview,
    *,
    approval: int,
    typed: str | None,
    snapshot: Callable[[str], bool] | None,
    fingerprint: str,
) -> Refusal | None:
    """Owner-side check of the tier's controls. L3: typed blast count + a snapshot verifier
    (``snapshot.Verified``) that proves 'snapshot-proof' for THIS database. A bare id is never
    enough. Not yet called from the gate path: BOT-APPROVAL-TIERS / BOT-SPINE-WIRE must."""
    if approval < p.tier.tier:
        return Refusal("RF-ANY", f"human-approve-L{p.tier.tier}", f"L{approval} < L{p.tier.tier}")
    if p.tier.tier >= 3:
        if typed is None or typed.strip() != str(p.tier.blast_count):
            return Refusal("RF-ANY", "typed-confirmation", "typed blast count does not match")
        snap = getattr(snapshot, "snap", None)
        sid = getattr(snap, "id", None)
        if (
            not isinstance(snapshot, Verified)
            or not isinstance(sid, str)
            or not sid.startswith("snap:")
            or not sid[5:].strip()
        ):
            return Refusal("RF-R3", "snapshot-proof", "L3 needs a verified snapshot")
        if not fingerprint or getattr(snap, "fingerprint", None) != fingerprint:
            return Refusal("RF-R3", "snapshot-proof", "snapshot is of another database")
        if not rules._ok(snapshot, "snapshot-proof"):
            return Refusal("RF-R3", "snapshot-proof", "snapshot restore not verified")
    return None


STALE = "stale-approval"


class StaleGuard:
    """Rehearsals adapter for WriteGate: recompute preview, refuse on a different payload."""

    def __init__(self, inner: Any, approved_hash: str, recompute: Callable[..., Preview | Refusal]):
        self.inner, self.approved, self.recompute = inner, approved_hash, recompute

    def reserve(self, spec: Any, model: str, ids: Sequence[Any], values: dict[str, Any]):
        try:
            fresh = self.recompute(model, list(ids), values)
        except Exception as exc:  # noqa: BLE001
            return Refusal("RF-ANY", STALE, f"preview not recomputable: {type(exc).__name__}")
        if isinstance(fresh, Refusal):
            return fresh
        if not self.approved or fresh.payload_hash != self.approved:
            return Refusal("RF-ANY", STALE, "diff/blast changed since approval: re-approve")
        return self.inner.reserve(spec, model, ids, values)

    def release(self, spec: Any) -> None:
        self.inner.release(spec)
