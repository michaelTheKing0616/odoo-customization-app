"""Bridge B5 (spec 12-15): dead-letter inbox with fix + replay, contract tests from samples,
schema-drift alerts with proposed fixes, and a sandbox run (read-only) before live.
"""

from __future__ import annotations

import json
from typing import Any

from app.bridge import mapping as bm
from app.bridge import sync_rules as sr
from app.bridge.queue import _reject_secret_keys, enqueue


# ---------------------------------------------------------------- 12 dead-letter inbox
def list_dead(db: Any, connection_ids: list[str], limit: int = 200) -> list[dict[str, Any]]:
    from app.db_models import IntegrationEvent

    rows = (
        db.query(IntegrationEvent)
        .filter(
            IntegrationEvent.connection_id.in_(connection_ids), IntegrationEvent.status == "dead"
        )
        .order_by(IntegrationEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "connection_id": r.connection_id,
            "attempts": r.attempts,
            "payload": json.loads(r.payload_json),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def replay(db: Any, event: Any, patched_payload: dict[str, Any] | None = None) -> Any:
    """Requeue a dead event (optionally fixed). The original stays as history (status=replayed)."""
    if event.status != "dead":
        raise ValueError("Only dead events can be replayed.")
    payload = patched_payload if patched_payload is not None else json.loads(event.payload_json)
    _reject_secret_keys(payload)
    root, _, prev = event.idempotency_key.partition(":replay:")
    key = f"{root}:replay:{int(prev or 0) + 1}"
    new = enqueue(db, event.connection_id, key, payload)
    event.status = "replayed"
    return new


# ---------------------------------------------------------------- 13 contract tests from samples
def contract_tests(
    mapping: list[dict[str, Any]],
    remote_fields: dict[str, str],
    odoo_fields: dict[str, dict[str, Any]],
    samples: list[dict[str, Any]],
) -> dict[str, Any]:
    errs = bm.validate_mapping(mapping, remote_fields, odoo_fields)
    cases = []
    for i, p in enumerate(bm.preview(mapping, samples)):
        problems = list(p["problems"])
        for name, f in odoo_fields.items():
            if (
                f.get("required")
                and not f.get("default_set")
                and name not in bm.READONLY_SKIP
                and p["values"].get(name) in (None, "")
            ):
                problems.append(f"{name} would be empty")
        cases.append({"sample": i, "ok": not problems, "problems": problems})
    ok = not errs and bool(cases) and all(c["ok"] for c in cases)
    return {
        "ok": ok,
        "mapping_errors": errs,
        "cases": cases,
        "why_blocked": None if ok else "Fix these before the change goes live.",
    }


# ---------------------------------------------------------------- 14 schema drift
def detect_drift(
    declared: dict[str, str],
    observed: dict[str, str],
    mapping: list[dict[str, Any]],
    odoo_fields: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    added = sorted(set(observed) - set(declared))
    removed = sorted(set(declared) - set(observed))
    changed = sorted(k for k in set(declared) & set(observed) if declared[k] != observed[k])
    mapped = {m["remote"]: m for m in mapping if m.get("odoo")}
    fixes: list[dict[str, Any]] = []
    for k in removed:
        if k in mapped:
            fixes.append(
                {
                    "kind": "unmap",
                    "remote": k,
                    "odoo": mapped[k]["odoo"],
                    "why": f"{k} no longer sent",
                }
            )
    for k in changed:
        if k in mapped and odoo_fields and mapped[k]["odoo"] in odoo_fields:
            ok, why = bm.check_pair(observed[k], odoo_fields[mapped[k]["odoo"]])
            if not ok:
                fixes.append(
                    {
                        "kind": "retype",
                        "remote": k,
                        "odoo": mapped[k]["odoo"],
                        "why": why,
                        "transform": bm.default_transform(
                            observed[k], odoo_fields[mapped[k]["odoo"]]
                        ),
                    }
                )
    if added and odoo_fields:
        taken = {m["odoo"] for m in mapping if m.get("odoo")}
        free = {n: f for n, f in odoo_fields.items() if n not in taken}
        for s in bm.suggest({k: observed[k] for k in added}, free):
            if s["odoo"]:
                fixes.append({"kind": "map_new", **s})
    severity = (
        "breaking"
        if any(f["kind"] in ("unmap", "retype") for f in fixes)
        else ("info" if added else "none")
    )
    return {
        "added": added,
        "removed": removed,
        "type_changed": changed,
        "severity": severity,
        "proposed_fixes": fixes,
    }


# ---------------------------------------------------------------- 15 sandbox run (read-only)
def sandbox_run(
    client: Any,
    model: str,
    mapping: list[dict[str, Any]],
    remote_fields: dict[str, str],
    samples: list[dict[str, Any]],
) -> dict[str, Any]:
    fields = bm.odoo_fields(client, model)
    tests = contract_tests(mapping, remote_fields, fields, samples)
    plan = []
    for p in bm.preview(mapping, samples):
        m = sr.match_record(p["values"], sr.odoo_candidates(client, model, p["values"]))
        plan.append(
            {
                "values": p["values"],
                "would": m["action"],
                "id": m.get("id"),
                "ids": m.get("ids"),
                "why": m.get("why"),
            }
        )
    counts = {a: sum(1 for x in plan if x["would"] == a) for a in ("create", "link", "review")}
    return {
        "sandbox": True,
        "writes": 0,
        "tests": tests,
        "plan": plan,
        "counts": counts,
        "ready_for_live": tests["ok"] and counts["review"] == 0,
    }
