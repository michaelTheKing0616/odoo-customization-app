"""NF BV-02: build verify()'s observation from live read-back only.

Takes a connection-scoped port (never run/artifact ids). Every call goes
through ``readback.rpc`` which refuses non-read methods. Change-set
success claims are never read.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.bot_verify.readback import READBACKS, PortUnavailable, data_sample, mask, rpc, target_model

PERSONAS: tuple[str, ...] = ("requester", "low_privilege", "portal")
DEFAULT_RETRY_AFTER_S = 5
_DATA_PREFIX = "data."
_PERMS = ("read", "write", "create", "unlink")

# Personas for whom an AccessError is the expected outcome (AC1); recorded, never a pass.
EXPECTED_DENIED: frozenset[str] = frozenset({"portal"})
DEFAULT_ATTEMPTS = 2

__all__ = [
    "DEFAULT_RETRY_AFTER_S",
    "BeforeSnapshot",
    "OdooUnavailable",
    "PortUnavailable",
    "capture_before",
    "collect_observation",
    "collect_with_retry",
]


@dataclass(frozen=True)
class BeforeSnapshot:
    """Pre-apply state read by the collector itself (AC2); callers cannot forge it."""

    db_name: str
    fingerprint: str
    access: dict[str, dict[str, list[str]]]
    mail: int


class OdooUnavailable(Exception):
    """Odoo answered 429/503; the layer is skipped, never passed."""

    def __init__(self, retry_after_s: int) -> None:
        super().__init__("odoo_unavailable")
        self.retry_after_s = retry_after_s


def _retry_after(raw: str | None) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_RETRY_AFTER_S
    return value if value > 0 else DEFAULT_RETRY_AFTER_S


def _guard(port: Any) -> str:
    db_name = str(getattr(port, "db_name", "") or "")
    if not db_name.startswith("ingenium_"):
        raise ValueError("collector only reads ingenium_* databases")
    return db_name


def _post(port: Any, changeset: list[dict[str, Any]]) -> dict[int, Any]:
    post: dict[int, Any] = {}
    for index, op in enumerate(changeset):
        fn = READBACKS.get(str(op.get("type") or ""))
        post[index] = fn(port, op) if fn else {"evidence": {"reason": "unknown op"}}
    return post


def _digest(post: Mapping[int, Any]) -> str:
    return hashlib.sha256(json.dumps(post, sort_keys=True, default=str).encode()).hexdigest()


def _mail_count(port: Any) -> Any:
    return rpc(port, "mail.mail", "search_count", ([("state", "in", ["outgoing", "exception"])],))


def capture_before(port: Any, changeset: list[dict[str, Any]]) -> BeforeSnapshot:
    """Read the pre-apply fingerprint, access map and mail count server-side."""
    db_name = _guard(port)
    return BeforeSnapshot(
        db_name=db_name,
        fingerprint=_digest(_post(port, changeset)),
        access=_access(port),
        mail=_mail_count(port),
    )


def collect_with_retry(
    port: Any,
    changeset: list[dict[str, Any]],
    *,
    before: BeforeSnapshot | None = None,
    baseline: Mapping[str, Any] | None = None,
    personas: Mapping[str, int] | None = None,
    attempts: int = DEFAULT_ATTEMPTS,
    sleep: Callable[[float], Any] = time.sleep,
) -> dict[str, Any]:
    """AC3: 429/503 is retried; still unavailable = skipped "retryable". Never rolls back."""
    tries = max(1, int(attempts))
    obs: dict[str, Any] = {}
    for n in range(1, tries + 1):
        obs = collect_observation(
            port, changeset, baseline=baseline, personas=personas, before=before
        )
        meta = obs.get("meta") or {}
        if meta.get("reason") != "odoo_unavailable":
            return obs
        if n < tries:
            sleep(meta.get("retry_after_s", DEFAULT_RETRY_AFTER_S))
    meta = obs.get("meta") or {}
    return {
        "meta": {
            "status": "skipped",
            "reason": "retryable",
            "retry_after_s": meta.get("retry_after_s", DEFAULT_RETRY_AFTER_S),
            "attempts": tries,
        }
    }


def collect_observation(
    port: Any,
    changeset: list[dict[str, Any]],
    *,
    baseline: Mapping[str, Any] | None = None,
    personas: Mapping[str, int] | None = None,
    before: BeforeSnapshot | None = None,
) -> dict[str, Any]:
    """Return the mapping ``changeset.verify.verify`` reads.

    ``baseline`` carries pre-apply snapshots (fingerprint_before,
    expected_after, access_before, mail_before). ``personas`` maps persona
    name to Odoo uid. A 429/503 yields a skipped observation that verify()
    fails, with ``meta.retry_after_s``.
    """
    db_name = _guard(port)
    if before is not None and (not isinstance(before, BeforeSnapshot) or before.db_name != db_name):
        raise TypeError("before must be a BeforeSnapshot from capture_before on this database")
    base = dict(baseline or {})
    if before is not None:
        base.update(
            fingerprint_before=before.fingerprint,
            access_before=before.access,
            mail_before=before.mail,
        )
    try:
        return _collect(port, changeset, base, personas or {})
    except PortUnavailable as exc:
        err = OdooUnavailable(_retry_after(exc.retry_after))
        return {
            "meta": {
                "status": "skipped",
                "reason": "odoo_unavailable",
                "retry_after_s": err.retry_after_s,
            }
        }


def _collect(
    port: Any,
    changeset: list[dict[str, Any]],
    baseline: Mapping[str, Any],
    personas: Mapping[str, int],
) -> dict[str, Any]:
    post = _post(port, changeset)
    target = target_model(changeset)
    after = _digest(post)
    return {
        "meta": {"status": "collected", "source": "live_readback"},
        "postconditions": post,
        "fingerprint": {
            "before": baseline.get("fingerprint_before"),
            "after": after,
            "expected_after": baseline.get("expected_after"),
        },
        "views": {name: _view(port, target, personas.get(name), name) for name in PERSONAS},
        "persona_access": {
            name: _persona_access(port, target, personas.get(name), name) for name in PERSONAS
        },
        "smoke": _smoke(port, target),
        "access": {"before": baseline.get("access_before"), "after": _access(port)},
        "mail": {
            "before": baseline.get("mail_before"),
            "after": _mail_count(port),
        },
        "data": _data(port, changeset),
    }


def _denied(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {getattr(exc, 'faultString', '')}"
    return "AccessError" in text or "AccessDenied" in text


def _persona_access(port: Any, model: str | None, uid: int | None, name: str) -> dict[str, Any]:
    """Read access probe run under the persona's own uid (AC1)."""
    if not model or not isinstance(uid, int):
        return {
            "outcome": "skipped",
            "reason": "no_target_model" if not model else "no persona login",
        }
    try:
        rpc(port, model, "search_count", ([],), as_uid=uid)
    except PortUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - a denial is evidence
        if _denied(exc):
            return {"outcome": "denied", "expected": name in EXPECTED_DENIED}
        return {"outcome": "error", "error": type(exc).__name__}
    return {"outcome": "allowed", "expected": name not in EXPECTED_DENIED}


def _view(port: Any, model: str | None, uid: int | None, name: str = "") -> dict[str, Any]:
    if not model:
        return {"rendered": False, "skipped": True, "reason": "no_target_model"}
    if not isinstance(uid, int):
        return {"rendered": False, "skipped": True, "reason": "persona_missing"}
    try:
        res = rpc(
            port, model, "get_views", ([[False, "form"]],), {"context": {"uid": uid}}, as_uid=uid
        )
    except PortUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - render failure is evidence
        if _denied(exc):
            return {
                "rendered": False,
                "error": "AccessError",
                "outcome": "denied",
                "expected": name in EXPECTED_DENIED,
            }
        return {"rendered": False, "error": type(exc).__name__}
    views = res.get("views") if isinstance(res, Mapping) else None
    ok = isinstance(views, Mapping) and bool(views)
    return {"rendered": ok, "error": None if ok else "no views", "live": False}


def _smoke(port: Any, model: str | None) -> list[dict[str, Any]]:
    if not model:
        return [
            {"name": n, "passed": False, "skipped": True, "reason": "no_target_model"}
            for n in ("record_read", "action_resolves")
        ]
    try:
        rows = rpc(port, model, "search_read", ([],), {"limit": 1, "fields": ["id"]})
    except PortUnavailable:
        raise
    except Exception:  # noqa: BLE001 - an unreadable or missing model fails the probe
        rows = None
    acts = rpc(
        port,
        "ir.actions.act_window",
        "search_read",
        ([("res_model", "=", model)],),
        {"limit": 1, "fields": ["id"]},
    )
    return [
        {"name": "record_read", "passed": isinstance(rows, list)},
        {"name": "action_resolves", "passed": bool(acts)},
    ]


def _name(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) > 1:
        return str(value[1])
    return str(value or "all")


def _access_source(port: Any) -> tuple[str, str]:
    """Odoo 20 replaced ir.model.access with ir.access (for_read..for_unlink)."""
    if rpc(port, "ir.model", "search_count", ([("model", "=", "ir.access")],)):
        return "ir.access", "for_"
    return "ir.model.access", "perm_"


def _access(port: Any) -> dict[str, dict[str, list[str]]]:
    model, prefix = _access_source(port)
    rows = rpc(
        port,
        model,
        "search_read",
        ([],),
        {"fields": ["group_id", "model_id"] + [f"{prefix}{p}" for p in _PERMS]},
    )
    out: dict[str, dict[str, list[str]]] = {}
    for row in rows:
        perms = [p for p in _PERMS if row.get(f"{prefix}{p}")]
        if perms:
            out.setdefault(_name(row.get("group_id")), {}).setdefault(
                _name(row.get("model_id")), []
            ).extend(perms)
    return out


def _data(port: Any, changeset: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, Any] = {}
    samples: dict[str, Any] = {}
    for op in changeset:
        if not str(op.get("type") or "").startswith(_DATA_PREFIX):
            continue
        model, expected, actual, rows = data_sample(port, op)
        counts[model] = {"expected": expected, "actual": actual}
        samples[model] = mask(rows)
    return {"counts": counts, "samples": samples}
