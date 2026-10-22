"""false_fold_rate + per-brief ITT coverage deltas from a replay.py output (fix plan c.6 / verification)."""
import json, pathlib, statistics, sys, collections

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import yaml  # noqa: E402
from score import match  # noqa: E402

out = json.loads(pathlib.Path(sys.argv[1]).read_text())
splits = sys.argv[2:]
gold = {}
for sp in splits:
    for g in (HERE / sp).glob("*.gold.yaml"):
        gold[g.name.removesuffix(".gold.yaml")] = yaml.safe_load(g.read_text())
off = {(r["id"], r["rep"]): r for r in out["rows"]["off"]}
true_off = false_fold = 0
lost = collections.Counter()
cov = collections.defaultdict(lambda: [[], []])
for r in out["rows"]["on"]:
    o = off[(r["id"], r["rep"])]
    ents = gold[r["id"]].get("entities") or []
    good_off = [m for m in o["models"] if any(match(e["name"], m) for e in ents)]
    true_off += len(good_off)
    gone = [m for m in good_off if m not in r["models"]]
    false_fold += len(gone)
    lost.update(f"{r['id']}:{m}" for m in gone)
    if o["cov_itt"] is not None:
        cov[r["id"]][0].append(o["cov_itt"]); cov[r["id"]][1].append(r["cov_itt"])
drops = {k: round(statistics.mean(b) - statistics.mean(a), 3) for k, (a, b) in cov.items()}
print(json.dumps({"false_fold_rate": round(false_fold / true_off, 3) if true_off else None,
                  "gold_entity_models_off": true_off, "lost": lost.most_common(12),
                  "briefs_cov_drop_gt_0.05": {k: v for k, v in drops.items() if v < -0.05}}, indent=1))
