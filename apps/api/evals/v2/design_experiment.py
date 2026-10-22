"""Fix plan discriminating experiments: design stage only, contract frozen, fresh (cache bypass).

  python evals/v2/design_experiment.py --rec /tmp/fp_rec --briefs dev2/salon_voice,... \
      --cells control,budget_none,gapfill_drop,temp_default,rules_v2 --n 10 --out OUT.json

The frozen contract is the intent_contract of the first recording of each brief; grounding and snapshot
are None for every cell (identical inputs, only the knob differs). Calls the design LLM step directly
(_call_llm), so there is no cache and no Odoo DB access at all. Rows are appended to OUT.jsonl (resumable).
"""
from __future__ import annotations

import argparse, concurrent.futures as cf, json, os, pathlib, sys, threading

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import yaml  # noqa: E402

CELLS = {
    "control": {},
    "budget_none": {"INGENIUM_DESIGN_BUDGET": "none"},
    "budget_one": {"INGENIUM_DESIGN_BUDGET": "one"},
    "gapfill_drop": {"INGENIUM_DESIGN_GAPFILL": "drop"},
    "temp_default": {"INGENIUM_DESIGN_TEMPERATURE": "default"},
    "temp_zero": {"INGENIUM_DESIGN_TEMPERATURE": "0"},
    "rules_v2": {"INGENIUM_DESIGN_RULES": "v2"},
}
_KNOBS = ("INGENIUM_DESIGN_BUDGET", "INGENIUM_DESIGN_GAPFILL", "INGENIUM_DESIGN_TEMPERATURE", "INGENIUM_DESIGN_RULES")
_lock = threading.Lock()


def frozen_inputs(rec_dir: str, case_text: str) -> tuple[str, list] | None:
    from replay import _norm

    t = _norm(case_text)
    for p in sorted(pathlib.Path(rec_dir).glob("*.json"), key=lambda p: int(p.stem.split("-")[1])):
        r = json.loads(p.read_text())
        b = _norm(r["brief"])
        if t in b or b in t:
            return r["brief"], r["design"].get("intent_contract") or []
    return None


def one(cell: str, brief: str, contract: list, conn: str) -> dict:
    from app.ai_client.ai_scope import ai_scope
    from app.ai_conversation import app_design as ad
    from app.llm_provider import get_llm_provider_for_tier

    with _lock:  # knobs are process env: build the prompt under a lock, then call
        for k in _KNOBS:
            os.environ.pop(k, None)
        os.environ.update(CELLS[cell])
        system = ad.design_system_prompt(None)
        user = ad.design_user_prompt(brief, None, None, budget=ad.model_budget_for(brief), intent_contract=contract)
        temp = ad.design_knobs()["temperature"]
    provider = get_llm_provider_for_tier("fast")
    with ai_scope(db=conn, fresh=True, surface="internal"):
        try:
            raw = provider.generate_json(user, system=system, timeout_s=180.0) if temp == "default" else \
                provider.generate_json(user, system=system, timeout_s=180.0, temperature=float(temp))
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)[:200]}
    parsed = ad._parse_json(raw)
    if not parsed:
        return {"error": "unparsed"}
    d = ad.AppDesign.from_dict(parsed)
    return {"models": [{"label": m.label or m.name, "suggested": m.suggested, "evidence": m.evidence} for m in d.new_models],
            "folded": d.folded}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", required=True)
    ap.add_argument("--briefs", required=True)
    ap.add_argument("--cells", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    conn = os.environ.get("EVAL_CONNECTION", "")
    if not conn:
        sys.exit("set EVAL_CONNECTION to the disposable connection id (scope only; no DB access)")
    log = pathlib.Path(a.out + ".jsonl")
    done = {(r["brief"], r["cell"], r["i"]) for r in map(json.loads, log.read_text().splitlines())} if log.exists() else set()
    inputs = {}
    for b in a.briefs.split(","):
        fi = frozen_inputs(a.rec, (HERE / f"{b}.md").read_text())
        if not fi:
            sys.exit(f"no recording for {b}")
        inputs[b] = fi
    jobs = [(b, c, i) for b in inputs for c in a.cells.split(",") for i in range(a.n) if (b, c, i) not in done]
    print(json.dumps({"remaining": len(jobs)}), flush=True)
    with cf.ThreadPoolExecutor(a.workers) as pool:
        futs = {pool.submit(one, c, *inputs[b], conn): (b, c, i) for b, c, i in jobs}
        for f in cf.as_completed(futs):
            b, c, i = futs[f]
            row = {"brief": b, "cell": c, "i": i, **f.result()}
            with _lock, log.open("a") as fh:
                fh.write(json.dumps(row) + "\n")
            print(json.dumps({"brief": b, "cell": c, "i": i, "n": len(row.get("models") or []), "err": row.get("error")}), flush=True)
    analyze(log, a.out)


def analyze(log: pathlib.Path, out: str) -> None:
    import random
    import statistics

    from score import match

    rows = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
    gold = {}
    for r in rows:
        if r["brief"] not in gold:
            gold[r["brief"]] = yaml.safe_load((HERE / f"{r['brief']}.gold.yaml").read_text())

    def inv(r):
        g = gold[r["brief"]]
        ge, alts = g.get("entities") or [], " ".join(g.get("acceptable_alternates") or [])
        built = [m["label"] for m in r.get("models") or []]  # suggested models are still built today
        return len(built), sum(1 for m in built if not any(match(e["name"], m) for e in ge) and not match(m, alts))

    cells: dict[str, dict[str, list]] = {}
    for r in rows:
        if r.get("error"):
            continue
        cells.setdefault(r["cell"], {}).setdefault(r["brief"], []).append(inv(r) + (frozenset(m["label"].lower() for m in r["models"]),))

    def stat(by_brief, k):
        v = [x[k] for xs in by_brief.values() for x in xs]
        return statistics.mean(v) if v else None

    def stability(by_brief):
        js = []
        for xs in by_brief.values():
            sets = [x[2] for x in xs]
            js += [len(a & b) / len(a | b) if (a | b) else 1.0 for i, a in enumerate(sets) for b in sets[i + 1:]]
        return statistics.mean(js) if js else None

    def boot_diff(ca, cb, f, B=2000, seed=11):
        rnd = random.Random(seed)
        briefs = sorted(set(ca) & set(cb))
        pt = f({b: cb[b] for b in briefs}) - f({b: ca[b] for b in briefs})
        vals = []
        for _ in range(B):
            sa, sb = {}, {}
            for j, b in enumerate(rnd.choice(briefs) for _ in briefs):  # stratified: resample briefs, then runs
                sa[(b, j)] = [rnd.choice(ca[b]) for _ in ca[b]]
                sb[(b, j)] = [rnd.choice(cb[b]) for _ in cb[b]]
            vals.append(f(sb) - f(sa))
        vals.sort()
        return [round(pt, 3), round(vals[50], 3), round(vals[1949], 3)]

    fns = {"built": lambda d: stat(d, 0), "invented_built": lambda d: stat(d, 1), "stability": stability}
    summary = {"cells": {c: {"runs": sum(len(v) for v in d.values()), **{k: round(f(d), 3) for k, f in fns.items()}}
                         for c, d in cells.items()},
               "errors": sum(1 for r in rows if r.get("error"))}
    if "control" in cells:
        summary["delta_vs_control_95ci"] = {c: {k: boot_diff(cells["control"], d, f) for k, f in fns.items()}
                                            for c, d in cells.items() if c != "control"}
    pathlib.Path(out).write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
