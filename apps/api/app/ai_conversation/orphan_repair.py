"""Fix plan step 4: orphan-requirement repair. One targeted LLM call, only when the recall audit finds
in-scope contract rows nothing in the design realizes.

INGENIUM_ORPHAN_REPAIR=off|shadow|on (default off). shadow: make the call, log what it would add, change
nothing. on: merge only elements that cite an orphan id: fields on models already in the design or on stock
extensions, automations, python pieces. Never adds a model (a missing record goes to the log as unmet).
Logged to INGENIUM_SHADOW_LOG when set.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


def mode() -> str:
    m = os.environ.get("INGENIUM_ORPHAN_REPAIR", "off")
    return m if m in {"shadow", "on"} else "off"


def repair_prompt_issues(orphans: list[dict[str, Any]]) -> list[str]:
    out = []
    for r in orphans:
        q = str((r.get("evidence") or {}).get("quote") or "") if isinstance(r.get("evidence"), dict) else str(r.get("evidence") or "")
        out.append(f"Requirement {r.get('id')} ({r.get('kind')}: {r.get('subject')}; owner said: \"{q}\") has no field, "
                   "automation or python piece. Add the smallest element that realizes it on a model already in the design, "
                   "and set its requirement_id to that id. Do not add new models.")
    return out


def merge(design: Any, proposed: Any, orphan_ids: set[str]) -> dict[str, Any]:
    """Pure: copy only orphan-citing elements from proposed onto design. Returns what was (or would be) added."""
    have = {m.name: m for m in design.new_models}
    exts = {e.model: e for e in design.stock_extensions}
    added: dict[str, list] = {"fields": [], "automations": [], "python": [], "unmet_models": []}

    def cites(x: Any) -> set[str]:
        get = x.get if isinstance(x, dict) else (lambda k, d=None: getattr(x, k, d))
        return ({str(get("requirement_id") or "")} | {str(i) for i in get("requirement_ids") or []}) & orphan_ids

    for m in proposed.new_models:
        target = have.get(m.name)
        if target is None:
            if cites(m):
                added["unmet_models"].append(m.label or m.name)
            continue
        names = {f.name for f in target.fields}
        for f in m.fields:
            if cites(f) and f.name not in names:
                target.fields.append(f)
                added["fields"].append(f"{m.name}.{f.name}")
    for e in proposed.stock_extensions:
        for f in e.fields:
            if not cites(f):
                continue
            ext = exts.get(e.model)
            if ext is None:
                from app.ai_conversation.app_design import StockExtension

                ext = StockExtension(model=e.model, reason=e.reason)
                design.stock_extensions.append(ext)
                exts[e.model] = ext
            if f.name not in {x.name for x in ext.fields}:
                ext.fields.append(f)
                added["fields"].append(f"{e.model}.{f.name}")
    for a in proposed.automations:
        if cites(a) and a.get("target_model") in set(have) | set(exts):
            design.automations.append(a)
            added["automations"].append(a.get("label") or a.get("target_model"))
    for p in proposed.python_needed:
        if cites(p):
            design.python_needed.append(p)
            added["python"].append(p.get("label"))
    return added


def repair_step(design: Any, prompt: str, *, grounding: Any = None, schema_packet: Any = None, snapshot: Any = None,
                provider: Any = None) -> dict[str, Any]:
    """At most one LLM call. Returns a log record (also appended to INGENIUM_SHADOW_LOG)."""
    import copy
    import hashlib

    from app.ai_conversation import app_design as ad
    from app.ai_conversation.model_authorizer import orphan_requirements

    m = mode()
    if m == "off" or design is None:
        return {"mode": m, "called": False}
    orphans = orphan_requirements(design)
    rec: dict[str, Any] = {"at": time.time(), "brief_hash": hashlib.sha256(prompt.encode()).hexdigest()[:12], "mode": m,
                           "orphans": [r.get("id") for r in orphans], "called": False}
    if orphans and provider is not None:
        user = ad.design_user_prompt(prompt, grounding, schema_packet, budget=len(design.new_models), intent_contract=design.intent_contract,
                                     repair_issues=repair_prompt_issues(orphans), previous=design.to_dict(), snapshot=snapshot)
        parsed, meta = ad._call_llm(provider, user, ad.design_system_prompt(grounding), min(60.0, ad.design_timeout_for(prompt)))
        rec.update(called=True, status=meta.get("status"), model=meta.get("model"))
        if parsed:
            target = design if m == "on" else copy.deepcopy(design)
            rec["added"] = merge(target, ad.AppDesign.from_dict(parsed), {str(r.get("id")) for r in orphans})
            rec["orphans_after"] = [r.get("id") for r in orphan_requirements(target)]
    path = os.environ.get("INGENIUM_SHADOW_LOG")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"orphan_repair": rec}, default=str) + "\n")
        except OSError:
            logger.warning("orphan repair log failed", exc_info=True)
    return rec
