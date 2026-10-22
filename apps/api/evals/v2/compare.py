"""Paired old/new comparison with a cluster bootstrap over briefs (repeats of one brief are one cluster).
usage: python evals/v2/compare.py OLD.json NEW.json [--metric need_coverage] [--n 2000]"""
import argparse, json, random, statistics


def per_brief(path, metric):
    out = {}
    for r in json.load(open(path))["results"]:
        if r.get("variant") == "base" and (r.get("score") or {}).get(metric) is not None:
            out.setdefault(r["id"], []).append(float(r["score"][metric]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old"); ap.add_argument("new")
    ap.add_argument("--metric", default="need_coverage"); ap.add_argument("--n", type=int, default=2000)
    a = ap.parse_args()
    old, new = per_brief(a.old, a.metric), per_brief(a.new, a.metric)
    briefs = sorted(set(old) & set(new))
    diffs = {b: statistics.mean(new[b]) - statistics.mean(old[b]) for b in briefs}
    rnd = random.Random(7)
    boots = sorted(statistics.mean(diffs[rnd.choice(briefs)] for _ in briefs) for _ in range(a.n)) if briefs else []
    lo, hi = (boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]) if boots else (None, None)
    print(json.dumps({"metric": a.metric, "briefs": len(briefs), "mean_diff": round(statistics.mean(diffs.values()), 4) if diffs else None,
                      "ci95": [lo, hi], "per_brief": diffs}, indent=1))


if __name__ == "__main__":
    main()
