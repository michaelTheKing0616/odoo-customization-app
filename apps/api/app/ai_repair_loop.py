"""Constrained repair loop — patch implicated nodes only; lock after PASS."""

from __future__ import annotations

from typing import Any


DEFAULT_MAX_REPAIR = 3


def _locked_paths(draft: dict[str, Any]) -> set[str]:
    cert = draft.get("_certified_artifacts") if isinstance(draft.get("_certified_artifacts"), dict) else {}
    paths = cert.get("locked_files") or []
    return {str(p) for p in paths if str(p).strip()}


def implicated_files(failures: list[dict[str, Any]]) -> list[str]:
    files: list[str] = []
    for f in failures:
        if not isinstance(f, dict):
            continue
        path = f.get("file")
        if path and str(path) not in files:
            files.append(str(path))
    return files


def repair_allowed(
    draft: dict[str, Any],
    *,
    target_file: str,
) -> tuple[bool, str]:
    locked = _locked_paths(draft)
    if target_file in locked:
        return False, f"locked artifact: {target_file}"
    constraints: list[str] = []
    for f in draft.get("_failures") or []:
        if isinstance(f, dict):
            constraints.extend(str(c) for c in (f.get("repair_constraints") or []))
    if "preserve_architecture_plan" in constraints and target_file in {
        "_architecture_plan",
        "architecture_plan",
    }:
        return False, "preserve_architecture_plan"
    return True, "ok"


def thrashing_detected(draft: dict[str, Any]) -> bool:
    hist = draft.get("_repair_history") if isinstance(draft.get("_repair_history"), list) else []
    if len(hist) < 2:
        return False
    last = [str(h.get("fingerprint") or "") for h in hist[-3:] if isinstance(h, dict)]
    return len(last) >= 2 and len(set(last)) == 1


def begin_repair_attempt(draft: dict[str, Any], failures: list[dict[str, Any]]) -> dict[str, Any]:
    """Record repair attempt metadata; refuse if thrashing or over budget."""
    count = int(draft.get("_repair_count") or 0)
    if count >= DEFAULT_MAX_REPAIR:
        return {
            "ok": False,
            "reason": "max_repair_exceeded",
            "repair_count": count,
        }
    if thrashing_detected(draft):
        return {
            "ok": False,
            "reason": "thrashing_detected",
            "repair_count": count,
        }
    files = implicated_files(failures)
    allowed: list[str] = []
    blocked: list[str] = []
    for path in files:
        ok, why = repair_allowed(draft, target_file=path)
        if ok:
            allowed.append(path)
        else:
            blocked.append(f"{path}: {why}")
    # Always allow editing custom_code_blocks content for implicated paths
    if not allowed and failures:
        allowed = ["custom_code_blocks"]
        ok, why = repair_allowed(draft, target_file="custom_code_blocks")
        if not ok:
            return {"ok": False, "reason": why, "repair_count": count}

    fingerprint = "|".join(
        sorted(str(f.get("failure_id") or "") for f in failures if isinstance(f, dict))
    )
    hist = list(draft.get("_repair_history") or [])
    hist.append({"fingerprint": fingerprint, "files": allowed})
    draft["_repair_history"] = hist[-10:]
    draft["_repair_count"] = count + 1
    return {
        "ok": True,
        "repair_count": draft["_repair_count"],
        "allowed_files": allowed,
        "blocked": blocked,
        "constraints": [
            "max_files:2",
            "do_not_touch_locked",
            "preserve_architecture_plan",
        ],
    }


def apply_constrained_block_patch(
    draft: dict[str, Any],
    *,
    source_file: str,
    new_content: str,
) -> dict[str, Any]:
    """Replace one custom_code_block by source_file if repair allowed."""
    ok, why = repair_allowed(draft, target_file=source_file)
    if not ok:
        return {"ok": False, "reason": why}
    blocks = list(draft.get("custom_code_blocks") or [])
    found = False
    for i, b in enumerate(blocks):
        if not isinstance(b, dict):
            continue
        path = str(b.get("source_file") or b.get("path") or "")
        if path == source_file:
            blocks[i] = {**b, "content": new_content, "source_file": path}
            found = True
            break
    if not found:
        return {"ok": False, "reason": f"block not found: {source_file}"}
    draft["custom_code_blocks"] = blocks
    return {"ok": True, "source_file": source_file}


def lock_certified_artifacts(draft: dict[str, Any], *, run_id: str | None = None) -> dict[str, Any]:
    """After smoke/install PASS, lock file paths so repair cannot thrash them."""
    files: list[str] = []
    for b in draft.get("custom_code_blocks") or []:
        if isinstance(b, dict):
            path = str(b.get("source_file") or b.get("path") or "")
            if path:
                files.append(path)
    artifact = {
        "locked_files": sorted(set(files)),
        "run_id": run_id,
        "locked_at": "sandbox_pass",
    }
    draft["_certified_artifacts"] = artifact
    return artifact


def repair_guidance(failures: list[dict[str, Any]]) -> list[str]:
    """Human/Expert hints — no full regenerate."""
    hints: list[str] = []
    for f in failures:
        if not isinstance(f, dict):
            continue
        cat = f.get("category")
        msg = str(f.get("message") or "")[:200]
        path = f.get("file") or "custom_code_blocks"
        hints.append(f"repair({cat}) {path}: {msg}")
    return hints[:12]


__all__ = [
    "DEFAULT_MAX_REPAIR",
    "apply_constrained_block_patch",
    "begin_repair_attempt",
    "implicated_files",
    "lock_certified_artifacts",
    "repair_allowed",
    "repair_guidance",
    "thrashing_detected",
]
