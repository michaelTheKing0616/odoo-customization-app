"""Bridge B7 (spec 21-23, 30-32): plain-cause alerts + digest, daily reconciliation report,
uptime/SLA, API quota/cost watch, PII masking for logs/tests, client mode (view/approve only).
Composes messages only; delivery uses the channels the workspace configured.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------- 21 alerts with a plain cause
_CAUSES = [
    (
        r"\b401\b|unauthori[sz]ed|invalid (api )?key|expired token",
        "The app's sign-in stopped working (key expired or changed).",
        "Reconnect the app in Bridge.",
    ),
    (
        r"\b403\b|forbidden|permission",
        "The app refused access to this data.",
        "Give the connection the missing permission.",
    ),
    (
        r"\b404\b|not found",
        "The record or address no longer exists on the app.",
        "Check whether it was deleted, then replay.",
    ),
    (
        r"\b429\b|rate limit|too many requests",
        "The app is limiting how fast we can send.",
        "Nothing to do; we slow down and retry.",
    ),
    (
        r"\b5\d\d\b|bad gateway|service unavailable|timeout|timed out",
        "The app is down or slow right now.",
        "We retry automatically.",
    ),
    (
        r"required|missing field|null value",
        "A required field was empty.",
        "Fill the field or change the mapping, then replay.",
    ),
    (
        r"duplicate|already exists|unique",
        "This record already exists.",
        "Review the match rule for this record.",
    ),
    (
        r"money|amount mismatch|reconcil",
        "Amounts don't agree between the app and Odoo.",
        "Money writes are paused; review the reconciliation.",
    ),
]


def plain_cause(error: str) -> dict[str, str]:
    e = (error or "").lower()
    for pat, cause, fix in _CAUSES:
        if re.search(pat, e):
            return {"cause": cause, "fix": fix}
    return {
        "cause": "Something unexpected went wrong.",
        "fix": "Open the record trace for details.",
    }


def build_alert(flow: str, error: str, record: str | None = None, count: int = 1) -> dict[str, Any]:
    pc = plain_cause(error)
    title = f"{flow}: {pc['cause']}"
    body = (
        f"{count} record(s) affected." + (f" First: {record}." if record else "") + f" {pc['fix']}"
    )
    return {
        "title": title,
        "text": mask_pii(body),
        "severity": "high"
        if "money" in pc["cause"].lower() or "sign-in" in pc["cause"]
        else "normal",
    }


def digest(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, int] = {}
    for a in alerts:
        by[a["title"]] = by.get(a["title"], 0) + 1
    lines = [f"{n}× {t}" for t, n in sorted(by.items(), key=lambda x: -x[1])]
    return {
        "title": f"Bridge daily digest: {len(alerts)} alert(s)",
        "lines": lines or ["All flows healthy."],
    }


def slack_blocks(alert: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": alert["title"],
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{alert['title']}*\n{alert['text']}"},
            }
        ],
    }


def teams_card(alert: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "weight": "Bolder", "text": alert["title"]},
                        {"type": "TextBlock", "wrap": True, "text": alert["text"]},
                    ],
                },
            }
        ],
    }


# ---------------------------------------------------------------- 22 daily reconciliation report
def reconciliation_report(results: dict[str, dict[str, Any]], day: str) -> dict[str, Any]:
    bad = {k: v for k, v in results.items() if not v.get("ok")}
    lines = [
        f"{k}: {len(v.get('missing_in_odoo', []))} missing, {len(v.get('amount_mismatch', []))} amount differences"
        for k, v in bad.items()
    ]
    return {
        "day": day,
        "flows": len(results),
        "ok": not bad,
        "title": f"Reconciliation {day}: "
        + ("all match" if not bad else f"{len(bad)} flow(s) need review"),
        "lines": lines,
    }


# ---------------------------------------------------------------- 23 uptime / SLA
def uptime(checks: list[dict[str, Any]], target: float = 0.995) -> dict[str, Any]:
    """checks: [{at, ok, latency_ms}] from scheduled health probes."""
    if not checks:
        return {"uptime": None, "meets_sla": None, "p95_ms": None}
    ok = sum(1 for c in checks if c.get("ok"))
    lat = sorted(c.get("latency_ms") or 0 for c in checks if c.get("ok"))
    p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else None
    up = ok / len(checks)
    return {
        "uptime": round(up, 4),
        "meets_sla": up >= target,
        "target": target,
        "p95_ms": p95,
        "checks": len(checks),
    }


# ---------------------------------------------------------------- 30 API quota / cost watch
def quota_watch(
    used: int, limit: int | None, cost_per_call: float = 0.0, budget: float | None = None
) -> dict[str, Any]:
    pct = used / limit if limit else None
    cost = round(used * cost_per_call, 4)
    warn = []
    if pct is not None and pct >= 0.8:
        warn.append(f"{round(pct * 100)}% of the app's API quota used")
    if budget is not None and cost >= 0.8 * budget:
        warn.append(f"Cost {cost} is near the budget {budget}")
    return {
        "used": used,
        "limit": limit,
        "share": round(pct, 3) if pct is not None else None,
        "cost": cost,
        "warnings": warn,
        "pause": bool((pct is not None and pct >= 1) or (budget is not None and cost >= budget)),
    }


# ---------------------------------------------------------------- 31 PII masking for logs and tests
_PII = [
    (
        re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
        lambda m: m.group(0)[0] + "***@" + m.group(0).split("@")[1],
    ),
    (re.compile(r"\+?\d[\d\s-]{8,}\d"), lambda m: "***" + re.sub(r"\D", "", m.group(0))[-2:]),
    (re.compile(r"\b(sk|pk|rk)_(live|test)_[A-Za-z0-9]+"), lambda m: m.group(1) + "_***"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._-]+"), lambda m: m.group(1) + " ***"),
    (
        re.compile(r"\b\d{10}\b"),
        lambda m: "******" + m.group(0)[-4:],
    ),  # NUBAN-length account numbers
]


def mask_pii(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    for rx, rep in _PII:
        text = rx.sub(rep, text)
    return text


def mask_record(
    rec: Any,
    keys: tuple[str, ...] = ("email", "phone", "mobile", "vat", "iban", "acc_number", "name"),
) -> Any:
    if isinstance(rec, dict):
        return {k: ("***" if k in keys and v else mask_record(v, keys)) for k, v in rec.items()}
    if isinstance(rec, list):
        return [mask_record(x, keys) for x in rec]
    return mask_pii(rec)


# ---------------------------------------------------------------- 32 client mode
CLIENT_ALLOWED_POST = ("/approve", "/contracts/validate")


def client_may(method: str, path: str) -> bool:
    if method.upper() in ("GET", "HEAD", "OPTIONS"):
        return True
    return any(path.rstrip("/").endswith(s) for s in CLIENT_ALLOWED_POST)
