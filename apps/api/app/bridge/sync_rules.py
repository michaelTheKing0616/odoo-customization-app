"""Bridge B4 (spec 8-11): matching rules + review queue, per-field direction/conflict rules,
triggers, and delivery policy (retry/backoff, idempotency, ordering, rate pacing, dead-letter).

All pure and clock-injectable; the durable store is the existing IntegrationEvent queue
(app.bridge.queue) — this module decides, it doesn't own a second queue.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Literal

# ---------------------------------------------------------------- 8 matching rules (no duplicates)
EXACT_KEYS = ("external_id", "email", "vat", "default_code", "barcode", "phone")


def _clean(k: str, v: Any) -> str:
    s = str(v or "").strip().lower()
    if k == "phone":
        s = re.sub(r"\D", "", s)[-10:]
    if k == "vat":
        s = re.sub(r"[^a-z0-9]", "", s)
    return s


def match_record(
    incoming: dict[str, Any],
    candidates: list[dict[str, Any]],
    keys: tuple[str, ...] = EXACT_KEYS,
    fuzzy_field: str = "name",
    link_at: float = 0.97,
    review_at: float = 0.8,
) -> dict[str, Any]:
    """link (one sure match) | create (nothing close) | review (ambiguous or only fuzzy)."""
    for k in keys:
        v = _clean(k, incoming.get(k))
        if not v:
            continue
        hits = [c for c in candidates if _clean(k, c.get(k)) == v]
        if len(hits) == 1:
            return {"action": "link", "id": hits[0].get("id"), "by": k, "score": 1.0}
        if len(hits) > 1:
            return {
                "action": "review",
                "ids": [h.get("id") for h in hits],
                "by": k,
                "why": f"{len(hits)} records share this {k}",
            }
    name = _clean(fuzzy_field, incoming.get(fuzzy_field))
    scored = sorted(
        (
            (SequenceMatcher(None, name, _clean(fuzzy_field, c.get(fuzzy_field))).ratio(), c)
            for c in candidates
            if name
        ),
        key=lambda t: -t[0],
    )
    if scored and scored[0][0] >= review_at:
        top = scored[0]
        close = [c.get("id") for sc, c in scored if sc >= review_at]
        if top[0] >= link_at and len(close) == 1:
            return {
                "action": "review",
                "ids": close,
                "by": fuzzy_field,
                "score": round(top[0], 2),
                "why": "name match only",
            }
        return {
            "action": "review",
            "ids": close,
            "by": fuzzy_field,
            "score": round(top[0], 2),
            "why": "similar names",
        }
    return {"action": "create", "score": round(scored[0][0], 2) if scored else 0.0}


# ---------------------------------------------------------------- 9 direction + conflict per field
Direction = Literal["in", "out", "both"]
Conflict = Literal["odoo_wins", "app_wins", "newest", "ask"]


@dataclass
class FieldRule:
    field: str
    direction: Direction = "in"
    conflict: Conflict = "ask"
    money: bool = False

    def __post_init__(self) -> None:
        if self.money and self.conflict in ("app_wins", "newest"):
            self.conflict = "ask"  # money guard: never auto-overwrite an amount


def resolve(
    rule: FieldRule,
    odoo_val: Any,
    app_val: Any,
    odoo_ts: float,
    app_ts: float,
    last_synced: Any = None,
    source: Literal["app", "odoo"] = "app",
) -> dict[str, Any]:
    if source == "app" and rule.direction == "out" or source == "odoo" and rule.direction == "in":
        return {"action": "skip", "why": f"{rule.field} only syncs {rule.direction}"}
    if odoo_val == app_val:
        return {"action": "noop"}
    odoo_changed = last_synced is not None and odoo_val != last_synced
    app_changed = last_synced is None or app_val != last_synced
    if not (odoo_changed and app_changed):  # only one side moved: take it
        return {
            "action": "set",
            "target": "odoo" if source == "app" else "app",
            "value": app_val if source == "app" else odoo_val,
        }
    c = rule.conflict
    if c == "odoo_wins":
        return {"action": "set", "target": "app", "value": odoo_val}
    if c == "app_wins":
        return {"action": "set", "target": "odoo", "value": app_val}
    if c == "newest":
        return (
            {"action": "set", "target": "odoo", "value": app_val}
            if app_ts >= odoo_ts
            else {"action": "set", "target": "app", "value": odoo_val}
        )
    return {
        "action": "review",
        "why": f"{rule.field} changed on both sides",
        "odoo": odoo_val,
        "app": app_val,
    }


# ---------------------------------------------------------------- 10 triggers
TRIGGERS = ("webhook", "schedule", "odoo_change", "manual")
_CRON = re.compile(r"^(\*|\d+|\*/\d+)( (\*|\d+|\*/\d+)){4}$")


def check_trigger(t: dict[str, Any]) -> list[str]:
    errs = []
    kind = t.get("kind")
    if kind not in TRIGGERS:
        return [f"unknown trigger {kind}"]
    if kind == "schedule":
        cron = str(t.get("cron", ""))
        if not _CRON.match(cron):
            errs.append("schedule needs a 5-part cron, e.g. */15 * * * *")
        elif cron.split()[0].startswith("*/") and int(cron.split()[0][2:]) < 5:
            errs.append("schedules run at most every 5 minutes")
    if kind == "odoo_change" and not (
        t.get("model") and t.get("on") in ("create", "write", "unlink", "create_or_write")
    ):
        errs.append("Odoo change trigger needs a model and on=create|write|unlink|create_or_write")
    if kind == "webhook" and not t.get("signature"):
        errs.append("webhook trigger needs a signature check")
    return errs


# ---------------------------------------------------------------- 11 delivery policy
def idempotency_key(
    connection_id: str, entity: str, remote_id: Any, payload: dict[str, Any]
) -> str:
    body = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(f"{connection_id}|{entity}|{remote_id}|{body}".encode()).hexdigest()[:40]


@dataclass
class RetryPolicy:
    base_s: float = 2.0
    cap_s: float = 900.0
    max_attempts: int = 8
    jitter: float = 0.2

    def next_delay(
        self,
        attempt: int,
        retry_after: float | None = None,
        rnd: Callable[[], float] = random.random,
    ) -> float:
        if retry_after is not None:
            return min(self.cap_s, max(0.0, retry_after))
        d = min(self.cap_s, self.base_s * (2 ** max(0, attempt - 1)))
        return round(d * (1 + self.jitter * (2 * rnd() - 1)), 3)

    def classify(self, status: int | None, attempt: int) -> Literal["done", "retry", "dead"]:
        if status is not None and 200 <= status < 300:
            return "done"
        retryable = status is None or status in (408, 409, 425, 429) or status >= 500
        if not retryable or attempt >= self.max_attempts:
            return "dead"
        return "retry"


@dataclass
class TokenBucket:
    rate_per_s: float
    burst: int
    clock: Callable[[], float] = time.monotonic
    _tokens: float = field(default=-1.0)
    _at: float = 0.0

    def take(self) -> float:
        """0 if allowed now, else seconds to wait."""
        now = self.clock()
        if self._tokens < 0:
            self._tokens, self._at = float(self.burst), now
        self._tokens = min(self.burst, self._tokens + (now - self._at) * self.rate_per_s)
        self._at = now
        if self._tokens >= 1:
            self._tokens -= 1
            return 0.0
        return round((1 - self._tokens) / self.rate_per_s, 3)


def order_batch(events: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Per-record ordering: same (entity, remote_id) stays in sequence; different records may run in parallel.
    Returns waves: wave n holds at most one event per record."""
    seqs: dict[tuple, list[dict[str, Any]]] = {}
    for e in sorted(events, key=lambda e: (e.get("seq", 0), e.get("received_at", 0))):
        seqs.setdefault((e.get("entity"), e.get("remote_id")), []).append(e)
    waves: list[list[dict[str, Any]]] = []
    for lst in seqs.values():
        for i, e in enumerate(lst):
            if len(waves) <= i:
                waves.append([])
            waves[i].append(e)
    return waves


def odoo_candidates(client: Any, model: str, incoming: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    """Live, read-only: fetch only records that could match (exact keys OR name ilike)."""
    fg = client.execute_kw(model, "fields_get", [], {"attributes": ["type"]})
    keys = [k for k in EXACT_KEYS if k in fg and incoming.get(k)]
    dom: list[Any] = []
    terms = [[k, "=ilike", str(incoming[k]).strip()] for k in keys if k != "phone"]
    if "name" in fg and incoming.get("name"):
        terms.append(["name", "ilike", str(incoming["name"]).strip()[:40]])
    for i, t in enumerate(terms):
        if i:
            dom.insert(0, "|")
        dom.append(t)
    if not dom:
        return []
    fields = ["id", "name"] + [k for k in EXACT_KEYS if k in fg]
    return client.execute_kw(model, "search_read", [dom], {"fields": fields, "limit": limit})
