"""BENCH-40: Bots tier/refusal bench (offline on versioncaps data; live stub needs ODOO_LIVE=1).

Splits: each task id is assigned at creation by sha256(id) -> "dev" or "holdout" (sealed).
The holdout file is never read unless EVAL_UNSEAL=yes (same rule as evals/v2/score.py,
INV-16); seal_manifest.json pins its sha256 so tampering is visible without reading it.
Loop-fed tasks (refused/failed real tasks) go to candidates.jsonl (append-only) and enter a
split only via promote(..., reviewer=...), into the split their id hashes to.

Task: {id, task (catalogue id) + optional fields/module_hint | parts [id or {task, fields,
module_hint}], about, apps (what the owner installed), installed ({version: apps closed over
real manifest depends + auto_install, from module_deps.json}), edition, versions (default
17-20), expect (grade or {version: grade}), until_capability (tier whose readiness flips the
expectation to "ok")}. module_deps.json is dumped from the odoo:17..20 images' __manifest__.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.bots import tiers as tt

HERE = Path(__file__).parent
DEV = HERE / "dev.json"
HOLDOUT = HERE / "holdout.json"
MANIFEST = HERE / "seal_manifest.json"
CANDIDATES = HERE / "candidates.jsonl"
DEPS = HERE / "module_deps.json"
DEFAULT_VERSIONS = (17, 18, 19, 20)
ID_RE = re.compile(r"^b40-[0-9a-z-]+$")
PART_KEYS = frozenset({"task", "fields", "module_hint"})
# promote() copies only these keys from a candidate; expect/until_capability/reviewed_by come
# from the reviewer's arguments, never from candidate data.
PROMOTE_KEYS = frozenset(
    {
        "id",
        "task",
        "parts",
        "about",
        "apps",
        "installed",
        "edition",
        "fields",
        "module_hint",
        "versions",
    }
)


class Sealed(PermissionError):
    pass


def split_of(task_id: str) -> str:
    return "holdout" if hashlib.sha256(task_id.encode()).digest()[0] % 2 else "dev"


def file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def closure(apps: list[str], version: int) -> list[str]:
    """Modules real Odoo installs for ``apps``: depends closure plus auto_install modules whose
    triggers are installed (country-bound localisations excluded)."""
    deps = json.loads(DEPS.read_text())[str(version)]
    got: set[str] = set()

    def add(m: str) -> None:
        if m not in got:
            if m not in deps:
                raise KeyError(f"{m} not a stock module in Odoo {version}")
            got.add(m)
            for d in deps[m]["d"]:
                add(d)

    for m in ["base", "web", *apps]:
        add(m)
    while True:
        new = [
            m
            for m, r in deps.items()
            if m not in got
            and r.get("a")
            and not r.get("c")
            and r["d"]
            and all(x in got for x in (r["d"] if r["a"] is True else r["a"]))
        ]
        if not new:
            return sorted(got)
        for m in new:
            add(m)


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


def _part(p: Any) -> dict[str, Any]:
    if isinstance(p, str):
        return {"task": p}
    if not isinstance(p, dict) or not isinstance(p.get("task"), str) or set(p) - PART_KEYS:
        raise ValueError(f"bad part {p!r}: needs task, optional fields/module_hint only")
    return p


def check_task(task: dict[str, Any]) -> None:
    if not isinstance(task.get("id"), str) or not ID_RE.match(task["id"]):
        raise ValueError("task id must match ^b40-[0-9a-z-]+$")
    if "parts" in task:
        if "task" in task or "fields" in task or "module_hint" in task:
            raise ValueError("multi-part task: put task/fields/module_hint on each part")
        if not isinstance(task["parts"], list) or not task["parts"]:
            raise ValueError("parts must be a non-empty list")
        for p in task["parts"]:
            _part(p)
    elif not isinstance(task.get("task"), str):
        raise ValueError("task needs task or parts")


def _installed(task: dict[str, Any], version: int) -> list[str]:
    inst = task.get("installed", ["base"])
    return list(inst[str(version)] if isinstance(inst, dict) else inst)


def grade(task: dict[str, Any], version: int) -> tt.Assessment | tt.Plan:
    check_task(task)
    kw = {
        "version": version,
        "edition": task.get("edition", "community"),
        "installed_modules": _installed(task, version),
    }
    if "parts" in task:
        return tt.compose(
            tt.assess(p["task"], fields=p.get("fields", ()), module_hint=p.get("module_hint"), **kw)
            for p in map(_part, task["parts"])
        )
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
        "versions": sorted({r["v"] for r in rows}),
        "fails": [r for r in rows if not r["pass"]],
    }


def _candidates() -> list[dict[str, Any]]:
    return [json.loads(x) for x in CANDIDATES.read_text().splitlines() if x.strip()]


def append_candidate(task: dict[str, Any], *, source: str, note: str) -> None:
    """One-way: real refused/failed tasks queue here for review; never enter a split."""
    check_task(task)
    if any(r["task"]["id"] == task["id"] for r in _candidates()):
        raise ValueError(f"duplicate candidate id {task['id']}")
    rec = {"task": task, "source": source, "note": note, "split": split_of(task["id"])}
    with CANDIDATES.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def promote(
    task_id: str, *, reviewer: str, expect: Any, until_capability: int | None = None
) -> str:
    """Reviewed promotion of a candidate into the split its id hashes to. Holdout promotion
    also needs EVAL_UNSEAL=yes and re-seals the manifest with the reviewer's name."""
    if not reviewer.strip():
        raise PermissionError("promotion needs a named reviewer")
    recs = [r for r in _candidates() if r["task"]["id"] == task_id]
    if len(recs) != 1:
        raise KeyError(f"{task_id}: {len(recs)} candidates match, need exactly 1")
    split = split_of(task_id)
    task = {k: v for k, v in recs[0]["task"].items() if k in PROMOTE_KEYS}
    task.update(expect=expect, reviewed_by=reviewer)
    if until_capability is not None:
        task["until_capability"] = int(until_capability)
    check_task(task)
    tasks = load(split)
    if any(t["id"] == task_id for t in tasks):
        raise ValueError("already in bench")
    path = HOLDOUT if split == "holdout" else DEV
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(tasks + [task], indent=1, sort_keys=True) + "\n")
    tmp.replace(path)
    if split == "holdout":
        seal(reviewer, note=f"promote {task_id}")
    return split


def seal(reviewer: str, *, note: str = "") -> None:
    """Re-pin the holdout hash. Needs EVAL_UNSEAL=yes and a named reviewer; appends a history
    record (old hash, new hash, reviewer, timestamp)."""
    if os.environ.get("EVAL_UNSEAL") != "yes":
        raise Sealed("re-sealing needs EVAL_UNSEAL=yes")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise PermissionError("re-sealing needs a named reviewer")
    old = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    new = file_sha(HOLDOUT)
    hist = list(old.get("history", []))
    hist.append(
        {
            "old": old.get("sha256"),
            "new": new,
            "reviewer": reviewer.strip(),
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "note": note,
        }
    )
    m = {"sha256": new, "count": len(json.loads(HOLDOUT.read_text())), "history": hist}
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    tmp.replace(MANIFEST)


if __name__ == "__main__":
    out = run(load(sys.argv[1] if len(sys.argv) > 1 else "dev"))
    print(json.dumps({k: v for k, v in out.items() if k != "fails"}), len(out["fails"]), "fails")
