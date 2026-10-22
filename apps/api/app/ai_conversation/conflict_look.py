"""Conflict look: an independent AI read of the QUOTED requirement rows, looking only for
contradictions. Code authorizes: both rows must exist, be stated, and have their quotes in the
owner's brief; then it turns the pair into one plain clarify question. At most MAX_BLOCKING
blocking questions in total; inferred extras never block."""
from __future__ import annotations

from typing import Any

from app.ai_conversation.intent_contract import MAX_BLOCKING, _CONFLICT_PREFIX, locate_evidence

SYSTEM = (
    "You read requirement rows quoted from a business owner's brief. Find pairs that contradict "
    "each other (the owner says two incompatible things about the same behaviour, e.g. who may "
    "approve, a limit, whether something is automatic). Do not invent requirements. Return JSON "
    '{"conflicts": [{"a": row id, "b": row id, "question": one plain question for the owner, '
    '"options": [2-3 short answers]}]}. Return {"conflicts": []} when there is none.'
)


def brief_sentences(prompt: str) -> list[dict[str, str]]:
    """The owner's own sentences (structural split), so a contradiction is visible even when the
    contract extractor merged or dropped one side."""
    import re

    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", prompt or "") if len(p.strip()) > 3]
    return [{"id": f"s{i + 1}", "subject": "", "quote": p[:300]} for i, p in enumerate(parts[:40])]


def rows_for_look(contract: list[dict[str, Any]], prompt: str = "") -> list[dict[str, str]]:
    out = brief_sentences(prompt)
    for r in contract:
        ev = r.get("evidence") if isinstance(r.get("evidence"), dict) else {}
        if r.get("origin") == "stated" and ev.get("quote"):
            out.append({"id": str(r.get("id")), "subject": str(r.get("subject") or "")[:120],
                        "quote": str(ev.get("quote"))[:300]})
    return out[:80]


def apply(contract: list[dict[str, Any]], raw: Any, prompt: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Code authorizes conflicts. Returns (contract, accepted conflicts)."""
    items = (raw or {}).get("conflicts") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return contract, []
    by_id = {str(r.get("id")): r for r in contract if r.get("id")}
    for srow in brief_sentences(prompt):  # sentence ids stand for the owner's words directly
        by_id.setdefault(srow["id"], {"id": srow["id"], "origin": "stated", "subject": "", "decision": "sentence",
                                      "evidence": {"quote": srow["quote"]}})
    blocking = sum(1 for r in contract if r.get("decision") == "clarify" and r.get("origin") != "inferred")
    accepted = []
    for c in items:
        if blocking >= MAX_BLOCKING or not isinstance(c, dict):
            break
        a, b = by_id.get(str(c.get("a"))), by_id.get(str(c.get("b")))
        if not a or not b or a is b:
            continue
        qa = str(((a.get("evidence") or {}).get("quote")) or "")
        qb = str(((b.get("evidence") or {}).get("quote")) or "")
        if a.get("origin") != "stated" or b.get("origin") != "stated" or not qa or not qb:
            continue
        if locate_evidence(prompt, qa) is None or locate_evidence(prompt, qb) is None:
            continue  # quotes must be in the owner's words
        if a.get("decision") == "clarify":
            continue
        opts = [str(o)[:80] for o in (c.get("options") or []) if str(o).strip()][:3]
        if a.get("decision") == "sentence":  # no contract row to mark: the decision carries the question
            blocking += 1
            accepted.append({"a": a["id"], "b": b.get("id"), "question": str(c.get("question") or "")[:240] or None,
                             "quote_a": qa, "quote_b": qb, "options": opts})
            continue
        a.update(decision="clarify", downgrade_reason=_CONFLICT_PREFIX + qb,
                 question=str(c.get("question") or "")[:240] or None,
                 options=[{"label": o, "decision": a.get("decision_before_conflict") or "metadata"} for o in opts] or a.get("options"),
                 conflict_with=str(b.get("id")))
        blocking += 1
        accepted.append({"a": a.get("id"), "b": b.get("id"), "question": a.get("question"),
                         "quote_a": qa, "quote_b": qb, "options": opts})
    return contract, accepted
