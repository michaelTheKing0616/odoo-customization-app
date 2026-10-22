"""Bridge delivery engine (spec Bridge 10-12): a durable queue on ``integration_events``.

- Enqueue is idempotent (same connection + idempotency key = same event).
- Ordering: events sharing an ``ordering_key`` (usually "<flow>|<record>") are delivered one at a
  time, oldest first. A later event waits while an earlier one is queued or retrying.
- Retries: exponential backoff with jitter (2 s, 4 s, 8 s ... capped at 15 min); after
  ``MAX_ATTEMPTS`` the event goes to the dead-letter inbox (fix and replay there).
- Pacing: at most ``limit`` deliveries per call and an optional minimum gap between them.
- Every step is traced with its station (outside app / Ingenium / Odoo), status and timing, so the
  record trace view shows what really happened.

The worker is pull-based (``deliver_due``); a scheduler or the API calls it. No thread is started here.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.bridge import flows as fl
from app.bridge.queue import enqueue as _enqueue
from app.db_models import IntegrationEvent

MAX_ATTEMPTS = 6
BASE_DELAY_S = 2.0
MAX_DELAY_S = 900.0
OPEN_STATES = ("queued", "retrying")


class Retryable(Exception):
    """The far side is busy or down (timeouts, 429, 5xx): try again later."""


class Permanent(Exception):
    """The event itself is wrong (bad data, refused by Odoo): straight to the dead-letter inbox."""


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def backoff_s(attempt: int, *, rnd: Callable[[], float] = random.random) -> float:
    base = min(MAX_DELAY_S, BASE_DELAY_S * (2 ** max(0, attempt - 1)))
    return round(base * (0.8 + 0.4 * rnd()), 3)


def submit(db: Session, *, connection_id: str, idempotency_key: str, payload: dict[str, Any],
           flow_id: str | None = None, record_key: str | None = None, ws: str | None = None,
           source: str = "outside app") -> IntegrationEvent:
    """Receive an event from the outside app and queue it (idempotent)."""
    t0 = time.perf_counter()
    ev = _enqueue(db, connection_id, idempotency_key, payload)
    if ev.ordering_key is None and flow_id:
        ev.ordering_key = f"{flow_id}|{record_key or idempotency_key}"
    if flow_id:
        fl.trace(ws, flow_id, record_key or idempotency_key, "Received", "ok",
                 f"From {source}.", station="outside", ms=(time.perf_counter() - t0) * 1000)
    db.flush()
    return ev


def _blocked_keys(db: Session) -> dict[str, datetime]:
    """Oldest open event time per ordering key (later events with that key must wait)."""
    out: dict[str, datetime] = {}
    rows = (db.query(IntegrationEvent.ordering_key, IntegrationEvent.created_at, IntegrationEvent.id)
            .filter(IntegrationEvent.status.in_(OPEN_STATES), IntegrationEvent.ordering_key.isnot(None))
            .order_by(IntegrationEvent.created_at, IntegrationEvent.id).all())
    for key, created, _id in rows:
        out.setdefault(key, _aware(created) or _now())
    return out


def deliver_due(db: Session, handler: Callable[[IntegrationEvent, dict[str, Any]], dict[str, Any] | None], *,
                connection_ids: list[str] | None = None, limit: int = 50, min_gap_s: float = 0.0,
                ws: str | None = None, now: datetime | None = None,
                sleep: Callable[[float], None] = time.sleep) -> dict[str, int]:
    """Deliver due events. ``handler(event, payload)`` writes to Odoo and may return
    {"odoo_id": ..., "steps": [{"step", "station", "status", "ms"}]} for the trace."""
    now = now or _now()
    q = db.query(IntegrationEvent).filter(IntegrationEvent.status.in_(OPEN_STATES))
    if connection_ids is not None:
        q = q.filter(IntegrationEvent.connection_id.in_(connection_ids))
    events = q.order_by(IntegrationEvent.created_at, IntegrationEvent.id).all()
    first_open: dict[str, str] = {}
    for ev in events:  # the head of each ordering key's line
        if ev.ordering_key:
            first_open.setdefault(ev.ordering_key, ev.id)
    counts = {"delivered": 0, "retrying": 0, "dead": 0, "waiting": 0}
    sent = 0
    for ev in events:
        if sent >= limit:
            break
        if ev.ordering_key and first_open.get(ev.ordering_key) != ev.id:
            counts["waiting"] += 1
            continue
        due = _aware(ev.next_attempt_at)
        if due and due > now:
            continue
        if sent and min_gap_s:
            sleep(min_gap_s)
        sent += 1
        flow_id, _, record_key = (ev.ordering_key or "").partition("|")
        payload = json.loads(ev.payload_json)
        t0 = time.perf_counter()
        ev.attempts = int(ev.attempts or 0) + 1
        try:
            out = handler(ev, payload) or {}
        except Permanent as exc:
            ev.status, ev.last_error = "dead", str(exc)[:500]
            counts["dead"] += 1
            _t(ws, flow_id, record_key, "Written to Odoo", "failed", str(exc), "odoo", t0)
            _promote_next(ev, first_open, events)
            continue
        except Exception as exc:  # noqa: BLE001  network, 429, 5xx, timeouts: retry
            ev.last_error = str(exc)[:500]
            if ev.attempts >= MAX_ATTEMPTS:
                ev.status = "dead"
                counts["dead"] += 1
                _t(ws, flow_id, record_key, "Written to Odoo", "failed",
                   f"Gave up after {ev.attempts} tries: {exc}", "odoo", t0)
                _promote_next(ev, first_open, events)
            else:
                ev.status = "retrying"
                wait = backoff_s(ev.attempts)
                ev.next_attempt_at = now + timedelta(seconds=wait)
                counts["retrying"] += 1
                _t(ws, flow_id, record_key, "Written to Odoo", "retrying",
                   f"Try {ev.attempts} of {MAX_ATTEMPTS} failed ({exc}). Next try in {int(wait)} s.", "odoo", t0)
            continue
        for st in out.get("steps") or []:
            if flow_id:
                fl.trace(ws, flow_id, record_key, st.get("step", "Step"), st.get("status", "ok"), st.get("detail", ""),
                         station=st.get("station", "ingenium"), ms=st.get("ms"))
        ev.status, ev.delivered_at, ev.last_error = "done", _now(), None
        counts["delivered"] += 1
        detail = f"Odoo record {out['odoo_id']}." if out.get("odoo_id") else ""
        _t(ws, flow_id, record_key, "Written to Odoo", "ok", detail, "odoo", t0)
        _promote_next(ev, first_open, events)
    db.flush()
    return counts


def _promote_next(done: IntegrationEvent, first_open: dict[str, str], events: list[IntegrationEvent]) -> None:
    """After the head of a line finishes (or dies), the next event with that key may go next call."""
    if not done.ordering_key:
        return
    nxt = next((e for e in events if e.ordering_key == done.ordering_key and e.id != done.id
                and e.status in OPEN_STATES and _aware(e.created_at) and e is not done), None)
    first_open[done.ordering_key] = nxt.id if nxt else ""


def _t(ws: str | None, flow_id: str, record_key: str, step: str, status: str, detail: str, station: str, t0: float) -> None:
    if flow_id:
        fl.trace(ws, flow_id, record_key, step, status, detail, station=station, ms=(time.perf_counter() - t0) * 1000)


def queue_stats(db: Session, connection_ids: list[str] | None = None) -> dict[str, int]:
    q = db.query(IntegrationEvent.status)
    if connection_ids is not None:
        q = q.filter(IntegrationEvent.connection_id.in_(connection_ids))
    out: dict[str, int] = {}
    for (s,) in q.all():
        out[s] = out.get(s, 0) + 1
    return out


# ---------------------------------------------------------------- the Odoo writer used by the API
def odoo_handler(client_for: Callable[[str], Any], ws: str | None) -> Callable[[IntegrationEvent, dict[str, Any]], dict[str, Any]]:
    """Map the incoming record with the flow's live version (or rollout candidate), find its match in
    Odoo, then create or update it. Unclear matches and money writes without two approvers never write."""
    from app.bridge import mapping as bm
    from app.bridge import sync_rules as sr

    def handle(ev: IntegrationEvent, payload: dict[str, Any]) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        flow_id, record_key = payload.get("flow_id"), str(payload.get("record_key") or ev.idempotency_key)
        t = time.perf_counter()
        f = fl.get_flow(ws, flow_id) if flow_id else None
        n = fl.version_for(ws, flow_id, record_key) if f else None
        if not f or not n:
            raise Permanent("This flow has no live version yet. Approve and roll out a version first.")
        v = next(x for x in f["versions"] if x["n"] == n)
        defn = v["defn"]
        if v.get("money") and len({a for a in v.get("approvals", []) if a != v.get("by")}) < 1:
            raise Permanent("Money guard: this flow writes amounts and needs a second person's approval first.")
        row = bm.preview(defn.get("mapping") or [], [payload.get("record") or {}])[0]
        if row["problems"]:
            raise Permanent("Mapping failed: " + "; ".join(row["problems"]))
        values = row["values"]
        steps.append({"step": f"Mapped with version {n}", "station": "ingenium", "status": "ok",
                      "ms": (time.perf_counter() - t) * 1000, "detail": f"{len(values)} field(s)."})
        client = client_for(payload.get("odoo_connection_id") or defn.get("odoo_connection_id"))
        model = defn["odoo_model"]
        t = time.perf_counter()
        m = sr.match_record(values, sr.odoo_candidates(client, model, values))
        steps.append({"step": "Matched in Odoo", "station": "odoo", "status": "ok" if m["action"] != "review" else "review",
                      "ms": (time.perf_counter() - t) * 1000,
                      "detail": {"link": f"Same record as #{m.get('id')} (by {m.get('by')}).", "create": "No match, new record.",
                                 "review": "More than one possible match."}[m["action"]]})
        if m["action"] == "review":
            raise Permanent("Needs a person: more than one Odoo record could be this one. Pick it in the review queue, then replay.")
        if m["action"] == "link":
            client.execute_kw(model, "write", [[int(m["id"])], values])
            return {"odoo_id": int(m["id"]), "steps": steps}
        new_id = client.execute_kw(model, "create", [values])
        return {"odoo_id": int(new_id[0] if isinstance(new_id, list) else new_id), "steps": steps}

    return handle
