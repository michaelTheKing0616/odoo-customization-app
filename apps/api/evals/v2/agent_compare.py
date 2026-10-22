"""Agent vs pipeline, paired by brief (cluster bootstrap over briefs; repeats are one cluster).
usage: python evals/v2/agent_compare.py PIPELINE.jsonl AGENT.jsonl --split dev --split dev2
Metrics: ITT coverage (unreached = 0), invented built models, gold-entity recall, false fold
(gold entity the pipeline covered that the agent leaves uncovered), reuse correctness (stock models
the gold names are used), stability (Jaccard of built sets across reps), latency, LLM calls, cost."""
import collections, itertools, json, pathlib, random, re, statistics, sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from metrics import run_metrics  # noqa: E402
from score import match  # noqa: E402

HERE = pathlib.Path(__file__).parent
_STOCK = re.compile(r"\b([a-z_]+\.[a-z_.]+)\b")


def load(path, gold):
    rows = collections.defaultdict(list)
    for line in open(path):
        r = json.loads(line)
        if r.get("variant", "base") == "base" and r["id"] in gold:
            rows[r["id"]].append(r)
    return rows


def covered(design, name):
    d = design or {}
    names = [m.get("label") or m.get("name") or "" for m in d.get("new_models") or []]
    names += [e.get("model") or "" for e in d.get("stock_extensions") or []]
    names += [f.get("relation") or "" for m in d.get("new_models") or [] for f in m.get("fields") or []]
    return any(match(name, n) for n in names if n)


def uses(design, model):
    blob = json.dumps(design or {})
    return f'"{model}"' in blob


def per_run(gold, r):
    m = run_metrics(gold, r)
    d = r.get("design") or {}
    ents = [e["name"] for e in gold.get("entities") or []]
    stock = sorted({x for a in gold.get("acceptable_alternates") or [] for x in _STOCK.findall(str(a))})
    m.update(ents={e for e in ents if m["reached"] and covered(d, e)}, n_ents=len(ents),
             reuse=(sum(uses(d, s) for s in stock) / len(stock)) if stock and m["reached"] else None,
             built=frozenset((x.get("label") or x.get("name") or "").lower() for x in d.get("new_models") or []),
             lat=r.get("latency_s"), calls=r.get("llm_calls") or 0, usd=((r.get("agent") or {}).get("usd_est") or 0.0))
    return m


def boot(clusters, stat, n=2000, seed=7):
    keys = sorted(clusters)
    rnd = random.Random(seed)
    vals = []
    for _ in range(n):
        v = stat({i: clusters[rnd.choice(keys)] for i in range(len(keys))})
        if v is not None:
            vals.append(v)
    vals.sort()
    return [round(vals[int(0.025 * len(vals))], 3), round(vals[int(0.975 * len(vals)) - 1], 3)] if vals else [None, None]


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def main():
    pipe_p, agent_p = sys.argv[1], sys.argv[2]
    splits = [a for i, a in enumerate(sys.argv) if i > 0 and sys.argv[i - 1] == "--split"]
    gold = {g.name.removesuffix(".gold.yaml"): yaml.safe_load(g.read_text())
            for sp in splits for g in (HERE / sp).glob("*.gold.yaml")}
    P, A = load(pipe_p, gold), load(agent_p, gold)
    pairs = {b: ([per_run(gold[b], r) for r in P[b]], [per_run(gold[b], r) for r in A[b]]) for b in sorted(set(P) & set(A))}

    def arm(s, i, k):
        return mean([x[k] for p in s.values() for x in p[i]])

    def delta(k):
        return lambda s: (lambda a, b: None if a is None or b is None else b - a)(arm(s, 0, k), arm(s, 1, k))

    def ff(s):
        num = den = 0
        for p, a in s.values():
            pe = set().union(*[x["ents"] for x in p]) if p else set()
            for x in a:
                num += len(pe - x["ents"])
                den += len(pe)
        return num / den if den else None

    def recall(s, i):
        return mean([len(x["ents"]) / x["n_ents"] for p in s.values() for x in p[i] if x["n_ents"]])

    def stab(s, i):
        return mean([len(a & b) / len(a | b) if a | b else 1.0 for p in s.values()
                     for a, b in itertools.combinations([x["built"] for x in p[i]], 2)])

    out = {"briefs": len(pairs), "runs": {"pipeline": sum(len(p) for p, _ in pairs.values()), "agent": sum(len(a) for _, a in pairs.values())}}
    for k, lab in (("cov_itt", "coverage_itt"), ("inv_built", "invented_per_run"), ("n_built", "built_per_run"),
                   ("reuse", "reuse_correctness"), ("lat", "latency_s"), ("calls", "llm_calls"), ("usd", "usd_est")):
        out[lab] = {"pipeline": round(arm(pairs, 0, k) or 0, 3), "agent": round(arm(pairs, 1, k) or 0, 3),
                    "delta_ci95": boot(pairs, delta(k))}
    out["entity_recall"] = {"pipeline": round(recall(pairs, 0) or 0, 3), "agent": round(recall(pairs, 1) or 0, 3),
                            "delta_ci95": boot(pairs, lambda s: (lambda a, b: None if a is None or b is None else b - a)(recall(s, 0), recall(s, 1)))}
    f = ff(pairs)
    out["false_fold_agent_vs_pipeline"] = {"rate": round(f, 3) if f is not None else None, "ci95": boot(pairs, ff)}
    out["stability"] = {"pipeline": round(stab(pairs, 0) or 0, 3), "agent": round(stab(pairs, 1) or 0, 3),
                        "delta_ci95": boot(pairs, lambda s: (lambda a, b: None if a is None or b is None else b - a)(stab(s, 0), stab(s, 1)))}
    out["per_brief_cov_delta"] = {b: round((mean([x["cov_itt"] for x in a]) or 0) - (mean([x["cov_itt"] for x in p]) or 0), 3)
                                  for b, (p, a) in pairs.items()}
    lat = sorted(x["lat"] for _, a in pairs.values() for x in a if x["lat"])
    out["agent_latency_p50_p95"] = [lat[len(lat) // 2], lat[int(len(lat) * 0.95) - 1]] if lat else None
    print(json.dumps(out, indent=1, default=list))


if __name__ == "__main__":
    main()
