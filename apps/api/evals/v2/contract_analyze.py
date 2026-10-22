import json, pathlib, sys, random, statistics
HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import yaml, metrics, score  # noqa: E401,E402
from score import match  # noqa: E402
rows = [json.loads(l) for l in pathlib.Path(sys.argv[1]).read_text().splitlines()]
per = []
for i, r in enumerate(rows):
    g = yaml.safe_load((HERE / f"{r['brief']}.gold.yaml").read_text())
    ents, alts = g.get("entities") or [], " ".join(g.get("acceptable_alternates") or [])
    lab = lambda d: [m.get("label") or m["name"] for m in d["new_models"]]  # noqa: E731
    isent = lambda m: any(match(e["name"], m) for e in ents)  # noqa: E731
    inv = lambda ms: sum(1 for m in ms if not isent(m) and not match(m, alts))  # noqa: E731
    off, on = lab(r["off"]), lab(r["on"])
    good = [m for m in off if isent(m)]
    per.append({"id": r["brief"], "rep": i, "inv_off": inv(off), "inv_on": inv(on), "good": len(good),
                "ff": sum(1 for m in good if m not in on), "n_off": len(off), "n_on": len(on),
                "roles": sum(1 for x in r["contract_roles"] if x[2])})
S = {"invented_off": lambda rs: statistics.mean(x["inv_off"] for x in rs),
     "invented_on": lambda rs: statistics.mean(x["inv_on"] for x in rs),
     "invented_delta": lambda rs: statistics.mean(x["inv_on"] - x["inv_off"] for x in rs),
     "false_fold_rate": lambda rs: (sum(x["ff"] for x in rs) / g) if (g := sum(x["good"] for x in rs)) else None,
     "built_off": lambda rs: statistics.mean(x["n_off"] for x in rs),
     "built_on": lambda rs: statistics.mean(x["n_on"] for x in rs)}
print(json.dumps({k: metrics.fmt(metrics.hboot(per, f)) for k, f in S.items()}, indent=0))
print("runs", len(per), "rows with roles", sum(1 for x in per if x["roles"]))
from collections import Counter
print("lost", Counter(f"{r['brief'].split('/')[-1]}:{m}" for r, x in zip(rows, per) for m in [mm.get("label") for mm in r["off"]["new_models"]] if m not in [mm.get("label") for mm in r["on"]["new_models"]]).most_common(12))
