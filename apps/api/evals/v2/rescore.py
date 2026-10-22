"""Re-summarize a score.py output JSON with the fix-plan metrics (no network)."""
import json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import yaml  # noqa: E402
import metrics  # noqa: E402

rows = []
for path, split in zip(sys.argv[1::2], sys.argv[2::2]):
    for r in json.loads(pathlib.Path(path).read_text())["results"]:
        if r.get("variant", "base") == "base":
            rows.append(metrics.run_metrics(yaml.safe_load((HERE / split / f"{r['id']}.gold.yaml").read_text()), r))
print(json.dumps({k: metrics.fmt(v) for k, v in metrics.summarize(rows).items()}, indent=0))
