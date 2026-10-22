"""Fix-plan eval metrics (c.3/c.6): intent-to-treat coverage, invention counts + micro-average,
built vs suggested/folded, hierarchical bootstrap CIs (briefs, then repeats), paired deltas.

Pure: works on result rows written by score.py (or replay.py). No network, no LLM.
"""
from __future__ import annotations

import random
import statistics
from typing import Any, Callable

B = 2000


def _models(d: dict) -> tuple[list[str], list[str]]:
    """Every new_models entry is built today (suggested = "allowed-but-flagged", still compiled);
    the suggested subset is reported separately. Folded/not-built items live in left_out."""
    built = [m.get("label") or m.get("name") or "" for m in (d or {}).get("new_models") or []]
    sugg = [m.get("label") or m.get("name") or "" for m in (d or {}).get("new_models") or [] if m.get("suggested")]
    return built, sugg


def run_metrics(gold: dict, r: dict) -> dict[str, Any]:
    """Per-run numbers. Unreached / errored runs count as coverage 0 (ITT) and invent nothing."""
    from score import match  # same name matcher as score.py

    d = r.get("design") or {}
    s = r.get("score") or {}
    reached = r.get("kind") == "diagnosis" and bool(d)
    needs = gold.get("needs") or []
    cov = s.get("need_coverage") if reached else None
    ge = gold.get("entities") or []
    alts = " ".join(gold.get("acceptable_alternates") or [])
    inv = lambda ms: [m for m in ms if not any(match(g["name"], m) for g in ge) and not match(m, alts)]  # noqa: E731
    built, sugg = _models(d) if reached else ([], [])
    folded = [x for x in d.get("left_out") or [] if isinstance(x, dict) and str(x.get("id", "")).startswith("model:")]
    return {"id": r["id"], "rep": r.get("rep", 0), "reached": reached,
            "cov_itt": (cov if cov is not None else 0.0) if needs else None,
            "cov_reached": cov,
            "n_built": len(built), "n_suggested": len(sugg), "n_folded": len(folded),
            "inv_built": len(inv(built)), "inv_suggested": len(inv(sugg)),
            "excl_violated": len(s.get("exclusions_violated") or []) if reached else 0,
            "severity": s.get("invented_severity", 0) if reached else 0}


def _group(rows: list[dict]) -> dict[str, list[dict]]:
    g: dict[str, list[dict]] = {}
    for x in rows:
        g.setdefault(x["id"], []).append(x)
    return g


def hboot(rows: list[dict], stat: Callable[[list[dict]], float | None], b: int = B, seed: int = 7) -> tuple:
    """Point estimate + 95% CI, resampling briefs then repeats within each brief."""
    g = _group(rows)
    ids = sorted(g)
    point = stat(rows)
    if point is None or not ids:
        return (point, None, None)
    rnd = random.Random(seed)
    vals = []
    for _ in range(b):
        sample = []
        for i in (rnd.choice(ids) for _ in ids):
            reps = g[i]
            sample += [rnd.choice(reps) for _ in reps]
        v = stat(sample)
        if v is not None:
            vals.append(v)
    vals.sort()
    lo, hi = vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]
    return (round(point, 3), round(lo, 3), round(hi, 3))


def _mean(k):
    return lambda rs: (statistics.mean(v) if (v := [x[k] for x in rs if x[k] is not None]) else None)


def _micro(num, den):
    return lambda rs: (sum(x[num] for x in rs) / d if (d := sum(x[den] for x in rs)) else 0.0)


STATS = {
    "coverage_itt": _mean("cov_itt"),
    "reached_rate": lambda rs: statistics.mean(1.0 if x["reached"] else 0.0 for x in rs) if rs else None,
    "invented_built_per_run": _mean("inv_built"),
    "invention_micro_built": _micro("inv_built", "n_built"),
    "invented_suggested_per_run": _mean("inv_suggested"),
    "built_models_per_run": _mean("n_built"),
    "folded_per_run": _mean("n_folded"),
    "severity_per_run": _mean("severity"),
    "exclusion_violations_per_run": _mean("excl_violated"),
}


def summarize(rows: list[dict]) -> dict[str, tuple]:
    return {k: hboot(rows, f) for k, f in STATS.items()}


def paired(a: list[dict], b: list[dict]) -> dict[str, tuple]:
    """CI of (b - a) on runs present in both arms, keyed (brief, repeat); same resampling for both arms."""
    ka = {(x["id"], x["rep"]): x for x in a}
    pairs = [(ka[(x["id"], x["rep"])], x) for x in b if (x["id"], x["rep"]) in ka]
    rows = [{"id": p[0]["id"], "rep": p[0]["rep"], "a": p[0], "b": p[1]} for p in pairs]
    out = {}
    for k, f in STATS.items():
        def d(rs, f=f):
            va, vb = f([r["a"] for r in rs]), f([r["b"] for r in rs])
            return None if va is None or vb is None else vb - va
        out[k] = hboot(rows, d)
    return out


def fmt(t: tuple) -> str:
    p, lo, hi = t
    return "n/a" if p is None else (f"{p}" if lo is None else f"{p} [{lo}, {hi}]")
