"""Crash recovery. A partial apply is never reported as finished."""

from __future__ import annotations

from typing import Any

_ALLOWED = frozenset({"VERIFIED", "ROLLED_BACK", "NEEDS_HUMAN"})


def recover(entries: list[dict[str, Any]], *, mode: str, expected_ops: int) -> dict[str, Any]:
    if mode not in {"T", "C"}:
        raise ValueError("mode must be T or C")
    if expected_ops < 0:
        raise ValueError("expected_ops")
    results = [entry for entry in entries if entry.get("kind") == "RESULT"]
    compensates = [entry for entry in entries if entry.get("kind") == "COMPENSATE"]
    verified = any(entry.get("kind") == "VERIFIED" for entry in entries)
    verifying = any(entry.get("kind") == "VERIFYING" for entry in entries)
    result_indexes = [entry.get("index") for entry in results]
    report = {
        "results": result_indexes,
        "missing": [index for index in range(expected_ops) if index not in result_indexes],
        "compensates": [entry.get("index") for entry in compensates],
    }
    if any(entry.get("kind") == "UNKNOWN" for entry in entries):
        return {"status": "NEEDS_HUMAN", "report": report}
    compensated = set(report["compensates"]) >= set(result_indexes)
    if verified and not report["missing"] and len(results) == expected_ops:
        status = "VERIFIED"
    elif verified or (verifying and not results):
        status = "NEEDS_HUMAN"
    elif not results:
        status = "ROLLED_BACK"
    elif mode == "T":
        status = "ROLLED_BACK" if report["missing"] else "NEEDS_HUMAN"
    elif compensated:
        status = "ROLLED_BACK"
    else:
        status = "NEEDS_HUMAN"
    if status not in _ALLOWED or (status == "VERIFIED" and report["missing"]):
        status = "NEEDS_HUMAN"
    return {"status": status, "report": report}
