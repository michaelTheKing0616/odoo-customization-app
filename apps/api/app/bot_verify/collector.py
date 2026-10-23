"""NF BV-02: build verify()'s observation from live read-back only.

Takes a connection-scoped port (never run/artifact ids). Every call goes
through ``readback.rpc`` which refuses non-read methods. Change-set
success claims are never read.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from app.bot_verify.readback import READBACKS, PortUnavailable, data_sample, mask, rpc, target_model

PERSONAS: tuple[str, ...] = ("requester", "low_privilege", "portal")
DEFAULT_RETRY_AFTER_S = 5
_DATA_PREFIX = "data."
_PERMS = ("read", "write", "create", "unlink")

__all__ = ["DEFAULT_RETRY_AFTER_S", "OdooUnavailable", "PortUnavailable", "collect_observation"]


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


def collect_observation(
    port: Any,
    changeset: list[dict[str, Any]],
    *,
    baseline: Mapping[str, Any] | None = None,
    personas: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Return the mapping ``changeset.verify.verify`` reads.

    ``baseline`` carries pre-apply snapshots (fingerprint_before,
    expected_after, access_before, mail_before). ``personas`` maps persona
    name to Odoo uid. A 429/503 yields a skipped observation that verify()
    fails, with ``meta.retry_after_s``.
    """
    db_name = str(getattr(port, "db_name", "") or "")
    if not db_name.startswith("ingenium_"):
        raise ValueError("collector only reads ingenium_* databases")
    try:
        return _collect(port, changeset, baseline or {}, personas or {})
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
    post: dict[int, Any] = {}
    for index, op in enumerate(changeset):
        fn = READBACKS.get(str(op.get("type") or ""))
        post[index] = fn(port, op) if fn else {"evidence": {"reason": "unknown op"}}
    target = target_model(changeset)
    after = hashlib.sha256(json.dumps(post, sort_keys=True, default=str).encode()).hexdigest()
    return {
        "meta": {"status": "collected", "source": "live_readback"},
        "postconditions": post,
        "fingerprint": {
            "before": baseline.get("fingerprint_before"),
            "after": after,
            "expected_after": baseline.get("expected_after"),
        },
        "views": {name: _view(port, target, personas.get(name)) for name in PERSONAS},
        "smoke": _smoke(port, target),
        "access": {"before": baseline.get("access_before"), "after": _access(port)},
        "mail": {
            "before": baseline.get("mail_before"),
            "after": rpc(
                port, "mail.mail", "search_count", ([("state", "in", ["outgoing", "exception"])],)
            ),
        },
        "data": _data(port, changeset),
    }


def _view(port: Any, model: str | None, uid: int | None) -> dict[str, Any]:
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
    rows = rpc(port, model, "search_read", ([],), {"limit": 1, "fields": ["id"]})
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


def _access(port: Any) -> dict[str, dict[str, list[str]]]:
    rows = rpc(
        port,
        "ir.model.access",
        "search_read",
        ([],),
        {"fields": ["group_id", "model_id"] + [f"perm_{p}" for p in _PERMS]},
    )
    out: dict[str, dict[str, list[str]]] = {}
    for row in rows:
        perms = [p for p in _PERMS if row.get(f"perm_{p}")]
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
