"""Offline replay (fix plan c.1): recorded pre-authorizer designs -> downstream repairs -> score.

  python evals/v2/replay.py --rec DIR --split dev [--split dev2 ...] --out OUT.json

Arms: "off" (authorizer off) vs "on" (authorizer applied); same recorded design for both arms, so the
deltas are paired and exact. Zero LLM calls. Downstream = strengthen_design + final pass (dedupe,
ensure_jobs, complete_from_brief, scope_and_limits). validate_and_repair needs the live snapshot and is
not replayed (same for both arms).
"""
from __future__ import annotations

import argparse, copy, json, os, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import yaml  # noqa: E402

import metrics  # noqa: E402
import score  # noqa: E402


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").lower()).strip()


def case_for(brief: str, cases: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    b = _norm(brief)
    best = None
    for cid, (split, text) in cases.items():
        t = _norm(text)
        if t and (t in b or b in t):
            best = max(best or (0, None), (len(t), (split, cid)))
    return best[1] if best else None


def downstream(raw: dict, brief: str, mode: str) -> dict:
    from dataclasses import asdict

    from app.ai_conversation.app_design import AppDesign
    from app.ai_conversation import design_quality as dq

    os.environ["INGENIUM_MODEL_AUTHORIZER"] = mode
    os.environ.pop("INGENIUM_RECORD_DIR", None)
    d = AppDesign.from_dict(copy.deepcopy(raw))
    dq.strengthen_design(d, brief)
    d.notes = list(dict.fromkeys(d.notes + dq.dedupe_fields(d) + dq.ensure_jobs(d, brief)
                                 + dq.complete_from_brief(d, brief) + dq.scope_and_limits(d, brief)))
    return asdict(d)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", required=True)
    ap.add_argument("--split", action="append", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cases = {}
    for sp in a.split:
        for c in sorted((HERE / sp).glob("*.md")):
            cases[c.stem] = (sp, c.read_text())
    recs = sorted(pathlib.Path(a.rec).glob("*.json"), key=lambda p: int(p.stem.split("-")[1]))
    reps: dict[str, int] = {}
    rows = {"off": [], "on": []}
    unmatched = 0
    for p in recs:
        rec = json.loads(p.read_text())
        hit = case_for(rec["brief"], cases)
        if not hit:
            unmatched += 1
            continue
        sp, cid = hit
        rep = reps.get(cid, 0)
        reps[cid] = rep + 1
        gold = yaml.safe_load((HERE / sp / f"{cid}.gold.yaml").read_text())
        for mode in rows:
            d = downstream(rec["design"], rec["brief"], mode)
            r = {"id": cid, "rep": rep, "kind": "diagnosis", "design": d}
            r["score"] = score.score(gold, r)
            rows[mode].append(metrics.run_metrics(gold, r) | {"models": [m.get("label") for m in d["new_models"]]})
    out = {"recordings": len(recs), "unmatched": unmatched, "per_brief_runs": reps,
           "off": {k: metrics.fmt(v) for k, v in metrics.summarize(rows["off"]).items()},
           "on": {k: metrics.fmt(v) for k, v in metrics.summarize(rows["on"]).items()},
           "delta_on_minus_off": {k: metrics.fmt(v) for k, v in metrics.paired(rows["off"], rows["on"]).items()},
           "rows": rows}
    pathlib.Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
