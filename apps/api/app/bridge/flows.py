"""Bridge B6 (spec 16-20): versioned flows with review/approval, gradual rollout and rollback,
safe backfill planning, money guard + reconciliation, live monitor counters and record trace.
Stored with the Code-runner JSON store (kind "bridge_flows" / "bridge_trace"), workspace-keyed.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from app.code_runner import store

MONEY_HINTS = ("amount", "price", "total", "balance", "payment", "tax", "fee", "cost", "subtotal")


def _k(ws: str | None) -> str:
    return f"flows_{ws or 'local'}"


def _hash(defn: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(defn, sort_keys=True, default=str).encode()).hexdigest()[:16]


def touches_money(defn: dict[str, Any]) -> bool:
    for m in defn.get("mapping") or []:
        if m.get("money") or any(h in str(m.get("odoo", "")).lower() for h in MONEY_HINTS):
            return True
    return str(defn.get("odoo_model", "")).startswith(("account.", "sale.order", "purchase.order"))


# ---------------------------------------------------------------- 16 versions, review, approval, rollout, rollback
def _log(v: dict[str, Any], step: str, by: str | None, *, verified: bool | None = None, **extra: Any) -> None:
    """Publish timeline for the status page: each step, when, who, and seconds since the last step."""
    log = v.setdefault("log", [])
    now = time.time()
    since = round(now - log[-1]["at"], 1) if log else None
    log.append({"step": step, "at": now, "by": by, "verified": verified, "since_prev_s": since, **extra})


def propose(
    ws: str | None, flow_id: str, defn: dict[str, Any], by: str | None, tests_ok: bool
) -> dict[str, Any]:
    if not tests_ok:
        raise ValueError("Contract tests must pass before a version can be proposed.")
    with store.lock():
        data = store.load("bridge_flows", _k(ws), {})
        f = data.setdefault(flow_id, {"versions": [], "live": None, "rollout": 0})
        v = {
            "n": len(f["versions"]) + 1,
            "hash": _hash(defn),
            "defn": defn,
            "by": by,
            "at": time.time(),
            "status": "review",
            "money": touches_money(defn),
            "approvals": [],
        }
        _log(v, "Proposed", by, tests="passed")
        f["versions"].append(v)
        store.save("bridge_flows", _k(ws), data)
    return {k: v[k] for k in ("n", "hash", "status", "money")}


def approve(ws: str | None, flow_id: str, n: int, by: str | None, hash_seen: str,
            *, verified: bool = True) -> dict[str, Any]:
    """Approve a version. Money flows need a second, different person. With sign-in off nobody is
    verified, so both people must give their name; the same name twice is refused and the approval is
    marked "name typed, not signed in" on the status page."""
    with store.lock():
        data = store.load("bridge_flows", _k(ws), {})
        v = _ver(data, flow_id, n)
        if v["hash"] != hash_seen:
            raise ValueError("This version changed since you reviewed it.")
        who = (by or "").strip()
        if v["money"]:
            if not str(v.get("by") or "").strip():
                raise PermissionError("This money flow was proposed without a name. Propose it again with your "
                                      "name, so a second person can approve it.")
            if not who:
                raise PermissionError("Money flows need a second person to approve. Sign-in is off, so type "
                                      "your name: Ingenium uses it to tell the two people apart.")
            if who.lower() == str(v.get("by") or "").strip().lower():
                raise PermissionError("Money flows need a second person to approve.")
        if who and who not in v["approvals"]:
            v["approvals"].append(who)
        v["status"] = "approved"
        _log(v, "Approved", who or None, verified=verified)
        store.save("bridge_flows", _k(ws), data)
    return {"n": n, "status": "approved", "approved_by": who or None, "verified": verified}


def set_rollout(ws: str | None, flow_id: str, n: int, percent: int, by: str | None = None) -> dict[str, Any]:
    if percent not in (0, 5, 25, 50, 100):
        raise ValueError("Roll out in steps: 0, 5, 25, 50, 100 %.")
    with store.lock():
        data = store.load("bridge_flows", _k(ws), {})
        v = _ver(data, flow_id, n)
        if v["status"] not in ("approved", "live"):
            raise ValueError("Only approved versions can roll out.")
        f = data[flow_id]
        prev = f["live"]
        f["candidate"], f["rollout"] = n, percent
        _log(v, "Live for everyone" if percent == 100 else (f"Rolled out to {percent}%" if percent else "Rollout paused"),
             by, percent=percent)
        if percent == 100:
            for o in f["versions"]:
                if o["status"] == "live":
                    o["status"] = "approved"
            v["status"], f["live"], f["candidate"], f["rollout"] = "live", n, None, 100
            f["previous"] = prev
        store.save("bridge_flows", _k(ws), data)
    return {"live": f["live"], "candidate": f.get("candidate"), "rollout": f["rollout"]}


def rollback(ws: str | None, flow_id: str, by: str | None = None) -> dict[str, Any]:
    with store.lock():
        data = store.load("bridge_flows", _k(ws), {})
        f = data.get(flow_id) or {}
        if f.get("candidate"):
            _log(_ver(data, flow_id, f["candidate"]), "Rollout stopped", by)
            f["candidate"], f["rollout"] = None, 100 if f.get("live") else 0
        elif f.get("previous"):
            cur = _ver(data, flow_id, f["live"])
            cur["status"] = "rolled_back"
            _log(cur, "Rolled back", by, to=f["previous"])
            _ver(data, flow_id, f["previous"])["status"] = "live"
            f["live"], f["previous"] = f["previous"], None
        else:
            raise ValueError("Nothing to roll back to.")
        store.save("bridge_flows", _k(ws), data)
    return {"live": f["live"], "candidate": f.get("candidate")}


def version_for(ws: str | None, flow_id: str, record_key: str) -> int | None:
    """Deterministic bucket: the same record always gets the same version during a rollout."""
    f = store.load("bridge_flows", _k(ws), {}).get(flow_id) or {}
    cand, pct = f.get("candidate"), f.get("rollout", 0)
    if cand and pct:
        bucket = int(hashlib.sha256(f"{flow_id}|{record_key}".encode()).hexdigest()[:8], 16) % 100
        if bucket < pct:
            return cand
    return f.get("live")


def get_flow(ws: str | None, flow_id: str) -> dict[str, Any] | None:
    return store.load("bridge_flows", _k(ws), {}).get(flow_id)


def _ver(data: dict, flow_id: str, n: int) -> dict[str, Any]:
    for v in (data.get(flow_id) or {}).get("versions", []):
        if v["n"] == n:
            return v
    raise KeyError(f"no version {n}")


# ---------------------------------------------------------------- 17 safe backfill
def plan_backfill(
    total: int, batch: int = 200, max_records: int = 50_000, per_minute: int = 600
) -> dict[str, Any]:
    if total > max_records:
        raise ValueError(f"Backfill capped at {max_records} records; split it by date.")
    batch = max(1, min(batch, 1000))
    batches = (total + batch - 1) // batch
    return {
        "total": total,
        "batch": batch,
        "batches": batches,
        "eta_min": round(total / max(1, per_minute), 1),
        "resumable": True,
        "dry_run_first": True,
    }


def backfill_step(
    cursor: dict[str, Any], fetch: Callable[[int, int], list[Any]], push: Callable[[Any], bool]
) -> dict[str, Any]:
    """One batch; returns the new cursor (resume from it after a stop or crash)."""
    if cursor.get("stopped"):
        return cursor
    rows = fetch(cursor.get("offset", 0), cursor["batch"])
    ok = fail = 0
    for r in rows:
        if push(r):
            ok += 1
        else:
            fail += 1
    done = cursor.get("done", 0) + ok
    return {
        **cursor,
        "offset": cursor.get("offset", 0) + len(rows),
        "done": done,
        "failed": cursor.get("failed", 0) + fail,
        "finished": len(rows) < cursor["batch"],
        "progress": round(
            min(1.0, (done + cursor.get("failed", 0) + fail) / max(1, cursor["total"])), 3
        ),
    }


# ---------------------------------------------------------------- 18 money guard + reconciliation
def reconcile(
    app_rows: list[dict[str, Any]],
    odoo_rows: list[dict[str, Any]],
    key: str = "ref",
    amount: str = "amount",
    tolerance: str = "0.01",
) -> dict[str, Any]:
    tol = Decimal(tolerance)
    a = {str(r[key]): Decimal(str(r.get(amount) or 0)) for r in app_rows}
    o = {str(r[key]): Decimal(str(r.get(amount) or 0)) for r in odoo_rows}
    missing = sorted(set(a) - set(o))
    extra = sorted(set(o) - set(a))
    diff = [
        {"ref": k, "app": str(a[k]), "odoo": str(o[k])}
        for k in sorted(set(a) & set(o))
        if abs(a[k] - o[k]) > tol
    ]
    ta, to = sum(a.values(), Decimal(0)), sum(o.values(), Decimal(0))
    ok = not (missing or extra or diff) and abs(ta - to) <= tol
    return {
        "ok": ok,
        "app_total": str(ta),
        "odoo_total": str(to),
        "missing_in_odoo": missing,
        "only_in_odoo": extra,
        "amount_mismatch": diff,
        "action": None if ok else "Pause money writes and review.",
    }


# ---------------------------------------------------------------- 19 live monitor + 20 record trace
STATIONS = {"outside": "Outside app", "ingenium": "Ingenium", "odoo": "Odoo"}


def _station_for(step: str) -> str:
    low = step.lower()
    if any(w in low for w in ("odoo", "written", "write", "create", "update")):
        return "odoo"
    if any(w in low for w in ("received", "webhook", "outside", "fetched", "sent by")):
        return "outside"
    return "ingenium"


def trace(
    ws: str | None, flow_id: str, record_key: str, step: str, status: str, detail: str = "",
    *, station: str | None = None, ms: float | None = None,
) -> None:
    """One step of a record's journey: station (outside app / Ingenium / Odoo), status, how long it took."""
    st = station if station in STATIONS else _station_for(step)
    with store.lock():
        data = store.load("bridge_trace", _k(ws), {})
        lst = data.setdefault(f"{flow_id}|{record_key}", [])
        lst.append({"at": time.time(), "step": step, "status": status, "detail": detail[:300],
                    "station": st, "station_label": STATIONS[st],
                    "ms": round(float(ms), 1) if ms is not None else None})
        del lst[:-50]
        store.save("bridge_trace", _k(ws), data)


def get_trace(ws: str | None, flow_id: str, record_key: str) -> list[dict[str, Any]]:
    return store.load("bridge_trace", _k(ws), {}).get(f"{flow_id}|{record_key}", [])


def monitor(
    ws: str | None, flow_id: str, since_s: float = 3600, now: float | None = None
) -> dict[str, Any]:
    now = now or time.time()
    data = store.load("bridge_trace", _k(ws), {})
    counts: dict[str, int] = {}
    buckets = 12  # sparkline / heartbeat: events per 5 min over the window (oldest first)
    volume = [0] * buckets
    last_err = None
    for k, lst in data.items():
        if not k.startswith(flow_id + "|"):
            continue
        for e in lst:
            if e["at"] >= now - since_s:
                counts[e["status"]] = counts.get(e["status"], 0) + 1
                i = int((e["at"] - (now - since_s)) / since_s * buckets)
                volume[min(buckets - 1, max(0, i))] += 1
                if e["status"] in ("failed", "dead") and (not last_err or e["at"] > last_err["at"]):
                    last_err = {**e, "record": k.split("|", 1)[1]}
    total = sum(counts.values())
    return {
        "window_s": since_s,
        "counts": counts,
        "volume": volume,
        "error_rate": round((counts.get("failed", 0) + counts.get("dead", 0)) / total, 3)
        if total
        else 0.0,
        "last_error": last_err,
    }


def list_flows(ws: str | None) -> list[dict[str, Any]]:
    out = []
    for fid, f in store.load("bridge_flows", _k(ws), {}).items():
        out.append({"id": fid, "live": f.get("live"), "candidate": f.get("candidate"), "rollout": f.get("rollout", 0),
                    "versions": [{k: v[k] for k in ("n", "hash", "status", "money", "by", "at")} for v in f.get("versions", [])]})
    return out
