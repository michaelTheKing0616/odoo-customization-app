"""Re-record analysis vs the fix-plan gates (Tope, Oct 19).

  python evals/v2/rerecord_analyze.py REPLAY.json SCORE_ROWS.jsonl[,MORE] SHADOW.jsonl --split dev --split dev2

Gates: false_fold upper 95% CI <= 0.10 (point <= 0.10 required), invented only goes down, at most one brief loses
> 0.05 ITT coverage. Stability = mean pairwise Jaccard of built-model sets across reps of a brief.
Brief-level bootstrap (resample briefs, then runs within brief), paired off vs on.
"""
from __future__ import annotations

import collections, itertools, json, pathlib, random, statistics, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import yaml  # noqa: E402
from score import match  # noqa: E402

B = 2000


def jac(a, b):
    a, b = set(map(str.lower, a)), set(map(str.lower, b))
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def boot(groups: dict, stat, seed=11):
    rnd = random.Random(seed)
    keys = list(groups)
    vals = []
    for _ in range(B):
        ks = [rnd.choice(keys) for _ in keys]
        sample = {}
        for i, k in enumerate(ks):
            g = groups[k]
            sample[(k, i)] = [rnd.choice(g) for _ in g]
        v = stat(sample)
        if v is not None:
            vals.append(v)
    vals.sort()
    return (round(vals[int(0.025 * len(vals))], 3), round(vals[int(0.975 * len(vals)) - 1], 3)) if vals else (None, None)


def main():
    rep_path, score_paths, shadow_path = sys.argv[1], sys.argv[2].split(","), sys.argv[3]
    splits = [a for i, a in enumerate(sys.argv) if i > 0 and sys.argv[i - 1] == "--split"]
    gold = {}
    for sp in splits:
        for g in (HERE / sp).glob("*.gold.yaml"):
            gold[g.name.removesuffix(".gold.yaml")] = yaml.safe_load(g.read_text())
    out = json.loads(pathlib.Path(rep_path).read_text())
    off = {(r["id"], r["rep"]): r for r in out["rows"]["off"]}
    pairs = collections.defaultdict(list)  # brief -> [(off, on)]
    for r in out["rows"]["on"]:
        pairs[r["id"]].append((off[(r["id"], r["rep"])], r))

    # false fold: gold-entity models built off and gone on
    def ff_parts(o, n):
        ents = gold[o["id"]].get("entities") or []
        good = [m for m in o["models"] if any(match(e["name"], m) for e in ents)]
        return len([m for m in good if m not in n["models"]]), len(good)

    def ff_stat(sample):
        num = den = 0
        for runs in sample.values():
            for o, n in runs:
                a, b = ff_parts(o, n)
                num += a
                den += b
        return num / den if den else None

    lost = collections.Counter()
    for b, runs in pairs.items():
        for o, n in runs:
            ents = gold[b].get("entities") or []
            lost.update(f"{b}:{m}" for m in o["models"] if any(match(e["name"], m) for e in ents) and m not in n["models"])
    ff = ff_stat(pairs)

    inv = lambda s, k: statistics.mean(x[k]["inv_built"] for runs in s.values() for x in runs) if s else None  # noqa: E731
    inv_off = statistics.mean(o["inv_built"] for runs in pairs.values() for o, _ in runs)
    inv_on = statistics.mean(n["inv_built"] for runs in pairs.values() for _, n in runs)
    d_inv = boot(pairs, lambda s: statistics.mean(n["inv_built"] - o["inv_built"] for runs in s.values() for o, n in runs))
    built_off = statistics.mean(o["n_built"] for runs in pairs.values() for o, _ in runs)
    built_on = statistics.mean(n["n_built"] for runs in pairs.values() for _, n in runs)

    # ITT coverage: live score rows (shipped = authorizer off in shadow). Unreached runs = 0 in both arms.
    live = collections.defaultdict(list)
    for p in score_paths:
        for line in open(p):
            r = json.loads(line)
            if r.get("variant", "base") == "base" and r["id"] in gold and gold[r["id"]].get("needs"):
                live[r["id"]].append(r)
    itt = {}
    for b, rows in live.items():
        n_unreached = sum(1 for r in rows if r.get("kind") != "diagnosis" or not r.get("design"))
        rp = pairs.get(b, [])
        offc = [o["cov_itt"] for o, _ in rp if o["cov_itt"] is not None] + [0.0] * n_unreached
        onc = [n["cov_itt"] for _, n in rp if n["cov_itt"] is not None] + [0.0] * n_unreached
        if offc:
            itt[b] = list(zip(offc, onc))
    cov_off = statistics.mean(a for v in itt.values() for a, _ in v)
    cov_on = statistics.mean(b for v in itt.values() for _, b in v)
    d_cov = boot(itt, lambda s: statistics.mean(b - a for v in s.values() for a, b in v))
    drops = {b: round(statistics.mean(y for _, y in v) - statistics.mean(x for x, _ in v), 3) for b, v in itt.items()}
    big = {b: d for b, d in drops.items() if d < -0.05}

    # stability: pairwise Jaccard of built sets across reps
    def stab(s, arm):
        vals = []
        for runs in s.values():
            sets = [(o if arm == 0 else n)["models"] for o, n in runs]
            vals += [jac(a, b) for a, b in itertools.combinations(sets, 2)]
        return statistics.mean(vals) if vals else None
    st_off, st_on = stab(pairs, 0), stab(pairs, 1)
    d_st = boot(pairs, lambda s: (lambda a, b: None if a is None or b is None else b - a)(stab(s, 0), stab(s, 1)))

    # orphan repair (shadow)
    orph = [json.loads(l).get("orphan_repair") for l in open(shadow_path) if '"orphan_repair"' in l] if pathlib.Path(shadow_path).exists() else []
    orph = [o for o in orph if o]
    called = [o for o in orph if o.get("called")]
    orph_sum = {"designs_checked": len(orph), "designs_with_orphans": sum(1 for o in orph if o.get("orphans")),
                "llm_calls": len(called), "errors": sum(1 for o in orph if o.get("error")),
                "orphans_before": sum(len(o.get("orphans") or []) for o in called),
                "orphans_after": sum(len(o.get("orphans_after") or []) for o in called),
                "added": sum(len(o.get("added") or []) for o in orph),
                "unmet_models": sum(len(o.get("unmet_models") or []) for o in orph)}

    ffci = boot(pairs, ff_stat)
    gates = {"false_fold_point_le_0.10": ff is not None and ff <= 0.10,
             "false_fold_upper_ci_le_0.10": ffci[1] is not None and ffci[1] <= 0.10,
             "invented_not_up": inv_on <= inv_off,
             "cov_drop_gt_0.05_on_le_1_brief": len(big) <= 1}
    res = {"recordings": out["recordings"], "unmatched": out["unmatched"], "runs_paired": sum(len(v) for v in pairs.values()),
           "briefs": len(pairs),
           "false_fold": {"rate": round(ff, 3) if ff is not None else None, "ci95": ffci, "lost_top": lost.most_common(10)},
           "invented_per_run": {"off": round(inv_off, 3), "on": round(inv_on, 3), "delta_ci95": d_inv},
           "built_per_run": {"off": round(built_off, 3), "on": round(built_on, 3)},
           "itt_coverage": {"off": round(cov_off, 3), "on": round(cov_on, 3), "delta_ci95": d_cov, "briefs_drop_gt_0.05": big},
           "stability_jaccard": {"off": round(st_off, 3), "on": round(st_on, 3), "delta_ci95": d_st},
           "orphan_repair_shadow": orph_sum, "gates": gates, "all_required_pass": gates["false_fold_point_le_0.10"]
           and gates["invented_not_up"] and gates["cov_drop_gt_0.05_on_le_1_brief"]}
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
