"""BENCH-40: Bots tier/refusal bench (offline on versioncaps data; live stub needs ODOO_LIVE=1).

Splits: each task id is assigned at creation by sha256(id) -> "dev" or "holdout" (sealed).
The holdout file is never read unless EVAL_UNSEAL=yes (same rule as evals/v2/score.py,
INV-16); seal_manifest.json pins its sha256 so tampering is visible without reading it.
Loop-fed tasks (refused/failed real tasks) go to candidates.jsonl (append-only) and enter a
split only via promote(..., reviewer=...), into the split their id hashes to.

Task: {id, task (catalogue id) | parts [ids], about, installed, edition, fields, module_hint,
versions (default 17,20; add 19 when delta), expect (grade or {version: grade}),
until_capability (tier whose readiness flips the expectation to "ok")}.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from app.bots import tiers as tt

HERE = Path(__file__).parent
DEV = HERE / "dev.json"
HOLDOUT = HERE / "holdout.json"
MANIFEST = HERE / "seal_manifest.json"
CANDIDATES = HERE / "candidates.jsonl"
DEFAULT_VERSIONS = (17, 20)


class Sealed(PermissionError):
    pass


def split_of(task_id: str) -> str:
    return "holdout" if hashlib.sha256(task_id.encode()).digest()[0] % 2 else "dev"


def file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(split: str) -> list[dict[str, Any]]:
    if split == "holdout":
        if os.environ.get("EVAL_UNSEAL") != "yes":
            raise Sealed("holdout is sealed; set EVAL_UNSEAL=yes only for the final evaluation")
        if file_sha(HOLDOUT) != json.loads(MANIFEST.read_text())["sha256"]:
            raise Sealed("holdout changed since it was sealed")
        return json.loads(HOLDOUT.read_text())
    if split != "dev":
        raise ValueError(split)
    return json.loads(DEV.read_text())


def expected(task: dict[str, Any], version: int) -> str:
    cap = task.get("until_capability")
    if cap is not None and tt.tier_ready(int(cap)):
        return tt.OK  # the capability landed: refusal is no longer the right answer
    e = task["expect"]
    return e[str(version)] if isinstance(e, dict) else e


def grade(task: dict[str, Any], version: int) -> tt.Assessment | tt.Plan:
    kw = {
        "version": version,
        "edition": task.get("edition", "community"),
        "installed_modules": list(task.get("installed", ["base"])),
    }
    if "parts" in task:
        return tt.compose(tt.assess(p, **kw) for p in task["parts"])
    return tt.assess(
        task["task"], fields=task.get("fields", ()), module_hint=task.get("module_hint"), **kw
    )


def run(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for t in tasks:
        for v in t.get("versions", DEFAULT_VERSIONS):
            got = grade(t, v).grade
            exp = expected(t, v)
            rows.append(
                {
                    "id": t["id"],
                    "v": v,
                    "expect": exp,
                    "got": got,
                    "pass": got == exp,
                    "boundary": exp != tt.OK,
                    "flipped": t.get("until_capability") is not None and exp == tt.OK,
                }
            )
    b = [r for r in rows if r["boundary"]]
    return {
        "n": len(rows),
        "passed": sum(r["pass"] for r in rows),
        "boundary_n": len(b),
        "boundary_passed": sum(r["pass"] for r in b),
        "flipped": sum(r["flipped"] for r in rows),
        "fails": [r for r in rows if not r["pass"]],
    }


def append_candidate(task: dict[str, Any], *, source: str, note: str) -> None:
    """One-way: real refused/failed tasks queue here for review; never enter a split."""
    if not task.get("id") or not (task.get("task") or task.get("parts")):
        raise ValueError("candidate needs id and task/parts")
    rec = {"task": task, "source": source, "note": note, "split": split_of(task["id"])}
    with CANDIDATES.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def promote(task_id: str, *, reviewer: str, expect: Any) -> str:
    """Reviewed promotion of a candidate into the split its id hashes to. Holdout promotion
    also needs EVAL_UNSEAL=yes and re-seals the manifest."""
    if not reviewer.strip():
        raise PermissionError("promotion needs a named reviewer")
    recs = [json.loads(x) for x in CANDIDATES.read_text().splitlines() if x.strip()]
    rec = next((r for r in recs if r["task"]["id"] == task_id), None)
    if rec is None:
        raise KeyError(task_id)
    split = split_of(task_id)
    task = dict(rec["task"], expect=expect, reviewed_by=reviewer)
    tasks = load(split)
    if any(t["id"] == task_id for t in tasks):
        raise ValueError("already in bench")
    path = HOLDOUT if split == "holdout" else DEV
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(tasks + [task], indent=1, sort_keys=True) + "\n")
    tmp.replace(path)
    if split == "holdout":
        seal()
    return split


def seal() -> None:
    m = {"sha256": file_sha(HOLDOUT), "count": len(json.loads(HOLDOUT.read_text()))}
    MANIFEST.write_text(json.dumps(m, sort_keys=True) + "\n")


if __name__ == "__main__":
    out = run(load(sys.argv[1] if len(sys.argv) > 1 else "dev"))
    print(json.dumps({k: v for k, v in out.items() if k != "fails"}), len(out["fails"]), "fails")
